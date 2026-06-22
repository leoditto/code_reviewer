import hashlib
import json
import re

from agent.schemas import (
    Category, Severity, Grade,
    ReviewComment, SpecialistReport, CodeReview,
    AgreementItem, ConflictItem,
)


# ── Mock Code Samples ──────────────────────────────────────────────────

USER_SERVICE_CODE = '''\
import sqlite3
import os

API_KEY = "sk-prod-abc123xyz789secret"
DB_PATH = "users.db"

def get_db():
    return sqlite3.connect(DB_PATH)

def get_user(username):
    db = get_db()
    query = f"SELECT * FROM users WHERE username = '{username}'"
    result = db.execute(query).fetchone()
    db.close()
    return result

def create_user(username, password):
    db = get_db()
    db.execute(
        f"INSERT INTO users (username, password) VALUES ('{username}', '{password}')"
    )
    db.commit()
    db.close()

def authenticate(username, password):
    user = get_user(username)
    if user[2] == password:
        return {"user": user[1], "token": API_KEY}
    return None

def get_all_users():
    db = get_db()
    users = []
    for user in db.execute("SELECT * FROM users").fetchall():
        profile = db.execute(
            f"SELECT * FROM profiles WHERE user_id = {user[0]}"
        ).fetchone()
        users.append({"user": user, "profile": profile})
    db.close()
    return users

def delete_user(username):
    db = get_db()
    db.execute(f"DELETE FROM users WHERE username = '{username}'")
    db.commit()
    result = get_user(username)
    return result is None
'''

DATA_PROCESSOR_CODE = '''\
import json
import os

def load_records(filepath):
    with open(filepath) as f:
        return json.load(f)

def find_duplicates(records):
    duplicates = []
    for i in range(len(records)):
        for j in range(len(records)):
            if i != j and records[i]["email"] == records[j]["email"]:
                duplicates.append(records[i])
    return duplicates

def process_batch(records):
    results = []
    for record in records:
        cleaned = {}
        for key in record.keys():
            cleaned[key.strip().lower()] = str(record[key]).strip()
        enriched = enrich_record(cleaned)
        results.append(enriched)
    return results

def enrich_record(record):
    all_records = load_records("data/all_records.json")
    for r in all_records:
        if r.get("id") == record.get("id"):
            record.update(r)
    return record

def compute_stats(records):
    values = []
    for r in records:
        values.append(float(r.get("amount", 0)))

    total = sum(values)
    count = len(values)
    avg = total / count

    sorted_vals = sorted(values)
    median = sorted_vals[count // 2]

    above_avg = [v for v in values if v > avg]
    below_avg = [v for v in values if v < avg]

    return {
        "total": total,
        "average": avg,
        "median": median,
        "above_average_count": len(above_avg),
        "below_average_count": len(below_avg),
        "records_processed": count,
    }

def export_results(records, output_dir):
    for i in range(0, len(records)):
        filename = os.path.join(output_dir, f"record_{i}.json")
        with open(filename, "w") as f:
            json.dump(records[i], f)

def main():
    records = load_records("data/input.json")
    dupes = find_duplicates(records)
    print(f"Found {len(dupes)} duplicates")
    processed = process_batch(records)
    stats = compute_stats(processed)
    print(stats)
    export_results(processed, "output/")
'''

CLEAN_API_CODE = '''\
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@dataclass
class User:
    id: int
    name: str
    email: str
    status: Status = Status.ACTIVE


class UserRepository:
    def __init__(self, db):
        self._db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        row = self._db.execute(
            "SELECT id, name, email, status FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return User(
            id=row[0],
            name=row[1],
            email=row[2],
            status=Status(row[3]),
        )

    def update_status(self, user_id: int, status: Status) -> bool:
        result = self._db.execute(
            "UPDATE users SET status = ? WHERE id = ?",
            (status.value, user_id),
        )
        self._db.commit()
        return result.rowcount > 0


class UserService:
    def __init__(self, repo: UserRepository):
        self._repo = repo

    def deactivate(self, user_id: int) -> dict:
        user = self._repo.get_by_id(user_id)
        if user is None:
            return {"error": "User not found", "status": 404}
        if user.status == Status.SUSPENDED:
            return {"error": "Cannot deactivate suspended user", "status": 400}
        success = self._repo.update_status(user_id, Status.INACTIVE)
        if not success:
            return {"error": "Update failed", "status": 500}
        return {"message": f"User {user.name} deactivated", "status": 200}

    def get_user(self, user_id: int) -> dict:
        user = self._repo.get_by_id(user_id)
        if user is None:
            return {"error": "User not found", "status": 404}
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "status": user.status.value,
        }
'''

