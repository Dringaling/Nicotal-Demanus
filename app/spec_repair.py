# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from typing import Any

_LAYOUTS = {
    "title",
    "section",
    "bullets",
    "two_column",
    "table",
    "quote",
    "closing",
}
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_PALETTE_KEYS = {"primary", "accent", "text", "muted", "background"}


def _text(value: Any, limit: int, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return (text or default)[:limit]


def _bullet(value: Any) -> dict | None:
    if isinstance(value, str):
        text, level = value.strip(), 0
    elif isinstance(value, dict):
        text = str(value.get("text", "")).strip()
        try:
            level = int(value.get("level", 0) or 0)
        except (TypeError, ValueError):
            level = 0
    else:
        return None
    if not text:
        return None
    return {"text": text[:220], "level": min(max(level, 0), 2)}


def _bullets(values: Any, limit: int = 8) -> list[dict]:
    if not isinstance(values, list):
        return []
    result: list[dict] = []
    for value in values:
        item = _bullet(value)
        if item is not None:
            result.append(item)
        if len(result) >= limit:
            break
    return result


def _column(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    heading = value.get("heading")
    heading_text = str(heading).strip()[:120] if heading else None
    return {
        "heading": heading_text or None,
        "bullets": _bullets(value.get("bullets")),
    }


def _table(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    raw_headers = value.get("headers")
    if not isinstance(raw_headers, list):
        return None
    headers = [
        str(header).strip()[:80]
        for header in raw_headers
        if str(header).strip()
    ][:6]
    if not headers:
        return None

    raw_rows = value.get("rows")
    if not isinstance(raw_rows, list):
        raw_rows = []
    rows: list[list[str]] = []
    for row in raw_rows[:8]:
        if not isinstance(row, list):
            continue
        cells = [str(cell).strip()[:200] for cell in row[: len(headers)]]
        cells += [""] * (len(headers) - len(cells))
        rows.append(cells)
    return {"headers": headers, "rows": rows}


def sanitize_slide(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None

    layout = value.get("layout")
    if layout not in _LAYOUTS:
        layout = "bullets"

    slide: dict[str, Any] = {
        "layout": layout,
        "title": _text(value.get("title"), 160, "Cần bổ sung"),
    }
    if value.get("subtitle") is not None:
        slide["subtitle"] = _text(value.get("subtitle"), 300)

    bullets = _bullets(value.get("bullets"))
    raw_columns = value.get("columns")
    columns = []
    if isinstance(raw_columns, list):
        for item in raw_columns[:2]:
            column = _column(item)
            if column is not None:
                columns.append(column)
    table = _table(value.get("table"))

    if layout == "two_column":
        if len(columns) >= 2:
            slide["columns"] = columns[:2]
        else:
            slide["layout"] = "bullets"
            layout = "bullets"
            flattened = [
                bullet for column in columns for bullet in column["bullets"]
            ]
            bullets = flattened[:8] or bullets

    if layout == "table" and table is None:
        slide["layout"] = "bullets"
        layout = "bullets"

    if layout == "bullets" and not bullets:
        bullets = [{"text": "Cần bổ sung", "level": 0}]

    if bullets:
        slide["bullets"] = bullets
    if table is not None:
        slide["table"] = table
    if value.get("note") is not None:
        slide["note"] = _text(value.get("note"), 2000)
    return slide


def sanitize_deck(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Deck spec phải là object JSON")

    raw_slides = value.get("slides")
    if not isinstance(raw_slides, list):
        raw_slides = []

    slides = []
    for item in raw_slides:
        slide = sanitize_slide(item)
        if slide is not None:
            slides.append(slide)

    deck: dict[str, Any] = {
        "title": _text(value.get("title"), 200, "Báo cáo"),
        "slides": slides
        or [{"layout": "title", "title": _text(value.get("title"), 160, "Báo cáo")}],
    }
    if value.get("subtitle") is not None:
        deck["subtitle"] = _text(value.get("subtitle"), 300)
    if value.get("author") is not None:
        deck["author"] = _text(value.get("author"), 120)

    font = value.get("font")
    if isinstance(font, str) and font.strip():
        deck["font"] = font.strip()[:80]

    palette = value.get("palette")
    if isinstance(palette, dict):
        cleaned = {
            key: item
            for key, item in palette.items()
            if key in _PALETTE_KEYS
            and isinstance(item, str)
            and _HEX.fullmatch(item)
        }
        if cleaned:
            deck["palette"] = cleaned

    return deck
