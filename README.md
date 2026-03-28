# Polymarket Copy Trading Bot

Automatically copy top traders on Polymarket in paper (simulation) mode. Includes a live dashboard with P&L, trade history, and equity curve.

## Quick Start (5 minutes)

### Option A: Automated Installer (Easiest)

We provide a one-command installer for Ubuntu/Debian:

```bash
git clone https://github.com/XMOMON/POLYMARKET-COPY.git
cd POLYMARKET-COPY
chmod +x install.sh
./install.sh
```

The installer will:
- Install system dependencies
- Set up Python environment
- Ask for your Polymarket private key (optional)
- Configure proxy if needed
- Set up hourly cron jobs
- Generate `license.json` if you provide a license key

After installation, simply run:
```bash
source $HOME/.polymarket_env   # if you set private key
python3 polymarket_copytrade.py watch   # first scan
python3 polymarket_copytrade.py ui      # open dashboard
```

### Option B: Manual Setup

If you prefer to install manually (or on macOS):

```bash
git clone https://github.com/XMOMON/POLYMARKET-COPY.git
cd POLYMARKET-COPY
pip3 install -r requirements.txt
```

Continue with step 3 below.

That's it! The bot will now check every hour for new trades and update the dashboard automatically (if you set up cron — see below).

---

## What You Get

- **Paper trading** — no real money involved by default
- **Automatic copying** — bot mimics trades from top traders
- **Web dashboard** — see balance, positions, P&L, full history
- **Equity curve** — track performance over time
- **Telegram alerts** — get notified when new trades are copied (optional)

---

## Licensing & Upgrades

This bot is provided **free of charge** with the following limitations:

- **Free tier:** 1 watched trader, max 10 trades per day

If you need higher limits (more traders, more trades per day), purchase a license key:

- **Basic License** ($49 one-time): Up to 3 traders, 50 trades/day
- **Pro License** ($99 one-time): Up to 5 traders, 200 trades/day
- **Unlimited** ($199 one-time): No limits

A license key removes the restrictions and supports ongoing development.

### How to Use a License Key

After installation, place your `license.json` file in the bot directory (same folder as `polymarket_copytrade.py`). The installer can also accept a license key and generate this file for you.

You'll see a message on startup: "🔑 Valid license detected".

### Purchasing a License

Contact the seller (or visit our Telegram channel) to purchase a license. You'll receive a `license.json` file via email. Simply place it in the working directory.

---

## Detailed Setup

### Prerequisites

- macOS or Linux (Windows works with WSL)
- Python 3.9 or higher
- Git
- Internet connection (proxy may be required depending on your location)

### Installation Steps

```bash
# 1. Clone repository
git clone https://github.com/XMOMON/POLYMARKET-COPY.git
cd POLYMARKET-COPY

# 2. Install Python packages
pip3 install requests

# 3. (Optional) Set up a proxy if needed
   If you can't access Polymarket, get a SOCKS5 proxy from:
   - https://free-proxy-list.net/en/us-proxy.html
   - https://spys.one/en/socks-proxy-list/
   - https://www.freeproxy.world/?type=socks5

   Then export:
   ```bash
   export ALL_PROXY="socks5://IP:PORT"
   ```
   For authentication: `socks5://user:pass@IP:PORT`

   Make it permanent by adding the export line to your `~/.zshrc` or `~/.bashrc`.
   Test with: `curl -s https://api.ipify.org`
```

### First Run

Initialize the watch list and generate the dashboard:

```bash
# Scan leaderboard and pick top traders
python3 polymarket_copytrade.py watch

# Check for new trades (dry-run simulation)
python3 polymarket_copytrade.py copy

# Open dashboard (starts a local server)
python3 polymarket_copytrade.py ui
```

You should see:
- terminal output showing trades being copied (paper)
- browser window opening to `http://localhost:8080` with your dashboard

---

## Automation (Cron Jobs)

The bot can run automatically in the background. Use `crontab -e` to add:

```bash
# Every hour: update watched traders (leaderboard scan)
0 * * * * cd /path/to/POLYMARKET-COPY && python3 polymarket_copytrade.py watch

# Every hour: check and copy new trades
15 * * * * cd /path/to/POLYMARKET-COPY && python3 polymarket_copytrade.py copy

# Every hour: refresh dashboard prices (updates floating P&L)
30 * * * * cd /path/to/POLYMARKET-COPY && python3 polymarket_copytrade.py status
```

