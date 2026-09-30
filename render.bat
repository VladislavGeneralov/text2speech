@echo off
rem Renders the audiobook; already finished chapters are skipped, so it is safe to re-run.
rem Usage: double-click (The Artist's Way), or drag another PDF onto this file.
cd /d "%~dp0"
set BOOK=%~1
if "%BOOK%"=="" set BOOK=The_Artists_Way_Julia_Cameron.pdf
del /q site\books\*\*.wav 2>nul
python -u convert.py "%BOOK%" --voice af_heart --speed 0.9
echo.
echo Render finished. Run publish.bat to put the new chapters online.
pause
