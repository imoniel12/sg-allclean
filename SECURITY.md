# SG AllClean security baseline

This project is hardened against the [OWASP Top 10:2025](https://top10.owasp.org/2025/). This is an engineering baseline, not a certification or substitute for an independent penetration test. Hosting, DNS, TLS, mailbox security, backups and administrator behavior remain part of the system.

| OWASP 2025 risk | Controls in this project |
| --- | --- |
| A01 Broken Access Control | Django model permissions; inquiry photos require `view_inquiry`; content moderators cannot access inquiries, users, site settings or navigation; CSRF on state changes; protected photo URLs; no public media route for inquiry photos; internal-only CMS links. |
| A02 Security Misconfiguration | Explicit hosts; production refuses placeholder/short secrets and wildcard hosts; DEBUG off in deployment guide; CSP, HSTS configuration, clickjacking, MIME sniffing, referrer, permissions and cross-origin headers; generic error pages; private admin caching. |
| A03 Software Supply Chain Failures | Exact direct dependency versions; `pip-audit` validation; minimal runtime dependencies; documented update and audit process. Commit review and a trusted package index are still required. |
| A04 Cryptographic Failures | HTTPS redirect/secure cookies in production; HttpOnly/SameSite cookies; Django PBKDF2 password hashing; legacy Werkzeug hashes automatically upgrade after successful login; SMTP TLS. Secrets stay in ignored `.env`. |
| A05 Injection | Django ORM; template auto-escaping; `richtext` escapes CMS input; no shell execution from requests; CSP; CMS URL schemes validated and neutralized at render time. |
| A06 Insecure Design | Quote workflow commits before email; signed one-use submission identifiers; duplicate prevention; request/file limits; image decode/re-encode; consent and retention behavior; database-backed throttles. |
| A07 Authentication Failures | Django authentication and password validators; 8-hour rolling admin sessions; ten failed attempts per username/IP per 15 minutes; session rotation by Django; no seeded default account on fresh installs. |
| A08 Software or Data Integrity Failures | Signed quote form token; CSRF; images are decoded and re-encoded as random-name WebP/JPEG with metadata removed; file type/size/pixel limits; migrations and one-time imports are explicit. |
| A09 Security Logging and Alerting Failures | Authentication failures/successes, throttles, access denials and server errors are logged without passwords or inquiry content; Django admin records content changes. Configure PythonAnywhere log retention and external alerts. |
| A10 Mishandling Exceptional Conditions | Generic 400/403/404/500 responses; failed SMTP preserves the inquiry; idempotent notifications and submissions; upload/parser limits; cleanup jobs; tests for failure paths. |

## Before every production release

```bash
python -m pip install pip-audit==2.10.1
python manage.py test website
python manage.py check
python manage.py check --deploy
python -m pip_audit -r requirements.txt
python manage.py collectstatic --noinput
```

Run `check --deploy` using production environment values. The deliberate HSTS subdomain/preload warnings are explained in `DEPLOY_PYTHONANYWHERE.md`.

Review PythonAnywhere access/error/server logs and Django security log events. Set alerts for repeated admin failures, 403/429 spikes and 500 responses. Back up the SQLite database and uploaded public media, encrypt backups, test restoration, and restrict filesystem permissions for `.env` and the database to the account owner.

Enable MFA for the PythonAnywhere account and the email account. Django admin MFA is not bundled in this small project; add and test a maintained Django MFA package before giving admin access to more people or exposing a higher-risk deployment.

Re-run dependency audit at least monthly and before deployment. Apply supported Django/Pillow/Werkzeug/python-dotenv security updates promptly. Remove `LegacyWerkzeugHasher` and the Werkzeug dependency after every imported administrator has successfully signed in once and their hash has upgraded.

After deployment, arrange an independent authenticated penetration test covering the public form, Django admin, WSGI/proxy configuration, static/media mappings, TLS and account recovery.
