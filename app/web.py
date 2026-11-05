from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Form, HTTPException, Query, Request
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
MAX_TITLE = 200
PPTX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


def write_deck(spec, meta, out_path: Path) -> None:
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

    try:
        storage.migrate_legacy_inputs(root=base)
    except Exception:
        logger.exception("Migrate input cũ thất bại")

    template_options = list_templates()

    app = FastAPI(title="Demanus", version="0.1.0")
    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    def render_index(
        request: Request,
        error: str | None = None,
        status_code: int = 200,
        form: dict | None = None,
        active_tag: str | None = None,
        query: str | None = None,
    ):
        records = storage.list_inputs(
            tag=active_tag, search=query, root=base
        )
        inputs = []
        for record in records:
            outputs = storage.outputs_for(record, root=base)
            inputs.append(
                {
                    "record": record,
                    "description": storage.read_text(
                        record.description_hash, base
                    )[:160],
                    "outputs": list(reversed(outputs)),
                    "newest": outputs[-1] if outputs else None,
                    "has_output": bool(outputs),
                }
            )
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "inputs": inputs,
                "tags": storage.list_tags(root=base),
                "counts": storage.tag_counts(root=base),
                "active_tag": active_tag,
                "query": query or "",
                "templates": template_options,
                "server_url": server_url,
                "error": error,
                "form": form or {},
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

    async def render_record(record: storage.InputRecord, template: str) -> str:
        meta = get_template(template)
        if meta is None:
            raise storage.StorageError("Template không hợp lệ.")

        storage.update_status(record.id, "generating", root=base)
        try:
            client = factory(settings)
            prompt_template = "flat" if meta.renderer == "copy" else template
            spec, _usage = await client.generate_spec(
                record.title,
                storage.read_text(record.details_hash, base),
                template=prompt_template,
                description=storage.read_text(record.description_hash, base),
            )
            out_path = storage.allocate_output(record.title, record.id, root=base)
            write_deck(spec, meta, out_path)

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
            storage.append_output(record.id, slug, root=base)
            storage.update_status(record.id, "done", root=base)
        except Exception:
            storage.update_status(record.id, "failed", root=base)
            raise
        return slug

    @app.get("/", response_class=HTMLResponse)
    async def index(
        request: Request,
        tag: str | None = Query(None),
        q: str | None = Query(None),
    ):
        return render_index(request, active_tag=tag, query=q)

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
        title: str = Form(""),
        description: str = Form(""),
        details: str = Form(""),
        tags: str = Form(""),
        template: str = Form("flat"),
    ):
        title = title.strip()
        description = description.strip()
        details = details.strip()
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        form = {
            "title": title,
            "description": description,
            "details": details,
            "tags": ",".join(tag_list),
            "template": template,
        }

        meta = get_template(template)
        if meta is None:
            return render_index(request, "Template không hợp lệ.", 400, form)
        if not title:
            return render_index(request, "Tiêu đề không được để trống.", 400, form)
        if not description:
            return render_index(request, "Mô tả không được để trống.", 400, form)
        if not details:
            return render_index(request, "Chi tiết không được để trống.", 400, form)

        try:
            record = storage.create_input(
                title,
                description,
                details,
                tags=tag_list,
                template=template,
                root=base,
            )
        except storage.DuplicateTitleError as exc:
            return render_index(
                request,
                f"Tiêu đề đã tồn tại (id {exc.existing_id}).",
                400,
                form,
            )
        except storage.StorageError as exc:
            return render_index(request, str(exc), 400, form)

        try:
            slug = await render_record(record, template)
        except Exception as exc:
            logger.exception("Sinh PPTX thất bại cho input %s", record.id)
            message = "Không thể sinh file. Vui lòng thử lại."
            if isinstance(exc, LLMError):
                message = f"Lỗi gọi model: {exc}"
            return render_index(request, message, 500, form)

        return RedirectResponse(f"/deck/{slug}", status_code=303)

    @app.post("/inputs/{input_id}/generate")
    async def regenerate(input_id: str, template: str = Form("flat")):
        try:
            record = storage.get_input(input_id, root=base)
        except (storage.StorageError, FileNotFoundError) as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy input"
            ) from exc
        if get_template(template) is None:
            raise HTTPException(status_code=400, detail="Template không hợp lệ")

        try:
            slug = await render_record(record, template)
        except LLMError as exc:
            raise HTTPException(
                status_code=500, detail=f"Lỗi gọi model: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("Sinh lại PPTX thất bại cho input %s", record.id)
            raise HTTPException(
                status_code=500, detail="Không thể sinh file"
            ) from exc
        return RedirectResponse(f"/deck/{slug}", status_code=303)

    @app.post("/inputs/{input_id}/tags")
    async def update_input_tags(input_id: str, tags: str = Form("")):
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        try:
            storage.set_input_tags(input_id, tag_list, root=base)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy input"
            ) from exc
        except storage.StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse("/", status_code=303)

    @app.post("/inputs/{input_id}/outputs/{slug}/delete")
    async def delete_input_output(input_id: str, slug: str):
        try:
            storage.remove_output(input_id, slug, root=base)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy input"
            ) from exc
        except storage.StorageError as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy output"
            ) from exc
        return RedirectResponse("/", status_code=303)

    @app.post("/inputs/{input_id}/delete")
    async def delete_input(input_id: str, confirm: str = Form("")):
        if confirm != "yes":
            raise HTTPException(status_code=400, detail="Thiếu xác nhận xoá")
        try:
            storage.delete_input(input_id, root=base)
        except (storage.StorageError, FileNotFoundError) as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy input"
            ) from exc
        return RedirectResponse("/", status_code=303)

    @app.post("/tags/{tag}/delete")
    async def delete_tag(tag: str):
        storage.delete_tag(tag, root=base)
        return RedirectResponse("/", status_code=303)

    @app.get("/api/inputs/check-title")
    async def check_title(title: str = Query("")):
        status = storage.title_status(title, root=base)
        return {
            "valid": status.valid,
            "duplicate": status.duplicate,
            "normalized": status.normalized,
            "message": status.message,
            "existing_id": status.existing_id,
        }

    @app.get("/api/inputs")
    async def api_inputs():
        payload = []
        for record in storage.list_inputs(root=base):
            outputs = storage.outputs_for(record, root=base)
            payload.append(
                {
                    "id": record.id,
                    "title": record.title,
                    "tags": record.tags,
                    "status": record.status,
                    "created_at": record.created_at,
                    "template": record.template,
                    "output_slug": record.output_slug,
                    "output_slugs": record.output_slugs,
                    "outputs": [
                        {
                            "slug": output.slug,
                            "size_bytes": output.size_bytes,
                            "modified_at": output.modified_at,
                            "has_preview": output.has_preview,
                        }
                        for output in outputs
                    ],
                }
            )
        return payload

    @app.get("/api/tags")
    async def api_tags():
        return {
            "tags": storage.list_tags(root=base),
            "counts": storage.tag_counts(root=base),
        }

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
        return RedirectResponse("/review", status_code=303)

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
