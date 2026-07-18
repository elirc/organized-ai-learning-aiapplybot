# scoring/tailor.py — Resume Tailoring Engine

**File:** `src/applypilot/scoring/tailor.py` (563 lines)
**Role:** The heaviest AI stage — generates a customized resume for each high-scoring job, with multi-layer validation.

---

## What This File Does

For each job with a fit score >= 7, this module:
1. Sends the base resume + job description to an LLM
2. Gets back a JSON-structured tailored resume
3. Validates it with programmatic checks (banned words, fabrication detection)
4. Validates it with an LLM "judge" (catches subtle lies)
5. Assembles the final text with a code-injected header
6. Saves as .txt and converts to PDF

This is the **most complex AI interaction** in the system — it involves multiple LLM calls, structured output parsing, and a validation pipeline.

---

## The Key Design Decision: JSON Output + Code Assembly

```
LLM returns JSON:
  {
    "title": "Senior DevOps Engineer",
    "summary": "...",
    "skills": {"Languages": "...", "Frameworks": "..."},
    "experience": [...],
    "projects": [...]
  }

Code assembles the resume:
  Jane Smith                    ← code-injected from profile
  Senior DevOps Engineer        ← from JSON
  jane@email.com | 555-1234     ← code-injected from profile

  SUMMARY
  ...                           ← from JSON
```

### Why Not Let the LLM Generate the Full Text?

**The header problem.** If the LLM generates the header (name, email, phone), it might:
- Misspell the name
- Use the wrong phone format
- Invent a LinkedIn URL
- Forget to include the email

By code-injecting the header from the profile, these bugs are impossible. The LLM only controls the content sections (summary, skills, experience, projects), where creativity is desired.

### Why JSON Instead of Plaintext?

JSON gives us **structural guarantees**:
- We know where the summary ends and skills begin
- We can validate each section independently
- We can count bullets per section
- We can check for banned words in specific fields

With plaintext, parsing would require heuristic regex — fragile and error-prone.

---

## The Tailoring Prompt

```python
def _build_tailor_prompt(profile):
    return f"""You are a senior technical recruiter rewriting a resume.

    ## RECRUITER SCAN (6 seconds):
    1. Title -- matches what they're hiring?
    2. Summary -- 2 sentences proving you've done this work
    3. First 3 bullets of most recent role -- verbs and outcomes match?
    4. Skills -- must-haves visible immediately?

    ## SKILLS BOUNDARY (real skills only):
    {skills_block}

    You MAY add 2-3 closely related tools. No unrelated languages/frameworks.

    ## VOICE:
    - GOOD: "Automated financial reporting with Python + API integrations"
    - BAD: "Leveraged cutting-edge AI technologies to drive efficiencies"
    - NEVER use: passionate, dedicated, leveraging, spearheaded, robust..."""
```

### The 6-Second Scan

Recruiters spend an average of 6 seconds on initial resume review. The prompt is structured around this reality — it tells the LLM to optimize for those critical first impressions.

### Skills Boundary

```python
boundary = profile.get("skills_boundary", {})
for category, items in boundary.items():
    skills_lines.append(f"{label}: {', '.join(items)}")
```

The skills boundary is a **truth constraint**. The user's profile lists all skills they actually have. The LLM can reorder these and add 2-3 closely related tools, but cannot invent skills from a completely different domain (e.g., adding "Rust" to a Python engineer's resume).

### Banned Words

The prompt explicitly bans corporate buzzwords:
```
passionate, dedicated, leveraging, spearheaded, robust, cutting-edge,
proven track record, eager, stakeholders, synergy, seamless, streamlined
```

These words are red flags to experienced recruiters. They signal a generic, mass-produced resume rather than a thoughtful one.

---

## The Retry Strategy: Fresh Context

```python
for attempt in range(max_retries + 1):
    prompt = tailor_prompt_base
    if avoid_notes:
        prompt += "\n\n## AVOID THESE ISSUES:\n" + "\n".join(f"- {n}" for n in avoid_notes[-5:])

    messages = [
        {"role": "system", "content": prompt},       # fresh system prompt
        {"role": "user", "content": f"ORIGINAL RESUME:\n{resume_text}\n\nTARGET JOB:\n{job_text}"},
    ]

    raw = client.chat(messages, max_tokens=2048, temperature=0.4)
```

### Why Fresh Conversations?

Each retry starts a **new conversation** (fresh `messages` list). The alternative — continuing the conversation with "try again, and fix X" — leads to **apologetic spirals**:

```
LLM (attempt 1): Here's the tailored resume...
User: You used a banned word. Fix it.
LLM (attempt 2): I apologize for the error. Let me rewrite without... [but now introduces fabrication]
User: You fabricated a skill. Fix it.
LLM (attempt 3): I'm so sorry. Let me remove... [but now the resume is too short]
```

Fresh conversations break this cycle. Each attempt gets the same clear instructions plus a list of specific issues to avoid from previous attempts.

---

## Two-Layer Validation

