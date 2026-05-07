param(
    [string]$StatePath = "PROJECT_STATE.json"
)

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & git @Arguments 2>&1
    return @($output | ForEach-Object { $_.ToString() })
}

if (-not (Test-Path -LiteralPath $StatePath)) {
    Write-Error "Missing state file: $StatePath"
    exit 1
}

try {
    $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
} catch {
    Write-Error "Invalid JSON in ${StatePath}: $($_.Exception.Message)"
    exit 1
}

$branch = (Invoke-Git -Arguments @("branch", "--show-current") | Select-Object -First 1)
$head = (Invoke-Git -Arguments @("rev-parse", "--short", "HEAD") | Select-Object -First 1)
$statusBranch = Invoke-Git -Arguments @("status", "--short", "--branch")
$statusLines = Invoke-Git -Arguments @("status", "--short")

$branchSummary = ($statusBranch | Where-Object { $_ -like "## *" } | Select-Object -First 1)
if (-not $branchSummary) {
    $branchSummary = "## $branch"
}

$changeLines = @($statusLines | Where-Object { $_ -match '^(\?\?\s+|[ MADRCUT!?][ MADRCUT!?]\s+)' })
$untrackedLines = @($changeLines | Where-Object { $_ -match '^\?\?\s+' })
$trackedChangeLines = @($changeLines | Where-Object { $_ -notmatch '^\?\?\s+' })
$gitWarnings = @($statusBranch + $statusLines | Where-Object { $_ -like "warning:*" } | Select-Object -Unique)

Write-Host "Project: $($state.project)"
Write-Host "Stage: $($state.current_stage)"
Write-Host "Branch: $branch"
Write-Host "HEAD: $head"
Write-Host "Ahead/behind: $branchSummary"
Write-Host "Runner: $($state.default_runner)"
Write-Host "Python: $($state.python_runner)"
Write-Host "Latest batch: $($state.latest_batch.path) [$($state.latest_batch.status)]"
Write-Host "Last validation: $($state.last_validation.result) $($state.last_validation.date)"
Write-Host "Next action: $($state.next_action)"

if ($state.blocked_on.Count -gt 0) {
    Write-Host "Blocked on:"
    $state.blocked_on | ForEach-Object { Write-Host " - $_" }
} else {
    Write-Host "Blocked on: none"
}

Write-Host "Dirty count: $($changeLines.Count)"
Write-Host "Tracked dirty count: $($trackedChangeLines.Count)"
Write-Host "Untracked count: $($untrackedLines.Count)"

if ($gitWarnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Git warnings:"
    $gitWarnings | ForEach-Object { Write-Host $_ }
}

if ($changeLines.Count -gt 0) {
    Write-Host ""
    Write-Host "Dirty files:"
    $changeLines | ForEach-Object { Write-Host $_ }
}
