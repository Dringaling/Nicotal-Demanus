# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from app.schema import DeckSpec
from app.spec_repair import sanitize_deck


def test_two_column_truncates_to_two() -> None:
    deck = sanitize_deck(
        {
            "title": "Báo cáo",
            "slides": [
                {
                    "layout": "two_column",
                    "title": "So sánh",
                    "columns": [
                        {"heading": "A", "bullets": [{"text": "a"}]},
                        {"heading": "B", "bullets": [{"text": "b"}]},
                        {"heading": "C", "bullets": [{"text": "c"}]},
                    ],
                }
            ],
        }
    )
    slide = deck["slides"][0]
    assert slide["layout"] == "two_column"
    assert len(slide["columns"]) == 2
    DeckSpec.model_validate(deck)


def test_two_column_with_one_column_becomes_bullets() -> None:
    deck = sanitize_deck(
        {
            "title": "Báo cáo",
            "slides": [
                {
                    "layout": "two_column",
                    "title": "Một cột",
                    "columns": [
                        {"heading": "A", "bullets": [{"text": "a"}]}
                    ],
                }
            ],
        }
    )
    slide = deck["slides"][0]
    assert slide["layout"] == "bullets"
    assert slide["bullets"][0]["text"] == "a"
    DeckSpec.model_validate(deck)


def test_table_rows_are_padded_and_trimmed() -> None:
    deck = sanitize_deck(
        {
            "title": "Báo cáo",
            "slides": [
                {
                    "layout": "table",
                    "title": "Bảng",
                    "table": {
                        "headers": ["A", "B"],
                        "rows": [["1"], ["1", "2", "3"]],
                    },
                }
            ],
        }
    )
    table = deck["slides"][0]["table"]
    assert table["rows"] == [["1", ""], ["1", "2"]]
    DeckSpec.model_validate(deck)


def test_bullets_layout_gets_placeholder() -> None:
    deck = sanitize_deck(
        {
            "title": "Báo cáo",
            "slides": [{"layout": "bullets", "title": "Trống"}],
        }
    )
    assert deck["slides"][0]["bullets"][0]["text"] == "Cần bổ sung"
    DeckSpec.model_validate(deck)


def test_invalid_layout_and_extra_fields_are_removed() -> None:
    deck = sanitize_deck(
        {
            "title": "Báo cáo",
            "unexpected": True,
            "slides": [
                {
                    "layout": "unknown",
                    "title": "X",
                    "extra": 1,
                    "bullets": [{"text": "a", "extra": 2}],
                }
            ],
        }
    )
    slide = deck["slides"][0]
    assert slide["layout"] == "bullets"
    assert "extra" not in slide
    assert "unexpected" not in deck
    DeckSpec.model_validate(deck)


def test_empty_slides_falls_back_to_title() -> None:
    deck = sanitize_deck({"title": "Báo cáo", "slides": []})
    assert deck["slides"][0]["layout"] == "title"
    DeckSpec.model_validate(deck)
