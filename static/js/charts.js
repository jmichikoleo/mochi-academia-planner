// Study-tracker charts. Pulls aggregated stats from /api/study/stats and
// renders with Chart.js. Exposes refreshStudyCharts() so the timer can
// re-render after a new session is saved.

(function () {
  const PINK = '#E79FB3';
  const PINK_SOFT = 'rgba(250, 218, 221, 0.6)';
  const PALETTE = ['#E79FB3', '#F8C8DC', '#FADADD', '#F4A6C0', '#FFB5C5', '#FFD1DC', '#FCE4EC'];

  let dailyChart = null;
  let classChart = null;

  async function fetchStats() {
    const r = await fetch('/api/study/stats');
    if (!r.ok) return null;
    return r.json();
  }

  function formatDay(iso) {
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString(undefined, { weekday: 'short' });
  }

  async function render() {
    const stats = await fetchStats();
    if (!stats) return;

    const dailyCtx = document.getElementById('chart-daily');
    const classCtx = document.getElementById('chart-class');

    if (dailyCtx) {
      const labels = stats.daily.map(d => formatDay(d.date));
      const data   = stats.daily.map(d => d.minutes);
      dailyChart?.destroy();
      dailyChart = new Chart(dailyCtx, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Minutes',
            data,
            borderColor: PINK,
            backgroundColor: PINK_SOFT,
            fill: true,
            tension: 0.35,
            pointRadius: 4,
            pointBackgroundColor: PINK,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } },
        },
      });
    }

    if (classCtx) {
      const labels = stats.per_class.map(c => c.name);
      const data   = stats.per_class.map(c => c.minutes);
      classChart?.destroy();
      classChart = new Chart(classCtx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: 'Minutes',
            data,
            backgroundColor: labels.map((_, i) => PALETTE[i % PALETTE.length]),
            borderRadius: 8,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } },
        },
      });
    }
  }

  window.refreshStudyCharts = render;
  render();
})();
