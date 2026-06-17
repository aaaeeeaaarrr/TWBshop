<#
  make_lane.ps1 — create an isolated git worktree for a parallel lane.

  Usage:   .\scripts\make_lane.ps1 accountant
  Result:  a NEW sibling folder ..\twbshop-accountant on branch lane/accountant.

  Safe by construction: a worktree is ADDITIVE — it creates a new folder sharing the
  same .git object store. It does NOT touch this folder, the server, or any data.
  Remove anytime with:  git worktree remove ..\twbshop-<lane>
#>
param([Parameter(Mandatory = $true)][string]$Lane)
$ErrorActionPreference = "Stop"

$repo   = Split-Path -Parent $PSScriptRoot
$parent = Split-Path -Parent $repo
$dir    = Join-Path $parent "twbshop-$Lane"

if (Test-Path $dir) { Write-Error "Folder already exists: $dir"; exit 1 }

git -C $repo worktree add -b "lane/$Lane" $dir

Write-Host ""
Write-Host "[OK] Lane '$Lane' ready at: $dir   (branch lane/$Lane)" -ForegroundColor Green
Write-Host "Next, in that folder:" -ForegroundColor Cyan
Write-Host "  cd `"$dir`""
Write-Host "  python bootstrap.py --sync                      # fetch secrets.py into this worktree"
Write-Host "  python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt -q   # per-lane venv"
Write-Host "  `$env:TWBSHOP_ENV = 'staging'                    # dev default — NEVER prod locally"
Write-Host "  claude                                          # start a Claude session bound to this lane"
Write-Host ""
Write-Host "When the lane is done: merge to main -> tag -> deploy the tag (see docs/PARALLEL_LANES.md)." -ForegroundColor Yellow
