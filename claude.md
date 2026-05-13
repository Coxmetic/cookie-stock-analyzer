# Cookie Clicker Stock Market Analyzer — Project Overview

## What this is
A web-based quantitative analysis tool for Cookie Clicker's Bank minigame stock market.
It collects live price snapshots via Tampermonkey, builds a time-series history, and generates Z-score mean-reversion trading signals (buy / sell / hold) for each stock.

## Architecture
- **Backend:** Python + Flask (`app.py`), runs on `http://localhost:8080`
- **Frontend:** Jinja2 template (`templates/index.html`) — pure HTML/CSS/JS, calls the backend via `fetch()`
- **Data source:** Tampermonkey userscript (`static/userscript.user.js`) — runs inside Cookie Clicker, reads `Game.Objects.Bank.minigame` live via `unsafeWindow.Game` and POSTs to `/api/inject` every 60 s. No manual save pasting needed.
- **History storage:** `history.json` (flat file, max 200 entries, persists across restarts)
- **Portfolio tracking:** `portfolio.json` — server-side state for avg buy price and realized P&L since the game doesn't expose these. Cleared when history is cleared.

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
| GET | `/userscript.user.js` | Serves the Tampermonkey userscript for installation (`.user.js` extension required for TM auto-install dialog) |

## Frontend behaviour
- Polls `/api/latest` every 20 s and auto-refreshes the dashboard when new data arrives
- Tampermonkey status dot: green (active) / amber (stale >2.5 min) / grey (no data yet)
- Save-paste is a collapsed `<details>` secondary option — Tampermonkey is the primary flow
- Z-score thresholds and window size are adjustable via sliders; recalculated client-side from stored price history
- Overview table shows "Rolling Mean" and "Δ vs Mean" (not hardcoded base price) — computed from `currentSignals` signal map
- Summary cards show Unrealized P&L (open positions) and Realized P&L (completed sells) separately
- Z-score window slider has no cap — goes up to current history depth dynamically
- Stale data banner appears when TM hasn't sent in >2.5 min, with optional browser notification

## Analysis model
- **Z-score mean reversion** per ticker: `Z = (price − rolling_mean) / rolling_std`
- Buy signal: Z < −2 (price far below recent mean → undervalued)
- Sell signal: Z > +2 (price far above recent mean → overvalued)
- Confidence boosted by market mode (Rising/Falling) and momentum
- More snapshots = better signal quality; at least 5 snapshots needed for meaningful Z-scores

## Data stored per history entry
```json
{ "ts": 1234567890000, "player_name": "…", "version": "…",
  "office_level": 0, "brokers": 2, "broker_max": 101,
  "goods": [{ "ticker": "CRL", "price": 52.75, "mode": 2,
              "momentum": 495, "owned": 0, "avg_buy": null }] }
```

## portfolio.json structure
```json
{
  "positions": {
    "SUG": { "avg_buy": 44.82, "owned": 500 }
  },
  "realized_pnl": 346.00
}
```
- `avg_buy` is estimated — first snapshot price when owned transitions 0→N, then weighted-averaged on subsequent buys
- `realized_pnl` accumulates on every partial or full sell, using snapshot price (not exact sell price — up to 60s drift)
- Entire file resets when history is cleared

## Game object fields (confirmed via CC console)
The live `Game.Objects.Bank.minigame.goodsById[i]` object has these useful fields:
- `symbol` — ticker (e.g. "CRL")
- `name` — full name
- `val` — current price (dollars)
- `mode` — market mode (0=Stable, 1=Chaotic, 2=Slow, 3=Falling, 4=Rising, 5=Slow↑)
- `dur` — duration in current mode (momentum)
- `stock` — shares owned
- `prev` — price at start of current mode (not buy price)
- `d` — price delta per tick
- `last` — previous tick price (always 0 when not owned)

Fields that do NOT exist: `buy` (avg buy price), `sus` (support/equilibrium), `brokerMax`. CC does not expose these in the live object.

## Broker max formula
`broker_max = 1 + Math.floor(Game.Objects['Grandma'].highest / 10)`
- `Game.Objects['Grandma'].highest` = peak grandmas owned this run (never decreases)
- Confirmed: 1001 peak grandmas → 1 + 100 = 101 max brokers ✓
- `M.brokerMax` does not exist — must compute from grandma data in TM script

## TM script quirk
`avg_buy` in the TM goods map uses `g.buy` which is always `undefined` in the game object — so it always sends `null`. The server ignores this and uses `portfolio.json` for buy price tracking instead. The line is harmless but could be simplified to just `null`.

---

## Bugs fixed (for reference)

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
| GOODS array had wrong tickers | Updated to match real game symbols: CHC, BTR, SUG, NUT, SLT, VNL, EGG, CNM, CRM, WCH, HNY etc. |
| `g.sus` (support) field doesn't exist | Confirmed via console: game object has no support price field. Support column removed entirely. |
| Cookie Reserve card always showed 0 | `M.cookiePool` is always 0 — CC has no separate trading pool, you buy stocks with main cookies. Card removed. |
| Avg Buy not available from game object | `g.buy` is undefined — CC doesn't expose buy price in the live object. Fixed with `portfolio.json`: server tracks weighted average across multiple buys. When owned increases between snapshots, computes `(prev_avg × prev_owned + current_price × new_shares) / total_owned`. Clears on full sell. |
| Window size slider capped at 20 | Removed hard cap — slider now goes up to current history depth dynamically |
| `g.base` and `base` stored in history | Both removed — `g.base` is always ~1.0 (internal multiplier, not a price), carrying no useful info |
| Demo button and `/api/demo` route | Removed — synthetic data was misleading and no longer needed |
| Realized P&L not tracked | Added `portfolio.json` with `realized_pnl` field. Accumulates on every sell detected between snapshots. Shown as a summary card in Overview. Resets on Clear History. |
| Tooltips used browser `title` attribute | Replaced with CSS custom tooltips — Z-score `(?)` header and signal badges now show styled popups on hover |
| Broker max formula wrong | Was `(office_level + 1) * 5`. Real formula: `1 + floor(peak_grandmas / 10)`. TM now sends `broker_max` computed from `Game.Objects['Grandma'].highest`. |
| Z-score chart Y-axis capped at ±4 | Removed `min: -4, max: 4` — both Z-score charts now auto-scale to actual values |
| Window slider showing too few Z-scores with no feedback | Added live counter next to slider: `(N saves · M valid Z-scores)` with warning when window is too large |

## Claude Code setup (MCP servers / plugins)
- **playwright** — browser automation
- **github** — GitHub repo access
- **context7** — live library documentation (`npx -y @upstash/context7-mcp` needed once)
- **superpowers** (v5.0.7) — `/brainstorming`, `/execute-plan` slash commands
