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
  interview:       { title: "Career Interview",  sub: "Answer a few questions to find your path" },
  todo:            { title: "To-Do List",        sub: "Track your career exploration tasks" },
  matches:         { title: "My Matches",        sub: "Jobs and schools matched to your profile" },
  pomodoro:        { title: "Pomodoro Timer",    sub: "Stay focused — work in sprints, rest between" },
  journal:         { title: "Learning Journal",  sub: "Reflect on what you learned each day" },
  skills:          { title: "Skills",            sub: "Your skill levels and what jobs need" },
  "game-strategy": { title: "Strategy Game",     sub: "Conquer the map — a Risk-style mini-game" },
  "game-social":   { title: "Social Game",       sub: "Read people, choose how to respond" },
};

function switchView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  document.getElementById("view-" + name).classList.add("active");
  document.getElementById("nav-" + name).classList.add("active");
  document.getElementById("topbarTitle").textContent = viewMeta[name].title;
  document.getElementById("topbarSub").textContent   = viewMeta[name].sub;

  // The Pomodoro overlay hides itself on the Pomodoro view and shows
  // elsewhere (when running). Re-evaluate after every view change.
  if (typeof window.refreshPomoOverlay === "function") {
    window.refreshPomoOverlay();
  }
}

window.switchView = switchView;

// ── Chat bootstrap ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const chat = window.Nova.createChat({
    chatBoxId: "chatBox",
    inputId: "userInput",
    sendBtnId: "sendBtn",
    advisorPlaceholder: "Ask me about careers, your matches, or what to do next…",
    onDone: () => {
      // Interview finished — reveal the banner. The chat stays open so the
      // user can ask the advisor follow-up questions.
      const banner = document.getElementById("resultBanner");
      if (banner) banner.style.display = "flex";
      // Swap the banner copy so it's clear they can keep chatting, not just
      // jump to their matches.
      const bannerText = document.getElementById("resultBannerText");
      if (bannerText) {
        bannerText.textContent =
          "🎯 Interview complete! Ask me anything below, or see your matches.";
      }
    }
  });
  chat.start();
});