### Layer 1: Programmatic Validator

```python
validation = validate_json_fields(data, profile)
if not validation["passed"]:
    avoid_notes.extend(validation["errors"])
    continue  # retry
```

The validator (in `validator.py`) checks:
- **Banned words** — "spearheaded", "leveraged", etc.
- **Skills boundary** — no skills from outside the allowed list
- **Metric inflation** — real numbers weren't changed
- **Em dash replacement** — auto-fixes `—` to `-`
- **Section completeness** — required fields present

### Layer 2: LLM Judge

```python
judge = judge_tailored_resume(original_text, tailored_text, job_title, profile)
if not judge["passed"]:
    avoid_notes.append(f"Judge rejected: {judge['issues']}")
    continue  # retry
```

The judge is a **separate LLM call** that compares the original and tailored resumes:

```python
judge_prompt = f"""You are a resume quality judge. Catch LIES, not style changes.

What IS fabrication (FAIL):
1. Adding tools not in the original skills list
2. Inventing new metrics not in the original
3. Adding companies or degrees that don't exist

What IS NOT fabrication (do NOT fail):
- Rewording bullets heavily
- Combining or splitting bullets
- Dropping bullets entirely
- Changing title or summary"""
```

### Why Two Layers?

The programmatic checker catches **obvious** problems (banned word list, skills boundary). The LLM judge catches **subtle** fabrication that rules can't detect — like inventing a plausible-sounding project or inflating a metric from "80%" to "95%".

Neither alone is sufficient:
- The programmatic checker misses semantic fabrication
- The LLM judge is expensive (another API call) and sometimes over-flags legitimate rewording

Together, they provide robust quality control.

---

## Resume Assembly

```python
def assemble_resume_text(data, profile):
    personal = profile.get("personal", {})
    lines = []

    # Header — ALWAYS code-injected
    lines.append(personal.get("full_name", ""))
    lines.append(sanitize_text(data.get("title", "Software Engineer")))
    contact_parts = [personal.get("email"), personal.get("phone"), ...]
    lines.append(" | ".join(p for p in contact_parts if p))

    # Body — from LLM JSON
    lines.append("SUMMARY")
    lines.append(sanitize_text(data["summary"]))

    lines.append("TECHNICAL SKILLS")
    for cat, val in data["skills"].items():
        lines.append(f"{cat}: {sanitize_text(str(val))}")

    lines.append("EXPERIENCE")
    for entry in data.get("experience", []):
        lines.append(sanitize_text(entry["header"]))
        for b in entry.get("bullets", []):
            lines.append(f"- {sanitize_text(b)}")
```

### `sanitize_text()`

Every piece of LLM-generated text goes through `sanitize_text()` which:
- Replaces em dashes (—) with hyphens (-)
- Replaces smart quotes ("") with straight quotes ("")
- Strips leading/trailing whitespace

This ensures consistent formatting regardless of the LLM's Unicode preferences.

---

## Batch Processing

```python
def run_tailoring(min_score=7, limit=20):
    for job in jobs:
        tailored, report = tailor_resume(resume_text, job, profile)

        # Save files: .txt, _JOB.txt (job description), _REPORT.json (validation)
        txt_path = TAILORED_DIR / f"{prefix}.txt"
        txt_path.write_text(tailored, encoding="utf-8")

        # PDF conversion (best-effort)
        if report["status"] == "approved":
            pdf_path = convert_to_pdf(txt_path)

    # DB update: save path for approved, increment attempts for all
    for r in results:
        if r["status"] == "approved":
            conn.execute("UPDATE jobs SET tailored_resume_path=? ...", (r["path"], ...))
        else:
            conn.execute("UPDATE jobs SET tailor_attempts=tailor_attempts+1 ...", (r["url"],))
```

### Three Output Files Per Job

1. **`Company_Title.txt`** — the tailored resume
2. **`Company_Title_JOB.txt`** — the original job description (for traceability)
3. **`Company_Title_REPORT.json`** — validation report (attempts, validator results, judge verdict)

This traceability is important for debugging. If a tailored resume looks wrong, you can read the job description and validation report to understand what happened.

---

## Design Patterns to Notice

### 1. Defense Against AI Hallucination
This is the most sophisticated anti-hallucination system in the codebase. Two validation layers, fresh-context retries, and explicit skills boundaries all work together to prevent the LLM from inventing qualifications.

### 2. Attempt Tracking Across Runs
```python
conn.execute("UPDATE jobs SET tailor_attempts=COALESCE(tailor_attempts,0)+1")
```
Even if a job fails all retries, the attempt counter persists. On the next pipeline run, jobs that have already failed 5 times are skipped, preventing infinite retry loops.

### 3. Best-Effort PDF
```python
try:
    pdf_path = convert_to_pdf(txt_path)
except Exception:
    log.debug("PDF generation failed", exc_info=True)
```
PDF generation is optional. If it fails (Playwright not installed, rendering error), the text file is still saved. The apply stage can work with .txt files as a fallback.
