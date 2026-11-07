# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.config import ConfigError
from app.help_docs import (
    HelpError,
    help_layouts,
    load_help,
    load_help_config,
    refresh_help,
    render_help,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    refresh_help()
    yield
    refresh_help()


def write_help(tmp_path: Path, docs: dict[str, str], layouts: str) -> tuple[Path, Path]:
    help_dir = tmp_path / "help"
    help_dir.mkdir(parents=True)
    for name, body in docs.items():
        (help_dir / name).write_text(body, encoding="utf-8")
    config = tmp_path / "help.toml"
    config.write_text(layouts, encoding="utf-8")
    return config, help_dir


def test_load_real_config() -> None:
    config = load_help_config()

    assert "tags" in config
    assert config["tags"]["docs"][0] == "tags-search.md"


def test_render_real_layout() -> None:
    doc = render_help("tags")

    assert doc.title == "Tags"
    assert "Tìm tag" in doc.html
    assert doc.docs


def test_shared_doc_between_layouts() -> None:
    tags = render_help("tags")
    theme_tags = render_help("theme-tags")

    assert "tags-search.md" in tags.docs
    assert "tags-search.md" in theme_tags.docs


def test_unknown_layout() -> None:
    with pytest.raises(HelpError):
        render_help("khong-co")


def test_layouts_listed() -> None:
    layouts = help_layouts()

    assert "input" in layouts
    assert "theme-edit" in layouts


def test_invalid_docs_type(tmp_path: Path) -> None:
    config = tmp_path / "help.toml"
    config.write_text('[layouts.x]\ndocs = "a.md"\n', encoding="utf-8")

    with pytest.raises(ConfigError):
        load_help_config(config)


def test_missing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_help_config(tmp_path / "missing.toml")


def test_missing_file_is_skipped(tmp_path: Path) -> None:
    config, help_dir = write_help(
        tmp_path,
        {"a.md": "# A\n"},
        '[layouts.x]\ndocs = ["a.md", "thieu.md"]\n',
    )

    doc = render_help("x", config, help_dir)

    assert doc.docs == ("a.md",)
    assert "A" in doc.html


def test_path_traversal_rejected(tmp_path: Path) -> None:
    config, help_dir = write_help(
        tmp_path, {}, '[layouts.x]\ndocs = ["../secret/x.md"]\n'
    )

    with pytest.raises(ConfigError):
        render_help("x", config, help_dir)


def test_non_markdown_rejected(tmp_path: Path) -> None:
    config, help_dir = write_help(
        tmp_path, {}, '[layouts.x]\ndocs = ["a.txt"]\n'
    )

    with pytest.raises(ConfigError):
        render_help("x", config, help_dir)


def test_cache_reused_and_refreshed(tmp_path: Path) -> None:
    config, help_dir = write_help(
        tmp_path, {"a.md": "# Một\n"}, '[layouts.x]\ndocs = ["a.md"]\n'
    )
    first = render_help("x", config, help_dir)

    (help_dir / "a.md").write_text("# Hai\n", encoding="utf-8")
    later = time.time() + 5
    os.utime(help_dir / "a.md", (later, later))

    second = render_help("x", config, help_dir)
    assert first.html != second.html
    assert "Hai" in second.html


def test_refresh_help_clears_cache(tmp_path: Path) -> None:
    config, help_dir = write_help(
        tmp_path, {"a.md": "# Một\n"}, '[layouts.x]\ndocs = ["a.md"]\n'
    )
    render_help("x", config, help_dir)
    (help_dir / "a.md").write_text("# Hai\n", encoding="utf-8")
    refresh_help()

    assert "Hai" in render_help("x", config, help_dir).html


def test_load_help_returns_all_layouts(tmp_path: Path) -> None:
    config, help_dir = write_help(
        tmp_path,
        {"a.md": "# A\n", "b.md": "# B\n"},
        '[layouts.one]\ndocs = ["a.md"]\n\n[layouts.two]\ndocs = ["b.md"]\n',
    )

    docs = load_help(config, help_dir)

    assert set(docs) == {"one", "two"}
