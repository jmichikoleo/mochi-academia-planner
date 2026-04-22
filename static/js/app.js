// Shared UI helpers: sidebar toggle + modal open/close.
// Kept tiny on purpose — page-specific behavior lives in per-template <script> blocks.

(function () {
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');

  if (toggle && sidebar && overlay) {
    const open = () => {
      sidebar.classList.remove('-translate-x-full');
      overlay.classList.remove('hidden');
    };
    const close = () => {
      sidebar.classList.add('-translate-x-full');
      overlay.classList.add('hidden');
    };
    toggle.addEventListener('click', open);
    overlay.addEventListener('click', close);
  }
})();

// Modal helpers. Modals use `hidden` + `flex` so Tailwind's display utilities toggle cleanly.
window.openModal = function (id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('hidden');
  el.classList.add('flex');
};
window.closeModal = function (id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('hidden');
  el.classList.remove('flex');
};

// Close any open modal on escape.
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  document.querySelectorAll('.flex.fixed.inset-0').forEach(el => {
    if (el.id) window.closeModal(el.id);
  });
});
