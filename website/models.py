from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


def validate_internal_path(value):
    if value and (not value.startswith("/") or value.startswith("//") or "\\" in value):
        raise ValidationError("Use an internal path beginning with one slash, for example /contact.")


def validate_image_size(value):
    if value and value.size > 5 * 1024 * 1024:
        raise ValidationError("Images must be 5 MB or smaller.")


IMAGE_VALIDATORS = [FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_image_size]


class SiteSettings(models.Model):
    company_name = models.CharField(max_length=140, default="SG AllClean")
    tagline = models.CharField(max_length=220)
    hero_title = models.CharField(max_length=220)
    hero_subtitle = models.TextField()
    intro_title = models.CharField(max_length=220)
    intro_body = models.TextField()
    contact_email = models.EmailField(blank=True, help_text="Hidden until PUBLIC_EMAIL_VERIFIED=true in .env.")
    contact_phone = models.CharField(max_length=80)
    location = models.CharField(max_length=140)
    coverage = models.CharField(max_length=220)
    investment_note = models.TextField(blank=True, help_text="Legacy internal note; never displayed publicly.")
    logo_path = models.CharField(max_length=240, blank=True, validators=[validate_internal_path])
    logo = models.ImageField(upload_to="logos/", blank=True, validators=IMAGE_VALIDATORS)

    @property
    def logo_url(self):
        return self.logo.url if self.logo else self.logo_path

    class Meta:
        verbose_name_plural = "site settings"

    def __str__(self):
        return self.company_name


class Page(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=180)
    subtitle = models.CharField(max_length=220, blank=True)
    body = models.TextField(help_text="Separate sections with a blank line. For FAQ/process/add-ons, use the first line as the heading.")
    cta_text = models.CharField(max_length=80, blank=True)
    cta_link = models.CharField(max_length=180, blank=True, validators=[validate_internal_path])

    def __str__(self):
        return self.slug + " — " + self.title


class Service(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180, unique=True)
    summary = models.CharField(max_length=280)
    details = models.TextField(help_text="Single source for package prices, duration, size limits and inclusions on the homepage, services page and detail page.")
    highlight = models.CharField(max_length=120, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    excerpt = models.CharField(max_length=320)
    body = models.TextField()
    image_path = models.CharField(max_length=240, blank=True)
    image = models.ImageField(upload_to="posts/", blank=True, validators=IMAGE_VALIDATORS)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("published", "Published")], default="draft")
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def image_url(self):
        return self.image.url if self.image else self.image_path

    def __str__(self):
        return self.title


class NavItem(models.Model):
    label = models.CharField(max_length=120)
    path = models.CharField(max_length=180, validators=[validate_internal_path])
    sort_order = models.IntegerField(default=0)
    is_button = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.label


class ContentSnippet(models.Model):
    key = models.CharField(max_length=120, unique=True)
    label = models.CharField(max_length=180)
    value = models.TextField(blank=True)
    group_name = models.CharField(max_length=80, default="homepage")
    input_type = models.CharField(max_length=30, default="textarea")
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return self.label


class ContactField(models.Model):
    """Retained legacy configuration; required quote fields now use a validated form."""
    label = models.CharField(max_length=120)
    name = models.CharField(max_length=120, unique=True)
    field_type = models.CharField(max_length=40, default="text")
    placeholder = models.CharField(max_length=180, blank=True)
    options = models.TextField(blank=True)
    required = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)


class ContentMigration(models.Model):
    name = models.CharField(max_length=100, unique=True)


class Inquiry(models.Model):
    reference = models.CharField(max_length=24, unique=True)
    details = models.JSONField()
    spam_key = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    email_status = models.CharField(max_length=24, default="pending")
    email_attempt_at = models.DateTimeField(null=True, blank=True)
    submission_token = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "quote inquiries"

    def __str__(self):
        return self.reference


class InquiryPhoto(models.Model):
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name="photos")
    data = models.BinaryField()
    expires_at = models.DateTimeField(db_index=True)


class InquiryThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)


class AdminLoginThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
