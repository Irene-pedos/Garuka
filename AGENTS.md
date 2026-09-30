# AGENTS.md — Rules for Coding Agents

## 0. Mandatory Rules
1. Everything must work through Africa's Talking (AT) sandbox with the backend exposed by ngrok.
2. USSD endpoint always returns HTTP 200, `Content-Type: text/plain`, body starting with `CON ` or `END `. Any HTTP error or malformed body makes AT terminate the session. Never let an exception escape the USSD route; catch everything and return `END Service temporarily unavailable. Please try again.`
3. Every USSD screen must be <= 160 characters (hard limit 182). Enforce in the renderer with a unit test.
4. Never log the raw `text` field or any PIN. `text` is cumulative and contains the PIN in plain digits on every request.
5. Minors' data: collect the minimum, scope every query by role, write audit logs, never put reasons or diagnoses in SMS.
6. Business dates use Africa/Kigali (UTC+2). Store timestamps as UTC `timestamptz`. Store phone numbers as E.164 (`+250788123456`).
7. Do not invent AT behavior. If unsure, check AT docs and note it in `docs/ASSUMPTIONS.md`.
8. Write tests with the code. A task is not done without tests.
