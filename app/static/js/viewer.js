(function () {
  const PAGE_SIZE = 50;
  const ARRAYS = {
    nfl: { team: 'NFLTeamGameStats', player: 'NFLPlayerGameStats' },
    cfb: { team: 'CFBTeamGameStats', player: 'CFBPlayerGameStats' }
  };

  const el = document.getElementById('simfba-viewer');
  if (!el) return;

  const $ = (s, r=el) => r.querySelector(s);
  const $$ = (s, r=el) => Array.from(r.querySelectorAll(s));

  const btnSport = $$('.sv-toggle-btn[data-sport]');
  const btnView  = $$('.sv-toggle-btn[data-view]');
  const yearPrev = $('.sv-year-prev');
  const yearNext = $('.sv-year-next');
  const yearSel  = $('.sv-year-select');
  const weekPrev = $('.sv-week-prev');
  const weekNext = $('.sv-week-next');
  const weekSel  = $('.sv-week-select');
  const searchIn = $('.sv-search');
  const thead    = $('thead');
  const tbody    = $('tbody');
  const tbl      = $('.sv-table');
  const emptyMsg = $('.sv-empty');
  const pagePrev = $('.sv-page-prev');
  const pageNext = $('.sv-page-next');
  const pageInfo = $('.sv-page-info');

  let M = null; // manifest
  let state = {
    sport: 'nfl',
    year: null,
    week: null,
    view: 'team',
    data: [],
    filtered: [],
    sortKey: null,
    sortDir: 'asc',
    page: 1,
    idKey: null
  };

  // Positions UI state
  const PositionState = {
    selected: new Set(),
    all: [],
    columnsByPosition: {}
  };
  const LS_POSITIONS_KEY = 'simfba.positions.selected';

  function savePos() {
    try { localStorage.setItem(LS_POSITIONS_KEY, JSON.stringify(Array.from(PositionState.selected))); } catch {}
  }
  function loadPos() {
    try {
      const raw = localStorage.getItem(LS_POSITIONS_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch { return []; }
  }

  function buildPositionBar() {
    const bar = document.getElementById('simfba-position-bar');
    if (!bar) return;
    const cfg = window.SIMFBA_POSITIONS || { shared:{positions:[],columnsByPosition:{}}, overrides:{} };
    const shared = cfg.shared || {};
    const overrides = (cfg.overrides && cfg.overrides[state.sport]) || null;

    PositionState.all = (overrides && Array.isArray(overrides.positions) && overrides.positions.length)
      ? overrides.positions
      : (shared.positions || []);
    PositionState.columnsByPosition = Object.assign({}, shared.columnsByPosition || {}, (overrides && overrides.columnsByPosition) || {});
    PositionState.selected = new Set(loadPos().filter(p => PositionState.all.includes(p)));
    bar.innerHTML = '';
    const mk = (label, key, cmd=null) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'simfba-chip';
      b.textContent = label;
      b.dataset.key = key;
      b.addEventListener('click', () => {
        if (cmd === 'all') PositionState.selected = new Set(PositionState.all);
        else if (cmd === 'none') PositionState.selected.clear();
        else {
          if (PositionState.selected.has(key)) PositionState.selected.delete(key);
          else PositionState.selected.add(key);
        }
        // Defense chip doesn’t force Team; we keep chips inert when view=team.
        savePos();
        refreshChips();
        applyFilterAndRender(currentColumns());
      });
      return b;
    };
    bar.appendChild(mk('All','ALL','all'));
    bar.appendChild(mk('None','NONE','none'));
    PositionState.all.forEach(p => bar.appendChild(mk(p, p)));
    refreshChips();
  }
  function refreshChips() {
    const bar = document.getElementById('simfba-position-bar');
    const isTeam = (state.view === 'team');
    bar.querySelectorAll('.simfba-chip').forEach(btn => {
      const key = btn.dataset.key;
      const isCmd = (key === 'ALL' || key === 'NONE');
      const sel = PositionState.selected.has(key);
      btn.style.background = sel && !isCmd ? '#1e73be' : '#f7f7f7';
      btn.style.color = sel && !isCmd ? '#fff' : '#222';
      btn.style.opacity = (isTeam && !isCmd) ? '0.5' : '1';
      btn.style.pointerEvents = (isTeam && !isCmd) ? 'none' : 'auto';
    });
  }

  function columnsForPositions() {
    if (state.view === 'team') return []; // inert
    const cfg = PositionState.columnsByPosition || {};
    const sel = Array.from(PositionState.selected);
    if (!sel.length) return []; // None => leave autodetected columns
    const seen = new Set();
    const out = [];
    for (const p of sel) {
      const cols = cfg[p] || [];
      for (const c of cols) if (!seen.has(c)) { seen.add(c); out.push(c); }
    }
    return out;
  }

  function yyww(y, w) { return String(y % 100).padStart(2,'0') + String(w).padStart(2,'0'); }
  function fileUrl() {
    if (!M) return null;
    const map = (M.files[state.sport] && M.files[state.sport][state.year]) || {};
    return map[yyww(state.year, state.week)] || null;
  }

  async function fetchManifest() {
    const r = await fetch('/manifest', { cache: 'no-store' });
    if (!r.ok) throw new Error('manifest fetch failed');
    M = await r.json();
  }

  function populateYearsWeeks() {
    yearSel.innerHTML = '';
    const ys = (M.years[state.sport] || []).slice().sort((a,b)=>a-b);
    ys.forEach(y => {
      const o = document.createElement('option');
      o.value = String(y); o.textContent = String(y);
      yearSel.appendChild(o);
    });
    if (!ys.length) { state.year = null; state.week = null; return; }
    if (!state.year || !ys.includes(state.year)) state.year = ys[ys.length-1];
    yearSel.value = String(state.year);
    populateWeeksForYear();
  }

  function populateWeeksForYear() {
    weekSel.innerHTML = '';
    const ws = (M.weeks[state.sport] && M.weeks[state.sport][state.year]) ? M.weeks[state.sport][state.year] : [];
    ws.slice().sort((a,b)=>a-b).forEach(w => {
      const o = document.createElement('option');
      o.value = String(w); o.textContent = String(w);
      weekSel.appendChild(o);
    });
    if (!ws.length) { state.week = null; return; }
    if (state.week == null || !ws.includes(state.week)) state.week = ws[ws.length-1];
    weekSel.value = String(state.week);
  }

  async function loadData() {
    const url = fileUrl();
    if (!url) return showEmpty('No data for this selection.');
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) return showEmpty('Failed to load data.');
    const json = await r.json();
    const arrName = ARRAYS[state.sport][state.view];
    let rows = json[arrName] || [];
    if (!Array.isArray(rows)) rows = [];
    // compute columns (player/team)
    rows = rows.map(row => state.view === 'player' ? computePlayer(row) : computeTeam(row));
    state.data = rows;
    state.page = 1;
    state.idKey = (state.view === 'team') ? 'TeamID' : 'ID';
    const cols = deriveColumns(rows);
    applyFilterAndRender(cols);
  }

  function showEmpty(msg) {
    thead.innerHTML = ''; tbody.innerHTML = '';
    tbl.style.display = 'none';
    emptyMsg.textContent = msg || 'No data'; emptyMsg.style.display = 'block';
    pageInfo.textContent = '';
  }

function deriveColumns(rows) {
  // Start with auto
  const set = new Set();
  rows.slice(0, 200).forEach(r => Object.keys(r).forEach(k => set.add(k)));
  let cols = Array.from(set).sort();

  // id first
  cols = ensureIdFirst(cols, state.idKey);

  if (state.view === 'team') {
    const teamCols = getTeamColumnsForSport();
    if (teamCols.length) {
      cols = ensureIdFirst(teamCols, state.idKey);
    }
  } else {
    // player view: optionally override by positions
    const posCols = columnsForPositions();
    if (posCols.length) {
      cols = ensureIdFirst(posCols, state.idKey);
    }
  }
  return cols;
}
  // ---------- Calculations (edit freely) ----------
  function computePlayer(row) {
    // Read from both NFL/CFB naming variants you’ve seen
    const pyds = Number(row.PassingYards ?? row.PassingYds ?? 0);
    const ptd  = Number(row.PassingTDs ?? row.PassingTouchdowns ?? 0);
    const pint = Number(row.Interceptions ?? row.PassingInterceptions ?? 0);

    const ryds = Number(row.RushingYards ?? 0);
    const rtd  = Number(row.RushingTDs ?? row.RushingTouchdowns ?? 0);
    const rff  = Number(row.Fumbles ?? row.RushingFumbles ?? 0);

    const rec   = Number(row.Catches ?? row.ReceivingCatches ?? 0);
    const recyd = Number(row.ReceivingYards ?? 0);
    const rectd = Number(row.ReceivingTDs ?? row.ReceivingTouchdowns ?? 0);
    const recff = Number(row.ReceivingFumbles ?? 0);

    const fg = Number(row.FGMade ?? 0);
    const xp = Number(row.ExtraPointsMade ?? 0);


    row.Calc_PassingPoints   = Math.round((pyds/25), 1) + (ptd * 4) + (pint * -2);
    row.Calc_RushingPoints   = Math.round((ryds/10), 1) + (rtd * 6) + (rff * -2);
    row.Calc_KickingPoints = (fg * 3) + (xp * 1)
    row.Calc_ReceivingPoints = rec + Math.round((recyd/10), 1) + (rectd * 6) + (recff * -2);
    row.Calc_TotalPoints = row.Calc_PassingPoints + row.Calc_RushingPoints + row.Calc_ReceivingPoints + row.Calc_KickingPoints;
    return row;
  }

  function computeTeam(row) {
    const sacks = Number(row.SacksMade ?? 0);
    const ints  = Number(row.InterceptionsCaught ?? 0);
    const fRec  = Number(row.RecoveredFumbles ?? 0);
    const saf   = Number(row.Safeties ?? 0);
    const dtd   = Number(row.DefensiveTDs ?? 0);
    const ktd   = Number(row.KickReturnTDs ?? 0);
    const ptd   = Number(row.PuntReturnTDs ?? 0);

    const q1 = Number(row.Score1Q ?? 0), q2 = Number(row.Score2Q ?? 0),
          q3 = Number(row.Score3Q ?? 0), q4 = Number(row.Score4Q ?? 0),
          q5 = Number(row.Score5Q ?? 0), q6 = Number(row.Score6Q ?? 0),
          q7 = Number(row.Score7Q ?? 0), ot = Number(row.ScoreOT ?? 0);

    const ptsAllowed = q1+q2+q3+q4+q5+q6+q7+ot;

    let pointsScore = 0;
    if (ptsAllowed === 0) pointsScore = 10;
    else if (ptsAllowed <= 6) pointsScore = 7;
    else if (ptsAllowed <= 13) pointsScore = 4;
    else if (ptsAllowed <= 20) pointsScore = 1;
    else if (ptsAllowed <= 27) pointsScore = 0;
    else if (ptsAllowed <= 34) pointsScore = -1;
    else if (ptsAllowed >= 35) pointsScore = -4;

    row.Calc_DefensiveScore = (sacks*1) + (ints*2) + (fRec*2) + (saf*2) + (dtd*6);
    row.Calc_ReturnScore    = (ktd + ptd) * 6;
    row.Calc_PointsScore    = pointsScore;
    row.Calc_TotalTeamScore = row.Calc_DefensiveScore + row.Calc_ReturnScore + row.Calc_PointsScore;
    return row;
  }
  // ---------- /Calculations ----------

  function applyFilterAndRender(cols) {
    const q = (searchIn.value || '').trim().toLowerCase();
    if (q) {
      const k = state.idKey;
      state.filtered = state.data.filter(r => String(r?.[k] ?? '').toLowerCase().includes(q));
    } else {
      state.filtered = state.data.slice();
    }
    // filter by position (player view only)
    if (state.view === 'player' && PositionState.selected.size > 0) {
      state.filtered = state.filtered.filter(r => {
        const p = r?.Position || r?.position || null;
        return p && PositionState.selected.has(String(p));
      });
    }
    // sort
    if (state.sortKey) {
      const k = state.sortKey, dir = (state.sortDir === 'desc') ? -1 : 1;
      state.filtered.sort((a,b)=>{
        const A = a?.[k], B = b?.[k];
        const na = (typeof A === 'number') || (!isNaN(parseFloat(A)) && A !== '' && A != null);
        const nb = (typeof B === 'number') || (!isNaN(parseFloat(B)) && B !== '' && B != null);
        const va = na ? parseFloat(A) : String(A ?? '');
        const vb = nb ? parseFloat(B) : String(B ?? '');
        if (va < vb) return -1*dir;
        if (va > vb) return  1*dir;
        return 0;
      });
    }
    renderTable(cols, pageRows());
    renderPager();
  }

  function renderTable(cols, rows) {
    emptyMsg.style.display = rows.length ? 'none' : 'block';
    tbl.style.display = rows.length ? 'table' : 'none';
    thead.innerHTML = '';
    const trh = document.createElement('tr');
    cols.forEach(c => {
      const th = document.createElement('th');
      th.textContent = c; th.dataset.key = c;
      th.className = 'sv-sortable' + (state.sortKey === c ? (' ' + state.sortDir) : '');
      th.addEventListener('click', () => {
        if (state.sortKey === c) state.sortDir = (state.sortDir === 'asc') ? 'desc' : 'asc';
        else { state.sortKey = c; state.sortDir = 'asc'; }
        applyFilterAndRender(cols);
      });
      trh.appendChild(th);
    });
    thead.appendChild(trh);

    tbody.innerHTML = '';
    const frag = document.createDocumentFragment();
    rows.forEach(r => {
      const tr = document.createElement('tr');
      cols.forEach(c => {
        const td = document.createElement('td');
        const v = r?.[c];
        td.textContent = (v == null) ? '' : (typeof v === 'object' ? JSON.stringify(v) : String(v));
        tr.appendChild(td);
      });
      frag.appendChild(tr);
    });
    tbody.appendChild(frag);
  }

  function pageRows() {
    const start = (state.page - 1) * PAGE_SIZE;
    return state.filtered.slice(start, start + PAGE_SIZE);
  }
  function renderPager() {
    const total = state.filtered.length;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (state.page > pages) state.page = pages;
    pageInfo.textContent = `Page ${state.page} of ${pages} • ${total} row(s)`;
    pagePrev.disabled = (state.page <= 1);
    pageNext.disabled = (state.page >= pages);
  }

  function syncButtons() {
    btnSport.forEach(b => b.classList.toggle('active', b.dataset.sport === state.sport));
    btnView.forEach(b => b.classList.toggle('active', b.dataset.view === state.view));
    if (state.year != null) yearSel.value = String(state.year);
    if (state.week != null) weekSel.value = String(state.week);
    refreshChips();
  }

  function nextYear(delta) {
    const ys = (M.years[state.sport] || []).slice().sort((a,b)=>a-b);
    if (!ys.length) return;
    let i = ys.indexOf(state.year);
    i = Math.min(ys.length-1, Math.max(0, i + delta));
    state.year = ys[i];
    const avail = (M.weeks[state.sport][state.year] || []).slice().sort((a,b)=>a-b);
    if (!avail.length) { state.week = null; return; }
    if (state.week == null) { state.week = avail[avail.length-1]; return; }
    if (!avail.includes(state.week)) {
      const ge = avail.find(x => x >= state.week);
      state.week = (ge != null ? ge : avail[avail.length-1]);
    }
  }
  function nextWeek(delta) {
    const avail = (M.weeks[state.sport][state.year] || []).slice().sort((a,b)=>a-b);
    if (!avail.length) return;
    let i = avail.indexOf(state.week);
    if (i === -1) { state.week = avail[avail.length-1]; return; }
    i += delta;
    if (i < 0) {
      // hop to prev year end
      const ys = (M.years[state.sport] || []).slice().sort((a,b)=>a-b);
      const j = Math.max(0, ys.indexOf(state.year) - 1);
      state.year = ys[j];
      const av = (M.weeks[state.sport][state.year] || []).slice().sort((a,b)=>a-b);
      state.week = av.length ? av[av.length-1] : null;
    } else if (i >= avail.length) {
      // hop to next year start
      const ys = (M.years[state.sport] || []).slice().sort((a,b)=>a-b);
      const j = Math.min(ys.length-1, ys.indexOf(state.year) + 1);
      state.year = ys[j];
      const av = (M.weeks[state.sport][state.year] || []).slice().sort((a,b)=>a-b);
      state.week = av.length ? av[0] : null;
    } else {
      state.week = avail[i];
    }
  }

  function currentColumns() {
    // derive from current data or position preset
    const columns = deriveColumns(state.data || []);
    return columns;
  }

  function getTeamColumnsForSport() {
    const C = (window.SIMFBA_COLUMNS || {});
    const shared = (C.shared && Array.isArray(C.shared.team)) ? C.shared.team : [];
    const ov = (C.overrides && C.overrides[state.sport] && Array.isArray(C.overrides[state.sport].team))
      ? C.overrides[state.sport].team
      : [];
    // override wins if provided; otherwise shared
    return (ov.length ? ov : shared).slice();
  }

  function ensureIdFirst(cols, idKey) {
    const out = [];
    const seen = new Set();
    if (idKey) { out.push(idKey); seen.add(idKey); }
    for (const c of cols) {
      if (!seen.has(c)) { out.push(c); seen.add(c); }
    }
    return out;
  }

  // Events
  btnSport.forEach(b => b.addEventListener('click', async () => {
    state.sport = b.dataset.sport;
    buildPositionBar();
    populateYearsWeeks(); syncButtons(); await loadData();
  }));
  btnView.forEach(b => b.addEventListener('click', async (e) => {
    e.preventDefault();
    state.view = b.dataset.view;
    syncButtons(); await loadData();
  }));
  yearPrev.addEventListener('click', async () => { nextYear(-1); populateWeeksForYear(); syncButtons(); await loadData(); });
  yearNext.addEventListener('click', async () => { nextYear(1);  populateWeeksForYear(); syncButtons(); await loadData(); });
  weekPrev.addEventListener('click', async () => { nextWeek(-1); syncButtons(); await loadData(); });
  weekNext.addEventListener('click', async () => { nextWeek(1);  syncButtons(); await loadData(); });
  yearSel.addEventListener('change', async () => { state.year = parseInt(yearSel.value,10); populateWeeksForYear(); syncButtons(); await loadData(); });
  weekSel.addEventListener('change', async () => { state.week = parseInt(weekSel.value,10); syncButtons(); await loadData(); });
  searchIn.addEventListener('input', () => applyFilterAndRender(currentColumns()));
  pagePrev.addEventListener('click', () => { if (state.page>1){ state.page--; renderPager(); renderTable(currentColumns(), pageRows()); }});
  pageNext.addEventListener('click', () => {
    const total = state.filtered.length; const pages = Math.max(1, Math.ceil(total/50));
    if (state.page < pages){ state.page++; renderPager(); renderTable(currentColumns(), pageRows()); }
  });

  // Init
  (async function init(){
    await fetchManifest();
    state.sport = (M.defaults && M.defaults.sport) || 'nfl';
    state.view  = (M.defaults && M.defaults.view)  || 'team';
    state.year  = (M.defaults && M.defaults.year)  || null;
    state.week  = (M.defaults && M.defaults.week)  || null;
    buildPositionBar();
    populateYearsWeeks();
    syncButtons();
    await loadData();
  })();
})();
