// Study-session timer. State lives in localStorage so a refresh doesn't lose a running session.
//
// Why localStorage and not a Supabase row? A running timer is ephemeral — persisting it
// server-side would create an open "session" concept we'd have to reconcile. Writing one
// row when the user hits Stop is simpler and matches how most study apps behave.

(function () {
  const STORAGE_KEY = 'mochi-timer';
  const display = document.getElementById('timer-display');
  const btnStart = document.getElementById('btn-start');
  const btnPause = document.getElementById('btn-pause');
  const btnStop  = document.getElementById('btn-stop');
  if (!display) return;

  let state = loadState() || { running: false, startedAt: null, accumulatedMs: 0 };
  let ticker = null;

  function loadState() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; }
  }
  function saveState() { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
  function clearState() { localStorage.removeItem(STORAGE_KEY); }

  function currentMs() {
    const active = state.running ? (Date.now() - state.startedAt) : 0;
    return state.accumulatedMs + active;
  }

  function render() {
    const ms = currentMs();
    const s = Math.floor(ms / 1000);
    const hh = String(Math.floor(s / 3600)).padStart(2, '0');
    const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const ss = String(s % 60).padStart(2, '0');
    display.textContent = `${hh}:${mm}:${ss}`;

    // Toggle buttons based on run state.
    btnStart.classList.toggle('hidden', state.running || state.accumulatedMs > 0);
    btnPause.classList.toggle('hidden', !state.running);
    btnStop .classList.toggle('hidden', !state.running && state.accumulatedMs === 0);
    btnPause.textContent = state.running ? 'Pause' : 'Resume';
  }

  function startTick() {
    if (ticker) return;
    ticker = setInterval(render, 500);
  }
  function stopTick() {
    clearInterval(ticker);
    ticker = null;
  }

  btnStart.addEventListener('click', () => {
    state = { running: true, startedAt: Date.now(), accumulatedMs: 0 };
    saveState();
    startTick();
    render();
  });

  btnPause.addEventListener('click', () => {
    if (state.running) {
      state.accumulatedMs += Date.now() - state.startedAt;
      state.running = false;
      state.startedAt = null;
      stopTick();
    } else {
      state.running = true;
      state.startedAt = Date.now();
      startTick();
    }
    saveState();
    render();
  });

  btnStop.addEventListener('click', async () => {
    if (state.running) {
      state.accumulatedMs += Date.now() - state.startedAt;
      state.running = false;
    }
    const minutes = Math.round(state.accumulatedMs / 60000);
    if (minutes < 1) {
      if (!confirm('Less than a minute logged. Save anyway?')) { return; }
    }

    const classId = document.getElementById('timer-class').value || null;
    const notes   = document.getElementById('timer-notes').value || '';

    const res = await fetch('/api/study', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        class_id: classId,
        duration: Math.max(minutes, 1),
        date: new Date().toISOString().slice(0, 10),
        notes,
      }),
    });
    if (res.ok) {
      clearState();
      state = { running: false, startedAt: null, accumulatedMs: 0 };
      document.getElementById('timer-notes').value = '';
      stopTick();
      render();
      // Charts are on the same page — refresh them in place.
      if (window.refreshStudyCharts) window.refreshStudyCharts();
    } else {
      alert('Failed to save session.');
    }
  });

  // Boot: if there was a running session in storage, resume ticking.
  if (state.running) startTick();
  render();
})();
