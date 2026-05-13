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

  function pomoDisplay(secs) {
    const m = String(Math.floor(secs / 60)).padStart(2, '0');
    const s = String(secs % 60).padStart(2, '0');
    return `${m}:${s}`;
  }

  function updatePomoUI() {
    document.getElementById('pomoTime').textContent = pomoDisplay(pomo.secondsLeft);
    document.title = pomo.running ? `${pomoDisplay(pomo.secondsLeft)} — Nova` : 'Nova — Dashboard';

    const card = document.getElementById('pomoCard');
    const progress = pomo.secondsLeft / pomo.totalSeconds;
    card.style.setProperty('--progress', progress);
    card.className = 'pomo-card ' + (modeConfig[pomo.mode].cardClass || '');

    document.getElementById('pomoLabel').textContent = modeConfig[pomo.mode].label;

    const btn = document.getElementById('pomoStartBtn');
    btn.textContent = pomo.running ? 'PAUSE' : 'START';
    btn.className = 'pomo-btn pomo-btn-main' + (pomo.running ? ' running' : '');

    const dotsEl = document.getElementById('pomoDots');
    dotsEl.innerHTML = '';
    for (let i = 0; i < pomo.settings.sessions; i++) {
      const d = document.createElement('div');
      d.className = 'pomo-dot' + (i < pomo.completedSessions ? ' done' : '');
      dotsEl.appendChild(d);
    }
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

  document.addEventListener("DOMContentLoaded", updatePomoUI);
})();
