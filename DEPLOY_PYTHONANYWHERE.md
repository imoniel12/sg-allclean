# SG AllClean — Django / PythonAnywhere

The site now uses Django 5.2 LTS and WSGI. Public pages retain Jinja templates and use local CSS. Django admin replaces the FastAPI CMS. There is no Uvicorn or Gunicorn requirement on PythonAnywhere.

## Local development

The current workspace has already been migrated into `sg_allclean_django.sqlite3`. Existing admin usernames/passwords are preserved; the original `sg_allclean.db` is unchanged.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Open `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/portal-access/` (or your configured `ADMIN_BASE_PATH`). Stop any old FastAPI server first if it occupies port 8000.

For another checkout, create `.env` from `.env.example`, set a random secret, then:

```bash
python manage.py migrate
# If you have the original database, import BEFORE bootstrap_site:
python manage.py import_legacy /path/to/sg_allclean.db
# Or, for a fresh site without the original database:
python manage.py bootstrap_site
python manage.py createsuperuser
```

Do not run `createsuperuser` for an imported username. Import is read-only against the original SQLite file, refuses to overwrite existing Django content, and only runs once. The initial brief is also applied once; future CMS edits survive restarts. Legacy Werkzeug passwords upgrade to Django's default hash upon successful login. No default admin account is created on a fresh installation.

## Upload and environment

1. Upload the project to `/home/YOUR_USERNAME/sg-allclean` using Git or PythonAnywhere Files. Include `config/`, `website/` (including migrations), `templates/`, `static/`, `favicon/`, `brief_content.py`, `manage.py`, and `requirements.txt`. Do not upload `.venv`, `.git`, caches, test artifacts or your local `.env`.
2. To preserve this workspace's content and accounts, privately upload `sg_allclean_django.sqlite3` into that directory while the destination app is stopped. It is intentionally excluded from Git. If you upload this database, do not run `import_legacy` or `createsuperuser`; just run migrations. Alternatively upload the original `sg_allclean.db` and import it into an empty Django database, or bootstrap a fresh site as above.
3. Upload `media/` if it contains images added through Django admin. Existing imported logos/posts under `static/uploads/` are included by `collectstatic`.
4. Create a virtualenv using a Python version available on your PythonAnywhere account and supported by Django 5.2 (Python 3.10–3.14; 3.12 is used locally). The Web app must use the same Python version. Example:

```bash
cd /home/YOUR_USERNAME/sg-allclean
python3.12 -m venv /home/YOUR_USERNAME/.virtualenvs/sg-allclean
source /home/YOUR_USERNAME/.virtualenvs/sg-allclean/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Paste the generated key into `.env` as `SECRET_KEY`. Set:

```dotenv
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com
DJANGO_DATABASE_PATH=/home/YOUR_USERNAME/sg-allclean/sg_allclean_django.sqlite3
SESSION_HTTPS_ONLY=true
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_HSTS_SECONDS=3600
```

Use your actual domain (including the EU hostname if applicable). Do not put a URL scheme in `DJANGO_ALLOWED_HOSTS`. SQLite is the default; the old FastAPI `DATABASE_URL`/`UPLOADS_DIR` variables are not used. Keep the database on persistent disk and back it up separately. This configuration targets a small site; evaluate a hosted database if write traffic grows.

Run:

```bash
python manage.py migrate
# Only if you did not upload a populated Django database:
# python manage.py import_legacy sg_allclean.db
# OR python manage.py bootstrap_site && python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py check --deploy
python -m pip install pip-audit==2.10.1
python -m pip_audit -r requirements.txt
```

With the production settings above, Django may report W005/W021 for HSTS subdomains and preload. Those are intentionally disabled: enable them only after you control the domain and confirm HTTPS for all relevant subdomains. They are not required to run the PythonAnywhere app.

The application adds CSP, clickjacking, MIME-sniffing, referrer, permissions and cross-origin headers. Production startup refuses a placeholder/short secret or wildcard host. Do not weaken those checks to make deployment errors disappear; correct `.env` instead.

## PythonAnywhere Web tab

1. Add a Web app using **Manual configuration** and the matching Python version.
2. Set the virtualenv to `/home/YOUR_USERNAME/.virtualenvs/sg-allclean`.
3. Open the WSGI configuration file linked from the Web tab. Replace its contents with `pythonanywhere_wsgi.py`, changing `YOUR_USERNAME` and the project directory.
4. Add these static mappings:

| URL | Directory |
| --- | --- |
| `/static/` | `/home/YOUR_USERNAME/sg-allclean/staticfiles` |
| `/media/` | `/home/YOUR_USERNAME/sg-allclean/media` |

Favicon routes are served by Django. Private inquiry photos are stored in the database and must never have a public static mapping. Reload the Web app, then check the homepage, `/contact`, `/faq`, `/how-it-works`, admin login, logo and admin styling.

This follows PythonAnywhere's [existing Django deployment guide](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/) and [Django static-file guide](https://help.pythonanywhere.com/pages/DjangoStaticFiles/).

## Quote delivery and photos

The local `.env` contains disabled placeholders. Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_SSL`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and `INQUIRY_TO_EMAIL` to your provider's real values. Port 587 uses STARTTLS; set `SMTP_SSL=true` for implicit TLS (usually port 465). Only enable `INQUIRY_EMAIL_VERIFIED=true` for the confirmed recipient, reload, then submit a test request and verify actual inbox receipt. SMTP acceptance alone does not prove delivery.

