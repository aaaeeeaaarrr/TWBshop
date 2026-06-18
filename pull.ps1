# Pull: fetch-all → stash → git pull --rebase → bootstrap sync → pip install → report
# Multi-lane: `main` carries the full cross-lane checkpoint (see scripts/checkpoint.ps1).

git fetch --all --prune --quiet

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

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne 'main') {
    Write-Host "NOTE: you are on '$branch'. main holds the full cross-lane checkpoint - 'git checkout main' for everything." -ForegroundColor Yellow
}
