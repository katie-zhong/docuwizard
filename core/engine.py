"""
engine.py — the rule engine.

A RULE SET is plain JSON: a list of field rules, each naming a rule type, its
anchors, and which uploaded file it applies to. No Python is edited to change
what gets extracted.

THE RULE TYPES
--------------
  between          Everything between two anchors.
                   params: start, end

                   Auto-detects shape. If both anchors sit inside the SAME
                   paragraph or cell, it returns the inline text between them
                   ("Project Title: X  Proposal Number:" -> "X"). If they are
                   further apart, it returns every block in between --
                   paragraphs AND tables -- reproduced verbatim.

                   This absorbs what used to be a separate "range" rule. The two
                   were the same request at different scales; making one rule
                   detect the scale removes a choice the user shouldn't have to
                   reason about.

  right_of         The table cell immediately to the right of a label cell.
                   params: label
                   Tables only, by definition of what it does.

  around_keywords  The paragraph OR table containing a word or phrase.
                   params: keyword, before, after

                   Auto-detects location. If the keyword is found inside a
                   table, that whole table is returned (the neighbour counts are
                   ignored, because half a table is not useful). If it is found
                   in a paragraph, that paragraph is returned plus the requested
                   number of neighbouring paragraphs.

  table_contains   The entire table containing a phrase.
                   params: contains
                   Kept for spreadsheets, where a sheet IS the table.

  sheet_cell       One spreadsheet cell, or a rectangular range.
                   params: sheet, cell   ("P10" or "P10:R14")

FAIL LOUDLY
-----------
A rule that finds nothing produces found=False. It never guesses and never
silently blanks a value. The renderers turn that into a red flag plus a
top-of-report "Things to check" list.
"""

from . import normalize as nz

# Older saved rulesets may still say "around_keyword" or "range". They are
# migrated on load so existing files keep working.
LEGACY_TYPES = {"around_keyword": "around_keywords", "range": "between"}


def migrate_type(t):
    return LEGACY_TYPES.get(t, t)


def _rec(name, value, kind, citation, found, note=None, rule_type=None):
    """One field result in a consistent shape, consumed by every renderer."""
    return {"name": name, "value": value, "kind": kind, "citation": citation,
            "found": found, "note": note, "rule_type": rule_type}


def _full_text(blocks):
    """All text in reading order, tables included, for text-scanning rules."""
    lines = []
    for b in blocks:
        if b["type"] == "paragraph":
            if b["text"].strip():
                lines.append(b["text"])
        else:
            for row in b["rows"]:
                for cell in row:
                    if cell.strip():
                        lines.append(cell)
    return "\n".join(lines)


def _locate(blocks, needle):
    """Location label of the first block containing `needle` (for citations)."""
    for b in blocks:
        hay = b["text"] if b["type"] == "paragraph" else " ".join(
            c for row in b["rows"] for c in row)
        if nz.matches(hay, needle):
            return b["location"]
    return None


def _unit_texts(blocks):
    """Every individually-addressable text unit: paragraphs and single cells.

    Used to decide whether two anchors live in the SAME unit (inline case) or
    are spread across the document (block-range case).
    """
    out = []
    for b in blocks:
        if b["type"] == "paragraph":
            out.append(b["text"])
        else:
            for row in b["rows"]:
                out.extend(row)
    return out


# --------------------------------------------------------------------------
# Rule implementations. Each returns (value, kind, location, note).
# kind tells the renderer how to draw it: "text" | "block" | "table".
# --------------------------------------------------------------------------

def _rule_between(blocks, p):
    """
    Inline if both anchors share one paragraph/cell; otherwise a verbatim block
    range. This is the merged between+range behaviour.
    """
    start, end = p.get("start", ""), p.get("end", "")
    if not start:
        return None, "text", None, None

    # --- case 1: both anchors inside a single paragraph or cell -> inline text
    for unit in _unit_texts(blocks):
        if nz.matches(unit, start) and (not end or nz.matches(unit, end)):
            v = nz.text_between(unit, start, end) if end else None
            if v:
                return v, "text", _locate(blocks, start), None

    # --- case 2: spread across the document -> verbatim blocks in between
    collected, capturing, started = [], False, False
    for b in blocks:
        if b["type"] == "paragraph":
            if not capturing:
                if nz.matches(b["text"], start):
                    capturing = started = True
                    continue          # skip the anchor line itself
            else:
                if end and nz.matches(b["text"], end):
                    break
                collected.append(b)
        elif capturing:
            collected.append(b)

    if started and collected:
        return collected, "block", _locate(blocks, start), None

    # --- case 3: last resort, scan the flattened text
    v = nz.text_between(_full_text(blocks), start, end) if end else None
    if v:
        return v, "text", _locate(blocks, start), None
    return None, "text", None, None


def _rule_right_of(blocks, p):
    """The cell to the right of a label cell. Tables only."""
    label = p.get("label", "")
    for b in blocks:
        if b["type"] != "table":
            continue
        for row in b["rows"]:
            for i, cell in enumerate(row):
                if nz.matches(cell, label):
                    # Layout A: value is the next non-empty cell to the right.
                    for j in range(i + 1, len(row)):
                        if row[j].strip():
                            return row[j].strip(), "text", b["location"], None
                    # Layout B: label and value share one cell.
                    same = nz.after_label(cell, label)
                    if same:
                        return same, "text", b["location"], None
                    return "", "text", b["location"], None
    return None, "text", None, None


