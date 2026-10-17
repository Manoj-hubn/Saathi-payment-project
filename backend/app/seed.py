from sqlalchemy import inspect, text
from app.database import Base, engine, SessionLocal
from app.models import User, Account, Payee, SystemConfig
from app.security import make_pin_hash

def ensure_columns():
    """Ensure database schema is up to date with any newly added model columns."""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        insp = inspect(engine)
        if "users" in insp.get_table_names():
            user_cols = [c["name"] for c in insp.get_columns("users")]
            if "failed_attempts" not in user_cols:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN failed_attempts INT DEFAULT 0"))
                    conn.commit()
                except Exception:
                    pass
            if "is_locked" not in user_cols:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_locked BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                except Exception:
                    pass
        if "accounts" in insp.get_table_names():
            try:
                conn.execute(text("ALTER TABLE accounts MODIFY COLUMN user_id INT NULL"))
                conn.commit()
            except Exception:
                pass
            acct_cols = [c["name"] for c in insp.get_columns("accounts")]
            if "account_type" not in acct_cols:
                try:
                    conn.execute(text("ALTER TABLE accounts ADD COLUMN account_type VARCHAR(20) DEFAULT 'customer'"))
                    conn.commit()
                except Exception:
                    pass
        if "payments" in insp.get_table_names():
            pay_cols = [c["name"] for c in insp.get_columns("payments")]
            if "idempotency_key" not in pay_cols:
                try:
                    conn.execute(text("ALTER TABLE payments ADD COLUMN idempotency_key VARCHAR(64) NULL"))
                    conn.commit()
                except Exception:
                    pass
        if "ledger_entries" in insp.get_table_names():
            ledger_cols = [c["name"] for c in insp.get_columns("ledger_entries")]
            if "balance_after_paise" not in ledger_cols:
                try:
                    conn.execute(text("ALTER TABLE ledger_entries ADD COLUMN balance_after_paise INT NULL"))
                    conn.commit()
                except Exception:
                    pass

def seed():
    ensure_columns()
    db = SessionLocal()
    try:
        # 1. System Configuration thresholds (Database-backed limits)
        configs = [
            ("payment_threshold", "5000", "Amount in Rupees above which PIN is required"),
            ("per_payment_limit", "10000", "Maximum single transaction limit in Rupees"),
            ("daily_limit", "20000", "Maximum daily spending limit in Rupees"),
            ("confidence_threshold", "0.78", "Minimum speech recognition confidence ratio")
        ]
        for key, val, desc in configs:
            cfg = db.get(SystemConfig, key)
            if not cfg:
                db.add(SystemConfig(key=key, value=val, description=desc))
            else:
                cfg.description = desc

        # 2. Users (customers and agent)
        users = {}
        user_data = [
            ("customer1", "Aarav Sharma", "customer", "1234"),
            ("customer2", "Meera Iyer", "customer", "2468"),
            ("agent1", "Demo Human Agent", "agent", "agentpass")
        ]
        for username, name, role, pin in user_data:
            u = db.query(User).filter_by(username=username).first()
            expected_hash = make_pin_hash(pin)
            if not u:
                u = User(
                    username=username,
                    display_name=name,
                    role=role,
                    pin_hash=expected_hash,
                    failed_attempts=0,
                    is_locked=False
                )
                db.add(u)
                db.flush()
            else:
                u.display_name = name
                u.role = role
                u.pin_hash = expected_hash
                u.failed_attempts = 0
                u.is_locked = False
            users[username] = u

        db.flush()

        # 3. Customer Accounts
        account_data = [
            ("customer1", "DEMO-100001", 2500000),  # ₹25,000
            ("customer2", "DEMO-100002", 1800000)   # ₹18,000
        ]
        for uname, acct_num, balance in account_data:
            acct = db.query(Account).filter_by(account_number=acct_num).first()
            if not acct:
                db.add(Account(
                    user_id=users[uname].id,
                    account_number=acct_num,
                    balance_paise=balance,
                    account_type="customer"
                ))
            else:
                acct.user_id = users[uname].id
                acct.account_type = "customer"

        # 4. Payees and destination ledger accounts
        contacts = [
            ("customer1", "Ramesh Kumar", "DEMO-PAYEE-001", True, 500000),
            ("customer1", "Priya Nair", "DEMO-PAYEE-002", True, 750000),
            ("customer1", "New Contact", "DEMO-PAYEE-003", False, 100000),
            ("customer2", "Ramesh Kumar", "DEMO-PAYEE-004", True, 300000)
        ]
        for uname, name, acct_num, trusted, dest_bal in contacts:
            p = db.query(Payee).filter_by(owner_user_id=users[uname].id, name=name).first()
            if not p:
                p = Payee(
                    owner_user_id=users[uname].id,
                    name=name,
                    account_number=acct_num,
                    trusted=trusted
                )
                db.add(p)
            else:
                p.account_number = acct_num
                p.trusted = trusted

            # Destination Account for double-entry mock ledger
            dest_acct = db.query(Account).filter_by(account_number=acct_num).first()
            if not dest_acct:
                db.add(Account(
                    user_id=None,
                    account_number=acct_num,
                    balance_paise=dest_bal,
                    account_type="payee"
                ))

        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
