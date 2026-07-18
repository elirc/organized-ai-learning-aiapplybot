# config.py — Paths, Platform Detection, and Feature Gating

**File:** `src/applypilot/config.py` (261 lines)
**Role:** Central configuration — defines file paths, detects the platform, loads user data, and gates features by tier.

---

## What This File Does

This file is the **address book** of the application. Every other module imports from it to know:
- Where the database lives
- Where to save tailored resumes
- Where Chrome is installed
- What the user's profile says
- Whether the user has the right dependencies for each feature

---

## Path Definitions

```python
APP_DIR = Path(os.environ.get("APPLYPILOT_DIR", Path.home() / ".applypilot"))

DB_PATH = APP_DIR / "applypilot.db"
PROFILE_PATH = APP_DIR / "profile.json"
RESUME_PATH = APP_DIR / "resume.txt"
SEARCH_CONFIG_PATH = APP_DIR / "searches.yaml"
ENV_PATH = APP_DIR / ".env"
TAILORED_DIR = APP_DIR / "tailored_resumes"
LOG_DIR = APP_DIR / "logs"
CHROME_WORKER_DIR = APP_DIR / "chrome-workers"
```

### Why `~/.applypilot/`?

All user-specific data lives under one directory. This follows the **XDG convention** on Linux and is standard practice for CLI tools:
- `~/.applypilot/applypilot.db` — the job database
- `~/.applypilot/profile.json` — personal data
- `~/.applypilot/tailored_resumes/` — generated resumes
- `~/.applypilot/logs/` — agent session logs

**Benefits:**
- Easy to back up (one folder)
- Easy to nuke and restart (delete the folder)
- Doesn't pollute the user's home directory with many files
- Overridable via `APPLYPILOT_DIR` environment variable for testing

### Package-Shipped Config

```python
PACKAGE_DIR = Path(__file__).parent
CONFIG_DIR = PACKAGE_DIR / "config"
```

`__file__` is the path to `config.py` itself. `Path(__file__).parent` gives us the package directory. This lets us find bundled YAML files (`sites.yaml`, `employers.yaml`) relative to the installed package, regardless of where Python is installed.

---

## Chrome Detection

```python
def get_chrome_path() -> str:
    env_path = os.environ.get("CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    system = platform.system()
    if system == "Windows":
        candidates = [
            Path("C:\\Program Files") / "Google/Chrome/Application/chrome.exe",
            Path("C:\\Program Files (x86)") / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
    elif system == "Darwin":
        candidates = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))
```

### The Search Strategy

1. **Environment variable first** — `CHROME_PATH=/opt/chrome/chrome` overrides everything. Useful for CI/CD or non-standard installations.
2. **Platform-specific common paths** — check where Chrome is usually installed on each OS.
3. **PATH fallback** — `shutil.which()` searches the system PATH for chrome-like executables.

### Why So Many Candidates?

Chrome can be installed in different locations:
- `C:\Program Files\` (64-bit system install)
- `C:\Program Files (x86)\` (32-bit install)
- `%LOCALAPPDATA%\` (per-user install)
- `/Applications/` (macOS)
- `/usr/bin/` (Linux system package)

Each is valid. The function tries them all and returns the first one that exists.

---

## Configuration Loaders

```python
def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError("Profile not found. Run `applypilot init` first.")
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

def load_search_config() -> dict:
    if not SEARCH_CONFIG_PATH.exists():
        example = CONFIG_DIR / "searches.example.yaml"
        if example.exists():
            return yaml.safe_load(example.read_text())
        return {}
    return yaml.safe_load(SEARCH_CONFIG_PATH.read_text())
```

### Fail-Fast vs. Graceful Fallback

**Profile: fail-fast.** If the profile doesn't exist, raise an error immediately. The profile is REQUIRED — without it, nothing works (no name, no email, no skills boundary).

**Search config: graceful fallback.** If the user hasn't created `searches.yaml`, fall back to the bundled example. This lets discovery work out of the box with example queries. The user can customize later.

---

## Site Configuration

```python
def load_sites_config() -> dict:
    path = CONFIG_DIR / "sites.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text())

