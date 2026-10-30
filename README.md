# fantasy-bot

Bot del David per als jocs de futbol fantasy: **Predicted11**, **FutbolFantasy (Fantasy✨)**, **Mister** (dues lligues) i **Sorare** (Pro i missions diàries, futbol i NBA).
S'executa sol a **GitHub Actions** (no cal cap PC engegat) i informa de tot per **Telegram**.

Les normes detallades (criteris de cada joc i decisions del David) són a [`CLAUDE.md`](CLAUDE.md).

## Com funciona
- `auto.yml` està programat cada 30 min, tot el dia (a la pràctica GitHub l'arrenca ~1 cop per hora i amb retard).
  `bot/plan.py` decideix què toca fer en els propers 90 min i `bot/execute.py` s'espera i ho fa a l'hora exacta.
- L'estat (sessions, claus xifrades, decisions ja preses) es desa a `state/` a la memòria cau d'Actions.
- Els resultats surten com a anotacions dels jobs i per Telegram (`bot/notify.py`).
- Fonts: **SorareInside** (onzes previstos, % de titularitat, punts projectats), **FutbolFantasy** (% per a LaLiga al Mister),
  **Jornada Perfecta** (LaLiga 2 quan SorareInside no té l'equip), i onzes oficials de **Sorare**, **FotMob** (només l'oficial)
  i **ESPN**.

## Què fa
| Joc | Què fa | Quan |
|---|---|---|
| Predicted11 | Onzes de LaLiga, LaLiga 2, Premier, Serie A i Champions (de SorareInside) amb emoticones | Cada matí 9:00 i 50 min abans del tancament |
| Quinieles | Predicted11 (resultat) i Mister (1 X 2) amb el text del Grok o `/quiniela` per Telegram; recordatoris 26 h i 5 h abans | Quan el David les envia |
| FutbolFantasy | Jocs de lliga, extres de LaLiga (Trío revulsivo, Trío antagonista, Resiliencia de portero), Copa del Rey | Cada matí 9:00 i revisió final 50 min abans |
| Mister (Quique i Fentaniños) | Mercat (pujes, vendes, deute), ofertes, alineació i capità, «Mis equipos» de FutbolFantasy | 4:15, 5:10, 6:00, 6:40, 17:10 i 45 min abans del primer partit |
| Sorare Pro | 7 alineacions Classic (Rare i Limited: U23 → Champion → All Star) i Arenes (només amb el «sí» del David) | Dimecres/diumenge 21:15, matins abans del tancament, 2 h i 40 min abans |
| Sorare · porters | Avís 1 h 15 min abans dels porters del 20–70% i Arena amb ell si és titular (amb el «sí») | Abans de cada partit |
| Sorare · Set NBA | Taulers personal i d'equip per punts previstos (límit d'estrelles) | 9:35 escaneig i 12 min abans del primer partit |
| Sorare · missions | Decisive Picker (futbol i NBA): prioritat essència → pistes → experiència | 9:05 i 15 min abans de cada partit |

## Workflows manuals
- `sorare.yml` (`cmd`): `login` (entrar; demana el codi de l'Authenticator per Telegram), `me`, `lineups` (prova), `fill`, `final`, `missions` (prova), `missionsgo`, `plandry` (simula el pla de demà).
- `mister.yml`: mercat del Mister (`--dry`, `--retira=Nom`).
- `fantasy.yml`: proves de Predicted11 / FutbolFantasy (`--dry`).
- `debug.yml`: diagnosi (`bot.misterwho`, `bot.copa`…).

## Normes de seguretat
- Les contrasenyes i tokens només viuen als **GitHub Secrets** (mai al repositori). La clau de Sorare es desa xifrada.
- Mai escriu contrasenyes ni codis de l'Authenticator: el codi l'envia el David per Telegram.
- Cap script compra, ven ni intercanvia cartes de Sorare, ni fa dipòsits o retirades.
- L'essència (Arenes) només es gasta si el David respon «sí» per Telegram.

## Pendent
- Sorare Set de futbol (l'NBA ja funciona).
- MLB (quan torni la temporada).
- Especials de partit de FutbolFantasy («Puntos en el X - Y»): ara només avisa.
