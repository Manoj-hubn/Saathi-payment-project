# Saathi Voice Banking — Design Note

## Architecture Overview

Saathi is a full-stack voice-enabled banking demo. The system is split into a React frontend (Vercel) and a FastAPI backend (Render) backed by a persistent MySQL database.

```mermaid
flowchart TD
    subgraph Client["Browser (Vercel)"]
        UI["React + Vite UI"]
        SA["speechAdapter.js\nBrowserSpeechProvider"]
        TTS["Web Speech API\n(TTS)"]
    end

    subgraph Backend["FastAPI Backend (Render)"]
        API["FastAPI REST API\napp/main.py"]
        FLOW["Voice Flow Engine\napp/flow.py"]
        PARSER["Hinglish Parser\napp/parser.py"]
        SPOOF["Spoof Adapter\napp/spoof.py"]
        SEC["Security\napp/security.py"]
        SEED["Auto-Seed\napp/seed.py"]
    end

    subgraph DB["Persistent Database"]
        MYSQL[("MySQL\n(Railway / Cloud)")]
    end

    subgraph Queue["Human Review"]
        AGENT["Agent Dashboard\n(role=agent)"]
        CASES["handoff_cases table"]
    end

    UI -->|"REST /api/*"| API
    SA -->|"transcript text"| UI
    UI -->|"TTS"| TTS
    API --> FLOW
    API --> SEC
    FLOW --> PARSER
    FLOW --> SPOOF
    API --> SEED
    API --> MYSQL
    FLOW --> CASES
    AGENT -->|"Bearer token (role=agent)"| API
```

## Components

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + Vite | Customer banking UI + agent dashboard |
| Speech | Web Speech API | STT (browser) + TTS (browser) |
| Backend | FastAPI 0.115 | REST API, business logic, auth |
| ORM | SQLAlchemy 2.0 | DB-agnostic models |
| Database | MySQL (Railway) | Persistent accounts, ledger, audit |
| Auth | JWT HS256 (python-jose) | Bearer tokens, role-based access |
| PIN | bcrypt (passlib) | Hashed PIN storage |
| Parser | Custom NLP | Hinglish/English amount parsing |
| Spoof | Pluggable adapter | Disabled → HeuristicTest → RemoteHttp |

## Primary Demo Data Flow

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant F as Frontend
    participant B as Backend API
    participant DB as MySQL

    U->>F: Speak / type payment intent
    F->>B: POST /api/turn {text, user_id}
    B->>B: Parse intent (parser.py)
    B->>DB: Fetch payees, check limits
    B-->>F: {parsed_amount, payee, ask_confirm}
    F->>U: Speak + display: "Send ₹500 to Priya. Confirm?"
    U->>F: Explicit "Yes" / button click
    F->>B: POST /api/confirm {transaction_id}
    B->>DB: Double-entry ledger (atomic)
    B-->>F: {status: completed, balance}
    F->>U: "Payment sent successfully"
```

## Hosting & Deployment

| Service | Provider | URL |
|---------|---------|-----|
| Frontend | Vercel | *(pending Vercel deployment)* |
| Backend | Render (Free) | https://saathi-payment-project-2.onrender.com *(Verified Live)* |
| Database | TiDB Cloud | Cloud-hosted persistent MySQL (AWS Tokyo) |

> [!NOTE]
> Render free tier services spin down after inactivity. Expect a ~30s cold start on first request after idle.

## Key Design Decisions

- **SQLite fallback**: If `DATABASE_URL` is not set, the backend falls back to `sqlite:///./voice_banking.db` — used only for local dev and tests.
- **Auto-seed**: On startup, if `users` table is empty, seed runs automatically. Safe for production; does not reset existing data.
- **Double-entry ledger**: All transfers atomically create two `ledger_entries` (debit source, credit destination) plus a `payments` record. On failure, the entire transaction rolls back.
- **Idempotency**: Each payment has an `idempotency_key`; duplicate submissions return the existing result.
- **Pluggable spoof detection**: `SPOOF_PROVIDER=disabled` (default) → all liveness checks fail-closed and route to human handoff. Switch to `heuristic` or `remote_http` without code changes.
