/**
 * index.js — landing page step navigation + authentication + chat bootstrap.
 * Features: Local signup/login with localStorage persistence, auto-login on refresh.
 * Depends on: chat.js (loaded first)
 */

// ── Authentication Storage ─────────────────────────────────────────
const AUTH_KEY = "novaUserAuth";

/**
 * Simple hash function for passwords (client-side only - not cryptographically secure)
 * In production, use server-side hashing!
 */
function simpleHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash).toString(16);
}

/**
 * Save user credentials to localStorage
 */
function saveCredentials(email, password) {
  const userData = {
    email: email,
    passwordHash: simpleHash(password),
    createdAt: new Date().toISOString()
  };
  localStorage.setItem(AUTH_KEY, JSON.stringify(userData));
}

/**
 * Get stored user credentials
 */
function getStoredCredentials() {
  const stored = localStorage.getItem(AUTH_KEY);
  return stored ? JSON.parse(stored) : null;
}

/**
 * Validate login against stored credentials
 */
function validateCredentials(email, password) {
  const stored = getStoredCredentials();
  if (!stored) return false;
  return stored.email === email && stored.passwordHash === simpleHash(password);
}

/**
 * Clear stored credentials (logout)
 */
function clearCredentials() {
  localStorage.removeItem(AUTH_KEY);
}

/**
 * Proceed to dashboard with authenticated user
 */
function proceedToDashboard(email) {
  const name = email.split("@")[0];
  window.location.href = "/dashboard?name=" + encodeURIComponent(name);
}

// ── Step nav ─────────────────────────────────────────────────────
function setStep(n) {
  document.querySelectorAll(".panel").forEach((p, i) => {
    p.classList.toggle("active", i === n);
  });
  document.querySelectorAll(".step").forEach((s, i) => {
    s.classList.toggle("active", i + 1 <= n);
  });
}

// ── Navigation between panels ────────────────────────────────────
function goToLogin() {
  setStep(0);
  document.getElementById("login-email").focus();
}

function goToSignup() {
  setStep(1);
  document.getElementById("inp-email").focus();
}

// ── Handle Signup ────────────────────────────────────────────────
function handleSignup() {
  const email = document.getElementById("inp-email").value.trim();
  const pass  = document.getElementById("inp-pass").value;
  const pass2 = document.getElementById("inp-pass2").value;

  // Validation
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
  if (pass !== pass2) {
    alert("Passwords do not match.");
    return;
  }

  // Check if account already exists
  const stored = getStoredCredentials();
  if (stored && stored.email === email) {
    alert("An account with this email already exists. Please log in instead.");
    goToLogin();
    return;
  }

  // Save credentials to localStorage
  saveCredentials(email, pass);
  
  // Clear form
  document.getElementById("inp-email").value = "";
  document.getElementById("inp-pass").value = "";
  document.getElementById("inp-pass2").value = "";

  alert("Account created successfully! Moving to the next step...");
  
  // Move to chat panel
  setStep(2);
}

// ── Handle Login ─────────────────────────────────────────────────
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

  // Clear form
  document.getElementById("login-email").value = "";
  document.getElementById("login-pass").value = "";

  // Proceed to dashboard
  proceedToDashboard(email);
}

// ── Auto-login on page load ──────────────────────────────────────
function checkAutoLogin() {
  const stored = getStoredCredentials();
  if (stored) {
    // User has stored credentials - show login panel
    document.getElementById("login-email").value = stored.email;
    setStep(0); // Show login panel
  } else {
    // No stored credentials - show signup panel
    setStep(1);
  }
}

// ── Panel 1 → Dashboard (deprecated, kept for backward-compat) ────
function goToDashboard() {
  handleSignup();
}

// Backward-compat alias
function goToChat() { handleSignup(); }

// Expose to inline onclick handlers
window.setStep = setStep;
window.goToDashboard = goToDashboard;
window.goToChat = goToChat;
window.handleSignup = handleSignup;
window.handleLogin = handleLogin;
window.goToLogin = goToLogin;
window.goToSignup = goToSignup;
window.clearCredentials = clearCredentials;

// ── Chat bootstrap ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Check for stored credentials and show appropriate panel
  checkAutoLogin();

  const chat = window.Nova.createChat({
    chatBoxId: "chatBox",
    inputId: "userInput",
    sendBtnId: "sendBtn",
    // On the landing page we move the user straight to the "all set" panel
    // when the interview ends; the advisor follow-up chat lives in the dashboard.
    onDone: () => {
      setTimeout(() => setStep(3), 800);
    }
  });
  chat.start();
});
