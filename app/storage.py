from __future__ import annotations

import re
import shutil
import unicodedata
import zlib
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

import tomllib
import tomli_w

from .config import REPO_ROOT

STATUSES = {"pending", "generating", "done", "failed"}
_ID_PATTERN = re.compile(r"^[0-9a-f]{8}(-\d+)?$")
_SAFE_PART = re.compile(r"^[A-Za-z0-9._-]+$")
_TITLE_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TAG_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class StorageError(RuntimeError):
    """Thao tác lưu trữ không hợp lệ."""


class DuplicateTitleError(StorageError):
    def __init__(self, message: str, existing_id: str) -> None:
        super().__init__(message)
        self.existing_id = existing_id


@dataclass
class InputRecord:
    id: str
    title: str
    description_hash: str
    details_hash: str
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    template: str = "flat"
    prompt_version: str = "demanus-deck-v4"
    status: str = "pending"
    output_slug: str = ""

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


def _text_dir(root: Path) -> Path:
    return Path(root) / "input" / "text"


def _output_dir(root: Path) -> Path:
    return Path(root) / "output"


def _tags_path(root: Path) -> Path:
    return Path(root) / "input" / "tags.toml"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _crc32(text: str) -> str:
    return f"{zlib.crc32(text.encode('utf-8')) & 0xFFFFFFFF:08x}"


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", str(title).strip())


def _title_key(title: str) -> str:
    return normalize_title(title).casefold()


def validate_title(title: str) -> str:
    cleaned = normalize_title(title)
    if not 1 <= len(cleaned) <= 200:
        raise StorageError("Tiêu đề phải từ 1 đến 200 ký tự")
    if _TITLE_FORBIDDEN.search(cleaned):
        raise StorageError("Tiêu đề chứa ký tự không hợp lệ")
    return cleaned


def normalize_tags(tags: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        tag = re.sub(r"\s+", " ", str(raw).strip())
        if not tag:
            continue
        if len(tag) > 40:
            raise StorageError("Tag tối đa 40 ký tự")
        if _TAG_FORBIDDEN.search(tag):
            raise StorageError("Tag chứa ký tự không hợp lệ")
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
    return result


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


def store_text(text: str, root: Path | None = None) -> str:
    if not text:
        return ""
    base = Path(root) if root is not None else REPO_ROOT
    digest = _crc32(text)
    path = _text_dir(base) / f"{digest}.txt"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return digest


def read_text(digest: str, root: Path | None = None) -> str:
    if not digest:
        return ""
    base = Path(root) if root is not None else REPO_ROOT
    path = _text_dir(base) / f"{digest}.txt"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _save_record(record: InputRecord, root: Path) -> None:
    path = _input_dir(root) / f"{record.id}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        tomli_w.dump(record.to_dict(), handle)


def _record_paths(root: Path):
    directory = _input_dir(root)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.toml")
        if path.name != "tags.toml"
    )


def list_tags(root: Path | None = None) -> list[str]:
    base = Path(root) if root is not None else REPO_ROOT
    path = _tags_path(base)
    if not path.is_file():
        return []
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    raw = data.get("tags", [])
    if not isinstance(raw, list):
        return []
    return normalize_tags([str(tag) for tag in raw])


def _write_tags(tags: list[str], root: Path) -> None:
    path = _tags_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        tomli_w.dump({"tags": tags}, handle)


def _merge_tags(tags: list[str], root: Path) -> None:
    merged: dict[str, str] = {}
    for tag in list_tags(root) + tags:
        merged.setdefault(tag.casefold(), tag)
    _write_tags(sorted(merged.values(), key=str.casefold), root)


def list_inputs(tag: str | None = None, root: Path | None = None) -> list[InputRecord]:
    base = Path(root) if root is not None else REPO_ROOT
    records: list[InputRecord] = []
    for path in _record_paths(base):
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        if "title" not in data or "details_hash" not in data:
            continue
        records.append(InputRecord.from_dict(data))
    if tag:
        key = tag.casefold()
        records = [
            record
            for record in records
            if any(item.casefold() == key for item in record.tags)
        ]
    records.sort(key=lambda record: record.created_at, reverse=True)
    return records


def _find_record_by_title(title: str, root: Path) -> InputRecord | None:
    key = _title_key(title)
    for record in list_inputs(root=root):
        if _title_key(record.title) == key:
            return record
    return None


