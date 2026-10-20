using UnityEngine;

namespace SuruIHA
{
    // Ekrandaki bilgi paneli: strateji, görev ilerlemesi, haberleşme ve GPS durumu,
    // renk açıklamaları ve kısayollar. H ile gizlenir/gösterilir.
    public class SwarmHud : MonoBehaviour
    {
        public SwarmVisualizer visualizer;
        public SwarmCamera cam;
        public bool visible = true;

        GUIStyle box, title, label, small, value;
        Texture2D bg, bar, barFill;
        float scale = 1f;

        static string PhaseName(string p) => p switch
        {
            "kalkis" => "kalkış",
            "intikal" => "intikal (düzende)",
            "gorev" => "görev",
            "toplanma" => "toplanma",
            "donus" => "dönüş (düzende)",
            "inis" => "iniş",
            "indi" => "indi",
            _ => p ?? "-",
        };

        static string StrategyName(string s) => s switch
        {
            "centralized" => "MERKEZİ (YER İSTASYONU)",
            "decentralized" => "MERKEZİYETSİZ",
            "resilient" => "MERKEZİYETSİZ + EH DİRENCİ",
            _ => s?.ToUpperInvariant() ?? "-",
        };

        static string PlannerName(string p, string strategy) => p switch
        {
            "greedy" => "açgözlü tek görev",
            "cbba" => strategy == "centralized" ? "SGA (merkezi paket)" : "CBBA paket planlama",
            "ai" => "CBBA + yapay zekâ",
            _ => p ?? "-",
        };

        void Start()
        {
            if (visualizer == null) visualizer = FindAnyObjectByType<SwarmVisualizer>();
            if (cam == null) cam = FindAnyObjectByType<SwarmCamera>();
        }

        void Update()
        {
            if (SwarmInput.Down(SwarmInput.K.H)) visible = !visible;
            if (SwarmInput.Down(SwarmInput.K.Esc) && !Application.isEditor) Application.Quit();   // uygulamadan çık
            if (visualizer == null) return;
            if (SwarmInput.Down(SwarmInput.K.L)) visualizer.showLinks = !visualizer.showLinks;
            if (SwarmInput.Down(SwarmInput.K.G)) visualizer.showEstimates = !visualizer.showEstimates;
            if (SwarmInput.Down(SwarmInput.K.J)) visualizer.showJamMap = !visualizer.showJamMap;
            if (SwarmInput.Down(SwarmInput.K.B)) visualizer.showBeacons = !visualizer.showBeacons;
            if (SwarmInput.Down(SwarmInput.K.P)) visualizer.showPlans = !visualizer.showPlans;
            // Grafik kalitesi: Yüksek (hacimsel sis, bulut gölgesi) -> Dengeli -> Performans
            if (SwarmInput.Down(SwarmInput.K.K))
            {
                int n = QualitySettings.names.Length;
                QualitySettings.SetQualityLevel((QualitySettings.GetQualityLevel() + 1) % n, true);
            }

            // Senaryo komutları (Python yeniden başlatılmadan değişir)
            var rx = visualizer.Receiver;
            if (rx == null) return;
            if (SwarmInput.Down(SwarmInput.K.F1)) rx.SendCommand("{\"cmd\":\"strategy\",\"value\":\"centralized\"}");
            if (SwarmInput.Down(SwarmInput.K.F2)) rx.SendCommand("{\"cmd\":\"strategy\",\"value\":\"decentralized\"}");
            if (SwarmInput.Down(SwarmInput.K.F3)) rx.SendCommand("{\"cmd\":\"strategy\",\"value\":\"resilient\"}");
            if (SwarmInput.Down(SwarmInput.K.F4)) rx.SendCommand("{\"cmd\":\"planner\"}");
            if (SwarmInput.Down(SwarmInput.K.Y)) rx.SendCommand("{\"cmd\":\"popup\"}");
            if (SwarmInput.Down(SwarmInput.K.Plus)) rx.SendCommand("{\"cmd\":\"jammer\",\"step\":1}");
            if (SwarmInput.Down(SwarmInput.K.Minus)) rx.SendCommand("{\"cmd\":\"jammer\",\"step\":-1}");
            if (SwarmInput.Down(SwarmInput.K.X)) rx.SendCommand("{\"cmd\":\"spoof\"}");
            if (SwarmInput.Down(SwarmInput.K.N)) rx.SendCommand("{\"cmd\":\"restart\"}");
            if (SwarmInput.Down(SwarmInput.K.V)) rx.SendCommand("{\"cmd\":\"formation\"}");
            if (SwarmInput.Down(SwarmInput.K.Z)) rx.SendCommand("{\"cmd\":\"fail\"}");
        }

