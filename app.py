import os
import asyncio
import hashlib
import time
import re

import json as _json

from fastapi import FastAPI, Form, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from agent.orchestrator import run_review, AgentError
from agent.schemas import AgentConfig
from agent.eval import evaluate_review
from agent.store import ReviewStore
from agent.guardrails import InputGuardError, validate_code_input
from agent.compare import compare_reviews
from agent.mock import MOCK_SAMPLES

app = FastAPI(title="Multi-Agent Code Reviewer")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

store = ReviewStore()
rate_limit_log: dict[str, list[float]] = {}

API_KEY = os.environ.get("REVIEWER_API_KEY")
security = HTTPBearer(auto_error=False)


def _check_rate_limit(client_ip: str, max_requests: int = 5, window: int = 60) -> bool:
    now = time.time()
    timestamps = rate_limit_log.get(client_ip, [])
    timestamps = [t for t in timestamps if now - t < window]
    rate_limit_log[client_ip] = timestamps
    if len(timestamps) >= max_requests:
        return False
    timestamps.append(now)
    return True


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not API_KEY:
        return
    if not credentials or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _detect_sample_key(code: str) -> str | None:
    for key, sample in MOCK_SAMPLES.items():
        if sample["code"].strip() == code.strip():
            return key
    return None


# ── Web UI ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "index.html", {
        "error": error or None,
        "mock_samples": MOCK_SAMPLES,
    })


@app.post("/review", response_class=HTMLResponse)
async def review(request: Request, code_input: str = Form("")):
    import urllib.parse

    if not code_input.strip():
        return RedirectResponse(url="/?error=" + urllib.parse.quote("Please paste some code to review."), status_code=303)

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return RedirectResponse(url="/?error=" + urllib.parse.quote("Rate limit exceeded. Please wait a minute."), status_code=303)

    try:
        code = validate_code_input(code_input)
    except InputGuardError as e:
        return RedirectResponse(url="/?error=" + urllib.parse.quote(str(e)), status_code=303)

    code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
    cached_id = store.get_by_hash(code_hash)
    if cached_id:
        return RedirectResponse(url=f"/review/{cached_id}", status_code=303)

    try:
        code_review, trace = await asyncio.wait_for(run_review(code), timeout=300)
    except asyncio.TimeoutError:
        return RedirectResponse(url="/?error=" + urllib.parse.quote("Analysis timed out. Please try again."), status_code=303)
    except (AgentError, Exception) as e:
        import traceback
        traceback.print_exc()
        msg = f"Analysis failed: {e}" if isinstance(e, AgentError) else f"An unexpected error occurred: {e}"
        return RedirectResponse(url="/?error=" + urllib.parse.quote(msg), status_code=303)

    sample_key = _detect_sample_key(code)
    eval_score = evaluate_review(code_review, sample_key)
    review_id = hashlib.md5(code_hash.encode()).hexdigest()[:8]

    store.put(review_id, {
        "review": code_review.model_dump(mode="json"),
        "trace": trace.model_dump(mode="json"),
        "eval": eval_score.model_dump(mode="json"),
        "source_lines": code.splitlines(),
        "sample_key": sample_key,
    }, code_hash=code_hash)

    return RedirectResponse(url=f"/review/{review_id}", status_code=303)


@app.get("/review/{review_id}", response_class=HTMLResponse)
async def review_page(request: Request, review_id: str):
    data = store.get(review_id)
    if not data:
        raise HTTPException(status_code=404, detail="Review not found")

    return templates.TemplateResponse(request, "review.html", {
        "review": data["review"],
        "trace": data["trace"],
        "eval": data["eval"],
        "source_lines": data.get("source_lines", []),
        "review_id": review_id,
    })


# ── SSE Review ────────────────────────────────────────────────────────

