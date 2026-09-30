import hashlib
import hmac
import io
import logging
import warnings
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import F, Q
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Inquiry, InquiryPhoto, InquiryThrottle

MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_DAYS = 30
LOG = logging.getLogger(__name__)


def clean_photo(raw):
    if len(raw) > MAX_PHOTO_BYTES:
        raise ValueError("Each photo must be 5 MB or smaller.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw), formats=["JPEG", "PNG", "WEBP"]) as source:
                if source.width * source.height > 20_000_000:
                    raise ValueError("Photos must be no larger than 20 megapixels.")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((2000, 2000))
                clean = Image.new("RGB", oriented.size, "white")
                if "A" in oriented.getbands():
                    clean.paste(oriented.convert("RGB"), mask=oriented.getchannel("A"))
                else:
                    clean.paste(oriented.convert("RGB"))
                output = io.BytesIO()
                clean.save(output, format="JPEG", quality=85)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Please upload valid JPG, PNG or WebP photos.") from exc


def mail_ready():
    values = [settings.EMAIL_HOST, settings.DEFAULT_FROM_EMAIL, settings.INQUIRY_TO_EMAIL]
    return settings.INQUIRY_EMAIL_VERIFIED and all(values) and not any("example." in value or "replace-" in value for value in values)


def purge_expired_photos():
    return InquiryPhoto.objects.filter(expires_at__lte=timezone.now()).delete()[0]


def check_throttle(request):
    # REMOTE_ADDR only: do not trust arbitrary client-supplied forwarding headers.
    key = hmac.new(settings.SECRET_KEY.encode(), request.META.get("REMOTE_ADDR", "unknown").encode(), hashlib.sha256).hexdigest()
    now = timezone.now()
    InquiryThrottle.objects.get_or_create(key=key, defaults={"window_start": now})
    InquiryThrottle.objects.filter(key=key, window_start__lte=now - timedelta(hours=1)).update(window_start=now, count=0)
    accepted = InquiryThrottle.objects.filter(key=key, count__lt=10).update(count=F("count") + 1)
    InquiryThrottle.objects.filter(window_start__lt=now - timedelta(days=1)).delete()
    return bool(accepted), key


def send_notification(inquiry_id):
    if not mail_ready():
        Inquiry.objects.filter(pk=inquiry_id).exclude(email_status="sent").update(email_status="not_configured")
        return False
    now = timezone.now()
    retryable = Q(email_status__in=["pending", "failed", "not_configured"]) | Q(email_status="sending", email_attempt_at__lt=now - timedelta(minutes=5))
    claimed = Inquiry.objects.filter(pk=inquiry_id).filter(retryable).update(email_status="sending", email_attempt_at=now)
    if not claimed:
        return False
    inquiry = Inquiry.objects.get(pk=inquiry_id)
    details = inquiry.details
    body = "New quote inquiry (not a confirmed booking).\n\n" + "\n".join(f"{key.replace('_', ' ').title()}: {value}" for key, value in details.items()) + "\n\nReview optional private photos in the admin inquiry inbox. Photos expire after 30 days."
    try:
        email = EmailMessage(subject=f"SG AllClean quote request {inquiry.reference}", body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[settings.INQUIRY_TO_EMAIL], reply_to=[details["email"]] if details.get("email") else [])
        if email.send(fail_silently=False) != 1:
            raise RuntimeError("Notification not accepted")
        Inquiry.objects.filter(pk=inquiry_id).update(email_status="sent")
        return True
    except Exception as exc:
        LOG.warning("Inquiry notification failed (%s)", type(exc).__name__)
        Inquiry.objects.filter(pk=inquiry_id).update(email_status="failed")
        return False
