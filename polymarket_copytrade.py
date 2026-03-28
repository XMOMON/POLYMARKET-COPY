#!/Users/mac/miniconda3/bin/python
"""
Polymarket Copy Trading Bot
Scans top weekly traders, filters by win rate, and copies their trades.

Usage:
    python3 polymarket_copytrade.py scan          # Scan leaderboard & show top traders
    python3 polymarket_copytrade.py watch          # Update watched traders list
    python3 polymarket_copytrade.py check          # Check for new trades from watched traders
    python3 polymarket_copytrade.py copy           # Copy new trades (dry-run by default)
    python3 polymarket_copytrade.py copy --live    # Copy new trades (REAL orders)
    python3 polymarket_copytrade.py status         # Show current state & watched traders
    python3 polymarket_copytrade.py balance        # Check wallet USDC balance
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import webbrowser
import http.server
import socketserver
import threading

import requests
import os

# Determine if we should disable SSL verification (when using a proxy that uses self-signed certs)
DISABLE_SSL_VERIFY = bool(os.environ.get("ALL_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"))

def get_request_kwargs():
    """Build kwargs for requests.get, including proxies and verify flag."""
    kwargs = {}
    if DISABLE_SSL_VERIFY:
        kwargs["verify"] = False
    proxies = {}
    if os.environ.get("ALL_PROXY"):
        proxies["http"] = os.environ["ALL_PROXY"]
        proxies["https"] = os.environ["ALL_PROXY"]
    if os.environ.get("HTTP_PROXY"):
        proxies["http"] = os.environ["HTTP_PROXY"]
    if os.environ.get("HTTPS_PROXY"):
        proxies["https"] = os.environ["HTTPS_PROXY"]
    if proxies:
        kwargs["proxies"] = proxies
    return kwargs


def fetch_current_prices(token_ids: list) -> dict:
    """Fetch current price for each token from Polymarket CLOB API."""
    prices = {}
    kwargs = get_request_kwargs()
    for token_id in token_ids:
        try:
            url = f"{CLOB_API}/book"
            params = {"token_id": token_id}
            resp = requests.get(url, params=params, timeout=10, **kwargs)
            if resp.status_code == 200:
                book = resp.json()
                bids = book.get("bids", [])
                asks = book.get("asks", [])
                if bids and asks:
                    bid_price = float(bids[0]["price"])
                    ask_price = float(asks[0]["price"])
                    mid_price = (bid_price + ask_price) / 2
                    prices[token_id] = mid_price
                elif asks:
                    prices[token_id] = float(asks[0]["price"])
                elif bids:
                    prices[token_id] = float(bids[0]["price"])
        except Exception as e:
            print(f"Warning: Failed to fetch price for {token_id}: {e}")
    return prices
    """Build kwargs for requests.get, including proxies and verify flag."""
    kwargs = {}
    if DISABLE_SSL_VERIFY:
        kwargs["verify"] = False
    # Set proxies if present in env
    proxies = {}
    if os.environ.get("ALL_PROXY"):
        proxies["http"] = os.environ["ALL_PROXY"]
        proxies["https"] = os.environ["ALL_PROXY"]
    if os.environ.get("HTTP_PROXY"):
        proxies["http"] = os.environ["HTTP_PROXY"]
    if os.environ.get("HTTPS_PROXY"):
        proxies["https"] = os.environ["HTTPS_PROXY"]
    if proxies:
        kwargs["proxies"] = proxies
    return kwargs

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "copytrade-config.json"
STATE_PATH = SCRIPT_DIR / "copytrade-state.json"
STATE_JS_PATH = SCRIPT_DIR / "copytrade-state.js"
TRADE_LOG_PATH = SCRIPT_DIR / "copytrade-trades.log"

# ---------------------------------------------------------------------------
# Polymarket API endpoints
# ---------------------------------------------------------------------------
DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon Mainnet


# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "risk": {
        "max_trade_pct": 0.02,          # 2% of balance per trade
        "max_trades_per_day": 5,
        "min_trade_usdc": 1.0,          # Minimum trade size in USDC
        "max_trade_usdc": 500.0,        # Maximum trade size in USDC
    },
    "scanner": {
        "min_win_rate": 0.70,           # 70% minimum win rate
        "min_resolved_trades": 5,       # At least 5 resolved trades in period
        "max_traders_to_watch": 4,      # Pick up to 4 best traders
        "leaderboard_limit": 10,        # Scan top 10 from leaderboard
        "time_period": "WEEK",          # WEEK, MONTH, DAY
        "categories": ["OVERALL"],      # Categories to scan
    },
    "polling": {
        "trade_check_interval_min": 30,     # Check for new trades every 30 min
        "leaderboard_scan_interval_hrs": 6, # Rescan leaderboard every 6 hours
    },
    "execution": {
        "mode": "dry-run",   # "dry-run" or "live"
        "order_type": "market",  # "market" or "limit"
        "slippage_pct": 0.03,    # 3% max slippage for market orders
    },
    "wallet": {
        "private_key_env": "POLYMARKET_PRIVATE_KEY",
        "funder_env": "POLYMARKET_FUNDER_ADDRESS",
    }
}


def load_config() -> dict:
    """Load config from file, creating defaults if missing."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            user_cfg = json.load(f)
        # Merge with defaults (user overrides)
        cfg = DEFAULT_CONFIG.copy()
        for section, values in user_cfg.items():
            if isinstance(values, dict) and section in cfg:
                cfg[section].update(values)
            else:
                cfg[section] = values
        return cfg
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG


