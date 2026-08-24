# Smart Resume Screener

A hybrid, explainable candidate-intelligence system: it parses resumes and job
descriptions into structured data, matches them with a deterministic
rule-based layer *and* a grounded LLM evaluation layer, and shows its work —
every requirement gets a match level, a verbatim evidence quote, and a
one-sentence reason, not just a number.

## Demo

<video src="https://raw.githubusercontent.com/Nishameela/smart-resume-screener-/main/docs/demo.mp4" controls width="100%"></video>

*(Video not loading? [Watch/download it directly](docs/demo.mp4).)*

## 1. Project Overview

Given a job description and a set of candidate resumes (PDF or plain text),
the system:

1. Extracts structured data from each resume (skills, experience, education).
2. Extracts structured, prioritized requirements from the job description
   (must-have vs preferred).
3. Runs a **hybrid matching engine** — deterministic skill/experience/
   education checks *plus* a grounded LLM evaluation — against every
   requirement.
4. Aggregates the results into one documented, tunable score per candidate.
5. Ranks candidates and shows a full requirement-by-requirement evidence
   breakdown for each one.

## 2. Problem Statement

Resume screening at any scale is either slow (a human reads every resume) or
shallow (a keyword filter counts term overlap). Neither is trustworthy: the
first doesn't scale, and the second is easy to game and impossible to
explain. A hiring team needs something that scales *and* that a recruiter can
actually trust and interrogate — "why did this candidate rank #1?" needs a
real answer, not a black-box percentage.

## 3. Why Naive Keyword Matching Fails

