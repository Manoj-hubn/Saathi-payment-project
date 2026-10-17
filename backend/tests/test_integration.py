import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.database import get_db, SessionLocal
from app.models import User, Account, Payee, Payment, LedgerEntry, HandoffCase, AuditEvent
from app.seed import seed
from app.spoof import detector, HeuristicTestSpoofAdapter

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    seed()

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_demo_users_endpoint():
    res = client.get("/api/demo-users")
    assert res.status_code == 200
    users = res.json()
    usernames = [u["username"] for u in users]
    assert "customer1" in usernames
    assert "customer2" in usernames
    assert "agent1" in usernames

def test_login_success():
    res = client.post("/api/login", json={"username": "customer1", "pin": "1234"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "customer1"
    assert data["role"] == "customer"
    assert "token" in data

    agent_res = client.post("/api/login", json={"username": "agent1", "pin": "agentpass"})
    assert agent_res.status_code == 200
    assert agent_res.json()["role"] == "agent"

def test_login_invalid_credentials():
    res = client.post("/api/login", json={"username": "customer1", "pin": "0000"})
    assert res.status_code == 401
    assert "Invalid credentials" in res.json()["detail"]

def test_login_lockout_after_failures():
    # 5 failed attempts trigger lockout
    for _ in range(5):
        client.post("/api/login", json={"username": "customer2", "pin": "0000"})
    
    # 6th attempt should return 403 Forbidden
    res = client.post("/api/login", json={"username": "customer2", "pin": "2468"})
    assert res.status_code == 403
    assert "locked" in res.json()["detail"].lower()

    # Agent unlocks user
    agent_login = client.post("/api/login", json={"username": "agent1", "pin": "agentpass"}).json()
    token = agent_login["token"]

    db = SessionLocal()
    u2 = db.query(User).filter_by(username="customer2").first()
    u2_id = u2.id
    db.close()

    unlock_res = client.post(f"/api/agent/unlock-user/{u2_id}", headers={"Authorization": f"Bearer {token}"})
    assert unlock_res.status_code == 200

    # Login should now succeed
    res_after = client.post("/api/login", json={"username": "customer2", "pin": "2468"})
    assert res_after.status_code == 200

def test_role_based_access_control():
    cust_token = client.post("/api/login", json={"username": "customer1", "pin": "1234"}).json()["token"]
    agent_token = client.post("/api/login", json={"username": "agent1", "pin": "agentpass"}).json()["token"]

    # Customer accessing agent endpoint should be forbidden (403)
    res_forbidden = client.get("/api/agent/cases", headers={"Authorization": f"Bearer {cust_token}"})
    assert res_forbidden.status_code == 403

    # Customer accessing audit endpoint should be forbidden (403)
    res_audit_forbidden = client.get("/api/audit", headers={"Authorization": f"Bearer {cust_token}"})
    assert res_audit_forbidden.status_code == 403

    # Agent accessing agent endpoint should succeed (200)
    res_agent = client.get("/api/agent/cases", headers={"Authorization": f"Bearer {agent_token}"})
    assert res_agent.status_code == 200

def test_complete_payment_flow_and_double_entry_ledger():
    cust = client.post("/api/login", json={"username": "customer1", "pin": "1234"}).json()
    user_id = cust["user_id"]

    # Check payees
    payees_res = client.get(f"/api/payees/{user_id}")
    assert payees_res.status_code == 200
    payees = payees_res.json()
    assert any(p["name"] == "Ramesh Kumar" for p in payees)

    # Initial balance
    acct_res = client.get(f"/api/account/{user_id}")
    assert acct_res.status_code == 200
    initial_balance = acct_res.json()["balance_paise"]

    # Step 1: Turn
    turn_res = client.post("/api/turn", json={
        "user_id": user_id,
        "transcript": "Ramesh ko paanch sau rupaye bhej do",
        "confidence": 0.95
    })
    assert turn_res.status_code == 200
    turn_data = turn_res.json()
    assert turn_data["action"] == "readback"
    assert turn_data["amount_paise"] == 50000
    assert turn_data["amount_rupees"] == 500
    sid = turn_data["session_id"]

    # Step 2: Explicit Confirmation
    conf_res = client.post("/api/confirm", json={
        "user_id": user_id,
        "session_id": sid,
        "confirmed": True
    })
    assert conf_res.status_code == 200
    conf_data = conf_res.json()
    assert conf_data["action"] == "liveness"
    token = conf_data["token"]
    phrase = conf_data["phrase"]

    # Step 3: Liveness Verification (normalizes digits)
    live_res = client.post("/api/liveness", json={
        "user_id": user_id,
        "session_id": sid,
        "token": token,
        "spoken_phrase": phrase
    })
    assert live_res.status_code == 200
    live_data = live_res.json()
    # Spoof provider is disabled by default -> fails closed to PIN step-up
    assert live_data["action"] == "pin"

    # Step 4: PIN Step-Up Verification
    pin_res = client.post("/api/pin", json={
        "user_id": user_id,
        "session_id": sid,
        "pin": "1234"
    })
    assert pin_res.status_code == 200
    receipt = pin_res.json()
    assert receipt["action"] == "receipt"
    assert receipt["amount_rupees"] == 500
    reference = receipt["reference"]

    # Verify double-entry ledger in database
    db = SessionLocal()
    payment = db.query(Payment).filter_by(reference=reference).first()
    assert payment is not None
    assert payment.amount_paise == 50000

    entries = db.query(LedgerEntry).filter_by(payment_id=payment.id).all()
    assert len(entries) == 2
    debit_entry = next(e for e in entries if e.entry_type == "DEBIT")
    credit_entry = next(e for e in entries if e.entry_type == "CREDIT")

    assert debit_entry.amount_paise == 50000
    assert credit_entry.amount_paise == 50000
    # Source and destination accounts must be distinct
    assert debit_entry.account_id != credit_entry.account_id
    db.close()

    # Step 5: Verify Idempotency - executing same session again must fail
    dup_pin_res = client.post("/api/pin", json={
        "user_id": user_id,
        "session_id": sid,
        "pin": "1234"
    })
    assert dup_pin_res.json()["action"] == "error"

def test_per_payment_limit_handoff():
    cust = client.post("/api/login", json={"username": "customer1", "pin": "1234"}).json()
    user_id = cust["user_id"]

    # ₹15,000 exceeds ₹10,000 per-payment limit -> routes to handoff
    turn_res = client.post("/api/turn", json={
        "user_id": user_id,
        "transcript": "Ramesh ko 15000 rupees bhej do",
        "confidence": 0.95
    })
    assert turn_res.status_code == 200
    data = turn_res.json()
    assert data["action"] == "handoff"
    assert "exceeds per-payment cap" in data["reason"]

def test_spoof_detection_adapter():
    detector.set_adapter(HeuristicTestSpoofAdapter())

    # Live genuine speech
    live_result = detector.check("live_sample_aarav.wav")
    assert live_result.status == "allow"
    assert live_result.score > 0.90

    # Replayed audio
    replay_result = detector.check("recorded_replay_sample.wav")
    assert replay_result.status == "spoof_detected"
    assert "replayed" in replay_result.explanation

    # Synthetic voice clone
    synth_result = detector.check("synthetic_voice_clone.wav")
    assert synth_result.status == "spoof_detected"
    assert "synthetic" in synth_result.explanation

def test_disabled_spoof_fails_closed():
    detector.set_adapter(None)  # reset to default config
    res = detector.check("sample.wav")
    assert res.status == "unavailable"
    assert "fail-closed" in res.explanation.lower() or "no anti-spoof provider" in res.explanation.lower()

def test_daily_limit_handoff():
    cust = client.post("/api/login", json={"username": "customer2", "pin": "2468"}).json()
    user_id = cust["user_id"]

    db = SessionLocal()
    acct = db.query(Account).filter_by(user_id=user_id).first()
    # Simulate already spent ₹18,000 today
    acct.daily_spent_paise = 1800000
    from datetime import date
    acct.daily_spent_date = date.today().isoformat()
    db.commit()
    db.close()

    # Attempting to send ₹5,000 when daily limit is ₹20,000 -> 18000 + 5000 = 23000 > 20000 -> handoff
    # First turn
    turn_res = client.post("/api/turn", json={
        "user_id": user_id,
        "transcript": "Ramesh ko 5000 rupees bhej do",
        "confidence": 0.95
    })
    sid = turn_res.json()["session_id"]
    conf_res = client.post("/api/confirm", json={"user_id": user_id, "session_id": sid, "confirmed": True})
    token = conf_res.json()["token"]
    phrase = conf_res.json()["phrase"]

    # Liveness check -> triggers step_up PIN
    live_res = client.post("/api/liveness", json={
        "user_id": user_id,
        "session_id": sid,
        "token": token,
        "spoken_phrase": phrase
    })
    assert live_res.json()["action"] == "pin"

    # Step-up PIN -> triggers daily limit check during execution -> handoff
    res = client.post("/api/pin", json={"user_id": user_id, "session_id": sid, "pin": "2468"})
    assert res.json()["action"] == "handoff"
    assert "Daily payment limit" in res.json()["reason"]