MOCK_SAMPLES = {
    "user_service": {
        "name": "user_service.py",
        "code": USER_SERVICE_CODE,
        "language": "python",
        "hash": hashlib.sha256(USER_SERVICE_CODE.encode()).hexdigest()[:16],
    },
    "data_processor": {
        "name": "data_processor.py",
        "code": DATA_PROCESSOR_CODE,
        "language": "python",
        "hash": hashlib.sha256(DATA_PROCESSOR_CODE.encode()).hexdigest()[:16],
    },
    "clean_api": {
        "name": "clean_api.py",
        "code": CLEAN_API_CODE,
        "language": "python",
        "hash": hashlib.sha256(CLEAN_API_CODE.encode()).hexdigest()[:16],
    },
}


# ── Mock Tool Results ──────────────────────────────────────────────────

def _identify_sample(code: str) -> str:
    if "API_KEY" in code and "sqlite3" in code:
        return "user_service"
    if "find_duplicates" in code and "enrich_record" in code:
        return "data_processor"
    if "UserRepository" in code and "UserService" in code:
        return "clean_api"
    return "unknown"


MOCK_TOOL_RESULTS = {
    "user_service": {
        "scan_security_patterns": json.dumps({
            "findings": [
                {"type": "sql_injection", "lines": [12, 13], "severity": "critical",
                 "detail": "f-string query building with unsanitized username input"},
                {"type": "sql_injection", "lines": [19, 20], "severity": "critical",
                 "detail": "f-string INSERT with unsanitized username and password"},
                {"type": "plaintext_password", "lines": [19, 25], "severity": "high",
                 "detail": "Passwords stored and compared in plaintext, no hashing"},
            ]
        }),
        "check_auth_flow": json.dumps({
            "findings": [
                {"type": "token_leakage", "lines": [26, 26], "severity": "high",
                 "detail": "API key returned directly as auth token"},
                {"type": "no_rate_limiting", "severity": "medium",
                 "detail": "No rate limiting or brute-force protection on authenticate()"},
            ]
        }),
        "detect_data_exposure": json.dumps({
            "findings": [
                {"type": "hardcoded_secret", "lines": [4, 4], "severity": "medium",
                 "detail": "Production API key hardcoded in source code"},
            ]
        }),
        "analyze_complexity": json.dumps({"findings": []}),
        "check_allocations": json.dumps({"findings": []}),
        "detect_query_patterns": json.dumps({
            "findings": [
                {"type": "n_plus_one", "lines": [32, 36], "severity": "medium",
                 "detail": "Query inside loop: SELECT profiles for each user separately"},
            ]
        }),
        "measure_complexity": json.dumps({
            "findings": [
                {"type": "missing_error_handling", "lines": [25, 26], "severity": "low",
                 "detail": "No null check on user before indexing user[2]"},
            ]
        }),
        "check_naming": json.dumps({
            "findings": [
                {"type": "poor_naming", "lines": [11, 11], "severity": "info",
                 "detail": "Variable 'db' could be more descriptive, e.g. 'connection'"},
            ]
        }),
        "detect_dead_code": json.dumps({"findings": []}),
        "trace_logic_flow": json.dumps({
            "findings": [
                {"type": "unchecked_none", "lines": [25, 26], "severity": "high",
                 "detail": "get_user() can return None but authenticate() indexes result without check"},
            ]
        }),
        "check_null_safety": json.dumps({
            "findings": [
                {"type": "unchecked_return", "lines": [25, 26], "severity": "high",
                 "detail": "user[2] will throw TypeError if get_user returns None"},
            ]
        }),
        "detect_race_conditions": json.dumps({"findings": []}),
    },
    "data_processor": {
        "scan_security_patterns": json.dumps({
            "findings": [
                {"type": "path_traversal", "lines": [5, 6], "severity": "medium",
                 "detail": "filepath passed directly to open() without sanitization"},
            ]
        }),
        "check_auth_flow": json.dumps({"findings": []}),
        "detect_data_exposure": json.dumps({"findings": []}),
        "analyze_complexity": json.dumps({
            "findings": [
                {"type": "quadratic_loop", "lines": [10, 14], "severity": "high",
                 "detail": "O(n^2) nested loop comparing all records against all records"},
                {"type": "repeated_io", "lines": [25, 28], "severity": "medium",
                 "detail": "load_records() called inside enrich_record() which is called per-record"},
            ]
        }),
        "check_allocations": json.dumps({
            "findings": [
                {"type": "allocation_in_loop", "lines": [19, 21], "severity": "medium",
                 "detail": "New dict created per record in loop; could reuse or use comprehension"},
            ]
        }),
        "detect_query_patterns": json.dumps({"findings": []}),
        "measure_complexity": json.dumps({
            "findings": [
                {"type": "function_too_long", "lines": [32, 49], "severity": "low",
                 "detail": "compute_stats is 18 lines with mixed concerns (calculation + formatting)"},
                {"type": "magic_number", "lines": [10, 14], "severity": "info",
                 "detail": "Duplicate detection logic uses implicit equality check without configurable threshold"},
            ]
        }),
        "check_naming": json.dumps({
            "findings": [
                {"type": "poor_naming", "lines": [19, 19], "severity": "info",
                 "detail": "Variable 'r' in enrich_record loop is ambiguous"},
            ]
        }),
        "detect_dead_code": json.dumps({"findings": []}),
        "trace_logic_flow": json.dumps({
            "findings": [
                {"type": "off_by_one", "lines": [42, 42], "severity": "high",
                 "detail": "median = sorted_vals[count // 2] is wrong for even-length lists"},
                {"type": "division_by_zero", "lines": [40, 40], "severity": "high",
                 "detail": "avg = total / count will crash if records is empty"},
            ]
        }),
        "check_null_safety": json.dumps({
            "findings": [
                {"type": "unchecked_get", "lines": [35, 35], "severity": "low",
                 "detail": "r.get('amount', 0) defaults to 0 but float() could fail on non-numeric strings"},
            ]
        }),
        "detect_race_conditions": json.dumps({"findings": []}),
    },
    "clean_api": {
        "scan_security_patterns": json.dumps({"findings": []}),
        "check_auth_flow": json.dumps({"findings": []}),
        "detect_data_exposure": json.dumps({
            "findings": [
                {"type": "email_in_response", "lines": [56, 56], "severity": "info",
                 "detail": "Email returned in API response; consider if PII filtering is needed"},
            ]
        }),
        "analyze_complexity": json.dumps({"findings": []}),
        "check_allocations": json.dumps({"findings": []}),
        "detect_query_patterns": json.dumps({"findings": []}),
        "measure_complexity": json.dumps({"findings": []}),
        "check_naming": json.dumps({"findings": []}),
        "detect_dead_code": json.dumps({"findings": []}),
        "trace_logic_flow": json.dumps({"findings": []}),
        "check_null_safety": json.dumps({"findings": []}),
        "detect_race_conditions": json.dumps({"findings": []}),
    },
}


