@echo off
REM Document Extractor launcher. Double-click to start.
REM Opens http://127.0.0.1:8765 in your browser. Close this window to stop.
cd /d "%~dp0"
where python >nul 2>nul && (python app.py & goto :eof)
where py >nul 2>nul && (py app.py & goto :eof)
echo Python was not found. Install Python 3.10+ then run:
echo    pip install fastapi uvicorn python-multipart python-docx openpyxl pdfplumber python-pptx reportlab
pause