        static Texture2D Tex(Color c)
        {
            var t = new Texture2D(1, 1);
            t.SetPixel(0, 0, c);
            t.Apply();
            return t;
        }

        void Styles()
        {
            float s = Mathf.Clamp(Screen.height / 1080f, 0.75f, 2f);
            if (box != null && Mathf.Approximately(s, scale)) return;
            scale = s;
            bg ??= Tex(new Color(0.03f, 0.05f, 0.07f, 0.78f));
            bar ??= Tex(new Color(1f, 1f, 1f, 0.12f));
            barFill ??= Tex(new Color(0.2f, 0.95f, 0.55f, 0.9f));
            box = new GUIStyle { normal = { background = bg }, padding = new RectOffset(18, 18, 14, 14) };
            title = new GUIStyle { fontSize = (int)(15 * s), fontStyle = FontStyle.Bold, wordWrap = true, normal = { textColor = new Color(0.55f, 0.85f, 1f) } };
            label = new GUIStyle { fontSize = (int)(14 * s), normal = { textColor = new Color(0.82f, 0.86f, 0.9f) } };
            value = new GUIStyle(label) { alignment = TextAnchor.UpperRight, fontStyle = FontStyle.Bold, normal = { textColor = Color.white } };
            small = new GUIStyle { fontSize = (int)(12 * s), richText = true, wordWrap = true, normal = { textColor = new Color(0.7f, 0.74f, 0.78f) } };
        }

