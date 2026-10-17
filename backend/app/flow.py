import difflib
import uuid
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import User, Account, Payee, Payment, LedgerEntry, HandoffCase, AuditEvent, SystemConfig
from app.parser import parse_turn, parse_amount
from app.security import create_challenge, verify_challenge, verify_pin_for_user
from app.config import settings
from app.spoof import detector

sessions = {}

def get_system_config(db: Session, key: str, default: int | float | str):
    """Retrieve system configuration threshold from SQL database with fallback to settings."""
    row = db.get(SystemConfig, key)
    if row and row.value:
        try:
            if isinstance(default, int):
                return int(row.value)
            if isinstance(default, float):
                return float(row.value)
            return row.value
        except Exception:
            pass
    return default

def audit(db: Session, user_id: int | None, event: str, details: str):
    db.add(AuditEvent(user_id=user_id, event_type=event, details=details[:1500]))

def handoff(db: Session, user_id: int, transcript: str, amount: int | None, payee: str | None, field: str, reason: str):
    case = HandoffCase(
        user_id=user_id,
        transcript=transcript,
        extracted_amount_paise=amount,
        extracted_payee=payee,
        uncertain_field=field,
        reason=reason,
        status="OPEN"
    )
    db.add(case)
    audit(db, user_id, "HANDOFF_CREATED", f"field={field};reason={reason}")
    db.commit()
    return {
        "action": "handoff",
        "message": "I’m not confident enough to continue safely. A human agent will review this.",
        "case_id": case.id,
        "reason": reason,
        "uncertain_field": field
    }

def payee_match_score(spoken: str, payee_name: str) -> float:
    s = spoken.lower().strip()
    p = payee_name.lower().strip()
    if s == p:
        return 1.0
    tokens = p.split()
    if s in tokens:
        return 0.95
    if any(tok.startswith(s) for tok in tokens) and len(s) >= 3:
        return 0.88
    return difflib.SequenceMatcher(None, s, p).ratio()

def resolve_payee(db: Session, user_id: int, text: str | None):
    payees = db.scalars(select(Payee).where(Payee.owner_user_id == user_id)).all()
    if not text or not payees:
        return None, "missing"
    ranked = sorted(
        ((payee_match_score(text, p.name), p) for p in payees),
        reverse=True,
        key=lambda x: x[0]
    )
    if not ranked or ranked[0][0] < 0.70:
        return None, "not_found"
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.12 and ranked[0][0] < 0.98:
        return None, "ambiguous"
    return ranked[0][1], "ok"

