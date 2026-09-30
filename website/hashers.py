from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from werkzeug.security import check_password_hash


class LegacyWerkzeugHasher(BasePasswordHasher):
    """Verify imported passwords; Django upgrades them to PBKDF2 on login."""
    algorithm = "werkzeug"

    def verify(self, password, encoded):
        try:
            return check_password_hash(encoded.split("$", 1)[1], password)
        except (ValueError, TypeError):
            return False

    def encode(self, password, salt):
        raise NotImplementedError("New passwords must use Django's default hasher.")

    def safe_summary(self, encoded):
        return {"algorithm": self.algorithm, "hash": mask_hash(encoded)}

    def must_update(self, encoded):
        return True
