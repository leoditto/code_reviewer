SECURITY_TOOLS = [
    {
        "name": "scan_security_patterns",
        "description": "Scan source code for common security vulnerabilities: injection risks, auth bypass, data exposure, OWASP Top 10 patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to scan"},
                "language": {"type": "string", "description": "Programming language"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "check_auth_flow",
        "description": "Analyze authentication and authorization patterns: password handling, token validation, session management, access control.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to analyze"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "detect_data_exposure",
        "description": "Detect potential data exposure: hardcoded secrets, PII leakage, insecure logging, missing encryption.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to check"},
            },
            "required": ["code"],
        },
    },
]

PERFORMANCE_TOOLS = [
    {
        "name": "analyze_complexity",
        "description": "Analyze algorithmic complexity of loops, recursion, and data structure operations. Identify O(n^2) or worse patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to analyze"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "check_allocations",
        "description": "Detect unnecessary memory allocations: object creation in loops, repeated list/dict rebuilding, missing object reuse.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to check"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "detect_query_patterns",
        "description": "Analyze database query patterns: N+1 queries, missing indexes, unbounded selects, missing pagination.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to analyze"},
            },
            "required": ["code"],
        },
    },
]

MAINTAINABILITY_TOOLS = [
    {
        "name": "measure_complexity",
        "description": "Measure code complexity: cyclomatic complexity, function length, nesting depth, parameter count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to measure"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "check_naming",
        "description": "Check naming conventions: variable/function naming consistency, abbreviations, misleading names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to check"},
                "language": {"type": "string", "description": "Programming language for convention rules"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "detect_dead_code",
        "description": "Detect dead code: unused imports, unreachable branches, unused variables, commented-out code blocks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to scan"},
            },
            "required": ["code"],
        },
    },
]

BUG_DETECTION_TOOLS = [
    {
        "name": "trace_logic_flow",
        "description": "Trace control flow for logic errors: incorrect conditions, missing edge cases, wrong operator precedence, off-by-one errors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to trace"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "check_null_safety",
        "description": "Check for null/None/undefined safety: unchecked return values, missing null guards, optional chaining gaps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to check"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "detect_race_conditions",
        "description": "Detect potential race conditions: shared mutable state, missing locks, async/await pitfalls, TOCTOU issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to analyze"},
            },
            "required": ["code"],
        },
    },
]

LEAD_TOOLS = [
    {
        "name": "group_by_location",
        "description": "Group specialist findings by code location to identify overlapping reviews on the same lines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "findings": {"type": "string", "description": "JSON array of all specialist findings"},
            },
            "required": ["findings"],
        },
    },
    {
        "name": "check_agreement",
        "description": "Analyze grouped findings to identify agreements (2+ specialists flagged same issue) and conflicts (different severities or contradictory advice).",
        "input_schema": {
            "type": "object",
            "properties": {
                "grouped_findings": {"type": "string", "description": "JSON of grouped findings from group_by_location"},
            },
            "required": ["grouped_findings"],
        },
    },
]

SPECIALIST_TOOLS = {
    "security": SECURITY_TOOLS,
    "performance": PERFORMANCE_TOOLS,
    "maintainability": MAINTAINABILITY_TOOLS,
    "bug_detection": BUG_DETECTION_TOOLS,
    "lead": LEAD_TOOLS,
}
