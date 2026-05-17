// ==UserScript==
// @name         Cookie Clicker — Stock Auto-Tracker
// @namespace    http://tampermonkey.net/
// @version      1.2
// @description  Henter aktiedata fra Cookie Clicker og sender det til vores analyser hvert 60 sek.
// @match        https://orteil.dashnet.org/cookieclicker/*
// @match        http://orteil.dashnet.org/cookieclicker/*
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

const ENDPOINT        = 'http://localhost:8080/api/inject';
const INTERVAL_SEC    = 60;
const MIN_INTERVAL_MS = 30_000;

let lastSent = 0;

function collectAndSend() {
    // skal bruge unsafeWindow - TMs sandbox kan ikke se spillets Game objekt ellers
    const Game = unsafeWindow.Game;
    if (!Game || !Game.Objects?.Bank?.minigame) {
        console.log('[CC Tracker] Bank minigame not ready yet — will retry');
        return;
    }

    const M = Game.Objects.Bank.minigame;
    if (!M.goodsById || !M.goodsById.length) {
        console.log('[CC Tracker] ingen aktier fundet endnu, prøver igen');
        return;
    }

    // vent mindst 30 sek mellem hvert send
    const now = Date.now();
    if (now - lastSent < MIN_INTERVAL_MS) return;
    lastSent = now;

    // hent data fra alle aktier
    const goods = M.goodsById.map((g, i) => ({
        idx:      i,
        ticker:   g.symbol  || `G${i}`,
        name:     g.name    || `Good ${i}`,
        price:    g.val     || 0,
        mode:     g.mode    || 0,
        momentum: g.dur     || 0,
        owned:    g.stock   || 0,
        avg_buy:  (g.stock > 0 && g.buy > 0) ? Math.round(g.buy / g.stock * 100) / 100 : null,
    }));

    // max mæglere = 1 + (antal bedste bedste mormødre / 10)
    const peakGrandmas = Game.Objects['Grandma']?.highest || 0;
    const payload = {
        player_name:  Game.bakeryName || 'Player',
        version:      Game.version    || '?',
        office_level: M.officeLevel   || 0,
        brokers:      M.brokers       || 0,
        broker_max:   1 + Math.floor(peakGrandmas / 10),
        cookie_pool:  M.cookiePool    || 0,
        goods,
    };

    console.log(`[CC Tracker] Sending ${goods.length} goods…`);

    GM_xmlhttpRequest({
        method:  'POST',
        url:     ENDPOINT,
        headers: { 'Content-Type': 'application/json' },
        data:    JSON.stringify(payload),
        onload: r => {
            if (r.status === 200) {
                const resp = JSON.parse(r.responseText);
                console.log(`[CC Tracker] ✓ Stored — history now has ${resp.history_count} saves`);
            } else {
                console.warn(`[CC Tracker] Server returned ${r.status}`);
            }
        },
        onerror: () => console.warn('[CC Tracker] Could not reach Flask server at ' + ENDPOINT),
    });
}

setTimeout(collectAndSend, 5000);
setInterval(collectAndSend, INTERVAL_SEC * 1000);

console.log(`[CC Tracker] v1.2 loaded — sending every ${INTERVAL_SEC}s to ${ENDPOINT}`);
