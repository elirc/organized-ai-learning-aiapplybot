# prompt.py — The AI Agent's Instructions

**File:** `src/applypilot/apply/prompt.py` (672 lines)
**Role:** Builds the complete instruction prompt that tells the AI agent how to fill out a job application.

---

## What This File Does

This is the **longest and most nuanced** file in the apply subsystem. It constructs a multi-thousand-word prompt that serves as the AI agent's complete instruction manual. Every behavior of the auto-apply system — from location eligibility checks to CAPTCHA solving to salary negotiation — is encoded here.

The prompt is entirely **profile-driven** — all personal data comes from `~/.applypilot/profile.json`. Zero hardcoded information.

---

## Prompt Architecture

The full prompt is assembled from ~10 sections:

```
1. MISSION STATEMENT     — "You are an autonomous job application agent"
2. JOB CONTEXT          — URL, title, company, fit score
3. FILES                — Resume PDF path, cover letter path
4. RESUME TEXT          — Full tailored resume (for text fields)
5. COVER LETTER TEXT    — Cover letter content
6. APPLICANT PROFILE    — Name, email, phone, work auth, etc.
7. HARD RULES          — Never lie about citizenship, name, etc.
8. NEVER DO THESE      — Camera permissions, payment info, etc.
9. LOCATION CHECK      — Eligibility based on work arrangement
10. SALARY INSTRUCTIONS — Decision tree for salary fields
11. SCREENING QUESTIONS — How to answer each type
12. STEP-BY-STEP        — Exact procedure (navigate → upload → fill → submit)
13. BROWSER EFFICIENCY  — Performance tips
14. FORM TRICKS         — Handle popups, dropdowns, file uploads
15. CAPTCHA SECTION     — Full CAPTCHA detection + solving via CapSolver API
16. WHEN TO GIVE UP     — Failure conditions
17. FINAL OUTPUT        — Required result format
```

---

## Profile Summary Builder

```python
def _build_profile_summary(profile):
    personal = profile["personal"]
    lines = [
        f"Name: {personal['full_name']}",
        f"Email: {personal['email']}",
        f"Phone: {personal['phone']}",
    ]
    # ... address, LinkedIn, GitHub, work auth, salary, etc.
    return "\n".join(lines)
```

### Why Build a Flat Text Summary?

The AI agent doesn't need to parse JSON — it needs a clear, readable reference of the applicant's information. The summary format mirrors how a human would take notes:

```
Name: Jane Smith
Email: jane@example.com
Phone: (555) 123-4567
Work Auth: Yes, authorized to work in US
Sponsorship Needed: No
Salary Expectation: $120000 USD
```

### Standard Responses

```python
lines.extend([
    "Age 18+: Yes",
    "Background Check: Yes",
    "Felony: No",
    "Previously Worked Here: No",
    "How Heard: Online Job Board",
])
```

These are **common screening questions** that almost every application asks. By including them in the profile, the agent doesn't have to guess.

---

## Location Check — The First Gate

```python
def _build_location_check(profile, search_config):
    return f"""== LOCATION CHECK (do this FIRST before any form) ==
    Read the job page. Determine the work arrangement. Then decide:
    - "Remote" → ELIGIBLE. Apply.
    - "Hybrid" or "onsite" in {city_list} → ELIGIBLE. Apply.
    - "Onsite only" in another city → NOT ELIGIBLE. Stop immediately.
    - Cannot determine location → Continue applying."""
```

### Why Check Location First?

Filling out a job application takes 2-5 minutes of agent time and costs API tokens. If the job requires being onsite in a city the candidate can't work in, that's all wasted. The location check is placed **before** the form-filling step to save time and money.

### The Accept Patterns

```python
accept_patterns = location_cfg.get("accept_patterns", [])
city_list = ", ".join(accept_patterns)  # e.g., "Toronto, Waterloo, Remote"
```

The user's search config defines which cities are acceptable for in-person roles. This is flexible — a user in Toronto might accept hybrid roles in Toronto, Waterloo, and Mississauga.

---

## Salary Decision Tree

```python
def _build_salary_section(profile):
    return f"""== SALARY (think, don't just copy) ==
    ${floor} {currency} is the FLOOR. Never go below it.

    Decision tree:
    1. Job shows a range ($120K-$160K)? → Answer with the MIDPOINT ($140K).
    2. Title says Senior/Staff/Lead? → Minimum $110K. Use midpoint if higher.
    3. Different currency? → {conversion_note}
    4. No salary info? → Use ${floor}.
    5. Asked for a range? → Midpoint minus 10% to midpoint plus 10%.
    6. Hourly rate? → Divide by 2080. ({hourly_line})"""
```

### Why a Decision Tree?

The naive approach is "always put $120K." But this leaves money on the table. If a job posts "$150K-$200K" and you answer "$120K," you might get lowballed.

