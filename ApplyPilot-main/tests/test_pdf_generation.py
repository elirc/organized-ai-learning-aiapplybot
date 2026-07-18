from __future__ import annotations

from pathlib import Path

from applypilot.scoring import pdf


def test_convert_cover_letter_to_pdf_html_uses_letter_layout(tmp_path) -> None:
    cover_letter_path = tmp_path / "role_CL.txt"
    cover_letter_path.write_text(
        "Dear Hiring Manager,\n\nBuilt Python services that reduced manual work by 80%.\n\nAda",
        encoding="utf-8",
    )

    html_path = pdf.convert_cover_letter_to_pdf(cover_letter_path, html_only=True)
    html = html_path.read_text(encoding="utf-8")

    assert "Dear Hiring Manager," in html
    assert "Technical Skills" not in html
    assert "<p>" in html


def test_batch_convert_skips_cover_letter_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pdf, "TAILORED_DIR", tmp_path)

    resume_path = tmp_path / "resume.txt"
    resume_path.write_text("placeholder", encoding="utf-8")
    (tmp_path / "resume_CL.txt").write_text("Dear Hiring Manager,", encoding="utf-8")
    (tmp_path / "resume_JOB.txt").write_text("Job description", encoding="utf-8")

    converted_files: list[str] = []

    def fake_convert_to_pdf(text_path: Path, output_path: Path | None = None, html_only: bool = False) -> Path:
        converted_files.append(Path(text_path).name)
        out = Path(text_path).with_suffix(".pdf")
        out.write_text("pdf", encoding="utf-8")
        return out

    monkeypatch.setattr(pdf, "convert_to_pdf", fake_convert_to_pdf)

    converted_count = pdf.batch_convert()

    assert converted_count == 1
    assert converted_files == ["resume.txt"]
