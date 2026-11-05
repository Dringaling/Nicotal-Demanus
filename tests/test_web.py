from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from app import storage
from app.config import lan_url, load_settings
from app.llm import LLMError, UsageInfo
from app.sample import sample_deck
from app.web import create_app

CONFIG = Path(__file__).resolve().parents[1] / "config" / "providers.toml"


class FakeClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def generate_spec(
        self,
        name: str,
        desc: str,
        template: str = "flat",
        description: str = "",
    ):
        return sample_deck(), UsageInfo()


class FailingClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def generate_spec(
        self,
        name: str,
        desc: str,
        template: str = "flat",
        description: str = "",
    ):
        raise LLMError("model không phản hồi")


def make_client(tmp_path: Path, *, failing: bool = False) -> TestClient:
    settings = load_settings(CONFIG)
    factory = (lambda _: FailingClient(settings)) if failing else (
        lambda current: FakeClient(current)
    )
    app = create_app(settings, llm_factory=factory, root=tmp_path)
    return TestClient(app)


def generate(
    client: TestClient,
    *,
    title: str = "Báo cáo",
    description: str = "Mô tả ngắn về mục tiêu",
    details: str = "Nội dung chi tiết từng slide",
    tags: str = "",
    template: str = "flat",
):
    return client.post(
        "/generate",
        data={
            "title": title,
            "description": description,
            "details": details,
            "tags": tags,
            "template": template,
        },
        follow_redirects=False,
    )


def test_index_and_health(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    expected_url = lan_url(load_settings(CONFIG))
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="title"' in response.text
    assert 'name="description"' in response.text
    assert 'name="details"' in response.text
    assert 'name="tags"' in response.text
    assert 'name="template"' in response.text
    assert expected_url in response.text

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "url": expected_url}


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

    records = storage.list_inputs(root=tmp_path)
    assert len(records) == 1
    assert records[0].status == "done"
    assert records[0].output_slug == slug

    deck = client.get(location)
    assert deck.status_code == 200
    assert "carousel" in deck.text
    assert "Tải PPTX" in deck.text


def test_generate_rejects_empty_title(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, title="")
    assert response.status_code == 400
    assert "Tiêu đề" in response.text


def test_generate_rejects_empty_description(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, description="")
    assert response.status_code == 400
    assert "Mô tả" in response.text


def test_generate_rejects_empty_details(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, details="")
    assert response.status_code == 400
    assert "Chi tiết" in response.text


def test_generate_accepts_long_details(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, details="Nội dung chi tiết. " * 1500)
    assert response.status_code == 303


def test_generate_duplicate_title(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert generate(client).status_code == 303
    response = generate(client, details="Nội dung khác")
    assert response.status_code == 400
    assert "Tiêu đề đã tồn tại" in response.text


def test_generate_failure_marks_failed(tmp_path: Path) -> None:
    client = make_client(tmp_path, failing=True)
    response = generate(client)

    assert response.status_code == 500
    assert "Lỗi gọi model" in response.text
    assert "test-key" not in response.text

    records = storage.list_inputs(root=tmp_path)
    assert len(records) == 1
    assert records[0].status == "failed"


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


def test_api_inputs_and_tags(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input(
        "Báo cáo",
        "Mô tả",
        "Chi tiết",
        tags=["dental", "research"],
        root=tmp_path,
    )

    inputs = client.get("/api/inputs")
    assert inputs.status_code == 200
    assert inputs.json()[0]["title"] == "Báo cáo"

    tags = client.get("/api/tags")
    assert tags.status_code == 200
    assert "dental" in tags.json()["tags"]
    assert tags.json()["counts"]["dental"] == 1


def test_preview_endpoint(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    preview = client.get(f"/preview/{slug}/1")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"

    assert client.get(f"/preview/{slug}/999").status_code == 404
    assert client.get("/preview/khong-ton-tai/1").status_code == 404


def test_delete_output(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    response = client.post(f"/api/decks/{slug}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert not (tmp_path / "output" / f"{slug}.pptx").exists()
    assert not (tmp_path / "output" / slug).exists()


def test_delete_missing_output(tmp_path: Path) -> None:
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


def test_review_page_lists_decks(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    response = client.get("/review")
    assert response.status_code == 200
    assert slug in response.text
    assert f"/preview/{slug}/1" in response.text
    assert "Xem slide" in response.text


def test_review_page_empty(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/review")
    assert response.status_code == 200
    assert "Chưa có deck nào" in response.text


def test_index_shows_input_thumbnail(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    response = client.get("/")
    assert response.status_code == 200
    assert f"/preview/{slug}/1" in response.text
    assert "thumb-sm" in response.text


def test_tag_filter_and_delete(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input(
        "Báo cáo nha khoa",
        "Mô tả",
        "Chi tiết",
        tags=["dental"],
        root=tmp_path,
    )

    filtered = client.get("/?tag=dental")
    assert filtered.status_code == 200
    assert "Báo cáo nha khoa" in filtered.text

    deleted = client.post("/tags/dental/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert storage.list_tags(root=tmp_path) == []
    records = storage.list_inputs(root=tmp_path)
    assert records[0].tags == []


def test_delete_input_keeps_tag(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "Báo cáo",
        "Mô tả",
        "Chi tiết",
        tags=["dental"],
        root=tmp_path,
    )

    response = client.post(
        f"/inputs/{record.id}/delete", follow_redirects=False
    )
    assert response.status_code == 303
    assert storage.list_inputs(root=tmp_path) == []
    assert "dental" in storage.list_tags(root=tmp_path)


def test_index_has_template_select(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="template"' in response.text
    assert "flat" in response.text
    assert "dividing-fractions" in response.text
    assert "boho-minimalist" in response.text
    assert "boho-copy" in response.text
    assert "neo_tech_minimal" in response.text


def test_generate_with_dividing_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="dividing-fractions")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]
    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert prs.slide_width == Inches(10)
    assert prs.slide_height == Inches(5.625)


def test_generate_with_boho_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="boho-minimalist")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]
    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert prs.slide_width == Inches(13.333)
    first = prs.slides[0]
    pictures = [
        shape
        for shape in first.shapes
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert pictures


def test_generate_with_copy_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="boho-copy")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]
    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert prs.slide_width == Inches(20)
    assert prs.slide_height == Inches(11.25)
    first = prs.slides[0]
    pictures = [
        shape
        for shape in first.shapes
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert pictures


def test_generate_with_theme_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="neo_tech_minimal")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]
    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert prs.slide_width == Inches(13.333)
    assert prs.slide_height == Inches(7.5)
    assert len(prs.slides[0].shapes) >= 2


def test_generate_with_unknown_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="khong-ton-tai")
    assert response.status_code == 400
    assert "Template không hợp lệ" in response.text
