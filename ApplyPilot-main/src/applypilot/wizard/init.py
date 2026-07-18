"""ApplyPilot first-time setup wizard."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from applypilot.config import (
    APP_DIR,
    ENV_PATH,
    PROFILE_PATH,
    RESUME_PATH,
    RESUME_PDF_PATH,
    SEARCH_CONFIG_PATH,
    ensure_dirs,
)

console = Console()


def _bool_to_yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _setup_resume() -> None:
    """Prompt for a resume file and copy it into APP_DIR."""
    console.print(Panel("[bold]Step 1: Resume[/bold]\nPoint to your master resume file (.txt or .pdf)."))

    while True:
        path_str = Prompt.ask("Resume file path")
        src = Path(path_str.strip().strip('"').strip("'")).expanduser().resolve()

        if not src.exists():
            console.print(f"[red]File not found:[/red] {src}")
            continue

        suffix = src.suffix.lower()
        if suffix not in (".txt", ".pdf"):
            console.print("[red]Unsupported format.[/red] Provide a .txt or .pdf file.")
            continue

        if suffix == ".txt":
            shutil.copy2(src, RESUME_PATH)
            console.print(f"[green]Copied to {RESUME_PATH}[/green]")
        else:
            shutil.copy2(src, RESUME_PDF_PATH)
            console.print(f"[green]Copied to {RESUME_PDF_PATH}[/green]")

            txt_path_str = Prompt.ask(
                "Plain-text version of your resume (.txt)",
                default="",
            )
            if txt_path_str.strip():
                txt_src = Path(txt_path_str.strip().strip('"').strip("'")).expanduser().resolve()
                if txt_src.exists():
                    shutil.copy2(txt_src, RESUME_PATH)
                    console.print(f"[green]Copied to {RESUME_PATH}[/green]")
                else:
                    console.print("[yellow]File not found, skipping plain-text copy.[/yellow]")
        break


def _setup_profile() -> dict:
    """Walk through profile questions and return a normalized profile dict."""
    console.print(Panel("[bold]Step 2: Profile[/bold]\nTell ApplyPilot about yourself."))

    full_name = Prompt.ask("Full name")
    default_preferred = full_name.split()[0] if full_name.strip() else ""

    console.print("\n[bold cyan]Personal Information[/bold cyan]")
    profile: dict = {
        "personal": {
            "full_name": full_name,
            "preferred_name": Prompt.ask("Preferred first name", default=default_preferred),
            "email": Prompt.ask("Email address"),
            "password": Prompt.ask("Job site password", password=True, default=""),
            "phone": Prompt.ask("Phone number", default=""),
            "address": Prompt.ask("Street address", default=""),
            "city": Prompt.ask("City", default=""),
            "province_state": Prompt.ask("State / province", default=""),
            "country": Prompt.ask("Country", default=""),
            "postal_code": Prompt.ask("Postal / ZIP code", default=""),
            "linkedin_url": Prompt.ask("LinkedIn URL", default=""),
            "github_url": Prompt.ask("GitHub URL", default=""),
            "portfolio_url": Prompt.ask("Portfolio URL", default=""),
            "website_url": Prompt.ask("Personal website URL", default=""),
        }
    }

    console.print("\n[bold cyan]Work Authorization[/bold cyan]")
    profile["work_authorization"] = {
        "legally_authorized_to_work": _bool_to_yes_no(
            Confirm.ask("Are you legally authorized to work in your target country?", default=True)
        ),
        "require_sponsorship": _bool_to_yes_no(
            Confirm.ask("Will you now or in the future need sponsorship?", default=False)
        ),
        "work_permit_type": Prompt.ask("Work permit / visa type", default=""),
    }

    console.print("\n[bold cyan]Compensation[/bold cyan]")
    salary = Prompt.ask("Expected annual salary (number)", default="")
    salary_currency = Prompt.ask("Currency", default="USD")
    salary_range = Prompt.ask("Acceptable range (e.g. 80000-120000)", default="")
    range_parts = salary_range.split("-") if "-" in salary_range else [salary, salary]
    profile["compensation"] = {
        "salary_expectation": salary,
        "salary_currency": salary_currency,
        "salary_range_min": range_parts[0].strip(),
        "salary_range_max": range_parts[1].strip() if len(range_parts) > 1 else range_parts[0].strip(),
        "currency_conversion_note": "",
    }

    console.print("\n[bold cyan]Experience[/bold cyan]")
    current_job_title = Prompt.ask("Current / most recent job title", default="")
    profile["experience"] = {
        "years_of_experience_total": Prompt.ask("Years of professional experience", default=""),
        "education_level": Prompt.ask(
            "Highest education (e.g. Bachelor's, Master's, PhD, Self-taught)",
            default="",
        ),
        "current_job_title": current_job_title,
        "current_company": Prompt.ask("Current / most recent company", default=""),
        "target_role": Prompt.ask("Target role", default=current_job_title or "software engineer"),
    }

    console.print("\n[bold cyan]Skills[/bold cyan] (comma-separated)")
    languages = Prompt.ask("Programming languages", default="")
    frameworks = Prompt.ask("Frameworks & libraries", default="")
    devops = Prompt.ask("DevOps / cloud / infra tools", default="")
    databases = Prompt.ask("Databases", default="")
    tools = Prompt.ask("Other tools & platforms", default="")
    profile["skills_boundary"] = {
        "languages": [item.strip() for item in languages.split(",") if item.strip()],
        "frameworks": [item.strip() for item in frameworks.split(",") if item.strip()],
        "devops": [item.strip() for item in devops.split(",") if item.strip()],
        "databases": [item.strip() for item in databases.split(",") if item.strip()],
        "tools": [item.strip() for item in tools.split(",") if item.strip()],
    }

    console.print("\n[bold cyan]Resume Facts[/bold cyan]")
    console.print("[dim]These are preserved exactly during resume tailoring.[/dim]")
    companies = Prompt.ask("Companies to always keep (comma-separated)", default="")
    projects = Prompt.ask("Projects to always keep (comma-separated)", default="")
    school = Prompt.ask("School name(s) to preserve", default="")
    metrics = Prompt.ask("Real metrics to preserve (comma-separated)", default="")
    profile["resume_facts"] = {
        "preserved_companies": [item.strip() for item in companies.split(",") if item.strip()],
        "preserved_projects": [item.strip() for item in projects.split(",") if item.strip()],
        "preserved_school": school.strip(),
        "real_metrics": [item.strip() for item in metrics.split(",") if item.strip()],
    }

    profile["eeo_voluntary"] = {
        "gender": "Decline to self-identify",
        "race_ethnicity": "Decline to self-identify",
        "veteran_status": "I am not a protected veteran",
        "disability_status": "I do not wish to answer",
    }

    profile["availability"] = {
        "earliest_start_date": Prompt.ask("Earliest start date", default="Immediately"),
        "available_for_full_time": "Yes",
        "available_for_contract": "No",
    }

    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"\n[green]Profile saved to {PROFILE_PATH}[/green]")
    return profile


def _build_accept_patterns(location: str, remote_only: bool) -> list[str]:
    if remote_only or location.lower() == "remote":
        return []

    patterns = [location]
    city_only = location.split(",", 1)[0].strip()
    if city_only and city_only not in patterns:
        patterns.append(city_only)
    return patterns


def _setup_searches() -> None:
    """Generate searches.yaml from user input."""
    console.print(Panel("[bold]Step 3: Job Search Config[/bold]\nDefine what you're looking for."))

    location = Prompt.ask(
        "Target location (e.g. 'Remote', 'Canada', 'New York, NY')",
        default="Remote",
    )
    distance_str = Prompt.ask("Search radius in miles (0 for remote-only)", default="0")
    try:
        distance = int(distance_str)
    except ValueError:
        distance = 0

    roles_raw = Prompt.ask(
        "Target job titles (comma-separated, e.g. 'Backend Engineer, Full Stack Developer')"
    )
    roles = [role.strip() for role in roles_raw.split(",") if role.strip()]
    if not roles:
        console.print("[yellow]No roles provided. Using a default set.[/yellow]")
        roles = ["Software Engineer"]

    remote_only = distance == 0 or location.lower() == "remote"
    accept_patterns = _build_accept_patterns(location, remote_only)

    lines = [
        "# ApplyPilot search configuration",
        "",
        "queries:",
    ]
    for index, role in enumerate(roles):
        lines.append(f'  - query: "{role}"')
        lines.append(f"    tier: {min(index + 1, 3)}")

    lines.extend(
        [
            "",
            "locations:",
            f'  - location: "{location}"',
            f"    remote: {'true' if remote_only else 'false'}",
            "",
            "location:",
            "  accept_patterns:",
        ]
    )
    if accept_patterns:
        for pattern in accept_patterns:
            lines.append(f'    - "{pattern}"')
    else:
        lines.append('    - "Remote"')
    lines.extend(
        [
            "  reject_patterns:",
            "",
            'country: "USA"',
            "",
            "boards:",
            "  - indeed",
            "  - linkedin",
            "  - glassdoor",
            "  - zip_recruiter",
            "",
            "defaults:",
            f"  distance: {distance}",
            "  results_per_site: 50",
            "  hours_old: 72",
        ]
    )

    SEARCH_CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"[green]Search config saved to {SEARCH_CONFIG_PATH}[/green]")


def _setup_ai_features() -> None:
    """Ask about AI scoring/tailoring and save provider settings."""
    console.print(
        Panel(
            "[bold]Step 4: AI Features (optional)[/bold]\n"
            "An LLM powers job scoring, resume tailoring, and cover letters.\n"
            "Without this, you can still discover and enrich jobs."
        )
    )

    if not Confirm.ask("Enable AI scoring and resume tailoring?", default=True):
        console.print("[dim]Discovery-only mode. You can configure AI later with [bold]applypilot init[/bold].[/dim]")
        return

    console.print("Supported providers: [bold]Gemini[/bold], OpenAI, local OpenAI-compatible endpoint")
    provider = Prompt.ask(
        "Provider",
        choices=["gemini", "openai", "local"],
        default="gemini",
    )

    env_lines = ["# ApplyPilot configuration", ""]

    if provider == "gemini":
        api_key = Prompt.ask("Gemini API key (from aistudio.google.com)")
        model = Prompt.ask("Model", default="gemini-2.0-flash")
        env_lines.append(f"GEMINI_API_KEY={api_key}")
        env_lines.append(f"LLM_MODEL={model}")
    elif provider == "openai":
        api_key = Prompt.ask("OpenAI API key")
        model = Prompt.ask("Model", default="gpt-4o-mini")
        env_lines.append(f"OPENAI_API_KEY={api_key}")
        env_lines.append(f"LLM_MODEL={model}")
    else:
        url = Prompt.ask("Local LLM endpoint URL", default="http://localhost:8080/v1")
        model = Prompt.ask("Model name", default="local-model")
        env_lines.append(f"LLM_URL={url}")
        env_lines.append(f"LLM_MODEL={model}")

    env_lines.append("")
    ENV_PATH.write_text("\n".join(env_lines), encoding="utf-8")
    console.print(f"[green]AI configuration saved to {ENV_PATH}[/green]")


def _setup_auto_apply() -> None:
    """Configure autonomous job application support."""
    console.print(
        Panel(
            "[bold]Step 5: Auto-Apply (optional)[/bold]\n"
            "ApplyPilot can submit applications with either Claude Code CLI or Codex CLI."
        )
    )

    if not Confirm.ask("Enable autonomous job applications?", default=True):
        console.print("[dim]You can still use ApplyPilot for discovery and document generation.[/dim]")
        return

    claude_installed = shutil.which("claude") is not None
    codex_installed = shutil.which("codex") is not None

    if claude_installed:
        console.print("[green]Claude Code CLI detected.[/green]")
    if codex_installed:
        console.print("[green]Codex CLI detected.[/green]")
    if not claude_installed and not codex_installed:
        console.print(
            "[yellow]No supported Stage-6 CLI found on PATH.[/yellow]\n"
            "Install Claude Code from [bold]https://claude.ai/code[/bold] or install Codex CLI."
        )

    console.print("\n[dim]Some job sites use CAPTCHAs. CapSolver can handle them automatically.[/dim]")
    if Confirm.ask("Configure CapSolver API key? (optional)", default=False):
        capsolver_key = Prompt.ask("CapSolver API key")
        if ENV_PATH.exists():
            existing = ENV_PATH.read_text(encoding="utf-8")
            if "CAPSOLVER_API_KEY" not in existing:
                ENV_PATH.write_text(
                    existing.rstrip() + f"\nCAPSOLVER_API_KEY={capsolver_key}\n",
                    encoding="utf-8",
                )
        else:
            ENV_PATH.write_text(
                f"# ApplyPilot configuration\nCAPSOLVER_API_KEY={capsolver_key}\n",
                encoding="utf-8",
            )
        console.print("[green]CapSolver key saved.[/green]")
    else:
        console.print("[dim]Skipped. Add CAPSOLVER_API_KEY to .env later if needed.[/dim]")


def run_wizard() -> None:
    """Run the full interactive setup wizard."""
    console.print()
    console.print(
        Panel.fit(
            "[bold green]ApplyPilot Setup Wizard[/bold green]\n\n"
            "This will create your configuration at:\n"
            f"  [cyan]{APP_DIR}[/cyan]\n\n"
            "You can re-run this anytime with [bold]applypilot init[/bold].",
            border_style="green",
        )
    )

    ensure_dirs()
    console.print(f"[dim]Created {APP_DIR}[/dim]\n")

    _setup_resume()
    console.print()

    _setup_profile()
    console.print()

    _setup_searches()
    console.print()

    _setup_ai_features()
    console.print()

    _setup_auto_apply()
    console.print()

    from applypilot.config import TIER_COMMANDS, TIER_LABELS, get_tier

    tier = get_tier()

    tier_lines: list[str] = []
    for current_tier in range(1, 4):
        label = TIER_LABELS[current_tier]
        commands = ", ".join(f"[bold]{command}[/bold]" for command in TIER_COMMANDS[current_tier])
        if current_tier <= tier:
            tier_lines.append(f"  [green]OK Tier {current_tier} - {label}[/green]  ({commands})")
        elif current_tier == tier + 1:
            tier_lines.append(f"  [yellow]Next Tier {current_tier} - {label}[/yellow]  ({commands})")
        else:
            tier_lines.append(f"  [dim]Locked Tier {current_tier} - {label}  ({commands})[/dim]")

    unlock_hint = ""
    if tier == 1:
        unlock_hint = "\n[dim]To unlock Tier 2: configure an LLM API key.[/dim]"
    elif tier == 2:
        unlock_hint = "\n[dim]To unlock Tier 3: install Chrome plus Claude Code or Codex CLI.[/dim]"

    console.print(
        Panel.fit(
            "[bold green]Setup complete![/bold green]\n\n"
            f"[bold]Your tier: Tier {tier} - {TIER_LABELS[tier]}[/bold]\n\n"
            + "\n".join(tier_lines)
            + unlock_hint,
            border_style="green",
        )
    )
