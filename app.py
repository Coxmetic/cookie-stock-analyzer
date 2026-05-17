"""
Cookie Clicker aktie-analyzer - kør med: python app.py og åbn localhost:8080
"""
import json, os, base64, math, time
from flask import Flask, request, jsonify, render_template, send_from_directory
from urllib.parse import unquote

app = Flask(__name__)
HISTORY_FILE   = 'history.json'
PORTFOLIO_FILE = 'portfolio.json'


@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# ─── AKTIER ───────────────────────────────────────────────────────────────────
# rækkefølgen skal passe med Cookie Clickers interne liste
# hvis priserne ser forkerte ud er det nok denne liste der er problemet
# TODO: base-priserne herunder er ikke rigtige, de skalerer med antal banker man har
GOODS = [
    {'ticker': 'CRL', 'name': 'Cereals',        'base': 17.33},
    {'ticker': 'CHC', 'name': 'Chocolate',       'base':  8.18},
    {'ticker': 'BTR', 'name': 'Butter',          'base':  2.43},
    {'ticker': 'SUG', 'name': 'Sugar',           'base':  7.43},
    {'ticker': 'NUT', 'name': 'Nuts',            'base':  9.68},
    {'ticker': 'SLT', 'name': 'Salt',            'base':  5.51},
    {'ticker': 'VNL', 'name': 'Vanilla',         'base':  4.88},
    {'ticker': 'EGG', 'name': 'Eggs',            'base':  3.14},
    {'ticker': 'CNM', 'name': 'Cinnamon',        'base':  6.09},
    {'ticker': 'CRM', 'name': 'Cream',           'base':  9.72},
    {'ticker': 'JAM', 'name': 'Jam',             'base':  9.46},
    {'ticker': 'WCH', 'name': 'White Chocolate', 'base': 12.43},
    {'ticker': 'HNY', 'name': 'Honey',           'base': 18.71},
    {'ticker': 'CKI', 'name': 'Cookies',         'base': 19.21},
    {'ticker': 'RCP', 'name': 'Recipes',         'base':  4.87},
    {'ticker': 'SBD', 'name': 'Subsidiaries',     'base': 14.77},
    {'ticker': 'PBL', 'name': 'Publicists',       'base': 15.12},
    {'ticker': 'YOU', 'name': 'Your Company',     'base': 10.00},
]

MODES = [
    {'label': 'Stable',  'cls': 'm-stable'},
    {'label': 'Chaotic', 'cls': 'm-chaotic'},
    {'label': 'Slow',    'cls': 'm-slow'},
    {'label': 'Falling', 'cls': 'm-falling'},
    {'label': 'Rising',  'cls': 'm-rising'},
    {'label': 'Slow ↑',  'cls': 'm-rising'},
]

OFFICE_LEVELS = ['Tent', 'Shed', 'Warehouse', 'Office', 'Corporation', 'Headquarters']

# ─── HISTORIK ─────────────────────────────────────────────────────────────────

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def write_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)


def load_portfolio():
    empty = {'positions': {}, 'realized_pnl': 0.0}
    if not os.path.exists(PORTFOLIO_FILE):
        return empty
    try:
        with open(PORTFOLIO_FILE) as f:
            data = json.load(f)
        if 'positions' not in data:
            return {'positions': data, 'realized_pnl': 0.0}
        return data
    except Exception:
        return empty


def write_portfolio(portfolio):
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolio, f)

# ─── SAVE-FIL PARSING ─────────────────────────────────────────────────────────
# bruges hvis man indsætter sin save manuelt istedet for tampermonkey

def decode_save(raw):
    s = raw.strip()
    try:
        s = unquote(s)
    except Exception:
        pass
    if s.endswith('!END!'):
        s = s[:-5]
    if s.startswith('!!=='):
        s = s[4:]
    try:
        return base64.b64decode(s).decode('utf-8', errors='replace')
    except Exception as e:
        raise ValueError(f'Base64 decode fejlede — er du sikker på du kopierede hele save-strengen? ({e})')


