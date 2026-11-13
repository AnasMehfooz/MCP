"""URL slugs, used for product handles."""

from __future__ import annotations

import re
import unicodedata

# NFKD alone would turn "ö" into "o"; German spelling expects "oe".
_GERMAN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def slugify(text: str, *, fallback: str, max_length: int = 80) -> str:
    """'Bio T-Shirt (Größe M)' -> 'bio-t-shirt-groesse-m'. Returns `fallback` if nothing is left."""
    ascii_text = unicodedata.normalize("NFKD", text.translate(_GERMAN)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:max_length].rstrip("-") or fallback
