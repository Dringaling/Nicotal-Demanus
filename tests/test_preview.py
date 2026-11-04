from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.preview import HEIGHT, WIDTH, preview_backend, render_preview
from app.sample import sample_deck
from app.schema import BulletItem, DeckSpec, SlideSpec


def _small_deck(count: int = 3) -> DeckSpec:
    slides = [
        SlideSpec(
            layout="bullets",
            title=f"Triệu chứng {index}",
            bullets=[BulletItem(text="Khó thở khi gắng sức.")],
        )
        for index in range(1, count + 1)
    ]
    return DeckSpec(title="Báo cáo", slides=slides)


def test_backend_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.preview.find_soffice", lambda: None)
    assert preview_backend() == "pillow"

    monkeypatch.setattr("app.preview.find_soffice", lambda: "/usr/bin/soffice")
    assert preview_backend() == "libreoffice"


def test_render_preview_creates_pngs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.preview.find_soffice", lambda: None)
    out_dir = tmp_path / "preview"
    paths = render_preview(tmp_path / "deck.pptx", _small_deck(3), out_dir)

    assert len(paths) == 3
    assert [path.name for path in paths] == [
        "slide-01.png",
        "slide-02.png",
        "slide-03.png",
    ]
    assert all(path.is_file() for path in paths)


def test_preview_dimensions_and_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.preview.find_soffice", lambda: None)
    paths = render_preview(tmp_path / "deck.pptx", _small_deck(1), tmp_path / "p")

    with Image.open(paths[0]) as image:
        assert image.format == "PNG"
        assert image.size == (WIDTH, HEIGHT)
        assert WIDTH == 2000
        assert HEIGHT == 1125


def test_preview_vietnamese_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.preview.find_soffice", lambda: None)
    deck = DeckSpec(
        title="Báo cáo",
        slides=[
            SlideSpec(
                layout="bullets",
                title="Triệu chứng cơ năng",
                bullets=[BulletItem(text="Ngứa nhiều, phân bố rải rác.")],
            )
        ],
    )
    paths = render_preview(tmp_path / "deck.pptx", deck, tmp_path / "p")
    assert paths[0].stat().st_size > 1000


def test_preview_render_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.preview.find_soffice", lambda: None)
    out_dir = tmp_path / "p"
    render_preview(tmp_path / "deck.pptx", _small_deck(2), out_dir)
    paths = render_preview(tmp_path / "deck.pptx", _small_deck(2), out_dir)
    assert len(list(out_dir.glob("slide-*.png"))) == 2
    assert len(paths) == 2


def test_preview_two_digit_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.preview.find_soffice", lambda: None)
    paths = render_preview(tmp_path / "deck.pptx", _small_deck(10), tmp_path / "p")
    assert paths[-1].name == "slide-10.png"


def test_preview_falls_back_when_libreoffice_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.preview.find_soffice", lambda: "/fake/soffice")

    def boom(*args, **kwargs):
        raise RuntimeError("convert failed")

    monkeypatch.setattr("app.preview._render_libreoffice", boom)
    paths = render_preview(tmp_path / "deck.pptx", _small_deck(2), tmp_path / "p")
    assert len(paths) == 2
    assert all(path.is_file() for path in paths)


def test_full_sample_deck_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.preview.find_soffice", lambda: None)
    paths = render_preview(
        tmp_path / "deck.pptx", sample_deck(), tmp_path / "preview"
    )
    assert len(paths) == len(sample_deck().slides)
