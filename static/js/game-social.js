/**
 * game-social.js — a Life-is-Strange-style social game (player vs scenarios).
 *
 * Unlike the Strategy game, the *content* and *scoring* live on the server
 * (social_scenes.py). This file only:
 *   - fetches the scenes from /api/social/scenes
 *   - walks the player through each scene's two steps (READ then RESPOND)
 *   - collects the player's picks
 *   - POSTs them to /api/social/score, which returns skill scores
 *   - shows the result screen
 *
 * The client never sees which emotion is "correct" or what a response is
 * worth — that's the whole point of keeping scoring server-side.
 *
 * ── Two steps per scene ────────────────────────────────────────────────────
 *   READ    — player guesses what the other person is feeling   → empathy
 *   RESPOND — player picks how to react (no "right" answer)      → support/logic
 */
(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────────────
  let scenes = [];          // fetched from the server
  let sceneIndex = 0;       // which scene we're on
  let step = "read";        // "read" | "respond"
  let pendingRead = null;   // the emotion key the player picked this scene
  let answers = [];         // [{scene, read, response}, ...] — sent for scoring
  let loading = true;
  let submitting = false;

  // ── DOM refs (filled on DOMContentLoaded) ──────────────────────────────────
  let el = {};

  // ── Avatar: a tiny procedural SVG face whose expression follows the scene ──
  // We don't know the "correct" emotion (server hides it), so the avatar shows
  // a neutral-but-readable expression keyed off the *posture text* mood. To
  // keep it honest, we derive a coarse mood from keywords in the posture so the
  // avatar never gives away the answer outright — it just sets a tone.
  function avatarSvg() {
    // A calm, attentive neutral face. Deliberately not emotion-specific:
    // reading the *text* is the player's job; the avatar is just presence.
    return `
      <svg viewBox="0 0 120 120" class="avatar-svg" aria-hidden="true">
        <circle cx="60" cy="60" r="54" class="avatar-head"/>
        <circle cx="60" cy="60" r="54" class="avatar-head-ring"/>
        <circle cx="44" cy="52" r="5" class="avatar-eye"/>
        <circle cx="76" cy="52" r="5" class="avatar-eye"/>
        <path d="M44 82 Q60 90 76 82" class="avatar-mouth" fill="none"/>
      </svg>`;
  }

  // ── Fetch scenes ───────────────────────────────────────────────────────────
  function loadScenes() {
    fetch("/api/social/scenes")
      .then(res => res.json())
      .then(data => {
        scenes = (data && data.scenes) || [];
        loading = false;
        if (scenes.length === 0) {
          renderError("No scenes available right now. Please try again later.");
          return;
        }
        render();
      })
      .catch(() => {
        loading = false;
        renderError("Couldn't load the game. Check your connection and refresh.");
      });
  }

  // ── Player actions ─────────────────────────────────────────────────────────
  function pickRead(emotionKey) {
    if (step !== "read") return;
    pendingRead = emotionKey;
    step = "respond";
    render();
  }

  function pickResponse(responseId) {
    if (step !== "respond" || submitting) return;

    const scene = scenes[sceneIndex];
    answers.push({
      scene: scene.id,
      read: pendingRead,
      response: responseId,
    });

    pendingRead = null;

    if (sceneIndex + 1 < scenes.length) {
      sceneIndex += 1;
      step = "read";
      render();
    } else {
      submitPlaythrough();
    }
  }

  function restart() {
    sceneIndex = 0;
    step = "read";
    pendingRead = null;
    answers = [];
    submitting = false;
    render();
  }

  // ── Submit for scoring ─────────────────────────────────────────────────────
  function submitPlaythrough() {
    submitting = true;
    renderSubmitting();

    fetch("/api/social/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    })
      .then(res => res.json())
      .then(data => {
        submitting = false;
        if (data && data.skills) {
          renderResult(data);
        } else {
          renderError("Something went wrong scoring your game. Please try again.");
        }
      })
      .catch(() => {
        submitting = false;
        renderError("Couldn't reach the server to save your results. Please try again.");
      });
  }

  // ── Rendering ──────────────────────────────────────────────────────────────
  function render() {
    if (loading) { renderLoading(); return; }
    if (submitting) { renderSubmitting(); return; }
    renderScene();
  }

  function renderLoading() {
    el.stage.innerHTML = `<div class="social-loading">Loading scenes…</div>`;
    el.progress.innerHTML = "";
  }

  function renderSubmitting() {
    el.stage.innerHTML = `<div class="social-loading">Reading your choices…</div>`;
  }

  function renderError(msg) {
    el.stage.innerHTML = `
      <div class="social-error">
        <p>${msg}</p>
        <button class="btn btn-violet" id="errorRetry">Retry</button>
      </div>`;
    const retry = document.getElementById("errorRetry");
    if (retry) retry.addEventListener("click", () => {
      loading = true;
      render();
      loadScenes();
    });
  }

  function renderProgress() {
    // Dots: filled for scenes done, ringed for current, empty for upcoming
    let dots = "";
    for (let i = 0; i < scenes.length; i++) {
      let cls = "progress-dot";
      if (i < sceneIndex) cls += " done";
      else if (i === sceneIndex) cls += " current";
      dots += `<span class="${cls}"></span>`;
    }
    el.progress.innerHTML = `
      <div class="progress-dots">${dots}</div>
      <div class="progress-label">Scene ${sceneIndex + 1} of ${scenes.length}</div>`;
  }

  function renderScene() {
    const scene = scenes[sceneIndex];
    renderProgress();

    // Shared scene header: situation + the person and their posture
    const header = `
      <div class="scene-situation">${scene.situation}</div>
      <div class="scene-person-card">
        <div class="scene-avatar">${avatarSvg()}</div>
        <div class="scene-person-text">
          <div class="scene-person-name">${scene.person}</div>
          <div class="scene-posture">${scene.posture}</div>
        </div>
      </div>`;

    if (step === "read") {
      // STEP 1: read the emotion
      let opts = "";
      scene.read_options.forEach(o => {
        opts += `
          <button class="social-option read-option" data-key="${o.key}">
            ${o.label}
          </button>`;
      });
      el.stage.innerHTML = `
        ${header}
        <div class="step-prompt">
          <span class="step-tag">Step 1 · Read them</span>
          <p>Look at how they're behaving. What are they actually feeling?</p>
        </div>
        <div class="social-options">${opts}</div>`;

    } else {
      // STEP 2: choose a response
      let opts = "";
      scene.responses.forEach(r => {
        opts += `
          <button class="social-option respond-option" data-id="${r.id}">
            ${r.text}
          </button>`;
      });
      el.stage.innerHTML = `
        ${header}
        <div class="step-prompt">
          <span class="step-tag">Step 2 · Respond</span>
          <p>There's no perfect answer here. How do you react?</p>
        </div>
        <div class="social-options">${opts}</div>`;
    }
  }

  function renderResult(data) {
    el.progress.innerHTML = "";

    const skills = data.skills;
    const labels = {
      empathy: "Empathy",
      emotional_support: "Emotional Support",
      logical_thinking: "Logical Thinking",
    };
    const blurb = {
      empathy: "How accurately you read what people were feeling.",
      emotional_support: "How much your responses validated and supported others.",
      logical_thinking: "How much your responses brought reasoning and problem-solving.",
    };

    let bars = "";
    Object.keys(labels).forEach(key => {
      const val = skills[key] != null ? skills[key] : 0;
      bars += `
        <div class="result-skill">
          <div class="result-skill-head">
            <span>${labels[key]}</span>
            <span class="result-skill-val">${val}</span>
          </div>
          <div class="result-bar-track">
            <div class="result-bar-fill" style="width:${val}%"></div>
          </div>
          <p class="result-skill-blurb">${blurb[key]}</p>
        </div>`;
    });

    // How many emotions they read correctly, from the detail breakdown
    let readLine = "";
    if (Array.isArray(data.detail) && data.detail.length) {
      const right = data.detail.filter(d => d.read_correct).length;
      readLine = `<p class="result-read-line">
        You read <strong>${right}</strong> of <strong>${data.detail.length}</strong>
        people correctly.</p>`;
    }

    el.stage.innerHTML = `
      <div class="social-result">
        <h2>How you connect</h2>
        <p class="social-result-sub">
          Every choice was valid — this is simply the pattern they formed.
        </p>
        ${readLine}
        <div class="result-skills">${bars}</div>
        <p class="save-note" id="saveNote">Saving to your profile…</p>
        <div class="social-result-actions">
          <button class="btn btn-violet" id="playAgainBtn">Play again</button>
          <a href="/skills" class="btn">View skills</a>
        </div>
      </div>`;

    const playAgain = document.getElementById("playAgainBtn");
    if (playAgain) playAgain.addEventListener("click", restart);

    // Persist to the user's profile via the shared game-result endpoint.
    fetch("/api/game-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game: "social", result: skills }),
    })
      .then(res => res.json())
      .then(saved => {
        const note = document.getElementById("saveNote");
        if (note) {
          note.textContent = (saved && saved.ok)
            ? "Skills updated and saved to your profile."
            : "Couldn't save your skills — please try again later.";
        }
      })
      .catch(() => {
        const note = document.getElementById("saveNote");
        if (note) note.textContent = "Couldn't reach the server — skills not saved.";
      });
  }

  // ── Wiring ─────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    el = {
      stage: document.getElementById("socialStage"),
      progress: document.getElementById("socialProgress"),
    };
    if (!el.stage) return;

    // Event delegation — option buttons are re-rendered every step
    el.stage.addEventListener("click", (e) => {
      const readBtn = e.target.closest(".read-option");
      if (readBtn) { pickRead(readBtn.dataset.key); return; }

      const respondBtn = e.target.closest(".respond-option");
      if (respondBtn) { pickResponse(respondBtn.dataset.id); return; }
    });

    loadScenes();
  });
})();
