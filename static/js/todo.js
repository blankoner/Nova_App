/**
 * todo.js — task list with active/done filters, due dates, and drag-and-drop reorder.
 * Persisted in sessionStorage. Each todo: { text, done, created, due (ISO|null) }.
 * Array order = display order. Manual reorder rewrites the array.
 */
(function () {
  let todos = JSON.parse(sessionStorage.getItem("nova_todos") || "[]");
  let filter = "all";
  let dragSrcIdx = null;  // index in the full `todos` array, not the visible slice

  function saveTodos() {
    sessionStorage.setItem("nova_todos", JSON.stringify(todos));
  }

  function escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ── Due-date helpers ─────────────────────────────────────────────────────
  function formatDue(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    const now = new Date();
    const sameYear = d.getFullYear() === now.getFullYear();
    return d.toLocaleString("en-GB", {
      day: "numeric",
      month: "short",
      year: sameYear ? undefined : "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function dueClass(iso, done) {
    if (!iso || done) return "";
    const d = new Date(iso).getTime();
    if (isNaN(d)) return "";
    const now = Date.now();
    if (d < now) return "due-overdue";
    if (d - now < 24 * 60 * 60 * 1000) return "due-soon";
    return "";
  }

  // ── Render ───────────────────────────────────────────────────────────────
  function renderTodos() {
    const list = document.getElementById("todoList");
    const active = todos.filter(t => !t.done).length;
    document.getElementById("todoCount").textContent =
      active === 0 ? "All done ✓" : active + " left";

    const visible = todos.filter(t => {
      if (filter === "active") return !t.done;
      if (filter === "done")   return t.done;
      return true;
    });

    if (visible.length === 0) {
      list.innerHTML = `<div class="empty-state">
        <span class="emoji">${filter === "done" ? "🏁" : "✨"}</span>
        ${filter === "done" ? "Nothing completed yet." : "No tasks yet — add one above!"}
      </div>`;
      return;
    }

    list.innerHTML = "";
    visible.forEach((todo) => {
      const idx = todos.indexOf(todo);
      const item = document.createElement("div");
      item.className = "todo-item" + (todo.done ? " done" : "");
      // Only allow drag in the "All" filter — reordering inside a filtered view
      // would produce surprising results since hidden items keep their positions.
      const draggable = filter === "all" && !todo.done;
      item.draggable = draggable;
      item.dataset.idx = idx;

      const dueLabel = formatDue(todo.due);
      const dueCls = dueClass(todo.due, todo.done);

      item.innerHTML = `
        ${draggable ? `<span class="todo-grip" title="Drag to reorder">
          <svg viewBox="0 0 12 16"><circle cx="3" cy="3" r="1.3"/><circle cx="9" cy="3" r="1.3"/><circle cx="3" cy="8" r="1.3"/><circle cx="9" cy="8" r="1.3"/><circle cx="3" cy="13" r="1.3"/><circle cx="9" cy="13" r="1.3"/></svg>
        </span>` : `<span class="todo-grip-placeholder"></span>`}
        <button class="todo-check" data-action="toggle" data-idx="${idx}">
          <svg viewBox="0 0 12 12"><polyline points="1.5,6 5,9.5 10.5,2.5" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <div class="todo-body">
          <span class="todo-text">${escHtml(todo.text)}</span>
          ${dueLabel ? `<span class="todo-due ${dueCls}">
            <svg viewBox="0 0 16 16" width="10" height="10"><path d="M3 1v2M13 1v2M2 6h12M3 3h10a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
            ${dueLabel}
          </span>` : ""}
        </div>
        <button class="todo-del" data-action="delete" data-idx="${idx}" title="Delete">
          <svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>
        </button>
      `;
      list.appendChild(item);
    });
  }

  // ── CRUD ─────────────────────────────────────────────────────────────────
  function addTodo() {
    const input = document.getElementById("todoInput");
    const dueInput = document.getElementById("todoDueInput");
    const text = input.value.trim();
    if (!text) return;
    const due = dueInput && dueInput.value ? new Date(dueInput.value).toISOString() : null;
    todos.unshift({ text, done: false, created: Date.now(), due });
    saveTodos();
    renderTodos();
    input.value = "";
    if (dueInput) dueInput.value = "";
    input.focus();
  }

  function toggleTodo(idx) {
    todos[idx].done = !todos[idx].done;
    saveTodos();
    renderTodos();
  }

  function deleteTodo(idx) {
    todos.splice(idx, 1);
    saveTodos();
    renderTodos();
  }

  function setFilter(f, btn) {
    filter = f;
    document.querySelectorAll(".filter-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    renderTodos();
  }

  // ── Drag-and-drop reorder ────────────────────────────────────────────────
  // The array `todos` IS the ordering. moveItem(srcIdx, dstIdx) splices.
  function moveItem(srcIdx, dstIdx) {
    if (srcIdx === dstIdx || srcIdx == null || dstIdx == null) return;
    const [moved] = todos.splice(srcIdx, 1);
    // After removing src, indices >= srcIdx shifted down by one
    if (dstIdx > srcIdx) dstIdx--;
    todos.splice(dstIdx, 0, moved);
    saveTodos();
    renderTodos();
  }

  function attachDragHandlers(list) {
    list.addEventListener("dragstart", (e) => {
      const item = e.target.closest(".todo-item");
      if (!item || !item.draggable) return;
      dragSrcIdx = parseInt(item.dataset.idx, 10);
      item.classList.add("dragging");
      // Required for Firefox to start a drag
      e.dataTransfer.effectAllowed = "move";
      try { e.dataTransfer.setData("text/plain", String(dragSrcIdx)); } catch (_) {}
    });

    list.addEventListener("dragend", (e) => {
      const item = e.target.closest(".todo-item");
      if (item) item.classList.remove("dragging");
      list.querySelectorAll(".drop-above, .drop-below")
          .forEach(el => el.classList.remove("drop-above", "drop-below"));
      dragSrcIdx = null;
    });

    list.addEventListener("dragover", (e) => {
      e.preventDefault();  // allow drop
      e.dataTransfer.dropEffect = "move";
      const target = e.target.closest(".todo-item");
      list.querySelectorAll(".drop-above, .drop-below")
          .forEach(el => el.classList.remove("drop-above", "drop-below"));
      if (!target || target.classList.contains("dragging")) return;
      const rect = target.getBoundingClientRect();
      const isAbove = (e.clientY - rect.top) < rect.height / 2;
      target.classList.add(isAbove ? "drop-above" : "drop-below");
    });

    list.addEventListener("drop", (e) => {
      e.preventDefault();
      const target = e.target.closest(".todo-item");
      if (!target || dragSrcIdx == null) return;
      const dstIdxRaw = parseInt(target.dataset.idx, 10);
      const rect = target.getBoundingClientRect();
      const isAbove = (e.clientY - rect.top) < rect.height / 2;
      // Convert "above this row" / "below this row" into an array insert index
      const dstIdx = isAbove ? dstIdxRaw : dstIdxRaw + 1;
      moveItem(dragSrcIdx, dstIdx);
      dragSrcIdx = null;
    });

    // ── Touch fallback ──
    // HTML5 drag events don't fire on most mobile browsers, so we implement
    // a minimal touch-driven version that mirrors the mouse behaviour.
    let touchSrcIdx = null;
    let touchDragging = null;

    list.addEventListener("touchstart", (e) => {
      const grip = e.target.closest(".todo-grip");
      if (!grip) return;
      const item = grip.closest(".todo-item");
      if (!item || !item.draggable) return;
      touchSrcIdx = parseInt(item.dataset.idx, 10);
      touchDragging = item;
      item.classList.add("dragging");
    }, { passive: true });

    list.addEventListener("touchmove", (e) => {
      if (!touchDragging) return;
      e.preventDefault();  // suppress scroll while dragging
      const t = e.touches[0];
      const el = document.elementFromPoint(t.clientX, t.clientY);
      const target = el ? el.closest(".todo-item") : null;
      list.querySelectorAll(".drop-above, .drop-below")
          .forEach(x => x.classList.remove("drop-above", "drop-below"));
      if (!target || target === touchDragging) return;
      const rect = target.getBoundingClientRect();
      const isAbove = (t.clientY - rect.top) < rect.height / 2;
      target.classList.add(isAbove ? "drop-above" : "drop-below");
    }, { passive: false });

    list.addEventListener("touchend", () => {
      if (!touchDragging) return;
      const marker = list.querySelector(".drop-above, .drop-below");
      if (marker) {
        const dstIdxRaw = parseInt(marker.dataset.idx, 10);
        const dstIdx = marker.classList.contains("drop-above") ? dstIdxRaw : dstIdxRaw + 1;
        moveItem(touchSrcIdx, dstIdx);
      }
      touchDragging.classList.remove("dragging");
      list.querySelectorAll(".drop-above, .drop-below")
          .forEach(x => x.classList.remove("drop-above", "drop-below"));
      touchDragging = null;
      touchSrcIdx = null;
    });
  }

  // ── Expose for inline onclick handlers in dashboard.html ────────────────
  window.addTodo = addTodo;
  window.toggleTodo = toggleTodo;
  window.deleteTodo = deleteTodo;
  window.setFilter = setFilter;

  document.addEventListener("DOMContentLoaded", () => {
    const todoInput = document.getElementById("todoInput");
    if (todoInput) {
      todoInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") addTodo();
      });
    }

    const list = document.getElementById("todoList");
    if (list) {
      // Event delegation for toggle/delete buttons
      list.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-action]");
        if (!btn) return;
        const idx = parseInt(btn.dataset.idx, 10);
        if (btn.dataset.action === "toggle") toggleTodo(idx);
        else if (btn.dataset.action === "delete") deleteTodo(idx);
      });
      attachDragHandlers(list);
    }

    renderTodos();
  });
})();
