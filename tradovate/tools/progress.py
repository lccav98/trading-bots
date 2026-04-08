"""
tools/progress.py — Tracker de progresso para meta de payout
"""

from datetime import datetime
import os
import json

PROGRESS_FILE = "data/progress.json"

GOAL_USD     = 3000.0
DEADLINE     = datetime(2026, 4, 26)  # 25/04/2026 ultimo dia

def load_progress():
    """Carrega progresso acumulado."""
    journal_file = "data/trading_journal.json"
    total = 0.0
    if os.path.exists(journal_file):
        try:
            entries = json.loads(open(journal_file).read())
            for e in entries:
                if "pnl" in e:
                    total += e["pnl"]
        except:
            pass
    return total

def status():
    """Imprime status do progresso ate a meta."""
    done = load_progress()
    today = datetime.now()
    days_left = (DEADLINE - today).days
    needed = GOAL_USD - done
    daily_needed = needed / max(1, days_left) if days_left > 0 else needed

    pct = min(100, max(0, (done / GOAL_USD) * 100))

    return {
        "done": round(done, 2),
        "goal": GOAL_USD,
        "pct": round(pct, 1),
        "days_left": days_left,
        "needed": round(needed, 2),
        "daily_needed": round(daily_needed, 2),
    }

if __name__ == "__main__":
    s = status()
    print(f"Meta: ${s['goal']:.2f}")
    print(f"Feito: ${s['done']:.2f} ({s['pct']}%)")
    print(f"Dias uteis: {s['days_left']}")
    print(f"Necessario/dia util: ${s['needed']:.2f} total, ${s['daily_needed']:.2f}/dia")
