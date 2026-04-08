# Apex Claude Trader
Bot de trading automatizado: **Claude Code → Tradovate API → Apex Trader Funding**

Estratégia: Bollinger Bands + Stochastic Oscillator | Futuros: MNQ / MES / MBT

---

## Estrutura do Projeto

```
apex-claude-trader/
├── main.py                  ← Ponto de entrada — rode este arquivo
├── requirements.txt
├── config/
│   └── settings.py          ← ⚠️ EDITE AQUI com suas credenciais
├── core/
│   ├── auth.py              ← Autenticação Tradovate (Bearer token)
│   ├── market_data.py       ← WebSocket — candles em tempo real
│   ├── executor.py          ← Envio de ordens REST API
│   └── risk.py              ← Risk management (regras Apex)
├── skills/
│   └── strategy.py          ← Análise técnica (BB + Stoch)
└── logs/
    └── trader.log           ← Log de operações (gerado automaticamente)
```

---

## Instalação

```bash
cd apex-claude-trader
pip install -r requirements.txt
```

---

## Configuração (OBRIGATÓRIO antes de rodar)

Edite `config/settings.py`:

1. **Credenciais Apex**
   - Preencha: `TRADOVATE_USERNAME`, `TRADOVATE_PASSWORD` (mesmo login/senha da plataforma)

2. **Ambiente**
   ```python
   ENV = "demo"  # mude para "live"
   ```

3. **Risk Management** — ajuste aos limites do seu plano Apex
   ```python
   MAX_DAILY_LOSS    = 500.0   # Seu daily loss limit
   MAX_DRAWDOWN      = 1500.0  # Seu trailing drawdown
   POSITION_SIZE     = 1       # Contratos por trade
   STOP_LOSS_TICKS   = 10      # Ticks de stop
   TAKE_PROFIT_TICKS = 20      # Ticks de alvo
   ```

---

## Execução

```bash
# Modo demo (simulado) — TESTE PRIMEIRO
python main.py

# Para rodar em background (Linux/Mac)
nohup python main.py &
```

---

## Lógica da Estratégia

### Sinal de COMPRA
- Preço fecha **na ou abaixo da banda inferior** de Bollinger
- Stochastic K < 20 (sobrevenda) **e K cruzando acima de D**

### Sinal de VENDA
- Preço fecha **na ou acima da banda superior** de Bollinger
- Stochastic K > 80 (sobrecompra) **e K cruzando abaixo de D**

### Saída
- Automática via ordem bracket (SL + TP enviados junto com a entrada)

---

## Regras Apex respeitadas automaticamente

| Regra | Implementação |
|---|---|
| Daily loss limit | `RiskManager.MAX_DAILY_LOSS` |
| Trailing drawdown | `RiskManager.MAX_DRAWDOWN` |
| Sem pirâmide | Bloqueia nova ordem com posição aberta |
| Flag `isAutomated: true` | Obrigatório CME — incluído em todas as ordens |
| Horário restrito | `TRADE_START_HOUR` / `TRADE_END_HOUR` |

---

## ⚠️ Avisos Importantes

- **Sempre teste em `ENV = "demo"` antes de usar com conta real**
- Futuros envolvem risco substancial de perda
- Monitore o bot regularmente — não é "set and forget"
- Mantenha logs para auditoria da Apex
- Em caso de problema, use `executor.flatten_position()` para fechar tudo

---

## Próximos passos sugeridos

- [ ] Adicionar filtro de notícias econômicas (evitar NFP, CPI, FOMC)
- [ ] Dashboard de monitoramento em tempo real
- [ ] Backtesting com dados históricos
- [ ] Alertas via Telegram ou e-mail
