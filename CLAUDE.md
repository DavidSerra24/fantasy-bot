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
  - Recordatori automàtic (`quinrem`): 26 h i 5 h abans del tancament de Predicted11, si la quiniela està buida, el bot envia per Telegram els partits i com respondre.
  - També es pot enganxar directament al xat del bot la resposta del Grok (taula amb capçaleres «Serie A – Jornada N», «Premier League», «LaLiga EA Sports», «LaLiga Hypermotion»…, en Markdown o sense format): `parse_grok` en treu els resultats de cada competició i el pronòstic 1/X/2 es descarta.
  - Amb els mateixos resultats el bot fa també la **Quiniela del Mister** (1 X 2; guanya local → 1, empat → X, guanya visitant → 2; `bot/misterpool.py`): LaLiga → «Oficial» i «Comunitat» de Fentaniños; LaLiga 2 → «Comunitat» de Quique. Mercat → `[data-sw=pool-public]`, pestanya `button[data-sw=pool-private]`, files `ul.pool-games > li` (`.left .name` / `.right .name`, `button.btn-pools[data-id_match][data-prediction]`). Pendent: confirmar quina classe marca el botó triat (es comprova recarregant).
  - Ordre de Telegram: `/quiniela [laliga|laliga2|premier|serie a|champions]` + un partit per línia («Local 2-1 Visitant»). Sense competició, la de l'últim recordatori. El planificador llegeix els missatges a cada execució (`getUpdates`, `state/tg_offset.json`).

## FutbolFantasy (Fantasy✨)
- Jocs: LaLiga, LaLiga 2, Premier, Serie A, Champions, Europa League, extres (Trío revulsivo, Trío antagonista, Resiliencia de portero) i especials de partit ("Puntos en el X - Y").
- Criteris: només jugadors amb **≥80%** de titularitat, respectar els usos (0 usos = no pot entrar), tàctica vàlida segons les REGLES del joc, cap **porter o defensa** amb cap jugador de l'equip rival (només resten punts els gols encajats als porters i defenses; migcampistes i davanters de dos equips rivals sí que poden anar junts — decisió del David, 28/10), i **maximitzar els punts projectats de SorareInside**.
- **Empats de PS: el que surti primer a la llista de punts projectats. El % NO compta.**
- Ítems: fer clic a l'ítem, veure a qui es pot assignar i posar-lo a l'elegible amb més PS.
- Especials de partit: els N jugadors amb més PS (≥80%) dels dos equips.
- Extra de gols de Copa del Rey (`bot/copa.py`, manual: `debug.yml` amb `bot.copa [--joc ID]`): un davanter per equip, el de l'onze probable de FutbolFantasy (`/copa-del-rey/posibles-alineaciones`; a la Copa no hi ha %, s'agafa el primer davanter titular).

