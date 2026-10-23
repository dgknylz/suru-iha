using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;

namespace SuruIHA
{
    // Yarışma arayüzü: açılış ekranı, senaryo seçimi, "Bu proje nedir?", "Nasıl kullanılır?", simülasyon
    // sırasında araç çubuğu, olay akışı, renk açıklamaları, görev sonu ekranı ve Esc menüsü.
    // Simülasyonu (Python) SimLauncher başlatır; terminal açmaya gerek yoktur.
    public partial class SwarmMenu : MonoBehaviour
    {
        public enum Page { Home, Scenarios, About, Help, Sim, Pause, Quit }

        public static SwarmMenu Instance { get; private set; }
        public Page Current { get; private set; } = Page.Home;
        public bool HidesHud => Current != Page.Sim && Current != Page.Pause;
        public string RunningTitle => running?.Title;

        Page back = Page.Home, beforeQuit = Page.Home;
        int scenario = 1, strategy = 2, planner = 1, seed;
        bool compare, fast;
        Scenario running;
        int runStrategy = 2;
        bool runCompare;
        bool bannerOpen, legendOpen, feedOpen = true, wasRunning;
        float bannerUntil;
        int resultsClosedFor = int.MinValue;
        string tip;
        SwarmCamera cam;
        SimLauncher launcher;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            var args = Environment.GetCommandLineArgs();
            if (args.Contains("-suruFilm") || args.Contains("-suruAutoPlay")) return;   // otomatik modlarda menü yok
            if (SwarmVisualizer.Main == null) return;
            var go = new GameObject("Arayuz");
            go.AddComponent<SimLauncher>();
            go.AddComponent<SwarmEvents>();
            go.AddComponent<SwarmMenu>();
        }

        void Awake() => Instance = this;

