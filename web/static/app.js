(function () {
  const input = document.querySelector('input[name="title"][data-check-url]');
  if (!input) {
    return;
  }

  const error = document.querySelector("[data-title-error]");
  const ok = document.querySelector("[data-title-ok]");
  const submit = document.querySelector(
    'form[action="/generate"] button[type="submit"]'
  );
  const url = input.dataset.checkUrl;
  let timer = null;
  let sequence = 0;

  function setState(state, message) {
    if (error) {
      error.textContent = message || "";
      error.hidden = state !== "error";
    }
    if (ok) {
      ok.hidden = state !== "ok";
    }
    if (submit) {
      submit.disabled = state === "error";
    }
  }

  async function check() {
    const value = input.value.replace(/[\r\n\t]+/g, " ");
    if (!value.trim()) {
      setState("idle");
      return;
    }

    const current = ++sequence;
    try {
      const response = await fetch(
        `${url}?title=${encodeURIComponent(value)}`
      );
      const data = await response.json();
      if (current !== sequence) {
        return;
      }
      if (data.duplicate || !data.valid) {
        setState("error", data.message || "Tiêu đề không hợp lệ.");
      } else {
        setState("ok");
      }
    } catch (exc) {
      setState("idle");
    }
  }

  input.addEventListener("input", () => {
    if (/[\r\n\t]/.test(input.value)) {
      input.value = input.value.replace(/[\r\n\t]+/g, " ");
    }
    clearTimeout(timer);
    timer = setTimeout(check, 300);
  });

  if (input.value.trim()) {
    check();
  }
})();

(function () {
  const carousel = document.querySelector(".carousel");
  if (!carousel) {
    return;
  }

  const slug = window.location.pathname.split("/").filter(Boolean).pop();
  const count = Number(carousel.dataset.count || "0");
  const image = document.getElementById("slide");
  const counter = document.getElementById("current");
  let index = 1;

  function show(next) {
    if (count === 0) {
      return;
    }
    index = ((next - 1 + count) % count) + 1;
    image.src = `/preview/${slug}/${index}`;
    counter.textContent = String(index);
  }

  carousel.querySelector(".prev").addEventListener("click", () => show(index - 1));
  carousel.querySelector(".next").addEventListener("click", () => show(index + 1));

  document.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      show(index - 1);
    }
    if (event.key === "ArrowRight") {
      show(index + 1);
    }
  });
})();

(function () {
  document.querySelectorAll("[data-tags-layout]").forEach((root) => {
    const form = root.querySelector(".tags-filter");
    if (!form) {
      return;
    }
    let timer = null;

    function submit() {
      clearTimeout(timer);
      timer = setTimeout(() => form.submit(), 150);
    }

    root.querySelectorAll('input[type="checkbox"]').forEach((box) => {
      box.addEventListener("change", submit);
    });

    const selectAll = root.querySelector("[data-select-all]");
    if (selectAll) {
      selectAll.addEventListener("click", () => {
        root.querySelectorAll('input[type="checkbox"]').forEach((box) => {
          box.checked = true;
        });
        submit();
      });
    }

    const deselectAll = root.querySelector("[data-deselect-all]");
    if (deselectAll) {
      deselectAll.addEventListener("click", () => {
        root.querySelectorAll('input[type="checkbox"]').forEach((box) => {
          box.checked = false;
        });
        submit();
      });
    }
  });
})();

(function () {
  document.querySelectorAll("[data-expand]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".input-card");
      const details = card && card.querySelector(".input-details");
      if (!details) {
        return;
      }
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      card.classList.toggle("expanded", !expanded);
      details.hidden = expanded;
      const label = button.querySelector("[data-expand-label]");
      if (label) {
        label.textContent = expanded ? "Xem output" : "Thu gọn";
      }
    });
  });
})();