## Sorare Set (mode gratuït; en preparació, encara no automatitzat)
- Obre sobres cada dia. Dos taulers: el **personal** i el **d'equip** (amb 9 persones més, cal arribar a uns punts per avançar).
- Fins a 4 alineacions per nivell. No es repeteixen jugadors entre alineacions (si ja hi ha un jugador, a la següent se salta encara que en tingui una altra carta).
- De cada jugador, la carta amb **més experiència**.
- Ordre: mitjana de punts (de més a menys). Desempat: més experiència, després la lletra d'impacte (A > B > C > D…), després el que surt primer a la llista.
- No posar jugadors de dos equips que s'enfrontin (es queda el de més mitjana). **Excepció**: si els dos són davanters, sí que es poden posar.
- Esperar que Sorare marqui els jugadors com a titulars (així s'actualitzen les lletres d'impacte).
- **Tauler personal**: filtre "Playing soon" (primer els que juguen abans). Si a l'hora del partit no hi ha prou titulars confirmats, completar amb els següents que tinguin ≥80% de titularitat.
- **Tauler d'equip**: filtre "Average score" (jugadors de tot el dia). Esperar els onzes del primer partit del dia; si no hi ha cap jugador a posar, esperar als següents partits i fer l'alineació quan toqui posar un titular.
- Accés: el David entra amb Google + Authenticator. El bot no pot fer-ho sol; extreure la sessió des del navegador està bloquejat per seguretat. Pendent (25/10): investigar l'API oficial de Sorare (api.sorare.com/graphql). Alternativa: fer-ho des del navegador de l'app amb el PC engegat. El Set són les "series" (sorare.com/football/series/play; tauler d'equip a /series/squad).

## Mister (automàtic)
- Dues lligues: **"Quique Carcel…"** (LaLiga 2) i **"Fentaniños"** (LaLiga).
- Font del % de titularitat per al mercat:
  - LaLiga 2: SorareInside (Segunda División). Franges: 80–90% → 70% → 60%.
  - LaLiga: **FutbolFantasy, "Mis equipos"** (filtre de forma i probabilitat). Mínim per fitxar: **70%** (entre 70 i 95%); si baixa del 70%, es ven. El David hi té els jugadors del Mister: quan el bot compri o vengui, ha d'actualitzar també "Mis equipos".
- Consulta manual: el David envia la llista de la plantilla. Ordenar-la per % de titularitat i, dins de cada %, per PS. Els jugadors sense dades van al final del seu grup.
- **Alineació** (automàtica; tanca a l'inici del primer partit de la jornada): primer els jugadors amb 80–90% ordenats per PS de SorareInside; si no n'hi ha prou, després els de 70% i després els de 60%. Dins de cada franja, primer els que tenen PS i al final els que no. **Sí que es poden posar jugadors d'equips que s'enfronten.** El Mister també mostra qui és titular (fer-ho servir a la revisió final).
- **Tàctica**: la que convingui segons els jugadors triats. **Capità**: el titular amb més PS.
- **Horaris del mercat**: els jugadors nous surten a les **5:00**; les ofertes per als jugadors posats en venda arriben a les **17:00** i a les **5:00**.
- **Mercat** (sense confirmació; són diners virtuals del joc):
  - Compres: primer la franja més alta (80–90%, després 70%, després 60%; a LaLiga 70–95% de FutbolFantasy) i, dins de cada franja, **del més barat al més car**, pujant el **preu mínim del mercat**. Es pot pujar fins on permeti el saldo negatiu màxim.
  - Si falten jugadors per completar alguna posició de l'onze: primer es puja per jugadors d'aquella posició, però **només si tenen el % mínim** (Quique 60%) i **sempre pel preu mínim**. Els que falten, el David els aconsegueix amb **cessions els divendres al matí**.
  - Vendes durant la setmana: jugadors per sota del mínim (LaLiga 2: <60% a SorareInside; LaLiga: <70% a FutbolFantasy).
  - **El dia que comença la jornada, abans de les 17:00**: posar en venda jugadors de menys a més PS fins que el bot calculi que es pot saldar el deute, **més un jugador de marge**. Saldo negatiu en començar la jornada = 0 punts.
  - **Mai vendre si la plantilla deixa de poder fer un onze vàlid**: com a mínim 1 porter, 1 davanter i prou defenses i migcampistes per completar l'onze.
- Accés: correu + contrasenya als GitHub Secrets (MISTER_EMAIL, MISTER_PASSWORD). La web és accessible des de GitHub (API interna a /api2/). Galetes: el bot clica "Aceptar y continuar" (autoritzat pel David; "Rechazar" obliga a subscriure's).
- Tècnic (`bot/mister.py`, `bot/misterplan.py`, `bot/misterrecon.py`):
  - Entrada: /feed → galetes → Siguiente ×3 → Empezar → Continuar con Email → correu → Continuar con contraseña → contrasenya. Web en català.
  - Canviar de lliga: `/action/change?id_community=2499621` (Quique Rules, LaLiga 2) i `2519290` (Fentaniños, LaLiga).
  - Plantilla a `/team` (`.player-row`, `a.player[href=players/<id>/<slug>]`, `.player-position[data-position]` 1=POR 2=DEF 3=MIG 4=DAV). Alineació: `button.lineup-player.slot-N` (classe `lineup-player-<id>`).
  - Mercat a `/market`: `li[data-position][data-price][data-owner]` (owner 0 = mercat; si no, un mànager), botó `.btn-bid`.
  - Accions per AJAX: `/ajax/player-community-info` (popup=bid / sale), `/ajax/sw/substitution` (canviar jugador d'una casella), `/ajax/sw/subs`, `/ajax/balance`.
  - Estat: informe (`bot/misterplan.py`) i **mercat automàtic** (`bot/mistermarket.py`, cada dia a les 6:00): vendes per sota del mínim (botó Gestionar → pestanya Vendre → `#btn-send`, preu mínim = valor) sense deixar la plantilla sense onze possible, i pujes pel preu mínim (`#form-bid` → `#btn-send` «Oferir»; el màxim permès és `#input-range[max]`; la meva puja = botó `.btn-bid.btn--accent`). Només jugadors lliures (owner 0).
  - Fonts: Fentaniños = % de FutbolFantasy (alineacions probables de la jornada, `bot/sources.ff_probs`; és la mateixa dada que "Mis equipos" → `/seguimiento/laliga/1`). Quique = SorareInside i, si l'equip no hi és, **Jornada Perfecta** (`/segunda/onces-posibles/`; si surt a l'onze probable compta com a 70%).
  - Relació de noms Mister ↔ font **sempre dins del mateix equip**: l'equip surt de la fitxa del jugador (`teams/<id>/<slug>`, desat a `state/mister_teams.json`); si no se sap l'equip, només nom exacte i únic. Porters només amb la fila del porter de SorareInside (Higinio Marín ≠ el porter suplent «Marín»); a igualtat de nom, el titular abans que el suplent. Diagnosi: `debug.yml` amb `bot.misterwho [Quique|Fentaniños] [equip…]`. Cada dia es revisen les pujes del bot i es retiren («Eliminar») les que ja no compleixen. Workflow manual: `mister.yml` (`--dry`, `--retira=Nom`).
  - Ofertes (`bot/misteroffers.py`, 5:10 i 17:10): per a cada jugador en venda torna a mirar el %; si ara arriba al mínim, el treu de la venda (finestra de venda → «Eliminar» `#btn-send`); si no, accepta l'oferta **sempre, encara que el preu hagi variat**. Les vendes per saldar el deute (`state/mister_debt_sales.json`) s'accepten sempre. Encara no s'ha vist la pantalla d'una oferta real: si no troba un únic botó «Acceptar», avisa i desa el que veu a les anotacions.
  - "Mis equipos" (`bot/misterff.py`, dins de la passada de les 6:00): afegeix/treu jugadors perquè coincideixi amb la plantilla de Fentaniños. Treure: `$('.once-actions .ls-unfollow').attr('data-jugador', id).click()`. Afegir: «Titular +» → `#seleccionar-respuesta-input` → `a.ls-follow[data-jugador]`. Si un nom és dubtós, no el toca.
  - Revisió abans de la resolució del mercat (4:15, la mateixa passada que la de les 6:00): retira les pujes dels jugadors que han baixat de % i posa en venda els que estan per sota del mínim, a les dues lligues.
  - Jugador de la plantilla que no surt a la font (ni titular ni suplent) però el seu equip sí → compta com a 0% i es pot vendre (decisió del David, 28/10). Si la font no té l'equip, es queda sense % i no es ven.
  - Vendes: mai si, sense el jugador, no surt cap formació gratuïta completa (1 POR + DEF/MIG/DAV d'alguna tàctica). Si sobra en aquella posició i té menys del mínim, es ven.
  - Deute (6:00): el dia del primer partit (o el dia abans si és abans de les 17:30) posa en venda de menys a més PS fins a saldo previst ≥ 0, més un de marge. Primer partit: `state/mister_kickoffs.json` (el desa `bot/plan.py`). Si les pujes es resolen (5:00) abans del primer partit, no se'n fan que deixin el saldo en negatiu.
  - Posicions que falten per fer l'onze: pujes prioritàries per jugadors d'aquella posició amb el % mínim, pel preu mínim. Mai per sota del mínim; si el % baixa, es retiren com la resta.
  - Alineació (`bot/misterlineup.py`, 6:40 cada dia i 45 min abans del primer partit de cada lliga): `/team?gameweek=N` (la jornada «Comença en…»), formació `button[data-popup=formation]` → `button.btn-free[data-formation]` (mai `btn-credits`), casella `button.lineup-player[data-slot]` → `.sw-content .player[data-id_player][data-slot]`, capità `.sw-content input[data-captain-toggle]`. Per ordenar fa servir el % i el PS de SorareInside.
  - Pendent: confirmar la pantalla de l'oferta real (primera: 27/10 17:10).

## Avisos d'onzes
- Quan el David demana si un jugador és titular, programar la comprovació cap a 1 hora abans del partit (a X solen publicar-se 1h15 abans) i avisar amb una notificació.

## Infraestructura
- Repositori: DavidSerra24/fantasy-bot. S'executa a GitHub Actions; no cal el PC del David. Oracle Free Tier (Madrid) no té capacitat.
- `auto.yml` cada 30 min (`bot/plan.py` → `bot/execute.py`):
  - Matí (9:00 Madrid), cada dia: Predicted11 de totes les jornades obertes (només refà equips que canviïn) i FutbolFantasy dels jocs que tanquin en ≤8 dies: omple els buits i revisa/edita els ja omplerts amb les dades del dia. Els jugadors de l'onze sense dades a SorareInside (equip encara sense onze o sense PS) es mantenen. Si no surt un onze vàlid, espera a l'endemà. Els extres de LaLiga també: s'omplen i es revisen cada matí (si un jugador ja no és dels 3 millors, es canvia). Sempre hi ha revisió final abans de tancar.
  - Predicted11: última revisió 50 min abans del tancament (tancament = 2 h abans del primer partit). Llegeix `data-countdown-end`. Només refà equips si canvien jugadors o posicions.
  - GitHub endarrereix les execucions programades (sovint 1 cop per hora): el planificador agafa les accions de la propera hora i s'espera fins a l'hora exacta; si en queda alguna pendent, la fa de seguida (primer la que tanca abans).
  - FutbolFantasy: revisió final 50 min abans del primer partit (dades fresques de SorareInside, amb onzes oficials d'ESPN) i canvis de jugadors si cal. Inclou els extres de LaLiga. Tancaments a `#juego-<id>[data-date-end]`.
- Mister: l'entrada torna a provar fins a 4 vegades (la web de vegades no respon a les 6:00) i, si una acció del Mister falla, es repeteix a la propera execució (fins a 3 intents, `state/tries.json`). Els errors surten com a `::error` a les anotacions.
- `fantasy.yml` (manual): proves (`--dry`), forçar competicions. `debug.yml` i `logintest.yml` per diagnosi.
- Resultats: anotacions dels jobs (`::notice`) i Telegram (`bot/notify.py`).
- Equivalències de noms: `config/predicted11.json` (alias) i `config/futbolfantasy.json`.