# ── Mock Specialist Reports ───────────────────────────────────────────

MOCK_SPECIALIST_REPORTS = {
    "user_service": {
        "security": SpecialistReport(
            specialist="security",
            comments=[
                ReviewComment(line_range=(12, 13), category=Category.SECURITY, severity=Severity.CRITICAL,
                    title="SQL Injection", description="User input interpolated directly into SQL query via f-string. Attacker can inject arbitrary SQL.",
                    suggestion="Use parameterized queries: db.execute('SELECT * FROM users WHERE username = ?', (username,))"),
                ReviewComment(line_range=(19, 20), category=Category.SECURITY, severity=Severity.CRITICAL,
                    title="SQL Injection in INSERT", description="Username and password interpolated into INSERT statement without sanitization.",
                    suggestion="Use parameterized query: db.execute('INSERT INTO users VALUES (?, ?)', (username, hashed_pw))"),
                ReviewComment(line_range=(19, 25), category=Category.SECURITY, severity=Severity.HIGH,
                    title="Plaintext Password Storage", description="Passwords stored and compared in plaintext. No hashing applied.",
                    suggestion="Use bcrypt or argon2: hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())"),
                ReviewComment(line_range=(26, 26), category=Category.SECURITY, severity=Severity.HIGH,
                    title="API Key Leaked as Auth Token", description="Hardcoded API key returned as authentication token to client.",
                    suggestion="Generate unique JWT tokens per session instead of returning a static API key."),
                ReviewComment(line_range=(4, 4), category=Category.SECURITY, severity=Severity.MEDIUM,
                    title="Hardcoded Secret", description="Production API key hardcoded in source. Will be exposed in version control.",
                    suggestion="Use environment variables: os.environ.get('API_KEY')"),
            ],
            summary="Critical security vulnerabilities found. SQL injection in multiple endpoints allows full database compromise. Passwords stored in plaintext. Hardcoded production secret.",
        ),
        "performance": SpecialistReport(
            specialist="performance",
            comments=[
                ReviewComment(line_range=(32, 36), category=Category.PERFORMANCE, severity=Severity.MEDIUM,
                    title="N+1 Query Pattern", description="Loop executes a separate SELECT for each user's profile. For 1000 users, this is 1001 queries.",
                    suggestion="Use a JOIN: SELECT u.*, p.* FROM users u LEFT JOIN profiles p ON p.user_id = u.id"),
            ],
            summary="One N+1 query pattern found in get_all_users. Otherwise acceptable for a simple service.",
        ),
        "maintainability": SpecialistReport(
            specialist="maintainability",
            comments=[
                ReviewComment(line_range=(25, 26), category=Category.MAINTAINABILITY, severity=Severity.LOW,
                    title="Missing Error Handling", description="No check if user is None before indexing. Will crash with TypeError on invalid username.",
                    suggestion="Add guard: if user is None: return None"),
                ReviewComment(line_range=(11, 11), category=Category.MAINTAINABILITY, severity=Severity.INFO,
                    title="Vague Variable Name", description="Variable 'db' doesn't convey it's a connection object.",
                    suggestion="Rename to 'conn' or 'connection' for clarity."),
            ],
            summary="Code is simple but lacks defensive programming. Missing null checks and vague naming reduce maintainability.",
        ),
        "bug_detection": SpecialistReport(
            specialist="bug_detection",
            comments=[
                ReviewComment(line_range=(25, 26), category=Category.BUG, severity=Severity.HIGH,
                    title="Null Dereference", description="get_user() returns None for missing users, but authenticate() accesses user[2] without check. This will raise TypeError.",
                    suggestion="Add null guard: if user is None: return None"),
            ],
            summary="Critical null dereference bug in authenticate(). get_user can return None but the result is indexed without checking.",
        ),
    },
    "data_processor": {
        "security": SpecialistReport(
            specialist="security",
            comments=[
                ReviewComment(line_range=(5, 6), category=Category.SECURITY, severity=Severity.MEDIUM,
                    title="Unsanitized File Path", description="filepath passed directly to open() without validation. Could allow path traversal.",
                    suggestion="Validate filepath against allowed directory: os.path.abspath(filepath).startswith(ALLOWED_DIR)"),
            ],
            summary="One medium-severity path traversal risk. Otherwise no significant security issues.",
        ),
        "performance": SpecialistReport(
            specialist="performance",
            comments=[
                ReviewComment(line_range=(10, 14), category=Category.PERFORMANCE, severity=Severity.HIGH,
                    title="O(n^2) Duplicate Detection", description="Nested loop compares every record against every other record. For 10k records this is 100M comparisons.",
                    suggestion="Use a set for O(n) detection: seen = set(); dupes = [r for r in records if r['email'] in seen or seen.add(r['email'])]"),
                ReviewComment(line_range=(25, 28), category=Category.PERFORMANCE, severity=Severity.MEDIUM,
                    title="Repeated File I/O in Loop", description="load_records() is called for every record during enrichment, re-reading the entire JSON file each time.",
                    suggestion="Load the enrichment data once before the loop and pass it as a parameter."),
                ReviewComment(line_range=(19, 21), category=Category.PERFORMANCE, severity=Severity.MEDIUM,
                    title="Unnecessary Allocation per Record", description="New dict created per record with manual key iteration. Could use dict comprehension.",
                    suggestion="Use comprehension: cleaned = {k.strip().lower(): str(v).strip() for k, v in record.items()}"),
            ],
            summary="Significant performance issues. O(n^2) duplicate detection and repeated file I/O will not scale beyond small datasets.",
        ),
        "maintainability": SpecialistReport(
            specialist="maintainability",
            comments=[
                ReviewComment(line_range=(10, 14), category=Category.MAINTAINABILITY, severity=Severity.MEDIUM,
                    title="Complex Loop Logic", description="Nested loop for duplicate detection is hard to reason about and could be replaced with a clearer pattern.",
                    suggestion="Extract to a named function using a set-based approach for clarity."),
                ReviewComment(line_range=(32, 49), category=Category.MAINTAINABILITY, severity=Severity.LOW,
                    title="Function Too Long", description="compute_stats mixes calculation, sorting, and filtering in one function. Hard to test individual parts.",
                    suggestion="Split into compute_basic_stats() and compute_distribution()."),
            ],
            summary="Moderate maintainability concerns. Complex duplicate detection logic and a long stats function reduce readability.",
        ),
        "bug_detection": SpecialistReport(
            specialist="bug_detection",
            comments=[
                ReviewComment(line_range=(42, 42), category=Category.BUG, severity=Severity.HIGH,
                    title="Incorrect Median Calculation", description="sorted_vals[count // 2] gives wrong median for even-length lists. Should average middle two values.",
                    suggestion="For even length: median = (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2"),
                ReviewComment(line_range=(40, 40), category=Category.BUG, severity=Severity.HIGH,
                    title="Division by Zero", description="avg = total / count will crash with ZeroDivisionError if records list is empty.",
                    suggestion="Add guard: if not values: return {'error': 'no records'}"),
            ],
            summary="Two high-severity bugs found. Median calculation is incorrect for even-length lists and division by zero on empty input.",
        ),
    },
    "clean_api": {
        "security": SpecialistReport(
            specialist="security",
            comments=[],
            summary="No security vulnerabilities found. Parameterized queries used correctly. No hardcoded secrets.",
        ),
        "performance": SpecialistReport(
            specialist="performance",
            comments=[],
            summary="No performance issues found. Simple CRUD operations with appropriate query patterns.",
        ),
        "maintainability": SpecialistReport(
            specialist="maintainability",
            comments=[],
            summary="Clean code structure. Good use of dataclasses, enums, and type hints. Functions are focused and well-named.",
        ),
        "bug_detection": SpecialistReport(
            specialist="bug_detection",
            comments=[
                ReviewComment(line_range=(56, 56), category=Category.BUG, severity=Severity.INFO,
                    title="Email in Response", description="Email returned in get_user response. Not a bug, but consider PII filtering depending on consumer.",
                    suggestion="Consider a UserResponse DTO that excludes sensitive fields for public-facing endpoints."),
            ],
            summary="No bugs found. Proper null checks, clean control flow, and correct status handling.",
        ),
    },
}