(function () {
  const MAX_TAG_LEN = 32;

  function normalizeTag(value) {
    const withoutAccent = String(value)
      .replace(/đ/g, "d")
      .replace(/Đ/g, "D")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
    return withoutAccent
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function tagError(tag) {
    if (!tag) {
      return "Tag không hợp lệ: chỉ chữ không dấu, số và dấu gạch ngang.";
    }
    if (tag.length > MAX_TAG_LEN) {
      return `Tag tối đa ${MAX_TAG_LEN} ký tự`;
    }
    return "";
  }

  function initTagEditor(config) {
    const { root, hidden, chips, entry } = config;
    if (!hidden || !chips || !entry) {
      return;
    }
    const error = root.querySelector("[data-tags-error]");
    const onChange = config.onChange || function () {};
    let values = (hidden.value || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    function showError(message) {
      if (!error) {
        return;
      }
      error.textContent = message || "";
      error.hidden = !message;
    }

    function render() {
      chips.innerHTML = "";
      values.forEach((tag, index) => {
        const chip = document.createElement("span");
        chip.className = "tag-chip";
        chip.textContent = tag;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "×";
        remove.addEventListener("click", () => {
          values.splice(index, 1);
          render();
          onChange();
        });
        chip.appendChild(remove);
        chips.appendChild(chip);
      });
      hidden.value = values.join(",");
    }

    function add(raw) {
      const tag = normalizeTag(raw);
      const message = tagError(tag);
      if (message) {
        showError(message);
        return false;
      }
      showError("");
      if (!values.includes(tag)) {
        values.push(tag);
      }
      entry.value = "";
      render();
      return true;
    }

    entry.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        if (add(entry.value)) {
          onChange();
        }
      }
    });
    entry.addEventListener("blur", () => {
      if (entry.value.trim() && add(entry.value)) {
        onChange();
      }
    });
    render();
  }

  const createRoot = document.getElementById("tag-input");
  if (createRoot) {
    initTagEditor({
      root: createRoot,
      hidden: document.getElementById("tags-hidden"),
      chips: document.getElementById("tag-chips"),
      entry: document.getElementById("tag-entry"),
    });
  }

  document.querySelectorAll("[data-tag-editor]").forEach((form) => {
    let submitted = false;
    initTagEditor({
      root: form,
      hidden: form.querySelector('input[name="tags"]'),
      chips: form.querySelector("[data-tag-chips]"),
      entry: form.querySelector(".tag-entry"),
      onChange: () => {
        if (submitted) {
          return;
        }
        submitted = true;
        form.submit();
      },
    });
    form.addEventListener("submit", () => {
      submitted = true;
    });
  });

  document.querySelectorAll("[data-reuse-tags]").forEach((root) => {
    const form = root.closest("form");
    const inputId = root.dataset.inputId;
    const hidden = form ? form.querySelector("[data-tags-hidden]") : null;
    if (!form || !inputId || !hidden) {
      return;
    }

    async function save() {
      try {
        const body = new URLSearchParams();
        body.set("tags", hidden.value);
        const response = await fetch(`/inputs/${inputId}/tags`, {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body,
        });
        if (!response.ok) {
          throw new Error("save failed");
        }
      } catch (exc) {
        const error = root.querySelector("[data-tags-error]");
        if (error) {
          error.textContent = "Không lưu được tag. Thử lại.";
          error.hidden = false;
        }
      }
    }

    initTagEditor({
      root,
      hidden,
      chips: root.querySelector("[data-tag-chips]"),
      entry: root.querySelector(".tag-entry"),
      onChange: save,
    });
  });
})();

