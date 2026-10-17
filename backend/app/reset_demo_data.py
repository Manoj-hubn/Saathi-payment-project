from sqlalchemy import text
from app.database import Base, engine, SessionLocal
from app.models import LedgerEntry, Payment, HandoffCase, AuditEvent, Payee, Account, User, SystemConfig
from app.seed import seed

def reset():
    """Reset all tables and cleanly re-seed initial demo state."""
    db = SessionLocal()
    try:
        # Disable foreign key checks for clean truncation across engines
        if engine.dialect.name == "mysql":
            db.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        elif engine.dialect.name == "sqlite":
            db.execute(text("PRAGMA foreign_keys = OFF;"))

        for model in [LedgerEntry, Payment, HandoffCase, AuditEvent, Payee, Account, User, SystemConfig]:
            db.query(model).delete()

        if engine.dialect.name == "mysql":
            db.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        elif engine.dialect.name == "sqlite":
            db.execute(text("PRAGMA foreign_keys = ON;"))

        db.commit()
    finally:
        db.close()

    seed()

if __name__ == "__main__":
    reset()
