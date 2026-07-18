# scoring/scorer.py — LLM Job Fit Evaluator

**File:** `src/applypilot/scoring/scorer.py` (181 lines)
**Role:** Evaluates how well the candidate fits each job using an LLM, producing a 1-10 score.

---

## What This File Does

For every job that has a full description, this module asks an LLM: "Given this resume and this job description, how well does this candidate fit? Score 1-10."

The score determines what happens next:
- **7-10:** Resume gets tailored, cover letter generated, job enters the apply queue
- **5-6:** Moderate match, kept in DB but not processed further (unless --min-score is lowered)
- **1-4:** Poor match, effectively filtered out

---

## The Scoring Prompt

```python
SCORE_PROMPT = """You are a job fit evaluator. Score how well the candidate fits the role.

SCORING CRITERIA:
- 9-10: Perfect match. Direct experience in nearly all required skills.
- 7-8: Strong match. Most required skills, minor gaps easily bridged.
- 5-6: Moderate match. Some relevant skills but missing key requirements.
- 3-4: Weak match. Significant skill gaps.
- 1-2: Poor match. Completely different field.

IMPORTANT FACTORS:
- Weight technical skills heavily
- Consider transferable experience
- Factor in project experience
- Be realistic about experience level vs. requirements

RESPOND IN EXACTLY THIS FORMAT:
SCORE: [1-10]
KEYWORDS: [comma-separated ATS keywords]
REASONING: [2-3 sentences]"""
```

### Why This Prompt Structure?

1. **Explicit criteria with examples.** Instead of "score the fit," we define what each score range means. This calibrates the LLM's judgment across thousands of evaluations.

2. **Important factors as guidance.** "Weight technical skills heavily" prevents the LLM from giving high scores based on soft skills alone.

3. **Strict output format.** The `RESPOND IN EXACTLY THIS FORMAT` instruction ensures parseable output. Without it, the LLM might write paragraphs of explanation without a clear score.

4. **Keywords extraction.** The `KEYWORDS` field captures ATS-relevant terms from the job description. These are stored in `score_reasoning` for later reference during tailoring.

---

## Response Parsing

```python
def _parse_score_response(response):
    score = 0
    keywords = ""
    reasoning = response

    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("SCORE:"):
            score = int(re.search(r"\d+", line).group())
            score = max(1, min(10, score))  # clamp to 1-10
        elif line.startswith("KEYWORDS:"):
            keywords = line.replace("KEYWORDS:", "").strip()
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()

    return {"score": score, "keywords": keywords, "reasoning": reasoning}
```

### Clamping

```python
score = max(1, min(10, score))
```

Even with clear instructions, LLMs sometimes output `0` or `11`. Clamping ensures the score is always in the valid range. A score of 0 means the LLM produced an unparseable response (error case).

### Graceful Degradation

If the response doesn't match the expected format:
- `score` stays 0 (signals parsing failure)
- `reasoning` defaults to the full response text
- No crash, just a degraded result

---

## Single Job Scoring

```python
def score_job(resume_text, job):
    job_text = (
        f"TITLE: {job['title']}\n"
        f"COMPANY: {job['site']}\n"
        f"LOCATION: {job.get('location', 'N/A')}\n\n"
        f"DESCRIPTION:\n{(job.get('full_description') or '')[:6000]}"
    )

    messages = [
        {"role": "system", "content": SCORE_PROMPT},
        {"role": "user", "content": f"RESUME:\n{resume_text}\n\n---\n\nJOB POSTING:\n{job_text}"},
    ]

    client = get_client()
    response = client.chat(messages, max_tokens=512, temperature=0.2)
    return _parse_score_response(response)
```

### Why Truncate to 6000 Characters?

```python
(job.get('full_description') or '')[:6000]
```

Job descriptions can be very long (15K+ characters for enterprise postings). Sending the full text wastes tokens and money. The first 6000 characters almost always contain:
- Job title and responsibilities
- Required skills and qualifications
- Nice-to-haves

The bottom portion is usually legal boilerplate, EEO statements, and company descriptions — not useful for scoring.

### Temperature 0.2

```python
response = client.chat(messages, max_tokens=512, temperature=0.2)
```

Low temperature = more deterministic output. Scoring should be consistent — the same resume + job should get approximately the same score each time. A temperature of 0.2 allows slight variation (good for ties) without wild swings.

### max_tokens=512

The expected output is ~100 tokens (score + keywords + 2-3 sentences). Setting `max_tokens=512` provides headroom while preventing runaway generation.

---

## Batch Scoring

```python
def run_scoring(limit=0, rescore=False):
    resume_text = RESUME_PATH.read_text(encoding="utf-8")
    jobs = get_jobs_by_stage(conn=conn, stage="pending_score", limit=limit)

    for job in jobs:
        result = score_job(resume_text, job)
        log.info("[%d/%d] score=%d  %s", completed, len(jobs), result["score"], job["title"][:60])

    # Write all scores to DB at once
    for r in results:
        conn.execute(
            "UPDATE jobs SET fit_score=?, score_reasoning=?, scored_at=? WHERE url=?",
            (r["score"], f"{r['keywords']}\n{r['reasoning']}", now, r["url"]),
        )
    conn.commit()
```

### Sequential, Not Parallel

Jobs are scored one at a time. Why not parallelize?

1. **LLM rate limits.** Most APIs have per-minute token limits. Parallel requests would hit these faster.
2. **Cost control.** Sequential processing lets you monitor costs in real-time and stop if they're too high.
3. **Simplicity.** The LLM call takes 2-5 seconds per job. For 100 jobs, that's ~5-8 minutes — acceptable.

### Batch DB Write

Scores are computed in memory, then written to the DB in one batch. This is more efficient than committing after each job (fewer write transactions).

---

## Design Patterns to Notice

### 1. Structured Output Parsing
The prompt enforces a format (`SCORE: N`), and the parser extracts it. This is the simplest form of structured output extraction — no JSON schema, no function calling, just line parsing.

### 2. Idempotency
Re-running scoring on already-scored jobs does nothing (they're filtered out by `stage="pending_score"`). The `rescore=True` flag explicitly opts in to re-evaluation.

### 3. The Score as a Gate
The score is the primary filter for the rest of the pipeline. Below the threshold, jobs are effectively frozen. This saves significant LLM costs — tailoring and cover letter generation are much more expensive than scoring.
