# Verification results

Verified against base commit `d8e919b882c75db1e74e53b26664450521a3e79b`.

- Python 3.12.14: **58 passed, 1 skipped** (`pytest`).
- Node 24.19.0 + jsdom 30.1.1: **7 passed** (DOM interaction tests).
- `pip-audit -r requirements.txt`: **No known vulnerabilities found** at preparation time.
- `node --check contact.js`, Python compile check and `git diff --check`: passed.
- Gunicorn `--check-config 'app:create_app()'`: passed with temporary dummy settings; no server started.
- systemd unit verification passed using a temporary copy with ExecStart pointing to the installed test virtualenv. Production paths do not exist here.

Python checks cover server validation and header injection, allowed/disallowed origins, HTTP/untrusted hosts, signed token expiry and client binding, CORS, unsupported/oversized/multiple attachments, allowed file formats, scanner failure/malware verdicts, image decompression limits, persistent rate limits, concurrent duplicate claims, SMTP TLS/authentication ordering, certificate verification, fixed recipient, retry behavior and uncertain delivery handling.

DOM checks cover service preselection, API availability gating, successful submission, SMTP refusal, retaining input, replaying the same token after a lost response, uncertain-result lockout, duplicate clicks and client-side file size validation. These are DOM tests with mocked fetch, not a full rendered browser/network acceptance test.

The skipped test opens a local AF_UNIX socket to exercise the scanner stream protocol. This execution environment returned `PermissionError`; the test remains runnable on Hetzner. Protocol framing and ClamAV OK/FOUND/ERROR responses passed separate mocked-socket tests.

## Checks still required on Hetzner

- Actual Natro hostname, TLS certificate, credentials, account authorization and outbound SMTP reachability.
- Real ClamAV daemon, fresh virus signatures, socket permissions and EICAR rejection.
- `nginx -t` with real TLS certificate files and existing proxy configuration (Nginx is not installed in this workspace).
- DNS, public HTTPS and actual CORS preflight from both allowed website origins.
- A real email with an attachment received by `operations@sama-transports.com`.

No real email was sent. No production DNS, server configuration or website deployment was changed.
