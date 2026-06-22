from enum import Enum
from pydantic import BaseModel


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    BUG = "bug"


class Grade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class ReviewComment(BaseModel):
    file: str = "<pasted>"
    line_range: tuple[int, int]
    category: Category
    severity: Severity
    title: str
    description: str
    suggestion: str
    confidence: float = 1.0


class SpecialistReport(BaseModel):
    specialist: str
    comments: list[ReviewComment]
    summary: str
    review_metadata: dict = {}


class AgreementItem(BaseModel):
    line_range: tuple[int, int]
    specialists: list[str]
    merged_comment: ReviewComment
    agreement_strength: str  # "strong" or "moderate"


class ConflictItem(BaseModel):
    line_range: tuple[int, int]
    specialist_positions: dict[str, ReviewComment]
    resolution: str
    resolved_comment: ReviewComment
    resolved_severity: Severity


class CodeReview(BaseModel):
    grade: Grade
    summary: str
    total_issues: int
    merged_findings: list[ReviewComment]
    agreements: list[AgreementItem]
    conflicts: list[ConflictItem]
    top_recommendations: list[str]
    per_specialist_summaries: dict[str, str]
    review_metadata: dict = {}


class AgentStep(BaseModel):
    step: int
    phase: str  # "reasoning" or "tool_call"
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: str | None = None
    reasoning: str | None = None


class SpecialistTrace(BaseModel):
    specialist: str
    steps: list[AgentStep]
    tool_calls: int
    tokens: int
    duration_ms: float


class ReviewTrace(BaseModel):
    code_hash: str
    specialist_traces: list[SpecialistTrace]
    lead_trace: SpecialistTrace
    total_duration_ms: float
    guardrail_flags: list[str] = []


class EvalScore(BaseModel):
    coverage: float
    false_positive_rate: float
    conflict_resolution_quality: float
    actionability: float
    overall: float
    per_specialist: dict[str, float] = {}
    details: dict = {}


class AgentConfig(BaseModel):
    specialists: list[str] = ["security", "performance", "maintainability", "bug_detection"]
