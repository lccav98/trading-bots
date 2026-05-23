# Binance Trading Bots

Bots automatizados para trading na Binance.

## Instalação

```bash
pip install python-binance pandas numpy
```

## Configuração

Defina as variáveis de ambiente:
```bash
export BINANCE_API_KEY="sua_api_key"
export BINANCE_API_SECRET="seu_api_secret"
export BINANCE_SYMBOL="BTCUSDT"
```

## Bots Disponíveis

### High Frequency Bot (`hf_bot.py`)
- Analisa momentum de curto prazo (1 e 5 candles)
- Filtro de volatilidade para evitar entradas em mercado agitado
- TRXUSDT, timeframe 3m
- Parâmetros otimizados por backtest (180 dias, 972 combinações):

```python
profit_target = 0.007   # 0.7% por trade
stop_loss     = 0.005   # 0.5%
c1_thresh     = 0.002   # momentum 1 candle > 0.2%
c5_thresh     = 0.002   # momentum 5 candles > 0.2%
```

**Executar:**
```bash
python hf_bot.py
```

## Modo Papel (Paper Trading)

O bot inicia em modo papel por padrão. Para ativar trading real, defina no `.env`:

```bash
PAPER_MODE=false
```

## Modo Real

⚠️ **Aviso importante:**
- Nunca use API key com permissão de saque
- Use apenas permissões de leitura e trading
- Ative 2FA na sua conta Binance
- Comece com valores pequenos para testar

## Arquivos

- `hf_bot.py` - Bot principal (único com backtest positivo)
- `webhook_bot.py` - Endpoint Flask para sinais externos (TradingView)
- `config.py` - Configurações globais
- `backtest.py` - Backtest histórico das estratégias
- `optimize.py` - Grid search de parâmetros
- `*.log` - Logs de execução
- `*_state.json` - Estado do bot (salvo automaticamente)