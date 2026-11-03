@echo off
cd /d "%~dp0"
echo ========================================================
echo   FloraChain B2B - Nursery Supply Management Platform
echo   Phase 2: Frontend Foundation
echo ========================================================
echo Server starting at: http://127.0.0.1:8000/index.html
echo Opening your default browser...
start "" "http://127.0.0.1:8000/index.html"
python -m http.server 8000 --bind 127.0.0.1
pause
