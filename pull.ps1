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

# In a lane, also absorb main so "pull" = "get me everything" (cross-lane work lives on main).
# Only when clean (mirrors pull-all's skip-dirty safety) so we never merge over in-progress work.
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -like 'lane/*') {
    if ($stashed) {
        Write-Host "NOTE: did NOT merge main (you have uncommitted changes). Commit, then run pull again." -ForegroundColor Yellow
    } else {
        git merge --no-edit origin/main
        if ($LASTEXITCODE -ne 0) {
            Write-Host "MERGE CONFLICT: main -> $branch. Resolve here (ask Claude), then commit." -ForegroundColor Red
        }
    }
}

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

if ($branch -ne 'main') {
    Write-Host "NOTE: on '$branch' (now includes main's latest). 'git checkout main' for the full integrator view." -ForegroundColor Yellow
}
