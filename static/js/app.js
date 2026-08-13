(() => {
  "use strict";

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const footnoteRegex = () => /\[\[FN:([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\]\]/gi;

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
    const readable = input.value.replace(footnoteRegex(), " ");
    const words = readable.trim().match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu) || [];
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
      applySequenceMap(data.sequence_map);
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

  function scheduleSave(input) {
    updateWordCount(input);
    setFieldState(input, "saving", "Alterado");
    const previous = timers.get(input);
    if (previous) window.clearTimeout(previous);
    timers.set(input, window.setTimeout(() => saveElement(input).catch(() => {}), 850));
  }

  function initAutosave() {
    qsa("[data-autosave], [data-section-field]").forEach((input) => {
      input.dataset.savedValue = input.value;
      updateWordCount(input);
      input.addEventListener("input", () => scheduleSave(input));
      input.addEventListener("blur", () => {
        if (input.value !== input.dataset.savedValue) saveElement(input).catch(() => {});
      });
    });
    window.addEventListener("beforeunload", (event) => {
      const dirty = qsa("[data-autosave], [data-section-field], [data-citation-note-input]").some((input) => input.value !== input.dataset.savedValue);
      if (dirty || activeSaves) { event.preventDefault(); event.returnValue = ""; }
    });
  }

  const citationNotes = new Map();
  const citationNoteTimers = new WeakMap();
  let citationOptions = [];
  let activeCitation = null;
  const selectionByEditor = new WeakMap();

  function readJSONScript(id) {
    const node = qs(`#${CSS.escape(id)}`);
    if (!node) return [];
    try { return JSON.parse(node.textContent || "[]"); }
    catch (_) { return []; }
  }

  function serializeCitationNode(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.nodeValue || "";
    if (node.nodeType !== Node.ELEMENT_NODE && node.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return "";
    if (node.nodeType === Node.ELEMENT_NODE) {
      if (node.matches("sup[data-citation-marker]")) return `[[FN:${node.dataset.citationMarker}]]`;
      if (node.tagName === "BR") return "\n";
    }
    let value = "";
    node.childNodes.forEach((child) => { value += serializeCitationNode(child); });
    if (node.nodeType === Node.ELEMENT_NODE && ["DIV", "P"].includes(node.tagName) && node.nextSibling && !value.endsWith("\n")) value += "\n";
    return value;
  }

  function noteForMarker(marker) {
    return citationNotes.get(String(marker || "").toLowerCase());
  }

  function renderCanonical(container, text) {
    container.replaceChildren();
    const regex = footnoteRegex();
    let cursor = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > cursor) container.appendChild(document.createTextNode(text.slice(cursor, match.index)));
      const note = noteForMarker(match[1]);
      const marker = document.createElement("sup");
      marker.className = "citation-marker";
      marker.dataset.citationMarker = match[1].toLowerCase();
      marker.contentEditable = "false";
      marker.textContent = note ? String(note.sequence) : "?";
      marker.title = note ? note.text : "Nota não encontrada";
      marker.setAttribute("aria-label", note ? `Nota de rodapé ${note.sequence}` : "Nota de rodapé inválida");
      container.appendChild(marker);
      cursor = regex.lastIndex;
    }
    if (cursor < text.length) container.appendChild(document.createTextNode(text.slice(cursor)));
  }

  function citationEditorFor(source) {
    return qs(`[data-citation-editor][data-source-id="${CSS.escape(source.id)}"]`);
  }

  function renderCitationEditor(source) {
    const editor = citationEditorFor(source);
    if (!editor) return;
    renderCanonical(editor, source.value);
  }

  function captureCitationSelection(editor) {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (editor.contains(range.commonAncestorContainer)) selectionByEditor.set(editor, range.cloneRange());
  }

  function setCaretAtEnd(editor) {
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    selectionByEditor.set(editor, range.cloneRange());
  }

  function insertPlainText(editor, text) {
    editor.focus();
    const selection = window.getSelection();
    let range = selection && selection.rangeCount ? selection.getRangeAt(0) : null;
    if (!range || !editor.contains(range.commonAncestorContainer)) {
      setCaretAtEnd(editor);
      range = window.getSelection().getRangeAt(0);
    }
    range.deleteContents();
    const node = document.createTextNode(String(text || "").replace(/\r\n?/g, "\n"));
    range.insertNode(node);
    range.setStartAfter(node);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    editor.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function syncCitationSource(editor, shouldSave = true) {
    const source = qs(`#${CSS.escape(editor.dataset.sourceId)}`);
    if (!source) return null;
    source.value = serializeCitationNode(editor);
    updateWordCount(source);
    renderCitationNotes(source);
    if (shouldSave) scheduleSave(source);
    return source;
  }

  function canonicalBeforeCaret(editor) {
    let range = selectionByEditor.get(editor);
    if (!range || !editor.contains(range.endContainer)) {
      return serializeCitationNode(editor);
    }
    const before = document.createRange();
    before.selectNodeContents(editor);
    before.setEnd(range.endContainer, range.endOffset);
    return serializeCitationNode(before.cloneContents());
  }

  function applySequenceMap(sequenceMap) {
    if (!sequenceMap) return;
    let changed = false;
    const activeMarkers = new Set(Object.keys(sequenceMap).map((marker) => marker.toLowerCase()));
    Array.from(citationNotes.keys()).forEach((marker) => {
      if (!activeMarkers.has(marker)) { citationNotes.delete(marker); changed = true; }
    });
    Object.entries(sequenceMap).forEach(([marker, sequence]) => {
      const note = noteForMarker(marker);
      if (note && note.sequence !== Number(sequence)) {
        note.sequence = Number(sequence);
        changed = true;
      }
    });
    if (!changed) return;
    qsa("[data-citation-source]").forEach((source) => {
      renderCitationEditor(source);
      renderCitationNotes(source);
    });
  }

  function renderCitationNotes(source) {
    const panel = qs(`[data-citation-notes][data-source-id="${CSS.escape(source.id)}"]`);
    if (!panel) return;
    const list = qs("[data-citation-note-list]", panel);
    const markers = [];
    const seen = new Set();
    for (const match of source.value.matchAll(footnoteRegex())) {
      const marker = match[1].toLowerCase();
      if (!seen.has(marker)) { seen.add(marker); markers.push(marker); }
    }
    list.replaceChildren();
    if (!markers.length) {
      const empty = document.createElement("p");
      empty.className = "citation-notes__empty";
      empty.textContent = "Nenhuma referência inserida neste conteúdo.";
      list.appendChild(empty);
      return;
    }
    markers.forEach((marker) => {
      const note = noteForMarker(marker);
      if (!note) return;
      const row = document.createElement("article");
      row.className = "citation-note-row";
      row.dataset.citationNoteId = note.id;
      const number = document.createElement("sup");
      number.textContent = String(note.sequence);
      const text = document.createElement("textarea");
      text.rows = 2;
      text.value = note.text;
      text.dataset.savedValue = note.text;
      text.dataset.citationNoteInput = "";
      text.setAttribute("aria-label", `Texto da nota ${note.sequence}`);
      const saveNoteText = async () => {
        if (text.dataset.saving === "true") return;
        const value = text.value.trim();
        if (!value || value === text.dataset.savedValue) return;
        const timer = citationNoteTimers.get(text);
        if (timer) window.clearTimeout(timer);
        text.dataset.saving = "true";
        text.disabled = true;
        activeSaves += 1;
        globalSaveState("saving", "Salvando nota…");
        let failed = false;
        try {
          const response = await apiFetch(note.update_url, { method: "POST", body: JSON.stringify({ text: value }) });
          Object.assign(note, response.note);
          citationNotes.set(marker, note);
          text.dataset.savedValue = note.text;
          renderCitationEditor(source);
        } catch (error) {
          failed = true;
          globalSaveState("error", "Falha ao salvar nota");
          toast(error.message, "error");
        } finally {
          delete text.dataset.saving;
          text.disabled = false;
          activeSaves = Math.max(0, activeSaves - 1);
          if (!activeSaves && !failed) globalSaveState("saved", "Progresso salvo");
        }
      };
      text.addEventListener("input", () => {
        globalSaveState("saving", "Nota alterada");
        const prior = citationNoteTimers.get(text);
        if (prior) window.clearTimeout(prior);
        citationNoteTimers.set(text, window.setTimeout(() => saveNoteText(), 850));
      });
      text.addEventListener("blur", () => saveNoteText());
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "citation-note-row__remove";
      remove.textContent = "Remover";
      remove.addEventListener("click", async () => {
        if (!window.confirm(`Remover a nota ${note.sequence} deste texto?`)) return;
        remove.disabled = true;
        try {
          const response = await apiFetch(note.delete_url, { method: "POST", body: "{}" });
          citationNotes.delete(marker);
          source.value = response.text;
          source.dataset.savedValue = response.text;
          renderCitationEditor(source);
          renderCitationNotes(source);
          applySequenceMap(response.sequence_map);
          updateWordCount(source);
          updateCompletion(response.completion);
          toast("Nota removida.");
        } catch (error) { remove.disabled = false; toast(error.message, "error"); }
      });
      row.append(number, text, remove);
      list.appendChild(row);
    });
  }

  function closeReferencePicker() {
    const picker = qs("[data-reference-picker]");
    if (!picker) return;
    picker.classList.remove("is-open");
    picker.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    const trigger = activeCitation && activeCitation.trigger;
    activeCitation = null;
    if (trigger) trigger.focus();
  }

  function renderReferenceChoices(filter = "") {
    const picker = qs("[data-reference-picker]");
    if (!picker) return;
    const list = qs("[data-reference-picker-list]", picker);
    const empty = qs("[data-reference-picker-empty]", picker);
    const query = filter.trim().toLocaleLowerCase("pt-BR");
    const matches = citationOptions.filter((option) => `${option.label} ${option.meta}`.toLocaleLowerCase("pt-BR").includes(query));
    list.replaceChildren();
    matches.forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "reference-choice";
      const meta = document.createElement("span");
      meta.textContent = option.meta;
      const label = document.createElement("strong");
      label.textContent = option.label;
      button.append(meta, label);
      button.addEventListener("click", async () => {
        if (!activeCitation) return;
        const root = qs("[data-editor-root]");
        const locator = qs("[data-reference-picker-locator]", picker).value.trim();
        qsa("button", list).forEach((item) => { item.disabled = true; });
        try {
          const response = await apiFetch(root.dataset.citationUrl, {
            method: "POST",
            body: JSON.stringify({
              target_key: activeCitation.source.dataset.targetKey,
              current_text: activeCitation.source.value,
              before_text: activeCitation.beforeText,
              source_kind: option.kind,
              source_id: option.id,
              locator,
            }),
          });
          const note = response.note;
          citationNotes.set(note.marker.toLowerCase(), note);
          applySequenceMap(response.sequence_map);
          activeCitation.source.value = response.text;
          activeCitation.source.dataset.savedValue = response.text;
          renderCitationEditor(activeCitation.source);
          renderCitationNotes(activeCitation.source);
          updateWordCount(activeCitation.source);
          updateCompletion(response.completion);
          closeReferencePicker();
          toast(`Referência incluída como nota ${note.sequence}.`);
        } catch (error) {
          qsa("button", list).forEach((item) => { item.disabled = false; });
          toast(error.message, "error");
        }
      });
      list.appendChild(button);
    });
    empty.hidden = matches.length > 0;
    list.hidden = matches.length === 0;
    const strong = qs("strong", empty);
    if (strong) strong.textContent = citationOptions.length ? "Nenhuma correspondência encontrada." : "Nenhuma referência disponível.";
  }

  function openReferencePicker(context) {
    const picker = qs("[data-reference-picker]");
    if (!picker) return;
    activeCitation = context;
    const search = qs("[data-reference-picker-search]", picker);
    const locator = qs("[data-reference-picker-locator]", picker);
    search.value = "";
    locator.value = "";
    renderReferenceChoices();
    picker.classList.add("is-open");
    picker.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    window.setTimeout(() => search.focus(), 0);
  }

  function initCitations() {
    citationOptions = readJSONScript("citation-reference-options");
    readJSONScript("citation-notes-data").forEach((note) => citationNotes.set(note.marker.toLowerCase(), note));
    qsa("[data-citation-editor]").forEach((editor) => {
      const source = qs(`#${CSS.escape(editor.dataset.sourceId)}`);
      if (!source) return;
      const rows = Math.min(18, Math.max(3, Number(editor.dataset.rows || 6)));
      editor.style.minHeight = `${(rows * 1.72).toFixed(2)}em`;
      renderCitationEditor(source);
      renderCitationNotes(source);
      ["focus", "keyup", "mouseup"].forEach((name) => editor.addEventListener(name, () => captureCitationSelection(editor)));
      editor.addEventListener("input", () => { syncCitationSource(editor); captureCitationSelection(editor); });
      editor.addEventListener("beforeinput", (event) => {
        if (["insertParagraph", "insertLineBreak"].includes(event.inputType)) {
          event.preventDefault();
          insertPlainText(editor, "\n");
        }
      });
      editor.addEventListener("paste", (event) => {
        event.preventDefault();
        insertPlainText(editor, event.clipboardData.getData("text/plain"));
      });
      editor.addEventListener("drop", (event) => event.preventDefault());
    });
    qsa("[data-citation-trigger]").forEach((button) => {
      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", async () => {
        const source = qs(`#${CSS.escape(button.dataset.sourceId)}`);
        const editor = source && citationEditorFor(source);
        if (!source || !editor) return;
        syncCitationSource(editor, false);
        const beforeText = canonicalBeforeCaret(editor);
        try {
          if (source.value !== source.dataset.savedValue) await saveElement(source);
        } catch (_) { return; }
        openReferencePicker({ source, editor, beforeText, trigger: button });
      });
    });
    const picker = qs("[data-reference-picker]");
    if (picker) {
      qsa("[data-reference-picker-close]", picker).forEach((button) => button.addEventListener("click", closeReferencePicker));
      qs("[data-reference-picker-search]", picker).addEventListener("input", (event) => renderReferenceChoices(event.target.value));
      document.addEventListener("keydown", (event) => { if (event.key === "Escape" && picker.classList.contains("is-open")) closeReferencePicker(); });
    }
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
    renderCanonical(qs("[data-ai-proposed]", drawer), revision.proposed_text);
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
        renderCitationEditor(activeRevision.input);
        renderCitationNotes(activeRevision.input);
        updateWordCount(activeRevision.input);
        updateCompletion(response.completion);
        applySequenceMap(response.sequence_map);
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
    qsa("[data-delete-imported-reference]").forEach((button) => button.addEventListener("click", async () => {
      if (!window.confirm("Remover esta referência importada da biblioteca? As notas já inseridas serão preservadas.")) return;
      try { await apiFetch(button.dataset.deleteUrl, { method: "POST", body: "{}" }); button.closest("[data-imported-reference-id]").remove(); toast("Referência importada removida."); }
      catch (error) { toast(error.message, "error"); }
    }));
  }

  document.addEventListener("DOMContentLoaded", () => {
    initCarousel(); initSidebar(); initGuidance(); initCitations(); initAutosave(); initConfirmations(); initSections(); initAI(); initResearch(); initReferences();
    window.setTimeout(() => qsa(".flash").forEach((item) => item.remove()), 5200);
  });
})();
