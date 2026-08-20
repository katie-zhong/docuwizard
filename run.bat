@echo off
REM ====================================================================
REM  DocuWizard launcher (source version - needs Python installed).
REM
REM  Double-click to start. Your browser opens at http://127.0.0.1:8765
REM  Close this window, or press Ctrl+C, to stop the tool.
REM
REM  If you have the PACKAGED version instead, run DocuWizard.exe -
REM  that one needs no Python at all.
REM ====================================================================
cd /d "%~dp0"

REM Find Python: "python" first, then the Windows launcher "py".
set PY=
where python >nul 2>nul && set PY=python
if not defined PY (where py >nul 2>nul && set PY=py)

if not defined PY (
    echo.
    echo Python was not found on this computer.
    echo Install Python 3.10 or newer from python.org, tick
    echo "Add Python to PATH" during setup, then run this file again.
    echo.
    pause
    exit /b 1
)

REM Check the libraries are present; install them from requirements.txt if not.
%PY% -c "import fastapi, uvicorn, docx, openpyxl, pdfplumber, pptx, reportlab" >nul 2>nul
if errorlevel 1 (
    echo First run: installing the required libraries...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo The libraries could not be installed. If this computer restricts
        echo installs, try:   %PY% -m pip install --user -r requirements.txt
        echo.
        pause
        exit /b 1
    )
)

%PY% app.py
pause
