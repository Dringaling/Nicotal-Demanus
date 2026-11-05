# Chính sách giấy phép

## Giấy phép chính

- **AGPL-3.0-or-later** cho toàn bộ mã nguồn do dự án viết. Xem `LICENSE`.
- **MPL-2.0** chỉ dùng cho module bắt buộc phải tách khỏi AGPLv3. Xem
  `LICENSE.MPL-2.0` và danh sách trong `NOTICE`.
- **Ngoại lệ Aspose.Slides** cho module preview (AGPLv3 + special exception).
  Xem `NOTICE`.

Hiện dự án **chưa có module MPL-2.0**; chính sách sẵn sàng cho tương lai.

## Module do dự án viết

| Phạm vi | Giấy phép | Ghi chú |
|---|---|---|
| `demanus.py` | AGPL-3.0-or-later | CLI entry point |
| `app/*.py` | AGPL-3.0-or-later | Trừ module preview Aspose |
| `app/preview/aspose.py` | AGPL-3.0-or-later + exception | Xem `NOTICE` |
| `app/preview/libreoffice.py` | AGPL-3.0-or-later | |
| `tests/*.py` | AGPL-3.0-or-later | |
| `web/` (HTML/CSS/JS) | AGPL-3.0-or-later | |
| `templates/themes/*.toml` | AGPL-3.0-or-later | Metadata thiết kế |

Quy ước header:

```text
# SPDX-License-Identifier: AGPL-3.0-or-later
```

Module MPL (nếu thêm sau này) phải dùng
`# SPDX-License-Identifier: MPL-2.0`, được liệt kê trong bảng trên và trong
`NOTICE`.

## Dependency bên thứ ba

Báo cáo đầy đủ: `THIRD_PARTY_LICENSES.md` (sinh bằng `make licenses`).

Các package cần review:

| Package | Giấy phép | Đánh giá |
|---|---|---|
| `pymupdf` | AGPL-3.0 hoặc thương mại Artifex | Tương thích AGPLv3 của dự án |
| `pymupdf4llm` | UNKNOWN (thuộc PyMuPDF) | Cùng bộ PyMuPDF; coi như AGPL-3.0/commercial |
| `pymupdf_layout` | UNKNOWN (thuộc PyMuPDF) | Cùng bộ PyMuPDF; coi như AGPL-3.0/commercial |
| `certifi` | MPL-2.0 | Tương thích qua điều khoản secondary license của MPL-2.0 |
| `uvloop` | MIT / Apache-2.0 | Tương thích |
| `aspose-slides` | Proprietary | Chỉ dùng qua extra `preview-aspose`; đã có exception trong `NOTICE` |

Các dependency còn lại (FastAPI, python-pptx, Jinja2, httpx, pydantic,
tomli-w, ...) dùng MIT/BSD/Apache-2.0, tương thích AGPLv3.

`UNKNOWN` trong báo cáo không có nghĩa là không có giấy phép: đó là các
package không khai báo metadata license. Cần review thủ công khi nâng cấp.

## Quy trình

```bash
cd demanus
make licenses     # sinh lại THIRD_PARTY_LICENSES.md
```

- Không sửa nội dung `LICENSE`, `LICENSE.MPL-2.0`; giữ nguyên văn.
- Mọi thay đổi giấy phép phải review pháp lý trước khi phát hành.
