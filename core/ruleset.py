"""
ruleset.py — saved rule sets and output templates.

A RULE SET is a named JSON file:

    {
      "name": "Grant intake",
      "fields": [
        {"name": "Project Title", "type": "between",
         "match": "application",
         "params": {"start": "Project Title:", "end": "Proposal Number:"}}
      ]
    }

"match" is a filename substring: the field runs against the uploaded file whose
name contains that text (case-insensitive). Leave it blank and the field runs
against every uploaded file, taking the first hit. That single mechanism covers
both "general rules" and "per-file rules" without needing two concepts.

An OUTPUT TEMPLATE is also JSON: a title plus an ordered list of sections, each
either a heading or a field reference. Templates are deliberately explicit
rather than inferred from an example document - inferring structure from a
sample is an AI capability and is deferred to the AI-enhanced phase.

Everything is stored as plain files under workspace/ so a rule set can be
copied, diffed, version-controlled, or emailed to a colleague.
"""

import json
import os
import re

# Where saved rulesets, templates, uploads and runs live.
#
# When running normally this is the "workspace" folder beside app.py. When
# packaged with PyInstaller the code is unpacked into a TEMPORARY folder that is
# deleted on exit, so the workspace must instead sit next to the executable -
# otherwise everything the user saves would vanish when they close the program.
import sys

if getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(sys.executable)
else:
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORKSPACE = os.environ.get("DOCUWIZARD_WORKSPACE") or os.path.join(_ROOT, "workspace")
RULESETS_DIR = os.path.join(WORKSPACE, "rulesets")
TEMPLATES_DIR = os.path.join(WORKSPACE, "templates")
RUNS_DIR = os.path.join(WORKSPACE, "runs")

for d in (RULESETS_DIR, TEMPLATES_DIR, RUNS_DIR):
    os.makedirs(d, exist_ok=True)


def _safe(name):
    """Turn a display name into a safe filename stem."""
    stem = re.sub(r"[^A-Za-z0-9 _-]", "", str(name)).strip() or "untitled"
    return stem[:80]


# --------------------------------------------------------------------------
# Rule sets
# --------------------------------------------------------------------------

def list_rulesets():
    out = []
    for f in sorted(os.listdir(RULESETS_DIR)):
        if f.endswith(".json"):
            try:
                with open(os.path.join(RULESETS_DIR, f), encoding="utf-8") as fh:
                    data = json.load(fh)
                out.append({"id": f[:-5], "name": data.get("name", f[:-5]),
                            "fields": len(data.get("fields", []))})
            except Exception:
                continue
    return out


def load_ruleset(rid):
    path = os.path.join(RULESETS_DIR, f"{_safe(rid)}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_ruleset(data):
    rid = _safe(data.get("name", "untitled"))
    data["name"] = data.get("name", rid)
    with open(os.path.join(RULESETS_DIR, f"{rid}.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return rid


def delete_ruleset(rid):
    path = os.path.join(RULESETS_DIR, f"{_safe(rid)}.json")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


# --------------------------------------------------------------------------
# Output templates
# --------------------------------------------------------------------------

def list_templates():
    out = []
    for f in sorted(os.listdir(TEMPLATES_DIR)):
        if f.endswith(".json"):
            try:
                with open(os.path.join(TEMPLATES_DIR, f), encoding="utf-8") as fh:
                    data = json.load(fh)
                out.append({"id": f[:-5], "name": data.get("name", f[:-5]),
                            "sections": len(data.get("sections", []))})
            except Exception:
                continue
    return out


def load_template(tid):
    path = os.path.join(TEMPLATES_DIR, f"{_safe(tid)}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_template(data):
    tid = _safe(data.get("name", "untitled"))
    data["name"] = data.get("name", tid)
    with open(os.path.join(TEMPLATES_DIR, f"{tid}.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return tid


def delete_template(tid):
    path = os.path.join(TEMPLATES_DIR, f"{_safe(tid)}.json")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


# --------------------------------------------------------------------------
# Starter content, written on first launch so the tool is never empty.
# This reproduces the V1 grant-intake rules as a worked example.
# --------------------------------------------------------------------------

STARTER_RULESET = {
    "name": "Grant intake (example)",
    "description": "The original eight-field grant intake, as a worked example.",
    "fields": [
        {"name": "Project Title", "type": "between", "match": "application",
         "params": {"start": "Project Title:", "end": "Proposal Number:"}},
        {"name": "Recipient Organization", "type": "right_of", "match": "application",
         "params": {"label": "Organization – legal name: (“The Applicant”)"}},
        {"name": "Project Summary", "type": "right_of", "match": "application",
         "params": {"label": "Project Summary"}},
        {"name": "Recipient Total Project Costs ($)", "type": "right_of",
         "match": "application",
         "params": {"label": "Total Project Cost (including ineligible and In-Kind)"}},
        {"name": "Project Team", "type": "range", "match": "application",
         "params": {"start": "B.4 Project Team",
                    "end": "B.5 Project Budget Information"}},
        {"name": "Recommended Funding ($)", "type": "sheet_cell", "match": "budget",
         "params": {"sheet": "Budget Summary", "cell": "P10"}},
        {"name": "Other Collaborators", "type": "range", "match": "agreement",
         "default": "N/A",
         "params": {"start": "Other Recognized Project Collaborators",
                    "end": "A.3 Activities & Milestones (Project Schedule)"}},
        {"name": "CHEESEMAKER Collaborative Value", "type": "table_contains",
         "match": "agreement",
         "params": {"contains": "Total CHEESEMAKER Collaborative Value ($)"}},
    ],
}

STARTER_TEMPLATE = {
    "name": "Standard summary",
    "title": "Project Intake Summary",
    "sections": [
        {"type": "heading", "text": "Project"},
        {"type": "field", "field": "Project Title"},
        {"type": "field", "field": "Recipient Organization"},
        {"type": "field", "field": "Project Summary"},
        {"type": "heading", "text": "Budget"},
        {"type": "field", "field": "Recipient Total Project Costs ($)"},
        {"type": "field", "field": "Recommended Funding ($)"},
        {"type": "field", "field": "CHEESEMAKER Collaborative Value"},
        {"type": "heading", "text": "People"},
        {"type": "field", "field": "Project Team"},
        {"type": "field", "field": "Other Collaborators"},
    ],
}


def ensure_starters():
    """Write the example rule set/template once, if the workspace is empty."""
    if not list_rulesets():
        save_ruleset(dict(STARTER_RULESET))
    if not list_templates():
        save_template(dict(STARTER_TEMPLATE))
