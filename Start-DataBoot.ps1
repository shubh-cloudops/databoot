# DataBoot launcher for Windows 11: .\Start-DataBoot.ps1 [-Folder D:\data or E:\] [-Docker]
param(
    [string]$Folder,
    [switch]$Docker
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Fail($Message) {
    Write-Host $Message
    if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
    Read-Host "Press Enter to close"
    exit 1
}

if (-not $Folder) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Choose the folder or drive to explore"
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 1 }
    $Folder = $dialog.SelectedPath
}
if (-not (Test-Path -LiteralPath $Folder -PathType Container)) {
    Write-Host "Folder not found: $Folder"
    exit 1
}

if ($Docker) {
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker is not running. Start Docker Desktop and try again."
        exit 1
    }
    docker image inspect databoot *> $null
    if ($LASTEXITCODE -ne 0) { docker build -t databoot . }
    docker run --rm -d -p 8765:8765 -v "${Folder}:/data:ro" databoot
    Start-Process http://localhost:8765/
    exit 0
}

if (-not (Test-Path .venv\Scripts\python.exe)) {
    $Candidates = @(@("py", "-3.13"), @("py", "-3.12"), @("py", "-3.11"), @("python"))
    $Check = "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)"
    $py = $null
    foreach ($c in $Candidates) {
        if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
        $rest = @($c | Select-Object -Skip 1)
        # Windows PowerShell 5.1 turns py's stderr into an error under "Stop"
        $ErrorActionPreference = "Continue"
        & $c[0] @rest -c $Check *> $null
        $code = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        if ($code -eq 0) { $py = $c; break }
    }
    if (-not $py) { Fail "DataBoot needs Python 3.12. Install it with: winget install -e --id Python.Python.3.12" }
    $rest = @($py | Select-Object -Skip 1)
    & $py[0] @rest -m venv .venv
    if (Test-Path wheels) {
        .venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements.txt
    } else {
        .venv\Scripts\python.exe -m pip install -r requirements.txt
    }
}
.venv\Scripts\python.exe -m app.launch $Folder
