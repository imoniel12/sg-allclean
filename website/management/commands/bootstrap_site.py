from django.core.management.base import BaseCommand
from website.content import apply_client_brief, setup_editor_group


class Command(BaseCommand):
    help = "Initialize the client brief once. Later CMS edits are preserved."

    def handle(self, *args, **options):
        updated = apply_client_brief()
        setup_editor_group()
        self.stdout.write(self.style.SUCCESS("Client brief applied." if updated else "Already initialized; CMS edits preserved."))
