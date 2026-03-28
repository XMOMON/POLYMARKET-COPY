# Selling Guide for Polymarket Copy Trader

This document explains how to sell and manage licenses for the bot.

## Product Tiers

| Tier | Price | Max Traders | Max Trades/Day |
|------|-------|-------------|----------------|
| Free | $0    | 1           | 10             |
| Basic | $49 one-time | 3 | 50 |
| Pro | $99 one-time | 5 | 200 |
| Unlimited | $199 one-time | unlimited | 1000 |

## Generating a License Key

1. Open a terminal in the repository directory.
2. Run the license generator:
   ```bash
   python3 tools/generate_license.py customer@example.com [days_valid]
   ```
   Example:
   ```bash
   python3 tools/generate_license.py alice@example.com 365
   ```
3. This creates a file `license_customer_at_example.com.json`
4. Send that file to the customer. Do NOT share your private key (`license_private_key.pem`).

## What to Include in the Sale

Provide the customer with:
- Download link to the repo (GitHub)
- Their `license.json` file (attached)
- Optional: installation support via Telegram/WhatsApp
- Optional: guide for setting up a VPS (we can provide a document)

## Customer Installation

Customers can either:
1. Use the automated installer (recommended):
   ```bash
   ./install.sh
   ```
   When prompted, paste their license key (the contents of license.json) or provide the file.

2. Manual install (if they skip the installer):
   - Place `license.json` in the working directory
   - Run commands manually

## Verifying a License

If a customer reports "invalid license", ask them to:
- Ensure `license.json` is in the same directory as `polymarket_copytrade.py`
- Check the license hasn't expired
- Send you the contents of `license.json` (you can verify with `tools/generate_license.py` or just check the email matches)

## Revoking a License

If a customer requests a refund or violates terms:
- Add their email to a blocklist (future version may support online revocation)
- For now, we rely on honor system.

## Advertising Channels

- Polymarket Discord
- Reddit: r/polymarket, r/predictionmarkets
- Twitter/X: post screenshots of your own paper trading results
- Telegram groups

## Pricing Strategy

Start with a low price to get early customers ($49 Basic). Collect testimonials. Then raise to $99.

Offer a 30-day money-back guarantee to reduce risk for buyers.

## Support

Provide support via:
- Telegram group (create one)
- GitHub Issues (private repo? we can use the public repo for issues, but label them as license-related)

## Tracking Customers

Keep a simple spreadsheet:
- Email, License key (or filename), Purchase date, Tier, Expiration, Notes

## Upgrades

If a customer wants to upgrade tier:
- Generate a new license with higher limits
- They replace their old `license.json`

## Refunds

Offer refunds within 30 days if the bot doesn't work as advertised (paper mode only). This builds trust.

---

**Remember:** You are selling software, not a trading signal service. Do not guarantee profits. Clearly state that trading involves risk and past performance does not guarantee future results.
