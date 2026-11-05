from __future__ import annotations

from pathlib import Path

import pytest

from app import storage
from app.storage import DuplicateTitleError, StorageError, slugify


def test_create_and_get_input(tmp_path: Path) -> None:
    record = storage.create_input(
        "Báo cáo viêm da",
        "Mô tả ngắn",
        "Nội dung chi tiết",
        tags=["dental"],
        root=tmp_path,
    )
    assert len(record.id) == 8
    assert (tmp_path / "input" / f"{record.id}.toml").is_file()
    assert record.description_hash
    assert record.details_hash

    loaded = storage.get_input(record.id, root=tmp_path)
    assert loaded.title == "Báo cáo viêm da"
    assert loaded.tags == ["dental"]
    assert storage.read_text(loaded.description_hash, root=tmp_path) == "Mô tả ngắn"
    assert storage.read_text(loaded.details_hash, root=tmp_path) == "Nội dung chi tiết"


def test_duplicate_title_is_rejected(tmp_path: Path) -> None:
    storage.create_input("Báo cáo", "Mô tả", "Chi tiết", root=tmp_path)
    with pytest.raises(DuplicateTitleError):
        storage.create_input("Báo cáo", "Mô tả khác", "Chi tiết khác", root=tmp_path)


def test_different_titles_have_different_ids(tmp_path: Path) -> None:
    first = storage.create_input("Báo cáo A", "Mô tả", "Chi tiết", root=tmp_path)
    second = storage.create_input("Báo cáo B", "Mô tả", "Chi tiết", root=tmp_path)
    assert first.id != second.id


def test_content_dedup(tmp_path: Path) -> None:
    first = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    second = storage.create_input("B", "Mô tả", "Chi tiết", root=tmp_path)
    assert first.description_hash == second.description_hash
    assert first.details_hash == second.details_hash
    assert len(list((tmp_path / "input" / "text").glob("*.txt"))) == 2


def test_tags_catalog_counts_and_delete(tmp_path: Path) -> None:
    record = storage.create_input(
        "A",
        "Mô tả",
        "Chi tiết",
        tags=["dental", "research"],
        root=tmp_path,
    )
    assert storage.list_tags(root=tmp_path) == ["dental", "research"]
    assert storage.tag_counts(root=tmp_path) == {"dental": 1, "research": 1}

    storage.delete_tag("dental", root=tmp_path)
    assert storage.list_tags(root=tmp_path) == ["research"]
    assert storage.get_input(record.id, root=tmp_path).tags == ["research"]


def test_delete_input_keeps_tag_and_removes_output(tmp_path: Path) -> None:
    record = storage.create_input(
        "A", "Mô tả", "Chi tiết", tags=["dental"], root=tmp_path
    )
    output = storage.allocate_output("A", record.id, root=tmp_path)
    output.write_bytes(b"pptx")
    storage.update_output(record.id, output.stem, root=tmp_path)

    storage.delete_input(record.id, root=tmp_path)
    assert storage.list_inputs(root=tmp_path) == []
    assert "dental" in storage.list_tags(root=tmp_path)
    assert not output.exists()


def test_update_status(tmp_path: Path) -> None:
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    updated = storage.update_status(record.id, "done", root=tmp_path)
    assert updated.status == "done"
    assert storage.get_input(record.id, root=tmp_path).status == "done"


def test_update_status_rejects_unknown(tmp_path: Path) -> None:
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    with pytest.raises(StorageError, match="Trạng thái không hợp lệ"):
        storage.update_status(record.id, "unknown", root=tmp_path)


def test_get_input_rejects_bad_id(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="Mã yêu cầu không hợp lệ"):
        storage.get_input("../../etc/passwd", root=tmp_path)


