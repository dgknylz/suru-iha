# Unity projesini sıfırdan kurar (C:\SuruIHA silinse bile bu repodan her şey geri gelir):
#   1) HDRP şablonundan boş proje   2) repodaki proje ayarları   3) Blender modelleri ve dokular
#   4) sahne + Windows uygulaması + uçtan uca test (tools/full_build.ps1)
#   powershell -File tools/setup_unity_project.ps1
param(
    [string]$Project = "C:\SuruIHA\SuruIHA_Unity",
    [string]$Models = "C:\SuruIHA\models",
    [string]$Unity = "C:\Program Files\Unity\Hub\Editor\6000.3.1f1\Editor\Unity.exe",
    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
)
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Python ortamı kuruluyor..."
    & py -3.14 -m venv (Join-Path $repo ".venv")
    & $py -m pip install -q -r (Join-Path $repo "requirements.txt")
}

if (-not (Test-Path (Join-Path $Project "Assets"))) {
    Write-Host "Unity projesi oluşturuluyor (HDRP şablonu)..."
    $tpl = Get-ChildItem (Join-Path (Split-Path $Unity) "Data\Resources\PackageManager\ProjectTemplates") -Filter "com.unity.template.3d-high-end*.tgz" | Select-Object -First 1
    New-Item -ItemType Directory -Force (Split-Path $Project) | Out-Null
    Start-Process -FilePath $Unity -ArgumentList @("-batchmode", "-quit", "-createProject", $Project, "-cloneFromTemplate", "`"$($tpl.FullName)`"",
        "-logFile", (Join-Path (Split-Path $Project) "create.log")) -Wait
}

# Repodaki proje ayarları (kalite seviyeleri, arka planda çalışma, paketler)
Copy-Item (Join-Path $repo "unity\ProjectSettings\*") (Join-Path $Project "ProjectSettings") -Force
Copy-Item (Join-Path $repo "unity\Packages\*") (Join-Path $Project "Packages") -Force

Write-Host "Modeller (Blender) ve dokular üretiliyor..."
New-Item -ItemType Directory -Force $Models | Out-Null
foreach ($s in "drone", "jammer", "gcs") { & $Blender -b --factory-startup -P (Join-Path $repo "blender\$s.py") -- $Models | Out-Null }
& $Blender -b --factory-startup -P (Join-Path $repo "blender\nature.py") -- (Join-Path $Models "nature") | Out-Null
& $Blender -b --factory-startup -P (Join-Path $repo "blender\village.py") -- (Join-Path $Models "village") | Out-Null
& $py (Join-Path $repo "tools\gen_textures.py") (Join-Path $Models "textures")

& (Join-Path $PSScriptRoot "full_build.ps1")
