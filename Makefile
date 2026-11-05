SHELL := /bin/sh

UV ?= uv
UV_RUN := $(UV) run
HOST ?= 0.0.0.0
PORT ?= 8765

.DEFAULT_GOAL := help

.PHONY: help install uninstall lock sync server dev test smoke check clean clean-output install-preview

help: ## Hiển thị trợ giúp
	@echo "Demanus commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Tạo .venv và cài dependencies từ uv.lock
	$(UV) sync

install-preview: ## Cài thêm backend preview Aspose (tuỳ chọn)
	$(UV) sync --extra preview-aspose

uninstall: ## Xoá .venv và cache
	rm -rf .venv .pytest_cache

lock: ## Cập nhật uv.lock
	$(UV) lock

sync: ## Đồng bộ môi trường theo uv.lock
	$(UV) sync

server: ## Chạy server LAN
	$(UV_RUN) demanus.py serve --host $(HOST) --port $(PORT)

dev: ## Chạy server với auto-reload
	$(UV_RUN) demanus.py serve --host $(HOST) --port $(PORT) --reload

test: ## Chạy test
	$(UV_RUN) pytest -q

smoke: ## Sinh deck mẫu offline
	$(UV_RUN) demanus.py smoke

check: ## Kiểm tra cú pháp
	$(UV_RUN) python -m compileall -q app demanus.py

clean: ## Xoá cache Python
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache

clean-output: ## Xoá toàn bộ file trong output/
	@echo "CẢNH BÁO: thao tác này xoá toàn bộ output/."
	@read -p "Nhấn Enter để tiếp tục, Ctrl+C để huỷ..." _; \
	rm -rf output/* output/.[!.]* 2>/dev/null || true