The decision tree teaches the agent to be **strategic**:
- When the employer shows a range, aim for the midpoint (shows you know your worth)
- For senior roles, never go below a reasonable floor
- Convert hourly ↔ annual correctly (2080 = 40 hours × 52 weeks)

### Hourly Rate Examples

```python
examples = [
    (f"${floor_int // 1000}K", floor_int // 2080),
    (f"${(floor_int + 25000) // 1000}K", (floor_int + 25000) // 2080),
]
hourly_line = ", ".join(f"{sal} = ${hr}/hr" for sal, hr in examples)
```

Concrete examples help the agent. Instead of "divide by 2080," it sees "$120K = $57/hr, $145K = $69/hr." This reduces calculation errors.

---

## The CAPTCHA Section — A Full Protocol

This is the most impressive part of the prompt (~200 lines). It encodes a complete CAPTCHA-solving protocol:

### Detection

```javascript
// Embedded JavaScript for CAPTCHA detection
const hc = document.querySelector('.h-captcha, [data-hcaptcha-sitekey]');
if (hc) { r.type = 'hcaptcha'; r.sitekey = hc.dataset.sitekey; }
```

The agent runs this JavaScript in the browser to detect which CAPTCHA type is present. The detection order matters:
1. hCaptcha (check first — also has `data-sitekey` like reCAPTCHA)
2. Cloudflare Turnstile
3. reCAPTCHA v3 (invisible)
4. reCAPTCHA v2 (checkbox)
5. FunCaptcha (Arkose Labs)

### Solving via CapSolver API

The agent makes API calls to CapSolver (a CAPTCHA-solving service):
1. **Create task** — send the CAPTCHA type + site key
2. **Poll for result** — wait 3 seconds, check if solved, repeat
3. **Inject token** — paste the solution token into the page's hidden fields

### Why Embed JavaScript in the Prompt?

The AI agent can execute JavaScript via `browser_evaluate`. By giving it the exact scripts to run, we avoid relying on the agent to write correct DOM queries. CAPTCHA detection requires precise selectors — a small mistake means missing the CAPTCHA entirely.

### Manual Fallback

```
If CapSolver genuinely failed (errorId > 0):
1. Audio challenge: click the "audio" button for an easier challenge
2. Text/logic puzzles: Solve them yourself
3. Simple text captchas ("What is 3+7?"): solve them
4. All else fails → Output RESULT:CAPTCHA
```

If the API solver fails, the agent tries simpler approaches. This layered strategy maximizes the success rate.

---

## Resume Upload Strategy

```python
upload_pdf = dest_dir / f"{name_slug}_Resume.pdf"
shutil.copy(str(src_pdf), str(upload_pdf))
```

### Why Copy to a Clean Filename?

Recruiters see the filename when reviewing applications. `John_Smith_Resume.pdf` looks professional. `Indeed_Senior_Software_Engineer_REPORT.txt.pdf` looks auto-generated. The copy step ensures a clean, professional filename.

---

## The Step-by-Step Section

```
1. browser_navigate to the job URL.
2. browser_snapshot. Run CAPTCHA DETECT.
3. LOCATION CHECK.
4. Find and click Apply button.
5. Login wall? Check SSO, try credentials, handle verification.
6. Upload resume. ALWAYS upload fresh — delete existing first.
7. Upload cover letter if asked.
8. Check ALL pre-filled fields (ATS parsers are often WRONG).
9. Answer screening questions.
10. Review before submit (or skip if --dry-run).
11. After submit: check for CAPTCHAs, verify success.
12. Output final result.
```

### Why So Prescriptive?

AI agents are powerful but unpredictable. Without clear step-by-step instructions, Claude might:
- Skip the location check and waste time on ineligible jobs
- Forget to check for CAPTCHAs after clicking Submit
- Not re-upload the resume (trusting the ATS parser's version)
- Not verify the submission actually went through

The step-by-step structure acts as a **checklist** that prevents common failures.

---

## Design Patterns to Notice

### 1. Configuration as Code (in the Prompt)
The prompt IS the configuration for the agent's behavior. Every rule, exception, and edge case is encoded as natural language instructions. This is a fundamentally different approach from traditional software — the "code" is English.

### 2. Defense in Depth
Multiple layers prevent bad behavior:
- Location check → prevents applying to wrong cities
- Domain allowlist → prevents navigating to dangerous sites
- Hard rules → prevents lying about credentials
- Never-do list → prevents granting permissions or entering payment info
- SSO blocklist → prevents getting stuck on OAuth pages

### 3. Profile-Driven Templates
Every section builder reads from the profile dict. The salary section uses `profile["compensation"]`, the screening section uses `profile["experience"]`, etc. This means the same code generates correct prompts for any user — a DevOps engineer, a data scientist, or a product manager.

### 4. Explicit > Implicit
The prompt is verbose by design. Rather than saying "handle salary questions appropriately," it gives a 6-step decision tree with concrete examples. AI agents perform better with explicit instructions than vague guidance.
