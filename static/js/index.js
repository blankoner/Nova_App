/**
 * index.js — landing page step navigation + chat bootstrap.
 * Depends on: chat.js (loaded first)
 */

// ── Step nav ─────────────────────────────────────────────────────
function setStep(n) {
  document.querySelectorAll(".panel").forEach((p, i) => {
    p.classList.toggle("active", i + 1 === n);
  });
  document.querySelectorAll(".step").forEach((s, i) => {
    s.classList.toggle("active", i + 1 <= n);
  });
}

// ── Panel 1 → Dashboard ──────────────────────────────────────────
function goToDashboard() {
  const email = document.getElementById("inp-email").value.trim();
  const pass  = document.getElementById("inp-pass").value;
  const pass2 = document.getElementById("inp-pass2").value;
  if (!email || pass.length < 8 || pass !== pass2) {
    alert("Please fill in all fields correctly.");
    return;
  }
  const name = email.split("@")[0];
  window.location.href = "/dashboard?name=" + encodeURIComponent(name);
}

// Backward-compat alias
function goToChat() { goToDashboard(); }

// Expose to inline onclick handlers
window.setStep = setStep;
window.goToDashboard = goToDashboard;
window.goToChat = goToChat;

// ── Chat bootstrap ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const chat = window.Nova.createChat({
    chatBoxId: "chatBox",
    inputId: "userInput",
    sendBtnId: "sendBtn",
    disableOnDone: false,
    onDone: () => {
      setTimeout(() => setStep(3), 800);
    }
  });
  chat.start();
});
