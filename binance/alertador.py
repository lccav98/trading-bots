#!/usr/bin/env python3
"""Alertador de trades - notifica quando o bot abrir/fechar posição"""
import time
import subprocess
import os

LOG_FILE = "/Users/luizclaudioaraujo/Projetos/trading-bots/binance/bot_real.log"
CICLO = 2  # segundos entre checagens

def notify(title, message):
    """Envia notificação do Mac"""
    try:
        subprocess.run([
            'osascript', '-e',
            f'display notification "{message}" with title "{title}" sound name "Purr"'
        ], check=False, timeout=5)
    except:
        pass
    # Também toca beep no terminal
    print(f"\n{'='*60}")
    print(f"🚨 {title}")
    print(f"{'='*60}")
    print(message)
    print('='*60 + "\n")

def tail_logs():
    print("🛡️  MONITORAMENTO ATIVO - Alertrade")
    print("="*60)
    print("⏳ Aguardando trades...")
    print("ℹ️  Mantenha este terminal aberto")
    print("🛑 Pressione Ctrl+C para parar\n")

    last_pos = 0
    while True:
        try:
            with open(LOG_FILE, 'r') as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                if not new_lines:
                    time.sleep(CICLO)
                    continue

                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Detecta ENTRADA em nova posição
                    if ">>> ⬆️ LONG" in line or ">>> ⬇️ SHORT" in line:
                        parts = line.split(">>> ")[1] if ">>>" in line else line
                        notify("🚀 TRADE ABERTO", parts)

                    # Detecta FECHAMENTO
                    if "EXIT" in line or "tp_tier1" in line or "tp_tier2" in line:
                        notify("✅ POSIÇÃO FECHADA", line.split(" - ")[-1] if " - " in line else line)

                    # Detecta STOP LOSS
                    if "stop_loss" in line and "CLOSE" in line:
                        notify("❌ STOP LOSS ATINGIDO", line.split(" - ")[-1] if " - " in line else line)

                    # Detecta erros críticos
                    if "Invalid API-key" in line:
                        notify("⚠️ ERRO DE API", "IP bloqueado na Binance!")

                last_pos = f.tell()
                time.sleep(CICLO)

        except FileNotFoundError:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoramento encerrado.")
            print(f"💡 Para reiniciar: python3 {__file__}")
            break

if __name__ == "__main__":
    tail_logs()
