# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.config import detect_lan_ip, load_settings
from app.render import render_deck
from app.sample import sample_deck


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    settings = load_settings()
    host = args.host or settings.server.host
    port = args.port or settings.server.port
    lan_host = settings.server.lan_ip.strip() or detect_lan_ip()
    print(f"Server: http://{host}:{port}")
    print(f"LAN:    http://{lan_host}:{port}")
    uvicorn.run("app.web:app", host=host, port=port, reload=args.reload)


def cmd_smoke(args: argparse.Namespace) -> None:
    from app.preview import render_preview

    out_path = Path(args.out or "output/_smoke.pptx")
    spec = sample_deck()
    render_deck(spec, out_path)
    render_preview(out_path, spec, out_path.parent / out_path.stem / "preview")
    print(f"Đã tạo {out_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    from app.llm import LLMClient
    from app.preview import render_preview
    from app.storage import allocate_output, create_input, update_status

    settings = load_settings()
    record = create_input(args.name, args.desc)
    update_status(record.id, "generating")

    try:
        spec, usage = asyncio.run(
            LLMClient(settings).generate_spec(args.name, args.desc)
        )
        out_path = allocate_output(args.name, record.id)
        render_deck(spec, out_path)
        render_preview(
            out_path, spec, out_path.parent / out_path.stem / "preview"
        )
        update_status(record.id, "done")
    except Exception:
        update_status(record.id, "failed")
        raise

    print(f"Đã tạo {out_path}")
    print(
        "usage: "
        f"prompt_tokens={usage.prompt_tokens} "
        f"cached_tokens={usage.cached_tokens} "
        f"estimated_cost={usage.estimated_cost} "
        f"from_cache={usage.from_cache}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="demanus")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Chạy server LAN")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=cmd_serve)

    smoke = subparsers.add_parser("smoke", help="Sinh deck mẫu offline")
    smoke.add_argument("--out", default=None)
    smoke.set_defaults(func=cmd_smoke)

    generate = subparsers.add_parser("generate", help="Sinh deck từ mô tả")
    generate.add_argument("name")
    generate.add_argument("desc")
    generate.set_defaults(func=cmd_generate)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
