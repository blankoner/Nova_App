/**
 * index.js — landing page signup/login logic with localStorage persistence.
 * Depends on: chat.js only when chat elements are present.
 */

const AUTH_KEY = "novaUserAuth";

function simpleHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(16);
}

function saveCredentials(name, email, password) {
  const userData = {
    name: name || "",
    email: email,
    passwordHash: simpleHash(password),
    createdAt: new Date().toISOString()
  };
  localStorage.setItem(AUTH_KEY, JSON.stringify(userData));
}

function getStoredCredentials() {
  const stored = localStorage.getItem(AUTH_KEY);
  return stored ? JSON.parse(stored) : null;
}

function validateCredentials(email, password) {
  const stored = getStoredCredentials();
  if (!stored) return false;
  return stored.email === email && stored.passwordHash === simpleHash(password);
}

function clearCredentials() {
  localStorage.removeItem(AUTH_KEY);
}

function getDisplayName(email) {
  const stored = getStoredCredentials();
  return stored && stored.email === email && stored.name ? stored.name : email.split("@")[0];
}

function proceedToDashboard(email) {
  const name = getDisplayName(email);
  window.location.href = "/dashboard?name=" + encodeURIComponent(name);
}

function showSignup() {
  document.querySelector(".signup-panel").classList.add("active");
  document.querySelector(".login-panel").classList.remove("active");
  const input = document.getElementById("inp-name");
  if (input) input.focus();
}

function showLogin() {
  document.querySelector(".login-panel").classList.add("active");
  document.querySelector(".signup-panel").classList.remove("active");
  const input = document.getElementById("login-email");
  if (input) input.focus();
}

function handleSignup() {
  const name  = document.getElementById("inp-name").value.trim();
  const email = document.getElementById("inp-email").value.trim();
  const pass  = document.getElementById("inp-pass").value;

  if (!name) {
    alert("Please enter your full name.");
    return;
  }
  if (!email) {
    alert("Please enter an email address.");
    return;
  }
  if (!email.includes("@")) {
    alert("Please enter a valid email address.");
    return;
  }
  if (pass.length < 8) {
    alert("Password must be at least 8 characters.");
    return;
  }

  const stored = getStoredCredentials();
  if (stored && stored.email === email) {
    alert("An account with this email already exists. Please log in instead.");
    showLogin();
    return;
  }

  saveCredentials(name, email, pass);
  document.getElementById("inp-name").value = "";
  document.getElementById("inp-email").value = "";
  document.getElementById("inp-pass").value = "";
  proceedToDashboard(email);
}

function handleLogin() {
  const email = document.getElementById("login-email").value.trim();
  const pass  = document.getElementById("login-pass").value;

  if (!email || !pass) {
    alert("Please enter both email and password.");
    return;
  }

  if (!validateCredentials(email, pass)) {
    alert("Invalid email or password. Please try again.");
    return;
  }

  document.getElementById("login-pass").value = "";
  proceedToDashboard(email);
}

function checkAutoLogin() {
  const stored = getStoredCredentials();
  if (stored) {
    document.getElementById("login-email").value = stored.email;
    showLogin();
  } else {
    showSignup();
  }
}

window.handleSignup = handleSignup;
window.handleLogin = handleLogin;
window.showLogin = showLogin;
window.showSignup = showSignup;
window.clearCredentials = clearCredentials;

document.addEventListener("DOMContentLoaded", () => {
  checkAutoLogin();

  const chatBox = document.getElementById("chatBox");
  if (chatBox && window.Nova && typeof window.Nova.createChat === "function") {
    const chat = window.Nova.createChat({
      chatBoxId: "chatBox",
      inputId: "userInput",
      sendBtnId: "sendBtn",
      onDone: () => {
        setTimeout(() => {
          const stepPanels = document.querySelectorAll(".panel");
          stepPanels.forEach((panel, index) => panel.classList.toggle("active", index === 3));
        }, 800);
      }
    });
    chat.start();
  }
});
