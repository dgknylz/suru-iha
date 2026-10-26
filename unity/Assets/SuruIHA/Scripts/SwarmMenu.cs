using System;
using System.Linq;
using UnityEngine;

namespace SuruIHA
{
    // Yarışma uygulaması: üstte sekmeler (Proje, Nasıl çalışır?, Kullanılanlar, Bulgular, Simülasyon, Uçuş raporu, Kullanım),
    // simülasyon sırasında araç çubuğu, olay akışı, renk açıklamaları, görev sonu ekranı ve Esc menüsü.
    // Simülasyonu (Python) SimLauncher başlatır; terminal açmaya gerek yoktur.
    // Sekmeler ←/→ ya da PageUp/PageDown ile de değişir (sunum kumandası).
    public partial class SwarmMenu : MonoBehaviour
    {
        public enum Page { Menu, Sim, Pause, Quit }
        public enum Tab { Proje, Nasil, Kullanilanlar, Bulgular, Simulasyon, Rapor, Kullanim }

        static readonly string[] TabNames = { "Proje", "Nasıl çalışır?", "Kullanılanlar", "Bulgular", "Simülasyon", "Uçuş raporu", "Kullanım" };

        public static SwarmMenu Instance { get; private set; }
        public Page Current { get; private set; } = Page.Menu;
        public Tab CurrentTab { get; private set; } = Tab.Proje;
        public bool HidesHud => Current == Page.Menu || Current == Page.Quit;
        public string RunningTitle => running?.Title;

