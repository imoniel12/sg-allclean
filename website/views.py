import hashlib
import re
import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core import signing
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .forms import QuoteForm
from .inquiry_service import MAX_PHOTO_BYTES, PHOTO_DAYS, check_throttle, clean_photo, mail_ready, purge_expired_photos, send_notification
from .models import ContentSnippet, Inquiry, InquiryPhoto, Page, Post, Service, SiteSettings, NavItem

CONFIRMATION = "We will review your request and contact you to confirm scope, price and availability. Your booking is not yet confirmed."


def context(request, **extra):
    site = SiteSettings.objects.first()
    result = {
        "request": request, "site_settings": site, "settings": site,
        "nav_items": NavItem.objects.filter(is_active=True),
        "current_path": request.path,
        "messages": [{"category": item.tags, "message": str(item)} for item in messages.get_messages(request)],
        "public_email": site.contact_email if site and settings.PUBLIC_EMAIL_VERIFIED else "",
        "phone_href": "tel:" + re.sub(r"[^+0-9]", "", site.contact_phone if site else ""),
        "facebook_url": "https://www.facebook.com/sgallcleanenvironmentalservices.ph",
        "facebook_message_url": "https://www.facebook.com/messages/t/sgallcleanenvironmentalservices.ph",
        "footer_content": dict(ContentSnippet.objects.filter(group_name="footer").values_list("key", "value")),
        "robots_disallow": settings.ROBOTS_DISALLOW_ALL,
    }
    result.update(extra)
    return result


def public_render(request, template, status=200, **extra):
    return render(request, template, context(request, **extra), status=status, using="public")


def quote_context(request):
    return {
        "quote_services": Service.objects.all(), "csrf_token": get_token(request),
        "quote_token": signing.dumps(secrets.token_hex(16), salt="quote-form"),
        "values": {"service": request.GET.get("service", "")},
        "errors": [], "today": timezone.localdate().isoformat(),
    }


@require_GET
def index(request):
    return public_render(request, "index.html", services=Service.objects.all(), homepage=dict(ContentSnippet.objects.filter(group_name="homepage").values_list("key", "value")), process_page=get_object_or_404(Page, slug="how-it-works"), faq_page=get_object_or_404(Page, slug="faq"), **quote_context(request))


@require_GET
def page(request, slug):
    item = get_object_or_404(Page, slug=slug)
    template = "privacy.html" if slug == "privacy" else "brief_page.html" if slug in {"faq", "how-it-works"} else "page.html"
    return public_render(request, template, page=item)


@require_GET
def services(request):
    return public_render(request, "services.html", services=Service.objects.all(), addons=get_object_or_404(Page, slug="add-ons"))


@require_GET
def service_detail(request, slug):
    return public_render(request, "service_detail.html", service=get_object_or_404(Service, slug=slug))


@require_GET
def journal(request):
    return public_render(request, "journal.html", posts=Post.objects.filter(status="published").order_by("-published_at", "-created_at"))


@require_GET
def post_detail(request, slug):
    posts = Post.objects.all() if request.user.has_perm("website.view_post") else Post.objects.filter(status="published")
    return public_render(request, "post_detail.html", post=get_object_or_404(posts, slug=slug))


