# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence
from urllib.parse import quote

from .text_norm import normalize_search, slugify_tag

MAX_TAG_LEN = 32
TAG_LABEL_MAX = 18
MAX_FILTER_TAGS = 30


class TagError(ValueError):
    """Tag không hợp lệ."""


def normalize_tag(raw: object) -> str:
    """Chuẩn hoá một tag về dạng không dấu, không khoảng cách."""
    tag = slugify_tag(str(raw))
    if not tag:
        raise TagError(
            "Tag không hợp lệ: chỉ chữ không dấu, số và dấu gạch ngang."
        )
    if len(tag) > MAX_TAG_LEN:
        raise TagError(f"Tag tối đa {MAX_TAG_LEN} ký tự")
    return tag


def normalize_tag_list(raw_tags: Sequence[object] | None) -> list[str]:
    """Chuẩn hoá danh sách tag, bỏ trùng, giữ thứ tự xuất hiện."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_tags or ():
        tag = normalize_tag(raw)
        if tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return result


def tag_key(raw: object) -> str:
    """Khoá so khớp tag; không raise với dữ liệu cũ."""
    try:
        return normalize_tag(raw)
    except TagError:
        return str(raw).strip().casefold()


def limit_filter_tags(tags: Sequence[str] | None) -> list[str]:
    """Giới hạn số tag dùng để lọc, tránh URL quá dài."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in tags or ():
        key = tag_key(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
        if len(result) >= MAX_FILTER_TAGS:
            break
    return result


def truncate_label(name: str, limit: int = TAG_LABEL_MAX) -> str:
    if len(name) <= limit:
        return name
    return name[: limit - 1] + "…"


@dataclass(frozen=True)
class TagItem:
    name: str
    key: str
    label: str
    count: int
    selected: bool
    delete_action: str = ""


@dataclass(frozen=True)
class TagLayout:
    dom_id: str
    title: str
    items: tuple[TagItem, ...] = ()
    query: str = ""
    search_param: str = "tq"
    filter_param: str = "tags"
    hidden_fields: dict[str, str] = field(default_factory=dict)
    selected: tuple[str, ...] = ()
    show_select_all: bool = False
    show_deselect_all: bool = False
    total: int = 0
    matched: int = 0
    clear_url: str = ""


def build_tag_layout(
    *,
    dom_id: str,
    title: str,
    counts: Mapping[str, int],
    selected: Sequence[str] = (),
    query: str = "",
    search_param: str = "tq",
    filter_param: str = "tags",
    hidden_fields: Mapping[str, str] | None = None,
    delete_base: str = "",
    clear_url: str = "",
) -> TagLayout:
    """Dựng dữ liệu cho một Tags Layout (dùng chung cho tag input và tag theme)."""
    selected_keys = {tag_key(tag) for tag in selected if str(tag).strip()}
    needle = normalize_search(query)
    rows: list[tuple[str, str, int]] = []
    for name, count in counts.items():
        key = tag_key(name)
        if needle and needle not in normalize_search(name):
            continue
        rows.append((name, key, int(count)))
    rows.sort(key=lambda row: (-row[2], row[0].casefold()))

    items = tuple(
        TagItem(
            name=name,
            key=key,
            label=truncate_label(name),
            count=count,
            selected=key in selected_keys,
            delete_action=(
                f"{delete_base.rstrip('/')}/{quote(name)}/delete"
                if delete_base
                else ""
            ),
        )
        for name, key, count in rows
    )
    has_unselected = any(not item.selected for item in items)
    return TagLayout(
        dom_id=dom_id,
        title=title,
        items=items,
        query=query or "",
        search_param=search_param,
        filter_param=filter_param,
        hidden_fields=dict(hidden_fields or {}),
        selected=tuple(selected_keys),
        show_select_all=bool(needle) and has_unselected,
        show_deselect_all=any(item.selected for item in items),
        total=len(counts),
        matched=len(items),
        clear_url=clear_url,
    )
