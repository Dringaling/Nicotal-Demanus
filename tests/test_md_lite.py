# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from app.md_lite import render_markdown


def test_heading_levels() -> None:
    html = render_markdown("# A\n\n## B\n\n### C")

    assert "<h1>A</h1>" in html
    assert "<h2>B</h2>" in html
    assert "<h3>C</h3>" in html


def test_unordered_list() -> None:
    assert "<ul>\n<li>a</li>\n<li>b</li>\n</ul>" in render_markdown("- a\n- b")


def test_ordered_list() -> None:
    assert "<ol>\n<li>a</li>\n<li>b</li>\n</ol>" in render_markdown("1. a\n2. b")


def test_inline_bold_and_code() -> None:
    html = render_markdown("**bold** và `code`")

    assert "<strong>bold</strong>" in html
    assert "<code>code</code>" in html


def test_link() -> None:
    html = render_markdown("[x](https://example.com)")

    assert '<a href="https://example.com">x</a>' in html


def test_unsafe_link_scheme_is_neutralized() -> None:
    html = render_markdown("[x](javascript:void)")

    assert 'href="#"' in html
    assert "javascript" not in html


def test_html_is_escaped() -> None:
    html = render_markdown("<script>alert(1)</script>")

    assert "&lt;script&gt;" in html
    assert "<script>" not in html


def test_paragraphs_split_on_blank_line() -> None:
    html = render_markdown("một\n\nhai")

    assert html.count("<p>") == 2


def test_lines_in_one_paragraph_are_joined() -> None:
    html = render_markdown("một\nhai")

    assert html == "<p>một hai</p>"
