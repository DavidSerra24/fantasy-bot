// SorareInside: extracció d'onzes previstos (provat al navegador del David).
// window.__si: navegació (lliga, obrir/tancar equip). window.__si2: extracció per files.
window.__si = (function () {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const dlg = () => document.querySelector('[role="dialog"]');
  const rows = () => { const d = dlg(); if (!d) return null; const f = d.querySelector('[class*="_field_"]'); if (!f) return null; return [...f.children].filter(c => c.className.includes('Group-root')).map(r => [...r.children]); };
  const sname = s => { const ps = [...s.querySelectorAll('p')].map(p => p.textContent.trim()).filter(t => t && !/^\d+%?$/.test(t) && t !== '-'); return ps[0] || null; };
  const starters = () => { const r = rows(); return r ? r.flat().filter(s => sname(s)) : []; };
  async function openTeam(name) {
    const a = [...document.querySelectorAll('main a')].find(a => a.getAttribute('href') === null && a.textContent.trim() === name); if (!a) return 'noanchor';
    a.click();
    for (let i = 0; i < 60; i++) { await sleep(400); const d = dlg(); if (d && d.innerText.split('\n')[0].trim() === name) { if (/Recent Lineups/.test(d.innerText.slice(0, 200))) return 'recent'; if (starters().length >= 11) return 'ok'; if (i > 20 && /Not enough starting players/.test(d.innerText)) return 'incomplete'; } }
    return 'timeout';
  }
  async function close() { for (let i = 0; i < 10; i++) { const d = dlg(); if (!d) return; const b = d.querySelector('button.mantine-Modal-close') || d.querySelector('button'); b && b.click(); await sleep(500); } }
  async function league(country, lg) { const all = [...document.querySelectorAll('main *')].filter(e => e.childElementCount === 0); let cur = null; for (const e of all) { const t = e.textContent.trim(); if (t === country) cur = country; else if (cur === country && t === lg) { e.click(); await sleep(2500); return 'ok'; } } return 'nf'; }
  function anchors() { return [...document.querySelectorAll('main a')].filter(a => a.getAttribute('href') === null && a.textContent.trim()).map(a => a.textContent.trim()); }
  return { league, anchors, openTeam, close };
})();

window.__si2 = (function () {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const dlg = () => document.querySelector('[role="dialog"]');
  function slotRows() { const d = dlg(); const f = d && d.querySelector('[class*="_field_"]'); if (!f) return []; const rs = [...f.children].filter(c => c.className.includes('Group-root')).map(r => [...r.children].filter(s => s.getAttribute('data-has-player'))); rs.sort((a, b) => Math.min(...a.map(s => +s.dataset.lineupPositionIndex)) - Math.min(...b.map(s => +s.dataset.lineupPositionIndex))); return rs.filter(r => r.length); }
  function subs(s) { return [...s.querySelectorAll(':scope > .mantine-Group-root')].map(g => { const ps = [...g.querySelectorAll('p')].map(p => p.textContent.trim()); return { name: ps[0], pct: parseInt(ps[1]) || null }; }); }
  function goalsOf(s) { const gi = [...s.querySelectorAll('img')].find(im => /\/goal_icon\.svg$/.test(im.getAttribute('src') || '')); if (!gi) return 0; const b = gi.parentElement.querySelector('span'); return b ? (+b.textContent.trim() || 1) : 1; }
  function iconCount() { return slotRows().flat().reduce((a, s) => a + s.querySelectorAll('img[src$="_icon.svg"]').length, 0); }
  async function view(lbl) { const d = dlg(); const l = [...d.querySelectorAll('label')].find(b => b.textContent.trim() === lbl); l && l.click(); await sleep(500); }
  async function extract() {
    await view('% + PS'); await sleep(400);
    const rows = slotRows().map(r => r.map(s => { const leaves = [...s.querySelectorAll('*')].filter(e => e.childElementCount === 0).map(e => e.textContent.trim()); const pi = leaves.findIndex(x => /^\d+%$/.test(x)); return { name: s.dataset.hasPlayer, pct: pi >= 0 ? parseInt(leaves[pi]) : null, ps: (pi >= 0 && /^\d+$/.test(leaves[pi + 1] || '')) ? +leaves[pi + 1] : null, subs: subs(s) }; }));
    await view('DA');
    let last = -1, stable = 0; for (let i = 0; i < 20; i++) { await sleep(700); const c = iconCount(); if (c === last) { stable++; if (stable >= 3) break; } else { stable = 0; last = c; } }
    const sr = slotRows(); rows.forEach((r, i) => r.forEach((p, j) => { p.goals = goalsOf(sr[i][j]); }));
    await view('% + PS');
    return rows;
  }
  // Extreu un sol equip (Python fa el bucle per evitar límits de temps).
  async function team(t) { const st = await __si.openTeam(t); let out; if (st === 'ok') { try { out = await extract(); } catch (e) { out = { err: String(e) }; } } else out = { st }; await __si.close(); await sleep(500); return out; }
  return { extract, team, slotRows };
})();
