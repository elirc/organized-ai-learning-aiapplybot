# Reading Map

## One-Paragraph Mental Model

ApplyPilot is a local Python automation pipeline for job applications. The CLI starts the app, config normalizes user profile/search data, SQLite records every job and stage result, pipeline runners move rows from discovery through scoring and artifact generation, and the apply launcher uses isolated Chrome workers plus Claude/Codex CLI agents to submit or dry-run applications. Think of it as a recruiting assembly line where every job row is a package moving across stations, and the `jobs` table is the shipping label that says what station it reached.

## Top 10 Files To Read In Order

| Order | File | Why Read It Now | Understand Before Reading | Explain After Reading | Key Lines |
| --- | --- | --- | --- | --- | --- |
| 1 | `pyproject.toml` | Identifies package type, deps, and CLI entry. | Python packaging basics. | How `applypilot` becomes a shell command. | `pyproject.toml:20-35`, `pyproject.toml:42-54` |
| 2 | `README.md` | Gives product workflow and setup. | This is a CLI app, not a web app. | The six business stages. | `README.md:9-16`, `README.md:83-139`, `README.md:288-309` |
| 3 | `src/applypilot/cli.py` | User-facing commands live here. | Typer commands map functions to CLI verbs. | What `run`, `apply`, `doctor`, `status`, and `dashboard` do. | `src/applypilot/cli.py:22-45`, `src/applypilot/cli.py:78-124`, `src/applypilot/cli.py:127-220` |
| 4 | `src/applypilot/config.py` | Config is the system's local environment boundary. | Local files live in `~/.applypilot`. | How profile/search/env/tier data are loaded. | `src/applypilot/config.py:11-33`, `src/applypilot/config.py:129-238`, `src/applypilot/config.py:300-440` |
| 5 | `src/applypilot/database.py` | This is the data model and state machine. | SQLite rows represent stage progress. | Why columns mirror pipeline stages. | `src/applypilot/database.py:20-49`, `src/applypilot/database.py:62-140`, `src/applypilot/database.py:186-219` |
| 6 | `src/applypilot/pipeline.py` | Shows orchestration and stage dependencies. | Each stage writes back to SQLite. | Sequential vs streaming execution. | `src/applypilot/pipeline.py:35-55`, `src/applypilot/pipeline.py:62-165`, `src/applypilot/pipeline.py:222-317`, `src/applypilot/pipeline.py:439-480` |
| 7 | `src/applypilot/discovery/jobspy.py` | Best discovery entry point. | JobSpy is optional and loaded lazily. | How external job data becomes rows. | `src/applypilot/discovery/jobspy.py:21-30`, `src/applypilot/discovery/jobspy.py:100-115`, `src/applypilot/discovery/jobspy.py:131-192`, `src/applypilot/discovery/jobspy.py:454-485` |
| 8 | `src/applypilot/enrichment/detail.py` | Shows extraction cascade and Playwright use. | Enrichment adds `full_description` and `application_url`. | Why deterministic extraction is tried before LLM extraction. | `src/applypilot/enrichment/detail.py:529-604`, `src/applypilot/enrichment/detail.py:607-675`, `src/applypilot/enrichment/detail.py:856-881` |
| 9 | `src/applypilot/scoring/tailor.py` | Shows LLM output handling and artifact writing. | LLM outputs are untrusted. | How JSON, validation, judge, files, and DB updates connect. | `src/applypilot/scoring/tailor.py:167-245`, `src/applypilot/scoring/tailor.py:291-360`, `src/applypilot/scoring/tailor.py:430-548` |
| 10 | `src/applypilot/apply/launcher.py` | Most complex full-system workflow. | Jobs must be claimed before browser automation. | How one eligible job becomes an agent run and a DB status. | `src/applypilot/apply/launcher.py:174-271`, `src/applypilot/apply/launcher.py:416-568`, `src/applypilot/apply/launcher.py:602-731` |

## The 3 Most Important Data Flows

### Flow 1: Discovery To Database

`run_pipeline()` calls discovery stage in `src/applypilot/pipeline.py:62-99`. JobSpy loads configuration and crawls in `src/applypilot/discovery/jobspy.py:454-485`. Results are inserted into `jobs` with duplicate handling in `src/applypilot/discovery/jobspy.py:131-192` or the generic helper in `src/applypilot/database.py:329-362`.

### Flow 2: Enrichment To Scoring To Tailoring

Enrichment fills detail fields in `src/applypilot/enrichment/detail.py:529-604` and writes them in `src/applypilot/enrichment/detail.py:662-674`. Scoring selects jobs with descriptions and writes `fit_score` in `src/applypilot/scoring/scorer.py:103-175`. Tailoring selects high-score jobs, validates output, writes artifacts, and updates `tailored_resume_path` in `src/applypilot/scoring/tailor.py:430-548`.

### Flow 3: Ready Job To Auto-Apply Result

The CLI validates local dependencies in `src/applypilot/cli.py:182-218`. `acquire_job()` atomically marks a row `in_progress` in `src/applypilot/apply/launcher.py:174-271`. `worker_loop()` launches Chrome and calls `run_job()` in `src/applypilot/apply/launcher.py:602-731`. `run_job()` builds the prompt, invokes Claude/Codex, maps parsed outcomes, and returns a durable status in `src/applypilot/apply/launcher.py:416-568`.

## 10-Question Pre-Reading Checklist

1. What command does the user run first?
2. Where is the CLI entry point declared?
3. Which file creates the `jobs` table?
4. Which columns show that a job has been enriched?
5. Which columns show that a job is ready to apply?
6. Which stages use LLM calls?
7. Which stages use browser automation?
8. Which files touch personal profile data?
9. Which tests isolate DB paths with `monkeypatch`?
10. What is the safest way to trace one job row end to end?

## Architecture And Code Review Red Flags

- A stage writes a DB column not declared in `src/applypilot/database.py:146-183`.
- A worker can claim a job without setting `apply_status = 'in_progress'`.
- An LLM output is trusted without parsing or validation.
- A prompt includes personal data and then logs it unredacted.
- A browser or CLI process can survive after a timeout.
- A retry path increments attempts inconsistently.
- A feature adds external network behavior without `doctor` or setup guidance.
- A dynamic SQL f-string includes user-controlled values.
- A new artifact path writes outside `APP_DIR`.
- A test relies on the real `~/.applypilot` directory.
