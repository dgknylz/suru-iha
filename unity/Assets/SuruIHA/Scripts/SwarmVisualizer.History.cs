using System.Collections.Generic;

namespace SuruIHA
{
    // Uçuş boyunca ölçümler (canlı grafikler ve uçuş raporu): simülasyon zamanında yarım saniyede bir örnek.
    // Yeni uçuş başlayınca (zaman geri gidince) sıfırlanır; uçuş raporu geldiğinde o uçuşun kopyası saklanır.
    public partial class SwarmVisualizer
    {
        public struct MetricSample
        {
            public float t;          // simülasyon zamanı (s)
            public float pdr;        // paket iletimi (0-1)
            public float gpsLost;    // GPS'siz uçan İHA sayısı (karıştırılan ya da GPS'e güvenmeyen)
            public float score;      // görev puanı (0-1)
            public float done;       // tamamlanan hedef
            public float alive;      // uçabilen İHA
        }

        public readonly List<MetricSample> History = new List<MetricSample>();
        public int HistoryVersion { get; private set; }
        public List<MetricSample> ReportHistory { get; private set; }
        int droneCount;
        public int DroneCount => droneCount;

        void RecordMetrics(SwarmFrame f)
        {
            if (f.m == null) return;
            if (f.drones != null) droneCount = f.drones.Length;
            if (History.Count > 0 && f.t < History[History.Count - 1].t - 0.5f) History.Clear();   // yeni uçuş
            if (History.Count > 0 && f.t - History[History.Count - 1].t < 0.5f) return;
            History.Add(new MetricSample
            {
                t = f.t, pdr = f.m.pdr, gpsLost = f.m.gpsLost, score = f.m.score, done = f.m.done, alive = f.m.alive,
            });
            if (History.Count > 4000) History.RemoveRange(0, 1000);
            HistoryVersion++;
        }
    }
}