def split_pipes(decoded):
    parts = decoded.split('|')
    if len(parts) < 6:
        raise ValueError(f'Kun {len(parts)} sektioner i save-filen — forventede mindst 6.')
    meta = (parts[2] or '').split(';')

    raw_ts = meta[0] if meta else ''
    ts = int(raw_ts) if raw_ts.lstrip('-').isdigit() else None

    return {
        'version':          parts[0],
        'timestamp':        ts,
        'player_name':      meta[3] if len(meta) > 3 else 'Unknown',
        'building_section': parts[5] or '',
    }


def extract_bank(building_section):
    buildings = building_section.split(';')
    if len(buildings) < 6:
        raise ValueError(f'Kun {len(buildings)} bygninger fundet — er Bank bygningen låst op?')
    fields = buildings[5].split(',')
    if len(fields) < 5:
        raise ValueError('Bank data for kort — er aktiemarkedet låst op?')
    return {
        'bank_owned':   int(fields[0]) if fields[0].isdigit() else 0,
        'minigame_raw': ','.join(fields[4:]),
    }


def _si(v, default=0):
    try:    return int(v)
    except: return default

def _sf(v, default=0.0):
    try:    return float(v)
    except: return default


def parse_minigame(minigame_raw):
    try:
        space_idx = minigame_raw.index(' ')
    except ValueError:
        raise ValueError('Kunne ikke finde separator i minigame data.')

    header       = minigame_raw[:space_idx].split(':')
    office_level = _si(header[0] if header else '')
    brokers      = _si(header[1] if len(header) > 1 else '')
    cookie_pool  = _sf(header[3] if len(header) > 3 else '')

    chunks      = minigame_raw[space_idx + 1:].split('!')
    good_chunks = [c.strip() for c in chunks[:-1] if c.strip()]

    if not good_chunks:
        raise ValueError('Ingen aktier fundet i minigame data.')

    goods = []
    for i, chunk in enumerate(good_chunks):
        f    = chunk.split(':')
        meta = GOODS[i] if i < len(GOODS) else {'ticker': f'G{i}', 'name': f'Good {i}', 'base': 1.0}

        price  = _si(f[0] if f else '') / 100
        mode   = _si(f[1] if len(f) > 1 else '')
        mom    = _si(f[2] if len(f) > 2 else '')
        owned  = _si(f[5] if len(f) > 5 else '')

        # felt 7 = antal * gennesnits-pris * 100 (total udgift i cents)
        total_cost_cents = _si(f[7] if len(f) > 7 else '')
        avg_buy = (total_cost_cents / owned / 100) if owned > 0 and total_cost_cents > 0 else None

        mode_info  = MODES[mode] if mode < len(MODES) else {'label': f'Mode{mode}', 'cls': 'm-stable'}
        change_pct = (price - meta['base']) / meta['base'] * 100 if meta['base'] > 0 else 0
        pnl        = round((price - avg_buy) * owned, 4) if owned > 0 and avg_buy is not None else None
        pnl_pct    = round((price - avg_buy) / avg_buy * 100, 2) if avg_buy and avg_buy > 0 and owned > 0 else None

        goods.append({
            'idx':       i,
            'ticker':    meta['ticker'],
            'name':      meta['name'],
            'base':      meta['base'],
            'price':     price,
            'mode':      mode,
            'mode_name': mode_info['label'],
            'mode_cls':  mode_info['cls'],
            'momentum':  mom,
            'owned':     owned,
            'avg_buy':   avg_buy,
            'change_pct': round(change_pct, 2),
            'pnl':       pnl,
            'pnl_pct':   pnl_pct,
        })

    return {'office_level': office_level, 'brokers': brokers, 'cookie_pool': cookie_pool, 'goods': goods}

# ─── Z-SCORE BEREGNINGER ──────────────────────────────────────────────────────
# TODO: kunne være fedt at sende en notifikation når en aktie rammer -2 eller +2

def rolling_stats(prices, window):
    result = []
    for i in range(len(prices)):
        if i < window - 1:
            result.append((None, None))
        else:
            sl       = prices[i - window + 1:i + 1]
            mean     = sum(sl) / len(sl)
            variance = sum((x - mean) ** 2 for x in sl) / len(sl)
            result.append((mean, math.sqrt(variance)))
    return result


