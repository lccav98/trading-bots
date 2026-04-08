# Apex Claude Trader — Estado da Sessao

## MODO ATUAL: SINAIS (v3)
Bot analisa mercado e gera sinais com entry/SL/TP. Usuario opera manualmente no trader.tradovate.com.

## PROBLEMA DA API DE ORDENS
- API auth direta: appId "tradovate_trader_web" revogado ("The app is not registered")
- App ID antigo: rate-limited com captcha
- Ordens via API externa: SEMPRE retornam "Access is denied" (testado: Bearer, Bearer+Origin, Bearer+Cookies, browser fetch)
- Read (account/list, position/list) via API: funciona
- **Solucao adotada: modo sinais com alerta sonoro**

## CREDENCIAIS (NUNCA EXPOR)
- Usuario: APEX_549417 | Conta demo: APEX5494170000001 (ID: 45402487)
- Base DEMO: https://demo.tradovateapi.com/v1
- Base LIVE: https://live.tradovateapi.com/v1
- Config: `config/settings.py`

## ARQUIVOS PRINCIPAIS
- `main.py` — Modo sinais, alertas sonoros
- `core/auth.py` — TradovateAuth (async)
- `core/market_data.py` — Candles via yfinance
- `core/risk.py` — Risk management
- `core/executor.py` — Executor (nao funciona para ordens, manter apenas metodos de leitura)
- `skills/strategy.py` — Motor multi-estrategia
- `skills/adaptive_threshold.py` — Threshold dinamico
- `skills/news_filter.py` — Filtro noticias/volatilidade

## CONFIGS
- SYMBOL=MNQ | TIMEFRAME=5min | Min Score=4 (adaptativo)
- Horario: 9h-21h BRT | Max daily loss=$800 | Max daily profit=$600
- Stop=16 ticks | TP=40 ticks | R/R 1:2.5

## DADOS
- `data/signals.json` — Registro de sinais
- `data/trading_journal.json` — Historico de trades
- `data/recovery_state.json` — Estado de recovery
- `data/token.json` — Token cache

## IMPORTANTE PARA PROXIMAS SESSOES
1. Nao tentar usar API externa para ordens — SEPRE falha
2. Se quiser automacao de ordens, usar Tradovate Desktop + bridge ou NinjaTrader
3. Executor pode ser simplificado: manter só get_positions() e get_account_status()
4. Sinal sonoro: `winsound.Beep()` no main.py
