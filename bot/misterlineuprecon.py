"""Reconeixement (només lectura) de l'alineació i la quiniela del Mister per l'API interna. No canvia res.
Ús: python -m bot.misterlineuprecon"""
import json
import re

from bot.misterapi import MisterAPI, U

api = MisterAPI().login()
out = []
sq = lambda x: re.sub(r"\s+", " ", x)
for cid in (2499621,):
    api.community(cid)
    html = api.page("/team")
    navs = re.findall(r'<a[^>]*class="[^"]*gameweek[^"]*"[^>]*>[\s\S]*?</a>', html)
    out.append("navs: " + " || ".join(sq(n)[:300] for n in navs[:12]))
    nxt = next((n for n in navs if re.search(r"Comen[çc]a|Empieza|Comienza", n)), None)
    href = re.search(r'href="([^"]+)"', nxt).group(1) if nxt else None
    out.append(f"next href: {href}")
    if href:
        h2 = api.page("/" + href.lstrip("/").replace(U + "/", ""))
        out.append("botons: " + " | ".join(sq(b) for b in re.findall(r"<button[^>]*?lineup-player[\s\S]*?>", h2)[:12]))
        out.append("formació: " + " | ".join(sq(b) for b in re.findall(r"<button[^>]*?data-popup=\"formation\"[\s\S]*?>", h2)[:2]))
        m = re.search(r"_FG_cfg\s*=\s*(\{.*?\});", h2, re.S)
        cfg = {}
        try:
            cfg = json.loads(m.group(1)) if m else {}
        except Exception:
            pass
        out.append("paths: " + json.dumps(cfg.get("paths"))[:500] + " | keys: " + ", ".join(list(cfg.keys())[:80]))
        for k in ("manager", "id_manager", "managerId", "manager_id", "bemanager"):
            for mm in re.finditer(k + r'["\']?\s*[:=]\s*["\']?([\w-]+)', h2):
                out.append(f"{k} = {mm.group(1)}"); break
        for mm in re.finditer(r"data-manager-id=\"([^\"]+)\"", h2):
            out.append("data-manager-id = " + mm.group(1)); break
        views = (cfg.get("paths") or {}).get("views") or ""
        for t in ("popups/formation.twig", "sw/substitution.twig", "sw/subs.twig", "popups/pool.twig", "sw/pools.twig", "sw/pool-public.twig", "sw/pool-private.twig", "ajax/pools.twig"):
            url = views + "/" + t if views.startswith("http") else U + views + "/" + t
            try:
                r = api.s.get(url, timeout=20)
                body = r.text
                out.append(f"TWIG {t} {r.status_code}: " + " ## ".join(sq(x) for x in re.findall(r"<(?:button|input|div)[^>]*(?:data-[\w-]+=)[^>]*>", body)[:15])[:2500])
            except Exception as e:
                out.append(f"TWIG {t}: {e}")
        # finestra de substitució d'una casella (només lectura)
        b = re.search(r"<button[^>]*?lineup-player[\s\S]*?>", h2)
        if b:
            data = dict(re.findall(r'data-([\w-]+)="([^"]*)"', b.group(0)))
            for post in ("substitution", "subs"):
                try:
                    d = api.ajax("sw/" + post, dict(data, post=post))
                    out.append(f"sw/{post} {json.dumps(data)} → " + json.dumps(d)[:2500])
                except Exception as e:
                    out.append(f"sw/{post}: {e}")
        try:
            d = api.ajax("sw/pool-public", {"post": "pool-public"})
            out.append("sw/pool-public → " + json.dumps(d)[:2500])
        except Exception as e:
            out.append(f"sw/pool-public: {e}")
for o in out:
    print("RECON| " + o[:3000])
