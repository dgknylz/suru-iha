# Depodaki Unity scriptlerini ve Blender'dan üretilen modelleri Unity projesine kopyalar.
#   powershell -File tools/sync_unity.ps1 [-Project C:\SuruIHA\SuruIHA_Unity] [-Models C:\SuruIHA\models]
param(
    [string]$Project = "C:\SuruIHA\SuruIHA_Unity",
    [string]$Models = "C:\SuruIHA\models"
)
$repo = Split-Path -Parent $PSScriptRoot
$dst = Join-Path $Project "Assets\SuruIHA"
New-Item -ItemType Directory -Force $dst | Out-Null
foreach ($d in "Scripts", "Editor") {
    New-Item -ItemType Directory -Force (Join-Path $dst $d) | Out-Null
    Copy-Item -Path (Join-Path $repo "unity\Assets\SuruIHA\$d\*") -Destination (Join-Path $dst $d) -Recurse -Force
}
$mdst = Join-Path $dst "Models"
New-Item -ItemType Directory -Force $mdst | Out-Null
Get-ChildItem $Models -Filter *.fbx -Recurse | ForEach-Object { Copy-Item $_.FullName $mdst -Force }
$tdst = Join-Path $dst "Textures\Gen"
New-Item -ItemType Directory -Force $tdst | Out-Null
Get-ChildItem (Join-Path $Models "textures") -Filter *.png -ErrorAction SilentlyContinue | ForEach-Object { Copy-Item $_.FullName $tdst -Force }
Write-Host "Unity projesi güncellendi: $dst"
