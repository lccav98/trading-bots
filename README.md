# Trading Bots

This repository contains automated trading bots for multiple platforms:

## 📁 Structure

```
trading-bots/
├── polymarket/   - Polymarket prediction market bot
├── tradovate/    - Tradovate/NinjaTrader 8 integration
└── trxbinary/   - TrxBinary binary options bot
```

## 🚀 Bots

### Polymarket Bot
- Automated trading on Polymarket prediction markets
- Uses Prophet AI for signal confirmation
- Risk management with drawdown protection
- **Status**: ⚠️ API signature bug - waiting for fix

### Tradovate Bot
- Integration with NinjaTrader 8 via OIF
- Real-time market data capture
- Automated order execution
- **Status**: ✅ Working

### TrxBinary Bot
- Binary options trading via Selenium automation
- Demo mode for testing strategies
- Support for EURJPY, EURUSD, and other forex pairs
- **Status**: ✅ Working (demo mode)

## ⚠️ Important Notes

- **TrxBinary**: Only use DEMO mode! Real account has payout issues.
- **Polymarket**: API has a bug with signature_type=1. Working on fix.
- **Tradovate**: Requires NT8 to be running with OIF enabled.

## 📝 Configuration

Each bot has its own configuration. Check individual folders for details.