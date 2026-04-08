"""
Utilitario: abre navegador, faz login na Tradovate, salva token.
Rode ANTES do bot principal se nao tem token salvo.
"""

from core.auth import TradovateAuth

auth = TradovateAuth()
ok = auth.authenticate()
if ok:
    print(f"\nTOKEN: {auth.access_token[:40]}...")
    print(f"Conta:  {auth.account_spec} (ID: {auth.account_id})")
    print(f"Expira: {int((auth.token_expiry - __import__('time').time()) / 60)} min restante")
else:
    print("Falha na autenticacao")
