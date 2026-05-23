#!/usr/bin/env python3
"""
Monitor ativo para o Futures Bot V2
Alerta imediatamente quando trades são abertos/fechados
"""
import time
import sys

LOG_FILE = "bot_real.log"
CHECK_INTERVAL = 5  # seconds

# Keywords to watch for
ALERT_PATTERNS = [
    ">>> LONG", ">>> SHORT",  # Entry signals
    "EXIT", "stop_loss", "trail_stop", "time_stop",  # Exits
    "tp_tier1", "tp_tier2",  # Take profits
    "ERROR", "Falha",  # Errors
    "PnL=",  # Cycle PnL
]

def tail_f(filename):
    """Generator to tail a file"""
    with open(filename, 'r') as f:
        f.seek(0, 2)  # Go to end
        while True:
            line = f.readline()
            if not line:
                time.sleep(CHECK_INTERVAL)
                continue
            yield line.strip()

def main():
    print("=" * 60)
    print("🛡️  MONITORAMENTO ATIVO - Futures Bot V2")
    print("=" * 60)
    print("\n✅ Modo REAL | Leverage 3x | R:R 3:1")
    print("⚠️  O monitor alertará imediatamente quando:")
    print("   - Um trade for aberto (LONG/SHORT)")
    print("   - Um stop-loss for atingido")
    print("   - Um erro crítico ocorrer")
    print("   - Ciclo de PnL for concluído")
    print(f"\n📊 Escaneando: {LOG_FILE}\n")
    print("=" * 60)
    
    try:
        for line in tail_f(LOG_FILE):
            for pattern in ALERT_PATTERNS:
                if pattern in line:
                    if ">>>" in line:
                        print(f"🚨 SINAL DETECTADO: {line}")
                    elif "stop_loss" in line or "trail_stop" in line:
                        print(f"❌ PERDA: {line}")
                    elif "tp_" in line:
                        print(f"✅ LUCRO: {line}")
                    elif "ERROR" in line or "Falha" in line:
                        print(f"⚠️  ERRO: {line}")
                    elif "PnL=" in line:
                        print(f"📊 CICLO: {line}")
                    else:
                        print(f"ℹ️  {line}")
                    break
    except KeyboardInterrupt:
        print("\n\nMonitoramento encerrado.")
        print("Dica: Use 'tail -f bot_real.log' para ver todos os logs.")
        sys.exit(0)

if __name__ == "__main__":
    main()
