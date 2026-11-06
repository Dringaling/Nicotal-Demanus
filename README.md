# Demanus

Sinh bài trình bày PowerPoint tiếng Việt từ mô tả, dùng `python-pptx` và
DeepInfra (service tier `flex`).

## Yêu cầu

- `uv` (đã bao gồm Python 3.12).
- Tùy chọn: LibreOffice (ưu tiên) hoặc Aspose.Slides để render preview đúng
  fidelity. Không có backend nào thì web hiện "Chưa có preview".

## Cài đặt

```bash
cd demanus
make install          # hoặc: uv sync
make install-preview  # tuỳ chọn: thêm Aspose.Slides cho preview
```

## Cấu hình

- `config/providers.toml`:
  - `default_provider` + `default_model` chọn model đang dùng.
  - `[providers.<type>]` khai báo `type` (`deepinfra` | `openai` | `lmstudio`),
    `base_url`, timeout, retries dùng chung.
  - `[providers.<type>.params]` là params mặc định cho type.
  - Mỗi model là `[providers.<type>.<model-id>]`, **bắt buộc** có
    `api_key_env` + `secret_file` riêng (chuỗi rỗng nếu local không cần key),
    kèm `[generation]`, `[cache]`, `[params]` tuỳ chọn.
  - API key không nằm trong TOML.
- Secret: mỗi model một biến môi trường + file riêng, ví dụ:

  ```env
  DEMANUS_DEEPINFRA_FLEX_8F3A=<api-key>
  DEMANUS_DEEPINFRA_STANDARD_9C1B=<api-key>
  ```

  Biến môi trường thật (nếu set) được ưu tiên hơn file. Local model
  (`lmstudio-*`) để trống cả `api_key_env` và `secret_file`.
- `DEMANUS_PROVIDER=<type>` + `DEMANUS_MODEL=<model-id>` override lúc load.
- `uv run demanus.py providers` liệt kê model + trạng thái key.

## Chạy

```bash
make server           # http://0.0.0.0:8765
make dev              # auto-reload
make smoke            # sinh output/_smoke.pptx, không cần API key
make test             # pytest
```

Input gồm 3 phần: **Tiêu đề** (duy nhất, 1–200 ký tự), **Mô tả** (ngắn) và
**Chi tiết** (nội dung từng slide, không giới hạn). Chi tiết dài được chia chunk
(`chunk_chars`, mặc định 8000 ký tự) trước khi gửi model. Tags nhập nhiều tag,
có gợi ý tag sẵn có; sidebar lọc và xoá tag.

Trên Windows, dùng Git Bash/WSL để chạy `make`, hoặc chạy trực tiếp `uv ...`.

## Provider

```bash
uv run demanus.py providers
uv run demanus.py generate "Tên" "Mô tả" \
  --provider lmstudio-native --model gemma-4-e4b-it
uv run demanus.py serve --provider lmstudio-openai \
  --model gemma-4-e4b-it
```

- `deepinfra`: DeepInfra OpenAI-compatible; gửi thêm `service_tier`, cache
  fields và `fail_fast`.
- `openai`: mọi server OpenAI-compatible (`{base_url}/chat/completions`), body
  tối thiểu, có thể dùng `response_format`.
- `lmstudio`: LM Studio native (`{base_url}/api/v1/chat`), body
  `input/system_prompt/max_output_tokens/store`, không cần API key.

## Truy cập LAN

- `[server] host = "0.0.0.0"` và `port = 8765`.
- `lan_ip` trong `[server]` là IP máy này (mặc định `192.168.1.12`); để trống
  để tự dò.
- Máy khác mở `http://<lan_ip>:8765`; cần mở firewall cho cổng 8765.
- Giao diện: `/` tạo deck, `/review` xem thumbnail tất cả deck,
  `/deck/<slug>` lật slide.

## Template

