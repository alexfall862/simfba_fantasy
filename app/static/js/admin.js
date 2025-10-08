// static/js/admin.js
(function () {
  const $ = (id) => document.getElementById(id);

  window.addEventListener('DOMContentLoaded', () => {
    // ---- Common auth (single token input, persisted) ----
    const tokenEl = $('run-token');

    // Restore saved token (optional convenience)
    try {
      const saved = localStorage.getItem('simfba_admin_token');
      if (saved && tokenEl) tokenEl.value = saved;
    } catch {}

    const authHeaders = () => {
      const t = (tokenEl?.value || '').trim();
      try { localStorage.setItem('simfba_admin_token', t); } catch {}
      return t ? { 'Authorization': `Bearer ${t}` } : {};
    };

    // ---- Run Sync controls ----
    const startEl = $('start-year');
    const aheadEl = $('years-ahead');
    const weekEl  = $('max-week');
    const runBtn  = $('run-sync');
    const outEl   = $('run-result');

    if (runBtn && startEl && aheadEl && weekEl) {
      runBtn.addEventListener('click', async (e) => {
        e.preventDefault();

        const payload = {
          start_year: parseInt(startEl.value || '0', 10),
          years_ahead: parseInt(aheadEl.value || '0', 10),
          max_week: parseInt(weekEl.value || '0', 10),
        };

        if (outEl) outEl.textContent = 'Running…';

        try {
          const res = await fetch('/admin/run-sync', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...authHeaders(),
            },
            body: JSON.stringify(payload),
          });

          const data = await res.json().catch(() => ({}));

          if (!res.ok) {
            if (outEl) outEl.textContent = JSON.stringify(data, null, 2) || res.statusText;
            alert(`Sync failed: ${data.detail || res.statusText}`);
            return;
          }

          if (outEl) outEl.textContent = JSON.stringify(data, null, 2);
        } catch (err) {
          console.error(err);
          if (outEl) outEl.textContent = String(err);
          alert('Network error while running sync.');
        }
      });
    } else {
      console.warn('[admin.js] Run Sync controls not found on this page.');
    }

    // ---- Reprocess controls ----
    const reBtn    = $('reprocess');
    const sportEl  = $('re-sport');
    const yearEl   = $('re-year');
    const forceEl  = $('re-force');
    const reOutEl  = $('reprocess-result');

    if (reBtn) {
      reBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (reOutEl) reOutEl.textContent = 'Reprocessing...';

        const payload = {
          sport: (sportEl && sportEl.value) ? sportEl.value : null,             // '', 'nfl', 'cfb' -> null or value
          year: (yearEl && yearEl.value) ? parseInt(yearEl.value, 10) : null,  // optional
          force: !!(forceEl && forceEl.checked),                                // default true in your HTML
        };

        try {
          const res = await fetch('/admin/reprocess', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...authHeaders(),
            },
            body: JSON.stringify(payload),
          });

          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            if (reOutEl) reOutEl.textContent = `Error: ${data.detail || res.statusText}`;
            alert(`Reprocess failed: ${data.detail || res.statusText}`);
            return;
          }

          if (reOutEl) reOutEl.textContent = JSON.stringify(data, null, 2);
          alert(`Reprocess done. Processed: ${data.processed}, Unchanged: ${data.unchanged}, Errors: ${data.errors}`);
        } catch (err) {
          console.error(err);
          if (reOutEl) reOutEl.textContent = 'Network error during reprocess.';
          alert('Network error during reprocess.');
        }
      });
    } else {
      console.warn('[admin.js] Reprocess controls not found on this page.');
    }
  });
})();
