/**
 * journal.js — calendar + daily reflection notes (sessionStorage).
 */
(function () {
  const STORAGE_KEY = 'nova_journal';
  const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December'];

  let calYear, calMonth, selectedDate = null;
  let notes = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');

  function dateKey(y, m, d) {
    return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  }

  function todayKey() {
    const t = new Date();
    return dateKey(t.getFullYear(), t.getMonth(), t.getDate());
  }

  function saveNotesStorage() {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
  }

  function renderCalendar() {
    const label = document.getElementById('calMonthLabel');
    label.textContent = `${MONTHS[calMonth]} ${calYear}`;

    const grid = document.getElementById('calGrid');
    grid.innerHTML = '';

    DOW.forEach(d => {
      const el = document.createElement('div');
      el.className = 'cal-dow';
      el.textContent = d;
      grid.appendChild(el);
    });

    const today = new Date();
    const firstDay = new Date(calYear, calMonth, 1);
    let startOffset = (firstDay.getDay() + 6) % 7;
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    const daysInPrev = new Date(calYear, calMonth, 0).getDate();

    for (let i = startOffset - 1; i >= 0; i--) {
      const el = document.createElement('div');
      el.className = 'cal-day other-month';
      el.textContent = daysInPrev - i;
      grid.appendChild(el);
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const el = document.createElement('div');
      el.className = 'cal-day';
      el.textContent = d;

      const key = dateKey(calYear, calMonth, d);
      const isToday = (calYear === today.getFullYear() &&
                       calMonth === today.getMonth() &&
                       d === today.getDate());
      const isSelected = (selectedDate === key);

      if (isToday)    el.classList.add('today');
      if (isSelected) el.classList.add('selected');
      if (notes[key]) el.classList.add('has-note');

      el.addEventListener('click', () => selectDay(calYear, calMonth, d));
      grid.appendChild(el);
    }

    const cellsUsed = startOffset + daysInMonth;
    const remainder = cellsUsed % 7 === 0 ? 0 : 7 - (cellsUsed % 7);
    for (let d = 1; d <= remainder; d++) {
      const el = document.createElement('div');
      el.className = 'cal-day other-month';
      el.textContent = d;
      grid.appendChild(el);
    }
  }

  function selectDay(y, m, d) {
    selectedDate = dateKey(y, m, d);

    const dateObj = new Date(y, m, d);
    const labelEl = document.getElementById('noteDateLabel');
    const subEl = document.getElementById('noteDateSub');
    const textarea = document.getElementById('noteText');
    const saveBtn = document.getElementById('noteSaveBtn');
    const delBtn = document.getElementById('noteDeleteBtn');
    const counter = document.getElementById('noteCharCount');

    labelEl.textContent = dateObj.toLocaleDateString('en-GB', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
    });

    const isToday = selectedDate === todayKey();
    subEl.textContent = isToday ? "Today's reflection" : "Past reflection";

    textarea.value = notes[selectedDate] || '';
    textarea.placeholder = isToday
      ? "What did you learn today? What are you proud of?"
      : "What did you learn on this day?";
    textarea.disabled = false;

    counter.textContent = `${textarea.value.length} characters`;
    saveBtn.classList.remove('visible', 'saved');
    delBtn.style.display = notes[selectedDate] ? 'block' : 'none';

    renderCalendar();
  }

  function insertPrompt(text) {
    const ta = document.getElementById('noteText');
    if (ta.disabled) return;
    const pos = ta.selectionStart;
    const before = ta.value.substring(0, pos);
    const after = ta.value.substring(ta.selectionEnd);
    ta.value = before + text + after;
    ta.selectionStart = ta.selectionEnd = pos + text.length;
    ta.focus();
    onNoteInput();
  }

  function onNoteInput() {
    const ta = document.getElementById('noteText');
    const saveBtn = document.getElementById('noteSaveBtn');
    document.getElementById('noteCharCount').textContent = `${ta.value.length} characters`;
    saveBtn.classList.add('visible');
    saveBtn.classList.remove('saved');
    saveBtn.textContent = 'Save';
  }

  function saveNote() {
    if (!selectedDate) return;
    const text = document.getElementById('noteText').value.trim();
    const saveBtn = document.getElementById('noteSaveBtn');
    const delBtn = document.getElementById('noteDeleteBtn');

    if (text) {
      notes[selectedDate] = text;
    } else {
      delete notes[selectedDate];
    }
    saveNotesStorage();

    saveBtn.textContent = 'Saved ✓';
    saveBtn.classList.add('saved');
    setTimeout(() => {
      saveBtn.classList.remove('visible', 'saved');
      saveBtn.textContent = 'Save';
    }, 1800);

    delBtn.style.display = notes[selectedDate] ? 'block' : 'none';
    renderCalendar();
  }

  function deleteNote() {
    if (!selectedDate) return;
    if (!confirm('Delete this note?')) return;
    delete notes[selectedDate];
    saveNotesStorage();
    document.getElementById('noteText').value = '';
    document.getElementById('noteDeleteBtn').style.display = 'none';
    document.getElementById('noteCharCount').textContent = '0 characters';
    document.getElementById('noteSaveBtn').classList.remove('visible');
    renderCalendar();
  }

  function calShiftMonth(delta) {
    calMonth += delta;
    if (calMonth > 11) { calMonth = 0; calYear++; }
    if (calMonth < 0)  { calMonth = 11; calYear--; }
    renderCalendar();
  }

  // Expose for inline onclick
  window.insertPrompt = insertPrompt;
  window.saveNote = saveNote;
  window.deleteNote = deleteNote;
  window.calShiftMonth = calShiftMonth;

  document.addEventListener("DOMContentLoaded", () => {
    const t = new Date();
    calYear = t.getFullYear();
    calMonth = t.getMonth();
    renderCalendar();
    selectDay(calYear, calMonth, t.getDate());

    document.getElementById('noteText').addEventListener('input', onNoteInput);
    document.getElementById('noteText').addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveNote();
      }
    });
  });
})();
