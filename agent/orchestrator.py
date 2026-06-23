import asyncio
import hashlib
import json
import os
import re
import time

from agent.schemas import (
    AgentConfig, AgentStep, CodeReview, ReviewComment, ReviewTrace,
    SpecialistReport, SpecialistTrace,
)
from agent.specialists import SPECIALISTS, LEAD_SYSTEM_PROMPT
from agent.tools import SPECIALIST_TOOLS
from agent.clients import get_specialist_client, get_lead_client
from agent.mock import _identify_sample, execute_tool

MAX_TURNS = 10
MAX_TOOL_RESULT_CHARS = 50_000


class AgentError(Exception):
    pass


def _extract_json(text: str) -> str | None:
    cleaned = re.sub(r'```(?:json)?\s*', '', text).strip()
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    return match.group() if match else None


def _parse_specialist_report(text: str, specialist_name: str) -> SpecialistReport:
    raw = _extract_json(text)
    if not raw:
        return SpecialistReport(specialist=specialist_name, comments=[], summary=text[:300])

    try:
        return SpecialistReport.model_validate_json(raw)
    except Exception:
        pass

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return SpecialistReport(specialist=specialist_name, comments=[], summary=text[:300])

    comments = []
    for f in data.get("comments", data.get("findings", data.get("merged_findings", []))):
        try:
            comments.append(ReviewComment(
                line_range=tuple(f.get("line_range", f.get("lines", [0, 0]))[:2]),
                category=f.get("category", specialist_name if specialist_name != "bug_detection" else "bug"),
                severity=f.get("severity", "medium").lower(),
                title=f.get("title", f.get("type", "Finding")),
                description=f.get("description", f.get("detail", "")),
                suggestion=f.get("suggestion", f.get("fix", "")),
                confidence=float(f.get("confidence", 0.8)),
            ))
        except Exception:
            continue

    return SpecialistReport(
        specialist=data.get("specialist", specialist_name),
        comments=comments,
        summary=data.get("summary", f"Found {len(comments)} issues."),
    )


def _parse_code_review(text: str) -> CodeReview:
    raw = _extract_json(text)
    if not raw:
        return CodeReview(
            grade="C", summary=text[:300], total_issues=0,
            merged_findings=[], agreements=[], conflicts=[],
            top_recommendations=[], per_specialist_summaries={},
        )

    try:
        return CodeReview.model_validate_json(raw)
    except Exception:
        pass

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return CodeReview(
            grade="C", summary=text[:300], total_issues=0,
            merged_findings=[], agreements=[], conflicts=[],
            top_recommendations=[], per_specialist_summaries={},
        )

    findings = []
    for f in data.get("merged_findings", data.get("findings", data.get("comments", []))):
        try:
            findings.append(ReviewComment(
                line_range=tuple(f.get("line_range", f.get("lines", [0, 0]))[:2]),
                category=f.get("category", "bug"),
                severity=f.get("severity", "medium").lower(),
                title=f.get("title", f.get("type", "Finding")),
                description=f.get("description", f.get("detail", "")),
                suggestion=f.get("suggestion", f.get("fix", "")),
            ))
        except Exception:
            continue

    grade = str(data.get("grade", "C")).upper().replace("GRADE.", "")
    if grade not in ("A", "B", "C", "D", "F"):
        grade = "C"

    return CodeReview(
        grade=grade,
        summary=data.get("summary", f"Found {len(findings)} issues."),
        total_issues=data.get("total_issues", len(findings)),
        merged_findings=findings,
        agreements=[],
        conflicts=[],
        top_recommendations=data.get("top_recommendations", data.get("recommendations", [])),
        per_specialist_summaries=data.get("per_specialist_summaries", {}),
    )


