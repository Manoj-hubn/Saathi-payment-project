from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import Base, engine, get_db
from app.config import settings
from app import models
from app.schemas import (
    LoginRequest, TurnRequest, ConfirmRequest, LivenessRequest,
    PinRequest, AgentAction, ConfigUpdateRequest
)
from app.flow import turn, confirm, liveness, pin_check, audit, get_system_config
from app.models import User, Account, Payee, HandoffCase, Payment, LedgerEntry, AuditEvent, SystemConfig
from app.security import verify_pin_for_user, create_access_token, verify_access_token
from app.seed import seed, ensure_columns
from app.reset_demo_data import reset as reset_database

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_columns()
    db = next(get_db())
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            seed()
    finally:
        db.close()
    yield

app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Dependency for extracting and verifying bearer token
def get_current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
    token = authorization.replace("Bearer ", "").strip()
    if not token or token in ("null", "undefined"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication token missing or invalid")
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.is_locked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is locked due to security policy")
    return user

def require_agent(user: User = Depends(get_current_user)) -> User:
    if user.role != "agent":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent role authorization required")
    return user

@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "status": "online",
        "health": "/api/health",
        "docs": "/docs",
        "frontend": "https://saathi-payment-project-qulg.vercel.app",
        "message": "Saathi Voice Banking Backend API is running."
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "synthetic-demo"}

@app.get("/api/demo-credentials")
def credentials():
    return {
        "customer": "customer1 / 1234",
        "second_customer": "customer2 / 2468",
        "agent": "agent1 / agentpass",
        "note": "Demo credentials for testing. No real accounts or payment rails."
    }

@app.get("/api/demo-users")
def get_demo_users(db: Session = Depends(get_db)):
    """Dynamic account list fetched directly from SQL database as source of truth."""
    users = db.scalars(select(User).order_by(User.id)).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "is_locked": u.is_locked
        }
        for u in users
    ]

@app.post("/api/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked due to repeated failed attempts. Please contact an agent."
        )

    ok, reason = verify_pin_for_user(user, payload.pin, db)
    if not ok:
        if reason == "locked":
            audit(db, user.id, "LOGIN_LOCKOUT", "Account locked after 5 failed login attempts")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been locked after 5 failed attempts. An agent must unlock it."
            )
        audit(db, user.id, "LOGIN_FAILED", f"Failed login attempt ({user.failed_attempts}/5)")
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid credentials ({user.failed_attempts}/5 attempts). 5 failures triggers lockout."
        )

    token = create_access_token(user.id, user.username, user.role)
    audit(db, user.id, "LOGIN_SUCCESS", f"User {user.username} logged in successfully")
    db.commit()

    return {
        "token": token,
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role
    }

@app.post("/api/turn")
def make_turn(payload: TurnRequest, db: Session = Depends(get_db)):
    return turn(db, payload.user_id, payload.transcript, payload.confidence, payload.alternate_transcript, payload.session_id)

@app.post("/api/confirm")
def make_confirm(payload: ConfirmRequest, db: Session = Depends(get_db)):
    return confirm(db, payload.user_id, payload.session_id, payload.confirmed)

@app.post("/api/liveness")
def make_liveness(payload: LivenessRequest, db: Session = Depends(get_db)):
    return liveness(db, payload.user_id, payload.session_id, payload.token, payload.spoken_phrase)

@app.post("/api/pin")
def make_pin(payload: PinRequest, db: Session = Depends(get_db)):
    return pin_check(db, payload.user_id, payload.session_id, payload.pin)

@app.get("/api/account/{user_id}")
def get_account(user_id: int, db: Session = Depends(get_db)):
    a = db.scalar(select(Account).where(Account.user_id == user_id))
    if not a:
        raise HTTPException(status_code=404, detail="Account not found")

    payment_thresh = get_system_config(db, "payment_threshold", settings.payment_threshold)
    per_limit = get_system_config(db, "per_payment_limit", settings.per_payment_limit)
    day_limit = get_system_config(db, "daily_limit", settings.daily_limit)

    return {
        "balance_paise": a.balance_paise,
        "balance_rupees": a.balance_paise // 100,
        "account_number": a.account_number,
        "daily_spent_paise": a.daily_spent_paise,
        "daily_spent_rupees": a.daily_spent_paise // 100,
        "limits": {
            "payment_threshold_rupees": payment_thresh,
            "per_payment_limit_rupees": per_limit,
            "daily_limit_rupees": day_limit
        }
    }