def is_manual_ats(url):
    domains = sites_cfg.get("manual_ats", [])
    return any(domain in url_lower for domain in domains)

def load_blocked_sites() -> tuple[set[str], list[str]]:
    blocked = cfg.get("blocked", {})
    sites = set(blocked.get("sites", []))
    patterns = blocked.get("url_patterns", [])
    return sites, patterns
```

### What's in sites.yaml?

This YAML registry controls per-site behavior:
- **`manual_ats`** — ATS domains that require manual application (unsolvable CAPTCHAs, video interviews). These are auto-skipped.
- **`blocked.sites`** — Site names to exclude from the apply queue.
- **`blocked.url_patterns`** — URL patterns (SQL LIKE) to exclude.
- **`blocked_sso`** — SSO domains the agent can't sign into (Google, Microsoft).
- **`base_urls`** — For resolving relative URLs during enrichment.

---

## The Tier System

```python
TIER_LABELS = {
    1: "Discovery",
    2: "AI Scoring & Tailoring",
    3: "Full Auto-Apply",
}

def get_tier() -> int:
    has_llm = any(os.environ.get(k) for k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_URL"))
    if not has_llm:
        return 1

    has_claude = shutil.which("claude") is not None
    has_chrome = ...
    if has_claude and has_chrome:
        return 3

    return 2
```

### How Tiers Work

| Tier | Requires | Enables |
|------|----------|---------|
| 1 | Python + pip | `discover`, `enrich`, `status` |
| 2 | + LLM API key | `score`, `tailor`, `cover`, `pdf` |
| 3 | + Claude CLI + Chrome | `apply` |

### Why Tiers?

Not every user needs the full pipeline. Someone might just want to discover and enrich jobs (Tier 1). Another might want AI scoring but manual applications (Tier 2). Tiers prevent confusing errors when optional dependencies are missing.

```python
def check_tier(required, feature):
    current = get_tier()
    if current >= required:
        return

    # Print helpful message about what's missing
    if required >= 2:
        missing.append("LLM API key — run applypilot init or set GEMINI_API_KEY")
    if required >= 3:
        if not shutil.which("claude"):
            missing.append("Claude Code CLI — install from https://claude.ai/code")
```

The error message tells you exactly what to install, not just "feature unavailable."

---

## Default Values

```python
DEFAULTS = {
    "min_score": 7,
    "max_apply_attempts": 3,
    "max_tailor_attempts": 5,
    "poll_interval": 60,
    "apply_timeout": 300,
    "viewport": "1280x900",
}
```

### Why Centralize Defaults?

Without this, you'd see magic numbers scattered across the codebase:
```python
# BAD: magic numbers
if attempts >= 3:  # what's 3? where did it come from?
```
```python
# GOOD: named constant
if attempts >= config.DEFAULTS["max_apply_attempts"]:
```

Centralizing defaults makes it easy to find, understand, and change them.

---

## Environment Loading

```python
def load_env():
    from dotenv import load_dotenv
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    load_dotenv()  # also try CWD .env
```

### Two .env Files

1. `~/.applypilot/.env` — the primary location (created by `applypilot init`)
2. `./.env` — fallback for development (CWD)

`python-dotenv` never overwrites existing environment variables, so if a key is set in both files, the first one loaded wins.

---

## Design Patterns to Notice

### 1. Configuration Module Pattern
This is a textbook configuration module: module-level constants, lazy-loaded functions, and no business logic. Every other module imports from here.

### 2. Convention Over Configuration
Sensible defaults everywhere. You can run `applypilot run` with zero configuration and it works. Customization is available but not required.

### 3. Environment Variable Override
Every path and setting can be overridden: `APPLYPILOT_DIR`, `CHROME_PATH`, `LLM_MODEL`, API keys. This enables CI/CD, Docker, and custom deployments without code changes.