(function () {
  const OVERLAYS =
    "[data-overlay], [data-help-overlay], [data-changelog-overlay], [data-ai-config-overlay]";
  const BODY_CLASSES = [
    "overlay-open",
    "help-open",
    "changelog-open",
    "ai-config-open",
  ];

  function initOverlay(options) {
    const overlay = document.querySelector(options.overlay);
    if (!overlay) {
      return null;
    }
    const dialog = options.dialog ? overlay.querySelector(options.dialog) : null;
    const closeButton = options.close
      ? overlay.querySelector(options.close)
      : null;
    const bodyClass = options.bodyClass || "overlay-open";
    let lastFocus = null;

    function focusable() {
      if (!dialog) {
        return [];
      }
      return Array.from(
        dialog.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
      ).filter((element) => !element.disabled);
    }

    function open(trigger) {
      lastFocus = trigger;
      document.querySelectorAll(OVERLAYS).forEach((element) => {
        if (element !== overlay) {
          element.hidden = true;
        }
      });
      BODY_CLASSES.forEach((name) => document.body.classList.remove(name));
      overlay.hidden = false;
      document.body.classList.add(bodyClass);
      if (closeButton) {
        closeButton.focus();
      }
    }

    function close() {
      overlay.hidden = true;
      document.body.classList.remove(bodyClass);
      if (lastFocus && typeof lastFocus.focus === "function") {
        lastFocus.focus();
      }
    }

    function onKeydown(event) {
      if (overlay.hidden) {
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const items = focusable();
      if (!items.length) {
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) {
        close();
      }
    });
    if (closeButton) {
      closeButton.addEventListener("click", close);
    }
    document.addEventListener("keydown", onKeydown);

    document.querySelectorAll(options.trigger).forEach((trigger) => {
      trigger.addEventListener("click", () => {
        open(trigger);
        if (options.onOpen) {
          options.onOpen(trigger);
        }
      });
    });

    return { open, close, overlay };
  }

  function initFetchedOverlay(options) {
    const overlay = document.querySelector(options.overlay);
    if (!overlay) {
      return null;
    }
    const body = overlay.querySelector(options.body);
    const title = options.title ? overlay.querySelector(options.title) : null;
    const cache = new Map();

    async function load(key) {
      if (cache.has(key)) {
        return cache.get(key);
      }
      const url = key
        ? `${options.endpoint}?${options.param}=${encodeURIComponent(key)}`
        : options.endpoint;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error("fetch failed");
      }
      const data = await response.json();
      cache.set(key, data);
      return data;
    }

    return initOverlay({
      ...options,
      onOpen: async (trigger) => {
        const key =
          options.param && options.datasetKey
            ? trigger.dataset[options.datasetKey] || ""
            : "";
        if (title) {
          title.textContent = options.fallbackTitle || "";
        }
        if (body) {
          body.innerHTML = '<p class="muted">Đang tải...</p>';
        }
        try {
          const data = await load(key);
          if (title) {
            title.textContent = data.title || options.fallbackTitle || "";
          }
          if (body) {
            body.innerHTML = options.render
              ? options.render(data)
              : data.html || '<p class="muted">Chưa có nội dung.</p>';
          }
        } catch (exc) {
          if (body) {
            body.innerHTML = '<p class="error">Không tải được nội dung.</p>';
          }
        }
      },
    });
  }

  window.Demanus = Object.assign(window.Demanus || {}, {
    initOverlay,
    initFetchedOverlay,
  });

  initFetchedOverlay({
    trigger: "[data-help]",
    overlay: "[data-help-overlay]",
    dialog: "[data-help-dialog]",
    body: "[data-help-body]",
    title: "[data-help-title]",
    close: "[data-help-close]",
    endpoint: "/api/help",
    param: "layout",
    datasetKey: "help",
    fallbackTitle: "Trợ giúp",
    bodyClass: "help-open",
  });
})();

