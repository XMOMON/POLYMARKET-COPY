#!/usr/bin/env python3
"""
License generator for Polymarket Copy Trader.
Run this to create a license.json for a customer.
Usage: python3 tools/generate_license.py customer@email.com [--tier basic|pro|unlimited] [--days 365]
"""
import json
import time
import base64
import argparse
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

PRIVATE_KEY_PATH = Path(__file__).parent.parent / "license_private_key.pem"

TIER_LIMITS = {
    "basic": {"max_traders": 3, "max_trades_per_day": 50},
    "pro": {"max_traders": 5, "max_trades_per_day": 200},
    "unlimited": {"max_traders": 1000, "max_trades_per_day": 1000},
}

def sign_license(customer_email: str, days_valid: int = 365, tier: str = "basic") -> dict:
    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    
    limits = TIER_LIMITS.get(tier, {"max_traders": 1, "max_trades_per_day": 10})
    
    payload = {
        "email": customer_email,
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + days_valid * 86400,
        "product": "polymarket-copy",
        "version": "1.0",
        "max_traders": limits["max_traders"],
        "max_trades_per_day": limits["max_trades_per_day"],
    }
    
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
    
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    return {
        "payload": payload,
        "signature": base64.b64encode(signature).decode()
    }

def main():
    parser = argparse.ArgumentParser(description="Generate a license key for Polymarket Copy Trader")
    parser.add_argument("email", help="Customer email")
    parser.add_argument("--tier", choices=["basic", "pro", "unlimited"], default="basic", help="License tier")
    parser.add_argument("--days", type=int, default=365, help="Days valid (default 365)")
    
    args = parser.parse_args()
    
    lic = sign_license(args.email, args.days, args.tier)
    output = json.dumps(lic, indent=2)
    print(output)
    
    # Save to file for convenience
    safe_email = args.email.replace('@', '_at_').replace('.', '_dot')
    out_file = f"license_{safe_email}_{args.tier}.json"
    with open(out_file, "w") as f:
        f.write(output)
    print(f"\nSaved to: {out_file}")

if __name__ == "__main__":
    main()