# ── Mock Synthesized Reviews ──────────────────────────────────────────

MOCK_CODE_REVIEWS = {
    "user_service": CodeReview(
        grade=Grade.F,
        summary="Critical security vulnerabilities make this code unsafe for any environment. SQL injection allows full database compromise, passwords are stored in plaintext, and a production API key is hardcoded. A null dereference bug in authentication will crash on invalid usernames.",
        total_issues=9,
        merged_findings=[
            ReviewComment(line_range=(12, 13), category=Category.SECURITY, severity=Severity.CRITICAL,
                title="SQL Injection", description="User input interpolated directly into SQL query via f-string.",
                suggestion="Use parameterized queries: db.execute('SELECT * FROM users WHERE username = ?', (username,))"),
            ReviewComment(line_range=(19, 20), category=Category.SECURITY, severity=Severity.CRITICAL,
                title="SQL Injection in INSERT", description="Username and password interpolated into INSERT statement.",
                suggestion="Use parameterized query with hashed password."),
            ReviewComment(line_range=(19, 25), category=Category.SECURITY, severity=Severity.HIGH,
                title="Plaintext Password Storage", description="Passwords stored and compared without hashing.",
                suggestion="Use bcrypt or argon2 for password hashing."),
            ReviewComment(line_range=(25, 26), category=Category.BUG, severity=Severity.HIGH,
                title="Null Dereference in Authentication", description="authenticate() indexes user[2] without checking if get_user() returned None.",
                suggestion="Add null guard: if user is None: return None"),
            ReviewComment(line_range=(26, 26), category=Category.SECURITY, severity=Severity.HIGH,
                title="API Key Leaked as Auth Token", description="Hardcoded API key returned as authentication token.",
                suggestion="Generate unique JWT tokens per session."),
            ReviewComment(line_range=(4, 4), category=Category.SECURITY, severity=Severity.MEDIUM,
                title="Hardcoded Secret", description="Production API key in source code.",
                suggestion="Use environment variables."),
            ReviewComment(line_range=(32, 36), category=Category.PERFORMANCE, severity=Severity.MEDIUM,
                title="N+1 Query Pattern", description="Separate profile query per user in loop.",
                suggestion="Use a JOIN query."),
            ReviewComment(line_range=(11, 11), category=Category.MAINTAINABILITY, severity=Severity.INFO,
                title="Vague Variable Name", description="'db' doesn't convey it's a connection.",
                suggestion="Rename to 'conn'."),
        ],
        agreements=[
            AgreementItem(
                line_range=(25, 26),
                specialists=["maintainability", "bug_detection"],
                merged_comment=ReviewComment(line_range=(25, 26), category=Category.BUG, severity=Severity.HIGH,
                    title="Null Dereference in Authentication",
                    description="Both maintainability and bug detection agents identified that authenticate() will crash when get_user() returns None.",
                    suggestion="Add null guard: if user is None: return None"),
                agreement_strength="moderate",
            ),
        ],
        conflicts=[
            ConflictItem(
                line_range=(25, 26),
                specialist_positions={
                    "maintainability": ReviewComment(line_range=(25, 26), category=Category.MAINTAINABILITY, severity=Severity.LOW,
                        title="Missing Error Handling", description="No null check before indexing.", suggestion="Add guard clause."),
                    "bug_detection": ReviewComment(line_range=(25, 26), category=Category.BUG, severity=Severity.HIGH,
                        title="Null Dereference", description="Will raise TypeError on None.", suggestion="Add null guard."),
                },
                resolution="Sided with bug_detection. This is not just a style issue — it's a crash bug. authenticate() will throw TypeError when given an invalid username, which is a normal user action, not an edge case.",
                resolved_comment=ReviewComment(line_range=(25, 26), category=Category.BUG, severity=Severity.HIGH,
                    title="Null Dereference in Authentication",
                    description="authenticate() indexes user[2] without checking if get_user() returned None.",
                    suggestion="Add null guard: if user is None: return None"),
                resolved_severity=Severity.HIGH,
            ),
        ],
        top_recommendations=[
            "Replace all f-string SQL with parameterized queries immediately",
            "Implement password hashing with bcrypt before any deployment",
            "Move API key to environment variables and generate per-session tokens",
            "Add null checks for all database query return values",
            "Replace N+1 query with a JOIN",
        ],
        per_specialist_summaries={
            "security": "Critical security vulnerabilities found. SQL injection in multiple endpoints allows full database compromise.",
            "performance": "One N+1 query pattern found in get_all_users.",
            "maintainability": "Missing null checks and vague naming reduce maintainability.",
            "bug_detection": "Critical null dereference bug in authenticate().",
        },
    ),
    "data_processor": CodeReview(
        grade=Grade.D,
        summary="Performance bottlenecks will prevent this code from scaling. O(n^2) duplicate detection, repeated file I/O per record, and two correctness bugs (wrong median, division by zero) need immediate attention.",
        total_issues=8,
        merged_findings=[
            ReviewComment(line_range=(10, 14), category=Category.PERFORMANCE, severity=Severity.HIGH,
                title="O(n^2) Duplicate Detection", description="Nested loop comparing every record pair.",
                suggestion="Use a set for O(n) detection."),
            ReviewComment(line_range=(42, 42), category=Category.BUG, severity=Severity.HIGH,
                title="Incorrect Median Calculation", description="Wrong for even-length lists.",
                suggestion="Average the two middle values for even-length lists."),
            ReviewComment(line_range=(40, 40), category=Category.BUG, severity=Severity.HIGH,
                title="Division by Zero", description="Crashes on empty input.",
                suggestion="Add empty list guard."),
            ReviewComment(line_range=(25, 28), category=Category.PERFORMANCE, severity=Severity.MEDIUM,
                title="Repeated File I/O", description="File re-read per record during enrichment.",
                suggestion="Load enrichment data once before the loop."),
            ReviewComment(line_range=(19, 21), category=Category.PERFORMANCE, severity=Severity.MEDIUM,
                title="Unnecessary Allocation", description="New dict per record via manual iteration.",
                suggestion="Use dict comprehension."),
            ReviewComment(line_range=(5, 6), category=Category.SECURITY, severity=Severity.MEDIUM,
                title="Unsanitized File Path", description="Path traversal risk in load_records.",
                suggestion="Validate against allowed directory."),
            ReviewComment(line_range=(32, 49), category=Category.MAINTAINABILITY, severity=Severity.LOW,
                title="Function Too Long", description="compute_stats mixes concerns.",
                suggestion="Split into focused functions."),
            ReviewComment(line_range=(19, 19), category=Category.MAINTAINABILITY, severity=Severity.INFO,
                title="Ambiguous Variable Name", description="'r' in loop is vague.",
                suggestion="Use descriptive name like 'enrichment_record'."),
        ],
        agreements=[
            AgreementItem(
                line_range=(10, 14),
                specialists=["performance", "maintainability"],
                merged_comment=ReviewComment(line_range=(10, 14), category=Category.PERFORMANCE, severity=Severity.HIGH,
                    title="O(n^2) Duplicate Detection",
                    description="Both performance and maintainability agents flagged the nested loop. Performance for scaling, maintainability for complexity.",
                    suggestion="Use a set for O(n) detection with clearer logic."),
                agreement_strength="moderate",
            ),
        ],
        conflicts=[
            ConflictItem(
                line_range=(10, 14),
                specialist_positions={
                    "performance": ReviewComment(line_range=(10, 14), category=Category.PERFORMANCE, severity=Severity.HIGH,
                        title="O(n^2) Duplicate Detection", description="Will not scale.", suggestion="Use set-based approach."),
                    "maintainability": ReviewComment(line_range=(10, 14), category=Category.MAINTAINABILITY, severity=Severity.MEDIUM,
                        title="Complex Loop Logic", description="Hard to reason about.", suggestion="Extract to named function."),
                },
                resolution="Sided with performance (HIGH). While the maintainability concern is valid, the O(n^2) scaling is the primary issue — this code will time out on real datasets. The fix (set-based approach) addresses both concerns.",
                resolved_comment=ReviewComment(line_range=(10, 14), category=Category.PERFORMANCE, severity=Severity.HIGH,
                    title="O(n^2) Duplicate Detection", description="Nested loop comparing every record pair.",
                    suggestion="Use a set for O(n) detection."),
                resolved_severity=Severity.HIGH,
            ),
        ],
        top_recommendations=[
            "Replace O(n^2) duplicate detection with set-based O(n) approach",
            "Fix median calculation for even-length lists",
            "Add empty input guard to prevent division by zero",
            "Cache enrichment data — load file once, not per-record",
            "Validate file paths before opening",
        ],
        per_specialist_summaries={
            "security": "One medium-severity path traversal risk.",
            "performance": "Significant performance issues. O(n^2) loop and repeated file I/O.",
            "maintainability": "Complex duplicate logic and long stats function.",
            "bug_detection": "Two high-severity bugs: wrong median and division by zero.",
        },
    ),
    "clean_api": CodeReview(
        grade=Grade.A,
        summary="Well-structured code with proper use of dataclasses, enums, type hints, and parameterized queries. No security vulnerabilities or bugs found. One minor consideration around PII in API responses.",
        total_issues=1,
        merged_findings=[
            ReviewComment(line_range=(56, 56), category=Category.BUG, severity=Severity.INFO,
                title="Email in Response", description="Email returned in API response. Consider PII filtering.",
                suggestion="Consider a UserResponse DTO that excludes sensitive fields."),
        ],
        agreements=[],
        conflicts=[],
        top_recommendations=[
            "Consider adding a response DTO to control which fields are exposed",
        ],
        per_specialist_summaries={
            "security": "No security vulnerabilities found.",
            "performance": "No performance issues found.",
            "maintainability": "Clean structure with good patterns.",
            "bug_detection": "No bugs found.",
        },
    ),
}


