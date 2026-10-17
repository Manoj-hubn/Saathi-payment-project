# Saathi Voice Banking — Demo & Evaluation Guide

## Live Application

> **Note:** URLs will be confirmed and updated once deployment to Render + Vercel completes.

| Service | URL |
|---------|-----|
| Frontend | https://saathi-payment-project.vercel.app *(pending deployment)* |
| Backend API | https://saathi-backend.onrender.com *(pending deployment)* |
| Backend Health | https://saathi-backend.onrender.com/api/health |
| API Docs (Swagger) | https://saathi-backend.onrender.com/docs |

> [!IMPORTANT]
> Render free tier has a cold-start delay of ~30 seconds after inactivity. If the first request times out, wait 30 seconds and try again.

## Demo Credentials

These accounts are auto-seeded on first backend startup when the database is empty:

| Username | PIN | Role | Account | Balance |
|----------|-----|------|---------|---------|
| `customer1` | `1234` | customer | DEMO-100001 | ₹25,000 |
| `customer2` | `2468` | customer | DEMO-100002 | ₹18,000 |
| `agent1` | `agentpass` | agent | — | — |

## Demo Script

### Customer Voice Banking Flow

1. **Open** the frontend URL in Chrome (Web Speech API works best in Chrome).
2. **Select** `customer1` from the dropdown and enter PIN `1234`. Click **Login**.
3. **Send Money tab**: Click 🎤 **Speak** and say:
   - `"Send paanch sau to Priya"` — tests Hinglish parser (₹500)
   - `"Transfer dedh hazaar rupees to Rahul"` — tests ₹1,500
   - `"Send dhai sau to Meera"` — tests ₹250
4. The system will **display and speak back** the parsed amount and payee for confirmation.
5. Click the large **Confirm** button (or speak "Yes") to complete the payment.
6. Check **History tab** for the completed transaction.
7. Check **Account tab** for updated balance.

### Liveness Challenge Flow

1. After login, go to **Security tab**.
2. Click **Start Liveness Check**.
3. The server generates a 6-digit random code. Speak it or type it.
4. The system verifies it server-side (single-use, 90-second expiry).

### Human Handoff Flow

1. Login as `customer1`. Try sending ₹15,000 (above the ₹10,000 per-payment limit).
2. The system will automatically create a handoff case and display the support reference.
3. **Logout** and login as `agent1` / `agentpass`.
4. The **Agent Dashboard** shows the pending case with full audit trail.
5. Click **Approve** or **Reject** with a reason.

### Reset Demo Data

```
POST /api/reset-demo
```
No auth required. Clears all payments, ledger, and handoff cases; restores demo balances.

---

## Test Results

**Backend test suite run on 2026-10-17 against local MySQL:**

```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-8.3.5, pluggy-1.6.0
collected 24 items

tests/test_integration.py::test_health                                    PASSED
tests/test_integration.py::test_demo_users_endpoint                       PASSED
tests/test_integration.py::test_login_success                             PASSED
tests/test_integration.py::test_login_invalid_credentials                 PASSED
tests/test_integration.py::test_login_lockout_after_failures              PASSED
tests/test_integration.py::test_role_based_access_control                 PASSED
tests/test_integration.py::test_complete_payment_flow_and_double_entry_ledger PASSED
tests/test_integration.py::test_per_payment_limit_handoff                 PASSED
tests/test_integration.py::test_spoof_detection_adapter                   PASSED
tests/test_integration.py::test_disabled_spoof_fails_closed               PASSED
tests/test_integration.py::test_daily_limit_handoff                       PASSED
tests/test_parser.py::test_required_hinglish_phrases                      PASSED
tests/test_parser.py::test_numeric_amount_is_paise                        PASSED
tests/test_parser.py::test_injection_is_not_payment                       PASSED
tests/test_parser.py::test_unknown_phrase_is_not_guessed                  PASSED
tests/test_parser.py::test_hinglish_payee_extraction                      PASSED
tests/test_parser.py::test_english_payee_extraction                       PASSED
tests/test_parser.py::test_mixed_phrases                                  PASSED
tests/test_security.py::test_challenge_single_use                         PASSED
tests/test_security.py::test_wrong_user_cannot_use_challenge              PASSED
tests/test_security.py::test_digit_normalization                          PASSED
tests/test_security.py::test_pin                                          PASSED
tests/test_security.py::test_jwt_access_token                             PASSED
tests/test_security.py::test_invalid_jwt_access_token                     PASSED

======================== 24 passed, 1 warning in 45.75s ========================
```

**Commands to reproduce:**
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python -m pytest tests/ -v
```

### Test Coverage by Category

| Category | Tests | Result |
|----------|-------|--------|
| API health & demo users | 2 | ✅ Pass |
| Authentication (login success/fail/lockout) | 3 | ✅ Pass |
| Role-based access control | 1 | ✅ Pass |
| Payment flow + double-entry ledger | 1 | ✅ Pass |
| Per-payment limit → handoff | 1 | ✅ Pass |
| Daily limit → handoff | 1 | ✅ Pass |
| Spoof detection adapter | 2 | ✅ Pass |
| Hinglish parser (paanch sau, dedh hazaar, etc.) | 4 | ✅ Pass |
| Mixed language amounts | 1 | ✅ Pass |
| Payee extraction (Hinglish + English) | 2 | ✅ Pass |
| JWT token create/verify | 2 | ✅ Pass |
| PIN hash/verify + bcrypt | 1 | ✅ Pass |
| Liveness challenge (single-use, cross-user) | 2 | ✅ Pass |
| Digit normalization (Devanagari) | 1 | ✅ Pass |
| **Total** | **24** | **✅ All Pass** |

### Voice/Audio Testing

Live, replayed, and cloned audio testing requires a configured `SPOOF_PROVIDER=heuristic` or `SPOOF_PROVIDER=remote_http` adapter. With `SPOOF_PROVIDER=disabled` (the default), all voice authentication routes to human handoff — a fail-closed posture. No spoof-detection adapter was connected to real audio for this submission; audio security behavior is verified via the adapter tests (`test_spoof_detection_adapter`, `test_disabled_spoof_fails_closed`) using synthetic inputs.

### Frontend Build

```
npm run build -- built in 952ms, 0 errors
```

---

## Known Limitations

- Render free tier cold-start: ~30 second delay after 15 minutes of inactivity.
- Browser STT accuracy varies by accent, microphone quality, and ambient noise.
- Spoof detection is disabled by default; all liveness checks hand off to human review.
- The double-entry ledger is simulated; no real payment rails are connected.
- There is no email/SMS OTP; PIN is the only step-up factor.
