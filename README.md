# Multi-Agent Code Reviewer

4 specialist AI agents review your code in parallel, then a lead agent synthesizes findings and resolves disagreements.

## Architecture

```
User submits code
        |
        v
+---- asyncio.gather -----------------------+
| Security    Performance                    |
| Maintainability    Bug Detection           |
| (each: own prompt, own tools, own context) |
+-------------------+------------------------+
                    |  4x SpecialistReport
                    v
              Lead Agent
         (merge, deduplicate,
          resolve conflicts)
                    |
                    v
             CodeReview
       (grade, merged findings,
        agreements, conflicts,
        recommendations)
```

Each specialist has isolated context — they can't see each other's work. The lead agent receives all reports and:
- Groups findings by code location
- Identifies where specialists agree (consensus items)
- Resolves conflicts when specialists disagree on severity
- Assigns a final grade (A-F)

## Key Features

- **Parallel multi-agent orchestration** — fan-out/fan-in with `asyncio.gather`
- **Structured disagreement resolution** — when specialists rate the same code differently, the lead explains which it sides with and why
- **Per-specialist tool use** — each agent has 3 domain-specific tools (14 total)
- **Eval framework** — ground-truth scoring across 4 dimensions: coverage, false positive rate, conflict resolution quality, actionability
- **Compare mode** — same code reviewed by different team compositions to see what gets missed
- **Pydantic v2 structured outputs** — typed schemas for all agent I/O

## Tech Stack

Python, FastAPI, Jinja2, Pydantic v2, Anthropic tool_use API

## Quick Start

```bash
pip install -r requirements.txt
python3 -m uvicorn app:app --reload
# open http://localhost:8000
```

Or with Docker:

```bash
docker compose up --build
```

Works out of the box with mock data — no API keys needed. Click "User Service", "Data Processor", or "Clean API" to try the demo samples.

## Mock Samples

| Sample | Grade | Issues | Conflicts | Key Findings |
|--------|-------|--------|-----------|--------------|
| User Service | F | 9 | 1 | SQL injection (CRITICAL), plaintext passwords, null deref |
| Data Processor | D | 8 | 1 | O(n^2) loop, wrong median, division by zero |
| Clean API | A | 1 | 0 | Well-written code, one INFO-level note |

## Tests

```bash
python3 -m pytest tests/ -v
# 84 tests across 7 modules
```

## Project Structure

```
app.py                  FastAPI server
agent/
  schemas.py            Pydantic models (ReviewComment, CodeReview, ConflictItem, etc.)
  tools.py              Per-specialist tool definitions (Anthropic format)
  specialists.py        Specialist configs (prompts, tools, colors)
  orchestrator.py       Fan-out/fan-in orchestration
  mock.py               3 code samples + mock clients
  clients.py            Client factory (mock or real LLM)
  eval.py               Ground-truth evaluation
  guardrails.py         Input validation + injection detection
  store.py              In-memory cache with TTL
  compare.py            Team composition comparison
templates/              Jinja2 HTML (index, review, compare)
static/style.css        Dark theme with specialist colors
tests/                  84 tests
```