@require_http_methods(["GET", "POST"])
def contact(request):
    data = quote_context(request)
    if request.method == "GET":
        return public_render(request, "contact.html", **data)
    allowed, spam_key = check_throttle(request)
    if not allowed:
        data["errors"] = ["Too many requests. Try again in an hour, or call/message us."]
        return public_render(request, "contact.html", status=429, **data)
    if getattr(request, "upload_limit_exceeded", False):
        data["errors"] = ["Photos exceed the upload limit. Use up to three photos, 5 MB each."]
        return public_render(request, "contact.html", status=413, **data)
    token = request.POST.get("quote_token", "")
    try:
        signing.loads(token, salt="quote-form", max_age=3600)
    except signing.BadSignature:
        data["errors"] = ["This form has expired. Please complete the refreshed form below."]
        data["values"] = request.POST
        return public_render(request, "contact.html", status=422, **data)
    if request.POST.get("website"):
        return HttpResponse("Unable to submit this request.", status=400)
    submission_token = hashlib.sha256(token.encode()).hexdigest()
    existing = Inquiry.objects.filter(submission_token=submission_token).first()
    if existing:
        messages.success(request, f"Request {existing.reference} already received. {CONFIRMATION}")
        return redirect(reverse("contact") + "#confirmation")
    form = QuoteForm(request.POST)
    errors = []
    photos = []
    if not form.is_valid():
        for field, items in form.errors.items():
            label = form.fields[field].label or field.replace('_', ' ').title() if field in form.fields else "Request"
            errors.extend(f"{label}: {item}" for item in items)
    uploads = request.FILES.getlist("photos")
    if len(uploads) > 3:
        errors.append("Please attach at most three photos.")
    if not errors:
        for upload in uploads:
            try:
                photos.append(clean_photo(upload.read(MAX_PHOTO_BYTES + 1)))
            except ValueError as exc:
                errors.append(str(exc))
    if errors:
        data.update(values=request.POST, errors=errors, quote_token=token)
        return public_render(request, "contact.html", status=422, **data)
    details = {key: str(value) if value is not None else "" for key, value in form.cleaned_data.items()}
    details["privacy_consent"] = "Agreed to inquiry handling and private photo review"
    try:
        with transaction.atomic():
            inquiry = Inquiry.objects.create(reference="SG-" + secrets.token_hex(6).upper(), details=details, spam_key=spam_key, submission_token=submission_token, email_status="pending" if mail_ready() else "not_configured")
            InquiryPhoto.objects.bulk_create([InquiryPhoto(inquiry=inquiry, data=photo, expires_at=timezone.now() + timedelta(days=PHOTO_DAYS)) for photo in photos])
    except IntegrityError:
        # Concurrent double submission of the same signed form.
        inquiry = Inquiry.objects.get(submission_token=submission_token)
    # WSGI-compatible: commit first, then a bounded SMTP attempt. Failure preserves the inquiry.
    if mail_ready():
        send_notification(inquiry.pk)
    purge_expired_photos()
    messages.success(request, f"Request {inquiry.reference} received. {CONFIRMATION}")
    return redirect(reverse("contact") + "#confirmation")


@permission_required("website.view_inquiry", raise_exception=True)
@require_GET
def inquiry_photo(request, photo_id):
    photo = get_object_or_404(InquiryPhoto, pk=photo_id, expires_at__gt=timezone.now())
    return HttpResponse(bytes(photo.data), content_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@require_GET
def robots(request):
    body = "User-agent: *\nDisallow: /\n" if settings.ROBOTS_DISALLOW_ALL else f"User-agent: *\nDisallow: /{settings.ADMIN_BASE_PATH}/\n"
    return HttpResponse(body, content_type="text/plain")


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def legacy_favicon(request, filename="favicon.ico"):
    allowed = {"favicon.ico", "favicon-16x16.png", "favicon-32x32.png", "apple-touch-icon.png", "android-chrome-192x192.png", "android-chrome-512x512.png", "site.webmanifest"}
    if filename not in allowed:
        raise Http404
    path = settings.BASE_DIR / "favicon" / filename
    if not path.exists():
        raise Http404
    return FileResponse(path.open("rb"))


def not_found(request, exception):
    return public_render(request, "404.html", status=404, missing_path=request.path)


def bad_request(request, exception):
    return render(request, "security_error.html", {"error_code": "400", "error_title": "We could not process that request."}, status=400)


def permission_denied(request, exception):
    return render(request, "security_error.html", {"error_code": "403", "error_title": "You do not have access to that page."}, status=403)


def server_error(request):
    return render(request, "security_error.html", {"error_code": "500", "error_title": "Something went wrong on our side."}, status=500)