def test_title_validation(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        storage.create_input("bad/title", "Mô tả", "Chi tiết", root=tmp_path)
    with pytest.raises(StorageError):
        storage.create_input("", "Mô tả", "Chi tiết", root=tmp_path)


def test_tag_validation(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        storage.create_input(
            "A", "Mô tả", "Chi tiết", tags=["bad/tag"], root=tmp_path
        )


def test_migrate_legacy_input(tmp_path: Path) -> None:
    legacy = tmp_path / "input" / "legacy.toml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        'id = "legacy"\n'
        'name = "Báo cáo cũ"\n'
        'desc = "Nội dung cũ"\n'
        'created_at = "2026-01-01T00:00:00Z"\n'
        'template = "flat"\n'
        'prompt_version = "demanus-deck-v1"\n'
        'status = "done"\n',
        encoding="utf-8",
    )
    output = tmp_path / "output" / "bao-cao-cu.pptx"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"pptx")

    migrated = storage.migrate_legacy_inputs(root=tmp_path)
    assert migrated == 1
    records = storage.list_inputs(root=tmp_path)
    assert len(records) == 1
    assert records[0].title == "Báo cáo cũ"
    assert storage.read_text(records[0].details_hash, root=tmp_path) == "Nội dung cũ"
    assert records[0].output_slug == "bao-cao-cu"
    assert not legacy.exists()
    assert (tmp_path / "input" / ".migrated" / "legacy.toml").is_file()


def test_migrate_dedupes_same_title(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir(parents=True)
    for name, created in (
        ("old.toml", "2026-01-01T00:00:00Z"),
        ("new.toml", "2026-01-02T00:00:00Z"),
    ):
        (input_dir / name).write_text(
            'id = "x"\n'
            'name = "Báo cáo trùng"\n'
            'desc = "Nội dung"\n'
            f'created_at = "{created}"\n'
            'template = "flat"\n'
            'prompt_version = "demanus-deck-v1"\n'
            'status = "done"\n',
            encoding="utf-8",
        )

    storage.migrate_legacy_inputs(root=tmp_path)
    records = storage.list_inputs(root=tmp_path)
    assert len(records) == 1
    assert records[0].created_at == "2026-01-02T00:00:00Z"
    assert (input_dir / ".migrated" / "old.toml").is_file()
    assert (input_dir / ".migrated" / "new.toml").is_file()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Báo cáo viêm da", "bao-cao-viem-da"),
        ("Điều trị đau", "dieu-tri-dau"),
        ("  Nhiều   khoảng trắng  ", "nhieu-khoang-trang"),
        ("!!!", ""),
    ],
)
def test_slugify(name: str, expected: str) -> None:
    assert slugify(name) == expected


def test_slugify_truncates() -> None:
    assert len(slugify("a" * 300)) <= 80


def test_safe_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        storage.safe_path(tmp_path, "../../etc/passwd")


def test_safe_path_rejects_absolute(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        storage.safe_path(tmp_path, "/etc/passwd")


def test_safe_path_rejects_windows_chars(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        storage.safe_path(tmp_path, "a:b*c?.pptx")


def test_allocate_output_avoids_overwrite(tmp_path: Path) -> None:
    first = storage.allocate_output("Báo cáo", "abcdef12", root=tmp_path)
    first.write_bytes(b"x")
    second = storage.allocate_output("Báo cáo", "abcdef12", root=tmp_path)

    assert first.name == "bao-cao.pptx"
    assert second.name == "bao-cao-2.pptx"
    assert first != second


def test_allocate_output_falls_back_to_id(tmp_path: Path) -> None:
    path = storage.allocate_output("!!!", "abcdef12", root=tmp_path)
    assert path.name == "abcdef12.pptx"


def test_list_and_delete_output(tmp_path: Path) -> None:
    path = storage.allocate_output("Báo cáo", "abcdef12", root=tmp_path)
    path.write_bytes(b"pptx")
    preview = tmp_path / "output" / path.stem / "preview"
    preview.mkdir(parents=True)
    (preview / "slide-01.png").write_bytes(b"png")

    records = storage.list_outputs(root=tmp_path)
    assert len(records) == 1
    assert records[0].slug == "bao-cao"
    assert records[0].has_preview is True

    storage.delete_output("bao-cao", root=tmp_path)
    assert not path.exists()
    assert not (tmp_path / "output" / "bao-cao").exists()


def test_delete_missing_output(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        storage.delete_output("khong-ton-tai", root=tmp_path)