# ── Mock Clients ──────────────────────────────────────────────────────

class _MockResponse:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = type("Usage", (), {"input_tokens": 500, "output_tokens": 300})()


class _TextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _ToolUseBlock:
    def __init__(self, tool_id, name, tool_input):
        self.type = "tool_use"
        self.id = tool_id
        self.name = name
        self.input = tool_input


class _MockMessages:
    def __init__(self, specialist):
        self._specialist = specialist

    def create(self, *, model, max_tokens, system, messages, tools=None):
        sample_key = self._detect_sample(messages)
        tool_calls_so_far = sum(
            1 for m in messages if m.get("role") == "user"
            and isinstance(m.get("content"), list)
            and any(b.get("type") == "tool_result" for b in m["content"])
        )

        tool_names = [t["name"] for t in (tools or [])]

        if tool_calls_so_far < len(tool_names):
            tool_name = tool_names[tool_calls_so_far]
            return _MockResponse(
                content=[
                    _TextBlock(f"Running {tool_name} analysis..."),
                    _ToolUseBlock(f"call_{tool_calls_so_far}", tool_name, {"code": "..."}),
                ],
                stop_reason="tool_use",
            )

        report = MOCK_SPECIALIST_REPORTS.get(sample_key, {}).get(self._specialist)
        if report:
            return _MockResponse(content=[_TextBlock(report.model_dump_json())])

        return _MockResponse(content=[_TextBlock(json.dumps({
            "specialist": self._specialist,
            "comments": [],
            "summary": "No significant issues found.",
        }))])

    def _detect_sample(self, messages):
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                key = _identify_sample(content)
                if key != "unknown":
                    return key
        return "unknown"