def turn(db: Session, user_id: int, transcript: str, confidence: float | None, alternate: str | None, session_id: str | None):
    user = db.get(User, user_id)
    if not user or user.role != "customer":
        return {"action": "error", "message": "Customer account not found."}

    if user.is_locked:
        return {"action": "error", "message": "Account is locked due to repeated security failures. Please contact a human agent."}

    parsed = parse_turn(transcript)
    if parsed.action == "handoff":
        return handoff(db, user_id, transcript, None, None, "intent", "Potential prompt injection or unsafe request.")

    conf_threshold = get_system_config(db, "confidence_threshold", settings.confidence_threshold)
    if confidence is not None and confidence < conf_threshold:
        return handoff(db, user_id, transcript, parsed.amount_paise, parsed.payee_text, "transcript", f"Speech confidence ({confidence:.2f}) below configured threshold ({conf_threshold:.2f}).")

    if alternate:
        alt_parsed = parse_turn(alternate)
        if parsed.amount_paise is None or alt_parsed.amount_paise is None or alt_parsed.amount_paise != parsed.amount_paise:
            return handoff(db, user_id, transcript, parsed.amount_paise, parsed.payee_text, "amount", "Primary and alternate transcript amount disagree or could not be parsed deterministically.")
        if parsed.payee_text and alt_parsed.payee_text:
            alt_ratio = difflib.SequenceMatcher(None, parsed.payee_text.lower(), alt_parsed.payee_text.lower()).ratio()
            if alt_ratio < 0.70:
                return handoff(db, user_id, transcript, parsed.amount_paise, parsed.payee_text, "payee", "Primary and alternate transcript payee names disagree.")

    if parsed.action != "payment" or parsed.amount_paise is None:
        return {
            "action": "clarify",
            "message": "Please say or type the amount clearly, for example: Ramesh ko paanch sau rupaye bhej do."
        }

    payee, status = resolve_payee(db, user_id, parsed.payee_text)
    if status != "ok":
        return {
            "action": "clarify",
            "message": "I could not uniquely identify the payee. Please choose a saved contact or talk to a person.",
            "uncertain_field": "payee"
        }

    amount = parsed.amount_paise
    per_payment_limit = get_system_config(db, "per_payment_limit", settings.per_payment_limit)
    if amount <= 0 or amount > per_payment_limit * 100:
        return handoff(db, user_id, transcript, amount, payee.name, "amount", f"Payment amount (₹{amount//100}) exceeds per-payment cap (₹{per_payment_limit}).")

    payment_threshold = get_system_config(db, "payment_threshold", settings.payment_threshold)
    pin_required = (not payee.trusted or amount > payment_threshold * 100)

    sid = session_id or str(uuid.uuid4())
    sessions[sid] = {
        "user_id": user_id,
        "transcript": transcript,
        "amount": amount,
        "payee_id": payee.id,
        "payee_name": payee.name,
        "state": "readback",
        "pin_required": pin_required,
        "liveness": None,
        "pin_ok": False
    }

    audit(db, user_id, "READBACK_PRESENTED", f"amount_paise={amount};payee_id={payee.id}")
    db.commit()

    rupees = amount // 100
    return {
        "action": "readback",
        "session_id": sid,
        "amount_paise": amount,
        "amount_rupees": rupees,
        "amount_words": f"{rupees:,} rupees",
        "payee": payee.name,
        "pin_required": pin_required,
        "message": f"Please confirm {rupees:,} rupees to {payee.name}. Nothing will be sent until you explicitly confirm and complete checks."
    }

def confirm(db: Session, user_id: int, sid: str, confirmed: bool):
    s = sessions.get(sid)
    if not s or s["user_id"] != user_id or s["state"] != "readback":
        return {"action": "error", "message": "This payment session is invalid or expired."}

    if not confirmed:
        s["state"] = "cancelled"
        audit(db, user_id, "PAYMENT_CANCELLED", "Customer explicitly cancelled before execution.")
        db.commit()
        return {"action": "cancelled", "message": "Payment cancelled. No money moved."}

    s["state"] = "liveness"
    challenge = create_challenge(user_id)
    s["challenge_token"] = challenge["token"]
    return {
        "action": "liveness",
        "session_id": sid,
        **challenge,
        "message": f"For safety, repeat the three digits shown: {challenge['phrase']}. This single-use challenge expires in 90 seconds."
    }

def liveness(db: Session, user_id: int, sid: str, token: str, spoken: str):
    s = sessions.get(sid)
    if not s or s["user_id"] != user_id or s["state"] != "liveness":
        return {"action": "error", "message": "Invalid or expired payment session."}

    if token != s.get("challenge_token") or not verify_challenge(user_id, token, spoken):
        return handoff(db, user_id, s["transcript"], s["amount"], s["payee_name"], "liveness", "Challenge failed, expired, or reused.")

    spoof = detector.check(None)
    s["spoof_status"] = spoof.status
    # Fail closed: detector unavailable or inconclusive is never treated as a pass
    if spoof.status != "allow":
        s["pin_required"] = True

    if s["pin_required"]:
        s["state"] = "step_up"
        return {
            "action": "pin",
            "session_id": sid,
            "message": "Additional verification is required. Enter your demo PIN.",
            "spoof_status": spoof.status,
            "spoof_explanation": spoof.explanation
        }

    s["state"] = "ready"
    return execute(db, user_id, sid)

