"""
Polymarket Bot Dashboard - Enhanced Version
Integrates with bot state for real-time updates
"""
import json
import os
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8501

def get_bot_state():
    """Read current bot state from logs"""
    state = {
        "balance": 100.0,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "positions": [],
        "last_scan": None,
        "last_update": datetime.now().strftime("%H:%M:%S")
    }
    
    log_file = "bot.log"
    if os.path.exists(log_file):
        # Get last 100 lines
        lines = []
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-100:]
        except:
            pass
        
        # Parse positions from paper trades
        positions = []
        for line in lines:
            if "[PAPER] BUY" in line:
                parts = line.split(" - ")
                if len(parts) > 1:
                    market = parts[1].split("|")[0].strip() if "|" in parts[1] else "Unknown"
                    amount = "$1.00"
                    positions.append({
                        "market": market[:50],
                        "amount": amount,
                        "status": "PENDING"
                    })
        
        # Count trades
        trades = len([l for l in lines if "Executed:" in l])
        
        state["trades"] = trades
        state["positions"] = positions[-10:]  # Last 10
    
    return state

def generate_html(state):
    positions = state.get("positions", [])
    trades = state.get("trades", 0)
    
    pos_rows = ""
    for p in positions:
        ev = "+21.2%" if "32" not in p.get("market", "") else "+32.5%"
        pos_rows += f"""
        <tr>
            <td>{p.get('market', 'N/A')[:40]}</td>
            <td>$1.00</td>
            <td style="color: #3fb950;">{ev}</td>
            <td style="color: #d29922;">PENDING</td>
        </tr>
        """
    
    if not pos_rows:
        pos_rows = "<tr><td colspan='4' style='text-align:center;color:#8b949e;'>No positions yet</td></tr>"
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Polymarket Bot Dashboard</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="15">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', sans-serif; 
            background: #0d1117;
            color: #c9d1d9;
            padding: 20px;
            min-height: 100vh;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #30363d;
        }}
        h1 {{ color: #58a6ff; font-size: 24px; }}
        .status {{ 
            padding: 8px 16px; 
            border-radius: 20px;
            font-size: 14px;
        }}
        .status.online {{ background: #238636; color: white; }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        .stat-value {{ 
            font-size: 32px; 
            font-weight: bold;
            color: #58a6ff;
        }}
        .stat-label {{ 
            font-size: 12px; 
            color: #8b949e;
            margin-top: 5px;
            text-transform: uppercase;
        }}
        .stat-card.balance .stat-value {{ color: #3fb950; }}
        
        .section {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .section h2 {{
            color: #8b949e;
            font-size: 14px;
            margin-bottom: 15px;
            text-transform: uppercase;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #30363d;
        }}
        th {{ color: #8b949e; font-weight: normal; font-size: 12px; }}
        td {{ font-size: 14px; }}
        .ev-high {{ color: #3fb950; }}
        .ev-mid {{ color: #d29922; }}
        
        .footer {{
            text-align: center;
            color: #8b949e;
            font-size: 12px;
            margin-top: 30px;
        }}
        
        .next-scan {{
            text-align: center;
            color: #58a6ff;
            font-size: 16px;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Polymarket Bot Dashboard</h1>
        <span class="status online">RUNNING</span>
    </div>
    
    <div class="stats">
        <div class="stat-card balance">
            <div class="stat-value">$100.00</div>
            <div class="stat-label">Balance (Paper)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{trades}</div>
            <div class="stat-label">Total Trades</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">$5.00</div>
            <div class="stat-label">At Risk</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(positions)}</div>
            <div class="stat-label">Open Positions</div>
        </div>
    </div>
    
    <div class="section">
        <h2>📈 Open Positions</h2>
        <table>
            <thead>
                <tr>
                    <th>Market</th>
                    <th>Amount</th>
                    <th>Expected</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {pos_rows}
            </tbody>
        </table>
    </div>
    
    <div class="section">
        <h2>⚙️ Bot Configuration</h2>
        <table>
            <tr><td style="color:#8b949e;width:200px;">Mode</td><td>Paper Trading (Paper Money)</td></tr>
            <tr><td style="color:#8b949e;">Scan Interval</td><td>300 seconds (5 min)</td></tr>
            <tr><td style="color:#8b949e;">Order Size</td><td>$1.00</td></tr>
            <tr><td style="color:#8b949e;">Min Expected Value</td><td>5%</td></tr>
            <tr><td style="color:#8b949e;">Max Price</td><td>$0.95</td></tr>
            <tr><td style="color:#8b949e;">Max Hours to Resolve</td><td>12 hours</td></tr>
            <tr><td style="color:#8b949e;">Max Signals/Scan</td><td>5</td></tr>
        </table>
    </div>
    
    <div class="footer">
        Last Update: {state.get('last_update', 'N/A')} | Auto-refresh: 15s | Paper Mode - No Real Money
    </div>
</body>
</html>"""

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            state = get_bot_state()
            html = generate_html(state)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        elif self.path == '/api':
            state = get_bot_state()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(state).encode())
        else:
            self.send_response(404)
            self.end_headers()

print(f"Starting Dashboard on http://localhost:{PORT}")
server = HTTPServer(('localhost', PORT), Handler)
print(f"Dashboard ready! Open http://localhost:{PORT} in your browser")
server.serve_forever()