"""ApplyPilot CLI — the main entry point."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Literal, Optional

import typer
from rich.console import Console
from rich.table import Table

from applypilot import __version__

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

app = typer.Typer(
    name="applypilot",
    help="AI-powered end-to-end job application pipeline.",
    no_args_is_help=True,
)
console = Console()
log = logging.getLogger(__name__)

# Valid pipeline stages (in execution order)
VALID_STAGES = ("discover", "enrich", "score", "tailor", "cover", "pdf")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    """Common setup: load env, create dirs, init DB."""
    from applypilot.config import load_env, ensure_dirs
    from applypilot.database import init_db

    load_env()
    ensure_dirs()
    init_db()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold]applypilot[/bold] {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """ApplyPilot — AI-powered end-to-end job application pipeline."""


@app.command()
def init() -> None:
    """Run the first-time setup wizard (profile, resume, search config)."""
    from applypilot.wizard.init import run_wizard

    run_wizard()


@app.command()
def run(
    stages: Optional[list[str]] = typer.Argument(
        None,
        help=(
            "Pipeline stages to run. "
            f"Valid: {', '.join(VALID_STAGES)}, all. "
            "Defaults to 'all' if omitted."
        ),
    ),
    min_score: int = typer.Option(7, "--min-score", help="Minimum fit score for tailor/cover stages."),
    workers: int = typer.Option(1, "--workers", "-w", help="Parallel threads for discovery/enrichment stages."),
    stream: bool = typer.Option(False, "--stream", help="Run stages concurrently (streaming mode)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview stages without executing."),
) -> None:
    """Run pipeline stages: discover, enrich, score, tailor, cover, pdf."""
    _bootstrap()

    from applypilot.pipeline import run_pipeline

    stage_list = stages if stages else ["all"]

    # Validate stage names
    for s in stage_list:
        if s != "all" and s not in VALID_STAGES:
            console.print(
                f"[red]Unknown stage:[/red] '{s}'. "
                f"Valid stages: {', '.join(VALID_STAGES)}, all"
            )
            raise typer.Exit(code=1)

    # Gate AI stages behind Tier 2
    llm_stages = {"score", "tailor", "cover"}
    if any(s in stage_list for s in llm_stages) or "all" in stage_list:
        from applypilot.config import check_tier
        check_tier(2, "AI scoring/tailoring")

    result = run_pipeline(
        stages=stage_list,
        min_score=min_score,
        dry_run=dry_run,
        stream=stream,
        workers=workers,
    )

    if result.get("errors"):
        raise typer.Exit(code=1)


@app.command()
def apply(
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Max applications to submit."),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of parallel browser workers."),
    min_score: int = typer.Option(7, "--min-score", help="Minimum fit score for job selection."),
    model: str = typer.Option("haiku", "--model", "-m", help="Deprecated alias for --claude-model."),
    agent: Literal["claude", "codex", "auto"] = typer.Option("claude", "--agent", help="Agent backend."),
    claude_model: Optional[str] = typer.Option(None, "--claude-model", help="Claude model name."),
    codex_model: Optional[str] = typer.Option(None, "--codex-model", help="Codex model name."),
    continuous: bool = typer.Option(False, "--continuous", "-c", help="Run forever, polling for new jobs."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview actions without submitting."),
    headless: bool = typer.Option(False, "--headless", help="Run browsers in headless mode."),
    enable_gmail: bool = typer.Option(False, "--enable-gmail", help="Enable Gmail MCP server."),
    domain_allowlist: Optional[str] = typer.Option(
        None,
        "--domain-allowlist",
        help="Comma-separated host allowlist (example.com,careers.example.com).",
    ),
    max_applies: int = typer.Option(25, "--max-applies", help="Hard cap on applications for this run."),
    min_delay_seconds: int = typer.Option(10, "--min-delay-seconds", help="Delay between attempts."),
    url: Optional[str] = typer.Option(None, "--url", help="Apply to a specific job URL."),
    gen: bool = typer.Option(False, "--gen", help="Generate prompt file for manual debugging instead of running."),
    mark_applied: Optional[str] = typer.Option(None, "--mark-applied", help="Manually mark a job URL as applied."),
    mark_failed: Optional[str] = typer.Option(None, "--mark-failed", help="Manually mark a job URL as failed (provide URL)."),
    fail_reason: Optional[str] = typer.Option(None, "--fail-reason", help="Reason for --mark-failed."),
    reset_failed: bool = typer.Option(False, "--reset-failed", help="Reset all failed jobs for retry."),
) -> None:
    """Launch auto-apply to submit job applications."""
    _bootstrap()

    from applypilot.config import PROFILE_PATH as _profile_path, get_chrome_path
    from applypilot.database import get_connection

    # --- Utility modes (no Chrome/Claude needed) ---

    if mark_applied:
        from applypilot.apply.launcher import mark_job
        mark_job(mark_applied, "applied")
        console.print(f"[green]Marked as applied:[/green] {mark_applied}")
        return

    if mark_failed:
        from applypilot.apply.launcher import mark_job
        mark_job(mark_failed, "failed", reason=fail_reason)
        console.print(f"[yellow]Marked as failed:[/yellow] {mark_failed} ({fail_reason or 'manual'})")
        return

    if reset_failed:
        from applypilot.apply.launcher import reset_failed as do_reset
        count = do_reset()
        console.print(f"[green]Reset {count} failed job(s) for retry.[/green]")
        return

    # --- Full apply mode ---

    # Runtime checks for local browser + selected CLI backend(s)
    try:
        get_chrome_path()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    if agent == "claude" and not shutil.which("claude"):
        console.print("[red]Claude CLI not found.[/red] Install from https://claude.ai/code")
        raise typer.Exit(code=1)
    if agent == "codex" and not shutil.which("codex"):
        console.print("[red]Codex CLI not found.[/red] Install and login via `codex login`.")
        raise typer.Exit(code=1)
    if agent == "auto" and not (shutil.which("claude") or shutil.which("codex")):
        console.print("[red]Neither Claude nor Codex CLI is installed.[/red]")
        raise typer.Exit(code=1)

    # Check 2: Profile exists
    if not _profile_path.exists():
        console.print(
            "[red]Profile not found.[/red]\n"
            "Run [bold]applypilot init[/bold] to create your profile first."
        )
        raise typer.Exit(code=1)

    # Check 3: Tailored resumes exist (skip for --gen with --url)
    if not (gen and url):
        conn = get_connection()
        ready = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE tailored_resume_path IS NOT NULL AND applied_at IS NULL"
        ).fetchone()[0]
        if ready == 0:
            console.print(
                "[red]No tailored resumes ready.[/red]\n"
                "Run [bold]applypilot run score tailor[/bold] first to prepare applications."
            )
            raise typer.Exit(code=1)

    if gen:
        from applypilot.apply.launcher import gen_prompt
        target = url or ""
        if not target:
            console.print("[red]--gen requires --url to specify which job.[/red]")
            raise typer.Exit(code=1)
        selected_claude_model = claude_model or model
        allowlist = [d.strip().lower() for d in (domain_allowlist or "").split(",") if d.strip()]
        prompt_file = gen_prompt(
            target,
            min_score=min_score,
            model=selected_claude_model,
            dry_run=dry_run,
            domain_allowlist=allowlist,
            min_delay_seconds=min_delay_seconds,
            json_output=(agent == "codex"),
            enable_gmail=enable_gmail,
        )
        if not prompt_file:
            console.print("[red]No matching job found for that URL.[/red]")
            raise typer.Exit(code=1)
        mcp_path = _profile_path.parent / ".mcp-apply-0.json"
        console.print(f"[green]Wrote prompt to:[/green] {prompt_file}")
        console.print("\n[bold]Run manually:[/bold]")
        if agent == "codex":
            console.print(f"  codex exec --json --skip-git-repo-check --model {codex_model or 'gpt-5.3-codex'} - < {prompt_file}")
        else:
            console.print(
                f"  claude --model {selected_claude_model} -p "
                f"--mcp-config {mcp_path} "
                f"--permission-mode bypassPermissions < {prompt_file}"
            )
        return

    from applypilot.apply.launcher import main as apply_main

    effective_limit = limit if limit is not None else (0 if continuous else 1)
    allowlist = [d.strip().lower() for d in (domain_allowlist or "").split(",") if d.strip()]
    selected_claude_model = claude_model or model

    console.print("\n[bold blue]Launching Auto-Apply[/bold blue]")
    console.print(f"  Limit:    {'unlimited' if continuous else effective_limit}")
    console.print(f"  Max:      {max_applies}")
    console.print(f"  Workers:  {workers}")
    console.print(f"  Agent:    {agent}")
    console.print(f"  Claude:   {selected_claude_model}")
    console.print(f"  Codex:    {codex_model or '(default)'}")
    console.print(f"  Headless: {headless}")
    console.print(f"  Dry run:  {dry_run}")
    console.print(f"  Gmail:    {enable_gmail}")
    console.print(f"  Delay:    {min_delay_seconds}s")
    if allowlist:
        console.print(f"  Domains:  {', '.join(allowlist)}")
    if url:
        console.print(f"  Target:   {url}")
    console.print()

    apply_main(
        limit=effective_limit,
        target_url=url,
        min_score=min_score,
        headless=headless,
        agent=agent,
        claude_model=selected_claude_model,
        codex_model=codex_model,
        dry_run=dry_run,
        continuous=continuous,
        workers=workers,
        enable_gmail=enable_gmail,
        domain_allowlist=allowlist,
        max_applies=max_applies,
        min_delay_seconds=min_delay_seconds,
    )


@app.command()
def doctor() -> None:
    """Check local CLI dependencies and Codex trust setup guidance."""
    _bootstrap()

    import importlib.util

    from applypilot.config import get_chrome_path

    claude_bin = shutil.which("claude")
    codex_bin = shutil.which("codex")
    playwright_pkg = importlib.util.find_spec("playwright") is not None
    jobspy_pkg = importlib.util.find_spec("jobspy") is not None
    try:
        chrome_path = get_chrome_path()
        chrome_ok = True
    except FileNotFoundError:
        chrome_path = "not found"
        chrome_ok = False

    table = Table(title="ApplyPilot Doctor", show_header=True, header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")
    table.add_row("Claude CLI", "[green]OK[/green]" if claude_bin else "[red]Missing[/red]", claude_bin or "Install from https://claude.ai/code")
    table.add_row("Codex CLI", "[green]OK[/green]" if codex_bin else "[red]Missing[/red]", codex_bin or "Install Codex CLI + run `codex login`")
    table.add_row("Chrome", "[green]OK[/green]" if chrome_ok else "[red]Missing[/red]", chrome_path)
    table.add_row(
        "Python Playwright",
        "[green]OK[/green]" if playwright_pkg else "[red]Missing[/red]",
        "Required for enrichment, smart extract, and PDF generation",
    )
    table.add_row(
        "python-jobspy",
        "[green]OK[/green]" if jobspy_pkg else "[yellow]Optional[/yellow]",
        "Needed for the JobSpy discovery stage",
    )
    console.print(table)

    project_path = str(Path.cwd().resolve())
    codex_global_cfg = Path.home() / ".codex" / "config.toml"
    cfg_hint = "(global config not found)"
    trust_detected = False
    if codex_global_cfg.exists():
        cfg_text = codex_global_cfg.read_text(encoding="utf-8", errors="replace")
        trust_detected = project_path in cfg_text and "trusted" in cfg_text.lower()
        cfg_hint = str(codex_global_cfg)

    console.print("\n[bold]Codex Project Trust[/bold]")
    if trust_detected:
        console.print(f"[green]Detected possible trust entry[/green] for {project_path}")
    else:
        console.print(
            f"[yellow]Codex may ignore project MCP config until this path is trusted:[/yellow]\n"
            f"  {project_path}"
        )
        console.print("If prompted by Codex, accept project trust for this repo.")
        console.print("Or add a trust entry in your global Codex config and retry.")
        console.print(f"Global config checked: {cfg_hint}")
        console.print(
            "Example snippet (shape may vary by Codex version):\n"
            f"  [projects.\"{project_path}\"]\n"
            "  trusted = true"
        )
    console.print("\nRun `applypilot apply --agent claude|codex|auto --dry-run` after fixing any missing items.")


@app.command()
def status() -> None:
    """Show pipeline statistics from the database."""
    _bootstrap()

    from applypilot.database import get_stats

    stats = get_stats()

    console.print("\n[bold]ApplyPilot Pipeline Status[/bold]\n")

    # Summary table
    summary = Table(title="Pipeline Overview", show_header=True, header_style="bold cyan")
    summary.add_column("Metric", style="bold")
    summary.add_column("Count", justify="right")

    summary.add_row("Total jobs discovered", str(stats["total"]))
    summary.add_row("With full description", str(stats["with_description"]))
    summary.add_row("Pending enrichment", str(stats["pending_detail"]))
    summary.add_row("Enrichment errors", str(stats["detail_errors"]))
    summary.add_row("Scored by LLM", str(stats["scored"]))
    summary.add_row("Pending scoring", str(stats["unscored"]))
    summary.add_row("Tailored resumes", str(stats["tailored"]))
    summary.add_row("Pending tailoring (7+)", str(stats["untailored_eligible"]))
    summary.add_row("Cover letters", str(stats["with_cover_letter"]))
    summary.add_row("Ready to apply", str(stats["ready_to_apply"]))
    summary.add_row("Applied", str(stats["applied"]))
    summary.add_row("Apply errors", str(stats["apply_errors"]))

    console.print(summary)

    # Score distribution
    if stats["score_distribution"]:
        dist_table = Table(title="\nScore Distribution", show_header=True, header_style="bold yellow")
        dist_table.add_column("Score", justify="center")
        dist_table.add_column("Count", justify="right")
        dist_table.add_column("Bar")

        max_count = max(count for _, count in stats["score_distribution"]) or 1
        for score, count in stats["score_distribution"]:
            bar_len = int(count / max_count * 30)
            if score >= 7:
                color = "green"
            elif score >= 5:
                color = "yellow"
            else:
                color = "red"
            bar = f"[{color}]{'=' * bar_len}[/{color}]"
            dist_table.add_row(str(score), str(count), bar)

        console.print(dist_table)

    # By site
    if stats["by_site"]:
        site_table = Table(title="\nJobs by Source", show_header=True, header_style="bold magenta")
        site_table.add_column("Site")
        site_table.add_column("Count", justify="right")

        for site, count in stats["by_site"]:
            site_table.add_row(site or "Unknown", str(count))

        console.print(site_table)

    console.print()


@app.command()
def dashboard() -> None:
    """Generate and open the HTML dashboard in your browser."""
    _bootstrap()

    from applypilot.view import open_dashboard

    open_dashboard()


if __name__ == "__main__":
    app()
