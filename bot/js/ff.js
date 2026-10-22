// FutbolFantasy Fantasy✨: lectura de jocs i del selector de jugadors.
window.__ff = (function () {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // Jocs de la pàgina (/fantasy/activas): id, etiqueta, títol, temps restant i places buides.
  function games() {
    const ids = [...new Set([...document.querySelectorAll('a.fantasy-add[data-juego]')].map(a => a.dataset.juego))];
    const out = [];
    for (const id of ids) {
      const a = document.querySelector('a.fantasy-add[data-juego="' + id + '"]');
      let c = a; while (c && !/Tiempo restante/.test(c.innerText || '')) c = c.parentElement;
      const txt = (c ? c.innerText : '').split('\n').map(s => s.trim()).filter(Boolean);
      const label = txt.find(s => /·/.test(s)) || txt[0] || '';
      const title = txt.find(s => /Jornada|Puntos en|Trío|Resiliencia/i.test(s) && s !== label) || '';
      const rem = (txt.find(s => /Tiempo restante/.test(s)) || '').replace('Tiempo restante:', '').trim();
      out.push({ id, label, title, rem, empty: document.querySelectorAll('a.fantasy-add[data-juego="' + id + '"]').length });
    }
    return out;
  }
  // Tots els jocs de la pàgina (també els plens): id, etiqueta, tancament (hora de Madrid) i jugadors triats.
  function cards() {
    return [...document.querySelectorAll('.fantasy-juego[id^="juego-"]')].map(c => {
      const txt = c.innerText.split('\n').map(s => s.trim()).filter(Boolean);
      let ids = []; try { ids = JSON.parse(c.dataset.filtrar || '[]'); } catch (e) {}
      return { id: c.dataset.id, label: txt.find(s => /·/.test(s)) || txt[0] || '', title: txt.find(s => /Jornada|Puntos en|Trío|Resiliencia/i.test(s)) || '',
               end: c.dataset.dateEnd || null, ids, empty: c.querySelectorAll('a.fantasy-add').length,
               slots: [...c.querySelectorAll('a.fantasy-slot')].map(a => +a.dataset.posicion) };
    });
  }
  // Resultats visibles del selector obert.
  function results() {
    const m = document.querySelector('.modal.show'); if (!m) return null;
    return [...m.querySelectorAll('.sel-item')].filter(e => e.offsetParent !== null).map(e => ({
      id: e.dataset.id, n: e.querySelector('.sel-nombre')?.textContent.trim(), p: e.querySelector('.sel-pos')?.textContent.trim(),
      u: ((e.innerText.match(/(\d+)\s*\/\s*\d+/) || [])[1] ?? null), t: (e.querySelector('.sel-escudo')?.src || '').split('/').pop().replace('.png', '') }));
  }
  async function search(q) {
    const m = document.querySelector('.modal.show'); if (!m) return null;
    const i = m.querySelector('input[type=text]'); i.value = q; i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    await sleep(900); return results();
  }
  function rules() { const m = document.querySelector('.modal.show'); return m ? m.innerText : null; }
  return { games, cards, results, search, rules };
})();