@app.post("/review/stream")
async def review_stream(request: Request):
    body = await request.json()
    code_input = body.get("code", "")

    if not code_input.strip():
        return JSONResponse({"error": "Please paste some code to review."}, status_code=400)

    try:
        code = validate_code_input(code_input)
    except InputGuardError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
    cached_id = store.get_by_hash(code_hash)
    if cached_id:
        return JSONResponse({"cached": True, "review_id": cached_id})

    progress_queue: asyncio.Queue = asyncio.Queue()

    async def on_progress(event, data):
        await progress_queue.put({"event": event, **data})

    async def generate():
        task = asyncio.create_task(_run_review_and_store(code, code_hash, progress_queue, on_progress))
        while True:
            try:
                msg = await asyncio.wait_for(progress_queue.get(), timeout=310)
            except asyncio.TimeoutError:
                yield f"data: {_json.dumps({'event': 'error', 'message': 'Timed out'})}\n\n"
                break
            yield f"data: {_json.dumps(msg)}\n\n"
            if msg.get("event") in ("done", "error"):
                break
        await task

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _run_review_and_store(code, code_hash, queue, on_progress):
    try:
        code_review, trace = await run_review(code, on_progress=on_progress)
        sample_key = _detect_sample_key(code)
        eval_score = evaluate_review(code_review, sample_key)
        review_id = hashlib.md5(code_hash.encode()).hexdigest()[:8]

        store.put(review_id, {
            "review": code_review.model_dump(mode="json"),
            "trace": trace.model_dump(mode="json"),
            "eval": eval_score.model_dump(mode="json"),
            "source_lines": code.splitlines(),
            "sample_key": sample_key,
        }, code_hash=code_hash)

        await queue.put({"event": "done", "review_id": review_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        await queue.put({"event": "error", "message": str(e)})


# ── Compare ────────────────────────────────────────────────────────────

@app.get("/compare", response_class=HTMLResponse)
async def compare_page(request: Request):
    return templates.TemplateResponse(request, "compare_input.html", {
        "error": None,
        "mock_samples": MOCK_SAMPLES,
    })


@app.post("/compare", response_class=HTMLResponse)
async def compare(
    request: Request,
    code_input: str = Form(""),
    team_a: str = Form("security,performance,maintainability,bug_detection"),
    team_b: str = Form("security,bug_detection"),
):
    if not code_input.strip():
        return templates.TemplateResponse(request, "compare_input.html", {
            "error": "Please paste code to compare.",
            "mock_samples": MOCK_SAMPLES,
        }, status_code=400)

    try:
        code = validate_code_input(code_input)
    except InputGuardError as e:
        return templates.TemplateResponse(request, "compare_input.html", {
            "error": str(e),
            "mock_samples": MOCK_SAMPLES,
        }, status_code=400)

    config_a = AgentConfig(specialists=[s.strip() for s in team_a.split(",")])
    config_b = AgentConfig(specialists=[s.strip() for s in team_b.split(",")])

    try:
        (review_a, trace_a), (review_b, trace_b) = await asyncio.wait_for(
            asyncio.gather(run_review(code, config_a), run_review(code, config_b)),
            timeout=60,
        )
    except Exception as e:
        return templates.TemplateResponse(request, "compare_input.html", {
            "error": f"Analysis failed: {e}",
            "mock_samples": MOCK_SAMPLES,
        }, status_code=500)

    sample_key = _detect_sample_key(code)
    eval_a = evaluate_review(review_a, sample_key)
    eval_b = evaluate_review(review_b, sample_key)

    label_a = "All Specialists" if len(config_a.specialists) == 4 else " + ".join(config_a.specialists)
    label_b = "All Specialists" if len(config_b.specialists) == 4 else " + ".join(config_b.specialists)

    comparison = compare_reviews(review_a, review_b, eval_a, eval_b, label_a, label_b)

    return templates.TemplateResponse(request, "compare.html", {
        "a": {"review": review_a.model_dump(mode="json"), "eval": eval_a.model_dump(mode="json"), "label": label_a},
        "b": {"review": review_b.model_dump(mode="json"), "eval": eval_b.model_dump(mode="json"), "label": label_b},
        "comparison": comparison,
    })


# ── JSON API ───────────────────────────────────────────────────────────

@app.post("/api/review", dependencies=[Depends(verify_api_key)])
async def api_review(request: Request):
    body = await request.json()
    code = body.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code field")

    try:
        code = validate_code_input(code)
    except InputGuardError as e:
        raise HTTPException(status_code=400, detail=str(e))

    code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
    cached_id = store.get_by_hash(code_hash)
    if cached_id:
        data = store.get(cached_id)
        return JSONResponse({"review": data["review"], "eval": data["eval"], "cached": True})

    try:
        code_review, trace = await asyncio.wait_for(run_review(code), timeout=300)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Analysis timed out")

    sample_key = _detect_sample_key(code)
    eval_score = evaluate_review(code_review, sample_key)
    review_id = hashlib.md5(code_hash.encode()).hexdigest()[:8]

    store.put(review_id, {
        "review": code_review.model_dump(mode="json"),
        "trace": trace.model_dump(mode="json"),
        "eval": eval_score.model_dump(mode="json"),
        "source_lines": code.splitlines(),
    }, code_hash=code_hash)

    return JSONResponse({
        "review": code_review.model_dump(mode="json"),
        "eval": eval_score.model_dump(mode="json"),
        "trace": trace.model_dump(mode="json"),
        "review_id": review_id,
        "cached": False,
    })