        const float BarH = 76f;     // üst sekme çubuğunun yüksekliği
        Page beforeQuit = Page.Menu;
        int scenario = 1, strategy = 2, planner = 1, seed;
        bool compare, fast;
        Scenario running;
        int runStrategy = 2;
        bool runCompare;
        bool bannerOpen, legendOpen, feedOpen = true, wasRunning, wasTpp;
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
            LoadLayers();
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, "-suruUiTest");
            if (i >= 0) StartCoroutine(UiTest(i + 1 < args.Length ? args[i + 1] : "UiTest"));
        }

        public void OpenMenu(Tab t)
        {
            CurrentTab = t;
            Current = Page.Menu;
        }

        void Go(Page p)
        {
            if (p == Page.Quit) beforeQuit = Current;
            Current = p;
        }

        bool SimConnected => SwarmVisualizer.Main != null && SwarmVisualizer.Main.Receiver != null &&
                             SwarmVisualizer.Main.Receiver.Connected;

        bool SimRunning => SimConnected && launcher != null &&
                           (launcher.Status == SimLauncher.State.Running || launcher.Status == SimLauncher.State.External);

        void Update()
        {
            Ui.Modal = Current != Page.Sim;
            if (SwarmInput.Down(SwarmInput.K.Esc))
            {
                switch (Current)
                {
                    case Page.Sim: Go(Page.Pause); break;
                    case Page.Pause: Current = Page.Sim; break;
                    case Page.Quit: Current = beforeQuit; break;
                    case Page.Menu: if (SimRunning) Current = Page.Sim; break;
                }
            }
            if (Current == Page.Menu)
            {
                int n = TabNames.Length;
                if (SwarmInput.Down(SwarmInput.K.Right) || SwarmInput.Down(SwarmInput.K.PageDown)) CurrentTab = (Tab)(((int)CurrentTab + 1) % n);
                if (SwarmInput.Down(SwarmInput.K.Left) || SwarmInput.Down(SwarmInput.K.PageUp)) CurrentTab = (Tab)(((int)CurrentTab + n - 1) % n);
            }
            if (Current == Page.Sim && SwarmInput.Down(SwarmInput.K.I)) legendOpen = !legendOpen;
            SaveLayersIfChanged();
            NoteReport();

            // İHA kamerasına geçince senaryo kutusu küçülür (İHA bilgi kartına yer açılır)
            bool tppNow = cam != null && cam.mode == SwarmCamera.Mode.Follow;
            if (tppNow && !wasTpp) bannerOpen = false;
            wasTpp = tppNow;

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
            runCompare = false;
            OpenMenu(Tab.Proje);
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
                case Page.Menu: DrawMenu(); break;
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
                SimLauncher.State.External => "<color=#7ff0a8>●</color> Terminalden çalışan bir simülasyona bağlı",
                SimLauncher.State.Crashed => "<color=#ff8a7a>" + launcher.LastError + "</color>",
                SimLauncher.State.Running => "<color=#7ff0a8>●</color> Simülasyon çalışıyor",
                SimLauncher.State.Starting => "Simülasyon başlatılıyor…",
                _ => "<color=#7ff0a8>●</color> Simülasyon hazır",
            };
        }

        void DrawMenu()
        {
            if (CurrentTab == Tab.Proje)
            {
                // Proje sekmesi: sağda 3D sahne görünür, solda koyu geçiş
                Ui.Gradient(new Rect(0, 0, 1180f * Ui.S, Screen.height), new Color(0.015f, 0.022f, 0.03f, 0.95f));
                Ui.Block(Ui.R(0, 0, 780, Ui.H));
            }
            else Dim(0.93f);
            switch (CurrentTab)
            {
                case Tab.Proje: DrawProjeTab(); break;
                case Tab.Nasil: DrawNasilTab(); break;
                case Tab.Kullanilanlar: DrawKullanilanlarTab(); break;
                case Tab.Bulgular: DrawBulgularTab(); break;
                case Tab.Simulasyon: DrawSimulasyonTab(); break;
                case Tab.Rapor: DrawRaporTab(); break;
                case Tab.Kullanim: DrawKullanimTab(); break;
            }
            DrawTopBar();
        }

        void DrawTopBar()
        {
            var bar = Ui.R(0, 0, Ui.W, BarH);
            Ui.Fill(bar, new Color(0.018f, 0.026f, 0.036f, 0.9f));
            Ui.Fill(Ui.R(0, BarH - 1, Ui.W, 1), Ui.Line);
            Ui.Block(bar);
            Ui.Label(Ui.R(40, 14, 200, 30), "SÜRÜ İHA", 21, Ui.Ink, true);
            Ui.Label(Ui.R(40, 43, 200, 20), "TÜBİTAK 2204-A", 12, Ui.Accent, true);

            float x = 240f;
            for (int i = 0; i < TabNames.Length; i++)
            {
                bool act = i == (int)CurrentTab;
                float tw = Ui.TextWidth(TabNames[i], 17, true) + 40f;
                var r = Ui.R(x, 0, tw, BarH);
                bool hover = r.Contains(Event.current.mousePosition);
                if (hover && !act) Ui.Fill(Ui.R(x + 6, 14, tw - 12, BarH - 28), new Color(1f, 1f, 1f, 0.06f), 8);
                Ui.Label(r, TabNames[i], 17, act || hover ? Ui.Ink : Ui.Ink2, act, TextAnchor.MiddleCenter);
                if (act) Ui.Fill(Ui.R(x + 14, BarH - 4, tw - 28, 4), Ui.Accent, 2);
                if (GUI.Button(r, GUIContent.none, GUIStyle.none)) CurrentTab = (Tab)i;
                x += tw;
            }

            float rx = Ui.W - 40f - 110f;
            if (Ui.Button(Ui.R(rx, 15, 110, 46), "Çıkış", Ui.Kind.Ghost, size: 15)) Go(Page.Quit);
            rx -= 16f + 250f;
            bool live = SimRunning;
            if (Ui.Button(Ui.R(rx, 15, 250, 46), live ? "Simülasyona dön" : "Simülasyonu başlat", Ui.Kind.Primary, size: 16, icon: true,
                          enabled: live || launcher.CanLaunch))
            {
                if (live) Current = Page.Sim;
                else QuickStart();
            }
            string st = StatusLine();
            if (st.Length > 90) st = st.Substring(0, 88) + "…";
            Ui.Label(Ui.R(x + 20, 15, rx - x - 36, 46), st, 13.5f, Ui.Ink2, false, TextAnchor.MiddleRight);
        }

        // ---------------------------------------------------------------- Proje sekmesi
        void DrawProjeTab()
        {
            float H = Ui.H;
            float x = 96f, w = 660f;
            float y = BarH + Mathf.Max(30f, (H - BarH - 880f) / 2f);
            Ui.Label(Ui.R(x, y, w, 24), "TÜBİTAK 2204-A · LİSE ÖĞRENCİLERİ ARAŞTIRMA PROJELERİ", 15, Ui.Accent, true);
            y += 32;
            const string title = "Sürü İHA'larda Otonom Sürü Zekâsı ile Karar Alma ve Elektronik Harp Direnci";
            float th = Ui.TextHeight(title, 42, w, true);
            Ui.Label(Ui.R(x, y, w, th), title, 42, Ui.Ink, true);
            y += th + 14;
            const string lead = "İHA sürüleri haberleşmeye ve GPS'e bağımlıdır; elektronik harp tam olarak bunları hedef alır. " +
                                "Karıştırılan, GPS'i aldatılan ve içine saldırgan sızan bir sürü görevini lidersiz nasıl sürdürür? " +
                                "10 İHA'lık sürüyü Python'da sıfırdan modelledik, kararlarını burada 3D olarak izliyorsun ve " +
                                "yaklaşık 6000 deney uçuşuyla ölçtük.";
            float lh = Ui.TextHeight(lead, 18.5f, w);
            Ui.Label(Ui.R(x, y, w, lh), lead, 18.5f, Ui.Ink2);
            y += lh + 24;
            float sw = (w - 28f) / 3f;
            Ui.Stat(Ui.R(x, y, sw, 104), "%100", "20 dBm karıştırmada görev tamamlama · diğerleri %87", Ui.Good);
            Ui.Stat(Ui.R(x + sw + 14, y, sw, 104), "%99", "GPS aldatmada görev tamamlama · diğerleri %51-61", Ui.Good);
            Ui.Stat(Ui.R(x + 2 * (sw + 14), y, sw, 104), "%100", "%20 saldırgan İHA'ya karşı · korumasız sürü %0", Ui.Good);
            y += 104 + 30;

            float bw = 460f, bh = 60f;
            bool live = SimRunning;
            if (Ui.Button(Ui.R(x, y, bw, bh + 10), live ? "Simülasyona dön" : "Simülasyonu başlat", Ui.Kind.Primary, size: 21,
                          sub: live ? "Uçuş arkada sürüyor" : "Önerilen: 20 dBm karıştırıcı, EH dirençli sürü", icon: true,
                          enabled: live || launcher.CanLaunch))
            {
                if (live) Current = Page.Sim;
                else QuickStart();
            }
            y += bh + 10 + 12;
            if (Ui.Button(Ui.R(x, y, bw, bh), "Senaryo seç", sub: "8 elektronik harp senaryosu · tek sürü ya da yan yana"))
                CurrentTab = Tab.Simulasyon;
            y += bh + 10;
            if (Ui.Button(Ui.R(x, y, bw, bh), "Nasıl çalışır?", sub: "Sürü zekâsı, otonom karar alma ve EH savunmaları"))
                CurrentTab = Tab.Nasil;
            y += bh + 10;
            if (Ui.Button(Ui.R(x, y, bw, bh), "Bulgular", sub: "Deney sonuçları ve grafikler")) CurrentTab = Tab.Bulgular;

            Ui.Label(Ui.R(x, H - 40, 1000, 22), "Sekmeler arasında ← → ya da sunum kumandasıyla geçebilirsin · Python simülasyonu · Unity HDRP · Blender",
                     12.5f, Ui.Ink3);
        }

        // ---------------------------------------------------------------- Simülasyon sekmesi
        // Yatay seçim düğmeleri; seçilen indeksi döndürür
        int Segments(float x, float y, float segW, string[] items, int sel, Func<int, bool> enabled = null)
        {
            for (int i = 0; i < items.Length; i++)
            {
                bool en = enabled == null || enabled(i);
                if (Ui.Button(Ui.R(x + i * (segW + 6), y, segW, 44), items[i], Ui.Kind.Normal, i == sel, 16, en)) sel = i;
            }
            return sel;
        }

        void DrawSimulasyonTab()
        {
            float W = Ui.W, H = Ui.H;
            float x0 = 80f, cw = W - 160f;
            float y = BarH + Mathf.Max(24f, (H - BarH - 860f) / 2f);
            Ui.Label(Ui.R(x0, y, cw, 28), "Bir senaryo seç, ayarları belirle ve başlat. Her senaryo aynı 10 İHA'lık sürüyü farklı bir " +
                                          "elektronik harp tehdidiyle sınar.", 17, Ui.Ink2);
            y += 42;

            const float gap = 16f, ch = 160f;
            float cwd = (cw - 3 * gap) / 4f;
            for (int i = 0; i < SwarmScenarios.All.Length; i++)
            {
                var sc = SwarmScenarios.All[i];
                var r = Ui.R(x0 + (i % 4) * (cwd + gap), y + (i / 4) * (ch + gap), cwd, ch);
                bool sel = i == scenario, hover = r.Contains(Event.current.mousePosition);
                Ui.Fill(r, sel ? new Color(0.33f, 0.78f, 1f, 0.13f) : hover ? new Color(0.12f, 0.16f, 0.2f, 0.95f) : new Color(0.06f, 0.08f, 0.11f, 0.95f), 14);
                Ui.Outline(r, sel ? Ui.Accent : Ui.Line, sel ? 2f : 1f, 14);
                float rx = r.x / Ui.S, ry = r.y / Ui.S;
                Ui.Chip(rx + 16, ry + 14, sc.Tag, sc.TagColor, 11.5f);
                Ui.Label(Ui.R(rx + 16, ry + 42, cwd - 32, 30), sc.Title, 20, Ui.Ink, true);
                Ui.Label(Ui.R(rx + 16, ry + 72, cwd - 32, 50), sc.Short, 15, Ui.Ink2);
                float other = Mathf.Max(sc.RefCentral, sc.RefDecentral), low = Mathf.Min(sc.RefCentral, sc.RefDecentral);
                string refText = $"Deneyde dirençli %{Pct(sc.RefResilient)} · diğerleri %{Pct(low)}" + (other - low > 0.6f ? $"-{Pct(other)}" : "");
                Ui.Label(Ui.R(rx + 16, ry + ch - 32, cwd - 32, 22), refText, 13.5f, Ui.Ink3);
                if (GUI.Button(r, GUIContent.none, GUIStyle.none)) scenario = i;
            }
            y += 2 * ch + gap + 24;

            float lx = x0, sx = x0 + 220f, segW = 196f, ix = sx + 3 * (segW + 6) + 24, iw = W - 80f - ix;
            Ui.Label(Ui.R(lx, y + 11, 210, 24), compare ? "Soldaki sürü" : "Karar mimarisi", 16, Ui.Ink2, true);
            strategy = Segments(sx, y, segW, SwarmScenarios.StrategyTitles, strategy, i => !compare || i < 2);
            Ui.Label(Ui.R(ix, y + 1, iw, 46), compare ? "Sağ tarafta hep EH dirençli sürü uçar. Sol taraf için korumasız bir mimari seç."
                                                       : SwarmScenarios.StrategyInfo[strategy], 14.5f, Ui.Ink2);
            y += 54;
            Ui.Label(Ui.R(lx, y + 11, 210, 24), "Görev paylaşımı", 16, Ui.Ink2, true);
            planner = Segments(sx, y, segW, SwarmScenarios.PlannerTitles, planner);
            Ui.Label(Ui.R(ix, y + 1, iw, 46), SwarmScenarios.PlannerInfo[planner], 14.5f, Ui.Ink2);
            y += 54;
            Ui.Label(Ui.R(lx, y + 11, 210, 24), "Görünüm", 16, Ui.Ink2, true);
            int view = Segments(sx, y, segW * 1.5f + 3, new[] { "Tek sürü", "Yan yana karşılaştırma" }, compare ? 1 : 0);
            if (view == 1 && !compare && strategy == 2) strategy = 1;
            compare = view == 1;
            Ui.Label(Ui.R(ix, y + 1, iw, 46), compare ? "Ekran ikiye bölünür; aynı haritada aynı saldırı. Arıza ve yeni hedef iki tarafa aynı uygulanır."
                                                       : "Tek bir sürü uçar; mimariyi ve algoritmayı sen seçersin.", 14.5f, Ui.Ink2);
            y += 54;
            Ui.Label(Ui.R(lx, y + 11, 210, 24), "Hız", 16, Ui.Ink2, true);
            fast = Segments(sx, y, segW, new[] { "Normal", "Hızlı" }, fast ? 1 : 0) == 1;
            Ui.Label(Ui.R(ix, y + 1, iw, 46), fast ? "Simülasyon gerçeğin 6 katı hızda akar (bir uçuş yaklaşık 40 saniye)."
                                                   : "Simülasyon gerçeğin 3 katı hızda akar (bir uçuş yaklaşık 1-1,5 dakika).", 14.5f, Ui.Ink2);
            y += 66;

            var sel2 = SwarmScenarios.All[scenario];
            float boxW = cw - 300f;
            float wh = Ui.TextHeight(sel2.Watch, 16, boxW - 36);
            var box = Ui.R(x0, y, boxW, wh + 56);
            Ui.Fill(box, new Color(1f, 1f, 1f, 0.05f), 14);
            Ui.Chip(x0 + 18, y + 14, "BU SENARYODA NE İZLEMELİSİN?", Ui.Accent, 11.5f);
            Ui.Label(Ui.R(x0 + 18, y + 44, boxW - 36, wh + 4), sel2.Watch, 16, Ui.Ink);
            float bx = x0 + cw - 270f;
            if (Ui.Button(Ui.R(bx, y + 4, 270, 64), "Başlat", Ui.Kind.Primary, size: 22, icon: true,
                          enabled: launcher.CanLaunch || launcher.Status == SimLauncher.State.External))
                Launch();
            if (!launcher.CanLaunch)
                Ui.Label(Ui.R(bx - 140, y + 76, 410, 80), StatusLine(), 13, Ui.Ink3);
        }

        static string Pct(float v) => v >= 99.95f ? "100" : v.ToString(v % 1f < 0.05f ? "0" : "0.0").Replace('.', ',');
    }
}
