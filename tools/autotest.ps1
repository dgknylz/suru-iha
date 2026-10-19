# Uçtan uca test: Python canlı simülasyonu + Unity görselleştirme + otomatik ekran görüntüleri.
# Varsayılan olarak derlenmiş uygulamayı (SuruIHA.exe) kullanır; -Editor ile Unity editöründe dener.
#   powershell -File tools/autotest.ps1 [-Out C:\SuruIHA\autotest] [-Strategy resilient] [-Jammer 20] [-Editor]
param(
    [string]$Out = "C:\SuruIHA\autotest",
    [string]$Strategy = "resilient",
    [string]$Jammer = "20",
    [string]$Exe = "C:\SuruIHA\Build\SuruIHA.exe",
    [string]$Project = "C:\SuruIHA\SuruIHA_Unity",
    [string]$Unity = "C:\Program Files\Unity\Hub\Editor\6000.3.1f1\Editor\Unity.exe",
    [switch]$Editor,
    [int]$Soak = 0          # >0 ise sabit kamerayla bu kadar saniye dayanıklılık testi
)
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force $Out | Out-Null
Remove-Item (Join-Path $Out "rapor.txt") -ErrorAction SilentlyContinue
$sim = Start-Process -FilePath $py -ArgumentList @("-u", "run_live.py", "--strategy", $Strategy, "--jammer", $Jammer, "--speed", "2", "--loop") `
    -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Out "python.log")
try {
    if ($Editor) {
        $u = Start-Process -FilePath $Unity -ArgumentList @("-projectPath", $Project, "-suruAutoPlay", $Out, "-logFile", (Join-Path $Out "unity.log")) -PassThru
    } else {
        $pargs = @("-suruAutoPlay", $Out, "-screen-fullscreen", "0", "-screen-width", "1600", "-screen-height", "900",
            "-logFile", (Join-Path $Out "player.log"))
        if ($Soak -gt 0) { $pargs += @("-suruSoak", "$Soak") }
        $u = Start-Process -FilePath $Exe -ArgumentList $pargs -PassThru
    }
    if (-not $u.WaitForExit(600000)) { Write-Host "zaman aşımı"; $u.Kill() }
}
finally {
    if (-not $sim.HasExited) { $sim.Kill() }
}
Get-Content (Join-Path $Out "rapor.txt") -ErrorAction SilentlyContinue
