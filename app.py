"""
app.py — the local web server.

WHY A BROWSER UI AND NOT A HOSTED SITE
--------------------------------------
This binds to 127.0.0.1 (loopback) only. That address is not reachable from any
other machine - not from the network, not from the internet - so "web UI" here
means "a local window that happens to be rendered by the browser you already
have installed". Files are read from and written to this machine only. Nothing
is uploaded anywhere. This keeps the on-device guarantee intact while allowing a
real rule-builder interface, which a plain desktop dialog toolkit cannot
practically provide.

Run it with:   python app.py
It opens http://127.0.0.1:8765 in the default browser.
"""

import os
import shutil
import threading
import webbrowser

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import uvicorn

from core import pipeline, readers, ruleset, sources
from core.engine import RULE_TYPES

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
UPLOADS = os.path.join(ruleset.WORKSPACE, "uploads")
os.makedirs(UPLOADS, exist_ok=True)

app = FastAPI(title="Document Extractor")
ruleset.ensure_starters()

# The most recent run, so the download endpoints can find output files.
LAST = {"run": None}


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as fh:
        return fh.read()


@app.get("/api/meta")
def meta():
    """Everything the UI needs to draw itself."""
    return {"rule_types": RULE_TYPES,
            "supported": readers.SUPPORTED,
            "rulesets": ruleset.list_rulesets(),
            "templates": ruleset.list_templates()}


# ---------------------------------------------------------------- rule sets
@app.get("/api/rulesets/{rid}")
def get_ruleset(rid: str):
    data = ruleset.load_ruleset(rid)
    if data is None:
        raise HTTPException(404, "Rule set not found")
    return data


@app.post("/api/rulesets")
async def post_ruleset(payload: dict):
    rid = ruleset.save_ruleset(payload)
    return {"id": rid, "rulesets": ruleset.list_rulesets()}


@app.delete("/api/rulesets/{rid}")
def del_ruleset(rid: str):
    ruleset.delete_ruleset(rid)
    return {"rulesets": ruleset.list_rulesets()}


# ---------------------------------------------------------------- templates
@app.get("/api/templates/{tid}")
def get_template(tid: str):
    data = ruleset.load_template(tid)
    if data is None:
        raise HTTPException(404, "Template not found")
    return data


@app.post("/api/templates")
async def post_template(payload: dict):
    tid = ruleset.save_template(payload)
    return {"id": tid, "templates": ruleset.list_templates()}


@app.delete("/api/templates/{tid}")
def del_template(tid: str):
    ruleset.delete_template(tid)
    return {"templates": ruleset.list_templates()}


# ------------------------------------------------------------------- upload
@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    """Write uploaded files into a fresh folder on this machine."""
    shutil.rmtree(UPLOADS, ignore_errors=True)
    os.makedirs(UPLOADS, exist_ok=True)
    saved = []
    for f in files:
        name = os.path.basename(f.filename or "unnamed")
        dest = os.path.join(UPLOADS, name)
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        ext = os.path.splitext(name)[1].lower()
        saved.append({"label": name, "size": os.path.getsize(dest),
                      "supported": ext in readers.SUPPORTED,
                      "ext": ext})
    return {"files": saved}


@app.get("/api/uploaded")
def uploaded():
    return {"files": sources.LocalUpload(UPLOADS).collect()}


# ---------------------------------------------------------------------- run
@app.post("/api/run")
async def run_extraction(payload: dict):
    rs = ruleset.load_ruleset(payload.get("ruleset", ""))
    if rs is None:
        raise HTTPException(400, "Choose a rule set first.")
    tpl = ruleset.load_template(payload.get("template", "")) or {}
    formats = payload.get("formats") or ["docx"]

    files = sources.LocalUpload(UPLOADS).collect()
    if not files:
        raise HTTPException(400, "Add at least one file first.")

    log_lines = []
    result = pipeline.run(files, rs, tpl, formats, log=log_lines.append)
    LAST["run"] = result

    return JSONResponse({
        "ok": True,
        "log": log_lines,
        "warnings": result["warnings"],
        "missing": result["missing"],
        "outputs": [{"format": o["format"], "name": o["name"]}
                    for o in result["outputs"]],
        "fields": [{"name": r["name"], "found": r["found"],
                    "citation": r["citation"], "note": r.get("note"),
                    "preview": _preview(r)} for r in result["records"]],
    })


def _preview(rec):
    """A short, plain-text glimpse of a value for the results table."""
    if not rec["found"]:
        return ""
    v = rec["value"]
    if rec["kind"] == "text":
        s = str(v)
    elif rec["kind"] == "table":
        s = " / ".join(c for c in (v.get("rows") or [[]])[0])
    else:
        parts = []
        for b in v[:3]:
            parts.append(b["text"] if b["type"] == "paragraph"
                         else f"[table {len(b['rows'])} rows]")
        s = " ".join(parts)
    s = " ".join(s.split())
    return s[:160] + ("…" if len(s) > 160 else "")


@app.get("/api/download/{fmt}")
def download(fmt: str):
    run = LAST.get("run")
    if not run:
        raise HTTPException(404, "Nothing has been extracted yet.")
    for o in run["outputs"]:
        if o["format"] == fmt:
            return FileResponse(o["path"], filename=o["name"])
    raise HTTPException(404, "That format was not produced in the last run.")


def main():
    url = "http://127.0.0.1:8765"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Document Extractor running at {url}  (local only — press Ctrl+C to stop)")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


if __name__ == "__main__":
    main()
