# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .config import REPO_ROOT
from .md_lite import render_markdown

logger = logging.getLogger(__name__)

CHANGELOG_DIR = REPO_ROOT / "src" / "changelog"
_VERSION = re.compile(r"^(\d+)\.(\d+)$")

_CACHE: dict[Path, tuple[float, list["ChangelogEntry"]]] = {}


@dataclass(frozen=True)
class ChangelogEntry:
    version: str
    key: tuple[int, int]
    title: str
    html: str


def version_for_module(module: int) -> str:
    """Mỗi module là một minor, 10 module là một major."""
    index = max(0, int(module) - 1)
    return f"{1 + index // 10}.{index % 10}"


def _parse(version: str, text: str) -> ChangelogEntry:
    major, minor = version.split(".", 1)
    title = f"v{version}"
    body = text
    lines = text.splitlines()
    for position, line in enumerate(lines):
        if line.startswith("# "):
            heading = line[2:].strip()
            if heading:
                title = heading
            body = "\n".join(lines[:position] + lines[position + 1 :])
            break
    return ChangelogEntry(
        version=version,
        key=(int(major), int(minor)),
        title=title,
        html=render_markdown(body),
    )


def load_changelog(directory: Path | None = None) -> list[ChangelogEntry]:
    """Đọc src/changelog/<major>.<minor>.md, mới nhất trước."""
    folder = Path(directory) if directory is not None else CHANGELOG_DIR
    if not folder.is_dir():
        return []

    files = [path for path in folder.glob("*.md") if _VERSION.match(path.stem)]
    if not files:
        return []

    stamp = max(path.stat().st_mtime for path in files)
    cached = _CACHE.get(folder)
    if cached is not None and cached[0] == stamp:
        return cached[1]

    entries: list[ChangelogEntry] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            logger.warning("Bỏ qua changelog rỗng: %s", path)
            continue
        entries.append(_parse(path.stem, text))
    entries.sort(key=lambda entry: entry.key, reverse=True)
    _CACHE[folder] = (stamp, entries)
    return entries


def current_version(directory: Path | None = None) -> str:
    entries = load_changelog(directory)
    return entries[0].version if entries else ""


def refresh_changelog() -> None:
    _CACHE.clear()
