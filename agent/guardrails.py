import re


class InputGuardError(Exception):
    pass


MAX_INPUT_CHARS = 50_000

INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"ignore\s+(all\s+)?previous",
        r"disregard\s+(all\s+)?prior",
        r"system\s*prompt",
        r"you\s+are\s+(now|a)\s+",
        r"act\s+as\s+(a\s+)?",
        r"pretend\s+to\s+be",
        r"jailbreak",
        r"do\s+anything\s+now",
        r"override\s+(your|all)\s+",
        r"forget\s+(your|all|previous)\s+",
        r"new\s+instructions?\s*:",
        r"<\s*script\b",
        r"javascript\s*:",
        r"on(error|load|click)\s*=",
    ]
]


def validate_code_input(code: str) -> str:
    code = code.strip()

    if not code:
        raise InputGuardError("No code provided.")

    if len(code) > MAX_INPUT_CHARS:
        raise InputGuardError(f"Input too large ({len(code)} chars). Maximum is {MAX_INPUT_CHARS}.")

    if len(code) < 20:
        raise InputGuardError("Input is too short to be meaningful code.")

    code_indicators = [
        r'\bdef\s+\w+',
        r'\bfunction\s+\w+',
        r'\bclass\s+\w+',
        r'\bimport\s+',
        r'\bconst\s+',
        r'\blet\s+',
        r'\bvar\s+',
        r'\breturn\s+',
        r'\bif\s*\(',
        r'\bfor\s*\(',
        r'\bwhile\s*\(',
        r'=\s*function',
        r'=>',
        r'public\s+(static\s+)?',
        r'#include\s*<',
    ]
    if not any(re.search(p, code) for p in code_indicators):
        raise InputGuardError(
            "Input does not appear to be source code. "
            "Expected function definitions, imports, or control flow statements."
        )

    injection_flags = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(code):
            injection_flags.append(pattern.pattern)

    if len(injection_flags) >= 3:
        raise InputGuardError("Input contains suspicious patterns.")

    return code


def sanitize_tool_result(result: str) -> str:
    for pattern in INJECTION_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def validate_review_output(review) -> list[str]:
    flags = []

    if hasattr(review, "merged_findings") and len(review.merged_findings) > 30:
        flags.append(f"Excessive findings count: {len(review.merged_findings)}")

    if hasattr(review, "summary") and len(review.summary) > 2000:
        flags.append(f"Anomalous summary length: {len(review.summary)}")

    if hasattr(review, "summary"):
        for pattern in INJECTION_PATTERNS:
            if pattern.search(review.summary):
                flags.append("Potential injection in summary")
                break

    return flags