        void Start()
        {
            cam = FindAnyObjectByType<SwarmCamera>();
            launcher = GetComponent<SimLauncher>();
            if (cam != null) cam.mode = SwarmCamera.Mode.Cinematic;
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, "-suruUiTest");
            if (i >= 0) StartCoroutine(UiTest(i + 1 < args.Length ? args[i + 1] : "UiTest"));
        }

        void Go(Page p)
        {
            if (p == Page.About || p == Page.Help || p == Page.Scenarios)
                back = Current == Page.Pause || Current == Page.Sim ? Page.Pause : Page.Home;
            if (p == Page.Quit) beforeQuit = Current;
            Current = p;
        }

        bool SimConnected => SwarmVisualizer.Main != null && SwarmVisualizer.Main.Receiver != null &&
                             SwarmVisualizer.Main.Receiver.Connected;

        void Update()
        {
            Ui.Modal = Current != Page.Sim;
            if (SwarmInput.Down(SwarmInput.K.Esc))
            {
                switch (Current)
                {
                    case Page.Sim: Go(Page.Pause); break;
                    case Page.Pause: Current = Page.Sim; break;
                    case Page.Scenarios:
                    case Page.About:
                    case Page.Help: Current = back; break;
                    case Page.Quit: Current = beforeQuit; break;
                    case Page.Home: if (SimConnected) Current = Page.Sim; break;
                }
            }
            if (Current == Page.Sim)
            {
                if (SwarmInput.Down(SwarmInput.K.I)) legendOpen = !legendOpen;
            }
            // Yan yana karşılaştırmada olay akışı sağdaki dirençli sürüyü anlatır (B baştan kurulu, kare gelince başlar)
            var cmp = SwarmCompare.Instance;
            if (SwarmEvents.Instance != null) SwarmEvents.Instance.Source = runCompare && cmp != null ? cmp.B : null;

            // Senaryo kutusu, simülasyon bağlandıktan sonra bir süre açık kalır, sonra küçülür
            bool runningNow = launcher != null && launcher.Status == SimLauncher.State.Running;
            if (runningNow && !wasRunning) bannerUntil = Time.unscaledTime + 18f;
            wasRunning = runningNow;
            if (bannerOpen && runningNow && Time.unscaledTime > bannerUntil) bannerOpen = false;
        }

        // ---------------------------------------------------------------- başlatma
        void QuickStart()
        {
            scenario = 1;
            strategy = 2;
            planner = 1;
            compare = false;
            Launch();
        }

        void Launch()
        {
            if (launcher.Status == SimLauncher.State.External)
            {
                // Terminalden çalışan simülasyon portları tutuyor: ona bağlan, yenisini açma
                Current = Page.Sim;
                return;
            }
            var sc = SwarmScenarios.All[scenario];
            string pl = SwarmScenarios.Planners[planner];
            seed = seed % 30 + 1;
            string common = $"--planner {pl} {sc.Args} --seed {seed} --speed {(fast ? 6 : 1)}";
            bool ok = compare
                ? launcher.Launch("run_compare.py", $"--left {(strategy == 0 ? "centralized" : "decentralized")} {common}")
                : launcher.Launch("run_live.py", $"--strategy {SwarmScenarios.Strategies[strategy]} {common}");
            if (!ok) return;
            running = sc;
            runStrategy = compare ? 2 : strategy;
            runCompare = compare;
            var cmp = SwarmCompare.Instance;
            if (SwarmEvents.Instance != null)
            {
                SwarmEvents.Instance.Source = compare && cmp != null ? cmp.B : null;
                SwarmEvents.Instance.Clear();
            }
            bannerOpen = true;
            bannerUntil = float.MaxValue;
            legendOpen = false;
            resultsClosedFor = int.MinValue;
            if (cam != null) cam.mode = SwarmCamera.Mode.Cinematic;
            Current = Page.Sim;
        }

        void BackToHome()
        {
            launcher.Stop();
            running = null;
            Current = Page.Home;
            if (cam != null) cam.mode = SwarmCamera.Mode.Cinematic;
        }

        void Send(string json) => SwarmVisualizer.Main?.Receiver?.SendCommand(json);

        // ---------------------------------------------------------------- çizim
        void OnGUI()
        {
            GUI.depth = -10;
            tip = null;
            switch (Current)
            {
                case Page.Home: DrawHome(); break;
                case Page.Scenarios: DrawScenarios(); break;
                case Page.About: DrawAbout(); break;
                case Page.Help: DrawHelp(); break;
                case Page.Sim: DrawSim(); break;
                case Page.Pause: DrawSim(); DrawPause(); break;
                case Page.Quit: DrawQuit(); break;
            }
            // Açılışta karanlıktan aydınlığa geçiş (HDRP'nin otomatik pozlaması ilk saniyelerde ekranı beyaz gösterir)
            float since = Time.realtimeSinceStartup;
            if (since < 5.5f)
            {
                float a = 1f - Mathf.SmoothStep(0f, 1f, (since - 2.5f) / 3f);
                if (a > 0.01f) Ui.Fill(new Rect(0, 0, Screen.width, Screen.height), new Color(0.012f, 0.018f, 0.026f, a));
            }
        }

        static void Dim(float a = 0.9f)
        {
            var r = new Rect(0, 0, Screen.width, Screen.height);
            Ui.Fill(r, new Color(0.012f, 0.018f, 0.026f, a));
            Ui.Block(r);
        }

        string StatusLine()
        {
            if (launcher == null) return "";
            return launcher.Status switch
            {
                SimLauncher.State.NotFound => "<color=#ff8a7a>Simülasyon bulunamadı.</color> " + launcher.LastError,
                SimLauncher.State.External => "<color=#7ff0a8>●</color> Terminalden çalışan bir simülasyona bağlı.",
                SimLauncher.State.Crashed => "<color=#ff8a7a>" + launcher.LastError + "</color>",
                SimLauncher.State.Running => "<color=#7ff0a8>●</color> Simülasyon çalışıyor.",
                SimLauncher.State.Starting => "Simülasyon başlatılıyor…",
                _ => "<color=#7ff0a8>●</color> Simülasyon hazır.",
            };
        }

        void DrawHome()
        {
            float W = Ui.W, H = Ui.H;
            Ui.Gradient(new Rect(0, 0, 1180f * Ui.S, Screen.height), new Color(0.015f, 0.022f, 0.03f, 0.95f));
            Ui.Block(Ui.R(0, 0, 760, H));
            float x = 96f, w = 650f;
            float y = Mathf.Max(48f, (H - 930f) / 2f);
            Ui.Label(Ui.R(x, y, w, 24), "TÜBİTAK 2204-A · LİSE ÖĞRENCİLERİ ARAŞTIRMA PROJELERİ", 15, Ui.Accent, true);
            y += 34;
            const string title = "Sürü İHA'larda Otonom Sürü Zekâsı ile Karar Alma ve Elektronik Harp Direnci";
            float th = Ui.TextHeight(title, 42, w, true);
            Ui.Label(Ui.R(x, y, w, th), title, 42, Ui.Ink, true);
            y += th + 14;
            const string lead = "Karıştırılan, GPS'i aldatılan ve içine saldırgan sızan bir İHA sürüsü görevini lidersiz nasıl sürdürür? " +
                                "10 İHA'lık sürüyü Python'da sıfırdan modelledik, kararlarını burada 3D olarak izliyorsun ve " +
                                "yaklaşık 6000 deney uçuşuyla ölçtük.";
            float lh = Ui.TextHeight(lead, 18.5f, w);
            Ui.Label(Ui.R(x, y, w, lh), lead, 18.5f, Ui.Ink2);
            y += lh + 22;
            float sw = (w - 28f) / 3f;
            Ui.Stat(Ui.R(x, y, sw, 104), "%100", "20 dBm karıştırmada görev tamamlama · diğerleri %87", Ui.Good);
            Ui.Stat(Ui.R(x + sw + 14, y, sw, 104), "%99", "GPS aldatmada görev tamamlama · diğerleri %51-61", Ui.Good);
            Ui.Stat(Ui.R(x + 2 * (sw + 14), y, sw, 104), "%100", "%20 saldırgan İHA'ya karşı · korumasız sürü %0", Ui.Good);
            y += 104 + 30;

            float bw = 450f, bh = 62f;
            if (Ui.Button(Ui.R(x, y, bw, bh + 8), SimConnected && launcher.Status == SimLauncher.State.Running ? "Simülasyona dön" : "Simülasyonu başlat",
                          Ui.Kind.Primary, size: 21, sub: "Önerilen: 20 dBm karıştırıcı, EH dirençli sürü", icon: true))
            {
                if (SimConnected && launcher.Status == SimLauncher.State.Running) Current = Page.Sim;
                else QuickStart();
            }
            y += bh + 8 + 12;
            if (Ui.Button(Ui.R(x, y, bw, bh), "Senaryo seç", sub: "8 elektronik harp senaryosu · mimari ve algoritma seçimi"))
                Go(Page.Scenarios);
            y += bh + 10;
            if (Ui.Button(Ui.R(x, y, bw, bh), "Yan yana karşılaştırma", sub: "Aynı saldırı: solda korumasız, sağda dirençli sürü"))
            {
                compare = true;
                scenario = 4;
                if (strategy == 2) strategy = 1;
                Go(Page.Scenarios);
            }
            y += bh + 10;
            if (Ui.Button(Ui.R(x, y, bw, bh), "Bu proje nedir?", sub: "Problem, yöntem ve bulgular")) Go(Page.About);
            y += bh + 10;
            if (Ui.Button(Ui.R(x, y, bw, bh), "Nasıl kullanılır?", sub: "Kamera, kısayollar ve renklerin anlamı")) Go(Page.Help);
            y += bh + 18;
            if (Ui.Button(Ui.R(x, y, 160, 46), "Çıkış", Ui.Kind.Ghost, size: 16)) Go(Page.Quit);

            Ui.Label(Ui.R(x, H - 62, 900, 24), StatusLine(), 14, Ui.Ink2);
            Ui.Label(Ui.R(x, H - 36, 900, 20), "Python simülasyonu · Unity HDRP · Blender modelleri", 12.5f, Ui.Ink3);
        }

        // Yatay seçim düğmeleri; seçilen indeksi döndürür
        int Segments(float x, float y, float segW, string[] items, int sel, Func<int, bool> enabled = null)
        {
            for (int i = 0; i < items.Length; i++)
            {
                bool en = enabled == null || enabled(i);
                if (Ui.Button(Ui.R(x + i * (segW + 6), y, segW, 46), items[i], Ui.Kind.Normal, i == sel, 16, en)) sel = i;
            }
            return sel;
        }

        void DrawScenarios()
        {
            Dim(0.92f);
            float W = Ui.W, H = Ui.H;
            float x0 = 80f, cw = W - 160f;
            float y = Mathf.Max(36f, (H - 1000f) / 2f);
            Ui.Label(Ui.R(x0, y, cw, 46), "Senaryo seç", 34, Ui.Ink, true);
            Ui.Label(Ui.R(x0, y + 48, cw, 26), "Her senaryo aynı 10 İHA'lık sürüyü farklı bir elektronik harp tehdidiyle sınar. " +
                                                "Bir kart seç, ayarları belirle ve başlat.", 17, Ui.Ink2);
            y += 92;

            const float gap = 18f, ch = 176f;
            float cwd = (cw - 3 * gap) / 4f;
            for (int i = 0; i < SwarmScenarios.All.Length; i++)
            {
                var sc = SwarmScenarios.All[i];
                var r = Ui.R(x0 + (i % 4) * (cwd + gap), y + (i / 4) * (ch + gap), cwd, ch);
                bool sel = i == scenario, hover = r.Contains(Event.current.mousePosition);
                Ui.Fill(r, sel ? new Color(0.33f, 0.78f, 1f, 0.13f) : hover ? new Color(0.12f, 0.16f, 0.2f, 0.95f) : new Color(0.06f, 0.08f, 0.11f, 0.95f), 14);
                Ui.Outline(r, sel ? Ui.Accent : Ui.Line, sel ? 2f : 1f, 14);
                float rx = r.x / Ui.S, ry = r.y / Ui.S;
                Ui.Chip(rx + 16, ry + 16, sc.Tag, sc.TagColor, 11.5f);
                Ui.Label(Ui.R(rx + 16, ry + 46, cwd - 32, 30), sc.Title, 21, Ui.Ink, true);
                Ui.Label(Ui.R(rx + 16, ry + 78, cwd - 32, 52), sc.Short, 15, Ui.Ink2);
                float other = Mathf.Max(sc.RefCentral, sc.RefDecentral), low = Mathf.Min(sc.RefCentral, sc.RefDecentral);
                string refText = $"Deneyde dirençli %{Pct(sc.RefResilient)} · diğerleri %{Pct(low)}" + (other - low > 0.6f ? $"-{Pct(other)}" : "");
                Ui.Label(Ui.R(rx + 16, ry + ch - 34, cwd - 32, 22), refText, 13.5f, Ui.Ink3);
                if (GUI.Button(r, GUIContent.none, GUIStyle.none)) scenario = i;
            }
            y += 2 * ch + gap + 26;

            float lx = x0, sx = x0 + 220f, segW = 196f, ix = sx + 3 * (segW + 6) + 24, iw = W - 80f - ix;
            Ui.Label(Ui.R(lx, y + 12, 210, 24), compare ? "Soldaki sürü" : "Karar mimarisi", 16, Ui.Ink2, true);
            strategy = Segments(sx, y, segW, SwarmScenarios.StrategyTitles, strategy, i => !compare || i < 2);
            Ui.Label(Ui.R(ix, y + 2, iw, 46), compare ? "Sağ tarafta hep EH dirençli sürü uçar. Sol taraf için korumasız bir mimari seç."
                                                       : SwarmScenarios.StrategyInfo[strategy], 14.5f, Ui.Ink2);
            y += 60;
            Ui.Label(Ui.R(lx, y + 12, 210, 24), "Görev paylaşımı", 16, Ui.Ink2, true);
            planner = Segments(sx, y, segW, SwarmScenarios.PlannerTitles, planner);
            Ui.Label(Ui.R(ix, y + 2, iw, 46), SwarmScenarios.PlannerInfo[planner], 14.5f, Ui.Ink2);
            y += 60;
            Ui.Label(Ui.R(lx, y + 12, 210, 24), "Görünüm", 16, Ui.Ink2, true);
            int view = Segments(sx, y, segW * 1.5f + 3, new[] { "Tek sürü", "Yan yana karşılaştırma" }, compare ? 1 : 0);
            if (view == 1 && !compare && strategy == 2) strategy = 1;
            compare = view == 1;
            Ui.Label(Ui.R(ix, y + 2, iw, 46), compare ? "Ekran ikiye bölünür; aynı haritada aynı saldırı. Arıza ve yeni hedef iki tarafa aynı uygulanır."
                                                       : "Tek bir sürü uçar; mimariyi ve algoritmayı sen seçersin.", 14.5f, Ui.Ink2);
            y += 60;
            Ui.Label(Ui.R(lx, y + 12, 210, 24), "Hız", 16, Ui.Ink2, true);
            fast = Segments(sx, y, segW, new[] { "Normal", "Hızlı" }, fast ? 1 : 0) == 1;
            Ui.Label(Ui.R(ix, y + 2, iw, 46), fast ? "Simülasyon gerçeğin 6 katı hızda akar (bir uçuş yaklaşık 40 saniye)."
                                                   : "Simülasyon gerçeğin 3 katı hızda akar (bir uçuş yaklaşık 1-1,5 dakika).", 14.5f, Ui.Ink2);
            y += 72;

            var sel2 = SwarmScenarios.All[scenario];
            float boxW = cw - 440f;
            float wh = Ui.TextHeight(sel2.Watch, 16, boxW - 36);
            var box = Ui.R(x0, y, boxW, wh + 56);
            Ui.Fill(box, new Color(1f, 1f, 1f, 0.05f), 14);
            Ui.Chip(x0 + 18, y + 14, "BU SENARYODA NE İZLEMELİSİN?", Ui.Accent, 11.5f);
            Ui.Label(Ui.R(x0 + 18, y + 44, boxW - 36, wh + 4), sel2.Watch, 16, Ui.Ink);
            float bx = x0 + cw - 410f;
            if (Ui.Button(Ui.R(bx, y + 4, 150, 58), "Geri", Ui.Kind.Ghost, size: 17)) Current = back;
            if (Ui.Button(Ui.R(bx + 166, y + 4, 244, 58), "Başlat", Ui.Kind.Primary, size: 21, icon: true,
                          enabled: launcher.CanLaunch || launcher.Status == SimLauncher.State.External))
                Launch();
            if (!launcher.CanLaunch)
                Ui.Label(Ui.R(bx, y + 70, 410, 60), StatusLine(), 13, Ui.Ink3);
        }

        static string Pct(float v) => v >= 99.95f ? "100" : v.ToString(v % 1f < 0.05f ? "0" : "0.0").Replace('.', ',');
    }
}
