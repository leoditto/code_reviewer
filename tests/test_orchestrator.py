import pytest
import asyncio
from agent.orchestrator import run_review, _run_specialist_sync, _run_lead_sync
from agent.schemas import AgentConfig, Grade, Severity
from agent.mock import MOCK_SAMPLES, MOCK_SPECIALIST_REPORTS


def test_run_specialist_sync_security():
    code = MOCK_SAMPLES["user_service"]["code"]
    report, trace = _run_specialist_sync("security", code)
    assert report.specialist == "security"
    assert len(report.comments) > 0
    assert trace.tool_calls > 0
    assert trace.duration_ms > 0


def test_run_specialist_sync_all_specialists():
    code = MOCK_SAMPLES["data_processor"]["code"]
    for name in ["security", "performance", "maintainability", "bug_detection"]:
        report, trace = _run_specialist_sync(name, code)
        assert report.specialist == name
        assert trace.specialist == name


def test_run_lead_sync():
    code = MOCK_SAMPLES["user_service"]["code"]
    reports = list(MOCK_SPECIALIST_REPORTS["user_service"].values())
    review, trace = _run_lead_sync(reports, code)
    assert review.grade == Grade.F
    assert len(review.conflicts) == 1
    assert trace.specialist == "lead"


@pytest.mark.asyncio
async def test_run_review_user_service():
    code = MOCK_SAMPLES["user_service"]["code"]
    review, trace = await run_review(code)
    assert review.grade == Grade.F
    assert review.total_issues > 0
    assert len(trace.specialist_traces) == 4
    assert trace.lead_trace.specialist == "lead"
    assert trace.total_duration_ms > 0


@pytest.mark.asyncio
async def test_run_review_clean_api():
    code = MOCK_SAMPLES["clean_api"]["code"]
    review, trace = await run_review(code)
    assert review.grade == Grade.A
    assert len(review.conflicts) == 0


@pytest.mark.asyncio
async def test_run_review_custom_config():
    code = MOCK_SAMPLES["user_service"]["code"]
    config = AgentConfig(specialists=["security", "bug_detection"])
    review, trace = await run_review(code, config)
    assert len(trace.specialist_traces) == 2


@pytest.mark.asyncio
async def test_run_review_produces_trace():
    code = MOCK_SAMPLES["data_processor"]["code"]
    review, trace = await run_review(code)
    assert trace.code_hash
    for st in trace.specialist_traces:
        assert st.tool_calls >= 0
        assert st.tokens > 0
