# fantasy-bot

Automatitzacions setmanals: Predicted11, FutbolFantasy (Fantasy✨), Sorare (Set i Pro) i Mister.
Corre en una VM Oracle Always Free (Ubuntu 24.04 ARM, Europe/Madrid) amb cron + Playwright.

## Instal·lació al servidor
```bash
git clone https://github.com/DavidSerra24/fantasy-bot.git
cd fantasy-bot
./scripts/setup.sh
nano .env            # omple-ho tu: tokens i contrasenyes
.venv/bin/python -m bot.selftest
```

## Actualitzar
```bash
cd ~/fantasy-bot && git pull
```

## Normes de seguretat
- Les contrasenyes només viuen a `.env` del servidor (no es pugen mai a GitHub).
- Cap script compra, ven ni intercanvia cartes de Sorare, ni fa dipòsits o retirades.
- Despesa d'essència a Arenes: mai automàtica.

## Mòduls (pendents)
- [ ] predicted11
- [ ] futbolfantasy
- [ ] sorare (set / pro)
- [ ] mister