def _run_specialist_sync(specialist_name: str, code: str, on_step=None) -> tuple[SpecialistReport, SpecialistTrace]:
    config = SPECIALISTS[specialist_name]
    client = get_specialist_client(specialist_name)
    sample_key = _identify_sample(code)

    messages = [{"role": "user", "content": f"Review this code:\n\n```\n{code}\n```"}]
    steps = []
    step_num = 0
    start_time = time.time()
    total_tokens = 0

    for turn in range(MAX_TURNS):
        if on_step:
            on_step({"type": "llm_call", "turn": turn + 1})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=config.system_prompt,
            messages=messages,
            tools=config.tools,
        )
        total_tokens += response.usage.input_tokens + response.usage.output_tokens

        tool_use_blocks = []
        for block in response.content:
            step_num += 1
            if block.type == "text":
                steps.append(AgentStep(
                    step=step_num, phase="reasoning", reasoning=block.text,
                ))
                if on_step:
                    preview = block.text[:120].replace('\n', ' ')
                    on_step({"type": "reasoning", "preview": preview})
            elif block.type == "tool_use":
                tool_result = execute_tool(block.name, block.input, sample_key)
                if len(tool_result) > MAX_TOOL_RESULT_CHARS:
                    tool_result = tool_result[:MAX_TOOL_RESULT_CHARS] + "\n...(truncated)"

                steps.append(AgentStep(
                    step=step_num, phase="tool_call",
                    tool_name=block.name,
                    tool_input=block.input,
                    tool_output=tool_result[:500],
                ))
                tool_use_blocks.append((block.id, block.name, tool_result))
                if on_step:
                    on_step({"type": "tool_call", "tool": block.name})

        if tool_use_blocks:
            tool_results_content = [
                {"type": "tool_result", "tool_use_id": tid, "content": result}
                for tid, name, result in tool_use_blocks
            ]
            messages.append({"role": "assistant", "content": [
                {"type": "text", "text": b.text} if b.type == "text"
                else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                for b in response.content
            ]})
            messages.append({"role": "user", "content": tool_results_content})
        else:
            break

        if response.stop_reason == "end_turn":
            break

    last_text = ""
    for block in response.content:
        if block.type == "text":
            last_text = block.text

    report = _parse_specialist_report(last_text, specialist_name)

    duration_ms = (time.time() - start_time) * 1000
    tool_call_count = sum(1 for s in steps if s.phase == "tool_call")

    trace = SpecialistTrace(
        specialist=specialist_name,
        steps=steps,
        tool_calls=tool_call_count,
        tokens=total_tokens,
        duration_ms=duration_ms,
    )

    return report, trace


def _run_lead_sync(specialist_reports: list[SpecialistReport], code: str, on_step=None) -> tuple[CodeReview, SpecialistTrace]:
    client = get_lead_client()
    sample_key = _identify_sample(code)

    reports_json = json.dumps([r.model_dump() for r in specialist_reports], indent=2)
    user_message = (
        f"Here are the independent specialist reviews of this code:\n\n"
        f"```\n{code}\n```\n\n"
        f"Specialist findings:\n{reports_json}\n\n"
        f"Merge these findings into a unified CodeReview."
    )

    tools = SPECIALIST_TOOLS["lead"]
    messages = [{"role": "user", "content": user_message}]
    steps = []
    step_num = 0
    start_time = time.time()
    total_tokens = 0

    for turn in range(MAX_TURNS):
        if on_step:
            on_step({"type": "llm_call", "turn": turn + 1})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=LEAD_SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
        )
        total_tokens += response.usage.input_tokens + response.usage.output_tokens

        tool_use_blocks = []
        for block in response.content:
            step_num += 1
            if block.type == "text":
                steps.append(AgentStep(
                    step=step_num, phase="reasoning", reasoning=block.text,
                ))
                if on_step:
                    preview = block.text[:120].replace('\n', ' ')
                    on_step({"type": "reasoning", "preview": preview})
            elif block.type == "tool_use":
                tool_result = execute_tool(block.name, block.input, sample_key)
                if len(tool_result) > MAX_TOOL_RESULT_CHARS:
                    tool_result = tool_result[:MAX_TOOL_RESULT_CHARS] + "\n...(truncated)"

                steps.append(AgentStep(
                    step=step_num, phase="tool_call",
                    tool_name=block.name, tool_input=block.input,
                    tool_output=tool_result[:500],
                ))
                tool_use_blocks.append((block.id, block.name, tool_result))
                if on_step:
                    on_step({"type": "tool_call", "tool": block.name})

        if tool_use_blocks:
            messages.append({"role": "assistant", "content": [
                {"type": "text", "text": b.text} if b.type == "text"
                else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                for b in response.content
            ]})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tid, "content": result}
                for tid, name, result in tool_use_blocks
            ]})
        else:
            break

        if response.stop_reason == "end_turn":
            break

    last_text = ""
    for block in response.content:
        if block.type == "text":
            last_text = block.text

    review = _parse_code_review(last_text)

    duration_ms = (time.time() - start_time) * 1000
    tool_call_count = sum(1 for s in steps if s.phase == "tool_call")

    trace = SpecialistTrace(
        specialist="lead",
        steps=steps,
        tool_calls=tool_call_count,
        tokens=total_tokens,
        duration_ms=duration_ms,
    )

    return review, trace


