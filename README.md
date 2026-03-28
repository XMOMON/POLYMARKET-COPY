# Polymarket Copy Trading Bot

Paper-trading bot that copies top traders on Polymarket automatically.

## Features

- Scans leaderboard for top weekly traders
- Filters by win rate and volume
- Automatically copies trades in dry-run mode
- Dashboard with portfolio, stats, and full trade history
- Telegram alerts for new trades
- Configurable risk limits

## Setup

1. Clone repo
2. Install dependencies:
   ```bash
   pip install requests pandas
   ```
3. Configure `copytrade-config.json` (risk limits, API settings)
4. Set environment variables:
   - `ALL_PROXY` (optional, for Tor/ socks5 proxy)
5. Run commands:

   ```bash
   # Scan leaderboard and update watched traders
   python3 polymarket_copytrade.py watch

   # Check for new trades
   python3 polymarket_copytrade.py check

   # Copy trades (dry-run)
   python3 polymarket_copytrade.py copy

   # Open dashboard
   python3 polymarket_copytrade.py ui
   ```

## Cron Jobs (Automation)

Set up via OpenClaw or system cron:

- `watch` every 1 hour
- `copy` every 1 hour (or desired frequency)
- `status` every 5 minutes to update dashboard prices

## Configuration

Edit `copytrade-config.json`:

- `risk.max_trades_per_day` — max trades per day (default 5)
- `scanner.min_win_rate` — minimum trader win rate (0-1)
- `scanner.max_traders_to_watch` — number of top traders to follow
- `execution.mode` — "dry-run" or "live"

## Live Trading

To trade with real money:

1. Set `POLYMARKET_PRIVATE_KEY` environment variable with your wallet private key
2. Change `execution.mode` to `"live"`
3. Ensure wallet has USDC on Polygon

**WARNING:** Live trading involves risk. Test thoroughly in dry-run first.

## Dashboard

Open `dashboard.html` in browser or run `python3 polymarket_copytrade.py ui` to launch local server.

Shows:
- Paper balance and P&L
- Active portfolio
- Full trade history
- Watched traders stats
- Equity curve

## Files

- `polymarket_copytrade.py` — main bot
- `copytrade-config.json` — configuration
- `dashboard.html` — web UI
- `copytrade-state.js` — generated state for dashboard
- `trades-full.js` — generated full trade log
- `copytrade-trades.log` — raw trade log

## License

MIT