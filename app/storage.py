from __future__ import annotations

import hashlib
import re
import shutil
import unicodedata
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

import tomllib
import tomli_w

from .config import REPO_ROOT

STATUSES = {"pending", "generating", "done", "failed"}
_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
_SAFE_PART = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageError(RuntimeError):
    """Thao tác lưu trữ không hợp lệ."""


@dataclass
class InputRecord:
    id: str
    name: str
    desc: str
    created_at: str
    template: str = "flat"
    prompt_version: str = "demanus-deck-v3"
    status: str = "pending"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "InputRecord":
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass
class OutputRecord:
    slug: str
    path: Path
    size_bytes: int
    modified_at: str
    has_preview: bool


def _input_dir(root: Path) -> Path:
    return Path(root) / "input"


def _output_dir(root: Path) -> Path:
    return Path(root) / "output"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def slugify(name: str) -> str:
    value = name.replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:80].strip("-")


def safe_path(base: Path, user_part: str) -> Path:
    part = str(user_part).strip()
    if not part or part in {".", ".."}:
        raise StorageError("Tên không hợp lệ")
    if ".." in part or "/" in part or "\\" in part:
        raise StorageError("Tên không được chứa đường dẫn")
    if Path(part).is_absolute() or not _SAFE_PART.fullmatch(part):
        raise StorageError("Tên chứa ký tự không hợp lệ")

    base_resolved = Path(base).resolve()
    candidate = (base_resolved / part).resolve()
    if candidate.parent != base_resolved:
        raise StorageError("Đường dẫn vượt ra ngoài thư mục cho phép")
    return candidate


def create_input(
    name: str,
    desc: str,
    template: str = "flat",
    prompt_version: str = "demanus-deck-v3",
    root: Path | None = None,
) -> InputRecord:
    base = Path(root) if root is not None else REPO_ROOT
    created_at = _now()
    digest = hashlib.sha256(
        f"{name}\x00{desc}\x00{created_at}".encode("utf-8")
    ).hexdigest()[:12]
    record = InputRecord(
        id=digest,
        name=name,
        desc=desc,
        created_at=created_at,
        template=template,
        prompt_version=prompt_version,
        status="pending",
    )

    directory = _input_dir(base)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.id}.toml"
    with path.open("wb") as handle:
        tomli_w.dump(record.to_dict(), handle)
    return record


def get_input(input_id: str, root: Path | None = None) -> InputRecord:
    if not _ID_PATTERN.fullmatch(str(input_id)):
        raise StorageError("Mã yêu cầu không hợp lệ")
    base = Path(root) if root is not None else REPO_ROOT
    path = _input_dir(base) / f"{input_id}.toml"
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy yêu cầu: {input_id}")
    with path.open("rb") as handle:
        return InputRecord.from_dict(tomllib.load(handle))


def update_status(
    input_id: str,
    status: str,
    root: Path | None = None,
) -> InputRecord:
    if status not in STATUSES:
        raise StorageError(f"Trạng thái không hợp lệ: {status}")
    record = get_input(input_id, root)
    record.status = status
    base = Path(root) if root is not None else REPO_ROOT
    path = _input_dir(base) / f"{record.id}.toml"
    with path.open("wb") as handle:
        tomli_w.dump(record.to_dict(), handle)
    return record


def allocate_output(
    name: str,
    input_id: str,
    root: Path | None = None,
) -> Path:
    base = Path(root) if root is not None else REPO_ROOT
    directory = _output_dir(base)
    directory.mkdir(parents=True, exist_ok=True)

    slug = slugify(name) or input_id
    candidate = directory / f"{slug}.pptx"
    suffix = 2
    while candidate.exists() or (directory / candidate.stem).exists():
        candidate = directory / f"{slug}-{suffix}.pptx"
        suffix += 1
    return candidate


def list_outputs(root: Path | None = None) -> list[OutputRecord]:
    base = Path(root) if root is not None else REPO_ROOT
    directory = _output_dir(base)
    if not directory.is_dir():
        return []

    records: list[OutputRecord] = []
    for path in sorted(directory.glob("*.pptx")):
        slug = path.stem
        preview_dir = directory / slug / "preview"
        has_preview = preview_dir.is_dir() and any(preview_dir.glob("slide-*.png"))
        stat = path.stat()
        records.append(
            OutputRecord(
                slug=slug,
                path=path,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                has_preview=has_preview,
            )
        )
    return records


def delete_output(slug: str, root: Path | None = None) -> None:
    base = Path(root) if root is not None else REPO_ROOT
    directory = _output_dir(base)
    safe_slug = safe_path(directory, f"{slug}.pptx").stem

    pptx_path = directory / f"{safe_slug}.pptx"
    if not pptx_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file: {safe_slug}.pptx")
    pptx_path.unlink()

    sidecar = directory / safe_slug
    if sidecar.is_dir():
        shutil.rmtree(sidecar)