def calc_zscores(prices, window):
    stats  = rolling_stats(prices, window)
    result = []
    for i, price in enumerate(prices):
        mean, std = stats[i]
        if mean is None or std is None or std < 0.0001:
            result.append(None)
        else:
            result.append((price - mean) / std)
    return result


def signal_for(z, buy_t, sell_t, mode, momentum):
    if z is None:
        return {'signal': 'HOLD', 'confidence': 0, 'reason': 'Insufficient history — paste more saves'}

    if z <= buy_t:
        signal     = 'BUY'
        confidence = min(100, int(abs(z / buy_t) * 60))
        reason     = f'Z={z:.2f} below buy threshold'
    elif z >= sell_t:
        signal     = 'SELL'
        confidence = min(100, int((z / sell_t) * 60))
        reason     = f'Z={z:.2f} above sell threshold'
    elif z <= buy_t * 0.6:
        signal, confidence, reason = 'WATCH', 30, f'Z={z:.2f}, approaching buy zone'
    elif z >= sell_t * 0.6:
        signal, confidence, reason = 'WATCH', 30, f'Z={z:.2f}, approaching sell zone'
    else:
        signal     = 'HOLD'
        confidence = int((1 - abs(z) / 2) * 40)
        reason     = f'Z={z:.2f}, neutral zone'

    if signal == 'BUY'  and mode in (4, 5):  confidence = min(100, confidence + 20); reason += ' + Rising mode'
    if signal == 'SELL' and mode == 3:        confidence = min(100, confidence + 20); reason += ' + Falling mode'
    if signal == 'BUY'  and momentum > 100:  confidence = min(100, confidence + 10); reason += ' + positive momentum'
    if signal == 'SELL' and momentum < -100: confidence = min(100, confidence + 10); reason += ' + negative momentum'

    return {'signal': signal, 'confidence': confidence, 'reason': reason}


def build_price_history(history):
    series = {}
    for entry in history:
        for g in entry.get('goods', []):
            t = g['ticker']
            if t not in series:
                series[t] = {'prices': [], 'timestamps': []}
            series[t]['prices'].append(g['price'])
            series[t]['timestamps'].append(entry['ts'])
    return series


def compute_signals(goods, history, buy_t, sell_t, window):
    ph = build_price_history(history)
    out = []
    for g in goods:
        prices = ph.get(g['ticker'], {}).get('prices', [])
        zs     = calc_zscores(prices, window)
        stats  = rolling_stats(prices, window)

        latest_z    = zs[-1]      if zs    else None
        latest_mean = stats[-1][0] if stats else None
        latest_std  = stats[-1][1] if stats else None
        sig = signal_for(latest_z, buy_t, sell_t, g['mode'], g['momentum'])

        out.append({
            'idx':        g['idx'],
            'ticker':     g['ticker'],
            'name':       g['name'],
            'price':      g['price'],
            'owned':      g['owned'],
            'avg_buy':    g['avg_buy'],
            'pnl':        g['pnl'],
            'pnl_pct':    g['pnl_pct'],
            'mean':       round(latest_mean, 4) if latest_mean is not None else None,
            'std':        round(latest_std, 4)  if latest_std  is not None else None,
            'zscore':     round(latest_z, 4)    if latest_z    is not None else None,
            'signal':     sig['signal'],
            'confidence': sig['confidence'],
            'reason':     sig['reason'],
            'price_series':  prices,
            'zscore_series': [round(z, 4) if z is not None else None for z in zs],
        })
    return out


