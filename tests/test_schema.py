# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schema import DeckSpec, SlideSpec, TableBlock


def test_minimal_deck_parses() -> None:
    spec = DeckSpec.model_validate(
        {
            "title": "Báo cáo",
            "slides": [{"layout": "title", "title": "Báo cáo"}],
        }
    )
    assert spec.font == "Lexend"
    assert len(spec.slides) == 1


def test_table_layout_requires_table() -> None:
    with pytest.raises(ValidationError, match="cần trường 'table'"):
        SlideSpec.model_validate({"layout": "table", "title": "Bảng"})


def test_table_row_width_must_match_headers() -> None:
    with pytest.raises(ValidationError, match="cần đúng 3 ô"):
        TableBlock.model_validate(
            {"headers": ["a", "b", "c"], "rows": [["1", "2"]]}
        )


def test_two_column_requires_two_columns() -> None:
    with pytest.raises(ValidationError, match="cần đúng 2 cột"):
        SlideSpec.model_validate(
            {
                "layout": "two_column",
                "title": "So sánh",
                "columns": [{"heading": "A", "bullets": []}],
            }
        )


def test_bullets_layout_requires_bullets() -> None:
    with pytest.raises(ValidationError, match="ít nhất 1 bullet"):
        SlideSpec.model_validate({"layout": "bullets", "title": "Danh sách"})


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SlideSpec.model_validate(
            {"layout": "title", "title": "Báo cáo", "unknown": "x"}
        )


def test_invalid_palette_color_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DeckSpec.model_validate(
            {
                "title": "Báo cáo",
                "palette": {"primary": "navy"},
                "slides": [{"layout": "title", "title": "Báo cáo"}],
            }
        )


def test_too_many_slides_is_rejected() -> None:
    slides = [{"layout": "title", "title": f"Slide {i}"} for i in range(61)]
    with pytest.raises(ValidationError):
        DeckSpec.model_validate({"title": "Báo cáo", "slides": slides})


def test_sixty_slides_are_accepted() -> None:
    slides = [{"layout": "title", "title": f"Slide {i}"} for i in range(60)]
    spec = DeckSpec.model_validate({"title": "Báo cáo", "slides": slides})
    assert len(spec.slides) == 60
