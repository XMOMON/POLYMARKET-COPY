#!/usr/bin/env python3
"""
License generator for Polymarket Copy Trader.
Run this to create a license.json for a customer.
Usage: python3 tools/generate_license.py customer@email.com [days_valid]
"""
import json
import time
import base64
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

PRIVATE_KEY_PATH = Path(__file__).parent.parent / "license_private_key.pem"

def sign_license(customer_email: str, days_valid: int = 365) -> dict:
    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    
    payload = {
        "email": customer_email,
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + days_valid * 86400,
        "product": "polymarket-copy",
        "version": "1.0"
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
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 generate_license.py customer@email.com [days_valid]")
        sys.exit(1)
    
    email = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    
    lic = sign_license(email, days)
    output = json.dumps(lic, indent=2)
    print(output)
    
    # Save to file for convenience
    out_file = f"license_{email.replace('@','_at_')}.json"
    with open(out_file, "w") as f:
        f.write(output)
    print(f"\nSaved to: {out_file}")

if __name__ == "__main__":
    main()
