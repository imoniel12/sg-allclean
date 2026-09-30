import json
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.utils import timezone

from website import models as target
from website.content import apply_client_brief, setup_editor_group


class Command(BaseCommand):
    help = "Read the original FastAPI SQLite database and copy content/accounts into Django. Never modifies the source."

    def add_arguments(self, parser):
        parser.add_argument("source", nargs="?", default=str(settings.BASE_DIR / "sg_allclean.db"))

    @transaction.atomic
    def handle(self, *args, **options):
        marker = "legacy-sqlite-import-v1"
        if target.ContentMigration.objects.filter(name=marker).exists():
            self.stdout.write("Already imported; no data changed.")
            return
        if target.SiteSettings.objects.exists() or target.Service.objects.exists():
            raise CommandError("Import requires an empty Django content database. Import before bootstrap_site; existing content is not overwritten.")
        source = Path(options["source"]).resolve()
        if not source.is_file():
            raise CommandError("Source SQLite file does not exist.")
        if source == Path(settings.DATABASES["default"]["NAME"]).resolve():
            raise CommandError("Source must be different from the Django database.")
        connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        copied = 0
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            mapping = {"site_settings": target.SiteSettings, "page": target.Page, "service": target.Service, "post": target.Post, "nav_item": target.NavItem, "content_snippet": target.ContentSnippet, "contact_field": target.ContactField, "inquiry": target.Inquiry, "inquiry_photo": target.InquiryPhoto}
            for table, model in mapping.items():
                if table not in tables:
                    continue
                for row in connection.execute('SELECT * FROM "' + table + '"'):
                    original = dict(row)
                    values = {}
                    for field in model._meta.fields:
                        key = field.attname
                        if key not in original:
                            continue
                        value = original[key]
                        if isinstance(field, models.BooleanField):
                            value = str(value).lower() in {"true", "1"}
                        elif isinstance(field, models.JSONField) and isinstance(value, str):
                            value = json.loads(value)
                        elif isinstance(field, models.DateTimeField) and value:
                            value = datetime.fromisoformat(value)
                            if timezone.is_naive(value):
                                from datetime import UTC
                                value = value.replace(tzinfo=UTC)
                        values[key] = value
                    if model is target.Inquiry:
                        values.setdefault("submission_token", secrets.token_hex(32))
                    model.objects.create(**values)
                    copied += 1
            editors = setup_editor_group()
            if "admin_user" in tables:
                for row in connection.execute("SELECT * FROM admin_user"):
                    data = dict(row)
                    if get_user_model().objects.filter(username=data["username"]).exists():
                        raise CommandError("A matching Django username already exists. Import before creating accounts.")
                    user = get_user_model().objects.create(username=data["username"], password="werkzeug$" + data["password_hash"], is_staff=True, is_superuser=data.get("role", "full_admin") == "full_admin", is_active=str(data.get("is_active", "true")).lower() == "true")
                    if not user.is_superuser:
                        user.groups.add(editors)
            apply_client_brief()
            target.ContentMigration.objects.create(name=marker)
        finally:
            connection.close()
        self.stdout.write(self.style.SUCCESS(f"Imported {copied} content/inquiry rows and existing admin accounts. Original database unchanged; client brief applied."))
