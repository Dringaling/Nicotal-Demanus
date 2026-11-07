# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import html
import re
from urllib.parse import urlparse

_HEADING = re.compile(r"^(#{1,3})\s+(.+)$")
_BULLET = re.compile(r"^[-*]\s+(.+)$")
_ORDERED = re.compile(r"^\d+\.\s+(.+)$")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_SAFE_SCHEMES = {"", "http", "https", "mailto"}


def _safe_href(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme.lower() not in _SAFE_SCHEMES:
        return "#"
    return url


def _inline(text: str) -> str:
    value = html.escape(text, quote=False)
    value = _CODE.sub(r"<code>\1</code>", value)
    value = _BOLD.sub(r"<strong>\1</strong>", value)
    return _LINK.sub(
        lambda match: (
            f'<a href="{html.escape(_safe_href(match.group(2)))}">'
            f"{match.group(1)}</a>"
        ),
        value,
    )


def render_markdown(text: str) -> str:
    """Render markdown tối giản, escape HTML trước khi xử lý cú pháp."""
    blocks: list[str] = []
    paragraph: list[str] = []
    list_kind: str | None = None

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_kind is not None:
            blocks.append(f"</{list_kind}>")
            list_kind = None

    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue

        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            blocks.append(
                f"<h{level}>{_inline(heading.group(2))}</h{level}>"
            )
            continue

        bullet = _BULLET.match(line)
        ordered = _ORDERED.match(line)
        if bullet or ordered:
            flush_paragraph()
            kind = "ul" if bullet else "ol"
            if list_kind != kind:
                flush_list()
                blocks.append(f"<{kind}>")
                list_kind = kind
            item = (bullet or ordered).group(1)
            blocks.append(f"<li>{_inline(item)}</li>")
            continue

        flush_list()
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)
