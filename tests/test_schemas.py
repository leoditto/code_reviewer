from agent.schemas import (
    Severity, Category, Grade,
    ReviewComment, SpecialistReport, CodeReview,
    AgreementItem, ConflictItem, AgentStep,
    SpecialistTrace, ReviewTrace, EvalScore, AgentConfig,
)


def _make_comment(**overrides):
    defaults = dict(
        line_range=(1, 5), category=Category.BUG, severity=Severity.HIGH,
        title="Test", description="desc", suggestion="fix it",
    )
    defaults.update(overrides)
    return ReviewComment(**defaults)


def test_severity_values():
    assert Severity.CRITICAL.value == "critical"
    assert Severity.INFO.value == "info"


def test_category_values():
    assert Category.SECURITY.value == "security"
    assert Category.BUG.value == "bug"


def test_grade_values():
    assert Grade.A.value == "A"
    assert Grade.F.value == "F"


def test_review_comment_defaults():
    c = _make_comment()
    assert c.file == "<pasted>"
    assert c.confidence == 1.0


def test_specialist_report():
    r = SpecialistReport(specialist="security", comments=[_make_comment()], summary="ok")
    assert r.specialist == "security"
    assert len(r.comments) == 1
    assert r.review_metadata == {}


def test_code_review_roundtrip():
    review = CodeReview(
        grade=Grade.B, summary="ok", total_issues=1,
        merged_findings=[_make_comment()], agreements=[], conflicts=[],
        top_recommendations=["do x"], per_specialist_summaries={"security": "ok"},
    )
    data = review.model_dump(mode="json")
    assert data["grade"] == "B"
    assert data["merged_findings"][0]["severity"] == "high"
    restored = CodeReview.model_validate(data)
    assert restored.grade == Grade.B


def test_agreement_item():
    a = AgreementItem(
        line_range=(10, 14), specialists=["security", "bug_detection"],
        merged_comment=_make_comment(), agreement_strength="strong",
    )
    assert len(a.specialists) == 2


def test_conflict_item():
    c = ConflictItem(
        line_range=(10, 14),
        specialist_positions={"a": _make_comment(), "b": _make_comment(severity=Severity.LOW)},
        resolution="Sided with a.",
        resolved_comment=_make_comment(),
        resolved_severity=Severity.HIGH,
    )
    assert c.resolved_severity == Severity.HIGH


def test_agent_step():
    s = AgentStep(step=1, phase="tool_call", tool_name="scan", tool_input={})
    assert s.reasoning is None


def test_specialist_trace():
    t = SpecialistTrace(specialist="security", steps=[], tool_calls=3, tokens=800, duration_ms=120.5)
    assert t.tool_calls == 3


def test_review_trace():
    st = SpecialistTrace(specialist="s", steps=[], tool_calls=1, tokens=100, duration_ms=50)
    rt = ReviewTrace(code_hash="abc", specialist_traces=[st], lead_trace=st, total_duration_ms=100)
    assert rt.code_hash == "abc"


def test_eval_score():
    e = EvalScore(coverage=0.8, false_positive_rate=0.9, conflict_resolution_quality=1.0,
                  actionability=0.7, overall=0.85)
    assert e.per_specialist == {}


def test_agent_config_defaults():
    c = AgentConfig()
    assert len(c.specialists) == 4
    assert "security" in c.specialists


def test_agent_config_custom():
    c = AgentConfig(specialists=["security", "bug_detection"])
    assert len(c.specialists) == 2
