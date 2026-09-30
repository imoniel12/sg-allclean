import hashlib
import io
import re
import secrets
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from werkzeug.security import generate_password_hash

from .content import apply_client_brief, setup_editor_group
from .image_security import sanitize_public_image
from .inquiry_service import purge_expired_photos, send_notification
from .models import AdminLoginThrottle, Inquiry, InquiryPhoto, InquiryThrottle, NavItem, Page, Service
from .views import server_error


@override_settings(BASIC_AUTH_ENABLED=False, INQUIRY_EMAIL_VERIFIED=False, PUBLIC_EMAIL_VERIFIED=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class WebsiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        apply_client_brief()
        cls.admin = get_user_model().objects.create_superuser("reviewer", "reviewer@sgallclean.test", "Testing-only-password-129!")
        cls.editor = get_user_model().objects.create_user("editor", password="Testing-only-password-129!", is_staff=True)
        cls.editor.groups.add(setup_editor_group())

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def payload(self, **updates):
        response = self.client.get("/contact")
        html = response.content.decode()
        data = {"csrfmiddlewaretoken": re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)[1], "quote_token": re.search(r'name="quote_token" value="([^"]+)"', html)[1], "name": "Test Client", "phone": "09763173177", "service": "residential-cleaning", "city": "Makati", "property_type": "Condo", "sqm": "30", "preferred_date": (timezone.localdate() + timedelta(days=2)).isoformat(), "description": "Routine clean", "privacy_consent": "on"}
        data.update(updates)
        return data

    def photo(self):
        output = io.BytesIO()
        image = Image.new("RGB", (20, 20), "white")
        exif = image.getexif()
        exif[270] = "Private metadata"
        image.save(output, format="JPEG", exif=exif)
        return SimpleUploadedFile("room.jpg", output.getvalue(), content_type="image/jpeg")

    def test_pages_prices_and_no_internal_proposal_copy(self):
        for url in ["/", "/about", "/contact", "/services", "/how-it-works", "/faq", "/privacy", "/journal"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        home = self.client.get("/").content.decode()
        for text in ["₱1,299", "₱1,699", "₱2,499", "₱4,999", "₱1,499", "₱1,899", "₱1,999", "₱7,200", "static/styles.css"]:
            self.assertIn(text, home)
        for text in ["47%", "margin outlook", "The proposal positions", "Trained,", "bantomagrace@gmail.com", "cdn.tailwindcss"]:
            self.assertNotIn(text, home)
        self.assertEqual(Service.objects.count(), 4)
        self.assertEqual(self.client.get("/services/not-a-service").status_code, 404)

    def test_security_headers_and_external_scripts(self):
        response = self.client.get("/")
        policy = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertNotIn("unsafe-inline", policy)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Permissions-Policy"], "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        html = response.content.decode()
        self.assertIn('/static/site.js', html)
        self.assertNotIn("<script>(", html)

    def test_server_error_page_does_not_query_site_content(self):
        request = RequestFactory().get("/broken")
        with patch("website.views.SiteSettings.objects.first", side_effect=RuntimeError("database unavailable")):
            response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Something went wrong", response.content)

    def test_cms_navigation_rejects_and_neutralizes_unsafe_links(self):
        item = NavItem(label="Unsafe", path="javascript:alert(1)", is_active=True)
        with self.assertRaises(ValidationError):
            item.full_clean()
        existing = NavItem.objects.first()
        NavItem.objects.filter(pk=existing.pk).update(path="javascript:alert(1)")
        html = self.client.get("/").content.decode()
        self.assertNotIn('href="javascript:', html)

    def test_cms_and_inquiry_text_is_escaped(self):
        Page.objects.filter(slug="about").update(body='<script>alert("cms")</script>')
        about = self.client.get("/about").content.decode()
        self.assertNotIn('<script>alert("cms")</script>', about)
        self.assertIn("&lt;script&gt;", about)
        self.client.post("/contact", self.payload(name='<script>alert("inquiry")</script>'))
        inquiry = Inquiry.objects.get()
        self.client.force_login(self.admin)
        admin_page = self.client.get(reverse("admin:website_inquiry_change", args=[inquiry.pk])).content.decode()
        self.assertNotIn('<script>alert("inquiry")</script>', admin_page)
        self.assertIn("&lt;script&gt;", admin_page)

    def test_brief_is_applied_once_and_preserves_cms_edits(self):
        Page.objects.filter(slug="about").update(title="Edited by client")
        self.assertFalse(apply_client_brief())
        self.assertEqual(Page.objects.get(slug="about").title, "Edited by client")

    def test_phone_only_inquiry_saved_without_email(self):
        response = self.client.post("/contact", self.payload())
        self.assertEqual(response.status_code, 302)
        inquiry = Inquiry.objects.get()
        self.assertEqual(inquiry.details["service"], "Standard Condo Cleaning")
        self.assertEqual(inquiry.email_status, "not_configured")
        self.assertContains(self.client.get(response.url), "Your booking is not yet confirmed")

    def test_email_only_inquiry(self):
        response = self.client.post("/contact", self.payload(phone="", email="client@sgallclean.test"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_csrf_required(self):
        data = self.payload()
        del data["csrfmiddlewaretoken"]
        self.assertEqual(self.client.post("/contact", data).status_code, 403)
        self.assertFalse(Inquiry.objects.exists())

    def test_invalid_quote_fields_and_expired_token(self):
        for changes in [{"phone": "", "email": ""}, {"service": "missing"}, {"sqm": "nan"}, {"sqm": "-1"}, {"preferred_date": "2000-01-01"}, {"privacy_consent": ""}, {"description": ""}, {"quote_token": "tampered"}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/contact", self.payload(**changes)).status_code, 422)
        self.assertFalse(Inquiry.objects.exists())

    def test_duplicate_post_saves_only_once(self):
        data = self.payload()
        self.assertEqual(self.client.post("/contact", data).status_code, 302)
        self.assertEqual(self.client.post("/contact", data).status_code, 302)
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_honeypot_and_rate_limit(self):
        self.assertEqual(self.client.post("/contact", self.payload(website="bot.invalid")).status_code, 400)
        InquiryThrottle.objects.update(count=10)
        self.assertEqual(self.client.post("/contact", self.payload()).status_code, 429)
        self.assertFalse(Inquiry.objects.exists())

    def test_photos_private_metadata_removed_and_deleted_with_inquiry(self):
        self.assertEqual(self.client.post("/contact", self.payload(photos=self.photo())).status_code, 302)
        photo = InquiryPhoto.objects.get()
        with Image.open(io.BytesIO(bytes(photo.data))) as image:
            self.assertFalse(image.getexif())
        url = reverse("inquiry_photo", args=[photo.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        photo.expires_at = timezone.now() - timedelta(seconds=1)
        photo.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(purge_expired_photos(), 1)
        InquiryPhoto.objects.create(inquiry=Inquiry.objects.get(), data=b"dummy", expires_at=timezone.now() + timedelta(days=1))
        Inquiry.objects.all().delete()
        self.assertFalse(InquiryPhoto.objects.exists())

    def test_fake_and_oversized_photos_rejected(self):
        for content in [b"not an image", b"x" * (5 * 1024 * 1024 + 1)]:
            photo = SimpleUploadedFile("room.jpg", content, content_type="image/jpeg")
            self.assertEqual(self.client.post("/contact", self.payload(photos=photo)).status_code, 422)
        self.assertFalse(Inquiry.objects.exists())

    def test_admin_public_images_are_reencoded_without_metadata(self):
        source = self.photo()
        cleaned = sanitize_public_image(source, "test")
        self.assertTrue(cleaned.name.endswith(".webp"))
        with Image.open(io.BytesIO(cleaned.read())) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertFalse(image.getexif())
        with self.assertRaises(ValidationError):
            sanitize_public_image(SimpleUploadedFile("fake.jpg", b"not-an-image"), "test")

    def test_total_upload_limit_rejects_request_before_saving(self):
        uploads = [SimpleUploadedFile(f"room-{number}.jpg", b"x" * (6 * 1024 * 1024), content_type="image/jpeg") for number in range(3)]
        self.assertEqual(self.client.post("/contact", self.payload(photos=uploads)).status_code, 413)
        self.assertFalse(Inquiry.objects.exists())

    @override_settings(INQUIRY_EMAIL_VERIFIED=True, EMAIL_HOST="smtp.sgallclean.test", DEFAULT_FROM_EMAIL="quotes@sgallclean.test", INQUIRY_TO_EMAIL="owner@sgallclean.test", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_success_and_no_duplicate_delivery(self):
        self.assertEqual(self.client.post("/contact", self.payload()).status_code, 302)
        inquiry = Inquiry.objects.get()
        self.assertEqual(inquiry.email_status, "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(inquiry.reference, mail.outbox[0].subject)
        self.assertFalse(send_notification(inquiry.pk))
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(INQUIRY_EMAIL_VERIFIED=True, EMAIL_HOST="smtp.sgallclean.test", DEFAULT_FROM_EMAIL="quotes@sgallclean.test", INQUIRY_TO_EMAIL="owner@sgallclean.test", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_failure_keeps_request_and_retry_works(self):
        with patch("website.inquiry_service.EmailMessage.send", side_effect=OSError("offline")):
            self.assertEqual(self.client.post("/contact", self.payload()).status_code, 302)
        inquiry = Inquiry.objects.get()
        self.assertEqual(inquiry.email_status, "failed")
        self.assertTrue(send_notification(inquiry.pk))
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.email_status, "sent")

    def test_admin_inbox_and_content_permissions(self):
        self.client.post("/contact", self.payload(photos=self.photo()))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("admin:website_inquiry_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:website_inquiry_change", args=[Inquiry.objects.get().pk])).status_code, 200)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse("admin:website_inquiry_changelist")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:website_service_changelist")).status_code, 200)

    def test_admin_login_is_rate_limited_and_success_resets_counter(self):
        login_client = Client()
        login_url = reverse("admin:login")
        for _ in range(10):
            self.assertEqual(login_client.post(login_url, {"username": "reviewer", "password": "wrong"}).status_code, 200)
        blocked = login_client.post(login_url, {"username": "reviewer", "password": "wrong"})
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked["Retry-After"], "900")
        AdminLoginThrottle.objects.all().delete()
        success = login_client.post(login_url, {"username": "reviewer", "password": "Testing-only-password-129!"})
        self.assertEqual(success.status_code, 302)
        self.assertFalse(AdminLoginThrottle.objects.exists())


@override_settings(BASIC_AUTH_ENABLED=False)
class LegacyImportTests(TestCase):
    def test_import_preserves_source_and_upgrades_existing_password(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.db"
            connection = sqlite3.connect(source)
            connection.execute("CREATE TABLE admin_user (id INTEGER, username TEXT, password_hash TEXT, role TEXT, is_active TEXT)")
            connection.execute("INSERT INTO admin_user VALUES (1, ?, ?, ?, ?)", ("existing-admin", generate_password_hash("Existing-pass-129!"), "full_admin", "true"))
            connection.commit()
            connection.close()
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            call_command("import_legacy", str(source), stdout=io.StringIO())
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(Service.objects.count(), 4)
            self.assertTrue(self.client.login(username="existing-admin", password="Existing-pass-129!"))
            user = get_user_model().objects.get(username="existing-admin")
            self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
            call_command("import_legacy", str(source), stdout=io.StringIO())
            self.assertEqual(get_user_model().objects.filter(username="existing-admin").count(), 1)
