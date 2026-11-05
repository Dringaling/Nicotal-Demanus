from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import storage
from .boho_render import render_deck_boho
from .config import REPO_ROOT, Settings, lan_url, load_settings
from .copy_slide_render import render_deck_copy_slides
from .llm import LLMClient, LLMError
from .preview import render_preview
from .render import render_deck
from .template_render import render_deck_with_template
from .templates_catalog import (
    apply_template_palette,
    get_template,
    list_templates,
    template_file,
)
from .theme_render import render_deck_theme

logger = logging.getLogger(__name__)

WEB_DIR = REPO_ROOT / "web"
MAX_NAME = 120
PPTX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


def create_app(
    settings: Settings | None = None,
    llm_factory: Callable[[Settings], LLMClient] | None = None,
    root: Path | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    factory = llm_factory or (lambda current: LLMClient(current))
    base = Path(root) if root is not None else REPO_ROOT
    output_dir = base / "output"
    server_url = lan_url(settings)
    template_options = list_templates()

    app = FastAPI(title="Demanus", version="0.1.0")
    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    def render_index(request: Request, error: str | None = None, status_code: int = 200):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "decks": storage.list_outputs(root=base),
                "error": error,
                "server_url": server_url,
                "templates": template_options,
            },
            status_code=status_code,
        )

    def resolve_pptx(slug: str) -> Path:
        try:
            path = storage.safe_path(output_dir, f"{slug}.pptx")
        except storage.StorageError as exc:
            raise HTTPException(status_code=404, detail="Không tìm thấy deck") from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy deck")
        return path

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return render_index(request)

    @app.get("/review", response_class=HTMLResponse)
    async def review(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context={
                "decks": storage.list_outputs(root=base),
                "server_url": server_url,
            },
        )

    @app.get("/health")
    async def health():
        return {"status": "ok", "url": server_url}

    @app.post("/generate")
    async def generate(
        request: Request,
        name: str = Form(""),
        desc: str = Form(""),
        template: str = Form("flat"),
    ):
        name = name.strip()
        desc = desc.strip()

        meta = get_template(template)
        if meta is None:
            return render_index(request, "Template không hợp lệ.", 400)

        if not 1 <= len(name) <= MAX_NAME:
            return render_index(
                request, "Tên báo cáo phải từ 1 đến 120 ký tự.", 400
            )
        if not desc:
            return render_index(
                request, "Mô tả không được để trống.", 400
            )

        record = storage.create_input(
            name, desc, template=template, root=base
        )
        storage.update_status(record.id, "generating", root=base)

        try:
            client = factory(settings)
            prompt_template = "flat" if meta.renderer == "copy" else template
            spec, _usage = await client.generate_spec(
                name, desc, template=prompt_template
            )
            out_path = storage.allocate_output(name, record.id, root=base)

            if meta.renderer == "flat":
                render_deck(spec, out_path)
            elif meta.renderer == "boho":
                render_deck_boho(spec, meta, out_path)
            elif meta.renderer == "copy":
                render_deck_copy_slides(spec, meta, out_path)
            elif meta.renderer == "theme":
                render_deck_theme(spec, meta, out_path)
            else:
                template_path = template_file(meta)
                if template_path is None:
                    render_deck(spec, out_path)
                else:
                    render_deck_with_template(spec, template_path, out_path)

            slug = out_path.stem
            sidecar = out_path.parent / slug
            sidecar.mkdir(parents=True, exist_ok=True)
            (sidecar / "spec.json").write_text(
                spec.model_dump_json(indent=2), encoding="utf-8"
            )
            render_preview(
                out_path,
                apply_template_palette(spec, meta),
                sidecar / "preview",
            )
            storage.update_status(record.id, "done", root=base)
        except Exception as exc:
            storage.update_status(record.id, "failed", root=base)
            logger.exception("Sinh PPTX thất bại cho input %s", record.id)
            message = "Không thể sinh file. Vui lòng thử lại."
            if isinstance(exc, LLMError):
                message = f"Lỗi gọi model: {exc}"
            return render_index(request, message, 500)

        return RedirectResponse(f"/deck/{slug}", status_code=303)

    @app.get("/deck/{slug}", response_class=HTMLResponse)
    async def deck(request: Request, slug: str):
        path = resolve_pptx(slug)
        preview_dir = path.parent / path.stem / "preview"
        previews = (
            sorted(item.name for item in preview_dir.glob("slide-*.png"))
            if preview_dir.is_dir()
            else []
        )
        return templates.TemplateResponse(
            request=request,
            name="deck.html",
            context={
                "slug": slug,
                "previews": previews,
                "count": len(previews),
                "server_url": server_url,
            },
        )

    @app.get("/api/decks")
    async def api_decks():
        return [
            {
                "slug": record.slug,
                "size_bytes": record.size_bytes,
                "modified_at": record.modified_at,
                "has_preview": record.has_preview,
            }
            for record in storage.list_outputs(root=base)
        ]

    @app.get("/download/{slug}")
    async def download(slug: str):
        path = resolve_pptx(slug)
        return FileResponse(
            path,
            media_type=PPTX_MEDIA_TYPE,
            filename=f"{slug}.pptx",
        )

    @app.post("/api/decks/{slug}/delete")
    async def delete(slug: str):
        try:
            storage.delete_output(slug, root=base)
        except (storage.StorageError, FileNotFoundError) as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy deck"
            ) from exc
        return RedirectResponse("/", status_code=303)

    @app.get("/preview/{slug}/{index}")
    async def preview(slug: str, index: int):
        try:
            sidecar = storage.safe_path(output_dir, slug)
        except storage.StorageError as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy preview"
            ) from exc
        if index < 1:
            raise HTTPException(status_code=404, detail="Không tìm thấy preview")

        path = sidecar / "preview" / f"slide-{index:02d}.png"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy preview")
        return FileResponse(path, media_type="image/png")

    return app


app = create_app()
