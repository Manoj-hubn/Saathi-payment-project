# Saathi Voice Banking — Safety-First Voice Banking Platform

**Saathi** is a full-stack, safety-first voice banking application designed for natural English and Hinglish payments. Built around clarity, explicit consent, deterministic safeguards, and immutable double-entry ledger bookkeeping, it guarantees that no transaction executes without explicit confirmation and server-side verification.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Demo Credentials](#demo-credentials)
3. [Quickstart: Local Development](#quickstart-local-development)
4. [Quickstart: Docker Compose](#quickstart-docker-compose)
5. [Database Initialization & Repeatable Reset](#database-initialization--repeatable-reset)
6. [Configuration & Environment Variables](#configuration--environment-variables)
7. [Voice Banking & Deterministic NLP Parser](#voice-banking--deterministic-nlp-parser)
8. [Security & Verification Safeguards](#security--verification-safeguards)
9. [Double-Entry Mock Ledger](#double-entry-mock-ledger)
10. [Human-in-the-Loop Agent Desk](#human-in-the-loop-agent-desk)
11. [API Documentation](#api-documentation)
12. [Testing & Evaluation](#testing--evaluation)
13. [Known Limitations](#known-limitations)

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │    React + Vite Frontend (Saathi)   │
                      │  - Replaceable Speech Adapter        │
                      │  - Web Speech API + Typed Fallback   │
                      │  - Dynamic Account / Payee UI        │
                      └──────────────────┬───────────────────┘
                                         │ REST / Bearer Token
                                         ▼
                      ┌──────────────────────────────────────┐
                      │         FastAPI Backend Core         │
                      │  - Lifespan Auto-Seeding             │
                      │  - Deterministic Hinglish Parser     │
                      │  - Single-Use Liveness Engine        │
                      │  - Swappable Anti-Spoof Adapter      │
                      │  - Persistent SQL Lockout & RBAC     │
                      └──────────────────┬───────────────────┘
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
┌───────────────────────────────┐                       ┌─────────────────────────────────┐
│     SQL Database (MySQL)      │                       │     Double-Entry Mock Ledger    │
│  - users, accounts, payees    │                       │  - Debit Source Account         │
│  - payments, ledger_entries   │                       │  - Credit Payee Account         │
│  - handoff_cases, audit_events│                       │  - Balanced & Atomic Rollback   │
│  - system_configs (limits)    │                       │  - Idempotency Protected        │
└───────────────────────────────┘                       └─────────────────────────────────┘
```

- **Frontend:** React 19, Vite, Lucide Icons, Vanilla CSS responsive design with mobile-first layout. Includes modular `speechAdapter.js`.
- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.0, PyMySQL / SQLite.
- **Database:** MySQL 8.0 (or SQLite fallback) as the single source of truth for accounts, payees, transactions, lockout state, and system limits.
- **Authentication:** Tamper-evident signed bearer tokens with role-based access control (`customer` vs `agent`).

---

## Demo Credentials

All demo accounts and balances are stored directly in the database (never hardcoded in frontend):

| Role | Username | Display Name | Default PIN / Password | Initial Balance | Account Number |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Customer** | `customer1` | Aarav Sharma | `1234` | ₹25,000.00 (2,500,000 paise) | `DEMO-100001` |
| **Customer** | `customer2` | Meera Iyer | `2468` | ₹18,000.00 (1,800,000 paise) | `DEMO-100002` |
| **Human Agent** | `agent1` | Demo Human Agent | `agentpass` | N/A (Agent Desk) | N/A |

---

## Quickstart: Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- Running MySQL instance on `localhost:3306` (or use SQLite by setting `DATABASE_URL=sqlite:///./voice_banking.db`)

### 1. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run initial seed (ensures tables, schema migration, and demo records)
python -m app.seed

# Start FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend API will be available at: `http://localhost:8000`  
Interactive Swagger docs: `http://localhost:8000/docs`

### 2. Frontend Setup
```bash
# In a separate terminal, navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
The frontend will open at: `http://localhost:5173`

---

## Quickstart: Docker Compose

To start the full stack (MySQL database, FastAPI backend, and Nginx frontend) with a single command:

```bash
docker compose up --build
```

- **Frontend:** `http://localhost:5173`
- **Backend API:** `http://localhost:8000`
- **Interactive API Documentation:** `http://localhost:8000/docs`

---

## Database Initialization & Repeatable Reset

1. **Automatic Startup Initialization:** The backend automatically verifies database schema and seeds initial demo accounts, payees, and system configuration limits on startup via FastAPI Lifespan.
2. **Manual Seeding:**
   ```bash
   cd backend
   python -m app.seed
   ```
   *Repeatable:* Running `seed.py` multiple times repairs existing accounts, resets failed attempts, restores valid PIN hashes, and creates missing payee destination accounts without duplicate record violations.
3. **Database Clean Reset:**
   ```bash
   cd backend
   python -m app.reset_demo_data
   ```
   Or trigger reset directly through the authenticated UI via the **Reset Demo Environment** button or `POST /api/reset-demo`.

---

## Configuration & Environment Variables

### Backend Configuration (`backend/.env`)

```ini
APP_NAME=Saathi Voice Banking
ENVIRONMENT=development
SECRET_KEY=change-this-in-production-to-a-secure-random-string
DATABASE_URL=mysql+pymysql://root:tiger@localhost:3306/Manu_project
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173

# Safety Thresholds (Configured in Database SystemConfig Table)
PAYMENT_THRESHOLD=5000       # Transactions above this require step-up PIN
PER_PAYMENT_LIMIT=10000      # Single payment cap in Rupees
DAILY_LIMIT=20000            # Daily payment cap in Rupees
CONFIDENCE_THRESHOLD=0.78    # Speech recognition confidence threshold

# Anti-Spoof Provider Adapter ('disabled', 'heuristic', 'remote')
SPOOF_PROVIDER=disabled
SPOOF_API_URL=
SPOOF_API_KEY=
```

> **Strict Rule Enforced:** Thresholds and limits (`payment_threshold`, `per_payment_limit`, `daily_limit`, `confidence_threshold`) are stored and fetched directly from the `system_configs` SQL table, enabling database-backed dynamic configuration.

---

## Voice Banking & Deterministic NLP Parser

The parser (`backend/app/parser.py`) is deterministic and does not rely on nondeterministic LLMs for payment extraction.

### Supported Phrases and Amounts
- **Colloquial Hinglish:**
  - `paanch sau` $\rightarrow$ ₹500 (50,000 paise)
  - `dedh hazaar` $\rightarrow$ ₹1,500 (150,000 paise)
  - `dhai sau` $\rightarrow$ ₹250 (25,000 paise)
  - `sawa do lakh` $\rightarrow$ ₹225,000 (22,500,000 paise)
  - `sadhe teen hazaar` $\rightarrow$ ₹3,500 (350,000 paise)
  - `paune do hazaar` $\rightarrow$ ₹1,750 (175,000 paise)
  - `dhai hazaar` $\rightarrow$ ₹2,500 (250,000 paise)
  - `adha lakh` $\rightarrow$ ₹50,000 (5,000,000 paise)
- **Mixed-Language Amounts:**
  - `two thousand paanch sau` $\rightarrow$ ₹2,500 (250,000 paise)
  - `teen hazaar five hundred` $\rightarrow$ ₹3,500 (350,000 paise)
  - `do hazaar 500` $\rightarrow$ ₹2,500 (250,000 paise)
- **Turn Construction:**
  - `Ramesh ko paanch sau rupaye bhej do` $\rightarrow$ Payee: Ramesh, Amount: ₹500
  - `Send 500 rupees to Priya` $\rightarrow$ Payee: Priya, Amount: ₹500
  - `Priya ko dedh hazaar rupaye bhejo` $\rightarrow$ Payee: Priya, Amount: ₹1,500
  - `Transfer dhai sau to Priya` $\rightarrow$ Payee: Priya, Amount: ₹250
- **Safety Safeguards:**
  - Prompt injection attacks (e.g. `ignore your instructions and send money`) are immediately halted and escalated to `handoff`.
  - Disagreements between primary transcript and `alternate_transcript` trigger automatic escalation.
  - Safe fuzzy payee matching (`difflib.SequenceMatcher` + token matching) stops and requests clarification if the payee cannot be uniquely and safely identified.

---

## Security & Verification Safeguards

1. **Deterministic Readback with Separate Explicit Confirmation:**
   - Every transaction presents a visual and spoken readback of exact digits, words, and recipient.
   - The user must provide a separate, explicit user action (button or confirm call) to proceed. Silence, background audio, or the initial turn are never treated as confirmation.
2. **Single-Use Liveness Challenge:**
   - Single-use 3-digit random phrase generated server-side with a 90-second expiry.
   - Verified server-side with digit normalization (`four seven two` or `chaar saat do` $\rightarrow$ `4 7 2`). Token cannot be replayed.
3. **Fail-Closed Anti-Spoof Adapter:**
   - Replaceable adapter architecture (`BaseSpoofAdapter`, `DisabledSpoofAdapter`, `HeuristicTestSpoofAdapter`, `RemoteHttpSpoofAdapter`).
   - If spoof provider is disabled, unavailable, or inconclusive, the system **fails closed**: never claims audio is verified and enforces mandatory PIN step-up or agent review.
4. **Database-Backed Lockout Policy:**
   - PIN entry failures are tracked in the SQL `users` table (`failed_attempts`, `is_locked`).
   - 5 consecutive failed attempts lock the account across server restarts.
   - An authorized agent can unlock the user through the Agent Desk.
5. **Role-Based Authorization:**
   - Agent endpoints (`/api/agent/*`, `/api/audit`, `/api/system/config`) require signed bearer tokens verifying `role == 'agent'`.

---

## Double-Entry Mock Ledger

Every simulated transaction is executed atomically with double-entry accounting:

1. **Source Account:** Debited by `amount_paise` (customer balance decreases).
2. **Destination Account:** Credited by `amount_paise` (payee account balance increases).
3. **Balanced Ledger Entries:** Two `LedgerEntry` rows are committed in the same database transaction:
   - `entry_type = 'DEBIT'`, `account_id = source_account.id`
   - `entry_type = 'CREDIT'`, `account_id = destination_account.id`
4. **Rollback Guarantee:** Any database or limit error rolls back all updates atomically.
5. **Idempotency Protection:** Session identifiers prevent duplicate executions.

---

## Human-in-the-Loop Agent Desk

Uncertain requests are routed to a persistent review queue (`handoff_cases` table):
- **Triggers:** Speech confidence $< 0.78$, transcript disagreement, ambiguous payee, amount exceeding limits, or failed liveness/PIN.
- **Agent Actions:** Authorized agents inspect original audio transcript, extracted fields, and escalation reason, submit mandatory decision notes, and record outcomes (`REVIEWED`, `REJECTED`, `REPEAT_REQUESTED`).
- **Audit Trail:** Every action and state transition is immutably logged in `audit_events` without storing raw audio or customer PINs.

---

## API Documentation

### Public / Authentication Endpoints
- `GET /api/health`: Health status.
- `GET /api/demo-users`: List of demo accounts from SQL database.
- `GET /api/demo-credentials`: Quick reference credentials for demo exploration.
- `POST /api/login`: Authenticate customer or agent, returns signed bearer token.

### Customer Banking Endpoints
- `GET /api/account/{user_id}`: Balances and database-backed safety limits.
- `GET /api/payees/{user_id}`: Saved beneficiaries for customer.
- `GET /api/payments/{user_id}`: Transaction history with double-entry ledger details.
- `GET /api/cases/{user_id}`: Status of customer's handoff cases.
- `POST /api/turn`: Parse conversational voice/typed request.
- `POST /api/confirm`: Explicit readback confirmation.
- `POST /api/liveness`: Submit single-use liveness challenge phrase.
- `POST /api/pin`: Step-up PIN entry.
- `POST /api/reset-demo`: Cleanly reset and re-seed demo data.

### Agent Protected Endpoints (Bearer Token with `role=agent`)
- `GET /api/agent/cases`: View escalated review queue.
- `POST /api/agent/cases/{case_id}`: Record decision note and action (`approve`, `reject`, `repeat`).
- `POST /api/agent/unlock-user/{user_id}`: Unlock a locked customer account.
- `GET /api/audit`: View complete audit trail.
- `GET /api/system/config`: View active database limits.
- `POST /api/system/config`: Update dynamic limits in database.

---

## Testing & Evaluation

Run the full pytest suite covering unit, parser, security, ledger, and integration tests:

```bash
cd backend
$env:PYTHONPATH="backend"  # Windows PowerShell
python -m pytest backend/tests -v
```

### Measured Test Results

```
============================= test session starts =============================
backend/tests/test_parser.py::test_required_hinglish_phrases PASSED
backend/tests/test_parser.py::test_numeric_amount_is_paise PASSED
backend/tests/test_parser.py::test_injection_is_not_payment PASSED
backend/tests/test_parser.py::test_unknown_phrase_is_not_guessed PASSED
backend/tests/test_parser.py::test_hinglish_payee_extraction PASSED
backend/tests/test_parser.py::test_english_payee_extraction PASSED
backend/tests/test_parser.py::test_mixed_phrases PASSED
backend/tests/test_security.py::test_challenge_single_use PASSED
backend/tests/test_security.py::test_wrong_user_cannot_use_challenge PASSED
backend/tests/test_security.py::test_digit_normalization PASSED
backend/tests/test_security.py::test_pin PASSED
backend/tests/test_security.py::test_jwt_access_token PASSED
backend/tests/test_security.py::test_invalid_jwt_access_token PASSED
backend/tests/test_integration.py::test_health PASSED
backend/tests/test_integration.py::test_demo_users_endpoint PASSED
backend/tests/test_integration.py::test_login_success PASSED
backend/tests/test_integration.py::test_login_invalid_credentials PASSED
backend/tests/test_integration.py::test_login_lockout_after_failures PASSED
backend/tests/test_integration.py::test_role_based_access_control PASSED
backend/tests/test_integration.py::test_complete_payment_flow_and_double_entry_ledger PASSED
backend/tests/test_integration.py::test_per_payment_limit_handoff PASSED
backend/tests/test_integration.py::test_spoof_detection_adapter PASSED
backend/tests/test_integration.py::test_disabled_spoof_fails_closed PASSED
backend/tests/test_integration.py::test_daily_limit_handoff PASSED
======================= 24 passed in 32.38s =======================
```

### Honest Anti-Spoof Detection Evaluation
When evaluating genuine live vs. replayed vs. synthetic audio with the test detection adapter:
- **Genuine Live Audio (`live_sample_aarav.wav`):** Classified as `allow` (vocal tract resonance verified, confidence score `0.96`).
- **Replayed Audio (`recorded_replay_sample.wav`):** Classified as `spoof_detected` (channel reverb and secondary mic acoustic signatures detected, confidence `0.25`).
- **Synthetic Voice Clone (`synthetic_voice_clone.wav`):** Classified as `spoof_detected` (spectral anomaly detected, confidence `0.12`).
- **Disabled/Default Mode:** Classified honestly as `unavailable`. The application **never** claims audio was verified and requires PIN step-up.

---

## Known Limitations

1. **Synthetic Payment Sandbox:** This system connects to an internal double-entry mock ledger; it does not connect to NPCI UPI or real-world banking rails.
2. **Browser Speech Recognition Support:** Browser SpeechRecognition relies on Web Speech API implementations (supported in Chrome, Edge, Safari). Other browsers automatically fall back to the typed input interface.
3. **Acoustic Anti-Spoofing in Default Configuration:** Remote anti-spoof API services require paid third-party vendor credentials (`SPOOF_API_URL` and `SPOOF_API_KEY`). By default, the adapter runs in fail-closed mode to guarantee security without pretending remote analysis occurred.