def create_input(
    title: str,
    description: str = "",
    details: str = "",
    tags: list[str] | None = None,
    template: str = "flat",
    prompt_version: str = "demanus-deck-v4",
    root: Path | None = None,
) -> InputRecord:
    base = Path(root) if root is not None else REPO_ROOT
    cleaned_title = validate_title(title)
    cleaned_tags = normalize_tags(tags)

    existing = _find_record_by_title(cleaned_title, base)
    if existing is not None:
        raise DuplicateTitleError(
            f"Tiêu đề đã tồn tại: {cleaned_title}", existing.id
        )

    input_dir = _input_dir(base)
    input_dir.mkdir(parents=True, exist_ok=True)

    base_id = _crc32(_title_key(cleaned_title))
    record_id = base_id
    suffix = 2
    while (input_dir / f"{record_id}.toml").exists():
        record_id = f"{base_id}-{suffix}"
        suffix += 1

    record = InputRecord(
        id=record_id,
        title=cleaned_title,
        description_hash=store_text(description, base),
        details_hash=store_text(details, base),
        tags=cleaned_tags,
        created_at=_now(),
        template=template,
        prompt_version=prompt_version,
        status="pending",
    )
    _save_record(record, base)
    _merge_tags(cleaned_tags, base)
    return record


def get_input(input_id: str, root: Path | None = None) -> InputRecord:
    if not _ID_PATTERN.fullmatch(str(input_id)):
        raise StorageError("Mã yêu cầu không hợp lệ")
    base = Path(root) if root is not None else REPO_ROOT
    path = _input_dir(base) / f"{input_id}.toml"
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy yêu cầu: {input_id}")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if "title" not in data or "details_hash" not in data:
        raise StorageError("Record cũ chưa được migrate")
    return InputRecord.from_dict(data)


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
    _save_record(record, base)
    return record


def update_output(
    input_id: str,
    slug: str,
    root: Path | None = None,
) -> InputRecord:
    record = get_input(input_id, root)
    record.output_slug = slug
    base = Path(root) if root is not None else REPO_ROOT
    _save_record(record, base)
    return record


def tag_counts(root: Path | None = None) -> dict[str, int]:
    base = Path(root) if root is not None else REPO_ROOT
    counts = {tag: 0 for tag in list_tags(base)}
    for record in list_inputs(root=base):
        for tag in record.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def delete_tag(tag: str, root: Path | None = None) -> None:
    base = Path(root) if root is not None else REPO_ROOT
    key = tag.casefold()
    _write_tags(
        [item for item in list_tags(base) if item.casefold() != key],
        base,
    )
    for record in list_inputs(root=base):
        updated = [item for item in record.tags if item.casefold() != key]
        if updated != record.tags:
            record.tags = updated
            _save_record(record, base)


def _infer_output_slug(title: str, root: Path) -> str:
    slug = slugify(title)
    if not slug:
        return ""
    candidates = sorted(
        _output_dir(root).glob(f"{slug}*.pptx"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0].stem if candidates else ""


def delete_input(
    input_id: str,
    root: Path | None = None,
    delete_output_file: bool = True,
) -> None:
    record = get_input(input_id, root)
    base = Path(root) if root is not None else REPO_ROOT
    path = _input_dir(base) / f"{record.id}.toml"
    if path.is_file():
        path.unlink()
    if delete_output_file and record.output_slug:
        try:
            delete_output(record.output_slug, root=base)
        except FileNotFoundError:
            pass


def migrate_legacy_inputs(root: Path | None = None) -> int:
    base = Path(root) if root is not None else REPO_ROOT
    input_dir = _input_dir(base)
    if not input_dir.is_dir():
        return 0

    legacy: list[tuple[Path, dict]] = []
    for path in input_dir.glob("*.toml"):
        if path.name == "tags.toml":
            continue
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        if "title" in data and "details_hash" in data:
            continue
        if "name" in data and "desc" in data:
            legacy.append((path, data))

    if not legacy:
        return 0

    groups: dict[str, list[tuple[Path, dict]]] = {}
    for path, data in legacy:
        title = str(data.get("name", "")).strip()
        if not title:
            continue
        groups.setdefault(_title_key(title), []).append((path, data))

    migrated_dir = input_dir / ".migrated"
    migrated = 0

    for items in groups.values():
        items.sort(
            key=lambda item: str(item[1].get("created_at", "")),
            reverse=True,
        )
        _, data = items[0]
        title = str(data.get("name", "")).strip()
        if _find_record_by_title(title, base) is None:
            record = create_input(
                title,
                description="",
                details=str(data.get("desc", "")),
                tags=[],
                template=str(data.get("template", "flat")),
                prompt_version=str(
                    data.get("prompt_version", "demanus-deck-v4")
                ),
                root=base,
            )
            record.created_at = str(data.get("created_at", record.created_at))
            record.status = str(data.get("status", "done"))
            record.output_slug = _infer_output_slug(title, base)
            _save_record(record, base)
            migrated += 1

        migrated_dir.mkdir(parents=True, exist_ok=True)
        for old_path, _ in items:
            target = migrated_dir / old_path.name
            if target.exists():
                target.unlink()
            shutil.move(str(old_path), str(target))

    return migrated


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
