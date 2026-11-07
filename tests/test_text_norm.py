# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from app import storage
from app.text_norm import normalize_search, slugify_tag, strip_accents


def test_strip_accents_vietnamese() -> None:
    assert strip_accents("Đồ án") == "Do an"


def test_strip_accents_d_stroke() -> None:
    assert strip_accents("đ") == "d"
    assert strip_accents("Đ") == "D"


def test_normalize_search_drops_punctuation() -> None:
    assert normalize_search("Nhiễm Khuẩn!") == "nhiem khuan"


def test_normalize_search_empty() -> None:
    assert normalize_search("   ") == ""


def test_normalize_search_matches_storage() -> None:
    for text in ("Nhiễm Khuẩn", "Báo cáo 2026", "Đồ án!?", ""):
        assert normalize_search(text) == storage.normalize_search(text)


def test_slugify_tag() -> None:
    assert slugify_tag("Medical Blue") == "medical-blue"
    assert slugify_tag("  ") == ""
