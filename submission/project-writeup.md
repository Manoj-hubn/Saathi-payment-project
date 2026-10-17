# Saathi Voice Banking — Project Write-Up

## What Was Built

Saathi is a voice-enabled banking demo that fulfils the Python Full Stack Developer Intern Assignment requirements. It is a realistic simulation — no real money moves and no real bank accounts are connected.

### Core Features Implemented

**Backend (FastAPI + SQLAlchemy + MySQL)**
- Full user authentication with bcrypt PIN hashing and JWT bearer tokens (HS256).
- DB-backed account lockout after 3 failed PIN attempts; agent can unlock.
- Double-entry ledger: every payment creates two balanced `ledger_entries` and one `payments` record. The entire transaction is atomic; DB rollback on any failure.
- Idempotency keys prevent duplicate payment execution.
- Per-payment limit and rolling 24-hour daily limit enforced server-side via `SystemConfig` (configurable without redeploy).
- Human handoff queue (`handoff_cases`) for: exceeds limit, low confidence, spoof failed, ambiguous intent.
- Agent dashboard APIs with role-based JWT guard (`role=agent`). All agent decisions written to immutable `audit_events`.
- Auto-seed on empty database. `ensure_columns()` handles schema migrations idempotently.
- Random single-use liveness challenge with 90-second expiry stored in DB.
- Pluggable spoof-detection adapter (`disabled` → `heuristic` → `remote_http`) without code changes.
- `POST /api/reset-demo` resets demo data without dropping schema.

**Hinglish/English NLP Parser (`app/parser.py`)**
- Deterministic (no ML) amount parsing covering:
  - `paanch sau` (500), `dedh hazaar` (1,500), `dhai sau` (250), `sawa do lakh` (125,000)
  - `sadhe`, `paune`, `aadha`, `sawa` multipliers
  - Devanagari digit normalization
  - Mixed English-Hindi phrases (`five hazaar`, `do thousand`)
- Payee extraction from natural-language phrases in both languages.
- 8 unit tests covering all required phrases plus injection resistance.

**Frontend (React 18 + Vite)**
- All data loaded from backend APIs — no hardcoded users, balances, or payees.
- Voice input via `BrowserSpeechProvider` (Web Speech API); fallback to typed input.
- TTS confirmation: system speaks parsed amount and payee before confirmation dialog.
- Explicit separate confirmation step; silence or initial request never treated as confirmation.
- PIN step-up for amounts above threshold and new payees.
- Loading states, error messages, empty states, and success feedback on all forms.
- Agent dashboard tab (visible only after `role=agent` login).
- Session persistence via `localStorage`.
- Editable system limits (per-payment, daily, confidence threshold) via admin API.
- Handoff deep-link from customer UI to support tab with case reference.

### What Was Cut or Simplified

| Feature | Status | Notes |
|---------|--------|-------|
| Server-side audio analysis | Not implemented | Browser sends text, not audio, to backend. Audio stays in browser/browser vendor. |
| Real spoof detection | Adapter ready; detection disabled | `SPOOF_PROVIDER=disabled` routes all liveness to human review (fail-closed). |
| Email/SMS OTP | Not implemented | PIN is the only step-up factor. |
| Multi-party agent approval | Not implemented | Single agent can approve any case. |
| On-device STT (Whisper.cpp) | Not implemented | Uses browser Web Speech API (sends audio to Google). |
| Real payment rails | Not implemented | All transfers are simulated. |
| Production secret rotation | Not implemented | `SECRET_KEY` is a static env var; JWT tokens do not support revocation. |

### Known Weaknesses

1. **Browser STT sends audio to Google** — the `BrowserSpeechProvider` uses the browser's built-in STT, which transmits audio to the browser vendor. Amounts and payee names are potentially visible to Google. PIN is entered via keypad and never spoken.

2. **Text-only liveness** — the backend receives only the transcript of the spoken challenge, not the audio. A user who types the correct code (after seeing it on screen) passes liveness. Full mitigation requires server-side audio verification.

3. **Render free-tier cold start** — 15 minutes of inactivity causes the service to spin down. The next request has a ~30-second delay.

4. **No JWT revocation** — tokens are valid until expiry (default: configurable `SECRET_KEY`). Logout only clears the local token; a captured token remains valid server-side.

5. **SQLite fallback** — if `DATABASE_URL` is not set, the backend silently falls back to an ephemeral SQLite file. On Render, this means data is lost on every redeploy. The `DATABASE_URL` env var must always be set in production.

### Next Steps for Production

- Connect a real spoof-detection API (e.g. Pindrop, Nuance Gatekeeper) via the `remote_http` adapter.
- Replace browser STT with on-device Whisper.cpp for full audio privacy.
- Add email OTP or TOTP as a second factor alongside PIN.
- Implement JWT revocation via a Redis-backed token blacklist.
- Add multi-party (four-eyes) approval for the agent handoff queue.
- Add proper migrations (Alembic) to replace the `ensure_columns()` shim.
- Set up PgBouncer or connection pooling for MySQL on production traffic.
- Add rate limiting (e.g. slowapi) on auth endpoints.
