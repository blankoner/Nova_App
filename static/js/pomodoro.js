/**
 * pomodoro.js — focus/short/long break timer with session dots.
 */
(function () {
  const pomo = {
    settings: { focus: 25, short: 5, long: 15, sessions: 4 },
    mode: 'focus',
    secondsLeft: 25 * 60,
    totalSeconds: 25 * 60,
    running: false,
    ticker: null,
    completedSessions: 0,
  };

  const modeConfig = {
    focus: { label: 'Focus time',    cardClass: '',            settingKey: 'focus' },
    short: { label: 'Short break ☕', cardClass: 'short-break', settingKey: 'short' },
    long:  { label: 'Long break 🌿', cardClass: 'break',       settingKey: 'long'  },
  };

  // Short label for the compact overlay (no emoji, fits the pill)
  const overlayLabel = { focus: 'Focus', short: 'Short break', long: 'Long break' };

  function pomoDisplay(secs) {
    const m = String(Math.floor(secs / 60)).padStart(2, '0');
    const s = String(secs % 60).padStart(2, '0');
    return `${m}:${s}`;
  }

  // Is the user currently looking at the full Pomodoro view?
  function onPomodoroView() {
    const view = document.getElementById('view-pomodoro');
    return !!view && view.classList.contains('active');
  }

  // Decide whether the floating overlay should be visible right now.
  // Shown only when the timer is running AND we're not on the Pomodoro view
  // (on that view the full widget already shows everything).
  function refreshOverlay() {
    const overlay = document.getElementById('pomoOverlay');
    if (!overlay) return;
    const shouldShow = pomo.running && !onPomodoroView();
    overlay.classList.toggle('visible', shouldShow);
  }

  function updateOverlayUI() {
    const overlay = document.getElementById('pomoOverlay');
    if (!overlay) return;

    const timeEl  = document.getElementById('pomoOverlayTime');
    const labelEl = document.getElementById('pomoOverlayLabel');
    const ringEl  = document.getElementById('pomoOverlayRing');
    const toggleEl = document.getElementById('pomoOverlayToggle');

    if (timeEl)  timeEl.textContent  = pomoDisplay(pomo.secondsLeft);
    if (labelEl) labelEl.textContent = overlayLabel[pomo.mode] || 'Focus';

    // Conic-gradient progress ring: fraction of time elapsed
    if (ringEl) {
      const elapsed = 1 - (pomo.secondsLeft / pomo.totalSeconds);
      ringEl.style.setProperty('--ring', (elapsed * 360) + 'deg');
    }

    // Colour-code by mode (matches the full card accents)
    overlay.classList.toggle('mode-short', pomo.mode === 'short');
    overlay.classList.toggle('mode-long',  pomo.mode === 'long');

    if (toggleEl) toggleEl.textContent = pomo.running ? '⏸' : '▶';
  }

  function updatePomoUI() {
    // ── Full widget (only present/visible on the Pomodoro view) ──
    const timeEl = document.getElementById('pomoTime');
    if (timeEl) timeEl.textContent = pomoDisplay(pomo.secondsLeft);
    document.title = pomo.running ? `${pomoDisplay(pomo.secondsLeft)} — Nova` : 'Nova — Dashboard';

    const card = document.getElementById('pomoCard');
    if (card) {
      const progress = pomo.secondsLeft / pomo.totalSeconds;
      card.style.setProperty('--progress', progress);
      card.className = 'pomo-card ' + (modeConfig[pomo.mode].cardClass || '');
    }

    const labelEl = document.getElementById('pomoLabel');
    if (labelEl) labelEl.textContent = modeConfig[pomo.mode].label;

    const btn = document.getElementById('pomoStartBtn');
    if (btn) {
      btn.textContent = pomo.running ? 'PAUSE' : 'START';
      btn.className = 'pomo-btn pomo-btn-main' + (pomo.running ? ' running' : '');
    }

    const dotsEl = document.getElementById('pomoDots');
    if (dotsEl) {
      dotsEl.innerHTML = '';
      for (let i = 0; i < pomo.settings.sessions; i++) {
        const d = document.createElement('div');
        d.className = 'pomo-dot' + (i < pomo.completedSessions ? ' done' : '');
        dotsEl.appendChild(d);
      }
    }

    // ── Floating overlay ──
    updateOverlayUI();
    refreshOverlay();
  }

  function setMode(mode, btnEl) {
    clearInterval(pomo.ticker);
    pomo.running = false;
    pomo.mode = mode;
    pomo.totalSeconds = pomo.settings[modeConfig[mode].settingKey] * 60;
    pomo.secondsLeft = pomo.totalSeconds;

    document.querySelectorAll('.pomo-tab').forEach(b => b.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');

    updatePomoUI();
  }

  function toggleTimer() {
    if (pomo.running) {
      clearInterval(pomo.ticker);
      pomo.running = false;
      updatePomoUI();
      return;
    }
    pomo.running = true;
    updatePomoUI();
    pomo.ticker = setInterval(() => {
      pomo.secondsLeft--;
      updatePomoUI();
      if (pomo.secondsLeft <= 0) {
        clearInterval(pomo.ticker);
        pomo.running = false;
        onSessionEnd();
      }
    }, 1000);
  }

  function onSessionEnd() {
    // Soft 3-beep cue via Web Audio API
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [0, 150, 300].forEach(delay => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 660;
        gain.gain.setValueAtTime(0.25, ctx.currentTime + delay / 1000);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay / 1000 + 0.3);
        osc.start(ctx.currentTime + delay / 1000);
        osc.stop(ctx.currentTime + delay / 1000 + 0.35);
      });
    } catch (e) { /* AudioContext unavailable */ }

    if (pomo.mode === 'focus') {
      pomo.completedSessions++;
      if (pomo.completedSessions >= pomo.settings.sessions) {
        pomo.completedSessions = 0;
        document.querySelectorAll('.pomo-tab').forEach((b, i) => b.classList.toggle('active', i === 2));
        setMode('long', null);
      } else {
        document.querySelectorAll('.pomo-tab').forEach((b, i) => b.classList.toggle('active', i === 1));
        setMode('short', null);
      }
    } else {
      document.querySelectorAll('.pomo-tab').forEach((b, i) => b.classList.toggle('active', i === 0));
      setMode('focus', null);
    }
  }

  function resetTimer() {
    clearInterval(pomo.ticker);
    pomo.running = false;
    pomo.secondsLeft = pomo.totalSeconds;
    updatePomoUI();
  }

  function skipSession() {
    clearInterval(pomo.ticker);
    pomo.running = false;
    pomo.secondsLeft = 0;
    onSessionEnd();
  }

  function adjustSetting(key, delta) {
    const mins = { focus: [5, 60], short: [1, 30], long: [5, 60], sessions: [1, 8] };
    const [min, max] = mins[key];
    pomo.settings[key] = Math.min(max, Math.max(min, pomo.settings[key] + delta));
    document.getElementById('set-' + key).textContent = pomo.settings[key];

    if (modeConfig[pomo.mode].settingKey === key) {
      pomo.totalSeconds = pomo.settings[key] * 60;
      pomo.secondsLeft = pomo.totalSeconds;
      clearInterval(pomo.ticker);
      pomo.running = false;
      updatePomoUI();
    }
    if (key === 'sessions') updatePomoUI();
  }

  // Expose to inline onclick
  window.setMode = setMode;
  window.toggleTimer = toggleTimer;
  window.resetTimer = resetTimer;
  window.skipSession = skipSession;
  window.adjustSetting = adjustSetting;

  // Exposed so dashboard.js can re-evaluate overlay visibility on view change
  window.refreshPomoOverlay = refreshOverlay;

  document.addEventListener("DOMContentLoaded", () => {
    updatePomoUI();

    const overlay = document.getElementById('pomoOverlay');
    const overlayToggle = document.getElementById('pomoOverlayToggle');

    if (overlay) {
      // Click on the overlay body → jump to the full Pomodoro view.
      // (Clicks on the pause button are handled separately and stop-propagated.)
      overlay.addEventListener('click', () => {
        if (typeof window.switchView === 'function') {
          window.switchView('pomodoro');
        }
      });
      // Keyboard accessibility: Enter/Space also opens the view
      overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (typeof window.switchView === 'function') {
            window.switchView('pomodoro');
          }
        }
      });
    }

    if (overlayToggle) {
      overlayToggle.addEventListener('click', (e) => {
        e.stopPropagation(); // don't trigger the overlay's "open view" click
        toggleTimer();
      });
    }
  });
})();
