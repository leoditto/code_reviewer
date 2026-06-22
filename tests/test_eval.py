from agent.eval import evaluate_review, _lines_overlap, GROUND_TRUTH
from agent.mock import MOCK_CODE_REVIEWS


def test_lines_overlap_true():
    assert _lines_overlap((1, 5), (3, 7))
    assert _lines_overlap((3, 7), (1, 5))
    assert _lines_overlap((1, 5), (5, 10))


def test_lines_overlap_false():
    assert not _lines_overlap((1, 5), (6, 10))
    assert not _lines_overlap((10, 20), (1, 5))


def test_user_service_eval():
    review = MOCK_CODE_REVIEWS["user_service"]
    score = evaluate_review(review, "user_service")
    assert score.coverage > 0.5
    assert score.conflict_resolution_quality > 0
    assert score.overall > 0
    assert "security" in score.per_specialist


def test_data_processor_eval():
    review = MOCK_CODE_REVIEWS["data_processor"]
    score = evaluate_review(review, "data_processor")
    assert score.coverage > 0.5
    assert score.overall > 0


def test_clean_api_eval():
    review = MOCK_CODE_REVIEWS["clean_api"]
    score = evaluate_review(review, "clean_api")
    assert score.false_positive_rate == 1.0
    assert score.overall > 0.5


def test_unknown_sample_heuristic():
    review = MOCK_CODE_REVIEWS["clean_api"]
    score = evaluate_review(review, None)
    assert score.coverage == 0.5
    assert score.false_positive_rate == 0.5


def test_eval_dimensions_bounded():
    for key in ["user_service", "data_processor", "clean_api"]:
        review = MOCK_CODE_REVIEWS[key]
        score = evaluate_review(review, key)
        assert 0 <= score.coverage <= 1
        assert 0 <= score.false_positive_rate <= 1
        assert 0 <= score.conflict_resolution_quality <= 1
        assert 0 <= score.actionability <= 1
        assert 0 <= score.overall <= 1


def test_ground_truth_has_expected_keys():
    for key in ["user_service", "data_processor", "clean_api"]:
        gt = GROUND_TRUTH[key]
        assert "expected_issues" in gt
        assert "expected_conflicts" in gt
        assert "expected_grade" in gt
        assert "is_clean" in gt