async def run_review(code: str, config: AgentConfig | None = None, on_progress=None) -> tuple[CodeReview, ReviewTrace]:
    if config is None:
        config = AgentConfig()

    code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
    start_time = time.time()

    async def _notify(event, data=None):
        if on_progress:
            await on_progress(event, data or {})

    active_names = [n for n in config.specialists if n in SPECIALISTS]
    await _notify("start", {"specialists": active_names})

    specialist_results = {}
    specialist_traces_map = {}

    is_mock = os.environ.get("LLM_PROVIDER", "mock").lower() == "mock"
    mock_delays = [0.8, 1.2, 1.6, 1.0] if is_mock and on_progress else [0] * 4

    loop = asyncio.get_event_loop() if on_progress else None

    def _make_step_callback(agent_name):
        if not on_progress:
            return None
        def cb(step_data):
            asyncio.run_coroutine_threadsafe(
                on_progress("agent_step", {"name": agent_name, **step_data}),
                loop,
            )
        return cb

    async def _run_one(name, delay):
        if delay:
            await asyncio.sleep(delay * 0.3)
        await _notify("specialist_start", {"name": name})
        if delay:
            await asyncio.sleep(delay)
        report, trace = await asyncio.to_thread(
            _run_specialist_sync, name, code, _make_step_callback(name),
        )
        if delay:
            trace = SpecialistTrace(
                specialist=trace.specialist, steps=trace.steps,
                tool_calls=trace.tool_calls, tokens=trace.tokens,
                duration_ms=delay * 1000,
            )
        specialist_results[name] = report
        specialist_traces_map[name] = trace
        await _notify("specialist_done", {
            "name": name,
            "findings": len(report.comments),
            "tool_calls": trace.tool_calls,
            "duration_ms": round(trace.duration_ms),
        })

    await asyncio.gather(*[_run_one(n, d) for n, d in zip(active_names, mock_delays)])

    reports = [specialist_results[n] for n in active_names]
    specialist_traces = [specialist_traces_map[n] for n in active_names]

    await _notify("lead_start", {"total_findings": sum(len(r.comments) for r in reports)})

    if is_mock and on_progress:
        await asyncio.sleep(1.5)
    review, lead_trace = await asyncio.to_thread(
        _run_lead_sync, reports, code, _make_step_callback("lead"),
    )

    await _notify("lead_done", {
        "grade": review.grade if isinstance(review.grade, str) else review.grade.value,
        "issues": review.total_issues,
        "conflicts": len(review.conflicts),
        "duration_ms": round(lead_trace.duration_ms),
    })

    total_duration_ms = (time.time() - start_time) * 1000

    trace = ReviewTrace(
        code_hash=code_hash,
        specialist_traces=specialist_traces,
        lead_trace=lead_trace,
        total_duration_ms=total_duration_ms,
    )

    return review, trace