def _rule_around_keywords(blocks, p):
    """
    The paragraph OR table containing a keyword.

    Tables win: if the keyword appears in a table, the whole table is returned,
    because returning "the row containing it" or a fragment loses the context
    that made the table worth extracting.
    """
    kw = p.get("keyword", "")
    if not kw:
        return None, "block", None, None
    before = int(p.get("before", 0) or 0)
    after = int(p.get("after", 0) or 0)

    # Tables first.
    for b in blocks:
        if b["type"] == "table":
            flat = " ".join(c for row in b["rows"] for c in row)
            if nz.matches(flat, kw):
                return b, "table", b["location"], None

    # Then paragraphs, with neighbours.
    paras = [b for b in blocks if b["type"] == "paragraph" and b["text"].strip()]
    for i, b in enumerate(paras):
        if nz.matches(b["text"], kw):
            lo, hi = max(0, i - before), min(len(paras), i + after + 1)
            return paras[lo:hi], "block", b["location"], None
    return None, "block", None, None


def _rule_table_contains(blocks, p):
    needle = p.get("contains", "")
    for b in blocks:
        if b["type"] == "table":
            flat = " ".join(c for row in b["rows"] for c in row)
            if nz.matches(flat, needle):
                return b, "table", b["location"], None
    return None, "table", None, None


def _rule_sheet_cell(reader, p):
    """One cell, or a rectangular range like P10:R14."""
    if not hasattr(reader, "cell"):
        return None, "text", None, "This rule only applies to spreadsheet files."
    sheet, ref = p.get("sheet", ""), (p.get("cell", "") or "").strip()

    if ":" in ref:
        if not hasattr(reader, "cell_range"):
            return None, "text", None, "Ranges are not supported for this file."
        rows, problem = reader.cell_range(sheet, ref)
        if problem:
            return None, "table", f"{sheet}!{ref}", problem
        return {"rows": rows, "location": sheet}, "table", f"{sheet}!{ref}", None

    value, problem = reader.cell(sheet, ref)
    return value, "text", f"{sheet}!{ref}", problem


RULE_TYPES = ["between", "right_of", "around_keywords",
              "table_contains", "sheet_cell"]

# Which methods make sense for which file type. Enforced in the UI and
# documented in the README, so a user is never offered a rule that cannot work.
METHODS_BY_EXT = {
    ".docx": ["between", "right_of", "around_keywords"],
    ".pdf":  ["between", "right_of", "around_keywords"],
    ".pptx": ["between", "right_of", "around_keywords"],
    ".xlsx": ["sheet_cell", "around_keywords", "table_contains"],
    ".xlsm": ["sheet_cell", "around_keywords", "table_contains"],
}

# One-line description of each rule, shown in the UI beside the chosen method.
RULE_HELP = {
    "between": "Everything between two anchors. Returns plain text if both "
               "anchors are in the same line, or the whole span (tables "
               "included) if they are further apart.",
    "right_of": "The table cell immediately to the right of a label cell. "
                "Works inside tables only.",
    "around_keywords": "The paragraph or table containing a word or phrase. "
                       "If the keyword is in a table, the whole table is "
                       "returned.",
    "table_contains": "The entire table containing a phrase.",
    "sheet_cell": "One spreadsheet cell, or a range of cells.",
}


def apply_rule(rule, reader, blocks, file_label):
    """
    Run one field rule and return a result record.

    `file_label` is the human name of the file it ran against; it is prefixed to
    the location so a citation reads like:
        "Application.docx — §B.4 Project Team"
    """
    name = rule.get("name", "Untitled field")
    rtype = migrate_type(rule.get("type", ""))
    p = rule.get("params", {}) or {}
    note = None

    try:
        if rtype == "between":
            value, kind, loc, note = _rule_between(blocks, p)
        elif rtype == "right_of":
            value, kind, loc, note = _rule_right_of(blocks, p)
        elif rtype == "around_keywords":
            value, kind, loc, note = _rule_around_keywords(blocks, p)
        elif rtype == "table_contains":
            value, kind, loc, note = _rule_table_contains(blocks, p)
        elif rtype == "sheet_cell":
            value, kind, loc, note = _rule_sheet_cell(reader, p)
        else:
            return _rec(name, None, "text", file_label, False,
                        f"Unknown rule type '{rtype}'.", rtype)
    except Exception as exc:
        # A single bad rule must never take down the whole run.
        return _rec(name, None, "text", file_label, False,
                    f"This rule could not run: {exc}", rtype)

    found = value is not None and value != "" and value != []

    if not found and rule.get("default"):
        return _rec(name, rule["default"], "text",
                    f"{file_label} — not found, default used", True,
                    "Nothing found; the rule's default value was used.", rtype)

    citation = f"{file_label} — {loc}" if (found and loc) else file_label
    return _rec(name, value if found else None, kind, citation, found, note, rtype)
