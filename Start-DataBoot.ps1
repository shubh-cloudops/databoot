# DataBoot launcher for Windows 11: .\Start-DataBoot.ps1 [-Folder D:\data or E:\] [-Docker]
param(
    [string]$Folder,
    [switch]$Docker
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

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
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3.11 -m venv .venv } else { python -m venv .venv }
    if (Test-Path wheels) {
        .venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements.txt
    } else {
        .venv\Scripts\python.exe -m pip install -r requirements.txt
    }
}
.venv\Scripts\python.exe -m app.launch $Folder
