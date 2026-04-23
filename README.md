# Cookie Clicker — Stock Market Analyzer

A dark-themed web dashboard that collects live stock prices from Cookie Clicker's Bank minigame via Tampermonkey and generates Z-score mean-reversion buy/sell/hold signals.

## Quick start

```bash
pip install flask
bash run.sh
```

Then open `http://localhost:8080` and follow the Tampermonkey setup steps on the page.

## How it works

- A Tampermonkey userscript runs inside Cookie Clicker and POSTs live stock data to the local Flask server every 60 s
- The server stores up to 200 price snapshots in `history.json`
- Z-scores are computed per ticker from the rolling mean and std of collected prices
- Buy signal: Z < −2 · Sell signal: Z > +2

## To stop/start the server

```bash
# Stop
kill $(lsof -ti :8080)

# Start
bash run.sh
```

> After editing `templates/index.html` or `app.py`, restart the server — Flask caches templates in memory.
