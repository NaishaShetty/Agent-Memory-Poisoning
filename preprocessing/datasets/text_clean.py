"""Text-level cleaning helpers shared by all dataset parsers.

Only whitespace/encoding normalization is applied here — nothing that
could alter meaning. Every dataset decides for itself, based on its own
inspection results, whether/when to call these.
"""
from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"[ \t ]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def normalize_whitespace(text: str) -> str:
    """Collapse runs of horizontal whitespace and cap blank-line runs.

    Leaves single newlines and leading/trailing structure of the string
    otherwise untouched except for an outer strip.
    """
    text = _WHITESPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def normalize_unicode(text: str) -> str:
    """Apply NFC normalization; does not strip or transliterate content."""
    return unicodedata.normalize("NFC", text)


def is_effectively_empty(text: str) -> bool:
    return text is None or text.strip() == ""


def clean_text(text: str) -> str:
    return normalize_whitespace(normalize_unicode(text))


def has_replacement_char(text: str) -> bool:
    """True if the text contains U+FFFD, the Unicode replacement character.

    This indicates the SOURCE data was already mis-decoded (mojibake)
    before we ever read it — e.g. a curly quote or currency symbol that
    lost its original byte value upstream. We never guess the original
    character; we only detect and flag it (data_quality), so downstream
    consumers know the content is source-corrupted at that point.
    """
    return "�" in text
