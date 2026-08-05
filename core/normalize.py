"""
normalize.py — forgiving text matching.

Real documents contain typographic noise that is invisible to the eye but fatal
to exact string comparison: en-dashes vs hyphens, curly vs straight quotes,
non-breaking spaces, trailing asterisks on headings, inconsistent capitals.

Every anchor comparison in the rule engine runs through normalize() first, so a
rule typed in plain readable form still matches messy real text. This is carried
over unchanged from V1, where it was the difference between rules "usually
working" and rules working reliably.
"""

import re
import unicodedata

_DASHES = {c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"}
_QUOTES = {**{c: "'" for c in "\u2018\u2019\u201A\u201B"},
           **{c: '"' for c in "\u201C\u201D\u201E\u00AB\u00BB"}}


def normalize(text):
    """Lower-case, ASCII-fold dashes/quotes, drop trailing '*', collapse spaces."""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = "".join(_DASHES.get(ch, ch) for ch in text)
    text = "".join(_QUOTES.get(ch, ch) for ch in text)
    text = text.replace("\u00A0", " ").replace("\u2007", " ").replace("\u202F", " ")
    text = text.lower().rstrip()
    if text.endswith("*"):
        text = text[:-1]
    return re.sub(r"\s+", " ", text).strip()


def matches(haystack, needle):
    """True if `needle` appears inside `haystack`, compared in normalized form."""
    if not needle:
        return False
    return normalize(needle) in normalize(haystack)


def loose_pattern(anchor):
    """A regex that finds `anchor` in original text despite dash/quote/space drift."""
    parts = []
    for ch in anchor.strip():
        if ch.isspace():
            parts.append(r"\s+")
        elif ch in "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212":
            parts.append(r"[-\u2010-\u2015\u2212]")
        elif ch in "\"\u201C\u201D\u00AB\u00BB":
            parts.append(r"[\"\u201C\u201D\u00AB\u00BB]")
        elif ch in "'\u2018\u2019\u201A\u201B":
            parts.append(r"['\u2018\u2019\u201A\u201B]")
        else:
            parts.append(re.escape(ch))
    return "".join(parts) + r"\*?"


def text_between(full_text, start_anchor, end_anchor):
    """Return the natural-looking text between two anchors, or None if not found."""
    m = re.search(loose_pattern(start_anchor) + r"(.*?)" + loose_pattern(end_anchor),
                  full_text, flags=re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def after_label(text, label):
    """If a value sits in the same cell/line as its label, return the trailing part."""
    m = re.search(loose_pattern(label), text, flags=re.IGNORECASE)
    if not m:
        return None
    tail = text[m.end():].strip(" :\t\r\n")
    return tail or None