Or if you use OpenClaw on your machine, you can add these as OpenClaw cron jobs (see its docs).

---

## Configuration

Edit `copytrade-config.json` before running:

### Basic options

```json
{
  "risk": {
    "max_trades_per_day": 20,          // Maximum trades per day
    "max_trade_usdc": 100.0,           // Maximum USDC per trade (paper size)
    "min_trade_usdc": 1.0              // Minimum trade size
  },
  "execution": {
    "mode": "dry-run",                 // "dry-run" (paper) or "live"
    "order_type": "market"             // "market" or "limit"
  }
}
```

### Choose traders to copy

**Option A: Automatic leaderboard scan (default)**

```json
"scanner": {
  "min_win_rate": 0.70,              // Only traders with >=70% win rate
  "min_resolved_trades": 5,          // At least 5 resolved trades
  "max_traders_to_watch": 4,         // Number of top traders to copy
  "leaderboard_limit": 10,           // How many leaderboard entries to scan
  "time_period": "WEEK",             // Performance window: WEEK, MONTH, DAY
  "categories": ["SPORTS","CRYPTO","POLITICS"]
}
```

**Option B: Manual trader selection** (override leaderboard)

Add wallet addresses directly:

```json
"scanner": {
  "manual_traders": [
    {
      "wallet": "0x1234...abcd",
      "name": "TraderOne"
    },
    {
      "wallet": "0x5678...efgh",
      "name": "TraderTwo"
    }
  ]
}
```

When `manual_traders` is non-empty, the `watch` command will analyze only those wallets and copy their trades. You can still set `max_traders_to_watch` but it's ignored — all manual traders are followed.

> **Note on limits:** The free tier restricts `max_traders_to_watch` to 1 and `max_trades_per_day` to 10, regardless of your config. A paid license key (see [Licensing & Upgrades](#licensing--upgrades)) raises these caps.

---

## Automation (Cron Jobs)

---

## Dashboard

The dashboard (`dashboard.html`) shows:

- **Virtual Balance** — cash available
- **Total Invested** — sum of open positions
- **Est. P&L** — floating profit/loss (updated hourly)
- **Win Rate** — based on resolved trades (N/A while paper)
- **Total Trades** — all-time copied trades
- **Active Positions** — currently open bets
- **Equity Curve** — balance over time
- **Active Portfolio** — list of open positions with current value
- **Watched Traders** — top traders you're following
- **Full Trade History** — every simulated trade with timestamps

Access it:
- Run `python3 polymarket_copytrade.py ui` (starts local server)
- Or open `dashboard.html` directly in browser (file://...)
- For remote access, serve via `python3 -m http.server 8080` and use your LAN IP

---

## Going Live (Real Money)

**WARNING:** Only proceed when you understand the risks.

1. Fund your Polymarket wallet with USDC on Polygon
2. Export your wallet private key (keep it secret!)
3. Set environment variable:
   ```bash
   export POLYMARKET_PRIVATE_KEY="your_private_key_here"
   ```
   (Add to `~/.zshrc` to persist)

4. Edit `copytrade-config.json`:
   ```json
   "execution": { "mode": "live" }
   ```

5. Restart the bot: `python3 polymarket_copytrade.py copy`

The bot will now place real orders on Polymarket.

---

## Common Issues

**Dashboard shows no data?**
- Run `python3 polymarket_copytrade.py status` to generate state files
- Ensure you've run `watch` and `copy` at least once

**Rate limit errors?**
- Increase intervals in cron (e.g., every 2 hours)
- Reduce `leaderboard_limit` and `max_traders_to_watch`

**No trades being copied?**
- Check `watch` output — are traders showing with high win rates?
- Ensure `trades_today` hasn't hit `max_trades_per_day` limit
- Markets may be settled/closed — bot only copies active markets

**Cannot fetch prices / API errors?**
- Check your proxy settings (`ALL_PROXY`)
- Polymarket API may be temporarily down

---

## Files

- `polymarket_copytrade.py` — main bot (run all commands from here)
- `copytrade-config.json` — configuration (risk, scanner, execution)
- `dashboard.html` — web dashboard UI
- `copytrade-state.js` — generated state file (auto)
- `trades-full.js` — full trade log (auto)
- `copytrade-trades.log` — raw trade log (auto)

---

## Support

- Issues: https://github.com/XMOMON/POLYMARKET-COPY/issues
- Polymarket docs: https://docs.polymarket.com

---

## License

MIT