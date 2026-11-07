# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.changelog import (
    current_version,
    load_changelog,
    refresh_changelog,
    version_for_module,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    refresh_changelog()
    yield
    refresh_changelog()


def write_entry(folder: Path, version: str, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{version}.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_version_for_module() -> None:
    assert version_for_module(1) == "1.0"
    assert version_for_module(10) == "1.9"
    assert version_for_module(11) == "2.0"
    assert version_for_module(21) == "3.0"
    assert version_for_module(24) == "3.3"


def test_loads_all_entries() -> None:
    entries = load_changelog()

    assert len(entries) >= 24
    assert entries[0].version == "3.3"
    assert entries[-1].version == "1.0"


def test_sorted_numerically() -> None:
    versions = [entry.version for entry in load_changelog()]

    assert versions.index("3.2") < versions.index("2.9")
    assert versions.index("2.9") < versions.index("1.9")


def test_sort_handles_double_digit_minor(tmp_path: Path) -> None:
    write_entry(tmp_path, "1.10", "# Mười\n")
    write_entry(tmp_path, "1.9", "# Chín\n")

    versions = [entry.version for entry in load_changelog(tmp_path)]
    assert versions == ["1.10", "1.9"]


def test_heading_becomes_title(tmp_path: Path) -> None:
    write_entry(tmp_path, "1.0", "# Tiêu đề\n\n- một\n")
    entry = load_changelog(tmp_path)[0]

    assert entry.title == "Tiêu đề"
    assert "<h1>" not in entry.html
    assert "<li>một</li>" in entry.html


def test_missing_heading_falls_back_to_version(tmp_path: Path) -> None:
    write_entry(tmp_path, "1.2", "- chỉ có bullet\n")
    entry = load_changelog(tmp_path)[0]

    assert entry.title == "v1.2"


def test_invalid_filename_skipped(tmp_path: Path) -> None:
    write_entry(tmp_path, "1.0", "# A\n")
    (tmp_path / "changelog-old.md").write_text("# B\n", encoding="utf-8")

    assert [entry.version for entry in load_changelog(tmp_path)] == ["1.0"]


def test_empty_file_skipped(tmp_path: Path) -> None:
    write_entry(tmp_path, "1.0", "# A\n")
    write_entry(tmp_path, "1.1", "   \n")

    assert [entry.version for entry in load_changelog(tmp_path)] == ["1.0"]


def test_html_is_escaped(tmp_path: Path) -> None:
    write_entry(tmp_path, "1.0", "# A\n\n<script>alert(1)</script>\n")
    entry = load_changelog(tmp_path)[0]

    assert "&lt;script&gt;" in entry.html


def test_missing_directory_returns_empty(tmp_path: Path) -> None:
    assert load_changelog(tmp_path / "khong-co") == []


def test_current_version(tmp_path: Path) -> None:
    write_entry(tmp_path, "1.0", "# A\n")
    write_entry(tmp_path, "2.3", "# B\n")

    assert current_version(tmp_path) == "2.3"
    assert current_version(tmp_path / "khong-co") == ""


def test_cache_refreshes_on_change(tmp_path: Path) -> None:
    path = write_entry(tmp_path, "1.0", "# Một\n")
    assert "Một" in load_changelog(tmp_path)[0].title

    path.write_text("# Hai\n", encoding="utf-8")
    later = time.time() + 5
    os.utime(path, (later, later))


    assert load_changelog(tmp_path)[0].title == "Hai"


def test_refresh_changelog_clears_cache(tmp_path: Path) -> None:
    path = write_entry(tmp_path, "1.0", "# Một\n")
    load_changelog(tmp_path)
    path.write_text("# Hai\n", encoding="utf-8")
    refresh_changelog()

    assert load_changelog(tmp_path)[0].title == "Hai"
