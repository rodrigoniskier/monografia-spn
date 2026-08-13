(() => {
  "use strict";

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken(), ...(options.headers || {}) },
      ...options,
    });
    let data;
    try { data = await response.json(); } catch (_) { data = { ok: false, error: "O servidor retornou uma resposta inesperada." }; }
    if (!response.ok || data.ok === false) {
      const error = new Error(data.error || "Não foi possível concluir a operação.");
      error.code = data.code;
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function toast(message, type = "info") {
    const region = qs("#toast-region");
    if (!region) return;
    const item = document.createElement("div");
    item.className = `toast${type === "error" ? " toast--error" : ""}`;
    item.textContent = message;
    region.appendChild(item);
    window.setTimeout(() => item.remove(), 4200);
  }

  function updateWordCount(input) {
    const wrap = input.closest("[data-field-wrap], [data-section-card]");
    const output = wrap && qs("[data-word-count]", input.closest(".section-card__body") || wrap);
    if (!output) return;
    const words = input.value.trim().match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu) || [];
    output.textContent = String(words.length);
  }

  function setFieldState(input, state, label) {
    const container = input.closest(".editor-field, .section-card__body, .section-card__header");
    const stateNode = container && qs("[data-field-state]", container);
    if (stateNode) {
      stateNode.textContent = label;
      stateNode.classList.toggle("is-saving", state === "saving");
      stateNode.classList.toggle("is-error", state === "error");
    }
  }

  function updateCompletion(value) {
    if (value === undefined || value === null) return;
    qsa("[data-completion-bar]").forEach((bar) => { bar.style.width = `${value}%`; });
    qsa("[data-completion-text]").forEach((text) => { text.textContent = `${value}%`; });
  }

  const timers = new WeakMap();
  let activeSaves = 0;

  function globalSaveState(state, label) {
    const indicator = qs("[data-save-indicator]");
    if (!indicator) return;
    indicator.classList.toggle("is-saving", state === "saving");
    indicator.classList.toggle("is-error", state === "error");
    const text = qs("[data-save-text]", indicator);
    if (text) text.textContent = label;
  }

  async function saveElement(input) {
    const root = qs("[data-editor-root]");
    if (!root || !input) return null;
    const timer = timers.get(input);
    if (timer) window.clearTimeout(timer);
    const field = input.dataset.field || input.dataset.sectionField;
    if (!field) return null;
    let url = root.dataset.autosaveUrl;
    if (input.dataset.sectionField) {
      const card = input.closest("[data-section-card]");
      url = `/api/monografias/${root.dataset.workId}/secoes/${card.dataset.sectionId}/`;
    }
    activeSaves += 1;
    globalSaveState("saving", "Salvando…");
    setFieldState(input, "saving", "Salvando…");
    try {
      const data = await apiFetch(url, { method: "POST", body: JSON.stringify({ field, value: input.value }) });
      input.dataset.savedValue = input.value;
      setFieldState(input, "saved", "Salvo");
      updateCompletion(data.completion);
      return data;
    } catch (error) {
      setFieldState(input, "error", "Não salvo");
      globalSaveState("error", "Falha ao salvar");
      toast(error.message, "error");
      throw error;
    } finally {
      activeSaves = Math.max(0, activeSaves - 1);
      if (!activeSaves && !qs("[data-field-state].is-error")) globalSaveState("saved", "Progresso salvo");
    }
  }

  function initAutosave() {
    qsa("[data-autosave], [data-section-field]").forEach((input) => {
      input.dataset.savedValue = input.value;
      updateWordCount(input);
      input.addEventListener("input", () => {
        updateWordCount(input);
        setFieldState(input, "saving", "Alterado");
        const previous = timers.get(input);
        if (previous) window.clearTimeout(previous);
        timers.set(input, window.setTimeout(() => saveElement(input).catch(() => {}), 850));
      });
      input.addEventListener("blur", () => {
        if (input.value !== input.dataset.savedValue) saveElement(input).catch(() => {});
      });
    });
    window.addEventListener("beforeunload", (event) => {
      const dirty = qsa("[data-autosave], [data-section-field]").some((input) => input.value !== input.dataset.savedValue);
      if (dirty || activeSaves) { event.preventDefault(); event.returnValue = ""; }
    });
  }

  function initGuidance() {
    const button = qs("[data-guidance-toggle]");
    const card = qs("[data-guidance-card]");
    if (!button || !card) return;
    button.addEventListener("click", () => {
      const opening = card.hidden;
      card.hidden = !opening;
      button.setAttribute("aria-expanded", String(opening));
      button.lastChild.textContent = opening ? " Ocultar roteiro" : " Ver roteiro de revisão";
    });
  }

  function initSidebar() {
    qsa("[data-sidebar-open]").forEach((button) => button.addEventListener("click", () => document.body.classList.add("sidebar-open")));
    qsa("[data-sidebar-close]").forEach((button) => button.addEventListener("click", () => document.body.classList.remove("sidebar-open")));
  }

  function initCarousel() {
    const carousel = qs("[data-carousel]");
    if (!carousel) return;
    const slides = qsa("[data-carousel-slide]", carousel);
    const dots = qsa("[data-carousel-dot]", carousel);
    let index = 0;
    const show = (next) => {
      index = (next + slides.length) % slides.length;
      slides.forEach((slide, i) => {
        slide.classList.toggle("is-active", i === index);
        slide.setAttribute("aria-hidden", String(i !== index));
      });
      dots.forEach((dot, i) => dot.classList.toggle("is-active", i === index));
    };
    qsa("[data-carousel-next]", carousel).forEach((button) => button.addEventListener("click", () => show(index + 1)));
    qsa("[data-carousel-prev]", carousel).forEach((button) => button.addEventListener("click", () => show(index - 1)));
    dots.forEach((dot) => dot.addEventListener("click", () => show(Number(dot.dataset.carouselDot))));
    carousel.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight") show(index + 1);
      if (event.key === "ArrowLeft") show(index - 1);
    });
  }

  function initConfirmations() {
    qsa("form[data-confirm]").forEach((form) => form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    }));
  }

  function initSections() {
    const root = qs("[data-section-editor]");
    const editorRoot = qs("[data-editor-root]");
    if (!root || !editorRoot) return;
    root.addEventListener("click", async (event) => {
      const addButton = event.target.closest("[data-add-section]");
      if (addButton) {
        const parentId = addButton.dataset.parentId || null;
        const title = window.prompt(parentId ? "Título da nova subseção:" : "Título da nova seção:");
        if (!title || !title.trim()) return;
        addButton.disabled = true;
        try {
          await apiFetch(root.dataset.addUrl, { method: "POST", body: JSON.stringify({ parent_id: parentId, title: title.trim() }) });
          window.location.reload();
        } catch (error) { toast(error.message, "error"); addButton.disabled = false; }
        return;
      }
      const deleteButton = event.target.closest("[data-delete-section]");
      if (deleteButton) {
        const card = deleteButton.closest("[data-section-card]");
        if (!window.confirm("Excluir esta seção e todas as subseções dentro dela?")) return;
        try {
          const response = await apiFetch(`/api/monografias/${editorRoot.dataset.workId}/secoes/${card.dataset.sectionId}/excluir/`, { method: "POST", body: "{}" });
          card.remove(); updateCompletion(response.completion); toast("Seção excluída.");
        } catch (error) { toast(error.message, "error"); }
      }
    });
  }

  let activeRevision = null;

  function openAIDrawer() {
    const drawer = qs("[data-ai-drawer]");
    if (!drawer) return;
    drawer.classList.add("is-open");
    drawer.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeAIDrawer() {
    const drawer = qs("[data-ai-drawer]");
    if (!drawer) return;
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function renderAIResult(revision) {
    const drawer = qs("[data-ai-drawer]");
    qs("[data-ai-loading]", drawer).hidden = true;
    qs("[data-ai-result]", drawer).hidden = false;
    qs("[data-ai-actions]", drawer).hidden = false;
    qs("[data-ai-summary]", drawer).textContent = revision.summary;
    qs("[data-ai-proposed]", drawer).textContent = revision.proposed_text;
    const warnings = qs("[data-ai-warnings]", drawer);
    warnings.replaceChildren();
    (revision.warnings || []).forEach((warning) => {
      const item = document.createElement("div"); item.className = "ai-warning"; item.textContent = warning; warnings.appendChild(item);
    });
    const suggestions = qs("[data-ai-suggestions]", drawer);
    suggestions.replaceChildren();
    (revision.suggestions || []).forEach((suggestion) => {
      const card = document.createElement("article"); card.className = "suggestion";
      const head = document.createElement("div"); head.className = "suggestion__head";
      const category = document.createElement("strong"); category.textContent = suggestion.category;
      const priority = document.createElement("span"); priority.textContent = `prioridade ${suggestion.priority}`;
      head.append(category, priority);
      const reason = document.createElement("p"); reason.textContent = suggestion.reason;
      card.append(head, reason);
      if (suggestion.proposed_change) { const proposed = document.createElement("em"); proposed.textContent = `Sugestão: ${suggestion.proposed_change}`; card.appendChild(proposed); }
      suggestions.appendChild(card);
    });
    if (!revision.suggestions || !revision.suggestions.length) {
      const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "A revisão não identificou ajustes pontuais adicionais."; suggestions.appendChild(empty);
    }
  }

  function initAI() {
    const editor = qs("[data-editor-root]");
    const drawer = qs("[data-ai-drawer]");
    if (!editor || !drawer) return;
    qsa("[data-ai-close]", drawer).forEach((button) => button.addEventListener("click", closeAIDrawer));
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && drawer.classList.contains("is-open")) closeAIDrawer(); });
    qsa("[data-ai-trigger]").forEach((button) => button.addEventListener("click", async () => {
      if (editor.dataset.aiAvailable !== "true") { toast("A revisão ficará disponível quando a GEMINI_API_KEY for configurada no servidor.", "error"); return; }
      const targetType = button.dataset.targetType;
      const input = targetType === "section" ? qs("[data-section-field='content']", button.closest("[data-section-card]")) : qs(`#field-${CSS.escape(button.dataset.field)}`);
      if (!input || input.value.trim().length < 20) { toast("Escreva um pouco mais antes de solicitar a revisão.", "error"); return; }
      try {
        if (input.value !== input.dataset.savedValue) await saveElement(input);
      } catch (_) { return; }
      activeRevision = { input, data: null };
      qs("[data-ai-loading]", drawer).hidden = false;
      qs("[data-ai-result]", drawer).hidden = true;
      qs("[data-ai-actions]", drawer).hidden = true;
      openAIDrawer();
      const payload = targetType === "section" ? { target_type: "section", section_id: button.dataset.sectionId, action: "review" } : { target_type: "monograph", field: button.dataset.field, action: "review" };
      try {
        const response = await apiFetch(editor.dataset.aiUrl, { method: "POST", body: JSON.stringify(payload) });
        activeRevision.data = response.revision;
        renderAIResult(response.revision);
      } catch (error) {
        closeAIDrawer(); toast(error.message, "error");
      }
    }));
    const accept = qs("[data-ai-accept]", drawer);
    accept.addEventListener("click", async () => {
      if (!activeRevision || !activeRevision.data) return;
      accept.disabled = true;
      accept.textContent = "Aplicando…";
      try {
        const response = await apiFetch(activeRevision.data.accept_url, { method: "POST", body: "{}" });
        activeRevision.input.value = response.text;
        activeRevision.input.dataset.savedValue = response.text;
        updateWordCount(activeRevision.input);
        updateCompletion(response.completion);
        closeAIDrawer(); toast("Versão revisada aplicada. Você ainda pode editá-la livremente.");
      } catch (error) { toast(error.message, "error"); }
      finally { accept.disabled = false; accept.textContent = "Aceitar versão proposta"; }
    });
  }

  function resultCard(result, saveUrl) {
    const article = document.createElement("article"); article.className = "research-result";
    const meta = document.createElement("div"); meta.className = "research-result__meta";
    const type = document.createElement("span");
    const labels = { book: "Livro", article: "Artigo", chapter: "Capítulo", thesis: "Tese/Dissertação", other: "Publicação" };
    type.textContent = labels[result.source_type] || "Publicação";
    const provider = document.createElement("span"); provider.textContent = `${result.provider}${result.year ? ` · ${result.year}` : ""}`;
    meta.append(type, provider);
    const title = document.createElement("h3"); title.textContent = result.title;
    const authors = document.createElement("p"); authors.className = "research-result__authors"; authors.textContent = (result.authors || []).join("; ") || "Autoria não informada";
    const reference = document.createElement("p"); reference.className = "research-result__reference"; reference.textContent = result.reference;
    const actions = document.createElement("div"); actions.className = "research-result__actions";
    const link = document.createElement("a"); link.href = result.url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = "Abrir publicação ↗";
    const save = document.createElement("button"); save.className = "button button--outline button--small"; save.type = "button"; save.textContent = "Salvar referência";
    save.addEventListener("click", async () => {
      save.disabled = true; save.textContent = "Salvando…";
      try { await apiFetch(saveUrl, { method: "POST", body: JSON.stringify({ token: result.token }) }); save.textContent = "Referência salva ✓"; toast("Publicação adicionada às referências."); }
      catch (error) { save.disabled = false; save.textContent = "Salvar referência"; toast(error.message, "error"); }
    });
    actions.append(link, save); article.append(meta, title, authors, reference, actions); return article;
  }

  function initResearch() {
    const root = qs("[data-research-root]");
    if (!root) return;
    const form = qs("[data-research-form]", root);
    const status = qs("[data-research-status]", root);
    const results = qs("[data-research-results]", root);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const query = String(data.get("query") || "").trim();
      if (query.length < 3) { toast("Digite ao menos três caracteres para pesquisar.", "error"); return; }
      status.innerHTML = "";
      const loading = document.createElement("div"); loading.className = "research-loading"; loading.innerHTML = '<span class="spinner"></span><span>Consultando catálogos acadêmicos…</span>'; status.appendChild(loading);
      results.replaceChildren();
      try {
        const response = await apiFetch(root.dataset.searchUrl, { method: "POST", body: JSON.stringify({ query, mode: data.get("mode") }) });
        status.replaceChildren();
        (response.warnings || []).forEach((message) => { const warning = document.createElement("div"); warning.className = "research-warning"; warning.textContent = message; status.appendChild(warning); });
        if (!response.results.length) {
          const empty = document.createElement("div"); empty.className = "research-empty"; empty.innerHTML = "<h2>Nenhum resultado suficientemente relacionado</h2><p>Tente termos mais específicos, outro idioma, sobrenome de autor ou título de uma obra.</p>"; status.appendChild(empty); return;
        }
        response.results.forEach((result) => results.appendChild(resultCard(result, root.dataset.saveUrl)));
      } catch (error) {
        status.replaceChildren(); const warning = document.createElement("div"); warning.className = "research-warning"; warning.textContent = error.message; status.appendChild(warning);
      }
    });
  }

  function initReferences() {
    qsa("[data-copy]").forEach((button) => button.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(button.dataset.copy); toast("Citação copiada."); }
      catch (_) { toast("Não foi possível copiar automaticamente.", "error"); }
    }));
    qsa("[data-delete-publication]").forEach((button) => button.addEventListener("click", async () => {
      if (!window.confirm("Remover esta publicação das referências salvas?")) return;
      try { await apiFetch(button.dataset.deleteUrl, { method: "POST", body: "{}" }); button.closest("[data-publication-id]").remove(); toast("Referência removida."); }
      catch (error) { toast(error.message, "error"); }
    }));
  }

  document.addEventListener("DOMContentLoaded", () => {
    initCarousel(); initSidebar(); initGuidance(); initAutosave(); initConfirmations(); initSections(); initAI(); initResearch(); initReferences();
    window.setTimeout(() => qsa(".flash").forEach((item) => item.remove()), 5200);
  });
})();
