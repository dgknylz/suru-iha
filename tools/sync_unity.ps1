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
# Fotoğraf tabanlı dokular (Poly Haven, CC0; tools/fetch_assets.py indirir). Yalnızca değişenler kopyalanır:
# her kopya Unity'de dokunun yeniden içe aktarılmasına yol açar.
$photo = "C:\SuruIHA\assets\polyhaven"
if (Test-Path $photo) {
    $pdst = Join-Path $dst "Textures\Photo"
    New-Item -ItemType Directory -Force $pdst | Out-Null
    Get-ChildItem $photo -Recurse -Include *.jpg, *.png | ForEach-Object {
        $t = Join-Path $pdst $_.Name
        if (-not (Test-Path $t) -or (Get-Item $t).Length -ne $_.Length) { Copy-Item $_.FullName $t -Force }
    }
}
Write-Host "Unity projesi güncellendi: $dst"
