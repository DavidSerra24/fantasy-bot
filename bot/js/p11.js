// Predicted11: omplir l'onze d'un equip, posar emoticones i Quiniela (provat al navegador del David).
window.__p11 = (function () {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/ø/g, 'o').replace(/ł/g, 'l').replace(/đ/g, 'dj').replace(/ı/g, 'i').replace(/\bfdez\b/g, 'fernandez').replace(/\bquique\b/g, 'kike').replace(/[^a-z0-9 .'-]/g, ' ');
  const toks = s => norm(s).replace(/[.'-]/g, ' ').split(/\s+/).filter(Boolean);
  function score(si, it) {
    const n = norm(it.nombre), c = norm(it.corto || ''); const sn = norm(si).replace(/\./g, '').trim();
    if (sn === n.replace(/\./g, '') || sn === c.replace(/\./g, '')) return 100; if (sn.replace(/[ '-]/g, '') === n.replace(/[ .'-]/g, '')) return 95;
    const st = toks(si), nt = toks(it.nombre).concat(toks(it.corto || ''));
    const full = st.filter(t => t.length > 1), ini = st.filter(t => t.length === 1);
    if (!full.length) return 0;
    const allIn = full.every(t => nt.includes(t));
    const iniOk = ini.every(i => nt.some(t => t[0] === i));
    const pt = toks(it.nombre).filter(t => t.length > 1); if (pt.length && pt.every(t => st.includes(t)) && !allIn) return 75; if (allIn && iniOk) return full.length > 1 ? 90 : (ini.length ? 85 : 70);
    const part = full.every(t => nt.some(x => x.startsWith(t) || t.startsWith(x) && x.length >= 3));
    if (part && iniOk) return 60;
    const lev = (a, b) => { const d = Array.from({ length: a.length + 1 }, (_, i) => [i]); for (let j = 1; j <= b.length; j++) d[0][j] = j; for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); return d[a.length][b.length]; };
    const fz = full.every(t => nt.some(x => lev(t, x) <= (t.length > 6 ? 2 : 1))); if (fz && iniOk) return 55;
    return 0;
  }
  function items() { return [...document.querySelectorAll('#playerList .player-item')].map(e => ({ el: e, id: e.dataset.id, nombre: e.dataset.nombre, corto: e.dataset.nombrecorto, pos: e.dataset.posicion })); }
  function match(si, list, used, wantPos) {
    let sc = list.filter(x => !used.has(x.id)).map(x => ({ x, s: score(si, x) })).filter(o => o.s >= 55);
    if (!sc.length) return { none: true };
    const max = Math.max(...sc.map(o => o.s)); let best = sc.filter(o => o.s === max);
    if (best.length > 1 && wantPos) { const b2 = best.filter(o => o.x.pos === wantPos); if (b2.length) best = b2; }
    if (best.length > 1 && new Set(best.map(o => norm(o.x.nombre))).size === 1) best = [best[0]]; // mateix jugador duplicat (amb/sense accent)
    if (best.length > 1) return { amb: best.map(o => o.x.nombre) };
    return { x: best[0].x, s: max };
  }
  function formation(rows) {
    let r = rows.map(x => x.slice()); const gk = r.shift();
    if (r[0].length === 3 && r[1] && r[1].length >= 4) { const m = r[1]; const lw = m.shift(), rw = m.pop(); r[0] = [lw, ...r[0], rw]; if (!m.length) r.splice(1, 1); }
    const D = r[0].length, F = r[r.length - 1].length;
    let f, sizes;
    if (D === 4) { if (F === 1) { f = '4-2-3-1'; sizes = [1, 4, 2, 3, 1]; } else if (F === 2) { f = '4-4-2'; sizes = [1, 4, 4, 2]; } else { f = '4-3-3'; sizes = [1, 4, 3, 3]; } }
    else if (D === 5) { if (F === 1) { f = '5-4-1'; sizes = [1, 5, 4, 1]; } else { f = '5-3-2'; sizes = [1, 5, 3, 2]; } }
    else { f = '4-3-3'; sizes = [1, 4, 3, 3]; }
    return { f, sizes, flat: [...gk, ...r.flat()] };
  }
  function slotsOrdered(sizes) {
    const s = [...document.querySelectorAll('.choose-slot-btn[data-slot]')].map(b => ({ b, slot: b.dataset.slot, top: parseFloat(b.style.top), left: parseFloat(b.style.left) }));
    s.sort((a, b) => b.top - a.top); const out = []; let i = 0;
    for (const n of sizes) { const ch = s.slice(i, i + n).sort((a, b) => a.left - b.left); out.push(...ch.map(x => x.slot)); i += n; }
    return out;
  }
  const posFor = (k, sizes) => { if (k === 0) return 'Portero'; if (k <= sizes[1]) return 'Defensa'; if (k >= 11 - sizes[sizes.length - 1]) return 'Delantero'; return 'Mediocampista'; };
  async function reset() {
    const on = [...document.querySelectorAll('#campoAlineacion .player-on-field')].filter(e => e.offsetParent !== null);
    if (on.length) { const rb = document.getElementById('resetFieldBtn'); if (!rb) return; const oc = window.confirm; window.confirm = () => true; rb.click(); await sleep(1500);
      const cb = document.getElementById('confirmResetBtn'); if (cb && cb.offsetParent !== null) { cb.click(); await sleep(1500); } window.confirm = oc; }
  }
  async function fill(rows, opts = {}) {
    const log = { unmatched: [], amb: [] };
    await reset();
    const { f, sizes, flat } = formation(rows);
    document.getElementById('tacticaSelector').tomselect.setValue(f); await sleep(1200);
    const order = slotsOrdered(sizes); log.formation = f;
    const used = new Set(); const placed = [];
    for (let k = 0; k < flat.length; k++) {
      const p = flat[k]; const btn = document.querySelector('.choose-slot-btn[data-slot="' + order[k] + '"]');
      if (!btn) { log.unmatched.push(p.name + ' (no slot)'); continue; }
      btn.click(); await sleep(700);
      const list = items(); let m = match(p.name, list, used, posFor(k, sizes));
      if (!m.x && (p.subs || []).length) { // no és a Predicted11: posar el suplent que indica SorareInside
         const m2 = match(p.subs[0].name, list, used, posFor(k, sizes)); if (m2.x) { log.subbed = (log.subbed || []).concat(p.name + '→' + m2.x.nombre); m = m2; } }
      if (m.x) { used.add(m.x.id); m.x.el.click(); placed.push({ si: p.name, p11: m.x.nombre, id: m.x.id, s: m.s }); await sleep(900); }
      else { if (m.amb) log.amb.push(p.name + ' → ' + m.amb.join(' / ')); else log.unmatched.push(p.name);
        document.getElementById('closePlayerSelector')?.click();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await sleep(500); }
    }
    log.placed = placed; return log;
  }
  async function setIcon(id, label) {
    const card = [...document.querySelectorAll('#campoAlineacion .player-on-field[data-id="' + id + '"]')].find(e => e.offsetParent !== null); if (!card) return 'nocard';
    card.querySelector('.p11-player-icon').click(); await sleep(600);
    const opt = [...document.querySelectorAll('.p11-icon-menu__option')].find(o => o.offsetParent !== null && o.textContent.trim() === label);
    if (!opt) return 'noopt'; opt.click(); await sleep(1200);
    document.querySelector('.p11-icon-menu__close')?.click(); return 'ok';
  }
  // Normes d'emoticones del David.
  function pickIcons(placed, golOv) {
    const cmp = (a, b) => (b.ps - a.ps) || ((b.pct || 0) - (a.pct || 0)) || ((a.nsubs || 0) - (b.nsubs || 0));
    const P = placed.filter(p => p.ps != null);
    const maxG = Math.max(0, ...placed.map(p => p.goals || 0));
    let gol = null, rec = null;
    if (maxG > 0) { const top = placed.filter(p => (p.goals || 0) === maxG).sort((a, b) => cmp({ ...a, ps: a.ps ?? -1 }, { ...b, ps: b.ps ?? -1 }));
      if (top.length > 1 && top[0].ps != null) { rec = top[0]; gol = top[1]; } else { gol = top[0]; } }
    if (!gol && golOv) { gol = placed.find(p => p.si === golOv || p.p11 === golOv) || null; }
    if (!gol) { const maxRow = Math.max(...placed.map(p => p.row ?? 0)); let fw = placed.filter(p => (p.row ?? 0) === maxRow); if (fw.length === 2) { const it = items(); const dl = fw.filter(p => (it.find(x => x.id === p.id) || {}).pos === 'Delantero'); if (dl.length === 1) fw = dl; } gol = fw.length === 1 ? fw[0] : (fw.length === 3 ? fw[1] : fw.slice().sort((a, b) => cmp({ ...a, ps: a.ps ?? -1 }, { ...b, ps: b.ps ?? -1 }))[0]); }
    if (!rec) { rec = P.filter(p => p !== gol).sort(cmp)[0] || null; }
    const no = P.filter(p => p !== gol && p !== rec).sort((a, b) => (a.ps - b.ps) || ((a.pct || 0) - (b.pct || 0)) || ((b.nsubs || 0) - (a.nsubs || 0)))[0] || null;
    return { gol, rec, no };
  }
  async function icons(placed, golOv) {
    const { gol, rec, no } = pickIcons(placed, golOv); const r = {}; const want = {}; if (gol) want[gol.id] = 'Goleador'; if (rec) want[rec.id] = 'Recomendable'; if (no) want[no.id] = 'No recomendable';
    for (const card of [...document.querySelectorAll('#campoAlineacion .player-on-field')].filter(x => x.offsetParent !== null)) { const ic = card.querySelector('.p11-player-icon'); if (ic && ic.dataset.icon && !want[card.dataset.id]) await setIcon(card.dataset.id, 'Sin icono'); }
    if (gol) r.Goleador = gol.p11 + ' ' + await setIcon(gol.id, 'Goleador');
    if (rec) r.Recomendable = rec.p11 + ' ' + await setIcon(rec.id, 'Recomendable');
    if (no) r['No recomendable'] = no.p11 + ' ' + await setIcon(no.id, 'No recomendable');
    return r;
  }
  function state() {
    const on = [...document.querySelectorAll('#campoAlineacion .player-on-field')].filter(e => e.offsetParent !== null);
    return { tactic: document.getElementById('tacticaSelector')?.value, n: on.length, icons: on.filter(e => e.querySelector('.p11-player-icon')?.dataset.icon).length,
      names: on.map(e => e.dataset.id) };
  }
  // Omple un equip. entry = {rows}, prev = {sig, placed} desat de l'última vegada (o null).
  async function runTeam(entry, prev, golOv) {
    const sig = entry.rows.map(r => r.map(p => p.name).join(',')).join('|');
    const st = state(); let res = prev && prev.placed ? prev : null; let msg = '';
    if (!res || prev.sig !== sig || st.tactic === 'Manual' || st.n < 11) {
      const log = await fill(entry.rows, { subFallback: ['Matteo Darmian', 'Darmian'] });
      res = { sig, formation: log.formation, placed: log.placed }; msg = 'FILLED ' + log.formation + ' ' + log.placed.length + (log.unmatched.length ? ' UN:' + log.unmatched.join(',') : '') + (log.amb.length ? ' AMB:' + log.amb.join(',') : '') + (log.subbed ? ' SUBSTITUT:' + log.subbed.join(',') : '');
    }
    if (!res.placed || res.placed.length < 11) { res.msg = (msg || '') + ' (icones no tocades: onze incomplet)'; return res; }
    const flat = entry.rows.flat();
    const placed = res.placed.map(p => { const d = flat.find(x => x.name === p.si) || {}; return { ...p, ps: d.ps ?? null, goals: d.goals || 0, pct: d.pct, nsubs: (d.subs || []).length, row: d.row }; });
    res.icons = await icons(placed, golOv);
    res.msg = msg; return res;
  }
  // Si en recarregar surt "Manual", tornar a posar la tàctica.
  async function fixTactic(f) { const sel = document.getElementById('tacticaSelector'); const before = sel.value; if (before === 'Manual' && f) { sel.tomselect.setValue(f); await sleep(3500); } return before + '->' + sel.value; }
  // Quiniela: picks = [[local, visitant, gols_local, gols_visitant], ...]. Clics sense esperes (molt més ràpid).
  function quiniela(picks) {
    const n2 = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const boxes = [...document.querySelectorAll('.partido-quiniela')].map(b => ({ b, l: n2(b.querySelector('.equipo-local .equipo-nombre').textContent), v: n2(b.querySelector('.equipo-visitante .equipo-nombre').textContent) }));
    const log = [];
    for (const [h, a, gh, ga] of picks) { const H = n2(h), A = n2(a);
      const bx = boxes.find(x => (x.l.includes(H) || H.includes(x.l)) && (x.v.includes(A) || A.includes(x.v))); if (!bx) { log.push('NOMATCH ' + h + '-' + a); continue; }
      const st = [...bx.b.querySelectorAll('.stepper-container')];
      for (const [c, t] of [[st[0], gh], [st[1], ga]]) { const inp = c.querySelector('input'); const btn = s => [...c.querySelectorAll('.stepper-btn')].find(b => b.textContent.trim() === s);
        for (let i = 0; i < 12; i++) { const v = inp.value; const n = v === '-' ? -1 : +v; if (n === t) break; (n < t ? btn('+') : btn('–')).click(); } }
      log.push(h + ' ' + st[0].querySelector('input').value + '-' + st[1].querySelector('input').value + ' ' + a); }
    return log;
  }
  return { fill, icons, pickIcons, state, match, items, runTeam, fixTactic, quiniela };
})();
