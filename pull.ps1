# Pull: stash → git pull --rebase → bootstrap sync → pip install → report

$stashed = $false
if (git status --porcelain) {
    git stash | Out-Null
    $stashed = $true
}

$before = git rev-parse HEAD
git pull --rebase

if ($stashed) { git stash pop | Out-Null }

if (Test-Path "secrets.py") {
    python bootstrap.py --sync
} else {
    python bootstrap.py
}

pip install -r requirements.txt -q

$after = git rev-parse HEAD
if ($before -ne $after) {
    $files = git diff --name-only $before $after
    Write-Host "Pulled: $($files -join ', ')"
} else {
    Write-Host "Already up to date."
}
