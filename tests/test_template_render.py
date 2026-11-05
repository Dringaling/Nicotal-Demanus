# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from app.sample import sample_deck
from app.template_render import render_deck_with_template

TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "Dividing Fractions by Fractions Lesson.pptx"
)


def test_template_render_preserves_layouts(tmp_path: Path) -> None:
    out = render_deck_with_template(
        sample_deck(), TEMPLATE, tmp_path / "deck.pptx"
    )
    prs = Presentation(out)

    assert len(prs.slides) == len(sample_deck().slides)
    assert prs.slide_width == Inches(10)
    assert prs.slide_height == Inches(5.625)

    layouts = [slide.slide_layout.name for slide in prs.slides]
    assert layouts == [
        "TITLE",
        "SECTION_HEADER",
        "TITLE_AND_BODY",
        "TITLE_AND_TWO_COLUMNS",
        "TITLE_ONLY",
        "MAIN_POINT",
        "TITLE",
    ]


def test_template_render_keeps_title_text(tmp_path: Path) -> None:
    out = render_deck_with_template(
        sample_deck(), TEMPLATE, tmp_path / "deck.pptx"
    )
    prs = Presentation(out)
    first = prs.slides[0]
    assert first.shapes.title.text == sample_deck().slides[0].title


def test_template_render_reopens(tmp_path: Path) -> None:
    out = render_deck_with_template(
        sample_deck(), TEMPLATE, tmp_path / "deck.pptx"
    )
    prs = Presentation(out)
    assert prs.core_properties.title == sample_deck().title
