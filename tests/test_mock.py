import json
from agent.mock import (
    MOCK_SAMPLES, MOCK_TOOL_RESULTS, MOCK_SPECIALIST_REPORTS,
    MOCK_CODE_REVIEWS, MockSpecialistClient, MockLeadClient,
    _identify_sample, execute_tool,
)
from agent.schemas import Severity, Grade


def test_three_samples_exist():
    assert set(MOCK_SAMPLES.keys()) == {"user_service", "data_processor", "clean_api"}


def test_sample_has_required_keys():
    for key, sample in MOCK_SAMPLES.items():
        assert "code" in sample
        assert "name" in sample
        assert "hash" in sample
        assert len(sample["code"]) > 50


def test_identify_sample_user_service():
    assert _identify_sample(MOCK_SAMPLES["user_service"]["code"]) == "user_service"


def test_identify_sample_data_processor():
    assert _identify_sample(MOCK_SAMPLES["data_processor"]["code"]) == "data_processor"


def test_identify_sample_clean_api():
    assert _identify_sample(MOCK_SAMPLES["clean_api"]["code"]) == "clean_api"


def test_identify_sample_unknown():
    assert _identify_sample("print('hello')") == "unknown"


def test_tool_results_per_sample():
    for sample_key in ["user_service", "data_processor", "clean_api"]:
        results = MOCK_TOOL_RESULTS[sample_key]
        assert "scan_security_patterns" in results
        assert "trace_logic_flow" in results


def test_execute_tool_known():
    result = execute_tool("scan_security_patterns", {}, "user_service")
    parsed = json.loads(result)
    assert "findings" in parsed
    assert len(parsed["findings"]) > 0


def test_execute_tool_unknown():
    result = execute_tool("nonexistent_tool", {}, "user_service")
    parsed = json.loads(result)
    assert parsed["findings"] == []


def test_specialist_reports_all_specialists():
    for sample_key in ["user_service", "data_processor"]:
        reports = MOCK_SPECIALIST_REPORTS[sample_key]
        assert set(reports.keys()) == {"security", "performance", "maintainability", "bug_detection"}


def test_user_service_has_critical_security():
    sec = MOCK_SPECIALIST_REPORTS["user_service"]["security"]
    critical = [c for c in sec.comments if c.severity == Severity.CRITICAL]
    assert len(critical) >= 2


def test_clean_api_minimal_findings():
    for specialist, report in MOCK_SPECIALIST_REPORTS["clean_api"].items():
        non_info = [c for c in report.comments if c.severity != Severity.INFO]
        assert len(non_info) == 0


def test_code_reviews_grades():
    assert MOCK_CODE_REVIEWS["user_service"].grade == Grade.F
    assert MOCK_CODE_REVIEWS["data_processor"].grade == Grade.D
    assert MOCK_CODE_REVIEWS["clean_api"].grade == Grade.A


def test_user_service_review_has_conflict():
    review = MOCK_CODE_REVIEWS["user_service"]
    assert len(review.conflicts) == 1
    assert "bug_detection" in review.conflicts[0].resolution.lower() or \
           "bug_detection" in str(review.conflicts[0].specialist_positions.keys())


def test_mock_specialist_client_cycles_tools():
    client = MockSpecialistClient("security")
    messages = [{"role": "user", "content": f"Review:\n```\n{MOCK_SAMPLES['user_service']['code']}\n```"}]
    response = client.messages.create(
        model="test", max_tokens=4096, system="test",
        messages=messages,
        tools=[{"name": "scan_security_patterns"}, {"name": "check_auth_flow"}, {"name": "detect_data_exposure"}],
    )
    assert any(b.type == "tool_use" for b in response.content)
    assert response.stop_reason == "tool_use"


def test_mock_specialist_client_final_response():
    client = MockSpecialistClient("security")
    messages = [
        {"role": "user", "content": f"Review:\n```\n{MOCK_SAMPLES['user_service']['code']}\n```"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "c0", "name": "scan_security_patterns", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c0", "content": "{}"}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "c1", "name": "check_auth_flow", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "{}"}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "c2", "name": "detect_data_exposure", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c2", "content": "{}"}]},
    ]
    response = client.messages.create(
        model="test", max_tokens=4096, system="test",
        messages=messages,
        tools=[{"name": "scan_security_patterns"}, {"name": "check_auth_flow"}, {"name": "detect_data_exposure"}],
    )
    text = [b.text for b in response.content if b.type == "text"][0]
    parsed = json.loads(text)
    assert parsed["specialist"] == "security"


def test_mock_lead_client_returns_review():
    client = MockLeadClient()
    messages = [
        {"role": "user", "content": f"Specialist findings for {MOCK_SAMPLES['user_service']['code']}"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "l0", "name": "group_by_location", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "l0", "content": "{}"}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "l1", "name": "check_agreement", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "l1", "content": "{}"}]},
    ]
    response = client.messages.create(
        model="test", max_tokens=4096, system="test",
        messages=messages,
        tools=[{"name": "group_by_location"}, {"name": "check_agreement"}],
    )
    text = [b.text for b in response.content if b.type == "text"][0]
    parsed = json.loads(text)
    assert "grade" in parsed
