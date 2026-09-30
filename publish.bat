@echo off
rem Commit everything and publish site\ to the gh-pages branch (GitHub Pages serves that branch).
cd /d "%~dp0"
git add -A
git commit -m "Update audiobook" || echo nothing new to commit
git push origin main
for /f %%i in ('git subtree split --prefix site') do set SPLIT=%%i
git push -f origin %SPLIT%:refs/heads/gh-pages
echo.
echo Published: https://vladislavgeneralov.github.io/text2speech/
pause
