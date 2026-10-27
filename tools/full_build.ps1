# Tüm hattı baştan çalıştırır: eşitle -> sahneyi kur -> önizleme -> Windows uygulaması -> uçtan uca test.
#   powershell -File tools/full_build.ps1 [-SkipPlayer] [-SkipTest]
param([switch]$SkipPlayer, [switch]$SkipTest)
$repo = Split-Path -Parent $PSScriptRoot
$u = "C:\Program Files\Unity\Hub\Editor\6000.3.1f1\Editor\Unity.exe"
$proj = "C:\SuruIHA\SuruIHA_Unity"
Get-Process Unity -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -Recurse -Force (Join-Path $proj "Temp\__Backupscenes") -ErrorAction SilentlyContinue
& (Join-Path $PSScriptRoot "sync_unity.ps1") | Out-Null

function RunUnity($method, $log, $extra = @()) {
    $args = @("-batchmode", "-projectPath", $proj, "-executeMethod", $method, "-logFile", $log) + $extra
    if ($method -notlike "*Build.BuildFromCommandLine") { $args = @("-quit") + $args }
    $t0 = Get-Date
    $p = Start-Process -FilePath $u -ArgumentList $args -PassThru -Wait
    $hata = Select-String -Path $log -Pattern "error CS|Exception:" | Select-Object -First 5
    Write-Host ("{0}: çıkış {1}, {2:0.0} dk" -f $method.Split('.')[-2], $p.ExitCode, ((Get-Date) - $t0).TotalMinutes)
    $hata | ForEach-Object { Write-Host "  ! $($_.Line)" }
    Select-String -Path $log -Pattern "\[SuruIHA\] (Sahne|Arazi|Derleme|Önizleme)" | ForEach-Object { Write-Host "  $($_.Line)" }
}

RunUnity "SuruIHA.EditorTools.SuruIHASetup.BuildFromCommandLine" "C:\SuruIHA\build.log"
# Unity'nin ürettiği arazi yüksekliğini simülasyona kopyala (Python aynı araziyi kullanır)
$data = Join-Path $repo "suru\data"
New-Item -ItemType Directory -Force $data | Out-Null
# her bölgenin haritası: arazi_yukseklik.* (ova) ve arazi_yukseklik_kar.* (karlı dağlar)
Copy-Item (Join-Path $proj "Arazi\arazi_yukseklik*") $data -Force
$frame = "C:\SuruIHA\kare_60.json"
& (Join-Path $repo ".venv\Scripts\python.exe") (Join-Path $repo "tools\dump_frame.py") $frame 45 | Out-Null
RunUnity "SuruIHA.EditorTools.SuruIHAPreview.FromCommandLine" "C:\SuruIHA\preview.log" @("-frame", $frame, "-out", "C:\SuruIHA\preview")
if (-not $SkipPlayer) { RunUnity "SuruIHA.EditorTools.SuruIHABuild.BuildFromCommandLine" "C:\SuruIHA\player.log" }
# Uygulama simülasyonu (Python) kendisi başlatır: deponun yerini uygulamanın ve Unity projesinin yanına yaz
foreach ($d in @("C:\SuruIHA\Build", $proj)) {
    if (Test-Path $d) { [IO.File]::WriteAllText((Join-Path $d "simulasyon_yolu.txt"), $repo, (New-Object Text.UTF8Encoding $false)) }
}
if (-not $SkipTest) { & (Join-Path $PSScriptRoot "autotest.ps1") }