Email attempts run after the inquiry is committed, with a 15-second SMTP timeout. Failures remain in **Quote inquiries** with a retry action. Interrupted requests can also be retried; stale delivery claims expire after five minutes. Do not rely on unsupervised background threads on WSGI hosting. A crash after SMTP acceptance but before the status update can result in a duplicate notification on retry.

PythonAnywhere free accounts restrict outbound connections, including most SMTP servers. Check their [SMTP guidance](https://help.pythonanywhere.com/pages/SMTPForFreeUsers/) for your account/provider before selecting a mailbox. Saved inquiries remain available even if SMTP is unavailable.

The public email is hidden until you edit it under **Site settings** and set `PUBLIC_EMAIL_VERIFIED=true`. Phone and Facebook actions work independently.

Each request allows up to three real JPG/PNG/WebP images, 5 MB and 20 megapixels each. Images are re-encoded without metadata, limited to 2,000 pixels per dimension, and stored privately in SQLite. Photo URLs require the inquiry-view permission and stop working after 30 days. Inquiries support CSRF checks, signed submission tokens, duplicate protection, a honeypot, server validation and a database-backed limit of ten attempts/hour per client IP. Reverse proxies may share a client IP; review this limit for your deployment rather than trusting arbitrary forwarded headers.

Schedule this daily in PythonAnywhere Tasks if your plan supports it:

```bash
/home/YOUR_USERNAME/.virtualenvs/sg-allclean/bin/python /home/YOUR_USERNAME/sg-allclean/manage.py purge_inquiry_photos
```

Cleanup also runs on submission and when administrators open the inbox. Inquiry text is retained for service coordination until an administrator deletes it; deleting an inquiry cascades to its photos. Mailbox copies and backups need their own retention process. Confirm that policy with the client before launch.

Schedule Django's session cleanup too:

```bash
/home/YOUR_USERNAME/.virtualenvs/sg-allclean/bin/python /home/YOUR_USERNAME/sg-allclean/manage.py clearsessions
```

Protect `/home/YOUR_USERNAME/sg-allclean/.env` and the SQLite database so only your PythonAnywhere account can read/write them. Enable MFA on PythonAnywhere and the mailbox, review access/error/server logs, and test encrypted database/media backups and restoration. See `SECURITY.md` for the OWASP Top 10 mapping, release checks and remaining operational controls.

## Content and launch checks

- **Services**: edit package inclusions, times and rates in Details; all three public placements reuse the same record.
- **Pages**: About, FAQ, How It Works, add-on prices and privacy copy. Separate blocks with blank lines; the first line is the FAQ/process/add-on heading.
- **Site settings**: hero, intro, phone, coverage, logo and verified public email.
- **Content snippets**: checklist and footer copy. **Navigation**: menu items.
- **Users / groups**: imported full admins become superusers. Content moderators can edit pages/services/posts/snippets, but cannot access inquiries, users or settings.
- **Quote inquiries**: full admins can view details/private photos, retry email and delete records using Django's confirmation screen.

The site implements the workbook's prices and copy; the separate approved price-list/checklist PDFs were not provided. Confirm final logo/photos, registered business name, service scope, prices, operating hours, mailbox, domain and final client sign-off. No gallery, unapproved PDF download, map, payment flow or instant booking is published. Existing journal records remain in the CMS; the old scaffold's proposal-style article is held as a draft for review.

Validation:

```bash
python manage.py test website
python manage.py check
python manage.py makemigrations --check --dry-run
```