        void OnGUI()
        {
            if (!visible || visualizer == null) return;
            Styles();
            float s = scale, w = 400 * s, line = 22 * s;
            var rx = visualizer.Receiver;
            var f = visualizer.Frame;

            GUILayout.BeginArea(new Rect(16 * s, 16 * s, w, Screen.height - 32 * s));
            GUILayout.BeginVertical(box);
            GUILayout.Label("SÜRÜ İHA · ELEKTRONİK HARP", title);
            GUILayout.Space(6 * s);
            if (rx == null || !rx.Connected || f == null)
            {
                GUILayout.Label("Python bağlantısı bekleniyor…", label);
                GUILayout.Label("Terminalde çalıştır:\n<color=#8fd3ff>python run_live.py</color>", small);
            }
            else
            {
                GUILayout.Label(StrategyName(f.strategy), value);
                Row("Görev paylaşımı", PlannerName(f.planner, f.strategy), line);
                Row("Uçuş evresi", PhaseName(f.phase), line);
                Row("Görev süresi", $"{f.t:0} s", line);
                var m = f.m;
                if (m != null)
                {
                    Row("Tamamlanan görev", $"{m.done} / {m.total}", line);
                    Rect r = GUILayoutUtility.GetRect(w - 36 * s, 8 * s);
                    GUI.DrawTexture(r, bar);
                    GUI.DrawTexture(new Rect(r.x, r.y, r.width * (m.total > 0 ? m.done / (float)m.total : 0), r.height), barFill);
                    GUILayout.Space(6 * s);
                    Row("Görev puanı", $"{m.score * 100:0} / 100", line);
                    Row("Yeni hedef · yeniden plan", $"{m.popups} · {m.reassign}", line);
                    Row("Paket iletim oranı", $"%{m.pdr * 100:0}", line);
                    Row("GPS'i kesilen İHA", $"{m.gpsLost}", line);
                    Row("Ort. konum hatası", $"{m.locErr:0.0} m", line);
                    Row("Yanlış tamamlama", $"{m.falseDone}", line);
                    Row("Gereksiz tekrar ziyaret", $"{m.redundant}", line);
                    Row("Sürü bağlantısı", $"%{m.conn * 100:0}", line);
                    Row("Düzen", $"{f.formation} · hata {m.formErr:0.0} m", line);
                    Row("Uçan İHA · röle", $"{m.alive} · {m.relays}", line);
                }
                if (f.jammers != null && f.jammers.Length > 0)
                    Row("Karıştırıcı", $"{f.jammers[0].pw:0} dBm · ~{f.jammers[0].r:0} m", line);
                else
                    Row("Karıştırıcı", "kapalı", line);
                if (f.ctl != null)
                {
                    Row("Saldırgan İHA", f.ctl.spoof > 0 ? $"%{f.ctl.spoof * 100:0}" : "yok", line);
                    Row("Harita", $"#{f.ctl.seed}", line);
                    if (f.ctl.finished == 1)
                        GUILayout.Label("<color=#33ff73><b>SÜRÜ İNDİ</b></color> · [N] yeni harita", small);
                    else if (f.ctl.missionDone == 1)
                        GUILayout.Label("<color=#33ff73><b>GÖREVLER BİTTİ</b></color> · sürü üsse dönüyor", small);
                }
            }
            GUILayout.Space(10 * s);
            GUILayout.Label("<b>İHA ışığı</b>  <color=#26ff8c>●</color> normal  <color=#ff9e1a>●</color> karıştırılıyor  " +
                            "<color=#ff2e26>●</color> GPS yok  <color=#4099ff>●</color> arıyor  <color=#cc40ff>●</color> saldırgan  <color=#1af2ff>●</color> röle  <color=#555555>●</color> arızalı", small);
            GUILayout.Label("<b>Görev</b>  <color=#d9e0f2>●</color> açık  <color=#ffc733>●</color> yolda  " +
                            "<color=#33ff73>●</color> tamam  <color=#ff2640>●</color> yanlış tamam  <color=#bf4dff>●</color> yeni, sürü bilmiyor  " +
                            "· halka sayısı = öncelik (1-3) · renkli çizgi = İHA'nın planı", small);
            GUILayout.Label("<b>Bağlantı</b>  <color=#26ff8c>━</color> sağlam → <color=#ff1f14>━</color> karıştırılmış   " +
                            "<color=#ff5a4d>○</color> İHA'nın sandığı konum", small);
            GUILayout.Space(6 * s);
            string camName = cam == null ? "-" : cam.mode switch
            {
                SwarmCamera.Mode.Cinematic => "sinematik",
                SwarmCamera.Mode.Orbit => "serbest",
                SwarmCamera.Mode.Follow => $"takip İHA-{cam.FollowIndex + 1}",
                _ => "taktik",
            };
            string[] qn = { "Yüksek", "Dengeli", "Performans" };
            int ql = QualitySettings.GetQualityLevel();
            GUILayout.Label($"Grafik: <b>{(ql < qn.Length ? qn[ql] : QualitySettings.names[ql])}</b> [K] değiştir · " +
                            $"{1f / Mathf.Max(Time.smoothDeltaTime, 1e-4f):0} FPS", small);
            GUILayout.Label($"Kamera: <b>{camName}</b>   [C] sinematik [O] serbest [F/Tab/1-9] takip [T] taktik\n" +
                            "[L] bağlantılar  [G] konum hayaletleri  [J] karıştırma haritası  [B] uzak işaretler  [P] planlar  [H] paneli gizle  [Esc] çıkış\n" +
                            "<b>Senaryo</b>  [F1] merkezi [F2] merkeziyetsiz [F3] dirençli  [F4] planlama algoritması  [+/-] karıştırıcı  [X] saldırgan  " +
                            "[N] yeni harita  [V] düzen  [Z] arıza  [Y] yeni hedef", small);
            GUILayout.EndVertical();
            GUILayout.EndArea();
        }

        void Row(string k, string v, float h)
        {
            GUILayout.BeginHorizontal(GUILayout.Height(h));
            GUILayout.Label(k, label);
            GUILayout.FlexibleSpace();
            GUILayout.Label(v, value);
            GUILayout.EndHorizontal();
        }
    }
}
