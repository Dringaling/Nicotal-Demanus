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
