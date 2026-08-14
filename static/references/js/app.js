document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector("[data-menu-toggle]");
  const menu = document.querySelector("[data-menu]");
  if (toggle && menu) {
    toggle.addEventListener("click", () => {
      const isOpen = menu.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(isOpen));
    });
  }

  document.querySelectorAll("[data-dismiss]").forEach((button) => {
    button.addEventListener("click", () => button.closest(".message")?.remove());
  });

  document.querySelectorAll("[data-select-all]").forEach((control) => {
    control.addEventListener("change", () => {
      const selector = control.dataset.selectAll;
      document.querySelectorAll(selector).forEach((checkbox) => {
        checkbox.checked = control.checked;
      });
    });
  });

  const copyButton = document.querySelector("[data-copy-list]");
  if (copyButton) {
    copyButton.addEventListener("click", async () => {
      const citations = [...document.querySelectorAll("[data-citation]")]
        .map((node) => node.innerText.trim())
        .filter(Boolean)
        .join("\n\n");
      try {
        await navigator.clipboard.writeText(citations);
        const original = copyButton.innerText;
        copyButton.innerText = "Lista copiada";
        copyButton.classList.add("is-success");
        window.setTimeout(() => {
          copyButton.innerText = original;
          copyButton.classList.remove("is-success");
        }, 1800);
      } catch (_) {
        window.alert("Não foi possível copiar automaticamente. Selecione o texto e copie manualmente.");
      }
    });
  }

  const printButton = document.querySelector("[data-print-list]");
  if (printButton) {
    printButton.addEventListener("click", () => window.print());
  }

  const fileInput = document.querySelector("input[type='file'][multiple]");
  const fileCount = document.querySelector("[data-file-count]");
  if (fileInput && fileCount) {
    fileInput.addEventListener("change", () => {
      const count = fileInput.files.length;
      fileCount.textContent = count ? `${count} arquivo${count > 1 ? "s" : ""} selecionado${count > 1 ? "s" : ""}` : "Nenhum arquivo selecionado";
    });
  }
});
