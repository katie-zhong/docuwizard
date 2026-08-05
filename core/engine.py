"""
engine.py — the rule engine.

A RULE SET is plain JSON: a list of field rules, each naming a rule type, its
anchors, and which uploaded file it applies to. No Python is edited to change
what gets extracted - that was V1's biggest maintainability lesson, promoted
here from "config file" to "data the UI edits".

THE SIX RULE TYPES
------------------
  between        text sitting between two labels
                 params: start, end
  right_of       the table cell to the right of a label
                 params: label
  range          a whole section between two headings, reproduced verbatim
                 params: start, end
  around_keyword the paragraph(s) surrounding a keyword
                 params: keyword, before (int), after (int)
  table_contains the entire table containing a phrase
                 params: contains
  sheet_cell     one exact spreadsheet cell
                 params: sheet, cell

Every rule may also set:
  default        value to use when nothing is found, instead of flagging
                 (e.g. "N/A" for a legitimately-absent field)

FAIL LOUDLY
-----------
A rule that finds nothing produces found=False. It never guesses, never
silently blanks. The renderers turn that into a red flag plus a top-of-report
"Things to check" list. This is the core safety property of the tool: a human
reviewer must always be able to see what the machine could not do.
"""

from . import normalize as nz


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
    """The location label of the first block containing `needle` (for citations)."""
    for b in blocks:
        hay = b["text"] if b["type"] == "paragraph" else " ".join(
            c for row in b["rows"] for c in row)
        if nz.matches(hay, needle):
            return b["location"]
    return None


# --------------------------------------------------------------------------
# Rule implementations. Each returns (value, kind, location, note).
# kind tells the renderer how to draw it: "text" | "block" | "table".
# --------------------------------------------------------------------------

def _rule_between(blocks, p):
    v = nz.text_between(_full_text(blocks), p.get("start", ""), p.get("end", ""))
    return v, "text", _locate(blocks, p.get("start", "")), None


def _rule_right_of(blocks, p):
    label = p.get("label", "")
    for b in blocks:
        if b["type"] != "table":
            continue
        for row in b["rows"]:
            for i, cell in enumerate(row):
                if nz.matches(cell, label):
                    # Layout A: the value is the next non-empty cell to the right.
                    for j in range(i + 1, len(row)):
                        if row[j].strip():
                            return row[j].strip(), "text", b["location"], None
                    # Layout B: label and value share one cell ("Total: $1,000").
                    same = nz.after_label(cell, label)
                    if same:
                        return same, "text", b["location"], None
                    return "", "text", b["location"], None
    return None, "text", None, None


def _rule_range(blocks, p):
    """Capture from the start heading up to (not including) the end heading."""
    start, end = p.get("start", ""), p.get("end", "")
    collected, capturing, started = [], False, False
    for b in blocks:
        if b["type"] == "paragraph":
            if not capturing:
                if nz.matches(b["text"], start):
                    capturing = started = True
                    continue          # skip the heading line itself
            else:
                if end and nz.matches(b["text"], end):
                    break
                collected.append(b)
        elif capturing:
            collected.append(b)
    if not started:
        return None, "block", None, None
    loc = _locate(blocks, start)
    return collected, "block", loc, None


def _rule_around_keyword(blocks, p):
    """The paragraph containing a keyword, plus N neighbours either side."""
    kw = p.get("keyword", "")
    before = int(p.get("before", 0) or 0)
    after = int(p.get("after", 0) or 0)
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
    """Spreadsheet-only: read one cell, distinguishing 'empty' from 'uncalculated'."""
    if not hasattr(reader, "cell"):
        return None, "text", None, "This rule only applies to spreadsheet files."
    sheet, ref = p.get("sheet", ""), p.get("cell", "")
    value, problem = reader.cell(sheet, ref)
    return value, "text", f"{sheet}!{ref}", problem


RULE_TYPES = ["between", "right_of", "range", "around_keyword",
              "table_contains", "sheet_cell"]


def apply_rule(rule, reader, blocks, file_label):
    """
    Run one field rule and return a result record.

    `file_label` is the human name of the file it ran against; it is prefixed to
    the location so a citation reads like:
        "Application.docx — §B.4 Project Team"
    """
    name = rule.get("name", "Untitled field")
    rtype = rule.get("type", "")
    p = rule.get("params", {}) or {}
    note = None

    try:
        if rtype == "between":
            value, kind, loc, note = _rule_between(blocks, p)
        elif rtype == "right_of":
            value, kind, loc, note = _rule_right_of(blocks, p)
        elif rtype == "range":
            value, kind, loc, note = _rule_range(blocks, p)
        elif rtype == "around_keyword":
            value, kind, loc, note = _rule_around_keyword(blocks, p)
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
