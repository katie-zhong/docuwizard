@echo off
REM ====================================================================
REM  Build DocuWizard into a standalone folder that runs without Python.
REM
REM  Run this ONCE on a Windows machine that has Python installed.
REM  The result is  dist\DocuWizard\  - zip that folder and hand it out.
REM ====================================================================
cd /d "%~dp0"

echo Installing build dependencies...
python -m pip install -r requirements-build.txt || goto :fail

echo.
echo Building (this takes a few minutes)...
python -m PyInstaller --noconfirm --clean docuwizard.spec || goto :fail

echo.
echo ============================================================
echo  Done. Your distributable is:  dist\DocuWizard\
echo  Zip that whole folder. Users run DocuWizard.exe inside it.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo Build failed. Check the messages above.
pause
exit /b 1
