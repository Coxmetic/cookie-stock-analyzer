# Cookie Clicker Stock Market Analyzer — Project Overview

## What this is
A web-based quantitative analysis tool for Cookie Clicker's Bank minigame stock market.
It collects live price snapshots via Tampermonkey, builds a time-series history, and generates Z-score mean-reversion trading signals (buy / sell / hold) for each stock.

## Architecture
- **Backend:** Python + Flask (`app.py`), runs on `http://localhost:8080`
- **Frontend:** Jinja2 template (`templates/index.html`) — pure HTML/CSS/JS, calls the backend via `fetch()`
- **Data source:** Tampermonkey userscript (`static/userscript.user.js`) — runs inside Cookie Clicker, reads `Game.Objects.Bank.minigame` live via `unsafeWindow.Game` and POSTs to `/api/inject` every 60 s. No manual save pasting needed.
- **History storage:** `history.json` (flat file, max 200 entries, persists across restarts)

## How to run
```bash
# Start the server
bash /Users/anilibryam/cookie/run.sh

# Stop the server (from any terminal)
kill $(lsof -ti :8080)

# If the server won't start ("port already in use"), run kill first, then start again.
# After editing index.html, always restart the server — Flask caches templates in memory
# (debug=False), so browser refresh alone will NOT pick up HTML/JS changes.
```

## Key API endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serves the frontend |
| POST | `/api/analyze` | Parse a raw base64 Cookie Clicker save string |
| POST | `/api/inject` | Accept pre-parsed data from the Tampermonkey script (primary data path) |
| GET | `/api/latest` | Return the most recent snapshot as full analysis JSON (used by frontend polling) |
| GET | `/api/history` | Return all stored snapshots |
| DELETE | `/api/history` | Clear all history |
| POST | `/api/demo` | Populate 10 synthetic snapshots for testing |
| GET | `/userscript.user.js` | Serves the Tampermonkey userscript for installation (`.user.js` extension required for TM auto-install dialog) |

## Frontend behaviour
- Polls `/api/latest` every 20 s and auto-refreshes the dashboard when new data arrives
- Tampermonkey status dot: green (active) / amber (stale >2.5 min) / grey (no data yet)
- Save-paste is a collapsed `<details>` secondary option — Tampermonkey is the primary flow
- Z-score thresholds and window size are adjustable via sliders; recalculated client-side from stored price history
- Overview table shows "Rolling Mean" and "Δ vs Mean" (not hardcoded base price) — computed from `currentSignals` signal map

## Analysis model
- **Z-score mean reversion** per ticker: `Z = (price − rolling_mean) / rolling_std`
- Buy signal: Z < −2 (price far below recent mean → undervalued)
- Sell signal: Z > +2 (price far above recent mean → overvalued)
- Confidence boosted by market mode (Rising/Falling) and momentum
- More snapshots = better signal quality; at least 5 snapshots needed for meaningful Z-scores

## Data stored per history entry
```json
{ "ts": 1234567890000, "player_name": "…", "version": "…",
  "office_level": 0, "brokers": 2, "cookie_pool": 0.0,
  "goods": [{ "ticker": "CRL", "price": 52.75, "base": 17.33, "mode": 2,
              "momentum": 495, "support": 5275, "owned": 0, "avg_buy": null }] }
```

---

## Critical known issues / research needed next session

### 1. `g.base` in Cookie Clicker is NOT the equilibrium price
**Symptom:** "Base Price" column showed $1.00 for almost all stocks (e.g. CHC $1.00, BTR $1.00) while actual prices are $30–$100. Only CRL showed $17.33 (the hardcoded fallback from GOODS array, meaning its `g.base` was falsy/null).
**Root cause:** Cookie Clicker's `good.base` is an internal game multiplier (~1.0), not the displayed equilibrium price. The actual equilibrium price scales with the player's bank building count and is NOT directly stored as a single accessible field. The game computes it internally.
**Fix deployed:** The overview table now shows "Rolling Mean" and "Δ vs Mean" (`(price − mean) / mean × 100`) computed from actual collected price history. This is accurate and avoids the base price problem entirely. ✓ Confirmed working.
**What still needs checking:** The `support` field (`g.sus`) may be the best approximation of the equilibrium price for display purposes. In the save format it's stored as an integer — need to determine if it's already in cookie units (same scale as price) or in cents (needs ÷100). If support ÷ 100 ≈ current price, it's in cents. Check console log values next session.

### 2. Brokers max formula is wrong
**Symptom:** Brokers shows "2 of 0 max" at office level 0 (Tent).
**Fix deployed:** Changed `Math.min(25, office_level * 5)` → `(office_level + 1) * 5`, giving Tent=5, Shed=10, etc. ✓ Confirmed working after server restart.
**Still uncertain:** Whether `(office_level + 1) * 5` is the correct CC formula. If it still looks wrong after refresh, check actual CC source or compare with in-game display.

### 3. Ticker symbols from game differ from hardcoded GOODS array
**Observation:** The Tampermonkey script correctly sends the game's actual ticker symbols: `CRL, CHC, BTR, SUG, NUT, SLT, VNL, EGG, CNM, CRM, JAM, WCH, …`. These differ from our hardcoded GOODS array (which has `CHCL, BUTR, SUGR, NUTS, CRML, VALN, CAKE, CNDY, CREM, …`).
**Impact:** No functional bug — TM path uses `g.get('ticker', meta['ticker'])` so the game's real tickers take priority. The table displays correct symbols. The GOODS array is only a fallback for the save-parse path.
**Action:** Update the GOODS array tickers/names to match the real game symbols so the save-parse path also uses correct names. Do this by comparing the `#` index column in the UI against the in-game stock list.

### 4. History entry now stores `base` per good
History entries from the inject path now include `"base": actual_base` per good (added to track the value for `change_pct` calculations). This means `g.base` from TM (which turns out to be ~1.0 for most stocks, not the equilibrium price) is being stored — not very useful. Consider removing `base` from history entries and relying solely on the rolling mean approach instead.

---

## Bugs fixed in previous sessions (for reference)

| Bug | Fix |
|-----|-----|
| Flask serves stale HTML after editing index.html | Flask caches templates in memory when `debug=False`. Must restart server (`kill $(lsof -ti :8080)` then `run.sh`) — browser refresh alone does nothing |
| Port 5000 blocked by macOS AirPlay | Changed to port 8080 |
| Tampermonkey not offering install dialog | File must be named `.user.js`, not `.js` |
| TM script silently sending nothing | `window.Game` is undefined in TM sandbox — must use `unsafeWindow.Game` + `@grant unsafeWindow` |
| avgBuy wrong from save parse | Save field 7 = `owned × avgBuy × 100` (total cost) — divide by owned and by 100 |
| `setStatus` messages invisible after first call | `clearStatus()` set inline `style.display='none'`; fixed by adding `el.style.display = ''` in `setStatus()` |
| +1860% "% vs Base" | Hardcoded bases don't scale with building count. Replaced with "Δ vs Mean" using rolling average from collected history |
| Brokers showing "X of 0 max" | `office_level * 5` gives 0 at level 0; fixed to `(office_level + 1) * 5` |

## Claude Code setup (MCP servers / plugins)
- **playwright** — browser automation
- **github** — GitHub repo access
- **context7** — live library documentation (`npx -y @upstash/context7-mcp` needed once)
- **superpowers** (v5.0.7) — `/brainstorming`, `/execute-plan` slash commands
