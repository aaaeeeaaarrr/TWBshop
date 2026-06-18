<#
  checkpoint.ps1 — the engine behind the "push" word: consolidate EVERY lane onto main and push.

  WHAT IT DOES (run it from ANY worktree):
    1. Finds whichever worktree holds `main` and operates there (so you can run it from a lane).
    2. Fetches origin.
    3. Merges every `lane/*` branch that is AHEAD of main into main (--no-ff).
    4. Pushes main + all lane branches to origin (lane branches = backup).
    5. Verifies main == origin/main (independent re-read).

  SAFE BY CONSTRUCTION: it NEVER resets and NEVER force-pushes. On a merge conflict it ABORTS that
  one lane (main is left exactly as it was) and reports it — it never guesses a resolution. It is
  fully re-runnable. The only thing it asks a human for is a genuine conflict or a moved origin/main.

  Because deploys come from TAGS (never from `main`), it is fine for `main` to carry work-in-progress
  from several lanes — that is what makes "type pull on the other machine and get everything" work.

  USAGE:
    .\scripts\checkpoint.ps1            # consolidate + push + verify
    .\scripts\checkpoint.ps1 -DryRun    # show the plan only; change nothing
#>
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$TRAILER = "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"

# --- locate the worktree that has `main` checked out ---
$mainWt = $null; $cur = $null
foreach ($line in (git worktree list --porcelain)) {
    if     ($line -like 'worktree *')           { $cur = $line.Substring(9) }
    elseif ($line -eq 'branch refs/heads/main') { $mainWt = $cur }
}
if (-not $mainWt) {
    Write-Host "STOP: 'main' is not checked out in any worktree. Check out main in your primary repo, then re-run." -ForegroundColor Red
    exit 1
}

git -C $mainWt fetch origin --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "STOP: git fetch failed." -ForegroundColor Red; exit 1 }

# --- which lane/* branches are AHEAD of main? ---
$lanes = @(git -C $mainWt for-each-ref --format='%(refname:short)' refs/heads/lane/)
$ahead = @()
foreach ($l in $lanes) {
    $n = git -C $mainWt rev-list --count "main..$l"
    if ([int]$n -gt 0) { $ahead += $l }
}

# --- warn about dirty sibling worktrees (their uncommitted work will NOT travel) ---
$dirty = @(); $p = $null
foreach ($line in (git worktree list --porcelain)) {
    if ($line -like 'worktree *') {
        $p = $line.Substring(9)
        if (git -C $p status --porcelain) { $dirty += $p }
    }
}

Write-Host ""
Write-Host "=== CHECKPOINT ===" -ForegroundColor Cyan
Write-Host "main worktree : $mainWt"
if ($ahead) { Write-Host "lanes ahead   : $($ahead -join ', ')" }
else        { Write-Host "lanes ahead   : (none - main already has everything)" }
if ($dirty) { Write-Host "DIRTY worktrees (uncommitted, NOT included): $($dirty -join ', ')" -ForegroundColor Yellow }

if ($DryRun) {
    Write-Host ""
    if (git -C $mainWt status --porcelain) {
        Write-Host "[DryRun] NOTE: main worktree has uncommitted changes - a real run will ask you to commit/stash first." -ForegroundColor Yellow
    }
    Write-Host "[DryRun] would merge those lanes into main, then push main + all lane branches. Nothing changed." -ForegroundColor Yellow
    exit 0
}

# --- real run only: the main worktree must be clean (we are about to merge into it) ---
if (git -C $mainWt status --porcelain) {
    Write-Host "STOP: the main worktree ($mainWt) has uncommitted changes. Commit or stash them first." -ForegroundColor Red
    exit 1
}

# --- merge each ahead lane; abort + record on conflict (main stays intact) ---
$merged = @(); $conflicted = @()
foreach ($l in $ahead) {
    git -C $mainWt merge --no-ff $l -m "checkpoint: merge $l into main" -m $TRAILER
    if ($LASTEXITCODE -ne 0) {
        git -C $mainWt merge --abort
        $conflicted += $l
        Write-Host "CONFLICT merging $l - aborted, main untouched. Resolve $l vs main, then re-run." -ForegroundColor Red
    } else {
        $merged += $l
    }
}

# --- push main, then all lane branches as backup ---
git -C $mainWt push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "STOP: 'git push origin main' was rejected (origin/main moved?). Run 'pull' then re-run checkpoint." -ForegroundColor Red
    exit 1
}
foreach ($l in $lanes) { git -C $mainWt push origin $l }

# --- verify (independent post-push re-read) ---
git -C $mainWt fetch origin --quiet
$lm = (git -C $mainWt rev-parse main).Trim()
$om = (git -C $mainWt rev-parse origin/main).Trim()
Write-Host ""
if ($lm -eq $om) {
    Write-Host "VERIFIED: main == origin/main ($($lm.Substring(0,7)))" -ForegroundColor Green
} else {
    Write-Host "VERIFY FAILED: main ($($lm.Substring(0,7))) != origin/main ($($om.Substring(0,7)))" -ForegroundColor Red
    exit 1
}
if ($merged) { Write-Host "merged    : $($merged -join ', ')" }
else         { Write-Host "merged    : (none - main was already current)" }
if ($conflicted) { Write-Host "NEEDS YOU : $($conflicted -join ', ')  (conflict - resolve vs main, re-run)" -ForegroundColor Red }
Write-Host "=== checkpoint done ===" -ForegroundColor Cyan
