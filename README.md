# Document Extractor (V2)

A **local, on-device** tool for pulling specific content out of documents and
assembling it into a formatted summary with a source citation for every field.

Rule-based, not AI. No internet, no model, no external API calls. The web
interface binds to `127.0.0.1` — a loopback address that is not reachable from
any other machine — so "web UI" here means a local window rendered by the
browser you already have. Files never leave the device.

---

## Setup

Once per machine:

```
pip install fastapi uvicorn python-multipart python-docx openpyxl pdfplumber python-pptx reportlab
```

Then run:

```
python app.py
```

It opens `http://127.0.0.1:8765` in your browser. On Windows you can
double-click `run.bat` instead. Press Ctrl+C in the console window to stop.

---

## Using it

**Extract tab** — drop in files, pick a rule set and an output template, choose
formats, click **Extract**. Results appear as a table: what was found, and where
it came from. Anything not found is red and listed at the top. Download the
output as `.docx`, `.md`, `.pdf`, or all three.

**Rules tab** — build the rule set. Each field has a name, a rule type, an
"applies to" (part of a file name), and the anchors that rule needs. Save it and
it's reusable.

**Output tab** — build the report layout: an ordered list of headings and
fields. Any field in the rule set that isn't placed in the template still
appears, appended at the end, so adding a rule never makes its output vanish.

Rule sets and templates are plain JSON under `workspace/`, so they can be
copied, diffed, or shared.

---

## Reads

| Format | Citations look like | Notes |
|---|---|---|
| `.docx` | `§B.4 Project Team` | Real table structure — cell rules are exact |
| `.xlsx` / `.xlsm` | `Budget Summary!P10` | Exact cell addressing |
| `.pptx` | `Slide 7` | Includes speaker notes |
| `.pdf` | `p. 4` | **Least reliable** — see below |

Word has no stored page concept (pagination is computed at render time), so
`.docx` citations reference the nearest heading. That's more useful anyway: a
reviewer can Ctrl+F an anchor, whereas a page number in a 40-page document can
drift.

PDF has no native concept of a table — tables are *inferred* from ruled lines
and alignment, so cell-based rules are meaningfully less dependable on PDF than
on Word or Excel. Prefer the original `.docx`/`.xlsx` when you have it.

Legacy `.doc` cannot be read. Open in Word → **Save As → Word Document (.docx)**.

---

## Rule types

| Type | Finds | Needs |
|---|---|---|
| `between` | Text between two labels | start, end |
| `right_of` | The table cell right of a label | label |
| `range` | A whole section between two headings, verbatim | start, end |
| `around_keyword` | The paragraph containing a keyword, plus neighbours | keyword, before, after |
| `table_contains` | The entire table containing a phrase | contains |
| `sheet_cell` | One exact spreadsheet cell | sheet, cell |

Any rule can set a **default** (e.g. `N/A`) for a field that is legitimately
sometimes absent. Without a default, a miss is flagged.

**Anchors are matched loosely.** Capitals, en-dashes vs hyphens, curly vs
straight quotes, non-breaking spaces, a trailing `*`, and extra whitespace are
all forgiven. Type the anchor the way it reads in the document.

---

## Two properties that are not negotiable

**Fail loudly.** A rule that finds nothing produces a visible red flag and an
entry in the "Things to check" box at the top of every output. The tool never
guesses and never silently blanks a field. It assists review; it does not
replace it.

**Every field is cited.** Each value carries the file it came from and the
location within it, so a reviewer can always verify against the source.

---

## Versioning

Each run writes to `workspace/runs/<timestamp>/` containing the outputs and a
`manifest.json` recording the rule set, template, per-field results, and a
SHA-256 fingerprint of every input file. Content hashing is used rather than
timestamps because copies and syncs change modification times without changing
content.

---

## Architecture: what's built for later

Two seams exist and are deliberately unimplemented.

**`core/sources.py` — where files come from.** The pipeline only ever sees "a
list of files", so the source is swappable:

- `LocalUpload` — **built.** Browser upload.
- `SyncedFolder` — designed. Reads a SharePoint library synced by the OneDrive
  client ("Add shortcut to OneDrive"). The preferred next step, because the tool
  still makes no network calls — the Microsoft-sanctioned sync client does the
  transport, so the on-device guarantee survives. Implementing it is close to
  "point at a path".
- `GraphSource` — designed and **not recommended.** A cloud pull via Microsoft
  Graph would need an Entra app registration, admin-consented permissions, and a
  secret stored on a managed laptop, and would break the no-external-calls
  constraint outright. Documented so the decision isn't rediscovered.

**`core/enrich.py` — the AI seam.** Every field result passes through an
enricher before rendering; today it's a pass-through that does nothing. When AI
features arrive they must (a) use a **local** model only, and (b) be
**additive** — a suggestion may be attached to a field, but must never overwrite
an extracted value or citation. A reviewer has to be able to tell mechanical
extraction from model output, or the audit trail that makes this tool
acceptable in a regulated setting is gone.

---

## Known limitations

- **Rules suit stable templates.** Anchor rules are reliable because
  institutional forms are consistent by construction. Pointed at arbitrary
  documents of varying shape, rule maintenance becomes the job — that's the
  known ceiling of this approach, and the reason commercial tools moved to AI.
- **First match wins.** A `range` rule takes the first occurrence of its start
  heading. If a Table of Contents repeats the heading text, the TOC entry could
  be captured instead. Needs a guard once real documents with TOCs are tested.
- **PDF table inference** is approximate (above).
- **Images are not extracted** — text and tables only.
- **Reproduced tables keep values, not formatting**; first row treated as header.
- **No OCR** — scanned/image-only PDFs return nothing.
- **Excel formula cells** only yield a value if Excel saved one; an
  uncalculated cell is reported as such rather than treated as empty.
- **One project at a time** — no batch across many folders yet.

---

## Files

```
app.py               local web server (127.0.0.1 only) + API
static/index.html    the entire frontend, no external assets
core/normalize.py    forgiving anchor matching
core/readers.py      docx / xlsx / pdf / pptx -> one uniform block format
core/engine.py       the six rule types
core/ruleset.py      saved rule sets and templates (JSON)
core/render.py       docx, markdown, pdf renderers
core/pipeline.py     one run end to end + manifest
core/sources.py      file sources (SharePoint seam)
core/enrich.py       AI seam (no-op)
workspace/           rulesets, templates, runs, uploads
```