- `templates/themes/*.toml` — metadata, palette, layout; quét lúc khởi động.
- `flat` — thiết kế flat mặc định.
- `pptx` — dùng `.pptx` làm gốc, fill placeholder (vd. `dividing-fractions`).
- `boho` — dùng asset trích từ template (nền giấy + cọ) trong
  `templates/assets/boho/`.
- `copy` — copy slide mẫu, thay text; không gửi template vào prompt.
- `theme` — dựng theo TOML layout (vd. `neo_tech_minimal`).
- Bộ theme TOML: `neo_tech_minimal`, `gruvbox`, `soft_light`, `cappuccino`,
  `latte`, `cream_pink`.
- Font luôn Lexend.

## Windows

- Cài Git for Windows và `uv` (`install.bat` thử cài `uv` bằng `winget`).
- Chạy `install.bat` lần đầu để tạo `.venv` và `uv sync`.
- Chạy `Nicotal-Demanus.bat` để mở phần mềm (tự cài nếu thiếu, tự kiểm tra cập
  nhật).
- `update.bat` cập nhật shallow `main` bằng `fetch --depth=1` + `reset --hard`
  (xoá thay đổi cục bộ).

## Cấu trúc

- `app/config.py` — nạp cấu hình, secret, đường dẫn.
- `app/schema.py` — Pydantic `DeckSpec`.
- `app/prompts.py` — system prompt ổn định + JSON schema.
- `app/llm.py` — client DeepInfra, retry, cache.
- `app/render.py` — `DeckSpec` → `.pptx`.
- `app/template_render.py` — dựng `.pptx` từ template gốc (prototype).
- `app/template_profile.py` — metadata template (khổ, màu, placeholder, media)
  để đưa vào prompt.
- `app/templates_catalog.py` — quét `templates/themes/*.toml`, design tokens.
- `app/boho_render.py` — dựng nền giấy/cọ boho từ asset.
- `app/copy_slide_render.py` — copy slide mẫu, thay text.
- `app/theme_render.py` — dựng theo TOML layout (Neo Tech Minimalist).
- `templates/assets/boho/` — asset đã trích (tracked).
- `templates/themes/` — TOML theme (tracked).
- `app/storage.py` — input records/text/tags + `output/<slug>.pptx`.
- `app/preview/` — chọn backend preview: `libreoffice.py` (soffice → PDF →
  PNG 150 DPI, toàn bộ slide) → `aspose.py` (tối đa 10 slide, rộng 640px) →
  không preview. Không dùng Pillow.
- `app/web.py` — FastAPI + Jinja2.
- `web/` — template HTML, CSS, JS.
- `templates/` — file `.pptx` mẫu gốc (giữ nguyên).
- `install.bat`, `update.bat`, `Nicotal-Demanus.bat` — bộ cài Windows.

## Preview

- Backend được chọn tự động: **LibreOffice** (`soffice`) → **Aspose.Slides** →
  **không preview**.
- LibreOffice render toàn bộ slide ở 150 DPI.
- Aspose render tối đa 10 slide đầu, ảnh rộng 640px; cài bằng
  `make install-preview` hoặc `uv sync --extra preview-aspose`.
- Không có backend thì `/preview/<slug>/<index>` trả 404 và giao diện hiện
  "Chưa có preview".
- Aspose.Slides là thư viện độc quyền; xem `NOTICE` cho ngoại lệ AGPLv3 và
  `THIRD_PARTY_LICENSES.md` cho danh sách giấy phép bên thứ ba.

## Giấy phép

- Mã nguồn dự án: **AGPLv3** (`LICENSE`), dùng cho mọi module mặc định.
- **MPL-2.0** (`LICENSE.MPL-2.0`) chỉ dành cho module bắt buộc không tương
  thích AGPLv3; hiện chưa có module nào như vậy.
- Ngoại lệ đặc biệt cho module preview Aspose.Slides: xem `NOTICE`.
- Chính sách giấy phép: `LICENSES.md`.
- Danh sách dependency và giấy phép: `THIRD_PARTY_LICENSES.md`
  (sinh bằng `make licenses`).
