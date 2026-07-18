# 03 - The ApplyPilot System Map

This file teaches the architecture using beginner-friendly language.

## Product Story

ApplyPilot helps a job seeker run a pipeline:

1. Find jobs.
2. Fetch full job details.
3. Score each job against the user's resume.
4. Tailor a resume for strong matches.
5. Generate cover letters.
6. Convert artifacts to PDFs.
7. Auto-apply using browser automation and agent CLIs.

Evidence:

- README describes these six stages in `README.md:9-16`.
- Pipeline stage names are defined in `src/applypilot/pipeline.py:35-44`.
- The database schema groups columns by stage in `src/applypilot/database.py:68-76` and `src/applypilot/database.py:90-133`.

## The Big Diagram

```text
User terminal
  |
  | applypilot run / applypilot apply / applypilot status
  v
src/applypilot/cli.py
  |
  | calls
  v
src/applypilot/pipeline.py
  |
  | calls stage modules
  v
discovery/ -> enrichment/ -> scoring/ -> apply/
  |
  | read/write
  v
SQLite jobs table + files under ~/.applypilot
  |
  | displays
  v
Rich terminal tables / generated HTML dashboard / logs
```

## The Folders

### `src/applypilot/`

The main Python package.

Important files:

- `cli.py`: user commands (`src/applypilot/cli.py:22-438`)
- `config.py`: local paths, env, profile/search config (`src/applypilot/config.py:11-29`, `src/applypilot/config.py:129-238`)
- `database.py`: SQLite state (`src/applypilot/database.py:20-427`)
- `pipeline.py`: stage orchestration (`src/applypilot/pipeline.py:35-480`)
- `llm.py`: LLM API client (`src/applypilot/llm.py:22-154`)
- `view.py`: generated HTML dashboard (`src/applypilot/view.py:25-407`)

### `src/applypilot/discovery/`

Finds job postings.

Key files:

- `jobspy.py`: uses JobSpy and stores results (`src/applypilot/discovery/jobspy.py:21-192`, `src/applypilot/discovery/jobspy.py:454-485`)
- `workday.py`: Workday-specific discovery (`src/applypilot/discovery/workday.py:156-303`)
- `smartextract.py`: smarter extraction from configured sites (`src/applypilot/discovery/smartextract.py:76-126`, `src/applypilot/discovery/smartextract.py:1086-1108`)

### `src/applypilot/enrichment/`

Turns raw job rows into richer job rows.

Key file:

- `detail.py`: loads pages, extracts full descriptions and apply URLs (`src/applypilot/enrichment/detail.py:529-675`, `src/applypilot/enrichment/detail.py:856-881`)

### `src/applypilot/scoring/`

Uses LLMs and validators to score jobs and create application artifacts.

Key files:

- `scorer.py`: assigns fit scores (`src/applypilot/scoring/scorer.py:72-175`)
- `tailor.py`: tailors resumes and writes artifacts (`src/applypilot/scoring/tailor.py:336-548`)
- `validator.py`: checks LLM output for bad content (`src/applypilot/scoring/validator.py:82-180`)
- `cover_letter.py`: generates cover letters (`src/applypilot/scoring/cover_letter.py:115-179`)
- `pdf.py`: converts text artifacts to PDFs (`src/applypilot/scoring/pdf.py:345-407`)

### `src/applypilot/apply/`

Runs auto-apply.

Key files:

- `launcher.py`: claims jobs, launches workers, runs agents, records results (`src/applypilot/apply/launcher.py:174-731`)
- `chrome.py`: manages Chrome processes and worker profiles (`src/applypilot/apply/chrome.py:189-255`)
- `prompt.py`: builds the prompt agents use to fill applications (`src/applypilot/apply/prompt.py:419-565`)
- `dashboard.py`: live Rich dashboard (`src/applypilot/apply/dashboard.py:22-190`)
- `agents/base.py`: shared agent result contracts (`src/applypilot/apply/agents/base.py:10-36`)
- `agents/parsing.py`: parses agent output (`src/applypilot/apply/agents/parsing.py:13-87`)
- `agents/claude_runner.py`: runs Claude CLI (`src/applypilot/apply/agents/claude_runner.py:48-149`)
- `agents/codex_runner.py`: runs Codex CLI (`src/applypilot/apply/agents/codex_runner.py:58-145`)

## How One Job Moves Through The System

Imagine this fake job row:

```python
job = {
    "url": "https://example.com/jobs/123",
    "title": "Platform Engineer",
    "site": "Example Corp",
    "description": "Short listing text",
    "full_description": None,
    "fit_score": None,
    "tailored_resume_path": None,
    "apply_status": None,
}
```

### Discovery

Discovery inserts the initial row.

Real evidence:

- Generic insert helper: `src/applypilot/database.py:329-362`
- JobSpy insert path: `src/applypilot/discovery/jobspy.py:131-192`

Fake before/after:

```python
# Before discovery
jobs_table = []

# After discovery
jobs_table.append({
    "url": "https://example.com/jobs/123",
    "title": "Platform Engineer",
    "site": "Example Corp",
})
```

### Enrichment

Enrichment fills `full_description` and `application_url`.

Real evidence:

- Extraction cascade: `src/applypilot/enrichment/detail.py:529-604`
- DB update: `src/applypilot/enrichment/detail.py:662-674`

Fake before/after:

```python
job["full_description"] = "Long job description..."
job["application_url"] = "https://example.com/apply/123"
job["detail_scraped_at"] = "2026-05-17T12:00:00Z"
```

### Scoring

Scoring fills `fit_score` and `score_reasoning`.

Real evidence:

- Score one job: `src/applypilot/scoring/scorer.py:72-100`
- Persist scores: `src/applypilot/scoring/scorer.py:154-161`

Fake before/after:

```python
job["fit_score"] = 9
job["score_reasoning"] = "Strong Python and automation match"
```

### Tailoring

Tailoring creates files and stores the path.

Real evidence:

- Tailor one resume: `src/applypilot/scoring/tailor.py:336-360`
- Write files and DB updates: `src/applypilot/scoring/tailor.py:467-540`

Fake before/after:

```python
job["tailored_resume_path"] = "~/.applypilot/tailored_resumes/Example_Platform_Engineer.txt"
job["tailored_at"] = "2026-05-17T12:05:00Z"
```

### Apply

Auto-apply claims the job, runs browser/agent automation, and marks the result.

Real evidence:

- Claim job: `src/applypilot/apply/launcher.py:174-271`
- Run job: `src/applypilot/apply/launcher.py:416-568`
- Worker loop final status: `src/applypilot/apply/launcher.py:690-702`

Fake before/after:

```python
job["apply_status"] = "in_progress"
job["agent_id"] = "worker-1"

# Later
job["apply_status"] = "applied"
job["applied_at"] = "2026-05-17T12:10:00Z"
job["agent_id"] = None
```

## What To Memorize First

Do not memorize every function. Memorize these four anchors:

1. `cli.py` is the front door.
2. `pipeline.py` is the assembly line manager.
3. `database.py` is the workflow ledger.
4. `apply/launcher.py` is the risky browser/agent automation center.

## Practice

Open `src/applypilot/database.py:90-133`.

Write every column under one of these headings:

- discovery
- enrichment
- scoring
- tailoring
- cover letter
- apply

Self-grade:

- Strong answer: each column has a stage and a meaning.
- Weak answer: you copy the column names without explaining how a job changes over time.