A resume that lists "Python, FastAPI, AWS, Docker, Kubernetes" in a skills
section will beat a genuinely qualified candidate on keyword overlap alone,
even if none of those keywords are backed by real work. The `demo_data/`
dataset includes exactly this case (**Sam Rivera**, the "keyword trap"
candidate) — a resume with dense keyword overlap and zero real backend
engineering experience behind it. A pure deterministic/keyword system scores
this candidate high. This system doesn't, because the grounded LLM stage is
explicitly instructed to treat keyword presence without substantiating
evidence as weak or unsupported (see [Prompt Engineering
Strategy](#9-prompt-engineering-strategy)).

The inverse failure mode also matters: a resume that describes real,
transferable experience using *different* terminology than the JD (Django
instead of FastAPI, Google Cloud instead of AWS) should not be penalized as
though it had no relevant experience at all. `demo_data/` includes this case
too (**Jordan Kim**).

## 4. Why This Solution Is Different

Most naive implementations of this assignment do this:

```
Resume → send everything to one LLM prompt → get back an arbitrary score
```

That's a single point of failure with no explainability and no way to
distinguish a lucky guess from a grounded judgment. This system instead
separates the pipeline into independently testable stages — extraction,
normalization, deterministic matching, semantic evaluation, and score
aggregation — so each stage does one job well and the final output is
traceable back to real evidence. See [Key Design
Decisions](#18-key-design-decisions) for why each separation was worth the
extra structure.

## 5. Architecture Diagram

```
                         ┌─────────────────────┐
                         │   React Frontend     │
                         │ Setup → Rankings →    │
                         │  Candidate Detail     │
                         └──────────┬───────────┘
                                    │ REST (JSON)
                         ┌──────────▼───────────┐
                         │      FastAPI App      │
                         │  (app/api/*, thin)    │
                         └──────────┬───────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                            │
┌───────▼────────┐        ┌─────────▼──────────┐       ┌─────────▼─────────┐
│ File validation  │        │  JD requirement    │       │  Evaluation        │
│ + text extraction│        │  extraction (LLM)  │       │  orchestration     │
│ (pypdf / utf-8)   │        │  Prompt B          │       │                    │
└───────┬────────┘        └─────────┬──────────┘       └─────────┬─────────┘
        │                           │                            │
┌───────▼────────┐                  │                  ┌─────────▼─────────┐
│ Resume structured│                 │                  │ Deterministic      │
│ extraction (LLM)  │                │                  │ matcher (pure fns) │
│ Prompt A          │                │                  │ skill/exp/edu      │
└───────┬────────┘                  │                  └─────────┬─────────┘
        │                           │                            │
┌───────▼────────┐                  │                            │
│ Skill normalizer  │                │                            │
│ (pure, taxonomy)   │               │                            │
└───────┬────────┘                  │                            │
        │                           │                            │
        └─────────────┬─────────────┴──────────────┬─────────────┘
                       │                            │
              ┌────────▼────────┐         ┌─────────▼─────────┐
              │  Grounded LLM     │         │   Scorer (pure)    │
              │  requirement      │────────▶│  weighted avg +    │
              │  evaluation       │         │  missing-must-have │
              │  Prompt C+D       │         │  penalty           │
              └───────────────────┘         └─────────┬─────────┘
                                                        │
                                             ┌──────────▼──────────┐
                                             │   SQLite (SQLAlchemy) │
                                             │  8-table relational   │
                                             │  schema                │
                                             └────────────────────────┘
```

## 6. End-to-End Data Flow

**Resume ingestion:** upload → file validation (type/size/empty) → text
extraction (pypdf for PDF, UTF-8/Latin-1 for text; a scanned PDF with no
text layer fails loudly rather than silently) → content-hash dedup check →
LLM structured extraction (Prompt A) → each extracted skill run through the
deterministic normalizer → persisted (resume + skills + experience +
education rows). An LLM failure here never crashes the request: the resume
is still saved with its raw text and a `FAILED` status + clear
`error_message`.

**JD ingestion:** raw text → validation → content-hash dedup → LLM
requirement extraction (Prompt B) → persisted (JD + prioritized, categorized
requirements).

**Evaluation:** given a `(resume_id, jd_id)` pair → for each requirement, the
deterministic matcher computes whatever rule-based evidence is available
(skill overlap, years-of-experience arithmetic, degree-level comparison) →
that evidence is fed into **one** grounded LLM call (merged Prompt C+D) that
returns a match level, evidence quotes, reasoning, and confidence per
requirement, plus an overall candidate summary → the scorer aggregates
everything into one documented score → persisted and returned. If the LLM
call fails after retries, the evaluation falls back to an honest
deterministic-only score (`llm_status=fallback`) instead of failing or
fabricating a result.

## 7. Matching/Scoring Methodology

The deterministic matcher's evidence is fed **into** the grounded LLM
evaluation as context — the LLM's per-requirement `match_level` is already
evidence-informed, so it is the authoritative per-requirement score, not a
second number to separately blend in.

```
requirement_score = MATCH_LEVEL_SCORES[llm_match_level]
    strong = 100, partial = 60, weak = 30, not_demonstrated = 0

weighted_avg = Σ(requirement_score × weight) / Σ(weight)
    weight: must_have = 2, preferred = 1

missing_must_have_penalty = min(40, 10 × count(must-have requirements marked not_demonstrated))

overall_score = clamp(weighted_avg − missing_must_have_penalty, 0, 100)
```

Every constant above lives in one place, `backend/app/core/scoring_config.py`
— nothing is hardcoded through the scoring logic itself
(`backend/app/services/scorer.py`, a small pure function), so the formula
can be tuned after observing results on the demo dataset without touching
matching or evaluation code.

For transparency, each evaluation also stores two parallel components:
`deterministic_component` (what a pure rule-based system alone would have
scored, over only the requirements where a deterministic signal existed) and
`llm_component` (the grounded score that, after the penalty, becomes
`overall_score`). The Candidate Detail screen shows both side by side —
this is the clearest way to demonstrate what the hybrid approach adds over
keyword matching alone.

Confidence is a weighted average of each requirement's LLM-reported
confidence, using the same must-have/preferred weights.

**Stability:** LLM calls use `temperature=0`, structured tool-use output
(not free-text JSON parsing), and results are cached by
`(resume.content_hash, jd.content_hash)` / `(resume_id, jd_id)` — re-running
the same pair never re-calls the LLM and never drifts.

## 8. AI/LLM Pipeline

| Stage | Prompt | Model setting | Input | Output |
|---|---|---|---|---|
| Resume structuring | Prompt A | `LLM_MODEL_EXTRACTION` (falls back to `LLM_MODEL_DEFAULT`) | Raw resume text | Skills, experience, education (Pydantic-validated) |
| JD analysis | Prompt B | `LLM_MODEL_EXTRACTION` | Raw JD text | Prioritized, categorized requirements |
| Requirement evaluation + summary | Prompt C+D (merged) | `LLM_MODEL_EVALUATION` (falls back to `LLM_MODEL_DEFAULT`) | Resume text + normalized skills + per-requirement deterministic evidence | Per-requirement match level/evidence/reasoning/confidence + strengths/gaps/executive summary/interview focus areas |

All three calls go through **one** wrapper
(`backend/app/core/llm_client.py`) whose public function, `call_structured`,
every service calls identically regardless of which LLM provider is
active. It validates the result with Pydantic before returning it. A
validation failure triggers one corrective retry that tells the model
exactly what was wrong; transient API failures get exponential-backoff
retries up to `LLM_MAX_RETRIES`. This is why structured output is reliable
here instead of fragile "ask for JSON in prose and hope" parsing.

**Provider-agnostic by design.** `LLM_PROVIDER` (`anthropic` or `gemini`)
picks which SDK `call_structured` dispatches to; no other module imports
`anthropic` or `google.genai` directly, and none of them branch on which
provider is active — that isolation is what made switching providers a
one-file, zero-caller-changes change:

- **Anthropic** — forces a single tool call whose `input_schema` *is* the
  JSON schema we want (`SomeModel.model_json_schema()` — one definition,
  no drift between what's requested and what's validated). Anthropic's
  tool-use mechanism guarantees the response is schema-shaped JSON.
- **Gemini** (`google-genai` SDK) — uses Gemini's native structured-output
  JSON mode instead of a forced tool call: `response_mime_type=
  "application/json"` plus `response_json_schema=` the *same*
  Pydantic-derived JSON schema (deliberately `response_json_schema`, not
  the older `response_schema` field — it's the one that reliably accepts
  raw JSON Schema, including the `$defs`/`$ref` our nested Pydantic models
  produce). One schema, two different provider mechanisms for enforcing
  it, same JSON shape out.

In both cases Pydantic validation of the parsed result is the second,
authoritative layer — schema-shaped JSON from the provider is necessary
but not sufficient (it doesn't enforce enum membership, cross-field
semantics, or catch a model that returns syntactically valid but
wrong-shaped JSON), so every response is `response_model.model_validate()`'d
regardless of provider before anything downstream sees it. Provider SDKs
raise different exception types for the same logical failure (a timeout
looks nothing alike in `anthropic` vs `google.genai`); each provider's
invoker normalizes its own exceptions into two internal signals
(retry-worthy vs. not) before the shared retry loop ever sees them, so the
retry/backoff/corrective-retry logic itself is written once and is
provider-independent.

**Model configuration:** every stage defaults to one model,
`LLM_MODEL_DEFAULT`, settable via `.env`. Leaving it blank falls back to a
built-in default for whichever `LLM_PROVIDER` is active, so flipping
`LLM_PROVIDER` alone (without also touching `LLM_MODEL_DEFAULT`) can't
silently send an Anthropic model name to Gemini or vice versa.
`LLM_MODEL_EXTRACTION` and `LLM_MODEL_EVALUATION` are optional overrides
for splitting extraction onto a cheaper/faster model and evaluation onto a
stronger one — no code changes needed, just env vars.

## 9. Prompt Engineering Strategy

Full prompt text lives in `backend/app/prompts/` (never scattered through
service code):

- `resume_extraction.py` (**Prompt A**) — strict extraction, not inference.
  Explicitly instructed: never invent skills/experience/dates not stated,
  never infer years of experience or seniority, null over guessing.
- `jd_analysis.py` (**Prompt B**) — must-have vs preferred classification,
  atomic requirement splitting, explicitly told to skip generic filler
  phrases rather than treat every sentence as an equally weighted
  requirement.
- `requirement_evaluation.py` (**Prompt C+D, merged**) — the most important
  prompt in the system. Grounded with pre-computed deterministic evidence
  per requirement. Critical rules baked into the system prompt:
  - Never fabricate evidence not actually present in the resume text.
  - A keyword mention without demonstrated use is **not** strong evidence —
    this is the specific instruction that defeats the keyword-trap
    candidate.
  - Related-but-not-equivalent evidence (e.g. TensorFlow experience offered
    for a general Machine Learning requirement) can be credited as
    `partial`/`weak` at most, never `strong`, and must say so explicitly —
    this prevents unsafe false equivalences.
  - No autonomous hiring decisions ("hire this candidate" is disallowed;
    "a strong candidate for further review" is the required framing).

## 10. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Async, Pydantic-native validation, auto-generated OpenAPI docs at `/docs`. |
| ORM/DB | SQLAlchemy + SQLite | Zero-setup relational DB (`git clone && run`, no server to stand up) while still exercising real FK/relational modeling. |
| PDF extraction | `pypdf` | Pure-Python, no system dependency (no poppler/tesseract), fails predictably on scanned/corrupted PDFs instead of silently. |
| LLM | Anthropic Claude API **or** Google Gemini API (`anthropic` + `google-genai` SDKs), switchable via `LLM_PROVIDER` | Structured output enforced by the provider (forced tool-use for Claude, native JSON-schema mode for Gemini) plus a second Pydantic validation layer; model and provider fully configurable via env vars, no code changes to switch. |
| Frontend | React + TypeScript + Vite | Fast setup, compile-time contract safety against the backend's schemas. |
| Styling | Tailwind CSS v4 | Dev-only dependency, no runtime cost, fast to build a polished UI without a component-library dependency. |
| Icons | `lucide-react` | Small, tree-shakeable. |
| Testing | `pytest` | Scoring/normalization/extraction logic is pure-function-testable. |

No Redis, no Celery, no vector database, no auth framework, no router/state
library on the frontend (three linear screens don't need one). Every
dependency addition was a deliberate call, not a default.

## 11. Project Structure

```
backend/
├── app/
│   ├── main.py            # app factory, CORS, global exception handler
│   ├── api/                # thin route handlers only
│   ├── core/                # config, database, exceptions, llm_client, scoring_config
│   ├── models/              # SQLAlchemy ORM models + enums
│   ├── schemas/              # Pydantic request/response + LLM I/O schemas
│   ├── services/              # business logic (extraction, matching, scoring)
│   ├── repositories/           # SQLAlchemy queries, isolated from business logic
│   └── prompts/                 # prompt text, one file per LLM stage
├── tests/                        # 112 pytest cases
├── scripts/                       # dev-only fixture/demo-data generators (not shipped functionality)
└── requirements.txt

frontend/
├── src/
│   ├── App.tsx              # 3-screen state machine (no router needed)
│   ├── api/                  # typed fetch client + TS types mirroring backend schemas
│   ├── components/             # SetupScreen, RankingsScreen, CandidateDetailScreen, shared UI
│   └── lib/                      # small formatting helpers
└── package.json

demo_data/          # JD + 4 fictional candidates for the demo (see demo_data/README.md)
scripts/             # ad-hoc Playwright smoke-test scripts (not a project dependency)
```

## 12. Database Design

Eight tables, normalized where it earns its keep:

- **`resumes`** — filename, file_type, raw_text, content_hash (unique, for
  dedup/caching), candidate_name/email, processing_status, error_message.
- **`experience_entries`**, **`education_entries`** — one row per entry,
  FK to `resumes`.
- **`resume_skills`** — raw_text, canonical_name, category, match_type
  (exact/normalized/unmatched), FK to `resumes`.
- **`job_descriptions`** — raw_text, job_title, content_hash.
- **`jd_requirements`** — requirement_text, priority (must_have/preferred),
  category (skill/experience/education/responsibility), FK to
  `job_descriptions`.
- **`evaluations`** — overall_score, deterministic_component, llm_component,
  confidence, ai_summary, strengths/gaps/interview_focus_areas (JSON),
  llm_status, FK to `resumes` and `job_descriptions`.
- **`requirement_matches`** — match_level, evidence (JSON list of quotes),
  reasoning, confidence, FK to `evaluations` and `jd_requirements`. This is
  the table backing the signature evidence matrix.

The skill-normalization *taxonomy* (canonical name → known aliases) is
deliberately **not** a database table — it's static reference data, not
per-run state, so it lives as a versioned, unit-tested Python module
(`app/services/skill_taxonomy.py`). What *is* persisted is the result of
applying it to one resume (`resume_skills.match_type`).

## 13. API Overview

Full interactive docs at `http://localhost:8000/docs` once the backend is
running. Key endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/resumes` | Upload + validate + extract + structure one resume (multipart file) |
| `GET` | `/api/resumes/{id}` | Full resume detail (skills, experience, education) |
| `POST` | `/api/job-descriptions` | Parse a JD into structured requirements |
| `GET` | `/api/job-descriptions/{id}` | JD detail |
| `POST` | `/api/evaluations` | `{resume_id, jd_id}` → run/fetch the hybrid evaluation |
| `GET` | `/api/evaluations?jd_id=` | Ranked list of evaluations for a JD |
| `GET` | `/api/evaluations/{id}` | Full evaluation detail (score breakdown + requirement matrix) |
| `GET` | `/api/health` | Health check |

Errors always return a consistent envelope: `{"error": {"code": "...",
"message": "..."}}` with an appropriate HTTP status (400 validation, 404 not
found, 422 extraction failure, 502 LLM failure, 500 unexpected).

## 14. Setup Instructions

Requires Python 3.11+, Node 20+, and an API key for whichever LLM provider
you use (a free-tier [Gemini API key](https://aistudio.google.com/apikey)
or an [Anthropic API key](https://console.anthropic.com/) — see
[Section 8](#8-aillm-pipeline) for how `LLM_PROVIDER` switches between
them).

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then edit .env: set LLM_PROVIDER and the matching API key

# Frontend
cd ../frontend
npm install
cp .env.example .env            # defaults are fine for local dev
```

## 15. Environment Variables

`backend/.env` (see `backend/.env.example` for the full annotated list):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `anthropic` or `gemini` — which SDK `call_structured` dispatches to |
| `ANTHROPIC_API_KEY` | *(required if `LLM_PROVIDER=anthropic`)* | Your Anthropic API key |
| `GEMINI_API_KEY` | *(required if `LLM_PROVIDER=gemini`)* | Your Gemini API key (free tier works) |
| `LLM_MODEL_DEFAULT` | *(blank → provider's built-in default)* | Model used for every stage unless overridden; blank picks a sensible default for whichever provider is active (`claude-sonnet-5` / `gemini-3.6-flash`) |
| `LLM_MODEL_EXTRACTION` | *(unset → falls back to default)* | Optional override for resume/JD extraction |
| `LLM_MODEL_EVALUATION` | *(unset → falls back to default)* | Optional override for requirement evaluation |
| `LLM_MAX_RETRIES` | `2` | Retry budget (shared between transient API failures and corrective validation retries) |
| `LLM_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLite file path |
| `MAX_UPLOAD_SIZE_MB` | `5` | Resume upload size cap |
| `CORS_ORIGINS` | localhost/127.0.0.1 on 5173 and 4173 | Allowed frontend origins |

`frontend/.env`:

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Backend base URL |

## 16. How to Run

```bash
# Terminal 1
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

Open `http://localhost:5173`, paste a JD (or use `demo_data/job_description.txt`),
upload resumes from `demo_data/`, and click Analyze.

## 17. Testing

```bash
cd backend && source venv/bin/activate
python -m pytest -q
```

112 tests covering: file validation and PDF/text extraction edge cases
(empty, corrupted, scanned/image-only PDFs); the LLM client's retry and
corrective-validation logic **for both providers** (fully mocked, no API
key needed) — including each provider's own exception-normalization code
(Anthropic timeout/status errors, Gemini server/rate-limit/client errors,
blocked responses, invalid JSON) and the `LLM_PROVIDER` config switch
itself; skill normalization (exact/normalized/unmatched, including
explicit guards that TensorFlow is never silently normalized to Machine
Learning and Agile is never conflated with Scrum); the deterministic
matcher's skill/experience/education logic including short-skill-name
false-positive avoidance ("Go" inside "Google"); the scorer's boundary
cases (missing must-have penalty, penalty cap, must-have-outweighs-
preferred, a keyword-trap-vs-transferable regression sanity check); the
evaluation service's success/idempotency/fallback/validation paths,
including the unique-constraint race-condition handling when two
concurrent requests target the same (resume, JD) pair; and full
API-level integration tests for every endpoint.

Two additional ad-hoc Playwright smoke tests live in `scripts/` (not a
project dependency — run manually with `pip install playwright && playwright install chromium`
if you want to reproduce them) that drive the real frontend build with a headless
browser: one against the real backend confirming graceful failure handling,
one with mocked network responses confirming the full Setup → Rankings →
Detail flow renders correctly end to end.

## 18. Key Design Decisions

- **Deterministic evidence grounds the LLM instead of being blended
  independently.** Feeding pre-computed skill/experience/education evidence
  into the same prompt the LLM uses to judge each requirement means the
  LLM's judgment is evidence-informed by construction, not a second opinion
  reconciled after the fact.
- **One LLM call for evaluation, not one per requirement.** Requirement
  matching and the overall summary (originally specified as two prompts)
  are merged into a single structured call per resume-JD pair, cutting
  latency and cost without weakening either half of the output.
- **Content-hash caching does triple duty.** The same mechanism that avoids
  re-processing a duplicate upload also makes scores stable across reruns
  and avoids re-billing the LLM for identical input — one piece of
  engineering solving three stated requirements at once.
- **Scoring constants live in one file, not scattered through the scoring
  logic.** `scoring_config.py` exists specifically so the weights/penalty
  can be tuned after observing results on the demo dataset without
  touching `scorer.py`.
- **No separate Candidate table.** A resume upload *is* the candidate-
  creation event in this app (no multi-resume-per-candidate use case
  exists), so a distinct 1:1 Candidate entity would be pure over-
  normalization.
- **No router/state-management library on the frontend.** Three linear
  screens (Setup → Rankings → Detail) are simpler and more legible as
  explicit `useState`-driven view switching than as URL routes.
- **Uploaded files are processed entirely in memory, never written to
  disk.** The upload handler reads the file into memory, extracts and
  cleans the text, and persists only the extracted text (plus the content
  hash) to the database. There's no raw-file storage to clean up, no stale
  temp files, and no path-traversal surface from user-supplied filenames.

## 19. Trade-offs

- **No embeddings/vector search.** Semantic "relatedness" (TensorFlow ↔
  Machine Learning) is judged by the grounded LLM call, not a vector
  similarity score. This keeps the architecture simple and avoids an
  entire dependency class (vector DB, embedding model, similarity
  thresholds) but means semantic matching quality depends entirely on the
  LLM prompt rather than a tunable numeric similarity.
- **Sequential resume processing in the frontend, not a background job
  queue.** For a handful of demo resumes this is simpler and gives clean
  per-file progress UI; it would not scale to bulk (hundreds of resumes)
  without adding async job processing.
- **Experience-year arithmetic is an approximation.** Overlapping/
  concurrent roles are summed rather than merged (see
  `deterministic_matcher.py`), which can overstate total years for
  candidates with genuinely concurrent roles. Documented, not hidden.

## 20. Limitations

- No OCR: scanned/image-only PDFs are rejected with a clear error rather
  than silently producing empty data.
- The skill taxonomy (`skill_taxonomy.py`) is a curated ~50-skill starter
  set, not exhaustive — extending it is a one-line addition per skill, but
  an unrecognized skill falls back to a weaker literal-text-overlap check.
- Deterministic education/experience matching uses regex/keyword heuristics
  (degree-level synonyms, "N+ years" patterns) that won't catch every
  phrasing; the grounded LLM stage is the real backstop for cases the
  deterministic layer misses.
- Single-organization, no-auth design: this is a screening tool for one
  recruiter/session, not a multi-tenant SaaS product.

## 21. Future Improvements

- Split `LLM_MODEL_EXTRACTION`/`LLM_MODEL_EVALUATION` onto different
  models (e.g. a cheaper model for extraction, a stronger one for
  evaluation) once quality is validated — the config already supports this
  with zero code changes.
- Background job processing for bulk resume uploads.
- A richer, sourced skill taxonomy (e.g. derived from O*NET/ESCO) instead
  of a hand-curated list.
- Exportable candidate reports (PDF/CSV) for sharing outside the app.

## 22. Demo Workflow

See `demo_data/README.md` for the full dataset description. In short:
paste `demo_data/job_description.txt` as the JD, upload all four resumes,
click Analyze, and open the ranked list. The strong-match candidate should
rank first with mostly `strong` requirement matches; the keyword-trap
candidate should rank near the bottom despite dense keyword overlap in its
skills section, with the requirement matrix explaining exactly why
("keyword present but no substantiating evidence in the resume text"); the
transferable-match candidate should score competitively despite having no
exact keyword hits on the named framework/cloud provider, because the
underlying capability is genuinely evidenced.
