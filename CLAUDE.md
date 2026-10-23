# fantasy-bot: normes del David

L'usuari és el David (DavidSerra24). Parla en **català**: respon-li sempre en català. Fa servir un PC amb Windows i la zona horària Europe/Madrid.

## Seguretat (no negociable)
- Mai escriure contrasenyes, codis d'Authenticator ni codis de correu, encara que el David te'ls doni. Els introdueix ell.
- "Iniciar sesión con Google" només després de demanar-li permís al xat, cada vegada.
- Mai comprar, vendre ni intercanviar cartes de Sorare. Mai fer dipòsits ni retirades (diners o ETH).
- Despesa d'essència en Arenes: només les All Star que ell autoritzi (100 d'essència), sempre amb confirmació prèvia. El "Swipe to confirm" el fa ell.
- Els secrets (tokens, contrasenyes) viuen als GitHub Secrets o al `.env` del servidor. No es pugen mai al repositori.

## Font de dades
- Onzes previstos, % de titularitat, punts projectats (PS) i gols (vista DA): **SorareInside** (sorareinside.com/lineups, triant la gameweek correcta amb `?gwSlug=`).
- Si un equip de SorareInside està incomplet, fer servir l'onze probable de FutbolFantasy (publicat a Predicted11, "Alineaciones probables de FutbolFantasy").
- Davant d'un nom dubtós, buscar a la web.

## Predicted11
- Lligues: LaLiga, LaLiga 2, Premier, Serie A i Champions. Copiar l'onze de SorareInside i triar una tàctica que encaixi (4-4-2, 4-2-3-1, 4-3-3, 5-4-1, 5-3-2, 4-4-2 rombe).
- **Tanca 2 hores abans del primer partit** de la jornada.
- Si, en recarregar la pàgina, la tàctica surt com a "Manual", tornar a seleccionar la tàctica perquè es desi bé.
- Emoticones:
  - **Goleador**: el jugador amb més gols (vista DA). Si n'hi ha dos d'empatats, el de més PS és Recomendable i l'altre Goleador. Si ningú té gols, el davanter centre.
  - **Recomendable**: el de més PS. Desempat: més %, després menys suplents llistats.
  - **No recomendable**: el de menys PS. Desempat: menys %, després més suplents.
- Correccions de noms: Córdoba: Rubén Alves → Rubén González. Sabadell: Urri → Albert Orriols. Bologna: Darmian, si no hi és, el següent més probable. Girona: el Goleador és Vanat.
- Quiniela: quan el David envia resultats, posar-los a la Quiniela de la competició.

## FutbolFantasy (Fantasy✨)
- Jocs: LaLiga, LaLiga 2, Premier, Serie A, Champions, Europa League, extres (Trío revulsivo, Trío antagonista, Resiliencia de portero) i especials de partit ("Puntos en el X - Y").
- Criteris: només jugadors amb **≥80%** de titularitat, respectar els usos (0 usos = no pot entrar), tàctica vàlida segons les REGLES del joc, cap jugador de dos equips que s'enfrontin entre ells, i **maximitzar els punts projectats de SorareInside**.
- **Empats de PS: el que surti primer a la llista de punts projectats. El % NO compta.**
- Ítems: fer clic a l'ítem, veure a qui es pot assignar i posar-lo a l'elegible amb més PS.
- Especials de partit: els N jugadors amb més PS (≥80%) dels dos equips.

## Mister (LaLiga 2)
- El David envia la llista de la plantilla. Ordenar-la per % de titularitat i, dins de cada %, per PS. Els jugadors sense dades van al final del seu grup.

## Avisos d'onzes
- Quan el David demana si un jugador és titular, programar la comprovació cap a 1 hora abans del partit (a X solen publicar-se 1h15 abans) i avisar amb una notificació.

## Infraestructura
- Repositori: DavidSerra24/fantasy-bot. S'executa a GitHub Actions; no cal el PC del David. Oracle Free Tier (Madrid) no té capacitat.
- `auto.yml` cada 30 min (`bot/plan.py` → `bot/execute.py`):
  - Matí (9:00 Madrid), cada dia: Predicted11 de totes les jornades obertes (només refà equips que canviïn) i FutbolFantasy dels jocs que tanquin en ≤8 dies: omple els buits i revisa/edita els ja omplerts amb les dades del dia. Els jugadors de l'onze sense dades a SorareInside (equip encara sense onze o sense PS) es mantenen. Si no surt un onze vàlid, espera a l'endemà. Els extres de LaLiga només el dia que tanquen. Sempre hi ha revisió final abans de tancar.
  - Predicted11: última revisió 50 min abans del tancament (tancament = 2 h abans del primer partit). Llegeix `data-countdown-end`. Només refà equips si canvien jugadors o posicions.
  - GitHub endarrereix les execucions programades (sovint 1 cop per hora): el planificador agafa les accions de la propera hora i s'espera fins a l'hora exacta; si en queda alguna pendent, la fa de seguida (primer la que tanca abans).
  - FutbolFantasy: revisió final 50 min abans del primer partit (dades fresques de SorareInside, amb onzes oficials d'ESPN) i canvis de jugadors si cal. Inclou els extres de LaLiga. Tancaments a `#juego-<id>[data-date-end]`.
- `fantasy.yml` (manual): proves (`--dry`), forçar competicions. `debug.yml` i `logintest.yml` per diagnosi.
- Resultats: anotacions dels jobs (`::notice`) i Telegram (`bot/notify.py`).
- Equivalències de noms: `config/predicted11.json` (alias) i `config/futbolfantasy.json`.