def save_config(cfg: dict):
    """Save config to file."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# State Management
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_STATE = {
    "watched_traders": [],          # List of {wallet, name, win_rate, pnl, selected_at}
    "last_leaderboard_scan": 0,     # Unix timestamp
    "last_trade_check": 0,          # Unix timestamp
    "trades_today": [],             # List of trades placed today
    "trades_today_date": "",        # Date string YYYY-MM-DD
    "trade_history": [],            # Recent trade log (last 50)
    "known_trade_ids": [],          # Activity IDs we've already processed
    "paper_balance": 10000.0,       # Virtual paper balance
    "paper_portfolio": [],          # Virtual paper portfolio positions
    "paper_history": [],            # Closed/executed paper trades
}


def load_state() -> dict:
    """Load state from file."""
    state = DEFAULT_STATE.copy()
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            loaded_state = json.load(f)
        # Merge with defaults for missing keys
        for k, v in DEFAULT_STATE.items():
            if k not in loaded_state:
                loaded_state[k] = v
        state = loaded_state
        
    # Ensure JS state exists for the local HTML dashboard
    if not STATE_JS_PATH.exists():
        save_state(state)
        
    return state


def save_state(state: dict):
    """Save state to JSON and JS file for local browser access."""
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
        
    # Enrich state with floating P&L before exporting to JS
    enriched = state.copy()
    portfolio = state.get("paper_portfolio", [])
    if portfolio:
        token_ids = [p["token_id"] for p in portfolio]
        prices = fetch_current_prices(token_ids)
        total_position_value = 0.0
        for pos in portfolio:
            token_id = pos["token_id"]
            current_price = prices.get(token_id)
            if current_price is not None:
                shares = pos["shares"]
                entry = pos["avg_price"]
                if pos["side"] == "BUY":
                    pos_value = shares * current_price
                else:  # SELL
                    pos_value = pos["cost_usdc"] - (shares * (current_price - entry))
                total_position_value += pos_value
            else:
                total_position_value += pos["cost_usdc"]
        enriched["total_position_value"] = total_position_value
        enriched["unrealized_pnl"] = total_position_value - sum(p["cost_usdc"] for p in portfolio)
    else:
        enriched["total_position_value"] = 0.0
        enriched["unrealized_pnl"] = 0.0

    with open(STATE_JS_PATH, "w") as f:
        f.write("window.POL_STATE = " + json.dumps(enriched, indent=2) + ";")


def reset_daily_trades(state: dict) -> dict:
    """Reset trade counter if it's a new day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("trades_today_date") != today:
        state["trades_today"] = []
        state["trades_today_date"] = today
    return state


# ═══════════════════════════════════════════════════════════════════════════
# Polymarket Data API Functions
# ═══════════════════════════════════════════════════════════════════════════

def scan_leaderboard(cfg: dict) -> list[dict]:
    """
    Fetch top traders from Polymarket leaderboard.
    Returns list of {rank, wallet, name, pnl, volume}.
    """
    scanner = cfg["scanner"]
    traders = []

    for category in scanner["categories"]:
        url = f"{DATA_API}/v1/leaderboard"
        params = {
            "category": category,
            "timePeriod": scanner["time_period"],
            "orderBy": "PNL",
            "limit": scanner["leaderboard_limit"],
        }

        try:
            kwargs = get_request_kwargs()
            resp = requests.get(url, params=params, timeout=15, **kwargs)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  ❌ Error fetching leaderboard ({category}): {e}")
            continue

        for entry in data:
            traders.append({
                "rank": int(entry.get("rank", 0)),
                "wallet": entry.get("proxyWallet", ""),
                "name": entry.get("userName", "Unknown"),
                "pnl": float(entry.get("pnl", 0)),
                "volume": float(entry.get("vol", 0)),
                "category": category,
            })

    # Deduplicate by wallet
    seen = set()
    unique = []
    for t in traders:
        if t["wallet"] not in seen:
            seen.add(t["wallet"])
            unique.append(t)

    return unique


