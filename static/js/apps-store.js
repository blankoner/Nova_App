/**
 * apps-store.js — shared client for persisting dashboard mini-app state.
 *
 * The to-do list, journal and pomodoro settings used to live in
 * sessionStorage, which is wiped when the tab closes. They now persist on the
 * backend (SQLite) via /api/apps, so nothing is lost between sessions.
 *
 * Exposes window.Nova.appsStore with:
 *   load()              → Promise<{todos, journal, pomodoro}>  (full app state)
 *   save(partial)       → debounced save of a partial update, e.g.
 *                         save({todos: [...]}) or save({journal: {...}})
 *   saveNow(partial)    → immediate (non-debounced) save, returns a Promise
 *
 * Saves are debounced (250 ms) and coalesced: rapid edits to the to-do list
 * become a single request carrying the latest state. Different keys sent
 * before a flush are merged, so the to-do list and journal don't overwrite
 * each other.
 */
(function () {
  window.Nova = window.Nova || {};

  const DEBOUNCE_MS = 250;
  let pending = {};        // accumulated partial update waiting to be flushed
  let timer = null;

  async function flush() {
    timer = null;
    const payload = pending;
    pending = {};
    if (Object.keys(payload).length === 0) return;
    try {
      await fetch("/api/apps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      // A failed save shouldn't break the UI — the in-memory state is still
      // correct, and the next save will retry with fresh data.
      console.error("apps-store: save failed", e);
    }
  }

  function save(partial) {
    // Merge into whatever is already waiting, so we never lose a key.
    Object.assign(pending, partial || {});
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, DEBOUNCE_MS);
  }

  async function saveNow(partial) {
    Object.assign(pending, partial || {});
    if (timer) { clearTimeout(timer); timer = null; }
    await flush();
  }

  async function load() {
    try {
      const res = await fetch("/api/apps");
      const data = await res.json();
      return {
        todos: Array.isArray(data.todos) ? data.todos : [],
        journal: (data.journal && typeof data.journal === "object") ? data.journal : {},
        pomodoro: (data.pomodoro && typeof data.pomodoro === "object")
          ? data.pomodoro : { settings: {} },
      };
    } catch (e) {
      console.error("apps-store: load failed", e);
      return { todos: [], journal: {}, pomodoro: { settings: {} } };
    }
  }

  // Best-effort flush if the user closes the tab mid-debounce.
  window.addEventListener("beforeunload", () => {
    if (timer && Object.keys(pending).length) {
      // sendBeacon survives page unload where fetch may not.
      try {
        navigator.sendBeacon(
          "/api/apps",
          new Blob([JSON.stringify(pending)], { type: "application/json" })
        );
      } catch (e) { /* nothing more we can do */ }
    }
  });

  window.Nova.appsStore = { load, save, saveNow };
})();
