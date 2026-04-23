// ==UserScript==
// @name         Cookie Clicker — Stock Auto-Tracker
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Sends live stock data to your local analyzer every 60 s. No save pasting needed.
// @match        https://orteil.dashnet.org/cookieclicker/*
// @match        http://orteil.dashnet.org/cookieclicker/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// ==/UserScript==

const ENDPOINT        = 'http://localhost:8080/api/inject';
const INTERVAL_SEC    = 60;   // how often to send data (seconds)
const MIN_INTERVAL_MS = 30_000;

let lastSent = 0;

function collectAndSend() {
    // Wait until the game and bank minigame are fully loaded
    if (!window.Game || !Game.Objects?.Bank?.minigame) return;

    const M = Game.Objects.Bank.minigame;
    if (!M.goodsById || !M.goodsById.length) return;

    const now = Date.now();
    if (now - lastSent < MIN_INTERVAL_MS) return;
    lastSent = now;

    const goods = M.goodsById.map((g, i) => ({
        idx:      i,
        ticker:   g.symbol  || `G${i}`,
        name:     g.name    || `Good ${i}`,
        price:    g.val     || 0,
        mode:     g.mode    || 0,
        momentum: g.dur     || 0,   // duration of current mode (used as momentum proxy)
        support:  g.sus     || 0,
        owned:    g.stock   || 0,
        avg_buy:  (g.stock > 0 && g.buy > 0) ? g.buy : null,
    }));

    const payload = {
        player_name:  Game.bakeryName || 'Player',
        version:      Game.version    || '?',
        office_level: M.officeLevel   || 0,
        brokers:      M.brokers       || 0,
        cookie_pool:  M.cookiePool    || 0,
        goods,
    };

    GM_xmlhttpRequest({
        method:  'POST',
        url:     ENDPOINT,
        headers: { 'Content-Type': 'application/json' },
        data:    JSON.stringify(payload),
        onload:  r => {
            if (r.status === 200) {
                const resp = JSON.parse(r.responseText);
                console.log(`[CC Tracker] ✓ Sent ${goods.length} goods — history: ${resp.history_count} saves`);
            }
        },
        onerror: () => console.warn('[CC Tracker] Flask server not reachable at ' + ENDPOINT),
    });
}

// Send immediately when the script loads, then on interval
setTimeout(collectAndSend, 5000);           // wait 5 s for game to finish loading
setInterval(collectAndSend, INTERVAL_SEC * 1000);

console.log(`[CC Tracker] Loaded — will send data every ${INTERVAL_SEC}s to ${ENDPOINT}`);
