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
  const root = document.getElementById("tag-input");
  if (!root) {
    return;
  }

  const entry = document.getElementById("tag-entry");
  const chips = document.getElementById("tag-chips");
  const hidden = document.getElementById("tags-hidden");
  let values = (hidden.value || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

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
      });
      chip.appendChild(remove);
      chips.appendChild(chip);
    });
    hidden.value = values.join(",");
  }

  function add(value) {
    const tag = value.trim().replace(/\s+/g, " ");
    if (!tag) {
      return;
    }
    if (!values.some((item) => item.toLowerCase() === tag.toLowerCase())) {
      values.push(tag);
    }
    entry.value = "";
    render();
  }

  entry.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      add(entry.value);
    }
  });
  entry.addEventListener("blur", () => {
    if (entry.value.trim()) {
      add(entry.value);
    }
  });
  render();
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
    });
  });
})();

(function () {
  document.querySelectorAll("[data-tag-editor]").forEach((form) => {
    const hidden = form.querySelector('input[name="tags"]');
    const chips = form.querySelector("[data-tag-chips]");
    const entry = form.querySelector(".tag-entry");
    if (!hidden || !chips || !entry) {
      return;
    }

    let values = (hidden.value || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    let submitted = false;

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
          save();
        });
        chip.appendChild(remove);
        chips.appendChild(chip);
      });
      hidden.value = values.join(",");
    }

    function save() {
      if (submitted) {
        return;
      }
      submitted = true;
      form.submit();
    }

    function add(value) {
      const tag = value.trim().replace(/\s+/g, " ");
      if (!tag) {
        return false;
      }
      if (!values.some((item) => item.toLowerCase() === tag.toLowerCase())) {
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
          save();
        }
      }
    });
    entry.addEventListener("blur", () => {
      if (entry.value.trim() && add(entry.value)) {
        save();
      }
    });
    form.addEventListener("submit", () => {
      submitted = true;
    });
    render();
  });
})();
