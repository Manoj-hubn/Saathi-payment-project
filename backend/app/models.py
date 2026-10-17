from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="customer")
    pin_hash: Mapped[str] = mapped_column(String(255), default="")
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    accounts = relationship("Account", back_populates="user")
    payees = relationship("Payee", back_populates="owner")

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    account_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    balance_paise: Mapped[int] = mapped_column(Integer, default=1000000)
    daily_spent_paise: Mapped[int] = mapped_column(Integer, default=0)
    daily_spent_date: Mapped[str] = mapped_column(String(10), default="")
    account_type: Mapped[str] = mapped_column(String(20), default="customer")

    user = relationship("User", back_populates="accounts")

class Payee(Base):
    __tablename__ = "payees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    account_number: Mapped[str] = mapped_column(String(24))
    trusted: Mapped[bool] = mapped_column(Boolean, default=True)

    owner = relationship("User", back_populates="payees")

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    payee_id: Mapped[int] = mapped_column(ForeignKey("payees.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="SUCCESS")
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    payee = relationship("Payee")
    user = relationship("User")

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    entry_type: Mapped[str] = mapped_column(String(10)) # DEBIT or CREDIT
    amount_paise: Mapped[int] = mapped_column(Integer)
    balance_after_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account")
    payment = relationship("Payment")

class HandoffCase(Base):
    __tablename__ = "handoff_cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    transcript: Mapped[str] = mapped_column(Text)
    extracted_amount_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_payee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    uncertain_field: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="OPEN") # OPEN, REVIEWED, REJECTED, REPEAT_REQUESTED
    agent_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[str] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SystemConfig(Base):
    __tablename__ = "system_configs"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(255), default="")
