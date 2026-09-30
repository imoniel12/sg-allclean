import base64
import hashlib
import hmac
import logging
from datetime import timedelta
from hmac import compare_digest
from django.conf import settings
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone

SECURITY_LOG = logging.getLogger("sgallclean.security")


class SecurityHeadersMiddleware:
    """Add browser controls centrally, including to framework error responses."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        admin_request = request.path.startswith("/" + settings.ADMIN_BASE_PATH + "/")
        script_src = "'self' 'unsafe-inline'" if admin_request else "'self'"
        style_src = "'self' 'unsafe-inline'" if admin_request else "'self'"
        policy = (
            "default-src 'self'; "
            f"script-src {script_src}; style-src {style_src}; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if not settings.DEBUG:
            policy += "; upgrade-insecure-requests"
        response.setdefault("Content-Security-Policy", policy)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if admin_request:
            response["Cache-Control"] = "no-store, private"
        if response.status_code >= 500:
            SECURITY_LOG.error("server_error method=%s path=%s status=%s", request.method, request.path, response.status_code)
        elif response.status_code in {401, 403, 429}:
            SECURITY_LOG.warning("security_response method=%s path=%s status=%s", request.method, request.path, response.status_code)
        return response


class StagingAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.BASIC_AUTH_ENABLED and request.path not in {"/health", "/robots.txt"}:
            try:
                scheme, encoded = request.headers.get("Authorization", "").split(" ", 1)
                username, password = base64.b64decode(encoded, validate=True).decode().split(":", 1)
                allowed = scheme.lower() == "basic" and compare_digest(username, settings.BASIC_AUTH_USERNAME) and compare_digest(password, settings.BASIC_AUTH_PASSWORD)
            except (ValueError, UnicodeError):
                allowed = False
            if not allowed:
                SECURITY_LOG.warning("staging_auth_failed path=%s", request.path)
                return HttpResponse("Staging access required", status=401, headers={"WWW-Authenticate": 'Basic realm="Staging"', "Cache-Control": "no-store"})
        response = self.get_response(request)
        if settings.ROBOTS_DISALLOW_ALL or request.path.startswith('/' + settings.ADMIN_BASE_PATH):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response


class AdminLoginThrottleMiddleware:
    WINDOW = timedelta(minutes=15)
    LIMIT = 10

    def __init__(self, get_response):
        self.get_response = get_response
        self.login_path = "/" + settings.ADMIN_BASE_PATH + "/login/"

    def _key(self, request):
        username = str(request.POST.get("username", "")).strip().casefold()[:150]
        address = request.META.get("REMOTE_ADDR", "unknown")
        payload = f"{address}\0{username}".encode()
        return hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()

    def __call__(self, request):
        if request.method != "POST" or request.path != self.login_path:
            return self.get_response(request)
        from .models import AdminLoginThrottle

        key = self._key(request)
        now = timezone.now()
        record, _ = AdminLoginThrottle.objects.get_or_create(key=key, defaults={"window_start": now})
        if record.window_start <= now - self.WINDOW:
            AdminLoginThrottle.objects.filter(key=key).update(window_start=now, count=0)
            record.count = 0
        if record.count >= self.LIMIT:
            SECURITY_LOG.warning("admin_login_rate_limited key=%s", key[:12])
            return HttpResponse("Too many sign-in attempts. Try again in 15 minutes.", status=429, headers={"Retry-After": "900", "Cache-Control": "no-store"})

        response = self.get_response(request)
        if request.user.is_authenticated:
            AdminLoginThrottle.objects.filter(key=key).delete()
            SECURITY_LOG.info("admin_login_success user_id=%s", request.user.pk)
        else:
            AdminLoginThrottle.objects.filter(key=key, count__lt=self.LIMIT).update(count=F("count") + 1)
            SECURITY_LOG.warning("admin_login_failed key=%s", key[:12])
        AdminLoginThrottle.objects.filter(window_start__lt=now - timedelta(days=1)).delete()
        return response
