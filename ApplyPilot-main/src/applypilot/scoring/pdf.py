"""Text-to-PDF conversion for tailored resumes and cover letters."""

from __future__ import annotations

from html import escape
import logging
from pathlib import Path

from applypilot.config import TAILORED_DIR

log = logging.getLogger(__name__)


def parse_resume(text: str) -> dict:
    """Parse a structured text resume into sections."""
    lines = [line.rstrip() for line in text.strip().split("\n")]

    header_lines: list[str] = []
    body_start = 0
    for index, line in enumerate(lines):
        if line.strip().upper() == "SUMMARY":
            body_start = index
            break
        if line.strip():
            header_lines.append(line.strip())

    name = header_lines[0] if len(header_lines) > 0 else ""
    title = header_lines[1] if len(header_lines) > 1 else ""

    location = ""
    contact = ""
    if len(header_lines) > 3:
        location = header_lines[2]
        contact = header_lines[3]
    elif len(header_lines) > 2:
        if "@" in header_lines[2] or "|" in header_lines[2]:
            contact = header_lines[2]
        else:
            location = header_lines[2]

    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines[body_start:]:
        stripped = line.strip()
        if (
            stripped
            and stripped == stripped.upper()
            and not stripped.startswith("-")
            and len(stripped) > 3
            and not stripped.startswith("\u2022")
        ):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = stripped
            current_lines = []
        else:
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return {
        "name": name,
        "title": title,
        "location": location,
        "contact": contact,
        "sections": sections,
    }


def parse_skills(text: str) -> list[tuple[str, str]]:
    """Parse a skills section into (category, value) tuples."""
    skills: list[tuple[str, str]] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            category, value = line.split(":", 1)
            skills.append((category.strip(), value.strip()))
    return skills


def parse_entries(text: str) -> list[dict]:
    """Parse experience or project entries from section text."""
    entries: list[dict] = []
    current: dict | None = None

    for line in text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") or stripped.startswith("\u2022 "):
            if current:
                current["bullets"].append(stripped[2:].strip())
        elif current is None or (
            not stripped.startswith("-")
            and not stripped.startswith("\u2022")
            and len(current.get("bullets", [])) > 0
        ):
            if current:
                entries.append(current)
            current = {"title": stripped, "subtitle": "", "bullets": []}
        elif current and not current["subtitle"]:
            current["subtitle"] = stripped
        elif current:
            current["bullets"].append(stripped)

    if current:
        entries.append(current)

    return entries


def _escape_with_breaks(text: str) -> str:
    return "<br>".join(escape(part) for part in text.splitlines()) if text else ""


def build_html(resume: dict) -> str:
    """Build professional resume HTML from parsed data."""
    sections = resume["sections"]

    skills_html = ""
    if "TECHNICAL SKILLS" in sections:
        skills = parse_skills(sections["TECHNICAL SKILLS"])
        rows = ""
        for category, value in skills:
            rows += (
                '<div class="skill-row">'
                f'<span class="skill-cat">{escape(category)}:</span> {escape(value)}'
                "</div>\n"
            )
        skills_html = f'<div class="section"><div class="section-title">Technical Skills</div>{rows}</div>'

    exp_html = ""
    if "EXPERIENCE" in sections:
        entries = parse_entries(sections["EXPERIENCE"])
        items = ""
        for entry in entries:
            bullets = "".join(f"<li>{escape(bullet)}</li>" for bullet in entry["bullets"])
            subtitle = (
                f'<div class="entry-subtitle">{escape(entry["subtitle"])}</div>'
                if entry["subtitle"]
                else ""
            )
            items += (
                '<div class="entry">'
                f'<div class="entry-title">{escape(entry["title"])}</div>'
                f"{subtitle}<ul>{bullets}</ul></div>"
            )
        exp_html = f'<div class="section"><div class="section-title">Experience</div>{items}</div>'

    proj_html = ""
    if "PROJECTS" in sections:
        entries = parse_entries(sections["PROJECTS"])
        items = ""
        for entry in entries:
            bullets = "".join(f"<li>{escape(bullet)}</li>" for bullet in entry["bullets"])
            subtitle = (
                f'<div class="entry-subtitle">{escape(entry["subtitle"])}</div>'
                if entry["subtitle"]
                else ""
            )
            items += (
                '<div class="entry">'
                f'<div class="entry-title">{escape(entry["title"])}</div>'
                f"{subtitle}<ul>{bullets}</ul></div>"
            )
        proj_html = f'<div class="section"><div class="section-title">Projects</div>{items}</div>'

    edu_html = ""
    if "EDUCATION" in sections:
        edu_html = (
            '<div class="section"><div class="section-title">Education</div>'
            f'<div class="edu">{_escape_with_breaks(sections["EDUCATION"].strip())}</div></div>'
        )

    summary_html = ""
    if "SUMMARY" in sections:
        summary_html = (
            '<div class="section"><div class="section-title">Summary</div>'
            f'<div class="summary">{_escape_with_breaks(sections["SUMMARY"].strip())}</div></div>'
        )

    contact_parts = [escape(part.strip()) for part in resume["contact"].split("|")] if resume["contact"] else []
    contact_html = " &nbsp;|&nbsp; ".join(contact_parts)
    location_html = f'<div class="location">{escape(resume["location"])}</div>' if resume["location"] else ""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: letter;
    margin: 0.35in 0.5in;
}}
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}
body {{
    font-family: "Calibri", "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.35;
    color: #1a1a1a;
}}
.header {{
    text-align: center;
    margin-bottom: 4px;
    padding-bottom: 4px;
    border-bottom: 1.5px solid #2a7ab5;
}}
.name {{
    font-size: 18pt;
    font-weight: 700;
    color: #1a3a5c;
    letter-spacing: 0.5px;
}}
.title {{
    font-size: 10.5pt;
    color: #3a6b8c;
    margin: 1px 0;
}}
.location {{
    font-size: 9pt;
    color: #555;
}}
.contact {{
    font-size: 9pt;
    color: #444;
    margin-top: 1px;
}}
.section {{
    margin-top: 5px;
}}
.section-title {{
    font-size: 10pt;
    font-weight: 700;
    color: #1a3a5c;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    border-bottom: 1.5px solid #2a7ab5;
    padding-bottom: 1px;
    margin-bottom: 3px;
}}
.summary {{
    font-size: 9.5pt;
    color: #333;
    line-height: 1.4;
}}
.skill-row {{
    font-size: 9.5pt;
    line-height: 1.35;
}}
.skill-cat {{
    font-weight: 600;
    color: #1a3a5c;
}}
.entry {{
    margin-bottom: 4px;
    break-inside: avoid;
}}
.entry-title {{
    font-weight: 600;
    font-size: 10pt;
    color: #1a3a5c;
}}
.entry-subtitle {{
    font-size: 9pt;
    color: #4a7a9b;
    font-style: italic;
    margin-bottom: 1px;
}}
ul {{
    margin-left: 14px;
    padding: 0;
}}
li {{
    font-size: 9.5pt;
    margin-bottom: 1px;
    line-height: 1.35;
}}
.edu {{
    font-size: 10pt;
}}
</style>
</head>
<body>
<div class="header">
    <div class="name">{escape(resume["name"])}</div>
    <div class="title">{escape(resume["title"])}</div>
    {location_html}
    <div class="contact">{contact_html}</div>
