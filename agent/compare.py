from agent.schemas import CodeReview, EvalScore


def compare_reviews(
    review_a: CodeReview,
    review_b: CodeReview,
    eval_a: EvalScore,
    eval_b: EvalScore,
    config_a_label: str = "Team A",
    config_b_label: str = "Team B",
) -> dict:
    findings_a = {f.title.lower() for f in review_a.merged_findings}
    findings_b = {f.title.lower() for f in review_b.merged_findings}

    only_a = findings_a - findings_b
    only_b = findings_b - findings_a
    shared = findings_a & findings_b

    return {
        "labels": [config_a_label, config_b_label],
        "grades": [review_a.grade, review_b.grade],
        "issue_counts": [review_a.total_issues, review_b.total_issues],
        "shared_findings": len(shared),
        "only_a": [f.model_dump() for f in review_a.merged_findings if f.title.lower() in only_a],
        "only_b": [f.model_dump() for f in review_b.merged_findings if f.title.lower() in only_b],
        "severity_breakdown": {
            config_a_label: _severity_counts(review_a),
            config_b_label: _severity_counts(review_b),
        },
        "eval": {
            config_a_label: eval_a.model_dump(),
            config_b_label: eval_b.model_dump(),
        },
    }


def _severity_counts(review: CodeReview) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in review.merged_findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
    return counts
