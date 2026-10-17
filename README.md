# Saathi Voice Banking

A voice-enabled banking demo built with React + FastAPI + MySQL.

> **Live Application**
> - 🌐 Frontend: *(Vercel URL — update after deployment)*
> - ⚡ Backend: *(Render URL — update after deployment)*
> - 📄 API Docs: `<backend-url>/docs`
>
> **Demo Credentials**
> | Username | PIN | Role |
> |----------|-----|------|
> | `customer1` | `1234` | Customer |
> | `customer2` | `2468` | Customer |
> | `agent1` | `agentpass` | Human Agent |

---

## Features

- 🎙️ Voice + typed payment intents in English and Hinglish
- 🧮 Deterministic Hinglish parser (`paanch sau`, `dedh hazaar`, `dhai sau`, `sawa do lakh`)
- 🔒 bcrypt PIN hashing, JWT auth, DB-backed account lockout
- 📒 Atomic double-entry ledger with idempotency
- 🚨 Per-payment and daily limits enforced server-side
- 🤖 Liveness challenge (single-use, 90-second expiry)
- 🛡️ Pluggable spoof-detection adapter
- 👤 Human handoff queue with authenticated agent dashboard
- 🔁 Role-based access (customer vs agent)

---

## Repository

```
https://github.com/Manoj-hubn/Saathi-payment-project
```

---

## Quick Start (Local)

### Prerequisites

- Python 3.11 or 3.12
- Node.js 18+
- MySQL 8.x (or SQLite for quick testing)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, etc.

# Run
uvicorn app.main:app --reload --port 8000
```

The backend auto-seeds demo accounts on first startup when the database is empty.

### Frontend

```bash
cd frontend
npm install

# Configure environment
cp .env.example .env
# Edit .env — set VITE_API_URL=http://localhost:8000 for local dev

npm run dev
# Open http://localhost:5173
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./voice_banking.db` | Database connection string. **Set to cloud MySQL for production.** |
| `SECRET_KEY` | *(dev default)* | JWT signing secret — use a long random string in production |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins (add your Vercel URL) |
| `PAYMENT_THRESHOLD` | `5000` | Amount (paise) above which PIN step-up is required |
| `PER_PAYMENT_LIMIT` | `10000` | Maximum single payment (paise) |
| `DAILY_LIMIT` | `20000` | Maximum 24h total (paise) |
| `CONFIDENCE_THRESHOLD` | `0.78` | Minimum NLP confidence score |
| `SPOOF_PROVIDER` | `disabled` | `disabled` \| `heuristic` \| `remote_http` |
| `SPOOF_API_URL` | *(empty)* | Remote spoof detection endpoint (when `SPOOF_PROVIDER=remote_http`) |
| `SPOOF_API_KEY` | *(empty)* | API key for remote spoof provider |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend URL. Set to Render URL for production. |

---

## Running Tests

```bash
cd backend
# Activate venv first (see above)
python -m pytest tests/ -v
```

**Expected result: 24 passed**

| Test file | Tests | Coverage |
|-----------|-------|---------|
| `test_integration.py` | 11 | Auth, payments, limits, handoff, RBAC, spoof |
| `test_parser.py` | 8 | Hinglish parsing, payee extraction, injection resistance |
| `test_security.py` | 5 | JWT, PIN, liveness challenge, digit normalization |

---

## Deployment

### Backend → Render

1. Connect your GitHub repo in Render dashboard.
2. Set **Root Directory** to `backend`.
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables in Render dashboard:
   - `DATABASE_URL` → your Railway/PlanetScale MySQL connection string
   - `SECRET_KEY` → generate a secure random string
   - `CORS_ORIGINS` → `https://<your-project>.vercel.app`
6. Deploy.

> **Cloud MySQL (Railway):**
> 1. Create account at https://railway.app
> 2. New Project → Add MySQL
> 3. Copy the `DATABASE_URL` from the MySQL service variables

### Frontend → Vercel

1. Connect your GitHub repo in Vercel dashboard.
2. Set **Root Directory** to `frontend`.
3. Add environment variable:
   - `VITE_API_URL` → `https://<your-render-service>.onrender.com`
4. Deploy.

> Vercel automatically uses `vercel.json` for SPA routing rewrites.

### Reset Demo Data

```
POST <backend-url>/api/reset-demo
```

Clears all payments, ledger entries, and handoff cases; restores demo account balances. Does not require authentication. Safe to run against an existing production database — it only clears demo records.

---

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | — | Health check |
| `GET` | `/api/demo-users` | — | List seeded demo usernames |
| `POST` | `/api/login` | — | Authenticate, receive JWT |
| `GET` | `/api/accounts/{user_id}` | Bearer | User accounts + balances |
| `GET` | `/api/payees/{user_id}` | Bearer | User payee list |
| `GET` | `/api/payments/{user_id}` | Bearer | Transaction history |
| `POST` | `/api/turn` | Bearer | Process voice/text intent |
| `POST` | `/api/confirm` | Bearer | Confirm pending transaction |
| `POST` | `/api/liveness` | Bearer | Submit liveness challenge response |
| `POST` | `/api/pin` | Bearer | PIN step-up verification |
| `GET` | `/api/agent/cases` | Bearer (agent) | All handoff cases |
| `GET` | `/api/cases/{user_id}` | Bearer | Handoff cases for user |
| `POST` | `/api/agent/decide/{case_id}` | Bearer (agent) | Approve / reject case |
| `POST` | `/api/agent/unlock-user/{user_id}` | Bearer (agent) | Unlock locked account |
| `GET` | `/api/system/config` | Bearer | Get system limits |
| `POST` | `/api/system/config` | Bearer | Update system limits |
| `POST` | `/api/reset-demo` | — | Reset all demo data |

Full interactive docs: `<backend-url>/docs`

---

## Known Limitations

- Render free tier: ~30s cold start after 15 minutes of inactivity.
- Browser STT (Chrome) sends audio to Google servers — PIN is never spoken.
- Spoof detection disabled by default; liveness routes to human handoff (fail-closed).
- JWT tokens have no server-side revocation mechanism.
- No real payment rails — all transfers are simulated.

---

## Submission

See [`submission/`](./submission/) for:
- [`design-note.md`](./submission/design-note.md) — Architecture and data flow
- [`threat-model.md`](./submission/threat-model.md) — Security threat analysis
- [`demo-and-evaluation.md`](./submission/demo-and-evaluation.md) — Demo script and test results
- [`project-writeup.md`](./submission/project-writeup.md) — What was built, cut, and next steps
