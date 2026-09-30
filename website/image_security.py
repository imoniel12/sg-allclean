import io
import secrets
import warnings
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError


def sanitize_public_image(upload, prefix):
    """Decode, resize and re-encode an admin image, stripping metadata/polyglot data."""
    if not upload:
        return upload
    raw = upload.read(5 * 1024 * 1024 + 1)
    upload.seek(0)
    if len(raw) > 5 * 1024 * 1024:
        raise ValidationError("Images must be 5 MB or smaller.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw), formats=["JPEG", "PNG", "WEBP"]) as source:
                if source.width * source.height > 20_000_000:
                    raise ValidationError("Images must be no larger than 20 megapixels.")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((2400, 2400))
                clean = Image.new("RGB", oriented.size, "white")
                if "A" in oriented.getbands():
                    clean.paste(oriented.convert("RGB"), mask=oriented.getchannel("A"))
                else:
                    clean.paste(oriented.convert("RGB"))
                output = io.BytesIO()
                clean.save(output, "WEBP", quality=88, method=6)
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("Upload a valid JPG, PNG or WebP image.") from exc
    name = f"{prefix}-{secrets.token_hex(8)}.webp"
    return ContentFile(output.getvalue(), name=name)
