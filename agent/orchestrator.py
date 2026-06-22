import asyncio
import hashlib
import json
import re
import time

from agent.schemas import (
    AgentConfig, AgentStep, CodeReview, ReviewTrace,
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


def _run_specialist_sync(specialist_name: str, code: str) -> tuple[SpecialistReport, SpecialistTrace]:
    config = SPECIALISTS[specialist_name]
    client = get_specialist_client(specialist_name)
    sample_key = _identify_sample(code)

    messages = [{"role": "user", "content": f"Review this code:\n\n```\n{code}\n```"}]
    steps = []
    step_num = 0
    start_time = time.time()
    total_tokens = 0

    for turn in range(MAX_TURNS):
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

    try:
        json_match = re.search(r'\{.*\}', last_text, re.DOTALL)
        if json_match:
            report = SpecialistReport.model_validate_json(json_match.group())
        else:
            raise ValueError("No JSON found")
    except Exception:
        report = SpecialistReport(
            specialist=specialist_name,
            comments=[],
            summary=last_text[:200] if last_text else "Analysis complete.",
        )

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


def _run_lead_sync(specialist_reports: list[SpecialistReport], code: str) -> tuple[CodeReview, SpecialistTrace]:
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

    try:
        json_match = re.search(r'\{.*\}', last_text, re.DOTALL)
        if json_match:
            review = CodeReview.model_validate_json(json_match.group())
        else:
            raise ValueError("No JSON found")
    except Exception:
        review = CodeReview(
            grade="C", summary=last_text[:200] if last_text else "Review complete.",
            total_issues=0, merged_findings=[], agreements=[], conflicts=[],
            top_recommendations=[], per_specialist_summaries={},
        )

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


async def run_review(code: str, config: AgentConfig | None = None) -> tuple[CodeReview, ReviewTrace]:
    if config is None:
        config = AgentConfig()

    code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
    start_time = time.time()

    specialist_tasks = [
        asyncio.to_thread(_run_specialist_sync, name, code)
        for name in config.specialists
        if name in SPECIALISTS
    ]

    specialist_results = await asyncio.gather(*specialist_tasks)

    reports = [r for r, t in specialist_results]
    specialist_traces = [t for r, t in specialist_results]

    review, lead_trace = await asyncio.to_thread(_run_lead_sync, reports, code)

    total_duration_ms = (time.time() - start_time) * 1000

    trace = ReviewTrace(
        code_hash=code_hash,
        specialist_traces=specialist_traces,
        lead_trace=lead_trace,
        total_duration_ms=total_duration_ms,
    )

    return review, trace
