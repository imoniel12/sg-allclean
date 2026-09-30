from django.contrib.auth.models import Group, Permission
from django.db import transaction
import brief_content as brief
from .models import ContentMigration, ContentSnippet, NavItem, Page, Post, Service, SiteSettings


@transaction.atomic
def apply_client_brief():
    key = "django-client-brief-v1"
    if ContentMigration.objects.filter(name=key).exists():
        return False
    site = SiteSettings.objects.first() or SiteSettings()
    for name, value in brief.SETTINGS.items():
        setattr(site, name, value)
    site.save()
    for data in brief.SERVICES:
        Service.objects.update_or_create(slug=data["slug"], defaults={key: value for key, value in data.items() if key != "slug"})
    for slug, (title, subtitle, body) in brief.PAGES.items():
        Page.objects.update_or_create(slug=slug, defaults={"title": title, "subtitle": subtitle, "body": body, "cta_text": "Request a Quote", "cta_link": "/contact"})
    Page.objects.get_or_create(slug="privacy", defaults={"title": "Data Privacy Statement", "subtitle": "How we handle inquiry details and service coordination.", "body": "SG AllClean collects the details needed to prepare quotes, communicate with you and coordinate cleaning services. Access is restricted to authorized administrators.\n\nWe do not publish your inquiry or property photos. Contact us using the phone number below for privacy questions, corrections or deletion requests."})
    NavItem.objects.filter(path__in=["/", "/about", "/services", "/journal", "/contact", "/faq", "/how-it-works"]).update(is_active=False)
    for order, (label, path, button) in enumerate(brief.NAVIGATION, 1):
        NavItem.objects.create(label=label, path=path, sort_order=order, is_button=button, is_active=True)
    for key_name, value in brief.SNIPPETS.items():
        ContentSnippet.objects.update_or_create(key=key_name, defaults={"label": key_name.replace('.', ' ').replace('_', ' ').title(), "value": value, "group_name": "footer" if key_name.startswith("footer.") else "homepage"})
    Post.objects.filter(title="Why Premium Cleaning Wins in Urban Properties", body__contains="That is where SG AllClean is positioned: premium, recurring, and detail-led.").update(status="draft")
    ContentMigration.objects.create(name=key)
    return True


def setup_editor_group():
    group, _ = Group.objects.get_or_create(name="Content moderators")
    group.permissions.set(Permission.objects.filter(content_type__app_label="website", content_type__model__in=["page", "service", "post", "contentsnippet"], codename__regex=r"^(add|change|view)_"))
    return group
