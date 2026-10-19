// Theme toggle (remembered per browser when storage works) and copy buttons.
(function () {
  const root = document.documentElement;
  const KEY = 'schematically-theme';
  const read = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
  const write = v => { try { localStorage.setItem(KEY, v); } catch { /* storage blocked: the choice lasts this page only */ } };
  const resolved = () => root.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');

  function syncFrames() {
    for (const f of document.querySelectorAll('iframe[data-viewer]')) {
      const base = f.dataset.viewer;
      const want = `${base}#theme=${resolved()}`;
      if (f.getAttribute('src') !== want) f.setAttribute('src', want);
    }
    const b = document.getElementById('theme');
    if (b) b.textContent = resolved() === 'dark' ? 'Light' : 'Dark';
  }
  const saved = read();
  if (saved === 'light' || saved === 'dark') root.dataset.theme = saved;
  document.addEventListener('DOMContentLoaded', () => {
    syncFrames();
    const b = document.getElementById('theme');
    if (b) b.addEventListener('click', () => {
      root.dataset.theme = resolved() === 'dark' ? 'light' : 'dark';
      write(root.dataset.theme);
      syncFrames();
    });
    matchMedia('(prefers-color-scheme: light)').addEventListener('change', syncFrames);
    for (const btn of document.querySelectorAll('[data-copy]')) {
      btn.addEventListener('click', () => {
        const text = btn.dataset.copy;
        const done = () => { const was = btn.textContent; btn.textContent = 'Copied'; btn.dataset.done = '';
          setTimeout(() => { btn.textContent = was; delete btn.dataset.done; }, 1400); };
        (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(done, () => prompt('Copy this', text));
      });
    }
  });
})();