@app.get("/api/payees/{user_id}")
def get_payees(user_id: int, db: Session = Depends(get_db)):
    """Fetch saved payees for the customer from the SQL database."""
    payees = db.scalars(select(Payee).where(Payee.owner_user_id == user_id).order_by(Payee.id)).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "account_number": p.account_number,
            "trusted": p.trusted
        }
        for p in payees
    ]

@app.get("/api/payments/{user_id}")
def get_payments(user_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(Payment).where(Payment.user_id == user_id).order_by(Payment.id.desc()).limit(20)).all()
    result = []
    for p in rows:
        # Include ledger double-entry breakdown
        entries = db.scalars(select(LedgerEntry).where(LedgerEntry.payment_id == p.id)).all()
        result.append({
            "id": p.id,
            "reference": p.reference,
            "amount_paise": p.amount_paise,
            "amount_rupees": p.amount_paise // 100,
            "payee": p.payee.name if p.payee else "Unknown",
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "ledger_entries": [
                {
                    "id": le.id,
                    "account_id": le.account_id,
                    "entry_type": le.entry_type,
                    "amount_paise": le.amount_paise,
                    "balance_after_paise": le.balance_after_paise
                }
                for le in entries
            ]
        })
    return result

@app.get("/api/cases/{user_id}")
def get_customer_cases(user_id: int, db: Session = Depends(get_db)):
    """Allow customer to view status of their own escalated requests."""
    rows = db.scalars(select(HandoffCase).where(HandoffCase.user_id == user_id).order_by(HandoffCase.id.desc())).all()
    return [
        {
            "id": c.id,
            "transcript": c.transcript,
            "amount_paise": c.extracted_amount_paise,
            "amount_rupees": c.extracted_amount_paise // 100 if c.extracted_amount_paise else None,
            "payee": c.extracted_payee,
            "uncertain_field": c.uncertain_field,
            "reason": c.reason,
            "status": c.status,
            "agent_note": c.agent_note,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in rows
    ]

# ----------------- AGENT PROTECTED ENDPOINTS -----------------

@app.get("/api/agent/cases")
def agent_cases(agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    rows = db.scalars(select(HandoffCase).order_by(HandoffCase.id.desc())).all()
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "transcript": c.transcript,
            "amount_paise": c.extracted_amount_paise,
            "payee": c.extracted_payee,
            "uncertain_field": c.uncertain_field,
            "reason": c.reason,
            "status": c.status,
            "agent_note": c.agent_note,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in rows
    ]

@app.post("/api/agent/cases/{case_id}")
def act_on_case(case_id: int, payload: AgentAction, agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    c = db.get(HandoffCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")

    status_map = {
        "approve": "REVIEWED",
        "reject": "REJECTED",
        "repeat": "REPEAT_REQUESTED"
    }
    c.status = status_map[payload.action]
    c.agent_note = payload.note
    audit(db, agent.id, "AGENT_CASE_ACTION", f"case={case_id};action={payload.action};note={payload.note};agent={agent.username}")
    db.commit()
    return {
        "status": c.status,
        "message": "Case updated. Agent review decision recorded in audit trail. Note: Review does not itself execute money movement."
    }

@app.post("/api/agent/unlock-user/{user_id}")
def unlock_user(user_id: int, agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(404, "User not found")
    target_user.is_locked = False
    target_user.failed_attempts = 0
    audit(db, agent.id, "USER_UNLOCKED", f"Agent {agent.username} unlocked user {target_user.username}")
    db.commit()
    return {"status": "ok", "message": f"User {target_user.username} unlocked successfully."}

@app.get("/api/system/config")
def get_system_configs(agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    configs = db.scalars(select(SystemConfig)).all()
    return [{"key": c.key, "value": c.value, "description": c.description} for c in configs]

@app.post("/api/system/config")
def update_system_config(payload: ConfigUpdateRequest, agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    cfg = db.get(SystemConfig, payload.key)
    if not cfg:
        cfg = SystemConfig(key=payload.key, value=payload.value)
        db.add(cfg)
    else:
        cfg.value = payload.value
    audit(db, agent.id, "CONFIG_UPDATED", f"agent={agent.username};key={payload.key};new_value={payload.value}")
    db.commit()
    return {"status": "ok", "key": cfg.key, "value": cfg.value}

@app.get("/api/audit")
def audit_events(agent: User = Depends(require_agent), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(100)).all()
    return [
        {
            "id": x.id,
            "user_id": x.user_id,
            "event_type": x.event_type,
            "details": x.details,
            "created_at": x.created_at.isoformat() if x.created_at else None
        }
        for x in rows
    ]

@app.post("/api/reset-demo")
def reset_demo(db: Session = Depends(get_db)):
    reset_database()
    return {"status": "ok", "message": "Demo database successfully reset and re-seeded."}
