import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set SECRET_KEY in .env before starting Django.")
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [url.strip() for url in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if url.strip()]
if not DEBUG:
    if SECRET_KEY == "replace-with-a-long-random-key" or len(SECRET_KEY) < 50:
        raise ImproperlyConfigured("Production SECRET_KEY must be a unique random value of at least 50 characters.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Production DJANGO_ALLOWED_HOSTS must list explicit hostnames; wildcard hosts are not allowed.")
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "website"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "website.middleware.SecurityHeadersMiddleware", "website.middleware.StagingAuthMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "website.middleware.AdminLoginThrottleMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "django_templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}},
    {"NAME": "public", "BACKEND": "django.template.backends.jinja2.Jinja2", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": False, "OPTIONS": {"environment": "website.jinja.environment"}},
]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ.get("DJANGO_DATABASE_PATH") or BASE_DIR / "sg_allclean_django.sqlite3", "OPTIONS": {"timeout": 20}}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher", "website.hashers.LegacyWerkzeugHasher"]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ADMIN_BASE_PATH = os.environ.get("ADMIN_BASE_PATH", "/portal-access").strip("/")
SESSION_COOKIE_SECURE = os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_SAVE_EVERY_REQUEST = True
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "false").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("DJANGO_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
SECURE_HSTS_PRELOAD = os.environ.get("DJANGO_HSTS_PRELOAD", "false").lower() == "true"
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 3
DATA_UPLOAD_MAX_NUMBER_FIELDS = 40
FILE_UPLOAD_HANDLERS = ["website.uploads.QuoteUploadLimit", "django.core.files.uploadhandler.MemoryFileUploadHandler", "django.core.files.uploadhandler.TemporaryFileUploadHandler"]
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("SMTP_USERNAME", "")
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_USE_SSL = os.environ.get("SMTP_SSL", "false").lower() == "true"
EMAIL_USE_TLS = not EMAIL_USE_SSL
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.environ.get("SMTP_FROM", "")
INQUIRY_TO_EMAIL = os.environ.get("INQUIRY_TO_EMAIL", "")
INQUIRY_EMAIL_VERIFIED = os.environ.get("INQUIRY_EMAIL_VERIFIED", "false").lower() == "true"
PUBLIC_EMAIL_VERIFIED = os.environ.get("PUBLIC_EMAIL_VERIFIED", "false").lower() == "true"
ROBOTS_DISALLOW_ALL = os.environ.get("ROBOTS_DISALLOW_ALL", "false").lower() == "true"
BASIC_AUTH_ENABLED = os.environ.get("BASIC_AUTH_ENABLED", "false").lower() == "true"
BASIC_AUTH_USERNAME = os.environ.get("BASIC_AUTH_USERNAME", "")
BASIC_AUTH_PASSWORD = os.environ.get("BASIC_AUTH_PASSWORD", "")
if BASIC_AUTH_ENABLED and (not BASIC_AUTH_USERNAME or not BASIC_AUTH_PASSWORD or BASIC_AUTH_PASSWORD.startswith("replace-")):
    raise ImproperlyConfigured("BASIC_AUTH_ENABLED requires non-placeholder BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD.")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"security": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "security"}},
    "loggers": {
        "sgallclean.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
