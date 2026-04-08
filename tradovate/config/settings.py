# ============================================================
# CONFIGURAÇÕES — Apex Claude Trader
# Edite este arquivo com suas credenciais antes de rodar
# ============================================================

# --- CREDENCIAIS APEX ---
TRADOVATE_USERNAME = "APEX_549417"
TRADOVATE_PASSWORD = "A16@JTWG2@$v"

# --- APP (extraido do JS do site trader.tradovate.com) ---
TRADOVATE_APP_ID = "tradovate_trader(web)"
TRADOVATE_APP_VERSION = "3.260403.0"

# --- AMBIENTE ---
# "demo"  → conta simulada (USE PRIMEIRO para testar)
# "live"  → conta real Apex funded
ENV = "demo"

# --- TOKEN CACHE ---
# Token salvo em disco para evitar re-login a cada execucao
TOKEN_FILE = "data/token.json"

TRADOVATE_API_URL = {
    "demo": "https://demo.tradovateapi.com/v1",
    "live": "https://live.tradovateapi.com/v1",
}

TRADOVATE_WS_URL = {
    "demo": "wss://demo.tradovateapi.com/v1/websocket",
    "live": "wss://live.tradovateapi.com/v1/websocket",
}

TRADOVATE_MD_URL = {
    "demo": "wss://md-demo.tradovateapi.com/v1/websocket",
    "live": "wss://md.tradovateapi.com/v1/websocket",
}

# --- INSTRUMENTO ---
# ES = S&P 500 | MNQ = Micro Nasdaq | MBT = Micro Bitcoin
SYMBOL = "ES"           # Altere para ES (S&P 500) - mais líquido
TIMEFRAME_MINUTES = 5   # Candles de 5 minutos

# --- RISK MANAGEMENT (Apex Express $50K Intraday) ---
# Regras oficiais do plano Express Intraday:
#   Drawdown: $3.000 (intraday, do ponto mais alto)
#   Max contracts: 6 mini / 60 micro
#   Payout: 80/20 (80% seu)
#   Min trading days: nenhum
#   Profit target: $3.000 para primeira retirada

# --- PROTECAO MAXIMA EVITAR PERDAS ---
# Meta: $3000 em 14 dias uteis = $214/dia
# Com 6 contracts: tick=$3, Win=$72, Loss=$36, R/R=1:2
# Target $600/dia a 55% WR => ~6 trades/dia (4W, 2L)
MAX_DAILY_LOSS        = 800.0   # 27% do drawdown — protecao maxima
MAX_DRAWDOWN          = 3000.0  # Drawdown intraday oficial Express
POSITION_SIZE         = 6       # max Apex — necessario para meta $3k
POSITION_SIZE_MINI    = 6       # contratos MNQ (mini) — max 6
POSITION_SIZE_MICRO   = 60      # contratos MES/MNQ (micro) — max 60
MAX_CONTRACTS_MINI    = 6       # Limite Apex mini contracts
MAX_CONTRACTS_MICRO   = 60      # Limite Apex micro contracts
STOP_LOSS_TICKS       = 25      # Stop minimo em ticks (6.25 pts, ~0.5×ATR em dias normais)
TAKE_PROFIT_TICKS     = 38      # Take profit minimo em ticks (~9.5 pts, R/R ~1:1.5)
MIN_SCORE_TO_TRADE    = 3       # Score minimo para entry (3 = mais trades, 4 = mais seletivo)

# --- RISK MANAGEMENT AVANCADO ---
RISK_PER_TRADE            = 2.0    # % do capital arriscado — compativel com 6 contracts
MAX_DAILY_PROFIT          = 600.0  # Meta diaria: $214 base + margem de seguranca
MAX_CONSECUTIVE_LOSSES    = 2      # Apos 2 perdas seguidas — PARA IMEDIATAMENTE
TRAILING_STOP_TRIGGER_TICKS = 8    # Ativa trailing apos 8 ticks favoraveis
BREAK_EVEN_TRIGGER_TICKS  = 4      # Move SL para breakeven apos 4 ticks favoraveis

# --- ESTRATÉGIA (Bollinger Bands + Stochastic) ---
BB_PERIOD   = 20
BB_STD      = 2.0
STOCH_K     = 14
STOCH_D     = 3
STOCH_SLOW  = 3
STOCH_OVERSOLD    = 20
STOCH_OVERBOUGHT  = 80

# --- HORARIOS PERMITIDOS (UTC-3 Brasilia) ---
TRADE_START_HOUR = 9   # 09:00 BRT (abertura NYSE)
TRADE_END_HOUR   = 21  # 21:00 BRT (market open, captura NY close e pos-mercado)
AVOID_NEWS       = True  # Pausa automatica 5min antes/depois de noticias

# --- EXECUCAO DE ORDENS AUTOMATICA ---
# True  = bot envia ordens automaticamente via Tradovate API
# False = apenas gera sinais (usuario opera manualmente)
AUTO_EXECUTE_TRADES = True

# --- MODO SIMULACAO TESTE ---
# True = simula trades virtuais (acompanha preco, aplica SL/TP, calcula P&L)
#        NAO envia ordens reais. Serve para validar a estrategia.
DEMO_SIMULATION = False
