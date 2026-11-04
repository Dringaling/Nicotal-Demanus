from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches

from app.render import render_deck
from app.sample import sample_deck


def _render(tmp_path: Path) -> Path:
    out = tmp_path / "deck.pptx"
    render_deck(sample_deck(), out)
    return out


def test_render_creates_file(tmp_path: Path) -> None:
    out = _render(tmp_path)
    assert out.is_file()
    assert out.stat().st_size > 0


def test_slide_count_and_size(tmp_path: Path) -> None:
    prs = Presentation(_render(tmp_path))
    assert len(prs.slides) == len(sample_deck().slides)
    assert prs.slide_width == Inches(13.333)
    assert prs.slide_height == Inches(7.5)


def test_render_uses_lexend(tmp_path: Path) -> None:
    prs = Presentation(_render(tmp_path))
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    assert run.font.name == "Lexend"


def test_header_block_is_primary(tmp_path: Path) -> None:
    prs = Presentation(_render(tmp_path))
    bullets_slide = prs.slides[2]
    main_header = bullets_slide.shapes[1]
    assert main_header.fill.fore_color.rgb == RGBColor(0x1B, 0x2A, 0x4A)


def test_table_dimensions(tmp_path: Path) -> None:
    prs = Presentation(_render(tmp_path))
    table_slide = prs.slides[4]
    tables = [shape.table for shape in table_slide.shapes if shape.has_table]
    assert len(tables) == 1
    table = tables[0]
    assert len(table.rows) == 4
    assert len(table.columns) == 3


def test_speaker_note_written(tmp_path: Path) -> None:
    prs = Presentation(_render(tmp_path))
    note = prs.slides[2].notes_slide.notes_text_frame.text
    assert "Hỏi kỹ thời điểm khởi phát" in note


def test_vietnamese_text_preserved(tmp_path: Path) -> None:
    prs = Presentation(_render(tmp_path))
    bullets_slide = prs.slides[2]
    texts = [
        run.text
        for shape in bullets_slide.shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
    ]
    assert any("Triệu chứng cơ năng chính" in text for text in texts)


def test_render_is_reopenable(tmp_path: Path) -> None:
    out = _render(tmp_path)
    prs = Presentation(out)
    assert prs.core_properties.title == sample_deck().title