class MockSpecialistClient:
    def __init__(self, specialist: str):
        self.messages = _MockMessages(specialist)


class _MockLeadMessages:
    def create(self, *, model, max_tokens, system, messages, tools=None):
        tool_calls_so_far = sum(
            1 for m in messages if m.get("role") == "user"
            and isinstance(m.get("content"), list)
            and any(b.get("type") == "tool_result" for b in m["content"])
        )

        if tools and tool_calls_so_far < len(tools):
            tool = tools[tool_calls_so_far]
            return _MockResponse(
                content=[
                    _TextBlock(f"Analyzing specialist findings with {tool['name']}..."),
                    _ToolUseBlock(f"lead_{tool_calls_so_far}", tool["name"], {"findings": "..."}),
                ],
                stop_reason="tool_use",
            )

        sample_key = self._detect_sample(messages)
        review = MOCK_CODE_REVIEWS.get(sample_key)
        if review:
            return _MockResponse(content=[_TextBlock(review.model_dump_json())])

        return _MockResponse(content=[_TextBlock(json.dumps({
            "grade": "B",
            "summary": "Code review complete. No major issues found.",
            "total_issues": 0,
            "merged_findings": [],
            "agreements": [],
            "conflicts": [],
            "top_recommendations": [],
            "per_specialist_summaries": {},
        }))])

    def _detect_sample(self, messages):
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                key = _identify_sample(content)
                if key != "unknown":
                    return key
                for sample_key in MOCK_SAMPLES:
                    if sample_key in content:
                        return sample_key
        return "unknown"


class MockLeadClient:
    def __init__(self):
        self.messages = _MockLeadMessages()


def execute_tool(name: str, tool_input: dict, sample_hint: str = "unknown") -> str:
    results = MOCK_TOOL_RESULTS.get(sample_hint, {})
    if name in results:
        return results[name]
    return json.dumps({"findings": [], "note": f"No mock data for tool {name}"})
