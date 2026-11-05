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
