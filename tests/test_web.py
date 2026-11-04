from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.llm import LLMError, UsageInfo
from app.sample import sample_deck
from app.web import create_app

CONFIG = Path(__file__).resolve().parents[1] / "config" / "providers.toml"


class FakeClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def generate_spec(self, name: str, desc: str, template: str = "flat"):
        return sample_deck(), UsageInfo()


class FailingClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def generate_spec(self, name: str, desc: str, template: str = "flat"):
        raise LLMError("model không phản hồi")


def make_client(tmp_path: Path, *, failing: bool = False) -> TestClient:
    settings = load_settings(CONFIG)
    factory = (lambda _: FailingClient(settings)) if failing else (
        lambda current: FakeClient(current)
    )
    app = create_app(settings, llm_factory=factory, root=tmp_path)
    return TestClient(app)


def generate(client: TestClient, name: str = "Báo cáo", desc: str = "Mô tả chi tiết về bệnh nhân"):
    return client.post(
        "/generate",
        data={"name": name, "desc": desc},
        follow_redirects=False,
    )


def test_index_and_health(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="name"' in response.text
    assert 'name="desc"' in response.text

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_generate_creates_deck(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client)

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/deck/")
    slug = location.rsplit("/", 1)[-1]

    assert (tmp_path / "output" / f"{slug}.pptx").is_file()
    assert (tmp_path / "output" / slug / "spec.json").is_file()
    assert (tmp_path / "output" / slug / "preview" / "slide-01.png").is_file()

    deck = client.get(location)
    assert deck.status_code == 200
    assert "carousel" in deck.text
    assert "Tải PPTX" in deck.text


def test_generate_rejects_short_name(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, name="")
    assert response.status_code == 400
    assert "Tên báo cáo" in response.text


def test_generate_rejects_short_desc(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, desc="ngắn")
    assert response.status_code == 400
    assert "Mô tả" in response.text


def test_generate_failure_marks_failed(tmp_path: Path) -> None:
    client = make_client(tmp_path, failing=True)
    response = generate(client)

    assert response.status_code == 500
    assert "Lỗi gọi model" in response.text
    assert "test-key" not in response.text

    inputs = list((tmp_path / "input").glob("*.toml"))
    assert len(inputs) == 1
    assert "failed" in inputs[0].read_text(encoding="utf-8")


def test_api_decks_and_download(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    api = client.get("/api/decks")
    assert api.status_code == 200
    payload = api.json()
    assert len(payload) == 1
    assert payload[0]["slug"] == slug
    assert payload[0]["has_preview"] is True

    download = client.get(f"/download/{slug}")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert download.content[:2] == b"PK"


def test_preview_endpoint(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    preview = client.get(f"/preview/{slug}/1")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"

    assert client.get(f"/preview/{slug}/999").status_code == 404
    assert client.get("/preview/khong-ton-tai/1").status_code == 404


def test_delete_deck(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    response = client.post(f"/api/decks/{slug}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert not (tmp_path / "output" / f"{slug}.pptx").exists()
    assert not (tmp_path / "output" / slug).exists()


def test_delete_missing_deck(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/decks/khong-ton-tai/delete", follow_redirects=False)
    assert response.status_code == 404


def test_deck_not_found(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/deck/khong-ton-tai").status_code == 404
    assert client.get("/download/khong-ton-tai").status_code == 404


def test_static_asset(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
