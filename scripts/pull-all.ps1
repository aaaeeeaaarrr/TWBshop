<#
  pull-all.ps1 - refresh EVERY clean worktree in one go (run from any terminal).

  WHAT IT DOES:
    1. Fetches origin.
    2. Fast-forwards the `main` worktree to origin/main (if it's checked out and clean).
    3. Merges origin/main INTO each clean lane worktree, so every lane picks up the
       other lanes' merged work.

  SAFE BY CONSTRUCTION:
    - SKIPS any worktree with uncommitted changes (it can't stomp in-progress work).
    - On a merge conflict it ABORTS that one lane (leaves it clean) and reports it -
      never leaves a half-merged lane, never resets, never force-pushes, never commits
      your working changes.
    - Merges (not rebases) so each lane's push to origin/lane-* stays fast-forward.

  USAGE:  .\scripts\pull-all.ps1
#>
$ErrorActionPreference = "Stop"

git fetch origin --prune --quiet

# enumerate worktrees
$wts = @(); $cur = $null
foreach ($line in (git worktree list --porcelain)) {
    if     ($line -like 'worktree *') { $cur = @{ path = $line.Substring(9) }; $wts += $cur }
    elseif ($line -like 'branch *')   { $cur.branch = ($line.Substring(7) -replace '^refs/heads/', '') }
    elseif ($line -eq 'detached')     { $cur.branch = '(detached)' }
}

$refreshed = @(); $skipped = @(); $conflicts = @(); $reqChanged = $false

# 1) fast-forward the main worktree (if present + clean)
$mainWt = ($wts | Where-Object { $_.branch -eq 'main' } | Select-Object -First 1)
if ($mainWt) {
    if (git -C $mainWt.path status --porcelain) {
        $skipped += "main (dirty)"
    } else {
        $b = (git -C $mainWt.path rev-parse HEAD).Trim()
        git -C $mainWt.path merge --ff-only origin/main --quiet 2>$null
        $a = (git -C $mainWt.path rev-parse HEAD).Trim()
        if ($b -ne $a) {
            $refreshed += "main"
            if (git -C $mainWt.path diff --name-only $b $a | Select-String 'requirements.txt') { $reqChanged = $true }
        }
    }
}

# 2) merge origin/main into each clean lane worktree
foreach ($wt in $wts) {
    if ($wt.branch -notlike 'lane/*') { continue }
    if (git -C $wt.path status --porcelain) { $skipped += "$($wt.branch) (dirty)"; continue }
    $b = (git -C $wt.path rev-parse HEAD).Trim()
    git -C $wt.path merge --no-edit origin/main 2>$null
    if ($LASTEXITCODE -ne 0) {
        git -C $wt.path merge --abort 2>$null
        $conflicts += $wt.branch
        Write-Host "CONFLICT merging origin/main into $($wt.branch) - aborted (lane left clean). Resolve in that lane." -ForegroundColor Red
    } else {
        $a = (git -C $wt.path rev-parse HEAD).Trim()
        if ($b -ne $a) {
            $refreshed += $wt.branch
            if (git -C $wt.path diff --name-only $b $a | Select-String 'requirements.txt') { $reqChanged = $true }
        }
    }
}

Write-Host ""
Write-Host "=== pull-all ===" -ForegroundColor Cyan
if ($refreshed) { Write-Host "refreshed : $($refreshed -join ', ')" -ForegroundColor Green }
else            { Write-Host "refreshed : (nothing - all current)" }
if ($skipped)   { Write-Host "skipped   : $($skipped -join ', ')  (dirty - pull them yourself when ready)" -ForegroundColor Yellow }
if ($conflicts) { Write-Host "CONFLICTS : $($conflicts -join ', ')  (resolve in that lane, then re-run)" -ForegroundColor Red }
if ($reqChanged){ Write-Host "NOTE: requirements.txt changed - run 'pip install -r requirements.txt -q' in refreshed lanes." -ForegroundColor Yellow }
