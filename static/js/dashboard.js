/**
 * dashboard.js — user setup + view switching + chat bootstrap.
 * Depends on: chat.js (loaded first). todo.js/pomodoro.js/journal.js
 * each self-init on DOMContentLoaded.
 */

// ── User setup ───────────────────────────────────────────────────
(function () {
  const params = new URLSearchParams(window.location.search);
  const userName = params.get("name") || "Guest";
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("userName").textContent = userName;
    document.getElementById("avatarEl").textContent = userName[0].toUpperCase();
  });
})();

// ── View switching ───────────────────────────────────────────────
const viewMeta = {
  interview: { title: "Career Interview",  sub: "Answer a few questions to find your path" },
  todo:      { title: "To-Do List",        sub: "Track your career exploration tasks" },
  matches:   { title: "My Matches",        sub: "Jobs and schools matched to your profile" },
  pomodoro:  { title: "Pomodoro Timer",    sub: "Stay focused — work in sprints, rest between" },
  journal:   { title: "Learning Journal",  sub: "Reflect on what you learned each day" },
};

function switchView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  document.getElementById("view-" + name).classList.add("active");
  document.getElementById("nav-" + name).classList.add("active");
  document.getElementById("topbarTitle").textContent = viewMeta[name].title;
  document.getElementById("topbarSub").textContent   = viewMeta[name].sub;
}

window.switchView = switchView;

// ── Chat bootstrap ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const chat = window.Nova.createChat({
    chatBoxId: "chatBox",
    inputId: "userInput",
    sendBtnId: "sendBtn",
    disableOnDone: true,
    onDone: () => {
      document.getElementById("resultBanner").style.display = "flex";
    }
  });
  chat.start();
});
