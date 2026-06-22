from agent.compare import compare_reviews, _severity_counts
from agent.mock import MOCK_CODE_REVIEWS
from agent.eval import evaluate_review


def test_compare_same_review():
    review = MOCK_CODE_REVIEWS["user_service"]
    score = evaluate_review(review, "user_service")
    result = compare_reviews(review, review, score, score, "Team A", "Team B")
    assert result["shared_findings"] == len(review.merged_findings)
    assert len(result["only_a"]) == 0
    assert len(result["only_b"]) == 0


def test_compare_different_reviews():
    a = MOCK_CODE_REVIEWS["user_service"]
    b = MOCK_CODE_REVIEWS["clean_api"]
    sa = evaluate_review(a, "user_service")
    sb = evaluate_review(b, "clean_api")
    result = compare_reviews(a, b, sa, sb, "Full Team", "Minimal")
    assert result["labels"] == ["Full Team", "Minimal"]
    assert len(result["only_a"]) > 0


def test_compare_has_severity_breakdown():
    a = MOCK_CODE_REVIEWS["user_service"]
    b = MOCK_CODE_REVIEWS["data_processor"]
    sa = evaluate_review(a, "user_service")
    sb = evaluate_review(b, "data_processor")
    result = compare_reviews(a, b, sa, sb, "A", "B")
    assert "A" in result["severity_breakdown"]
    assert "B" in result["severity_breakdown"]
    assert "critical" in result["severity_breakdown"]["A"]


def test_severity_counts():
    review = MOCK_CODE_REVIEWS["user_service"]
    counts = _severity_counts(review)
    assert counts["critical"] >= 2
    assert counts["info"] >= 0
    assert sum(counts.values()) == len(review.merged_findings)
