from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .admin_forms import PostForm, SiteSettingsForm
from .inquiry_service import mail_ready, purge_expired_photos, send_notification
from .models import ContentSnippet, Inquiry, NavItem, Page, Post, Service, SiteSettings

admin.site.site_header = "SG AllClean"
admin.site.site_title = "SG AllClean Admin"
admin.site.index_title = "Website content and quote inquiries"


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    form = SiteSettingsForm
    exclude = ["investment_note"]

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["title", "highlight", "sort_order"]
    prepopulated_fields = {"slug": ("title",)}
    ordering = ["sort_order"]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["slug", "title"]
    prepopulated_fields = {"slug": ("title",)}

    def get_readonly_fields(self, request, obj=None):
        return ["slug"] if obj and obj.slug in {"about", "privacy", "faq", "how-it-works", "add-ons"} else []

    def has_delete_permission(self, request, obj=None):
        return False  # Required public pages must remain available.


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    form = PostForm
    list_display = ["title", "status", "published_at"]
    list_filter = ["status"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        if obj.status == "published" and not obj.published_at:
            obj.published_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(NavItem)
class NavItemAdmin(admin.ModelAdmin):
    list_display = ["label", "path", "sort_order", "is_button", "is_active"]
    list_editable = ["sort_order", "is_active"]


@admin.register(ContentSnippet)
class SnippetAdmin(admin.ModelAdmin):
    list_display = ["label", "key", "group_name"]
    readonly_fields = ["key"]

    def get_queryset(self, request):
        # Only expose copy actually rendered by the new public templates.
        return super().get_queryset(request).filter(key__in=["home.checklist_title", "home.checklist_body", "footer.badge", "footer.body"])


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ["reference", "customer", "created_at", "email_status"]
    list_filter = ["email_status", "created_at"]
    search_fields = ["reference", "details"]
    readonly_fields = ["reference", "created_at", "email_status", "email_attempt_at", "request_details", "private_photos"]
    fields = readonly_fields
    actions = ["retry_notifications"]
    list_per_page = 25

    def has_add_permission(self, request):
        return False

    @admin.display(description="Customer")
    def customer(self, obj):
        return obj.details.get("name", "")

    @admin.display(description="Request details")
    def request_details(self, obj):
        return format_html("<dl class='inquiry-details'>{}</dl>", format_html_join("", "<dt><strong>{}</strong></dt><dd>{}</dd>", [(key.replace('_', ' ').title(), str(value)) for key, value in obj.details.items() if value]))

    @admin.display(description="Private photos (expire after 30 days)")
    def private_photos(self, obj):
        photos = obj.photos.filter(expires_at__gt=timezone.now()).defer("data")
        return format_html_join(" ", '<a class="inquiry-photo" href="{}" target="_blank" rel="noopener"><img src="{}" alt="Private inquiry photo"></a>', [(reverse("inquiry_photo", args=[photo.pk]), reverse("inquiry_photo", args=[photo.pk])) for photo in photos]) or "No current photos."

    def changelist_view(self, request, extra_context=None):
        purge_expired_photos()
        if not mail_ready():
            self.message_user(request, "Email delivery is not configured. Inquiries remain saved here. Update SMTP placeholders and verify the recipient mailbox before enabling delivery.", messages.WARNING)
        return super().changelist_view(request, extra_context)

    @admin.action(description="Retry email notifications for selected inquiries", permissions=["change"])
    def retry_notifications(self, request, queryset):
        if not mail_ready():
            self.message_user(request, "Configure and verify SMTP and the recipient mailbox first.", messages.ERROR)
            return
        sent = sum(send_notification(pk) for pk in queryset.values_list("pk", flat=True))
        self.message_user(request, f"{sent} notification(s) accepted by the email backend. Check status and verify inbox receipt.")
