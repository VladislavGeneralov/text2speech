@echo off
cd /d "%~dp0site"
echo Bedtime Reader: http://localhost:8000
start "" http://localhost:8000
python -m http.server 8000
