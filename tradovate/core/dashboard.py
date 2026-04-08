"""
core/dashboard.py — Dashboard web simples para Apex Claude Trader
"""

import json
import logging
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

from config.settings import SYMBOL

logger = logging.getLogger(__name__)

# Estado compartilhado — atualizado pelo bot
_dashboard_state = {
    "price": 0,
    "action": "HOLD",
    "score": 0,
    "threshold": 4,
    "ATR": 0,
    "strategies": {},
    "indicators": {},
    "signal": None,
    "last_update": "",
    "status": "running",
    "pnl": 0,
    "trades_today": 0,
}


def update_state(state: dict):
    """Chamado pelo bot para atualizar o dashboard."""
    _dashboard_state.update(state)
    _dashboard_state["last_update"] = datetime.now().strftime("%H:%M:%S")


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler que serve o dashboard HTML e API de estado."""

    def __init__(self, *args, **kwargs):
        # Route all requests to dashboard
        super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)

    def do_GET(self):
        if self.path == "/api/state":
            self._send_json(_dashboard_state)
        elif self.path == "/":
            self._send_html()
        else:
            self.send_error(404)

    def _send_json(self, data):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self):
        html = _DASHBOARD_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, fmt, *args):
        # Suppress request logging
        pass


def start_dashboard(host: str = "localhost", port: int = 8501):
    """Inicia o servidor do dashboard em thread separada."""
    server = HTTPServer((host, port), DashboardHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logger.info(f"📊 Dashboard: http://{host}:{port}")


# ─────────────────────────────────────────────
# FRONTEND — HTML inline
# ─────────────────────────────────────────────

_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apex Claude Trader — Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }
h1 { font-size: 1.5rem; margin-bottom: 4px; }
.subtitle { color: #8b949e; font-size: 0.85rem; margin-bottom: 20px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; background: #3fb950; animation: pulse 2s infinite; margin-right: 8px; display: inline-block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-bottom: 16px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px; }
.card h3 { font-size: 0.8rem; text-transform: uppercase; color: #8b949e; margin-bottom: 10px; letter-spacing: 0.5px; }
.price-big { font-size: 2.2rem; font-weight: 700; }
.price-change { font-size: 1rem; margin-left: 12px; }
.up { color: #3fb950; }
.down { color: #f85149; }
.neutral { color: #8b949e; }

.stat-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d; }
.stat-row:last-child { border-bottom: none; }
.stat-label { color: #8b949e; font-size: 0.9rem; }
.stat-value { font-weight: 600; }

.signal-box { text-align: center; padding: 20px; }
.signal-action { font-size: 1.8rem; font-weight: 700; margin: 8px 0; padding: 8px 24px; display: inline-block; border-radius: 6px; }
.signal-buy { background: rgba(63,185,80,0.15); color: #3fb950; border: 1px solid rgba(63,185,80,0.3); }
.signal-sell { background: rgba(248,81,73,0.15); color: #f85149; border: 1px solid rgba(248,81,73,0.3); }
.signal-hold { background: rgba(139,148,158,0.15); color: #8b949e; border: 1px solid rgba(139,148,158,0.3); }
.score-bar { background: #21262d; border-radius: 6px; height: 24px; position: relative; overflow: hidden; margin-top: 12px; }
.score-fill { height: 100%; border-radius: 6px; transition: width 0.5s ease; }
.score-text { position: absolute; right: 8px; top: 2px; font-size: 0.75rem; font-weight: 600; }

.strategy-vote { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #21262d; }
.strategy-vote:last-child { border-bottom: none; }
.vote-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.vote-buy { background: #3fb950; }
.vote-sell { background: #f85149; }
.vote-hold { background: #484f58; }
.vote-name { flex: 1; font-size: 0.85rem; }
.vote-val { font-weight: 600; font-size: 0.85rem; }

.alert-box { padding: 14px; border-radius: 8px; margin-top: 12px; font-size: 0.9rem; text-align: center; }
.alert-green { background: rgba(63,185,80,0.1); border: 1px solid rgba(63,185,80,0.3); color: #3fb950; }
.alert-red { background: rgba(248,81,73,0.1); border: 1px solid rgba(248,81,73,0.3); color: #f85149; }
.alert-gray { background: rgba(139,148,158,0.1); border: 1px solid rgba(139,148,158,0.3); color: #8b949e; }

#timestamp { color: #8b949e; font-size: 0.8rem; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Apex Claude Trader</h1>
    <p class="subtitle" id="sym">MNQ | Modo Sinais</p>
  </div>
  <div style="text-align: right;">
    <div><span class="status-dot" id="dot"></span><span id="dot-label">Conectado</span></div>
    <p id="timestamp">--:--:--</p>
  </div>
</div>

<div class="grid">
  <!-- PRICE CARD -->
  <div class="card">
    <h3>Preço Atual</h3>
    <div>
      <span class="price-big" id="price">--</span>
      <span class="price-change" id="price-change">--</span>
    </div>
    <div style="margin-top: 14px;">
      <div class="stat-row"><span class="stat-label">ATR(14)</span><span class="stat-value" id="atr-val">--</span></div>
      <div class="stat-row"><span class="stat-label">Volatilidade</span><span class="stat-value" id="vol-regime">--</span></div>
      <div class="stat-row"><span class="stat-label">Trades Hoje</span><span class="stat-value" id="trades-today">0</span></div>
    </div>
  </div>

  <!-- SIGNAL CARD -->
  <div class="card">
    <h3>Sinal Atual</h3>
    <div class="signal-box">
      <div class="signal-action signal-hold" id="sig-badge">HOLD</div>
      <div class="score-bar">
        <div class="score-fill" id="score-fill" style="width:0%; background: #484f58;"></div>
        <span class="score-text" id="score-text">0/4</span>
      </div>
      <p id="sig-reason" style="margin-top:10px; font-size:0.85rem; color:#8b949e;">--</p>
    </div>
    <div id="alert-box" class="alert-box alert-gray">Aguardando sinal...</div>
  </div>

  <!-- STRATEGIES -->
  <div class="card">
    <h3>Estrat&aacute;gias (Votos)</h3>
    <div id="strategies">
      <div class="strategy-vote"><span class="vote-dot vote-hold"></span><span class="vote-name">Mean Reversion</span><span class="vote-val" id="st-mean">--</span></div>
      <div class="strategy-vote"><span class="vote-dot vote-hold"></span><span class="vote-name">Trend Following</span><span class="vote-val" id="st-trend">--</span></div>
      <div class="strategy-vote"><span class="vote-dot vote-hold"></span><span class="vote-name">Smart Money</span><span class="vote-val" id="st-sm">--</span></div>
      <div class="strategy-vote"><span class="vote-dot vote-hold"></span><span class="vote-name">VWAP Pullback</span><span class="vote-val" id="st-vwap">--</span></div>
      <div class="strategy-vote"><span class="vote-dot vote-hold"></span><span class="vote-name">Momentum Scalp</span><span class="vote-val" id="st-mom">--</span></div>
      <div class="strategy-vote"><span class="vote-dot vote-hold"></span><span class="vote-name">Session Alpha</span><span class="vote-val" id="st-sess">--</span></div>
    </div>
  </div>

  <!-- INDICATORS -->
  <div class="card">
    <h3>Indicadores</h3>
    <div class="stat-row"><span class="stat-label">RSI(14)</span><span class="stat-value" id="ind-rsi">--</span></div>
    <div class="stat-row"><span class="stat-label">MACD</span><span class="stat-value" id="ind-macd">--</span></div>
    <div class="stat-row"><span class="stat-label">MACD Signal</span><span class="stat-value" id="ind-macd-sig">--</span></div>
    <div class="stat-row"><span class="stat-label">MACD Hist.</span><span class="stat-value" id="ind-macd-h">--</span></div>
    <div class="stat-row"><span class="stat-label">Stoch %K</span><span class="stat-value" id="ind-k">--</span></div>
    <div class="stat-row"><span class="stat-label">Stoch %D</span><span class="stat-value" id="ind-d">--</span></div>
    <div class="stat-row"><span class="stat-label">BB Upper</span><span class="stat-value" id="ind-bbu">--</span></div>
    <div class="stat-row"><span class="stat-label">BB Lower</span><span class="stat-value" id="ind-bbl">--</span></div>
    <div class="stat-row"><span class="stat-label">VWAP</span><span class="stat-value" id="ind-vwap">--</span></div>
    <div class="stat-row"><span class="stat-label">EMA 9/21/50</span><span class="stat-value" id="ind-emas">--</span></div>
  </div>

  <!-- SINAL / TRADE PLAN -->
  <div class="card">
    <h3>Plano de Trade</h3>
    <div class="stat-row"><span class="stat-label">Dire&ccedil;&atilde;o</span><span class="stat-value" id="tp-dir">--</span></div>
    <div class="stat-row"><span class="stat-label">Entrada</span><span class="stat-value" id="tp-entry">--</span></div>
    <div class="stat-row"><span class="stat-label">Stop Loss</span><span class="stat-value down" id="tp-sl">--</span></div>
    <div class="stat-row"><span class="stat-label">Take Profit</span><span class="stat-value up" id="tp-tp">--</span></div>
    <div class="stat-row"><span class="stat-label">Contratos</span><span class="stat-value" id="tp-contracts">--</span></div>
    <div class="stat-row"><span class="stat-label">Risco ($)</span><span class="stat-value down" id="tp-risk">--</span></div>
    <div class="stat-row"><span class="stat-label">Potencial ($)</span><span class="stat-value up" id="tp-reward">--</span></div>
    <div class="stat-row"><span class="stat-label">R/R</span><span class="stat-value" id="tp-rr">--</span></div>
  </div>

  <!-- REASON -->
  <div class="card" style="grid-column: span 1;">
    <h3>Conflu&ecirc;ncia</h3>
    <div id="confluence" style="font-size:0.95rem; line-height:1.5;">
      <p style="color: #8b949e;">Analisando mercado...</p>
    </div>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
const stateIds = { price: 'price', atr: 'atr-val', vol: 'vol-regime', tradePlan: 'tp-risk' };

function updateUI(d) {
  // Price
  $('price').textContent = d.price ? d.price.toFixed(2) : '--';
  $('atr-val').textContent = d.ATR ? d.ATR.toFixed(2) : '--';
  $('vol-regime').textContent = d.vol_regime || '--';
  $('trades-today').textContent = d.trades_today || 0;

  // Signal
  const action = d.action || 'HOLD';
  const badge = $('sig-badge');
  badge.textContent = action;
  badge.className = 'signal-action signal-' + (action === 'BUY' ? 'buy' : action === 'SELL' ? 'sell' : 'hold');

  const score = d.score || 0;
  const threshold = d.threshold || 4;
  const pct = Math.min((score / (threshold + 2)) * 100, 100);
  const color = score >= threshold ? '#3fb950' : score > 0 ? '#d29922' : '#484f58';
  $('score-fill').style.width = pct + '%';
  $('score-fill').style.background = color;
  $('score-text').textContent = `${score}/${threshold}`;

  $('sig-reason').textContent = d.signal_reason || '';

  // Alert
  const alertEl = $('alert-box');
  if (score >= threshold && action !== 'HOLD') {
    alertEl.className = 'alert-box ' + (action === 'BUY' ? 'alert-green' : 'alert-red');
    alertEl.textContent = `>>> SINAL: ${action === 'BUY' ? 'COMPRAR' : 'VENDER'} MNQ <<<`;
  } else if (d.signal) {
    alertEl.className = 'alert-box alert-gray';
    alertEl.textContent = 'Sinal fraco - aguardando';
  } else {
    alertEl.className = 'alert-box alert-gray';
    alertEl.textContent = 'Aguardando configura&ccedil;&atilde;o...';
  }

  // Strategies
  const st = d.strategies || {};
  const stMap = {
    MeanRev: 'st-mean',
    Trend: 'st-trend',
    SmartMoney: 'st-sm',
    VWAP: 'st-vwap',
    Momentum: 'st-mom',
    Session: 'st-sess',
  };
  for (const [k, elId] of Object.entries(stMap)) {
    const v = st[k] || { action: 'HOLD', score: 0 };
    const el = $(elId);
    el.textContent = `${v.action || 'HOLD'} (${v.score || 0}pt)`;
  }

  // Indicators
  const ind = d.indicators || {};
  if (ind.RSI) $('ind-rsi').textContent = ind.RSI.toFixed(1);
  if (ind.MACD !== undefined) $('ind-macd').textContent = ind.MACD.toFixed(4);
  if (ind.MACDSignal !== undefined) $('ind-macd-sig').textContent = ind.MACDSignal.toFixed(4);
  const macdHist = ind.MACDHist !== undefined ? ind.MACDHist.toFixed(4) : '--';
  $('ind-macd-h').innerHTML = `<span class="${(ind.MACDHist||0) > 0 ? 'up' : 'down'}">${macdHist}</span>`;
  if (ind.StochK !== undefined) $('ind-k').textContent = ind.StochK.toFixed(1);
  if (ind.StochD !== undefined) $('ind-d').textContent = ind.StochD.toFixed(1);
  if (ind.BBUpper !== undefined) $('ind-bbu').textContent = ind.BBUpper.toFixed(2);
  if (ind.BBLower !== undefined) $('ind-bbl').textContent = ind.BBLower.toFixed(2);
  if (ind.VWAP !== undefined) $('ind-vwap').textContent = ind.VWAP.toFixed(2);
  if (ind.EMAs) {
    const em = ind.EMAs;
    const c = em.e9 > em.e21 ? 'up' : 'down';
    $('ind-emas').innerHTML = `<span class="${c}">${em.e9.toFixed(1)} / ${em.e21.toFixed(1)} / ${em.e50.toFixed(1)}</span>`;
  }

  // Trade Plan
  const tp = d.trade_plan || {};
  $('tp-dir').textContent = tp.direction || '--';
  $('tp-dir').className = 'stat-value ' + (tp.direction === 'BUY' ? 'up' : tp.direction === 'SELL' ? 'down' : 'neutral');
  $('tp-entry').textContent = tp.entry ? tp.entry.toFixed(2) : '--';
  $('tp-sl').textContent = tp.stop_loss ? tp.stop_loss.toFixed(2) : '--';
  $('tp-tp').textContent = tp.take_profit ? tp.take_profit.toFixed(2) : '--';
  $('tp-contracts').textContent = tp.contracts || '--';
  $('tp-risk').textContent = tp.risk_usd ? `$${tp.risk_usd.toFixed(2)}` : '--';
  $('tp-reward').textContent = tp.reward_usd ? `$${tp.reward_usd.toFixed(2)}` : '--';
  $('tp-rr').textContent = tp.rr ? `1:${tp.rr}` : '--';

  // Confluence
  const conf = d.confluence || [];
  if (conf.length > 0) {
    $('confluence').innerHTML = conf.map(c => `<p style="margin:4px 0;">${c}</p>`).join('');
  } else {
    $('confluence').innerHTML = '<p style="color:#8b949e;">Sem conflu&ecirc;ncia no momento.</p>';
  }

  // Timestamp
  $('timestamp').textContent = d.last_update || '';
}

function fetchData() {
  fetch('/api/state')
    .then(r => r.json())
    .then(d => updateUI(d))
    .catch(() => {
      $('dot').style.background = '#f85149';
      $('dot-label').textContent = 'Desconectado';
    });
}

fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>
"""
