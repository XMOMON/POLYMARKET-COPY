#!/bin/bash
set -e

echo "================================================"
echo " Polymarket Copy Trader — Self-Hosted Installer"
echo "================================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Don't run as root. Use a regular user with sudo privileges."
    exit 1
fi

# 1. System update and install dependencies
echo "[1/7] Updating system and installing dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip git curl > /dev/null 2>&1
echo "   ✓ System packages installed"

# 2. Create app directory
APP_DIR="$HOME/polymarket-trader"
echo "[2/7] Creating app directory: $APP_DIR"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# 3. Download bot code from GitHub
echo "[3/7] Downloading Polymarket Copy Trader..."
if [ -d "POLYMARKET-COPY" ]; then
    rm -rf POLYMARKET-COPY
fi
git clone -q https://github.com/XMOMON/POLYMARKET-COPY.git
cd POLYMARKET-COPY
echo "   ✓ Code downloaded"

# 4. Install Python dependencies
echo "[4/7] Installing Python packages..."
pip3 install -q requests
echo "   ✓ Python dependencies installed"

# 5. Prompt for configuration
echo "[5/7] Configuration"
read -p "   Enter your Polymarket wallet private key (leave empty if none): " PRIVATE_KEY
read -p "   Enter SOCKS5 proxy URL (e.g., socks5://IP:PORT) or leave empty if none: " PROXY
read -p "   Enter your license key (provided by seller): " LICENSE_KEY

# 6. Set up environment variables
ENV_FILE="$HOME/.polymarket_env"
echo "Creating environment file: $ENV_FILE"
cat > "$ENV_FILE" << EOF
POLYMARKET_PRIVATE_KEY=$PRIVATE_KEY
ALL_PROXY=$PROXY
EOF
chmod 600 "$ENV_FILE"
echo "   ✓ Environment variables saved"

# 7. Configure copy script to use license
if [ -n "$LICENSE_KEY" ]; then
    echo "[6/7] Activating license..."
    # Write license key to config
    jq --arg key "$LICENSE_KEY" '.scanner.manual_traders = [] | .license_key = $key' copytrade-config.json > copytrade-config.json.tmp && mv copytrade-config.json.tmp copytrade-config.json || echo "   ⚠️  jq not installed, please add license_key manually to config"
    echo "   ✓ License configured"
else
    echo "[6/7] Skipping license key (none provided)"
fi

# 8. Set up cron jobs if user wants
echo "[7/7] Cron jobs"
read -p "   Set up automatic hourly runs? (y/n): " SETUP_CRON
if [ "$SETUP_CRON" = "y" ] || [ "$SETUP_CRON" = "Y" ]; then
    # Add to crontab if not already present
    (crontab -l 2>/dev/null | grep -v "polymarket-trader"; cat << 'EOF'
# Polymarket Copy Trader — hourly jobs
0 * * * * cd $HOME/polymarket-trader/POLYMARKET-COPY && source $HOME/.polymarket_env && python3 polymarket_copytrade.py watch >> /tmp/polymarket_watch.log 2>&1
15 * * * * cd $HOME/polymarket-trader/POLYMARKET-COPY && source $HOME/.polymarket_env && python3 polymarket_copytrade.py copy >> /tmp/polymarket_copy.log 2>&1
30 * * * * cd $HOME/polymarket-trader/POLYMARKET-COPY && source $HOME/.polymarket_env && python3 polymarket_copytrade.py status >> /tmp/polymarket_status.log 2>&1
EOF
    ) | crontab -
    echo "   ✓ Cron jobs installed"
else
    echo "   Skipping cron setup. You can add manually later."
fi

echo ""
echo "================================================"
echo " Installation complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Source your environment: source $ENV_FILE"
echo "2. Run first scan: python3 polymarket_copytrade.py watch"
echo "3. Open dashboard: python3 polymarket_copytrade.py ui"
echo ""
echo "Logs:"
echo "  - Watch: /tmp/polymarket_watch.log"
echo "  - Copy: /tmp/polymarket_copy.log"
echo "  - Status: /tmp/polymarket_status.log"
echo ""
echo "Support: https://github.com/XMOMON/POLYMARKET-COPY/issues"
echo ""
