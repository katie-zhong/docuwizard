# DocuWizard

A **local, on-device** tool for pulling specific content out of documents and
assembling it into a formatted summary with a source citation for every field.

Rule-based, not AI. No internet, no model, no external API calls. The web
interface binds to `127.0.0.1` — a loopback address that is not reachable from
any other machine — so "web UI" here means a local window rendered by the
browser you already have. Files never leave the device.

---

## Setup

### For end users — no Python needed

If you were given the packaged version, there is nothing to install:

1. Unzip the `DocuWizard` folder anywhere (Desktop, Documents, a network drive).
2. Double-click **`DocuWizard.exe`**, or from Command Prompt:
   `cd` into the folder and run `DocuWizard.exe`.
3. Your browser opens at `http://127.0.0.1:8765`. Close the black console
   window to stop it.

A `workspace` folder appears next to the .exe — that's where your files,
rulesets, templates and past runs are saved. Keep it with the program.

### For developers — running from source

```
pip install -r requirements.txt
python app.py
```

Opens `http://127.0.0.1:8765`. On Windows `run.bat` does the same.
Press Ctrl+C to stop.

### Building the standalone executable

On a Windows machine that has Python, double-click **`build.bat`** (or run
`pyinstaller docuwizard.spec`). The result is `dist\DocuWizard\` — zip that
whole folder and hand it out; recipients need nothing installed.

The build uses `docuwizard.spec` rather than a plain one-liner because
python-docx, python-pptx and pdfplumber ship data files that a naive build
silently omits (causing "Package not found" errors at runtime), and uvicorn
imports several modules dynamically. The spec collects all of them. It builds a
**folder** rather than a single file on purpose: single-file builds unpack
~100 MB to a temp directory on every launch, and managed-Windows antivirus
tends to treat large self-extracting executables with suspicion.

---

## Using it

The intended order is **build a ruleset → build an output template → add files
→ extract**. Every picker includes a **+ Create new…** option that jumps
straight to the editor, so the flow is visible from the landing page. A **?**
button in the header opens the built-in *How to use* page.

**Extract tab** — three numbered steps: add files, choose the ruleset and
output template, click **Extract**. Results show what was found and where it
came from; anything missing is red and listed at the top. Outputs download
automatically (`.docx` and PDF by default), and the buttons re-download.

**Rules & Output tab** — a side-by-side editor. Rules on the left, output
layout on the right, both live, so renaming a field updates the layout
immediately.

Building a field is progressive: name it, choose **which file**, then the
**extraction method** (which stays dimmed until a file is chosen), then the
details. Click **Pick from document** to open a preview of the real file —
select text and assign it as a start/end anchor rather than retyping it. For
spreadsheets, click the cell and it fills the sheet and cell reference.

Output sections are **drag-and-drop**, and headings are shown *as* headings, so
the editor roughly mirrors the finished document. Any field not placed in the
template still appears, appended at the end, so adding a rule never makes its
output vanish.

Rulesets and templates are plain JSON under `workspace/`, and both can be
**downloaded and imported**, so a setup built on one machine can be moved to
another.

---

## Reads

| Format | Citations look like | Notes |
|---|---|---|
| `.docx` | `§B.4 Project Team` | Real table structure — cell rules are exact |
| `.xlsx` / `.xlsm` | `Budget Summary!P10` | Exact cell addressing |
| `.pptx` | `Slide 7` | Includes speaker notes |
| `.pdf` | `p. 4` | **Least reliable** — see below |
| Output | `.docx`, PDF, `.md`, `.json` | JSON gives structured field/citation data for downstream systems |

Word has no stored page concept (pagination is computed at render time), so
`.docx` citations reference the nearest heading. That's more useful anyway: a
reviewer can Ctrl+F an anchor, whereas a page number in a 40-page document can
drift.

PDF has no native concept of a table — tables are *inferred* from ruled lines
and alignment, so cell-based rules are meaningfully less dependable on PDF than
on Word or Excel. Prefer the original `.docx`/`.xlsx` when you have it.

Legacy `.doc` cannot be read. Open in Word → **Save As → Word Document (.docx)**.

---

## Rule types, by file type

| Method | Finds | Needs | Available for |
|---|---|---|---|
| **Between** | Everything between two anchors. Returns plain text if both anchors sit in the same line; the whole span including tables if they're further apart. | start, end | Word, PDF, PowerPoint |
| **Right of (table cell)** | The table cell immediately right of a label cell. Tables only. | label | Word, PDF, PowerPoint |
| **Around keywords** | The paragraph *or* table containing a word/phrase. If the keyword is in a table, the whole table is returned; if in a paragraph, that paragraph plus any extra neighbouring paragraphs requested. | keyword, before, after | All formats |
| **Table contains** | The entire table containing a phrase. | contains | Excel only |
| **Sheet cell** | One spreadsheet cell, or a range (`P10` or `P10:R14`, selected by dragging). | sheet, cell | Excel only |

`before` / `after` on **Around keywords** mean *how many extra paragraphs to
include either side of the one containing the keyword* — leave both at 0 to get
just the matching paragraph.

**Two rules were merged.** `range` used to be separate from `between`, but they
were the same request at different scales, so `between` now detects the scale
itself: same-line anchors give inline text, far-apart anchors give the whole
verbatim span. Old rulesets using `range` or `around_keyword` are migrated
automatically on load.

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

## Where your data lives

Everything is saved locally, in the `workspace` folder beside the program, and
nothing is ever sent anywhere:

```
workspace/
  uploads/     files you've added (a library that persists between sessions)
  runs/        every past run: its outputs and manifest.json
  rulesets/    saved rulesets
  templates/   saved output templates
```

Uploaded files accumulate into a **local library**, so documents added earlier
are still available next time. On the Extract tab, **Previously uploaded files
(saved locally)** lists them: click one to select it, click-and-drag or use
Ctrl/Shift to select several, and only the highlighted files are used for that
run. **Remove selected** deletes individual files; **Clear all files** empties
the library. Rulesets, templates and past runs are untouched by both.

When packaged as an executable (below), the `workspace` folder is created next
to `DocuWizard.exe`, so saved work persists there.

Bundled **sample files** (a cartoon grant application from Doofenshmirtz Evil
Incorporated) let the tool be demonstrated and tested without loading anything
confidential.

## Versioning

Each run writes to `workspace/runs/<timestamp>/` containing the outputs and a
`manifest.json` recording the rule set, template, per-field results, and a
SHA-256 fingerprint of every input file. Content hashing is used rather than
timestamps because copies and syncs change modification times without changing
content.

**Note:** because of the privacy purge above, this folder is deleted as soon as
the run has been delivered. The manifest is therefore a within-run record, not a
long-term audit trail. If you need retained provenance, save the JSON output
alongside your downloaded summary.

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
- **`right_of` is table-only** by definition; the preview dims non-table content
  to make that obvious.
- **Very tall table rows in PDF** are rendered as labelled paragraphs instead of
  a grid. ReportLab cannot split a table row across pages, so a row taller than
  one page would otherwise fail the export; content is preserved, the grid is
  not.
- **Fonts**: TT Norms Pro / TT Wellingtons are commercial and cannot be bundled
  or fetched (no internet). They are requested first and used if installed on
  the machine; otherwise a humanist/geometric system fallback is used.

---

## Files

```
app.py               local web server (127.0.0.1 only) + API
docuwizard.spec      PyInstaller build recipe
build.bat            one-click build script (Windows)
requirements.txt     runtime dependencies
requirements-build.txt  build-time dependencies (adds PyInstaller)
samples/             bundled demo documents
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
