# Poppler Installation Helper Script for Windows
# This script helps install Poppler for PDF processing

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Poppler Installation Helper" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$popplerUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.11.0-0/Release-23.11.0-0.zip"
$downloadPath = "$env:USERPROFILE\Downloads\poppler.zip"
$extractPath = "$env:USERPROFILE\poppler"

Write-Host "This script will:" -ForegroundColor Yellow
Write-Host "1. Download Poppler for Windows" -ForegroundColor Yellow
Write-Host "2. Extract it to: $extractPath" -ForegroundColor Yellow
Write-Host "3. Add it to your system PATH" -ForegroundColor Yellow
Write-Host ""

$response = Read-Host "Do you want to proceed? (Y/N)"
if ($response -ne 'Y' -and $response -ne 'y') {
    Write-Host "Installation cancelled." -ForegroundColor Red
    exit
}

Write-Host "`nStep 1: Downloading Poppler..." -ForegroundColor Green
try {
    Invoke-WebRequest -Uri $popplerUrl -OutFile $downloadPath -UseBasicParsing
    Write-Host "Download complete!" -ForegroundColor Green
} catch {
    Write-Host "Download failed: $_" -ForegroundColor Red
    Write-Host "Please download manually from: $popplerUrl" -ForegroundColor Yellow
    exit
}

Write-Host "`nStep 2: Extracting Poppler..." -ForegroundColor Green
try {
    if (Test-Path $extractPath) {
        Remove-Item $extractPath -Recurse -Force
    }
    Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force
    Write-Host "Extraction complete!" -ForegroundColor Green
} catch {
    Write-Host "Extraction failed: $_" -ForegroundColor Red
    exit
}

# Find the actual poppler folder (it might be nested)
$popplerBin = Get-ChildItem -Path $extractPath -Recurse -Directory -Filter "bin" | Select-Object -First 1
if ($popplerBin) {
    $popplerBinPath = $popplerBin.FullName
    Write-Host "`nFound Poppler bin folder at: $popplerBinPath" -ForegroundColor Green
} else {
    Write-Host "`nWarning: Could not find bin folder. Please set path manually." -ForegroundColor Yellow
    $popplerBinPath = "$extractPath\Library\bin"  # Common location
}

Write-Host "`nStep 3: Adding to PATH..." -ForegroundColor Green
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$popplerBinPath*") {
    $newPath = $currentPath + ";$popplerBinPath"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added to PATH!" -ForegroundColor Green
    Write-Host "`nIMPORTANT: Please restart your terminal/IDE for PATH changes to take effect!" -ForegroundColor Yellow
} else {
    Write-Host "Already in PATH!" -ForegroundColor Green
}

Write-Host "`nStep 4: Cleaning up..." -ForegroundColor Green
Remove-Item $downloadPath -Force
Write-Host "Done!" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nPoppler is installed at: $popplerBinPath" -ForegroundColor Green
Write-Host "Please restart your Flask application and try again." -ForegroundColor Yellow
Write-Host ""
