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

### 1. Grid Trading Bot (`grid_bot.py`)
- Estratégia: Compra/vende em níveis fixos de preço
- Ideal para mercados laterais
- Configurável: número de níveis, faixa de preço, valor por ordem

**Parâmetros no config.py:**
```python
SYMBOL = 'BTCUSDT'
GRID_LEVELS = 10
PRICE_RANGE_PCT = 5
ORDER_AMOUNT = 10
```

**Executar:**
```bash
python grid_bot.py
```

### 2. Advanced Bot (`advanced_bot.py`)
- Estratégia: Média Móvel + RSI + Bollinger Bands
- Sinais: Cruzamento de médias, sobrecompra/sobvenda
- Stop loss e take profit configuráveis

**Parâmetros:**
```python
short_period = 7
long_period = 25
stop_loss_pct = 2
take_profit_pct = 5
```

**Executar:**
```bash
python advanced_bot.py
```

## Modo Papel (Paper Trading)

Ambos bots iniciam em modo papel por padrão (`paper_mode: True`).
Nenhuma ordem real é executada - apenas simulada.

Para ativar trading real:
```python
'paper_mode': False
# E configurar API key/secret
```

## Modo Real

⚠️ **Aviso importante:**
- Nunca use API key com permissão de saque
- Use apenas permissões de leitura e trading
- Ative 2FA na sua conta Binance
- Comece com valores pequenos para testar

## Arquivos

- `grid_bot.py` - Bot de grid trading
- `advanced_bot.py` - Bot com estratégia avançada
- `config.py` - Configurações
- `*.log` - Logs de execução
- `bot_state.json` - Estado do bot (salvo automaticamente)