</div>
{summary_html}
{skills_html}
{exp_html}
{proj_html}
{edu_html}
</body>
</html>"""


def build_cover_letter_html(text: str) -> str:
    """Build a simple, printable HTML letter layout."""
    paragraphs = [block.strip() for block in text.strip().split("\n\n") if block.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]

    body = "\n".join(f"<p>{_escape_with_breaks(paragraph)}</p>" for paragraph in paragraphs)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: letter;
    margin: 0.7in;
}}
body {{
    font-family: "Calibri", "Segoe UI", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
}}
.letter {{
    max-width: 7in;
}}
p {{
    margin: 0 0 0.9rem 0;
}}
</style>
</head>
<body>
<div class="letter">
{body}
</div>
</body>
</html>"""


def render_pdf(html: str, output_path: str) -> None:
    """Render HTML to PDF using Playwright's headless Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=output_path,
            format="Letter",
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            print_background=True,
        )
        browser.close()


def convert_to_pdf(
    text_path: Path,
    output_path: Path | None = None,
    html_only: bool = False,
) -> Path:
    """Convert a structured text resume to PDF."""
    text_path = Path(text_path)
    text = text_path.read_text(encoding="utf-8")
    resume = parse_resume(text)
    html = build_html(resume)

    if html_only:
        out = Path(output_path or text_path.with_suffix(".html"))
        out.write_text(html, encoding="utf-8")
        log.info("HTML generated: %s", out)
        return out

    out = Path(output_path or text_path.with_suffix(".pdf"))
    render_pdf(html, str(out))
    log.info("PDF generated: %s", out)
    return out


def convert_cover_letter_to_pdf(
    text_path: Path,
    output_path: Path | None = None,
    html_only: bool = False,
) -> Path:
    """Convert a plain-text cover letter to PDF."""
    text_path = Path(text_path)
    text = text_path.read_text(encoding="utf-8")
    html = build_cover_letter_html(text)

    if html_only:
        out = Path(output_path or text_path.with_suffix(".html"))
        out.write_text(html, encoding="utf-8")
        log.info("Cover-letter HTML generated: %s", out)
        return out

    out = Path(output_path or text_path.with_suffix(".pdf"))
    render_pdf(html, str(out))
    log.info("Cover-letter PDF generated: %s", out)
    return out


def batch_convert(limit: int = 50) -> int:
    """Convert resume .txt files in TAILORED_DIR that do not have PDFs yet."""
    if not TAILORED_DIR.exists():
        log.warning("Tailored directory does not exist: %s", TAILORED_DIR)
        return 0

    txt_files = sorted(TAILORED_DIR.glob("*.txt"))
    candidates = [
        file_path
        for file_path in txt_files
        if not file_path.name.endswith("_JOB.txt")
        and not file_path.name.endswith("_CL.txt")
    ]

    to_convert: list[Path] = []
    for file_path in candidates:
        pdf_path = file_path.with_suffix(".pdf")
        if not pdf_path.exists():
            to_convert.append(file_path)
        if len(to_convert) >= limit:
            break

    if not to_convert:
        log.info("All resume text files already have PDFs.")
        return 0

    log.info("Converting %d resume files to PDF...", len(to_convert))
    converted = 0
    for file_path in to_convert:
        try:
            convert_to_pdf(file_path)
            converted += 1
        except Exception as exc:
            log.error("Failed to convert %s: %s", file_path.name, exc)

    log.info("Done: %d/%d PDFs generated in %s", converted, len(to_convert), TAILORED_DIR)
    return converted