(function () {
  const init = window.Demanus && window.Demanus.initFetchedOverlay;
  if (!init) {
    return;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  init({
    trigger: "[data-changelog]",
    overlay: "[data-changelog-overlay]",
    dialog: "[data-changelog-dialog]",
    body: "[data-changelog-body]",
    close: "[data-changelog-close]",
    endpoint: "/api/changelog",
    bodyClass: "changelog-open",
    render: (data) => {
      const versions = data.versions || [];
      if (!versions.length) {
        return '<p class="muted">Chưa có thông tin cập nhật.</p>';
      }
      return versions
        .map(
          (entry) =>
            `<section class="changelog-entry" id="v${escapeHtml(entry.version)}">` +
            `<h3>v${escapeHtml(entry.version)} — ${escapeHtml(entry.title)}</h3>` +
            `${entry.html}</section>`
        )
        .join("");
    },
  });
})();

(function () {
  const overlay = document.querySelector("[data-overlay]");
  if (!overlay) {
    return;
  }

  const dialog = overlay.querySelector("[data-dialog]");
  const title = overlay.querySelector("[data-delete-title]");
  const count = overlay.querySelector("[data-delete-count]");
  const form = overlay.querySelector("[data-delete-form]");
  const closeButton = overlay.querySelector("[data-close]");
  let lastFocus = null;

  function focusable() {
    return Array.from(
      dialog.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => !element.disabled);
  }

  function open(trigger) {
    lastFocus = trigger;
    if (title) {
      title.textContent = trigger.dataset.inputTitle || "";
    }
    if (count) {
      const total = Number(trigger.dataset.outputCount || "0");
      count.textContent = `${total} output sẽ bị xoá.`;
    }
    if (form) {
      form.action = trigger.dataset.action || "";
    }
    overlay.hidden = false;
    document.body.classList.add("overlay-open");
    if (closeButton) {
      closeButton.focus();
    }
  }

  function close() {
    overlay.hidden = true;
    document.body.classList.remove("overlay-open");
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
  }

  document.querySelectorAll("[data-delete-trigger]").forEach((trigger) => {
    trigger.addEventListener("click", () => open(trigger));
  });
  if (closeButton) {
    closeButton.addEventListener("click", close);
  }
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      close();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (overlay.hidden) {
      return;
    }
    if (event.key === "Escape") {
      close();
      return;
    }
    if (event.key !== "Tab") {
      return;
    }
    const items = focusable();
    if (!items.length) {
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
})();

(function () {
  const init = window.Demanus && window.Demanus.initOverlay;
  const root = document.querySelector("[data-ai-config-overlay]");
  if (!init || !root) {
    return;
  }

  const body = root.querySelector("[data-ai-config-body]");
  const errorBox = root.querySelector("[data-ai-config-error]");
  const state = {
    payload: null,
    provider: "",
    model: "",
    defaultProvider: "",
    defaultModel: "",
    creatingProvider: false,
    creatingModel: false,
  };

  const KEY_LABELS = {
    set: "đã có key",
    missing: "chưa có key",
    "not-required": "không cần key",
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function showError(message) {
    if (!errorBox) {
      return;
    }
    errorBox.textContent = message || "";
    errorBox.hidden = !message;
  }

  async function request(url, options) {
    const response = await fetch(url, options);
    let data = null;
    try {
      data = await response.json();
    } catch (exc) {
      data = null;
    }
    if (!response.ok) {
      const detail = data && data.detail;
      throw new Error(detail || "Không lưu được cấu hình");
    }
    return data;
  }

  function providers() {
    return (state.payload && state.payload.providers) || [];
  }

  function findProvider(name) {
    return providers().find((item) => item.name === name) || null;
  }

  function currentProvider() {
    return findProvider(state.provider) || providers()[0] || null;
  }

  function currentModel() {
    const provider = currentProvider();
    if (!provider) {
      return null;
    }
    return provider.models.find((item) => item.id === state.model) || null;
  }

  function section(title, key) {
    const node = el("details", "ai-config-section");
    node.open = true;
    const summary = el("summary");
    summary.appendChild(el("span", "ai-config-title", title));
    node.appendChild(summary);
    const content = el("div", "ai-config-section-body");
    node.appendChild(content);
    return { node, content };
  }

  function selectField(label, options, value, onChange) {
    const wrap = el("label", "ai-config-field");
    wrap.appendChild(el("span", null, label));
    const select = el("select");
    options.forEach((option) => {
      const node = el("option", null, option.label);
      node.value = option.value;
      if (option.value === value) {
        node.selected = true;
      }
      select.appendChild(node);
    });
    select.addEventListener("change", () => onChange(select.value));
    wrap.appendChild(select);
    return { wrap, input: select };
  }

  function inputField(label, value, options) {
    const config = options || {};
    const wrap = el("label", "ai-config-field");
    wrap.appendChild(el("span", null, label));
    const input = el("input");
    input.value = value === undefined || value === null ? "" : value;
    if (config.type) {
      input.type = config.type;
    }
    if (config.step) {
      input.step = config.step;
    }
    if (config.placeholder) {
      input.placeholder = config.placeholder;
    }
    if (config.readOnly) {
      input.readOnly = true;
    }
    wrap.appendChild(input);
    return { wrap, input };
  }

  function checkField(label, value) {
    const wrap = el("label", "ai-config-check");
    const input = el("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
    wrap.appendChild(input);
    wrap.appendChild(el("span", null, label));
    return { wrap, input };
  }

  function actions(nodes) {
    const row = el("div", "ai-config-actions");
    nodes.filter(Boolean).forEach((node) => row.appendChild(node));
    return row;
  }

  function button(label, className, onClick) {
    const node = el("button", className || "button", label);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
  }

  function confirmButton(label, onConfirm) {
    let armed = false;
    let timer = null;
    const node = el("button", "button danger", label);
    node.type = "button";
    node.addEventListener("click", async () => {
      if (!armed) {
        armed = true;
        node.textContent = "Bấm lần nữa để xoá";
        timer = setTimeout(() => {
          armed = false;
          node.textContent = label;
        }, 4000);
        return;
      }
      clearTimeout(timer);
      armed = false;
      node.textContent = label;
      await onConfirm();
    });
    return node;
  }

  function applyConfig(data, provider, model) {
    state.payload = data;
    state.creatingProvider = false;
    state.creatingModel = false;
    if (provider) {
      state.provider = provider;
    }
    if (model) {
      state.model = model;
    }
    state.defaultProvider = data.default_provider;
    state.defaultModel = data.default_model;
    render();
  }

  function renderDefaults() {
    const { node, content } = section("Mặc định");
    const provider = findProvider(state.defaultProvider) || providers()[0];
    const providerOptions = providers().map((item) => ({
      value: item.name,
      label: item.name + " · " + item.type,
    }));
    const modelOptions = ((provider && provider.models) || []).map((item) => ({
      value: item.id,
      label: item.id + (item.key === "missing" ? " (chưa có key)" : ""),
    }));

    content.appendChild(
      selectField("Nhà cung cấp", providerOptions, provider && provider.name, (value) => {
        state.defaultProvider = value;
        const next = findProvider(value);
        state.defaultModel = next && next.models[0] ? next.models[0].id : "";
        render();
      }).wrap
    );
    content.appendChild(
      selectField("Model", modelOptions, state.defaultModel, (value) => {
        state.defaultModel = value;
        render();
      }).wrap
    );

    const status = state.payload.default_key_status;
    if (status === "missing") {
      content.appendChild(
        el(
          "p",
          "ai-config-warn",
          "Model mặc định chưa có API key; sinh deck sẽ báo thiếu key."
        )
      );
    }

    content.appendChild(
      actions([
        button(
          "Dùng làm mặc định",
          "button",
          async () => {
            if (!state.defaultProvider || !state.defaultModel) {
              return;
            }
            try {
              const data = await request("/api/ai-config/default", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  provider: state.defaultProvider,
                  model: state.defaultModel,
                }),
              });
              showError("");
              applyConfig(data.config, state.defaultProvider, state.defaultModel);
            } catch (exc) {
              showError(exc.message);
            }
          }
        ),
      ])
    );
    return node;
  }

  function renderProvider() {
    const { node, content } = section("Provider");
    const provider = state.creatingProvider ? null : currentProvider();

    const head = el("div", "ai-config-row");
    head.appendChild(
      selectField(
        "Chọn provider",
        providers().map((item) => ({
          value: item.name,
          label:
            item.name +
            " · " +
            item.type +
            (item.source === "local" ? " · tự tạo" : ""),
        })),
        state.provider,
        (value) => {
          state.provider = value;
          const next = findProvider(value);
          state.model = next && next.models[0] ? next.models[0].id : "";
          state.creatingModel = false;
          render();
        }
      ).wrap
    );
    head.appendChild(
      button("Thêm provider", "button secondary", () => {
        state.creatingProvider = true;
        render();
      })
    );
    content.appendChild(head);

    const fields = el("div", "ai-config-grid");
    const name = inputField(
      "Tên provider",
      provider ? provider.name : "",
      {
        readOnly: Boolean(provider),
        placeholder: "vi-du: local-openai",
      }
    );
    fields.appendChild(name.wrap);

    const type = selectField(
      "Kiểu kết nối",
      (state.payload.types || []).map((value) => ({ value, label: value })),
      provider ? provider.type : "openai",
      () => {}
    );
    if (provider) {
      type.input.disabled = true;
      type.wrap.title = "Không đổi được type sau khi tạo";
    }
    fields.appendChild(type.wrap);

    const baseUrl = inputField(
      "Base URL",
      provider ? provider.base_url : "",
      { placeholder: "https://api.example.com/v1" }
    );
    fields.appendChild(baseUrl.wrap);

    const timeout = inputField(
      "Timeout (giây)",
      provider ? provider.timeout_seconds : 180,
      { type: "number", step: "1" }
    );
    fields.appendChild(timeout.wrap);

    const retries = inputField(
      "Số lần thử",
      provider ? provider.max_retries : 3,
      { type: "number", step: "1" }
    );
    fields.appendChild(retries.wrap);
    content.appendChild(fields);

    if (provider) {
      content.appendChild(
        el(
          "p",
          "muted",
          provider.source === "local"
            ? "Provider tự tạo: lưu trong config/providers.local.toml."
            : "Provider phát hành sẵn: lưu sẽ ghi bản đè vào config/providers.local.toml."
        )
      );
    }

    const isDefaultProvider =
      provider && provider.name === state.payload.default_provider;
    content.appendChild(
      actions([
        button(
          "Lưu provider",
          "button",
          async () => {
            try {
              const data = await request("/api/ai-config/provider", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  name: name.input.value.trim(),
                  type: type.input.value,
                  base_url: baseUrl.input.value.trim(),
                  timeout_seconds: Number(timeout.input.value || 180),
                  max_retries: Number(retries.input.value || 0),
                  create: state.creatingProvider,
                }),
              });
              showError("");
              applyConfig(
                data.config,
                name.input.value.trim(),
                provider ? state.model : ""
              );
            } catch (exc) {
              showError(exc.message);
            }
          }
        ),
        provider && provider.source === "local" && !isDefaultProvider
          ? confirmButton(
              "Xoá provider",
              async () => {
                try {
                  const data = await request(
                    "/api/ai-config/provider?name=" +
                      encodeURIComponent(provider.name),
                    { method: "DELETE" }
                  );
                  showError("");
                  applyConfig(data.config, "", "");
                } catch (exc) {
                  showError(exc.message);
                }
              }
            )
          : null,
        state.creatingProvider
          ? button("Huỷ", "button secondary", () => {
              state.creatingProvider = false;
              render();
            })
          : null,
      ])
    );
    return node;
  }

  function renderModel() {
    const { node, content } = section("Model");
    const provider = currentProvider();
    if (!provider) {
      content.appendChild(el("p", "muted", "Tạo provider trước."));
      return node;
    }
    const model = state.creatingModel ? null : currentModel();

    const head = el("div", "ai-config-row");
    head.appendChild(
      selectField(
        "Chọn model",
        provider.models.map((item) => ({
          value: item.id,
          label: item.id + (item.is_default ? " · mặc định" : ""),
        })),
        state.model,
        (value) => {
          state.model = value;
          render();
        }
      ).wrap
    );
    head.appendChild(
      button("Thêm model", "button secondary", () => {
        state.creatingModel = true;
        render();
      })
    );
    content.appendChild(head);

    const grid = el("div", "ai-config-grid");
    const id = inputField("ID model", model ? model.id : "", {
      readOnly: Boolean(model),
      placeholder: "vi-du: deepseek-flash-flex",
    });
    grid.appendChild(id.wrap);
    const modelName = inputField(
      "Tên model trên server",
      model ? model.model : "",
      { placeholder: "deepseek-ai/DeepSeek-V4.1-Flash-1017" }
    );
    grid.appendChild(modelName.wrap);
    const key = inputField(
      "API key",
      "",
      {
        type: "password",
        placeholder: model
          ? KEY_LABELS[model.key] || model.key
          : "để trống nếu server không cần key",
      }
    );
    grid.appendChild(key.wrap);
    content.appendChild(grid);

    const params = el("div", "ai-config-grid");
    const allowed = (state.payload.param_fields || {})[provider.type] || [];
    const paramsValues = {};
    allowed.forEach((field) => {
      const value = (model && model.params && model.params[field]) || "";
      if (field === "service_tier") {
        const field1 = selectField(
          "service_tier",
          [
            { value: "flex", label: "flex" },
            { value: "standard", label: "standard" },
          ],
          value || "flex",
          () => {}
        );
        paramsValues[field] = () => field1.input.value;
        params.appendChild(field1.wrap);
      } else if (field === "fail_fast" || field === "store") {
        const field1 = checkField(field, value);
        paramsValues[field] = () => field1.input.checked;
        params.appendChild(field1.wrap);
      } else {
        const field1 = inputField(
          field,
          Array.isArray(value) ? value.join(", ") : value,
          { placeholder: "danh sách cách nhau bởi dấu phẩy" }
        );
        paramsValues[field] = () => field1.input.value;
        params.appendChild(field1.wrap);
      }
    });
    content.appendChild(params);

    const generation = el("div", "ai-config-grid");
    const generationValues = {};
    const gen = (model && model.generation) || {};
    [
      ["temperature", "number", "0.1"],
      ["top_p", "number", "0.05"],
      ["max_tokens", "number", "100"],
      ["chunk_chars", "number", "100"],
    ].forEach(([field, type, step]) => {
      const field1 = inputField(field, gen[field] === undefined ? "" : gen[field], {
        type,
        step,
      });
      generationValues[field] = () => field1.input.value;
      generation.appendChild(field1.wrap);
    });
    const format = selectField(
      "response_format",
      (state.payload.response_formats || []).map((value) => ({
        value,
        label: value,
      })),
      gen.response_format || "json_schema",
      () => {}
    );
    generationValues.response_format = () => format.input.value;
    generation.appendChild(format.wrap);
    content.appendChild(generation);

    if (model) {
      content.appendChild(
        el("p", "muted", "Trạng thái key: " + (KEY_LABELS[model.key] || model.key))
      );
    }

    content.appendChild(
      actions([
        button(
          "Lưu model",
          "button",
          async () => {
            const paramPayload = {};
            Object.keys(paramsValues).forEach((field) => {
              const value = paramsValues[field]();
              if (value === "" || value === false) {
                return;
              }
              paramPayload[field] =
                field === "fallback_models"
                  ? String(value)
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean)
                  : value;
            });
            const generationPayload = {};
            Object.keys(generationValues).forEach((field) => {
              const value = generationValues[field]();
              if (value === "") {
                return;
              }
              generationPayload[field] = value;
            });
            try {
              const data = await request("/api/ai-config/model", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  provider: provider.name,
                  id: id.input.value.trim(),
                  model: modelName.input.value.trim(),
                  params: paramPayload,
                  generation: generationPayload,
                  api_key: key.input.value.trim() || null,
                  create: state.creatingModel,
                }),
              });
              showError("");
              applyConfig(
                data.config,
                provider.name,
                id.input.value.trim()
              );
            } catch (exc) {
              showError(exc.message);
            }
          }
        ),
        model && model.source === "local" && !model.is_default
          ? confirmButton(
              "Xoá model",
              async () => {
                try {
                  const data = await request(
                    "/api/ai-config/model?provider=" +
                      encodeURIComponent(provider.name) +
                      "&id=" +
                      encodeURIComponent(model.id),
                    { method: "DELETE" }
                  );
                  showError("");
                  applyConfig(data.config, provider.name, "");
                } catch (exc) {
                  showError(exc.message);
                }
              }
            )
          : null,
        state.creatingModel
          ? button("Huỷ", "button secondary", () => {
              state.creatingModel = false;
              render();
            })
          : null,
      ])
    );
    return node;
  }

  function render() {
    if (!body || !state.payload) {
      return;
    }
    body.replaceChildren(renderDefaults(), renderProvider(), renderModel());
  }

  async function loadConfig() {
    showError("");
    if (body) {
      body.innerHTML = '<p class="muted">Đang tải...</p>';
    }
    try {
      const data = await request("/api/ai-config");
      state.payload = data;
      state.defaultProvider = data.default_provider;
      state.defaultModel = data.default_model;
      const provider = data.providers[0] || null;
      state.provider = provider ? provider.name : "";
      state.model =
        provider && provider.models[0] ? provider.models[0].id : "";
      state.creatingProvider = false;
      state.creatingModel = false;
      render();
    } catch (exc) {
      if (body) {
        body.innerHTML = "";
      }
      showError(exc.message);
    }
  }

  init({
    trigger: "[data-ai-config]",
    overlay: "[data-ai-config-overlay]",
    dialog: "[data-ai-config-dialog]",
    close: "[data-ai-config-close]",
    bodyClass: "ai-config-open",
    onOpen: loadConfig,
  });
})();
