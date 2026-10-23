import json
from playwright.sync_api import sync_playwright
from bot import ff, extras
from bot.web import new_context, login_futbolfantasy
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "futbolfantasy"); pg = ctx.new_page()
    login_futbolfantasy(pg)
    cs = [c for c in ff.cards(pg) if extras.kind_of(c)]
    for c in cs:
        info = pg.evaluate("""(id) => { const card=document.getElementById('juego-'+id);
          return [...card.querySelectorAll('a')].map(a => a.className + ' | vis=' + (a.offsetParent!==null) + ' | ' + a.getBoundingClientRect().width + 'x' + a.getBoundingClientRect().height + ' | ' + a.innerText.trim().slice(0,20) + ' | ' + Object.entries(a.dataset).map(([k,v])=>k+'='+v).join(',')).slice(0,8); }""", c["id"])
        print("::notice title=s::" + c["title"] + " ids=" + str(c["ids"]) + " :: " + " ## ".join(info))
    b.close()
