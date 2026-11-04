from __future__ import annotations

from pathlib import Path

import pytest

from app import storage
from app.storage import StorageError, slugify


def test_create_and_get_input(tmp_path: Path) -> None:
    record = storage.create_input("Báo cáo viêm da", "Mô tả chi tiết", root=tmp_path)
    assert len(record.id) == 12
    assert (tmp_path / "input" / f"{record.id}.toml").is_file()

    loaded = storage.get_input(record.id, root=tmp_path)
    assert loaded.name == "Báo cáo viêm da"
    assert loaded.desc == "Mô tả chi tiết"
    assert loaded.status == "pending"


def test_ids_differ_for_different_desc(tmp_path: Path) -> None:
    first = storage.create_input("Báo cáo", "Mô tả A", root=tmp_path)
    second = storage.create_input("Báo cáo", "Mô tả B", root=tmp_path)
    assert first.id != second.id


def test_update_status(tmp_path: Path) -> None:
    record = storage.create_input("Báo cáo", "Mô tả", root=tmp_path)
    updated = storage.update_status(record.id, "done", root=tmp_path)
    assert updated.status == "done"
    assert storage.get_input(record.id, root=tmp_path).status == "done"


def test_update_status_rejects_unknown(tmp_path: Path) -> None:
    record = storage.create_input("Báo cáo", "Mô tả", root=tmp_path)
    with pytest.raises(StorageError, match="Trạng thái không hợp lệ"):
        storage.update_status(record.id, "unknown", root=tmp_path)


def test_get_input_rejects_bad_id(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="Mã yêu cầu không hợp lệ"):
        storage.get_input("../../etc/passwd", root=tmp_path)


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
    first = storage.allocate_output("Báo cáo", "abcdef123456", root=tmp_path)
    first.write_bytes(b"x")
    second = storage.allocate_output("Báo cáo", "abcdef123456", root=tmp_path)

    assert first.name == "bao-cao.pptx"
    assert second.name == "bao-cao-2.pptx"
    assert first != second


def test_allocate_output_falls_back_to_id(tmp_path: Path) -> None:
    path = storage.allocate_output("!!!", "abcdef123456", root=tmp_path)
    assert path.name == "abcdef123456.pptx"


def test_list_and_delete_output(tmp_path: Path) -> None:
    path = storage.allocate_output("Báo cáo", "abcdef123456", root=tmp_path)
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
