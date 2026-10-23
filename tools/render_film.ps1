# Tanıtım videosu 2/3 + 3/3: Unity uygulamasında kareleri çeker, sonra Blender'da MP4'e çevirir.
#   powershell -File tools/render_film.ps1 [-Film C:\SuruIHA\film] [-SkipFrames]
# Önce: python tools/record_film.py (uçuş kayıtları, film.json, kurgu.json, kartlar)
param(
    [string]$Film = "C:\SuruIHA\film",
    [string]$Exe = "C:\SuruIHA\Build\SuruIHA.exe",
    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    [switch]$SkipFrames
)
$repo = Split-Path -Parent $PSScriptRoot
if (-not $SkipFrames) {
    Remove-Item -Recurse -Force (Join-Path $Film "kareler") -ErrorAction SilentlyContinue
    $t0 = Get-Date
    $p = Start-Process -FilePath $Exe -PassThru -ArgumentList @("-suruFilm", (Join-Path $Film "film.json"),
        "-screen-fullscreen", "0", "-screen-width", "960", "-screen-height", "540", "-logFile", (Join-Path $Film "film.log"))
    if (-not $p.WaitForExit(3 * 3600 * 1000)) { Write-Host "zaman aşımı"; $p.Kill() }
    Write-Host ("Unity kareleri: {0:0.0} dk" -f ((Get-Date) - $t0).TotalMinutes)
    Get-Content (Join-Path $Film "kareler\film_rapor.txt") -ErrorAction SilentlyContinue
}
$t0 = Get-Date
& $Blender -b --factory-startup --python (Join-Path $PSScriptRoot "make_video.py") -- (Join-Path $Film "kurgu.json") 2>&1 |
    Select-String "\[video\]|Error|Traceback" | ForEach-Object { Write-Host $_.Line }
Write-Host ("Blender: {0:0.0} dk" -f ((Get-Date) - $t0).TotalMinutes)
Get-Item (Join-Path $repo "sunum\tanitim_videosu.mp4") -ErrorAction SilentlyContinue | ForEach-Object { "{0}  {1:0.0} MB" -f $_.FullName, ($_.Length / 1MB) }
