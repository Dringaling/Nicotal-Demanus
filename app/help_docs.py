# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .config import REPO_ROOT, ConfigError
from .md_lite import render_markdown

logger = logging.getLogger(__name__)

HELP_DIR = REPO_ROOT / "src" / "help"
CONFIG_PATH = REPO_ROOT / "config" / "help.toml"

_CACHE: tuple[float, dict[str, "HelpDoc"]] | None = None


class HelpError(RuntimeError):
    """Không có help cho layout được yêu cầu."""


@dataclass(frozen=True)
class HelpDoc:
    layout: str
    title: str
    html: str
    docs: tuple[str, ...]


def _resolve_doc(name: object, help_dir: Path) -> Path:
    filename = str(name).strip()
    if (
        not filename.endswith(".md")
        or "/" in filename
        or "\\" in filename
        or filename.startswith(".")
    ):
        raise ConfigError(f"Tên file help không hợp lệ: {filename}")
    path = (help_dir / filename).resolve()
    if path.parent != help_dir.resolve():
        raise ConfigError(f"File help nằm ngoài {help_dir}: {filename}")
    return path


def load_help_config(path: Path | None = None) -> dict[str, dict]:
    """Đọc config/help.toml: layout -> {title, docs}."""
    config_path = Path(path) if path is not None else CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(f"Thiếu file cấu hình help: {config_path}")
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    layouts = data.get("layouts")
    if not isinstance(layouts, dict):
        raise ConfigError("Thiếu bảng [layouts] trong config/help.toml")

    result: dict[str, dict] = {}
    for layout, entry in layouts.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"[layouts.{layout}] phải là bảng TOML")
        docs = entry.get("docs")
        if not isinstance(docs, list) or not docs:
            raise ConfigError(f"[layouts.{layout}].docs phải là mảng không rỗng")
        if not all(isinstance(item, str) for item in docs):
            raise ConfigError(f"[layouts.{layout}].docs phải là mảng chuỗi")
        title = entry.get("title", layout)
        if not isinstance(title, str):
            raise ConfigError(f"[layouts.{layout}].title phải là chuỗi")
        result[str(layout)] = {"title": title, "docs": [str(d) for d in docs]}
    return result


def _fingerprint(config_path: Path, help_dir: Path, docs: list[str]) -> float:
    stamps = [config_path.stat().st_mtime]
    for name in docs:
        try:
            stamps.append((help_dir / name).stat().st_mtime)
        except OSError:
            continue
    return max(stamps)


def _build(
    config_path: Path, help_dir: Path, config: dict[str, dict]
) -> dict[str, HelpDoc]:
    docs: dict[str, HelpDoc] = {}
    for layout, entry in config.items():
        sections: list[str] = []
        used: list[str] = []
        for name in entry["docs"]:
            path = _resolve_doc(name, help_dir)
            if not path.is_file():
                logger.warning("Thiếu file help %s cho layout %s", name, layout)
                continue
            body = render_markdown(path.read_text(encoding="utf-8"))
            sections.append(
                f'<section class="help-section" id="help-{path.stem}">'
                f"{body}</section>"
            )
            used.append(name)
        docs[layout] = HelpDoc(
            layout=layout,
            title=entry["title"],
            html="\n".join(sections),
            docs=tuple(used),
        )
    return docs


def load_help(
    path: Path | None = None, help_dir: Path | None = None
) -> dict[str, HelpDoc]:
    """Nạp toàn bộ help, cache theo mtime của config và các file .md."""
    global _CACHE
    config_path = Path(path) if path is not None else CONFIG_PATH
    docs_dir = Path(help_dir) if help_dir is not None else HELP_DIR
    config = load_help_config(config_path)
    all_docs = [
        name for entry in config.values() for name in entry["docs"]
    ]
    stamp = _fingerprint(config_path, docs_dir, all_docs)
    if _CACHE is not None and _CACHE[0] == stamp:
        return _CACHE[1]
    docs = _build(config_path, docs_dir, config)
    _CACHE = (stamp, docs)
    return docs


def render_help(
    layout: str, path: Path | None = None, help_dir: Path | None = None
) -> HelpDoc:
    docs = load_help(path, help_dir)
    doc = docs.get(str(layout))
    if doc is None:
        raise HelpError(f"Không có help cho layout {layout}")
    return doc


def refresh_help() -> None:
    global _CACHE
    _CACHE = None


def help_layouts(
    path: Path | None = None, help_dir: Path | None = None
) -> list[str]:
    return list(load_help(path, help_dir))
