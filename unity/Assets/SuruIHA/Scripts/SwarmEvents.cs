using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace SuruIHA
{
    // Olay akışı: ardışık kareleri karşılaştırıp önemli anları sade cümlelerle anlatır
    // ("İHA-4'ün GPS'i karıştırıldı", "Sürü karıştırıcının yerini buldu"...). Jüri ekranda ne olduğunu
    // klavye kısayollarını bilmeden takip edebilsin diye.
    public class SwarmEvents : MonoBehaviour
    {
        public struct Ev
        {
            public float real, sim;
            public string text;
            public Color color;
        }

        public static SwarmEvents Instance { get; private set; }
        public readonly List<Ev> Items = new List<Ev>();
        public float MissionDoneAt { get; private set; } = -1f;   // görevlerin bittiği simülasyon saniyesi

        SwarmFrame prev;
        float lastT = -1f;
        int lastSeed = -1;
        string lastStrategy, lastPlanner;
        bool jamFound, jamGood, attackersNamed;
        float liarsSaid = -1f;
        int pendingDone;
        float pendingDoneSince;

        void Awake() => Instance = this;

        // Yeni simülasyon başlatılınca çağrılır. Eski uçuşun son karesi ekranda bir süre daha durur;
        // yeni uçuşun karesi (zaman başa döner) gelene kadar o karelerden olay üretilmez.
        public void Clear()
        {
            Items.Clear();
            prev = null;
            lastT = -1f;
            MissionDoneAt = -1f;
            var vis = Source != null ? Source : SwarmVisualizer.Main;
            staleT = vis != null && vis.Frame != null ? vis.Frame.t : -1f;
        }

        float staleT = -1f;

        void Add(SwarmFrame f, string text, Color c)
        {
            Items.Add(new Ev { real = Time.unscaledTime, sim = f.t, text = text, color = c });
            if (Items.Count > 40) Items.RemoveAt(0);
        }

        static string Names(IEnumerable<int> ids)
        {
            var n = ids.OrderBy(i => i).Select(i => $"İHA-{i + 1}").ToList();
            if (n.Count <= 3) return string.Join(", ", n);
            return $"{n.Count} İHA";
        }

        // Aynı türden olaylar 2,5 saniye biriktirilip tek satırda söylenir
        // (İHA'lar karıştırma bölgesine farklı anlarda girer; her biri için ayrı satır akışı boğar).
        class Bucket
        {
            public readonly HashSet<int> ids = new HashSet<int>();
            public float since;
            public string format;
            public Color color;
        }

        readonly Dictionary<string, Bucket> buckets = new Dictionary<string, Bucket>();

        void Collect(string key, List<int> ids, string format, Color c)
        {
            if (ids.Count == 0) return;
            if (!buckets.TryGetValue(key, out var b)) buckets[key] = b = new Bucket();
            if (b.ids.Count == 0) b.since = Time.unscaledTime;
            b.format = format;
            b.color = c;
            foreach (int i in ids) b.ids.Add(i);
        }

        void Flush(SwarmFrame f, bool all)
        {
            foreach (var b in buckets.Values)
            {
                if (b.ids.Count == 0 || (!all && Time.unscaledTime - b.since < 2.5f)) continue;
                Add(f, string.Format(b.format, Names(b.ids)), b.color);
                b.ids.Clear();
            }
        }

        static string PhaseText(string p, string formation) => p switch
        {
            "intikal" => $"Sürü kalktı ve {formation} düzenine girdi. Lider yok: İHA'lar sanal liderin konumunda uzlaşıyor.",
            "gorev" => "Görev alanına varıldı: İHA'lar dağılıp planladıkları hedeflere gidiyor.",
            "toplanma" => "Hedefler bitti: sürü toplanma noktasında buluşuyor.",
            "donus" => "Sürü düzende üsse dönüyor.",
            "inis" => "İniş başladı.",
            "indi" => "Sürü indi.",
            _ => null,
        };

        // Anlatılan sürü (yan yana karşılaştırmada sağdaki dirençli sürü); boşsa ana sürü
        public SwarmVisualizer Source;

        void Update()
        {
            if (SwarmReceiver.Replaying) return;            // tekrar izlenirken olay akışı donar
            var vis = Source != null ? Source : SwarmVisualizer.Main;
            var f = vis != null ? vis.Frame : null;
            if (f == null || f == prev || f.drones == null) return;
            if (staleT >= 0f)
            {
                if (f.t >= 3f && f.t >= staleT - 0.5f) return;   // hâlâ eski uçuşun karesi
                staleT = -1f;
            }

            // Yeni uçuş: zaman geri gitti, harita ya da senaryo değişti
            bool fresh = prev == null || f.t < lastT - 0.5f || (f.ctl != null && f.ctl.seed != lastSeed) ||
                         f.strategy != lastStrategy || f.planner != lastPlanner;
            if (fresh)
            {
                bool first = prev == null;
                prev = f;
                lastT = f.t;
                lastSeed = f.ctl?.seed ?? -1;
                lastStrategy = f.strategy;
                lastPlanner = f.planner;
                jamFound = jamGood = attackersNamed = false;
                liarsSaid = -1f;
                pendingDone = 0;
                MissionDoneAt = -1f;
                foreach (var b in buckets.Values) b.ids.Clear();
                missileSt.Clear();
                radarFound.Clear();
                intelSaid = windSaid = false;
                Add(f, (first ? "Simülasyon bağlandı: " : "Yeni uçuş: ") +
                       $"{SwarmScenarios.StrategyTitle(f.strategy)}, {SwarmScenarios.PlannerTitle(f.planner, f.strategy)}.", Ui.Accent);
                return;
            }

            var p = prev;
            lastT = f.t;
            if (p.phase != f.phase)
            {
                string s = PhaseText(f.phase, f.formation);
                if (s != null) Add(f, s, Ui.Ink);
            }

            if (!attackersNamed && f.ctl != null && f.ctl.spoof > 0)
            {
                var liars = new List<int>();
                for (int i = 0; i < f.drones.Length; i++) if (f.drones[i].mode == 2) liars.Add(i);
                if (liars.Count > 0)
                {
                    attackersNamed = true;
                    string kind = f.ctl.spoofMode == "sneaky" ? "sinsi" : "saf";
                    Add(f, $"Sürüde {kind} saldırgan var: {Names(liars)} (mor). Yalan bilgi yayacaklar.", Ui.Violet);
                }
            }

            int n = Mathf.Min(f.drones.Length, p.drones.Length);
            var lost = new List<int>();
            var back = new List<int>();
            var search = new List<int>();
            var recover = new List<int>();
            var spoofed = new List<int>();
            var seen = new List<int>();
            var failed = new List<int>();
            var relay = new List<int>();
            var shot = new List<int>();
            var empty = new List<int>();
            var rtb = new List<int>();
            var rwr = new List<int>();
            var locked = new List<int>();
            var evade = new List<int>();
            for (int i = 0; i < n; i++)
            {
                var a = p.drones[i];
                var b = f.drones[i];
                if (b.mode == 2 || b.mode == 4 && a.mode == 4) continue;
                if (b.phase >= 5 && b.mode != 4) continue;   // iniş ve sonrası: yerdeki İHA'nın GPS dalgalanması anlatılmaz
                // Aldatmayı fark edip GPS'i kendisi bırakan İHA (mod 7) "karıştırıldı" diye anlatılmaz
                if (a.gps == 1 && b.gps == 0 && b.mode != 6 && b.mode != 7) lost.Add(i);
                if (a.gps == 0 && b.gps == 1 && b.mode != 6) back.Add(i);
                if (b.mode != a.mode)
                {
                    if (b.mode == 1) search.Add(i);
                    else if (b.mode == 5) recover.Add(i);
                    else if (b.mode == 6) spoofed.Add(i);
                    else if (b.mode == 7) seen.Add(i);
                    else if (b.mode == 4)
                    {
                        if (f.missiles != null && f.missiles.Any(m => m.st == 1 && m.tgt == i)) shot.Add(i);
                        else if (b.bat <= 0.005f) empty.Add(i);
                        else failed.Add(i);
                    }
                    else if (b.mode == 3) relay.Add(i);
                    else if (b.mode == 8) rtb.Add(i);
                    else if (b.mode == 9) evade.Add(i);
                }
                if (b.mode != 4)
                {
                    if (b.rw >= 1 && a.rw == 0) rwr.Add(i);
                    if (b.trk == 1 && a.trk == 0) locked.Add(i);
                }
            }
            bool jammed = f.jammers != null && f.jammers.Length > 0;
            Collect("lost", lost, jammed ? "{0}: GPS karıştırıldı, konumu artık tahminle buluyor."
                                         : "{0}: GPS'i kullanmayı bıraktı, konumu tahminle buluyor.", Ui.Bad);
            Collect("back", back, "{0}: GPS geri geldi.", Ui.Good);
            Collect("search", search, "{0}: hedefi göremedi, \"bitti\" demeden spiral çizerek arıyor.", Ui.Accent);
            Collect("recover", recover, "{0}: konum belirsizliği büyüdü, GPS'i geri almak için bölgeden çıkıyor.", Ui.Warn);
            Collect("spoofed", spoofed, "{0}: GPS'i aldatılıyor, sahte konuma inanıyor.", Ui.Pink);
            Collect("seen", seen, "{0}: aldatmayı fark etti (IMU ile tutmuyor), GPS'e güvenmeyi bıraktı.", Ui.Warn);
            Collect("failed", failed, "{0}: arızalandı. Görevleri diğer İHA'lara geçiyor, düzen yeniden kuruluyor.", Ui.Bad);
            Collect("relay", relay, "{0}: röle oldu, kopan arkadaşıyla bağlantıyı koruyor.", Ui.Cyan);
            Collect("shot", shot, "{0}: hava savunma füzesiyle vuruldu.", Ui.Bad);
            Collect("empty", empty, "{0}: bataryası bitti, eve varamadan düştü.", Ui.Bad);
            Collect("rtb", rtb, f.strategy == "resilient"
                ? "{0}: rüzgâra karşı eve dönüş enerjisini hesapladı, bataryası yetmeden önce eve dönüyor."
                : "{0}: bataryası %10'a indi, eve dönüyor (standart emniyet).", Ui.Ink);
            Collect("rwr", rwr, "{0}: radar ikaz alıcısı huzmeyi duydu, radarın yönünü (kerteriz) ölçüyor.", Ui.Warn);
            Collect("locked", locked, "{0}: radar kilitlendi, izleniyor!", Ui.Bad);
            Collect("evade", evade, "{0}: kilit ikazı aldı, alçalıp radarın görmediği yere kaçıyor.", Ui.Warn);
            Flush(f, false);
            ThreatEvents(f, p);

            if (f.tasks != null && p.tasks != null)
            {
                int m = Mathf.Min(f.tasks.Length, p.tasks.Length);
                for (int i = 0; i < m; i++)
                {
                    int a = p.tasks[i].s, b = f.tasks[i].s;
                    if (a == b) continue;
                    if (a < 0 && b >= 0)
                        Add(f, $"Yeni hedef belirdi (öncelik {f.tasks[i].v}). Sürü yeniden plan yapıyor.", Ui.Violet);
                    else if (b == 2)
                    {
                        if (pendingDone == 0) pendingDoneSince = Time.unscaledTime;
                        pendingDone++;
                    }
                    else if (b == 3)
                        Add(f, $"Hedef {i + 1} yanlışlıkla \"bitti\" sayıldı: İHA konumunu yanlış biliyor.", Ui.Bad);
                }
            }
            if (pendingDone > 0 && Time.unscaledTime - pendingDoneSince > 3f && f.m != null)
            {
                Add(f, $"{pendingDone} hedef tamamlandı · toplam {f.m.done}/{f.m.total}", Ui.Good);
                pendingDone = 0;
            }

            if (f.m != null)
            {
                if (!jamFound && f.m.jamErr >= 0f && f.m.jamErr < 120f)
                {
                    jamFound = true;
                    Add(f, $"Sürü karıştırıcının yerini ölçümlerden buldu (hata {f.m.jamErr:0} m). Karıştırma alanı önceden tahmin ediliyor.", Ui.Good);
                }
                else if (jamFound && !jamGood && f.m.jamErr >= 0f && f.m.jamErr < 50f)
                {
                    jamGood = true;
                    Add(f, $"Karıştırıcı tahmini netleşti: hata {f.m.jamErr:0} m.", Ui.Good);
                }
                if (f.m.liars > 0f && f.m.liars >= liarsSaid + 0.25f)
                {
                    liarsSaid = f.m.liars;
                    Add(f, $"Güven sistemi saldırganları dışlıyor: dürüst İHA'ların %{f.m.liars * 100:0}'ı onlara artık güvenmiyor.", Ui.Good);
                }
            }
            if (f.ctl != null && p.ctl != null && f.ctl.missionDone == 1 && p.ctl.missionDone == 0)
            {
                MissionDoneAt = f.t;
                // Sürü kalan hedefleri yapamadığı ya da bilerek bıraktığı için de görev bitebilir (boşta kalma)
                if (f.m.done >= f.m.total)
                    Add(f, $"Bütün hedefler tamam: görev puanı {f.m.score * 100:0}/100. Sürü üsse dönüyor.", Ui.Good);
                else
                    Add(f, $"Görev bitti: {f.m.done}/{f.m.total} hedef yapıldı, kalanlar bırakıldı (puan {f.m.score * 100:0}/100). Sürü üsse dönüyor.", Ui.Warn);
            }
            prev = f;
        }

        // Hava savunma ve rüzgâr olayları: radar açıldı, istihbarat, füze atıldı / ıskaladı, radar bulundu
        readonly Dictionary<int, int> missileSt = new Dictionary<int, int>();
        readonly HashSet<int> radarFound = new HashSet<int>();
        bool intelSaid, windSaid;

        void ThreatEvents(SwarmFrame f, SwarmFrame p)
        {
            bool res = f.strategy == "resilient";
            if (!windSaid && f.wind != null && f.wind.Length >= 2)
            {
                float s = new Vector2(f.wind[0], f.wind[1]).magnitude;
                if (s > 1.5f)
                {
                    windSaid = true;
                    Add(f, $"Rüzgâr {s:0} m/s, {SwarmHud.WindFrom(f.wind)} esiyor: üsse dönüş karşı rüzgârla, yavaş ve pahalı olacak.", Ui.Ink);
                }
            }
            if (f.radars == null) return;
            if (!intelSaid && f.radars.Any(r => r.known == 1))
            {
                intelSaid = true;
                Add(f, res ? "İstihbarat: hava savunma radarının yeri biliniyor. Sürü rotasını ve toplanma yerini radarın görmediği yerden planladı."
                           : "Bölgede hava savunma radarı var. Bu sürü radarı hesaba katmadan düz uçacak.", Ui.Warn);
            }
            if (p.radars != null)
                for (int k = 0; k < Mathf.Min(f.radars.Length, p.radars.Length); k++)
                    if (f.radars[k].on == 1 && p.radars[k].on == 0 && f.radars[k].known == 0)
                        Add(f, "Pusu! Görev alanının yakınında gizli bir hava savunma radarı açıldı.", Ui.Bad);
            if (f.missiles != null)
                foreach (var m in f.missiles)
                {
                    bool had = missileSt.TryGetValue(m.id, out int old);
                    if (!had) Add(f, $"Hava savunma füze attı: hedef İHA-{m.tgt + 1}.", Ui.Bad);
                    else if (m.st == 2 && old == 0) Add(f, $"Füze ıskaladı: İHA-{m.tgt + 1} radarın izini kopardı.", Ui.Good);
                    missileSt[m.id] = m.st;
                }
            if (res && f.radarEst != null)
                foreach (var e in f.radarEst)
                {
                    if (e.intel == 1 || radarFound.Contains(e.id) || e.id < 0 || e.id >= f.radars.Length) continue;
                    radarFound.Add(e.id);
                    var q = f.radars[e.id].p;
                    float err = new Vector2(e.p[0] - q[0], e.p[1] - q[1]).magnitude;
                    Add(f, f.radars[e.id].known == 1
                        ? $"Kerteriz ölçümleri bilinen radarın yerini düzeltti (hata {err:0} m)."
                        : $"Sürü pusu radarının yerini kerterizlerin kesişiminden buldu (hata {err:0} m). Rotalar yeniden planlanıyor.", Ui.Good);
                }
        }
    }
}
