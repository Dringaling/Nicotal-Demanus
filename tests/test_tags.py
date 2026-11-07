# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import pytest

from app.tags import (
    MAX_TAG_LEN,
    TagError,
    build_tag_layout,
    normalize_tag,
    normalize_tag_list,
)


def test_normalize_tag_spaces() -> None:
    assert normalize_tag("Medical Blue") == "medical-blue"


def test_normalize_tag_accents() -> None:
    assert normalize_tag("Nhiễm Khuẩn") == "nhiem-khuan"


def test_normalize_tag_symbols() -> None:
    assert normalize_tag("a/b_c.d") == "a-b-c-d"


def test_normalize_tag_collapses_dashes() -> None:
    assert normalize_tag("--a---b--") == "a-b"


def test_normalize_tag_casefold() -> None:
    assert normalize_tag("ABC") == "abc"


def test_normalize_tag_empty() -> None:
    with pytest.raises(TagError) as exc:
        normalize_tag("  ")
    assert "gạch ngang" in str(exc.value)


def test_normalize_tag_too_long() -> None:
    with pytest.raises(TagError) as exc:
        normalize_tag("a" * (MAX_TAG_LEN + 1))
    assert "tối đa" in str(exc.value)


def test_normalize_tag_list_dedupes() -> None:
    assert normalize_tag_list(["A B", "a-b", "C"]) == ["a-b", "c"]


def test_layout_sorted_by_count_then_name() -> None:
    layout = build_tag_layout(
        dom_id="tags",
        title="Tags",
        counts={"b": 2, "a": 2, "c": 5},
    )

    assert [item.name for item in layout.items] == ["c", "a", "b"]


def test_layout_search_matches_accent_insensitive() -> None:
    layout = build_tag_layout(
        dom_id="tags",
        title="Tags",
        counts={"nhiem-khuan": 1, "medical": 2},
        query="NHIEM",
    )

    assert [item.name for item in layout.items] == ["nhiem-khuan"]


def test_layout_label_is_truncated() -> None:
    name = "a" * 30
    layout = build_tag_layout(dom_id="tags", title="Tags", counts={name: 1})
    item = layout.items[0]

    assert item.name == name
    assert item.label.endswith("…")
    assert len(item.label) < len(name)


def test_layout_selected_is_normalized() -> None:
    layout = build_tag_layout(
        dom_id="tags",
        title="Tags",
        counts={"medical-blue": 1},
        selected=["Medical Blue"],
    )

    assert layout.items[0].selected is True
    assert layout.show_deselect_all is True


def test_layout_select_all_flags() -> None:
    plain = build_tag_layout(dom_id="tags", title="Tags", counts={"a": 1})
    assert plain.show_select_all is False

    searched = build_tag_layout(
        dom_id="tags", title="Tags", counts={"a": 1, "b": 2}, query="a"
    )
    assert searched.show_select_all is True

    all_selected = build_tag_layout(
        dom_id="tags",
        title="Tags",
        counts={"a": 1},
        selected=["a"],
        query="a",
    )
    assert all_selected.show_select_all is False


def test_layout_hidden_fields_and_clear_url() -> None:
    layout = build_tag_layout(
        dom_id="tags",
        title="Tags",
        counts={"a": 1},
        hidden_fields={"q": "bao"},
        clear_url="/?q=bao",
    )

    assert layout.hidden_fields == {"q": "bao"}
    assert layout.clear_url == "/?q=bao"


def test_layout_delete_action() -> None:
    layout = build_tag_layout(
        dom_id="tags",
        title="Tags",
        counts={"a b": 1},
        delete_base="/tags",
    )

    assert layout.items[0].delete_action == "/tags/a%20b/delete"