# ─── API ENDPOINTS ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/userscript.user.js')
def userscript():
    return send_from_directory('static', 'userscript.user.js', mimetype='application/javascript')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    body = request.get_json(silent=True) or {}
    raw  = body.get('save_string', '').strip()
    if not raw:
        return jsonify({'error': 'No save string provided'}), 400

    try:
        decoded  = decode_save(raw)
        parsed   = split_pipes(decoded)
        bank     = extract_bank(parsed['building_section'])
        minigame = parse_minigame(bank['minigame_raw'])

        data = {
            'version':      parsed['version'],
            'timestamp':    parsed['timestamp'],
            'player_name':  parsed['player_name'],
            'office_level': minigame['office_level'],
            'brokers':      minigame['brokers'],
            'cookie_pool':  minigame['cookie_pool'],
            'goods':        minigame['goods'],
        }

        history = load_history()
        entry   = {
            'ts':           int(time.time() * 1000),
            'player_name':  data['player_name'],
            'version':      data['version'],
            'office_level': data['office_level'],
            'brokers':      data['brokers'],
            'cookie_pool':  data['cookie_pool'],
            'goods': [{
                'ticker':   g['ticker'],
                'price':    g['price'],
                'mode':     g['mode'],
                'momentum': g['momentum'],
                'owned':    g['owned'],
                'avg_buy':  g['avg_buy'],
            } for g in data['goods']],
        }

        if history and (entry['ts'] - history[-1]['ts']) < 30_000:
            history[-1] = entry
        else:
            history.append(entry)

        if len(history) > 50:
            history = history[-50:]

        write_history(history)

        buy_t  = float(body.get('buy_thresh', -2))
        sell_t = float(body.get('sell_thresh',  2))
        window = int(body.get('window', 5))

        signals      = compute_signals(data['goods'], history, buy_t, sell_t, window)
        price_history = build_price_history(history)

        return jsonify({
            'success':       True,
            'data':          data,
            'signals':       signals,
            'price_history': price_history,
            'history_count': len(history),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/signals', methods=['POST'])
def recalc_signals():
    body   = request.get_json(silent=True) or {}
    goods  = body.get('goods', [])
    buy_t  = float(body.get('buy_thresh', -2))
    sell_t = float(body.get('sell_thresh',  2))
    window = int(body.get('window', 5))

    history  = load_history()
    signals  = compute_signals(goods, history, buy_t, sell_t, window)
    return jsonify({'signals': signals, 'history_count': len(history)})


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({'ok': True, 'history_count': len(load_history())})


@app.route('/api/inject', methods=['POST', 'OPTIONS'])
def inject():
    if request.method == 'OPTIONS':
        return '', 204

    body = request.get_json(silent=True) or {}
    goods_raw = body.get('goods', [])
    if not goods_raw:
        return jsonify({'error': 'No goods data provided'}), 400

    portfolio  = load_portfolio()
    positions  = portfolio['positions']
    goods = []
    for g in goods_raw:
        i    = int(g.get('idx', 0))
        meta = GOODS[i] if i < len(GOODS) else {'ticker': g.get('ticker', f'G{i}'), 'name': g.get('name', f'Good {i}')}
        price   = float(g.get('price', 0))
        owned   = int(g.get('owned', 0))
        ticker  = g.get('ticker', meta['ticker'])

        if owned > 0:
            if ticker not in positions:
                avg_buy = round(price, 4)
                positions[ticker] = {'avg_buy': avg_buy, 'owned': owned}
            else:
                prev_avg   = positions[ticker]['avg_buy']
                prev_owned = positions[ticker]['owned']
                if owned > prev_owned:
                    additional = owned - prev_owned
                    avg_buy = round((prev_avg * prev_owned + price * additional) / owned, 4)
                elif owned < prev_owned:
                    # delsalg - vi bruger snapshot-prisen, ikke den excakte salgspris
                    sold = prev_owned - owned
                    portfolio['realized_pnl'] = round(portfolio['realized_pnl'] + (price - prev_avg) * sold, 4)
                    avg_buy = prev_avg
                else:
                    avg_buy = prev_avg
                positions[ticker] = {'avg_buy': avg_buy, 'owned': owned}
        else:
            if ticker in positions:
                # helt solgt - nulstil positionen
                prev = positions[ticker]
                portfolio['realized_pnl'] = round(portfolio['realized_pnl'] + (price - prev['avg_buy']) * prev['owned'], 4)
                del positions[ticker]
            avg_buy = None

        pnl     = round((price - avg_buy) * owned, 4) if avg_buy and owned > 0 else None
        pnl_pct = round((price - avg_buy) / avg_buy * 100, 2) if avg_buy and avg_buy > 0 and owned > 0 else None
        mode    = int(g.get('mode', 0))
        goods.append({
            'idx': i, 'ticker': ticker, 'name': g.get('name', meta['name']),
            'price': price, 'mode': mode,
            'mode_name': MODES[mode]['label'] if mode < len(MODES) else f'Mode{mode}',
            'mode_cls':  MODES[mode]['cls']   if mode < len(MODES) else 'm-stable',
            'momentum': int(g.get('momentum', 0)),
            'owned': owned, 'avg_buy': avg_buy, 'pnl': pnl, 'pnl_pct': pnl_pct,
        })

    write_portfolio(portfolio)

    history = load_history()
    entry = {
        'ts':           int(time.time() * 1000),
        'player_name':  body.get('player_name', 'Player'),
        'version':      str(body.get('version', '?')),
        'office_level': int(body.get('office_level', 0)),
        'brokers':      int(body.get('brokers', 0)),
        'broker_max':   int(body.get('broker_max', 0)),
        'cookie_pool':  float(body.get('cookie_pool', 0)),
        'goods': [{'ticker': g['ticker'], 'price': g['price'],
                   'mode': g['mode'], 'momentum': g['momentum'],
                   'owned': g['owned'], 'avg_buy': g['avg_buy']} for g in goods],
    }

    if history and (entry['ts'] - history[-1]['ts']) < 30_000:
        history[-1] = entry
    else:
        history.append(entry)

    if len(history) > 200:   # max 200 snapshots gemt
        history = history[-200:]

    write_history(history)
    return jsonify({'success': True, 'history_count': len(history), 'realized_pnl': portfolio['realized_pnl']})


@app.route('/api/latest', methods=['GET'])
def latest():
    history = load_history()
    if not history:
        return jsonify({'data': None, 'history_count': 0, 'last_ts': None})

    last = history[-1]
    goods = []
    for g_entry in last['goods']:
        i = 0
        meta = {'ticker': g_entry['ticker'], 'name': g_entry['ticker']}
        for j, m in enumerate(GOODS):
            if m['ticker'] == g_entry['ticker']:
                i = j
                meta = m
                break

        price   = g_entry['price']
        owned   = g_entry.get('owned', 0)
        avg_buy = g_entry.get('avg_buy')
        mode    = g_entry.get('mode', 0)
        pnl     = round((price - avg_buy) * owned, 4) if avg_buy and owned > 0 else None
        pnl_pct = round((price - avg_buy) / avg_buy * 100, 2) if avg_buy and avg_buy > 0 and owned > 0 else None

        goods.append({
            'idx': i, 'ticker': g_entry['ticker'], 'name': meta['name'],
            'price': price, 'mode': mode,
            'mode_name': MODES[mode]['label'] if mode < len(MODES) else f'Mode{mode}',
            'mode_cls':  MODES[mode]['cls']   if mode < len(MODES) else 'm-stable',
            'momentum': g_entry.get('momentum', 0),
            'owned': owned, 'avg_buy': avg_buy, 'pnl': pnl, 'pnl_pct': pnl_pct,
        })

    data = {
        'version':      last.get('version', '?'),
        'timestamp':    last['ts'],
        'player_name':  last.get('player_name', 'Player'),
        'office_level': last.get('office_level', 0),
        'brokers':      last.get('brokers', 0),
        'broker_max':   last.get('broker_max', 0),
        'cookie_pool':  last.get('cookie_pool', 0),
        'goods':        goods,
    }

    signals       = compute_signals(goods, history, -2, 2, 5)
    price_history = build_price_history(history)

    realized_pnl = load_portfolio().get('realized_pnl', 0.0)
    return jsonify({
        'data':          data,
        'signals':       signals,
        'price_history': price_history,
        'history_count': len(history),
        'last_ts':       last['ts'],
        'realized_pnl':  realized_pnl,
    })


@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify({'history': load_history()})


@app.route('/api/history', methods=['DELETE'])
def delete_history():
    write_history([])
    write_portfolio({'positions': {}, 'realized_pnl': 0.0})
    return jsonify({'success': True})



if __name__ == '__main__':
    print('\n  🍪  Cookie Clicker Stock Analyzer')
    print('  Running at → http://localhost:8080')
    print('  Keep this terminal open while using the app.\n')
    app.run(debug=False, port=8080)
