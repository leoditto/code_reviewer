from agent.schemas import EvalScore, CodeReview, Severity

GROUND_TRUTH = {
    # user_service
    "user_service": {
        "expected_issues": [
            {"line_range": (12, 13), "category": "security", "severity": "critical", "keyword": "sql injection"},
            {"line_range": (19, 20), "category": "security", "severity": "critical", "keyword": "sql injection"},
            {"line_range": (19, 25), "category": "security", "severity": "high", "keyword": "plaintext password"},
            {"line_range": (26, 26), "category": "security", "severity": "high", "keyword": "api key"},
            {"line_range": (4, 4), "category": "security", "severity": "medium", "keyword": "hardcoded"},
            {"line_range": (32, 36), "category": "performance", "severity": "medium", "keyword": "n+1"},
            {"line_range": (25, 26), "category": "bug", "severity": "high", "keyword": "null"},
        ],
        "expected_conflicts": [
            {"line_range": (25, 26), "expected_winner": "bug_detection", "expected_severity": "high"},
        ],
        "expected_grade": "F",
        "is_clean": False,
    },
    # data_processor
    "data_processor": {
        "expected_issues": [
            {"line_range": (10, 14), "category": "performance", "severity": "high", "keyword": "o(n"},
            {"line_range": (25, 28), "category": "performance", "severity": "medium", "keyword": "file"},
            {"line_range": (19, 21), "category": "performance", "severity": "medium", "keyword": "allocation"},
            {"line_range": (42, 42), "category": "bug", "severity": "high", "keyword": "median"},
            {"line_range": (40, 40), "category": "bug", "severity": "high", "keyword": "division"},
            {"line_range": (5, 6), "category": "security", "severity": "medium", "keyword": "path"},
        ],
        "expected_conflicts": [
            {"line_range": (10, 14), "expected_winner": "performance", "expected_severity": "high"},
        ],
        "expected_grade": "D",
        "is_clean": False,
    },
    # clean_api
    "clean_api": {
        "expected_issues": [],
        "expected_conflicts": [],
        "expected_grade": "A",
        "is_clean": True,
    },
}


def _lines_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def evaluate_review(review: CodeReview, sample_key: str | None = None) -> EvalScore:
    gt = GROUND_TRUTH.get(sample_key) if sample_key else None

    if gt is None:
        return _heuristic_eval(review)

    # Coverage: how many expected issues were found
    expected = gt["expected_issues"]
    if expected:
        found_count = 0
        for exp in expected:
            for f in review.merged_findings:
                if (exp["keyword"].lower() in f.title.lower() or
                    exp["keyword"].lower() in f.description.lower()):
                    if _lines_overlap(f.line_range, tuple(exp["line_range"])):
                        found_count += 1
                        break
        coverage = found_count / len(expected)
    else:
        coverage = 1.0

    # False positive rate
    if gt["is_clean"]:
        non_info = [f for f in review.merged_findings if f.severity != Severity.INFO]
        false_positive_rate = 1.0 - min(len(non_info) / 3, 1.0) if non_info else 1.0
    else:
        false_positive_rate = 0.8

    # Conflict resolution quality
    expected_conflicts = gt["expected_conflicts"]
    if expected_conflicts:
        resolved_correctly = 0
        for ec in expected_conflicts:
            for conflict in review.conflicts:
                if _lines_overlap(conflict.line_range, tuple(ec["line_range"])):
                    if conflict.resolved_severity.value == ec["expected_severity"]:
                        resolved_correctly += 1
                    break
        conflict_quality = resolved_correctly / len(expected_conflicts)
    else:
        conflict_quality = 1.0 if not review.conflicts else 0.5

    # Actionability: suggestions are concrete
    actionable_count = 0
    action_keywords = ["replace", "add", "remove", "use", "change", "implement", "move", "split", "rename"]
    for f in review.merged_findings:
        if len(f.suggestion) > 30 and any(k in f.suggestion.lower() for k in action_keywords):
            actionable_count += 1
    actionability = actionable_count / max(len(review.merged_findings), 1)

    overall = (
        coverage * 0.30
        + false_positive_rate * 0.20
        + conflict_quality * 0.25
        + actionability * 0.25
    )

    per_specialist = {}
    if expected:
        for cat in ["security", "performance", "maintainability", "bug"]:
            cat_expected = [e for e in expected if e["category"] == cat]
            if cat_expected:
                cat_found = 0
                for exp in cat_expected:
                    for f in review.merged_findings:
                        if (exp["keyword"].lower() in f.title.lower() or
                            exp["keyword"].lower() in f.description.lower()):
                            cat_found += 1
                            break
                specialist_name = "bug_detection" if cat == "bug" else cat
                per_specialist[specialist_name] = cat_found / len(cat_expected)

    return EvalScore(
        coverage=round(coverage, 3),
        false_positive_rate=round(false_positive_rate, 3),
        conflict_resolution_quality=round(conflict_quality, 3),
        actionability=round(actionability, 3),
        overall=round(overall, 3),
        per_specialist=per_specialist,
    )


def _heuristic_eval(review: CodeReview) -> EvalScore:
    has_findings = len(review.merged_findings) > 0
    has_recommendations = len(review.top_recommendations) > 0
    has_summaries = len(review.per_specialist_summaries) > 0

    completeness = sum([
        0.3 if has_findings or review.grade in ("A", "B") else 0,
        0.3 if has_recommendations else 0,
        0.2 if has_summaries else 0,
        0.2 if review.summary else 0,
    ])

    actionable_count = 0
    action_keywords = ["replace", "add", "remove", "use", "change", "implement"]
    for f in review.merged_findings:
        if len(f.suggestion) > 30 and any(k in f.suggestion.lower() for k in action_keywords):
            actionable_count += 1
    actionability = actionable_count / max(len(review.merged_findings), 1)

    return EvalScore(
        coverage=0.5,
        false_positive_rate=0.5,
        conflict_resolution_quality=0.5,
        actionability=round(actionability, 3),
        overall=round((0.5 * 0.30 + 0.5 * 0.20 + 0.5 * 0.25 + actionability * 0.25), 3),
        per_specialist={},
    )
