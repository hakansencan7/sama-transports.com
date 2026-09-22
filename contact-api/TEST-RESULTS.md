# Verification results

Base: `d8e919b882c75db1e74e53b26664450521a3e79b`. Verified on 22 September 2026.

## Local verification

- Python 3.12.14: **68 passed, 1 skipped** (`pytest`).
- Node 24.19.0 + jsdom 30.1.1: **7 passed** for the unchanged frontend code.
- Dependency audit found no known vulnerabilities at preparation time.
- JavaScript syntax, Python compile and `git diff --check`: passed.
- Alternative VPS Gunicorn/systemd configuration checks passed with temporary dummy settings.

Tests cover field/header validation, exact origins, HTTPS and hosts, signed tokens, CORS,
file count/type/size/content checks, malware and scanner failures, image limits,
persistent rates, concurrent duplicate claims, SMTP TLS/auth ordering, fixed recipient,
retry/uncertain delivery, maintenance mode, private configuration and password files,
symlink rejection, and refusal to authenticate with a missing password.

DOM tests use mocked fetch, not full browser/network email acceptance.
The single local skip is the real AF_UNIX scanner test because this workspace refused
socket creation. It passed on Hetzner.

## Actual Hetzner Webhosting L deployment

- Installed privately under the hosting account; Gunicorn on loopback port 18091,
  Apache routing through a dedicated forms directory and one-minute exclusive cron watchdog.
- Initial installed suite: **64 passed**, including the real Unix socket test.
- Final deployed configuration/password-file update: **69 passed**. Service reloaded in maintenance mode; private password file remains empty.
- Real ClamAV clean-content scan: passed.
- ClamAV **1.4.3**, signature revision **28131**, timestamp **22 September 2026 08:27:06**.
- Real EICAR scan: rejected correctly; no test file was stored publicly or emailed.
- Natro authoritative DNS: added only forms A record to Hetzner.
- Hetzner forms subdomain bound to existing wildcard certificate; public HTTPS verified.
- GET `/v1/contact/token`: **503** maintenance response with exact allowed-origin CORS.
- GET `/healthz`, `/settings.json`, `/app.py`: **404** externally.
- Internal service health: successful. Main site and TRACK routes unchanged.

## SMTP blocker found by live tests

| Target | Result |
|---|---|
| `mail.kurumsaleposta.com:465` | Connection refused |
| `mail.kurumsaleposta.com:587` | STARTTLS available, but certificate hostname mismatch (verify code 62) |
| SMTP peer at `94.73.187.200:587` | Banner `vsp-in3.natrohost.com`; certificate SAN only `*.natrohost.com`, `natrohost.com` |
| `vsp-in3.natrohost.com:587` | Resolves to `89.19.13.6`; connection refused |

The certificate chain was not accepted for a different hostname. No TLS verification
was disabled; no SMTP password, AUTH command or email was sent.
`operations@sama-transports.com` is a group, so a real same-domain mailbox must authenticate.

## Remaining acceptance gates

1. Natro must supply a reachable SMTP endpoint whose certificate matches its hostname.
2. Enter the chosen mailbox password only in the private server file, then verify SMTP login/NOOP.
3. Enable the service, verify both origins and a real request/attachment delivered to operations.
4. Merge the draft frontend PR after successful backend acceptance.
5. Confirm ongoing wildcard certificate renewal with externally hosted DNS.

No frontend production release has been made. The deployed service remains in maintenance mode.
Nginx checks apply only to the alternative VPS deployment, not the actual Apache hosting account.