def pin_check(db: Session, user_id: int, sid: str, pin: str):
    s = sessions.get(sid)
    user = db.get(User, user_id)
    if not s or s["user_id"] != user_id or s["state"] != "step_up":
        return {"action": "error", "message": "No PIN verification is pending for this session."}

    ok, reason = verify_pin_for_user(user, pin, db)
    if not ok:
        if reason == "locked":
            audit(db, user_id, "USER_LOCKED", "PIN locked after repeated failures.")
            return handoff(db, user_id, s["transcript"], s["amount"], s["payee_name"], "pin", "PIN locked after 5 failed attempts.")
        audit(db, user_id, "PIN_FAILURE", f"Invalid PIN attempt ({getattr(user, 'failed_attempts', 0)}/5)")
        return {
            "action": "pin",
            "session_id": sid,
            "message": f"PIN incorrect ({getattr(user, 'failed_attempts', 0)}/5 attempts). Repeated failures trigger lockout."
        }

    s["pin_ok"] = True
    s["state"] = "ready"
    return execute(db, user_id, sid)

def execute(db: Session, user_id: int, sid: str):
    s = sessions.get(sid)
    if not s or s["user_id"] != user_id:
        return {"action": "error", "message": "Session not found."}

    if s.get("state") == "complete":
        return {"action": "error", "message": "This payment session has already been executed."}

    if s["state"] not in ("ready",):
        return {"action": "error", "message": "Payment has not passed required verification checks."}

    account = db.scalar(select(Account).where(Account.user_id == user_id))
    payee = db.get(Payee, s["payee_id"])
    if not account or not payee:
        return handoff(db, user_id, s["transcript"], s["amount"], s["payee_name"], "account", "Customer account or payee record unavailable.")

    # Reset daily limit counter if new day
    today = date.today().isoformat()
    if account.daily_spent_date != today:
        account.daily_spent_paise = 0
        account.daily_spent_date = today

    daily_limit = get_system_config(db, "daily_limit", settings.daily_limit)
    if account.daily_spent_paise + s["amount"] > daily_limit * 100:
        return handoff(db, user_id, s["transcript"], s["amount"], payee.name, "limit", f"Daily payment limit (₹{daily_limit}) would be exceeded.")

    if s["amount"] > account.balance_paise:
        return {"action": "failure", "message": "Insufficient demo balance. No payment made."}

    # Locate or create distinct destination account for the payee
    dest_account = db.scalar(select(Account).where(Account.account_number == payee.account_number))
    if not dest_account:
        dest_account = Account(
            user_id=None,
            account_number=payee.account_number,
            balance_paise=500000,
            account_type="payee"
        )
        db.add(dest_account)
        db.flush()

    try:
        # Atomic double-entry execution
        account.balance_paise -= s["amount"]
        account.daily_spent_paise += s["amount"]
        dest_account.balance_paise += s["amount"]

        reference = "DEMO-" + uuid.uuid4().hex[:12].upper()
        payment = Payment(
            user_id=user_id,
            payee_id=payee.id,
            amount_paise=s["amount"],
            reference=reference,
            idempotency_key=sid,
            status="SUCCESS"
        )
        db.add(payment)
        db.flush()

        # Balanced double-entry ledger entries
        debit_entry = LedgerEntry(
            payment_id=payment.id,
            account_id=account.id,
            entry_type="DEBIT",
            amount_paise=s["amount"],
            balance_after_paise=account.balance_paise
        )
        credit_entry = LedgerEntry(
            payment_id=payment.id,
            account_id=dest_account.id,
            entry_type="CREDIT",
            amount_paise=s["amount"],
            balance_after_paise=dest_account.balance_paise
        )
        db.add(debit_entry)
        db.add(credit_entry)

        audit(db, user_id, "PAYMENT_EXECUTED", f"ref={reference};amount_paise={s['amount']};payee={payee.name};debit_acct={account.account_number};credit_acct={dest_account.account_number}")
        db.commit()

        s["state"] = "complete"
        return {
            "action": "receipt",
            "message": "Demo payment successful. This is synthetic data; no real money moved.",
            "reference": reference,
            "amount_paise": s["amount"],
            "amount_rupees": s["amount"] // 100,
            "payee": payee.name,
            "balance_paise": account.balance_paise,
            "balance_rupees": account.balance_paise // 100
        }
    except Exception as e:
        db.rollback()
        return {"action": "error", "message": f"Ledger execution error: {str(e)}"}
