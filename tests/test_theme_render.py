from __future__ import annotations

from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches

from app.sample import sample_deck
from app.templates_catalog import get_template
from app.theme_render import render_deck_theme


def test_theme_render_creates_deck(tmp_path: Path) -> None:
    meta = get_template("neo_tech_minimal")
    assert meta is not None
    out = render_deck_theme(sample_deck(), meta, tmp_path / "deck.pptx")
    prs = Presentation(out)
    assert len(prs.slides) == len(sample_deck().slides)
    assert prs.slide_width == Inches(13.333)
    assert prs.slide_height == Inches(7.5)


def test_theme_render_uses_lexend(tmp_path: Path) -> None:
    meta = get_template("neo_tech_minimal")
    assert meta is not None
    out = render_deck_theme(sample_deck(), meta, tmp_path / "deck.pptx")
    prs = Presentation(out)
    first = prs.slides[0]
    assert len(first.shapes) >= 2

    fonts = set()
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.text.strip():
                        fonts.add(run.font.name)
    assert fonts == {"Lexend"}


@pytest.mark.parametrize(
    "theme_id",
    ["gruvbox", "soft_light", "cappuccino", "latte", "cream_pink"],
)
def test_generated_theme_renders(tmp_path: Path, theme_id: str) -> None:
    meta = get_template(theme_id)
    assert meta is not None
    out = render_deck_theme(sample_deck(), meta, tmp_path / f"{theme_id}.pptx")
    prs = Presentation(out)
    assert len(prs.slides) == len(sample_deck().slides)
    assert prs.slide_width == Inches(13.333)
    assert prs.slide_height == Inches(7.5)