def fetch_positions(wallet: str, limit: int = 200) -> list[dict]:
    """Fetch position history for a trader."""
    url = f"{DATA_API}/positions"
    params = {"user": wallet, "limit": limit}
    try:
        kwargs = get_request_kwargs()
        resp = requests.get(url, params=params, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ❌ Error fetching positions for {wallet[:10]}...: {e}")
        return []


def calculate_win_rate(wallet: str, days: int = 7) -> dict:
    """
    Calculate win rate from a trader's position history.
    Returns {win_rate, wins, losses, total, avg_pnl_pct}.
    """
    positions = fetch_positions(wallet)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    wins = 0
    losses = 0
    total_pnl_pct = 0.0
    resolved = []

    for pos in positions:
        # Only count resolved positions (have an end date and a non-zero cashPnl)
        end_date_str = pos.get("endDate", "")
        cash_pnl = float(pos.get("cashPnl", 0))
        initial_value = float(pos.get("initialValue", 0))

        if not end_date_str:
            continue

        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue

        if end_date < cutoff:
            continue

        if initial_value == 0:
            continue

        resolved.append(pos)
        pnl_pct = float(pos.get("percentPnl", 0))
        total_pnl_pct += pnl_pct

        if cash_pnl > 0:
            wins += 1
        else:
            losses += 1

    total = wins + losses
    win_rate = wins / total if total > 0 else 0.0
    avg_pnl_pct = total_pnl_pct / total if total > 0 else 0.0

    return {
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "total": total,
        "avg_pnl_pct": avg_pnl_pct,
    }


def select_best_traders(traders: list[dict], cfg: dict) -> list[dict]:
    """
    From a list of traders with win rates, select the best 1-4.
    """
    scanner = cfg["scanner"]
    min_wr = scanner["min_win_rate"]
    min_trades = scanner["min_resolved_trades"]
    max_pick = scanner["max_traders_to_watch"]

    # Filter by minimum win rate and trade count
    qualified = [
        t for t in traders
        if t.get("win_rate", 0) >= min_wr and t.get("total_trades", 0) >= min_trades
    ]

    if not qualified:
        return []

    # Sort by: win_rate (desc), pnl (desc), volume (desc)
    qualified.sort(
        key=lambda t: (t.get("win_rate", 0), t.get("pnl", 0), t.get("volume", 0)),
        reverse=True,
    )

    return qualified[:max_pick]


def fetch_recent_activity(wallet: str, since_ts: int = 0, limit: int = 30) -> list[dict]:
    """
    Fetch recent activity for a trader.
    Returns trades newer than since_ts.
    """
    url = f"{DATA_API}/activity"
    params = {"user": wallet, "limit": limit}
    try:
        kwargs = get_request_kwargs()
        resp = requests.get(url, params=params, timeout=15, **kwargs)
        resp.raise_for_status()
        activities = resp.json()
    except Exception as e:
        print(f"  ❌ Error fetching activity for {wallet[:10]}...: {e}")
        return []

    # Filter to only TRADE type and newer than since_ts
    trades = []
    for act in activities:
        if act.get("type") != "TRADE":
            continue
        ts = int(act.get("timestamp", 0))
        if ts > since_ts:
            trades.append(act)

    return trades


# ═══════════════════════════════════════════════════════════════════════════
# Trade Execution
# ═══════════════════════════════════════════════════════════════════════════

def get_clob_client(cfg: dict):
    """Initialize py-clob-client. Returns None if keys not configured."""
    try:
        from py_clob_client.client import ClobClient
    except ImportError:
        print("❌ py-clob-client not installed. Run: pip install py-clob-client")
        return None

    pk = os.environ.get(cfg["wallet"]["private_key_env"], "")
    funder = os.environ.get(cfg["wallet"]["funder_env"], "")

    if not pk:
        print(f"❌ Private key not set. Export {cfg['wallet']['private_key_env']}")
        return None

    try:
        client = ClobClient(
            CLOB_API,
            key=pk,
            chain_id=CHAIN_ID,
            signature_type=0,  # EOA wallet
            funder=funder if funder else None,
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        return client
    except Exception as e:
        print(f"❌ Failed to init CLOB client: {e}")
        return None


def get_balance(cfg: dict) -> Optional[float]:
    """Get USDC balance via CLOB client."""
    client = get_clob_client(cfg)
    if not client:
        return None
    try:
        bal = client.get_balance()
        return float(bal) if bal else 0.0
    except Exception as e:
        print(f"❌ Failed to get balance: {e}")
        return None


def calculate_trade_size(balance: float, cfg: dict) -> float:
    """Calculate trade size based on balance and risk params."""
    risk = cfg["risk"]
    size = balance * risk["max_trade_pct"]
    size = max(size, risk["min_trade_usdc"])
    size = min(size, risk["max_trade_usdc"])
    return round(size, 2)


def copy_trade(trade: dict, cfg: dict, state: dict, live: bool = False) -> Optional[dict]:
    """
    Copy a trade from a watched trader.
    Returns trade record or None if skipped.
    """
    risk = cfg["risk"]

    # Check daily limit
    if len(state["trades_today"]) >= risk["max_trades_per_day"]:
        print(f"  ⚠️  Daily trade limit reached ({risk['max_trades_per_day']})")
        return None

    # Build trade record
    token_id = trade.get("asset", "")
    side = trade.get("side", "BUY")
    price = float(trade.get("price", 0))
    title = trade.get("title", "Unknown")
    outcome = trade.get("outcome", "")
    source_wallet = trade.get("proxyWallet", "")[:10]
    source_name = trade.get("name", "Unknown")

    trade_record = {
        "timestamp": int(time.time()),
        "source_trader": source_name,
        "source_wallet": source_wallet,
        "market": title,
        "outcome": outcome,
        "side": side,
        "price": price,
        "token_id": token_id,
        "status": "pending",
        "mode": "live" if live else "dry-run",
    }

    if not live:
        # Paper Trade mode
        balance = state.get("paper_balance", 10000.0)
        size_usdc = calculate_trade_size(balance, cfg)
        
        if balance < size_usdc or size_usdc < risk["min_trade_usdc"]:
            trade_record["status"] = "skipped"
            trade_record["error"] = f"insufficient paper balance or below min (${size_usdc:.2f})"
            print(f"  ❌ PAPER TRADE SKIPPED: Not enough balance or below minimum trade size.")
            return trade_record

        if price <= 0 or price >= 1:
            trade_record["status"] = "error"
            trade_record["error"] = f"invalid price {price}"
            print(f"  ❌ Invalid price: {price}")
            return trade_record

        shares = size_usdc / price

        # Deduct balance
        state["paper_balance"] = balance - size_usdc
        
        # Add to portfolio
        position = {
            "market": title,
            "outcome": outcome,
            "side": side,
            "shares": shares,
            "avg_price": price,
            "cost_usdc": size_usdc,
            "token_id": token_id,
            "timestamp": int(time.time()),
            "source": source_name
        }
        state["paper_portfolio"].append(position)
        
        trade_record["status"] = "paper"
        trade_record["size_usdc"] = size_usdc
        trade_record["balance_at_trade"] = state["paper_balance"]
        
        print(f"  📝 PAPER BOUGHT: {side} ${size_usdc:.2f} on '{outcome}' @ {price:.2f} (Shares: {shares:.2f})")
        print(f"     Market: {title[:60]}")
        print(f"     Remaining Paper Balance: ${state['paper_balance']:,.2f}")
        return trade_record

    # Live execution
    client = get_clob_client(cfg)
    if not client:
        trade_record["status"] = "error"
        trade_record["error"] = "CLOB client init failed"
        return trade_record

    # Get balance and calculate size
    try:
        balance = float(client.get_balance() or 0)
    except Exception:
        balance = 0.0

    if balance <= 0:
        print(f"  ❌ No USDC balance available")
        trade_record["status"] = "error"
        trade_record["error"] = "no balance"
        return trade_record

    size_usdc = calculate_trade_size(balance, cfg)
    trade_record["size_usdc"] = size_usdc
    trade_record["balance_at_trade"] = balance

    if size_usdc < risk["min_trade_usdc"]:
        print(f"  ❌ Trade size too small: ${size_usdc:.2f}")
        trade_record["status"] = "skipped"
        trade_record["error"] = "below minimum"
        return trade_record

    # Calculate shares from USDC amount
    if price <= 0 or price >= 1:
        print(f"  ❌ Invalid price: {price}")
        trade_record["status"] = "error"
        trade_record["error"] = f"invalid price {price}"
        return trade_record

    try:
        from py_clob_client.clob_types import OrderType
        from py_clob_client.order_builder.constants import BUY as BUY_SIDE, SELL as SELL_SIDE

        order_side = BUY_SIDE if side == "BUY" else SELL_SIDE

        if cfg["execution"]["order_type"] == "market":
            # Market order with slippage protection
            worst_price = price * (1 + cfg["execution"]["slippage_pct"]) if side == "BUY" else price * (1 - cfg["execution"]["slippage_pct"])
            worst_price = min(worst_price, 0.99) if side == "BUY" else max(worst_price, 0.01)

            order = client.create_market_order(
                token_id=token_id,
                side=order_side,
                amount=size_usdc,
                price=round(worst_price, 2),
            )
            resp = client.post_order(order, order_type=OrderType.FOK)
        else:
            # Limit order
            shares = size_usdc / price
            order = client.create_order(
                token_id=token_id,
                price=round(price, 2),
                side=order_side,
                size=round(shares, 2),
                order_type=OrderType.GTC,
            )
            resp = client.post_order(order)

        trade_record["status"] = "placed"
        trade_record["response"] = str(resp)
        print(f"  ✅ PLACED: {side} ${size_usdc:.2f} on '{outcome}' @ {price:.2f}")
        print(f"     Market: {title}")

    except Exception as e:
        trade_record["status"] = "error"
        trade_record["error"] = str(e)
        print(f"  ❌ Order failed: {e}")

    return trade_record


def log_trade(trade_record: dict):
    """Append trade to log file."""
    with open(TRADE_LOG_PATH, "a") as f:
        ts = datetime.fromtimestamp(
            trade_record["timestamp"], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        f.write(f"[{ts}] {json.dumps(trade_record)}\n")
    # Export full trades for dashboard
    export_full_trades_js()


def export_full_trades_js():
    """Read all trades from log and write JS file for dashboard."""
    trades = []
    if TRADE_LOG_PATH.exists():
        with open(TRADE_LOG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    # Format: [timestamp] {json}
                    parts = line.split('] ', 1)
                    if len(parts) == 2:
                        trade_json = parts[1]
                        trade = json.loads(trade_json)
                        trades.append(trade)
                except Exception:
                    continue
    # Write as JS file
    out_path = SCRIPT_DIR / "trades-full.js"
    with open(out_path, "w") as f:
        f.write("window.FULL_TRADES = " + json.dumps(trades, indent=2) + ";")
    return out_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI Commands
# ═══════════════════════════════════════════════════════════════════════════

def cmd_scan(cfg: dict, state: dict):
    """Scan leaderboard and show top traders with win rates."""
    print("🔍 Scanning Polymarket leaderboard...\n")

    traders = scan_leaderboard(cfg)
    if not traders:
        print("❌ No traders found.")
        return

    print(f"{'Rank':<5} {'Name':<25} {'PNL':>15} {'Volume':>15} {'Win Rate':>10} {'W/L':>8}")
    print("─" * 82)

    enriched = []
    for t in traders:
        print(f"  ⏳ Analyzing {t['name'][:20]}...", end="", flush=True)
        wr_data = calculate_win_rate(t["wallet"])
        t.update({
            "win_rate": wr_data["win_rate"],
            "wins": wr_data["wins"],
            "losses": wr_data["losses"],
            "total_trades": wr_data["total"],
            "avg_pnl_pct": wr_data["avg_pnl_pct"],
        })
        enriched.append(t)

        wr_str = f"{wr_data['win_rate']*100:.0f}%" if wr_data["total"] > 0 else "N/A"
        wl_str = f"{wr_data['wins']}/{wr_data['losses']}" if wr_data["total"] > 0 else "-"
        passed = "✅" if wr_data["win_rate"] >= cfg["scanner"]["min_win_rate"] and wr_data["total"] >= cfg["scanner"]["min_resolved_trades"] else "  "

        print(f"\r{passed}{t['rank']:<4} {t['name']:<25} ${t['pnl']:>13,.2f} ${t['volume']:>13,.2f} {wr_str:>10} {wl_str:>8}")

    # Show selection
    selected = select_best_traders(enriched, cfg)
    print(f"\n{'═' * 82}")
    if selected:
        print(f"🏆 Selected {len(selected)} trader(s) to watch:\n")
        for s in selected:
            print(f"  → {s['name']} — WR: {s['win_rate']*100:.0f}% ({s['wins']}W/{s['losses']}L) — PNL: ${s['pnl']:,.2f}")
    else:
        print("⚠️  No traders meet the criteria (>70% win rate, ≥5 trades)")
        print("   Try lowering min_win_rate or min_resolved_trades in config.")

    # Update state
    state["last_leaderboard_scan"] = int(time.time())
    save_state(state)


def cmd_watch(cfg: dict, state: dict):
    """Scan leaderboard and update watched traders list."""
    print("🔍 Scanning leaderboard to update watch list...\n")

    traders = scan_leaderboard(cfg)
    enriched = []
    for t in traders:
        print(f"  ⏳ Analyzing {t['name'][:20]}...", end="", flush=True)
        wr_data = calculate_win_rate(t["wallet"])
        t.update({
            "win_rate": wr_data["win_rate"],
            "wins": wr_data["wins"],
            "losses": wr_data["losses"],
            "total_trades": wr_data["total"],
            "avg_pnl_pct": wr_data["avg_pnl_pct"],
        })
        enriched.append(t)
        wr_str = f"{wr_data['win_rate']*100:.0f}%" if wr_data["total"] > 0 else "N/A"
        print(f"\r  ✓ {t['name'][:20]:<20} WR: {wr_str}")

    selected = select_best_traders(enriched, cfg)

    if not selected:
        print("\n⚠️  No traders meet criteria. Watch list unchanged.")
        return

    # Update state
    now = int(time.time())
    state["watched_traders"] = [
        {
            "wallet": s["wallet"],
            "name": s["name"],
            "win_rate": s["win_rate"],
            "wins": s["wins"],
            "losses": s["losses"],
            "pnl": s["pnl"],
            "selected_at": now,
        }
        for s in selected
    ]
    state["last_leaderboard_scan"] = now
    save_state(state)

    print(f"\n✅ Now watching {len(selected)} trader(s):")
    for s in selected:
        print(f"  👁️  {s['name']} — WR: {s['win_rate']*100:.0f}% — PNL: ${s['pnl']:,.2f}")


def cmd_check(cfg: dict, state: dict):
    """Check watched traders for new trades."""
    watched = state.get("watched_traders", [])
    if not watched:
        print("❌ No traders being watched. Run 'watch' first.")
        return

    since = state.get("last_trade_check", 0)
    if since == 0:
        # Default to 1 hour ago
        since = int(time.time()) - 3600

    print(f"👀 Checking {len(watched)} watched trader(s) for new trades...\n")
    print(f"   Looking for trades after: {datetime.fromtimestamp(since, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")

    all_new_trades = []
    known_ids = set(state.get("known_trade_ids", []))

    for trader in watched:
        name = trader["name"]
        wallet = trader["wallet"]
        print(f"  🔍 {name}...", end="", flush=True)

        trades = fetch_recent_activity(wallet, since_ts=since)

        # Filter out already-known trades
        new_trades = []
        for t in trades:
            trade_id = f"{t.get('transactionHash', '')}_{t.get('timestamp', '')}"
            if trade_id not in known_ids:
                new_trades.append(t)
                known_ids.add(trade_id)

        if new_trades:
            print(f" {len(new_trades)} new trade(s)!")
            for t in new_trades:
                side = t.get("side", "?")
                title = t.get("title", "Unknown")
                outcome = t.get("outcome", "?")
                price = float(t.get("price", 0))
                size = float(t.get("usdcSize", 0))
                print(f"     → {side} '{outcome}' on '{title}' @ {price:.2f} (${size:,.2f})")
        else:
            print(f" no new trades")

        all_new_trades.extend(new_trades)

    # Update state
    state["last_trade_check"] = int(time.time())
    state["known_trade_ids"] = list(known_ids)[-500:]  # Keep last 500
    save_state(state)

    print(f"\n📊 Total new trades found: {len(all_new_trades)}")
    return all_new_trades


def cmd_copy(cfg: dict, state: dict, live: bool = False):
    """Check for new trades and copy them."""
    state = reset_daily_trades(state)

    mode = "🔴 LIVE" if live else "🧪 DRY-RUN"
    print(f"📋 Copy Trading Mode: {mode}\n")

    # Get new trades
    watched = state.get("watched_traders", [])
    if not watched:
        print("❌ No traders being watched. Run 'watch' first.")
        return

    since = state.get("last_trade_check", 0)
    if since == 0:
        since = int(time.time()) - 3600

    known_ids = set(state.get("known_trade_ids", []))
    all_new_trades = []

    for trader in watched:
        trades = fetch_recent_activity(trader["wallet"], since_ts=since)
        for t in trades:
            trade_id = f"{t.get('transactionHash', '')}_{t.get('timestamp', '')}"
            if trade_id not in known_ids:
                t["_source_name"] = trader["name"]
                all_new_trades.append(t)
                known_ids.add(trade_id)

    if not all_new_trades:
        print("✅ No new trades to copy.")
        state["last_trade_check"] = int(time.time())
        state["known_trade_ids"] = list(known_ids)[-500:]
        save_state(state)
        return

    print(f"Found {len(all_new_trades)} new trade(s) to copy:\n")

    for trade in all_new_trades:
        trade["name"] = trade.get("_source_name", "Unknown")
        result = copy_trade(trade, cfg, state, live=live)
        if result:
            state["trades_today"].append(result)
            state["trade_history"].append(result)
            # Keep only last 50 in history
            state["trade_history"] = state["trade_history"][-50:]
            log_trade(result)

    # Export full trades for dashboard
    export_full_trades_js()

    state["last_trade_check"] = int(time.time())
    state["known_trade_ids"] = list(known_ids)[-500:]
    save_state(state)

    placed = sum(1 for t in state["trades_today"] if t.get("status") in ("placed", "paper"))
    print(f"\n📊 Trades today: {placed}/{cfg['risk']['max_trades_per_day']}")


def cmd_status(cfg: dict, state: dict):
    """Show current state."""
    state = reset_daily_trades(state)

    print("📊 Polymarket Copy Trading Status\n")
    print(f"{'═' * 60}")

    # Config summary
    print(f"\n⚙️  Configuration:")
    print(f"   Mode:            {cfg['execution']['mode']}")
    print(f"   Max trade:       {cfg['risk']['max_trade_pct']*100:.0f}% of balance")
    print(f"   Max trades/day:  {cfg['risk']['max_trades_per_day']}")
    print(f"   Min win rate:    {cfg['scanner']['min_win_rate']*100:.0f}%")
    print(f"   Min trades:      {cfg['scanner']['min_resolved_trades']}")

    # Watched traders
    watched = state.get("watched_traders", [])
    print(f"\n👁️  Watched Traders ({len(watched)}):")
    if watched:
        for t in watched:
            age = ""
            if t.get("selected_at"):
                hrs = (time.time() - t["selected_at"]) / 3600
                age = f" (selected {hrs:.0f}h ago)"
            print(f"   → {t['name']} — WR: {t['win_rate']*100:.0f}% ({t['wins']}W/{t['losses']}L){age}")
    else:
        print("   (none — run 'watch' to start)")

    # Today's trades
    trades_today = state.get("trades_today", [])
    print(f"\n📈 Trades Today: {len(trades_today)}/{cfg['risk']['max_trades_per_day']}")
    for t in trades_today[-5:]:
        status_icon = {"placed": "✅", "dry-run": "🧪", "error": "❌", "skipped": "⏭️"}.get(t.get("status"), "❓")
        print(f"   {status_icon} {t.get('side', '?')} '{t.get('outcome', '?')}' on '{t.get('market', '?')[:40]}'")

    # Timestamps
    last_scan = state.get("last_leaderboard_scan", 0)
    last_check = state.get("last_trade_check", 0)
    print(f"\n⏰ Timestamps:")
    print(f"   Last leaderboard scan: {datetime.fromtimestamp(last_scan, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if last_scan else 'never'}")
    print(f"   Last trade check:      {datetime.fromtimestamp(last_check, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if last_check else 'never'}")

    # Wallet
    print(f"\n💰 Wallet:")
    pk_env = cfg["wallet"]["private_key_env"]
    if os.environ.get(pk_env):
        print(f"   Private key: ✅ set via ${pk_env}")
    else:
        print(f"   Private key: ❌ not set (export {pk_env})")


def cmd_balance(cfg: dict):
    """Check wallet balance."""
    print("💰 Checking wallet balance...\n")
    bal = get_balance(cfg)
    if bal is not None:
        print(f"   USDC Balance: ${bal:,.2f}")
        trade_size = calculate_trade_size(bal, cfg)
        print(f"   Trade size (2%): ${trade_size:,.2f}")
    else:
        print("   ❌ Could not fetch balance. Check wallet config.")


def cmd_paper_balance(cfg: dict, state: dict):
    """Check virtual paper money balance."""
    bal = state.get("paper_balance", 10000.0)
    print("💰 Virtual Paper Trading Balance\n")
    print(f"   USDC Balance: ${bal:,.2f} paper money")


def cmd_paper_portfolio(cfg: dict, state: dict):
    """View virtual paper portfolio."""
    portfolio = state.get("paper_portfolio", [])
    bal = state.get("paper_balance", 10000.0)
    print("📁 Virtual Paper Portfolio\n")
    print(f"   Available Cash: ${bal:,.2f}\n")
    
    if not portfolio:
        print("   No active positions.")
        return
        
    for pos in portfolio:
        print(f"   [{pos['side']}] {pos['outcome']} @ ${pos['avg_price']:.3f} | Cost: ${pos['cost_usdc']:.2f} | Shares: {pos['shares']:.2f}")
        print(f"   Market: {pos['market']}")
        print(f"   Copied: {pos['source']}")
        print("   ─" * 40)


def cmd_paper_stats(cfg: dict, state: dict):
    """View paper trading stats."""
    portfolio = state.get("paper_portfolio", [])
    bal = state.get("paper_balance", 10000.0)
    start_bal = 10000.0
    
    total_cost = sum(p["cost_usdc"] for p in portfolio)
    account_value = bal + total_cost  # Assuming current prices = avg_price for simple stats
    
    pnl = account_value - start_bal
    pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
    
    print("📊 Paper Trading Stats\n")
    print(f"   Starting Balance: ${start_bal:,.2f}")
    print(f"   Current Cash:     ${bal:,.2f}")
    print(f"   Active Positions: {len(portfolio)}")
    print(f"   Invested Cost:    ${total_cost:,.2f}")
    print(f"   Net P&L (cost):   {pnl_str}")
    print("\n   Note: P&L is calculated using average entry price. Live market price updates coming soon.")

def cmd_ui(cfg: dict, state: dict):
    """Open the paper trading UI dashboard directly in your local browser."""
    print("🌐 Opening local Web UI Dashboard in your browser...")
    html_path = "file://" + str(SCRIPT_DIR / "dashboard.html")
    webbrowser.open(html_path)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Polymarket Copy Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  scan            Scan leaderboard & show top traders with win rates
  watch           Update watched traders list based on leaderboard
  check           Check for new trades from watched traders
  copy            Copy new trades (paper mode by default)
  status          Show current state & config
  balance         Check live wallet USDC balance
  paper-balance   Check virtual paper money balance
  paper-portfolio Show virtual paper portfolio
  paper-stats     Show paper trading performance
  ui              Open the live Paper Trading Web Dashboard 🌐

Examples:
  %(prog)s scan                  # View top traders
  %(prog)s watch                 # Start watching best traders
  %(prog)s copy                  # Paper trade (zero risk)
  %(prog)s copy --live           # Place REAL orders
  %(prog)s ui                    # View your virtual portfolio dashboard
        """,
    )
    parser.add_argument("command", choices=["scan", "watch", "check", "copy", "status", "balance", "paper-balance", "paper-portfolio", "paper-stats", "ui"])
    parser.add_argument("--live", action="store_true", help="Execute real trades (copy command only)")
    parser.add_argument("--json", action="store_true", help="Output JSON (for script consumption)")

    args = parser.parse_args()

    cfg = load_config()
    state = load_state()

    # ================================================
    # License Check & Tier Enforcement
    # ================================================
    FREE_TIER_MAX_TRADERS = 1
    FREE_TIER_MAX_TRADES = 10

    lic = None
    try:
        from pathlib import Path
        license_path = Path("license.json")
        if license_path.exists():
            from license_check import load_license_from_file
            lic = load_license_from_file(str(license_path))
            if lic:
                print("🔑 Valid license detected — premium features unlocked")
                # License can override limits
                if "max_traders" in lic:
                    cfg["scanner"]["max_traders_to_watch"] = lic["max_traders"]
                if "max_trades_per_day" in lic:
                    cfg["risk"]["max_trades_per_day"] = lic["max_trades_per_day"]
            else:
                print("⚠️  Invalid or expired license — using free tier")
    except Exception as e:
        print(f"⚠️  License check failed: {e} — using free tier")

    if not lic:
        # Enforce free tier limits
        cfg["scanner"]["max_traders_to_watch"] = FREE_TIER_MAX_TRADERS
        cfg["risk"]["max_trades_per_day"] = FREE_TIER_MAX_TRADES

    print(f"\n🦞 Polymarket Copy Trader v1.0")
    print(f"   Config: {CONFIG_PATH}")
    print(f"   State:  {STATE_PATH}")
    print(f"   License: {'✅ Active' if lic else '🆓 Free Tier (1 trader, 10 trades/day)'}")
    print()

    if args.command == "scan":
        cmd_scan(cfg, state)
    elif args.command == "watch":
        cmd_watch(cfg, state)
    elif args.command == "check":
        cmd_check(cfg, state)
    elif args.command == "copy":
        cmd_copy(cfg, state, live=args.live)
    elif args.command == "status":
        cmd_status(cfg, state)
    elif args.command == "balance":
        cmd_balance(cfg)
    elif args.command == "paper-balance":
        cmd_paper_balance(cfg, state)
    elif args.command == "paper-portfolio":
        cmd_paper_portfolio(cfg, state)
    elif args.command == "paper-stats":
        cmd_paper_stats(cfg, state)
    elif args.command == "ui":
        cmd_ui(cfg, state)

if __name__ == "__main__":
    main()
