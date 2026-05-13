/**
 * todo.js — task list with active/done filters, persisted in sessionStorage.
 */
(function () {
  let todos = JSON.parse(sessionStorage.getItem("nova_todos") || "[]");
  let filter = "all";

  function saveTodos() {
    sessionStorage.setItem("nova_todos", JSON.stringify(todos));
  }

  function escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

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

      const date = new Date(todo.created);
      const dateStr = date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });

      item.innerHTML = `
        <button class="todo-check" data-action="toggle" data-idx="${idx}">
          <svg viewBox="0 0 12 12"><polyline points="1.5,6 5,9.5 10.5,2.5" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <span class="todo-text">${escHtml(todo.text)}</span>
        <span class="todo-meta">${dateStr}</span>
        <button class="todo-del" data-action="delete" data-idx="${idx}" title="Delete">
          <svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>
        </button>
      `;
      list.appendChild(item);
    });
  }

  function addTodo() {
    const input = document.getElementById("todoInput");
    const text = input.value.trim();
    if (!text) return;
    todos.unshift({ text, done: false, created: Date.now() });
    saveTodos();
    renderTodos();
    input.value = "";
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

  // Expose for inline onclick handlers in dashboard.html
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

    // Event delegation for toggle/delete buttons (cleaner than per-row inline onclick)
    const list = document.getElementById("todoList");
    if (list) {
      list.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-action]");
        if (!btn) return;
        const idx = parseInt(btn.dataset.idx, 10);
        if (btn.dataset.action === "toggle") toggleTodo(idx);
        else if (btn.dataset.action === "delete") deleteTodo(idx);
      });
    }

    renderTodos();
  });
})();
