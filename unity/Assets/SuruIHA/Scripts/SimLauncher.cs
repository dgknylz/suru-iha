using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Text;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace SuruIHA
{
    // Python simülasyonunu uygulamanın içinden başlatır ve kapatır (fuarda terminal açmaya gerek kalmasın).
    // Deponun yeri, derleme sırasında tools/full_build.ps1'in uygulamanın yanına yazdığı
    // "simulasyon_yolu.txt" dosyasından okunur. Python, deponun .venv ortamından çalışır.
    public class SimLauncher : MonoBehaviour
    {
        public enum State { NotFound, Idle, Starting, Running, External, Crashed }

        public static SimLauncher Instance { get; private set; }

        public string RepoPath { get; private set; }
        public string PythonPath { get; private set; }
        public State Status { get; private set; } = State.Idle;
        public string LastError { get; private set; } = "";
        public string RunningArgs { get; private set; } = "";

        Process proc;
        float startedAt;
        readonly ConcurrentQueue<string> lines = new ConcurrentQueue<string>();
        string lastLine = "";

        const string PathFile = "simulasyon_yolu.txt";
        static string PidFile => Path.Combine(Application.temporaryCachePath, "simulasyon_pid.txt");

        void Awake()
        {
            Instance = this;
            FindPython();
            KillOrphan();
        }

        // Deponun yeri: uygulamanın yanındaki dosya, ortam değişkeni ya da bilinen konumlar
        void FindPython()
        {
            var candidates = new System.Collections.Generic.List<string>();
            string appDir = Path.GetDirectoryName(Application.dataPath);
            foreach (var dir in new[] { appDir, Application.dataPath })
            {
                string f = Path.Combine(dir, PathFile);
                if (File.Exists(f)) candidates.Add(File.ReadAllText(f, Encoding.UTF8).Trim());
            }
            string env = Environment.GetEnvironmentVariable("SURU_IHA_REPO");
            if (!string.IsNullOrEmpty(env)) candidates.Add(env);
            string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            candidates.Add(Path.Combine(home, "OneDrive", "Desktop", "sürü_iha"));
            candidates.Add(Path.Combine(home, "Desktop", "sürü_iha"));
            foreach (var c in candidates)
            {
                if (string.IsNullOrEmpty(c) || !File.Exists(Path.Combine(c, "run_live.py"))) continue;
                RepoPath = c;
                string venv = Path.Combine(c, ".venv", "Scripts", "python.exe");
                PythonPath = File.Exists(venv) ? venv : "python";
                Status = State.Idle;
                Debug.Log($"[SuruIHA] Simülasyon bulundu: {RepoPath} ({PythonPath})");
                return;
            }
            Status = State.NotFound;
            LastError = "Simülasyon klasörü bulunamadı. Uygulamanın yanına simulasyon_yolu.txt koy " +
                        "(içinde deponun yolu) ya da terminalde python run_live.py çalıştır.";
        }

        public bool CanLaunch => RepoPath != null;
        public bool IsOurs => proc != null && !proc.HasExited;

        // script: run_live.py ya da run_compare.py; args: komut satırı seçenekleri
        public bool Launch(string script, string args)
        {
            if (!CanLaunch) return false;
            Stop();
            var psi = new ProcessStartInfo
            {
                FileName = PythonPath,
                Arguments = $"-u {script} {args}",
                WorkingDirectory = RepoPath,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            try
            {
                proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
                proc.OutputDataReceived += (_, e) => { if (e.Data != null) lines.Enqueue(e.Data); };
                proc.ErrorDataReceived += (_, e) => { if (e.Data != null) lines.Enqueue(e.Data); };
                proc.Start();
                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();
                File.WriteAllText(PidFile, proc.Id.ToString());
                Status = State.Starting;
                startedAt = Time.unscaledTime;
                RunningArgs = $"{script} {args}";
                LastError = "";
                Debug.Log($"[SuruIHA] Simülasyon başlatıldı: python {RunningArgs}");
                return true;
            }
            catch (Exception ex)
            {
                proc = null;
                Status = State.Crashed;
                LastError = "Python başlatılamadı: " + ex.Message;
                Debug.LogError("[SuruIHA] " + LastError);
                return false;
            }
        }

        public void Stop()
        {
            if (proc == null) return;
            try
            {
                if (!proc.HasExited) KillTree(proc.Id);
            }
            catch (Exception ex) { Debug.LogWarning("[SuruIHA] Simülasyon kapatılamadı: " + ex.Message); }
            proc.Dispose();
            proc = null;
            try { File.Delete(PidFile); } catch (Exception) { }
            Status = CanLaunch ? State.Idle : State.NotFound;
            RunningArgs = "";
        }

        // .venv'deki python.exe gerçek yorumlayıcıyı alt süreç olarak açar: ağacın tamamı kapatılmalı,
        // yoksa eski simülasyon UDP portlarını tutmaya ve kare yollamaya devam eder.
        static void KillTree(int pid)
        {
            using var k = Process.Start(new ProcessStartInfo("taskkill", $"/PID {pid} /T /F")
            {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true,
            });
            k?.WaitForExit(3000);
        }

        // Uygulama çöküp kapanmışsa önceki çalıştırmadan kalan simülasyonu temizle
        static void KillOrphan()
        {
            try
            {
                if (!File.Exists(PidFile)) return;
                if (int.TryParse(File.ReadAllText(PidFile), out int pid))
                {
                    try
                    {
                        var p = Process.GetProcessById(pid);
                        if (p.ProcessName.ToLowerInvariant().Contains("python")) KillTree(pid);
                    }
                    catch (ArgumentException) { }   // süreç zaten yok
                }
                File.Delete(PidFile);
            }
            catch (Exception ex) { Debug.LogWarning("[SuruIHA] Eski simülasyon temizlenemedi: " + ex.Message); }
        }

        void Update()
        {
            while (lines.TryDequeue(out var l))
                if (!string.IsNullOrWhiteSpace(l)) lastLine = l.Trim();

            var rx = SwarmVisualizer.Main != null ? SwarmVisualizer.Main.Receiver : null;
            bool connected = rx != null && rx.Connected;
            if (proc != null)
            {
                if (proc.HasExited)
                {
                    Status = State.Crashed;
                    LastError = "Simülasyon kapandı" + (string.IsNullOrEmpty(lastLine) ? "." : ": " + lastLine);
                    Debug.LogWarning("[SuruIHA] " + LastError);
                    proc.Dispose();
                    proc = null;
                }
                else if (connected) Status = State.Running;
                else if (Time.unscaledTime - startedAt > 45f)
                {
                    Status = State.Crashed;
                    LastError = "Simülasyon 45 saniyede bağlanmadı" + (string.IsNullOrEmpty(lastLine) ? "." : ": " + lastLine);
                }
            }
            else if (connected) Status = State.External;   // terminalden başlatılmış bir simülasyon
            else if (Status == State.External || Status == State.Running) Status = CanLaunch ? State.Idle : State.NotFound;
        }

        void OnApplicationQuit() => Stop();
        void OnDestroy() => Stop();
    }
}
