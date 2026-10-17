import hashlib
import hmac
import json
import base64
import os
import re
import secrets
import time
from sqlalchemy.orm import Session
from app.config import settings

_challenges = {}

DIGIT_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ek": "1", "do": "2", "teen": "3", "char": "4", "chaar": "4",
    "paanch": "5", "cheh": "6", "chhe": "6", "saat": "7", "aath": "8",
    "nau": "9", "shunya": "0"
}

def normalize_digits(text: str) -> str:
    """Extract and normalize digit characters or words to space-separated digits."""
    cleaned = text.lower().strip()
    tokens = re.split(r"[\s,\-\.]+", cleaned)
    extracted = []
    for token in tokens:
        if token.isdigit():
            for ch in token:
                extracted.append(ch)
        elif token in DIGIT_WORDS:
            extracted.append(DIGIT_WORDS[token])
    if not extracted:
        # Fallback to direct digits
        direct = re.findall(r"\d", cleaned)
        return " ".join(direct)
    return " ".join(extracted)

def create_challenge(user_id: int):
    phrase = " ".join(str(secrets.randbelow(10)) for _ in range(3))
    token = secrets.token_urlsafe(24)
    _challenges[token] = {
        "user_id": user_id,
        "phrase": phrase,
        "expires": time.time() + 90,
        "used": False
    }
    return {"token": token, "phrase": phrase, "expires_in_seconds": 90}

def verify_challenge(user_id: int, token: str, spoken: str):
    c = _challenges.get(token)
    if not c or c["user_id"] != user_id or c["used"] or time.time() > c["expires"]:
        return False
    c["used"] = True  # Single-use challenge
    normalized_spoken = normalize_digits(spoken)
    return normalized_spoken == c["phrase"]

def pin_digest(pin: str, salt: str = "voice-demo"):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 260000).hex()

def make_pin_hash(pin: str, salt: str = "voice-demo"):
    return f"pbkdf2-sha256:{salt}:{pin_digest(pin, salt)}"

def check_pin_raw(supplied: str, expected_hash: str) -> bool:
    try:
        parts = expected_hash.split(":", 2)
        if len(parts) == 3 and parts[0] == "pbkdf2-sha256":
            algo, salt, digest = parts
            return hmac.compare_digest(pin_digest(supplied, salt), digest)
    except Exception:
        pass
    return False

def verify_pin_for_user(user, supplied_pin: str, db: Session | None = None):
    """
    Validates user PIN with database-backed lockout tracking.
    Locks after 5 failed attempts.
    """
    if getattr(user, "is_locked", False):
        return False, "locked"

    valid = check_pin_raw(supplied_pin, getattr(user, "pin_hash", ""))
    if not valid:
        if hasattr(user, "failed_attempts"):
            user.failed_attempts = getattr(user, "failed_attempts", 0) + 1
            if user.failed_attempts >= 5:
                user.is_locked = True
            if db:
                db.commit()
            if user.is_locked:
                return False, "locked"
        return False, "invalid"

    if hasattr(user, "failed_attempts") and user.failed_attempts > 0:
        user.failed_attempts = 0
        if db:
            db.commit()
    return True, "ok"

# Legacy compatibility function for existing tests
def verify_pin(user_id: int, supplied: str, expected_hash: str):
    valid = check_pin_raw(supplied, expected_hash)
    if not valid:
        return False, "invalid"
    return True, "ok"

def create_access_token(user_id: int, username: str, role: str, expires_in: int = 86400) -> str:
    """Create a tamper-evident signed bearer token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": int(time.time()) + expires_in
    }
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signing_input = f"{h_b64}.{p_b64}"
    sig = hmac.new(settings.secret_key.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{signing_input}.{sig_b64}"

def verify_access_token(token: str) -> dict | None:
    """Verify signed bearer token and return payload if valid."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h_b64, p_b64, sig_b64 = parts
        signing_input = f"{h_b64}.{p_b64}"
        expected_sig = hmac.new(settings.secret_key.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(sig_b64 + "==")
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload_data = base64.urlsafe_b64decode(p_b64 + "==")
        payload = json.loads(payload_data)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
