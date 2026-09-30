from django.core.management.base import BaseCommand
from website.inquiry_service import purge_expired_photos


class Command(BaseCommand):
    help = "Delete expired private inquiry photos. Run daily as a scheduled task."

    def handle(self, *args, **options):
        self.stdout.write(f"Deleted {purge_expired_photos()} expired photo(s).")
