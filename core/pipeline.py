"""
pipeline.py — one run, end to end.

    files (from a Source)  ->  match each field rule to a file
                           ->  read that file into blocks
                           ->  apply the rule
                           ->  (enrich: currently a no-op)
                           ->  render docx / md / pdf
                           ->  write manifest with SHA-256 fingerprints

Readers are opened once per file and cached, because a 40-page document should
not be parsed eight times for eight fields.
"""

import datetime
import hashlib
import json
import os

from . import engine, enrich, readers, render
from .ruleset import RUNS_DIR


def sha256(path):
    """Content fingerprint. Used instead of timestamps because copies and syncs
    can change mtime without changing content (and vice versa)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_run_folder():
    base = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(RUNS_DIR, base)
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(RUNS_DIR, f"{base}_{n}")
    os.makedirs(path)
    return path


def _pick_file(files, match):
    """
    Choose which uploaded file a rule runs against.

    A blank `match` means "any file" - the caller then tries each in turn. A
    non-blank match is a case-insensitive filename substring, which tolerates
    real-world naming like 'ABC123 Grant application-final-v2.docx'.
    """
    if not match:
        return files
    m = match.strip().lower()
    return [f for f in files if m in f["label"].lower()]


def run(files, ruleset, template, formats, log=print, enrich_mode="none"):
    """
    Execute one extraction. `files` is [{"label","path"}, ...].
    Returns a result dict describing outputs, records, and warnings.
    """
    warnings = []
    records = []
    cache = {}          # path -> (reader, blocks) so each file is parsed once

    def get_reader(path):
        if path not in cache:
            reader, problem = readers.open_reader(path)
            if reader is None:
                cache[path] = (None, None, problem)
            else:
                try:
                    cache[path] = (reader, reader.blocks(), None)
                except Exception as exc:
                    cache[path] = (None, None, f"Could not read this file: {exc}")
        return cache[path]

    log(f"Reading {len(files)} file(s)...")
    for f in files:
        _, _, problem = get_reader(f["path"])
        if problem:
            warnings.append(f"{f['label']}: {problem}")
            log(f"  ! {f['label']}: {problem}")
        else:
            log(f"  · {f['label']}")

    log("Applying rules...")
    for rule in ruleset.get("fields", []):
        candidates = _pick_file(files, rule.get("match", ""))
        if not candidates:
            records.append(engine._rec(
                rule.get("name", "Untitled"), None, "text",
                f"(no uploaded file matched '{rule.get('match','')}')", False,
                f"No uploaded file name contains '{rule.get('match','')}'.",
                rule.get("type")))
            log(f"  ✗ {rule.get('name')} (no matching file)")
            continue

        best = None
        for cand in candidates:
            reader, blocks, problem = get_reader(cand["path"])
            if reader is None:
                continue
            rec = engine.apply_rule(rule, reader, blocks, cand["label"])
            if rec["found"]:
                best = rec
                break
            if best is None:
                best = rec
        if best is None:
            best = engine._rec(rule.get("name", "Untitled"), None, "text",
                               candidates[0]["label"], False,
                               "The matching file could not be read.",
                               rule.get("type"))
        records.append(best)
        log(f"  {'✓' if best['found'] else '✗'} {best['name']}")

    # AI seam: a pass-through today, always.
    records = enrich.get_enricher(enrich_mode).enrich(records)

    run_folder = make_run_folder()
    meta = {"generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "files": ", ".join(f["label"] for f in files) or "none"}

    outputs = []
    stem = "".join(ch for ch in (template or {}).get("title", "Extraction Summary")
                   if ch.isalnum() or ch in " -_").strip() or "Extraction Summary"
    for fmt in formats:
        fn = render.RENDERERS.get(fmt)
        if not fn:
            continue
        path = os.path.join(run_folder, f"{stem}.{fmt}")
        try:
            fn(records, template, path, meta)
            outputs.append({"format": fmt, "path": path,
                            "name": os.path.basename(path)})
            log(f"  wrote {os.path.basename(path)}")
        except Exception as exc:
            warnings.append(f"Could not write the {fmt} output: {exc}")
            log(f"  ! {fmt} failed: {exc}")

    manifest = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "ruleset": ruleset.get("name"),
        "template": (template or {}).get("name"),
        "enrichment": enrich_mode,
        "warnings": warnings,
        "files": [{"label": f["label"], "sha256": sha256(f["path"])} for f in files],
        "fields": [{"name": r["name"], "rule": r.get("rule_type"),
                    "found": r["found"], "citation": r["citation"]}
                   for r in records],
    }
    with open(os.path.join(run_folder, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    missing = [r["name"] for r in records if not r["found"]]
    return {"ok": True, "run_folder": run_folder, "outputs": outputs,
            "records": records, "warnings": warnings, "missing": missing,
            "manifest": manifest}
