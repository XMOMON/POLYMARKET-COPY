"""
License validation for Polymarket Copy Trader.
Uses RSA digital signatures to verify license keys without online check.
"""
import json
import base64
from pathlib import Path
from typing import Optional, Dict
import time

def load_public_key():
    """Load RSA public key from PEM file."""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        pub_path = Path(__file__).parent / "license_public_key.pem"
        with open(pub_path, "rb") as f:
            public_key = serialization.load_pem_public_key(
                f.read(),
                backend=default_backend()
            )
        return public_key
    except ImportError:
        print("❌ cryptography library not installed. Run: pip install cryptography")
        return None
    except Exception as e:
        print(f"❌ Failed to load public key: {e}")
        return None

def verify_license(license_json: str) -> Dict:
    """
    Verify a license file (JSON string) and return payload if valid.
    Raises exception if invalid.
    """
    try:
        data = json.loads(license_json)
        payload = data["payload"]
        signature = base64.b64decode(data["signature"])
        
        # Recreate the signed data exactly as it was
        signed_data = json.dumps(payload, separators=(',', ':')).encode()
        
        public_key = load_public_key()
        if not public_key:
            raise Exception("Public key unavailable")
        
        # Verify signature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        
        public_key.verify(
            signature,
            signed_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Check expiration
        now = int(time.time())
        if payload["expires_at"] < now:
            raise Exception("License expired")
        
        # Check product
        if payload.get("product") != "polymarket-copy":
            raise Exception("Invalid product")
        
        return payload
    except KeyError as e:
        raise Exception(f"Invalid license format (missing {e})")
    except Exception as e:
        raise Exception(f"License verification failed: {e}")

def load_license_from_file(path: str = "license.json") -> Optional[Dict]:
    """Load and verify license from file."""
    try:
        with open(path, "r") as f:
            content = f.read()
        payload = verify_license(content)
        return payload
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"❌ License error: {e}")
        return None

if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        payload = load_license_from_file(sys.argv[1])
        if payload:
            print("✅ License valid")
            print(json.dumps(payload, indent=2))
        else:
            print("❌ Invalid license")
    else:
        print("Usage: python license_check.py [license.json]")
