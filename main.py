"""Local development entry point: python main.py."""
import os
import sys
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    execute_from_command_line([sys.argv[0], "runserver", os.environ.get("HOST", "127.0.0.1") + ":" + os.environ.get("PORT", "8000")])
