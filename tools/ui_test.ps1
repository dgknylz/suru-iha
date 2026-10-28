# Arayüz testi: uygulama bütün ekranları kendisi gezer (açılış, senaryo seçimi, proje, kullanım),
# simülasyonu menüden başlatır, uçuşu sonuna kadar izler, yan yana karşılaştırmayı açar ve her adımda
# ekran görüntüsü alır. Python'u uygulamanın kendisi başlatır (terminale gerek yok).
#   powershell -File tools/ui_test.ps1 [-Out C:\SuruIHA\arayuz_testi] [-Width 1600 -Height 900]
param(
    [string]$Out = "C:\SuruIHA\arayuz_testi",
    [string]$Exe = "C:\SuruIHA\Build\SuruIHA.exe",
    [int]$Width = 1600,
    [int]$Height = 900,
    [switch]$Portable       # uygulamanın yanındaki taşınabilir Python'la (sim klasörü) dene
)
Remove-Item -Recurse -Force $Out -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Out | Out-Null
$pargs = @("-suruUiTest", $Out, "-screen-fullscreen", "0", "-screen-width", "$Width", "-screen-height", "$Height",
    "-logFile", (Join-Path $Out "player.log"))
if ($Portable) { $pargs += "-suruTasinabilir" }
$p = Start-Process -FilePath $Exe -PassThru -ArgumentList $pargs
if (-not $p.WaitForExit(900000)) { Write-Host "zaman aşımı"; $p.Kill() }
Get-Content (Join-Path $Out "rapor.txt") -ErrorAction SilentlyContinue
Get-ChildItem $Out -Filter *.png | ForEach-Object { $_.Name }
