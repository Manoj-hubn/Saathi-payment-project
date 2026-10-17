# Saathi Voice Banking — Threat Model

## Threat 1: Recorded Voice Replay

| | |
|---|---|
| **Attack** | Attacker captures a legitimate user's voice saying "send money to X" and plays it back to authenticate or authorize a transaction. |
| **Defense** | Server generates a random, single-use liveness challenge (6-digit code) with a 90-second expiry. The user must speak the exact challenge digits. A recording of a previous session will not contain the correct challenge. |
| **Enforcement** | Backend (`app/flow.py`, `liveness()` function): challenge stored in DB per-session; marked used after one validation; expired challenges are rejected. |
| **Limitation** | Browser STT sends text not audio to backend — the backend cannot verify whether the text came from live speech or typed input. A determined attacker who intercepts the real-time challenge and replays a voice response within 90 seconds could still pass. Full mitigation requires server-side audio analysis (not implemented in demo). |

## Threat 2: Voice Cloning

| | |
|---|---|
| **Attack** | Attacker synthesizes a voice clone of the user using a text-to-speech model and uses it to pass the liveness check. |
| **Defense** | The `spoof.py` adapter layer is designed to accept a remote spoof-detection API. Even when spoof detection passes (or is disabled), transactions above `PAYMENT_THRESHOLD` (₹5,000 default) still require a separate PIN step-up. A cloned voice alone cannot complete a high-value transfer without knowing the PIN. |
| **Enforcement** | `app/flow.py`: after liveness, `pin_check()` is required for new payees and amounts above threshold. PIN is bcrypt-hashed and never stored in plaintext. Three failed PIN attempts lock the account (DB-backed). |
| **Limitation** | With `SPOOF_PROVIDER=disabled`, the spoof check always routes to human handoff — effectively blocking any voice-only transaction. When a detection adapter is configured, a sufficiently good clone that passes the detector and the user's PIN is leaked out-of-band would defeat this layer. |

## Threat 3: Misheard Amounts and Transaction Confirmation

| | |
|---|---|
| **Attack** | Speech recognition mishears "paanch sau" (₹500) as ₹5,000, causing an unintended larger transfer. Or a user says "yes" in a different context and it is captured as transaction confirmation. |
| **Defense** | The deterministic Hinglish parser (`app/parser.py`) converts spoken amounts to exact integers with unit tests. The backend always echoes back the parsed amount in digits AND words before asking for confirmation. Confirmation requires a separate, explicit HTTP `POST /api/confirm` call — not implicit from the speech transcript. |
| **Enforcement** | Frontend (`App.jsx`): shows a large confirmation dialog with amount in numerals and words. User must click "Confirm" button or say "Yes" in response to the explicit confirmation prompt, not their original request. Backend confirms only when `transaction_id` is passed and its state is `pending_confirm`. |
| **Limitation** | Browser STT can still mishear amounts. If the parser receives an incorrect transcript it will parse what was heard. Mitigation relies on user reviewing the displayed amount before confirming. |

## Threat 4: Social Engineering of the Agent

| | |
|---|---|
| **Attack** | A caller manipulates a human agent into approving a fraudulent handoff case by providing false context (e.g. impersonating an account holder or claiming urgency). |
| **Defense** | The agent dashboard (`GET /api/agent/cases`) shows verified metadata — account number, failed verification count, flagged reason, and immutable audit trail — not just the caller's claim. Agents cannot modify the transaction amount or payee; they can only approve or reject the case as-submitted. |
| **Enforcement** | Agent endpoints require `role=agent` JWT claim (`require_agent()` in `app/main.py`). All agent decisions are written to `audit_events` with the agent's user ID, timestamp, and decision. Audit events are append-only; they cannot be edited via any API. |
| **Limitation** | The demo does not implement multi-party agent approval (four-eyes principle). A single compromised agent account can approve cases. |

## Threat 5: Third-Party Speech Provider Data Exposure

| | |
|---|---|
| **Attack** | A third-party cloud STT provider receives audio containing sensitive information (account numbers, PINs, payee details) and may log, analyze, or leak it. |
| **Defense** | The system uses only the browser's built-in Web Speech API (`BrowserSpeechProvider` in `speechAdapter.js`) by default. This processes audio locally or via the browser vendor's servers — no application-controlled third-party API receives the audio stream. The backend never receives raw audio; it only receives the text transcript. PINs are entered via a numeric keypad, not spoken. |
| **Enforcement** | `app/main.py`: no audio upload endpoint exists. Audio processing is entirely client-side. |
| **Limitation** | The browser STT (e.g. Chrome's API) does send audio to Google's servers for processing. This is outside application control. Sensitive words (payee name, amounts) are transmitted. Production deployment should evaluate on-device STT (Whisper.cpp) for full air-gap. PIN is never spoken — the keypad entry avoids that exposure. |
