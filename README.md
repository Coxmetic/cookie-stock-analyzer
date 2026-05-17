# Cookie Clicker Aktie-Analyzer

Et værktøj der analyserer aktiemarkedet i Cookie Clickers Bank minigame. Det bruger Z-score mean reversion til at give køb/sælg signaler baseret på prishistorik.

## Hvad skal du bruge

- Python 3
- En browser med Tampermonkey (Chrome eller Firefox)
- Cookie Clicker med Bank minigame låst op (kræver ca. 1 milliard cookies og Bank bygningen)

## Installation

**1. Installer Python pakker**
```bash
pip install -r requirements.txt
```

**2. Start serveren**
```bash
bash run.sh
```
Terminalen skal vise `Running at → http://localhost:8080` — lad den stå åben.

**3. Åbn dashboardet**

Gå til `http://localhost:8080` i din browser.

**4. Installer Tampermonkey**

Download Tampermonkey til [Chrome](https://chrome.google.com/webstore/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo) eller [Firefox](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/).

**5. Installer tracker-scriptet**

Med serveren kørende, gå til `http://localhost:8080/userscript.user.js` — Tampermonkey vil automatisk tilbyde at installere scriptet. Klik installer.

**6. Åbn Cookie Clicker**

Gå til `https://orteil.dashnet.org/cookieclicker/`. Scriptet sender automatisk aktiedata til dashboardet hvert 60. sekund.

## Sådan bruger du det

Når data begynder at ankomme kan du se:

- **Oversigt** — alle aktiers priser, gennemsnit og din portefølje
- **Signaler** — Z-score signaler for hver aktie (køb/sælg/hold)
- **Grafer** — prishistorik og Z-score historik pr. aktie
- **Historik** — liste over alle gemte snapshots

Z-score slideren (vindue) bestemmer hvor mange snapshots der bruges til at beregne gennemsnittet. 10-20 er et godt udgangspunkt.

## Stop serveren

```bash
kill $(lsof -ti :8080)
```
