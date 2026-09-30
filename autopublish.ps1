# Publishes newly rendered chapters to GitHub Pages every 5 minutes while convert.py runs.
Set-Location $PSScriptRoot
$last = ""
while ($true) {
    $running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -like '*convert.py*'
    $state = (Get-ChildItem site\books -Recurse -Filter *.m4a | Measure-Object).Count
    if ("$state" -ne $last) {
        git add -A
        git commit -q -m "Add rendered chapters ($state)`n`nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        git push -q origin main
        $split = git subtree split --prefix site | Select-Object -Last 1
        git push -q -f origin "${split}:refs/heads/gh-pages"
        "$(Get-Date -Format HH:mm) published $state chapters" | Add-Content autopublish.log
        $last = "$state"
    }
    if (-not $running) { break }
    Start-Sleep -Seconds 300
}
