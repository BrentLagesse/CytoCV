[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunserverArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message"
}

function Fail {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

function Find-RepoRoot {
    param([string]$StartDirectory)

    $current = Get-Item -LiteralPath $StartDirectory
    while ($null -ne $current) {
        $requirements = Join-Path $current.FullName 'requirements.txt'
        $managePy = Join-Path $current.FullName 'cytocv\manage.py'
        if ((Test-Path -LiteralPath $requirements -PathType Leaf) -and (Test-Path -LiteralPath $managePy -PathType Leaf)) {
            return $current.FullName
        }
        $current = $current.Parent
    }

    return $null
}

function Find-GitBash {
    $candidates = New-Object System.Collections.Generic.List[string]

    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles 'Git\bin\bash.exe'))
    }

    $programFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if ($programFilesX86) {
        $candidates.Add((Join-Path $programFilesX86 'Git\bin\bash.exe'))
    }

    try {
        $gitCommand = Get-Command git.exe -ErrorAction Stop | Select-Object -First 1
        $gitRoot = Split-Path -Parent (Split-Path -Parent $gitCommand.Source)
        $candidates.Add((Join-Path $gitRoot 'bin\bash.exe'))
    } catch {
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }

    return $null
}

$repoRoot = Find-RepoRoot -StartDirectory (Get-Location).Path
if (-not $repoRoot) {
    Fail "Could not find the CytoCV repo root from the current directory. Launch this script from somewhere inside the CytoCV repo tree."
}

$gitBash = Find-GitBash
if (-not $gitBash) {
    Fail "Could not find Git Bash. Install Git for Windows or run scripts/run-local-windows.sh from Git Bash directly."
}

$bashScript = Join-Path $repoRoot 'scripts\run-local-windows.sh'
if (-not (Test-Path -LiteralPath $bashScript -PathType Leaf)) {
    Fail "Could not find scripts/run-local-windows.sh under the discovered repo root."
}

Write-Info "Discovered repo root: $repoRoot"
Write-Info "Using Git Bash: $gitBash"

Push-Location -LiteralPath $repoRoot
try {
    & $gitBash $bashScript @RunserverArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($exitCode -ne 0) {
    exit $exitCode
}
