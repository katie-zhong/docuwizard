# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for DocuWizard.

Build with:      pyinstaller docuwizard.spec
Output:          dist/DocuWizard/DocuWizard.exe   (a folder you can zip)

WHY A SPEC FILE RATHER THAN A ONE-LINER
---------------------------------------
Three of the libraries here do not survive a naive PyInstaller build:

  * python-docx and python-pptx ship .xml/.docx TEMPLATE files inside the
    package. Without them, creating a document raises "Package not found".
  * pdfplumber/pdfminer ship encoding data files (CMaps). Without them, some
    PDFs fail to extract text.
  * uvicorn and fastapi import large parts of themselves dynamically, so
    PyInstaller's static analysis misses modules unless they are collected.

collect_all() pulls in each package's code, data files and hidden imports
together, which is what makes the frozen build behave like the source build.

ONE-FILE VS ONE-FOLDER
----------------------
This spec builds ONE FOLDER (the default below). That is deliberate:
  * it starts noticeably faster - a one-file exe unpacks ~100MB to a temp
    directory on every launch;
  * antivirus and application-control software on managed Windows machines are
    far more suspicious of a single large self-extracting exe.
If you specifically want a single file, see the note at the bottom.
"""

from PyInstaller.utils.hooks import collect_all

datas = [
    ("static", "static"),      # the whole UI
    ("samples", "samples"),    # bundled demo documents
]
binaries = []
hiddenimports = []

# Packages that need their data files and dynamic imports pulled in wholesale.
for pkg in ("docx", "pptx", "openpyxl", "pdfplumber", "pdfminer",
            "reportlab", "uvicorn", "fastapi", "starlette",
            "anyio", "click", "h11"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        # A package that isn't installed simply isn't bundled.
        pass

# uvicorn resolves these by string name at runtime, so they must be forced in.
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy.tests", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DocuWizard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX compression trips some antivirus heuristics
    console=True,       # keep the console: it shows the URL and any errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DocuWizard",
)

# ---------------------------------------------------------------------------
# For a SINGLE-FILE build instead, delete the COLLECT block above and change the
# EXE call to include a.binaries and a.datas with exclude_binaries=False:
#
#   exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
#             name="DocuWizard", console=True, upx=False)
#
# Remember that the workspace folder is created next to the .exe either way, so
# saved rulesets, templates and runs persist in both builds.
# ---------------------------------------------------------------------------
