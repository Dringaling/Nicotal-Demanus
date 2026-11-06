# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.preview import aspose, libreoffice, preview_backend, render_preview

PNG_BYTES = b"\x89PNG\r\n\x1a\n"


def _no_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(libreoffice, "find_soffice", lambda: None)
    monkeypatch.setattr(aspose, "is_available", lambda: False)


def test_backend_prefers_libreoffice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(libreoffice, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(aspose, "is_available", lambda: True)
    assert preview_backend() == "libreoffice"


def test_backend_aspose_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(libreoffice, "find_soffice", lambda: None)
    monkeypatch.setattr(aspose, "is_available", lambda: True)
    assert preview_backend() == "aspose"


def test_backend_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_backend(monkeypatch)
    assert preview_backend() == "none"


def test_backend_never_pillow(monkeypatch: pytest.MonkeyPatch) -> None:
    for soffice, available in (
        ("/usr/bin/soffice", True),
        (None, True),
        (None, False),
    ):
        monkeypatch.setattr(
            libreoffice, "find_soffice", lambda value=soffice: value
        )
        monkeypatch.setattr(aspose, "is_available", lambda value=available: value)
        assert preview_backend() != "pillow"


def test_render_preview_without_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_backend(monkeypatch)
    out_dir = tmp_path / "preview"

    paths = render_preview(tmp_path / "deck.pptx", None, out_dir)

    assert paths == []
    assert list(out_dir.glob("slide-*.png")) == []


def test_render_preview_clears_stale_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_backend(monkeypatch)
    out_dir = tmp_path / "preview"
    out_dir.mkdir(parents=True)
    (out_dir / "slide-01.png").write_bytes(PNG_BYTES)

    render_preview(tmp_path / "deck.pptx", None, out_dir)

    assert list(out_dir.glob("slide-*.png")) == []


def test_render_preview_prefers_libreoffice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = tmp_path / "libre.png"
    monkeypatch.setattr(libreoffice, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(
        libreoffice, "render", lambda *args, **kwargs: [expected]
    )

    def boom(*args, **kwargs):
        raise AssertionError("Aspose không được gọi khi có LibreOffice")

    monkeypatch.setattr(aspose, "render", boom)

    assert render_preview(tmp_path / "deck.pptx", None, tmp_path / "p") == [
        expected
    ]


def test_render_preview_falls_back_to_aspose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = tmp_path / "aspose.png"
    monkeypatch.setattr(libreoffice, "find_soffice", lambda: None)
    monkeypatch.setattr(aspose, "is_available", lambda: True)
    monkeypatch.setattr(
        aspose, "render", lambda *args, **kwargs: [expected]
    )

    assert render_preview(tmp_path / "deck.pptx", None, tmp_path / "p") == [
        expected
    ]


def test_libreoffice_failure_falls_back_to_aspose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = tmp_path / "aspose.png"
    monkeypatch.setattr(libreoffice, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(
        libreoffice,
        "render",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(aspose, "is_available", lambda: True)
    monkeypatch.setattr(
        aspose, "render", lambda *args, **kwargs: [expected]
    )

    assert render_preview(tmp_path / "deck.pptx", None, tmp_path / "p") == [
        expected
    ]


def test_aspose_failure_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(libreoffice, "find_soffice", lambda: None)
    monkeypatch.setattr(aspose, "is_available", lambda: True)
    monkeypatch.setattr(
        aspose,
        "render",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert render_preview(tmp_path / "deck.pptx", None, tmp_path / "p") == []


class _FakePixmap:
    def save(self, path) -> None:
        Path(path).write_bytes(PNG_BYTES)


class _FakePage:
    def get_pixmap(self, matrix=None) -> _FakePixmap:
        return _FakePixmap()


class _FakeDocument:
    def __init__(self, pages: int) -> None:
        self._pages = [_FakePage() for _ in range(pages)]

    def __iter__(self):
        return iter(self._pages)

    def close(self) -> None:
        pass


def test_libreoffice_renders_all_slides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(command, **kwargs):
        outdir = Path(command[command.index("--outdir") + 1])
        stem = Path(command[-1]).stem
        (outdir / f"{stem}.pdf").write_bytes(b"%PDF")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(libreoffice.subprocess, "run", fake_run)
    fake_pymupdf = SimpleNamespace(
        Matrix=lambda x, y: (x, y),
        open=lambda path: _FakeDocument(20),
    )
    monkeypatch.setitem(sys.modules, "pymupdf", fake_pymupdf)

    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"pptx")
    out_dir = tmp_path / "out"

    paths = libreoffice.render("/usr/bin/soffice", pptx, out_dir)

    assert len(paths) == 20
    assert [path.name for path in paths] == [
        f"slide-{index:02d}.png" for index in range(1, 21)
    ]
    assert all(path.is_file() for path in paths)


def _fake_slides(width: int = 960, count: int = 20):
    recorded: list[tuple[float, float]] = []

    class FakeImage:
        def save(self, path, image_format) -> None:
            Path(path).write_bytes(PNG_BYTES)

    class FakeSlide:
        def get_image(self, scale_x, scale_y):
            recorded.append((scale_x, scale_y))
            return FakeImage()

    class FakePresentation:
        def __init__(self, path) -> None:
            self.slide_size = SimpleNamespace(
                size=SimpleNamespace(width=width)
            )
            self.slides = [FakeSlide() for _ in range(count)]

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

    module = SimpleNamespace(
        Presentation=FakePresentation,
        ImageFormat=SimpleNamespace(PNG="png"),
    )
    return module, recorded


def test_aspose_limits_slides_and_scales(tmp_path: Path) -> None:
    slides, recorded = _fake_slides(width=960, count=20)

    paths = aspose.render(
        tmp_path / "deck.pptx", tmp_path / "out", slides_module=slides
    )

    assert aspose.TARGET_WIDTH == 640
    assert aspose.MAX_ASPOSE_SLIDES == 10
    assert len(paths) == 10
    assert all(scale == pytest.approx(640 / 960) for pair in recorded for scale in pair)


def test_aspose_rejects_invalid_width(tmp_path: Path) -> None:
    slides, _ = _fake_slides(width=0, count=1)

    with pytest.raises(RuntimeError):
        aspose.render(
            tmp_path / "deck.pptx", tmp_path / "out", slides_module=slides
        )


@pytest.mark.skipif(not aspose.is_available(), reason="aspose.slides chưa cài")
def test_real_aspose_is_available() -> None:
    assert aspose.is_available() is True


def test_license_and_notice_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    notice = (root / "NOTICE").read_text(encoding="utf-8")

    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3" in license_text
    assert "SPECIAL EXCEPTION FOR DOCUMENT PREVIEW MODULE" in notice
    assert "aspose.slides for Python" in notice


def test_optional_extra_declared() -> None:
    import tomllib

    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    extras = data["project"].get("optional-dependencies", {})
    assert "preview-aspose" in extras
    dependencies = [item.lower() for item in data["project"]["dependencies"]]
    assert not any(item.startswith("pillow") for item in dependencies)


def test_aspose_honors_max_slides(tmp_path: Path) -> None:
    slides, _ = _fake_slides(width=960, count=20)

    paths = aspose.render(
        tmp_path / "deck.pptx",
        tmp_path / "out",
        slides_module=slides,
        max_slides=5,
    )

    assert len(paths) == 5


def test_libreoffice_honors_max_slides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(command, **kwargs):
        outdir = Path(command[command.index("--outdir") + 1])
        stem = Path(command[-1]).stem
        (outdir / f"{stem}.pdf").write_bytes(b"%PDF")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(libreoffice.subprocess, "run", fake_run)
    fake_pymupdf = SimpleNamespace(
        Matrix=lambda x, y: (x, y),
        open=lambda path: _FakeDocument(20),
    )
    monkeypatch.setitem(sys.modules, "pymupdf", fake_pymupdf)

    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"pptx")
    paths = libreoffice.render(
        "/usr/bin/soffice", pptx, tmp_path / "out", max_slides=5
    )

    assert len(paths) == 5
