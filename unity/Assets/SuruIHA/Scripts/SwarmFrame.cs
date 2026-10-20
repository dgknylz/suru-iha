using System;
using UnityEngine;

namespace SuruIHA
{
    // Python'dan (suru/world.py -> frame()) gelen JSON karenin C# karşılığı.
    // Alan adları Python tarafındakiyle birebir aynı olmalı.

    [Serializable]
    public class DroneState
    {
        public int id;
        public float[] p;      // gerçek konum (ENU)
        public float[] e;      // İHA'nın sandığı konum (kestirim)
        public float[] v;      // hız
        public float jam;      // 0..1 karıştırma seviyesi
        public int gps;        // 1 = GPS var
        public int task;       // hedef görev (-1 = yok)
        public int mode;       // 0 normal, 1 spiral arama, 2 saldırgan, 3 röle, 4 arızalı
        public int phase;      // 0 kalkış, 1 intikal, 2 görev, 3 toplanma, 4 dönüş, 5 iniş, 6 indi
        public int relay;      // röle ise bağlantısını koruduğu İHA (-1: değil)
        public float sigma;    // konum belirsizliği (m)
    }

    [Serializable]
    public class TaskState
    {
        public float[] p;
        public int s;          // 0 açık, 1 sahiplenildi, 2 tamamlandı, 3 yanlış tamamlandı
    }

    [Serializable]
    public class JammerState
    {
        public float[] p;
        public float pw;       // güç (dBm)
        public float r;        // etkili yarıçap (m)
    }

    [Serializable]
    public class GcsState
    {
        public float[] p;
        public int on;         // merkezi mimaride 1
        public int[] up;       // hangi İHA istasyonla bağlantıda
    }

    [Serializable]
    public class FrameMetrics
    {
        public int done;
        public int total;
        public int falseDone;
        public int redundant;
        public float pdr;
        public float locErr;
        public int gpsLost;
        public float conn;     // en büyük bağlı grubun oranı
        public float formErr;  // düzen hatası (m)
        public int relays;
        public int alive;
    }

    [Serializable]
    public class ControlState
    {
        public float power;    // karıştırıcı gücü (dBm), -1 = kapalı
        public float spoof;    // saldırgan oranı
        public int seed;       // harita numarası
        public int finished;   // 1 = sürü indi, yeni komut bekleniyor
        public int missionDone; // 1 = görevler bitti (sürü dönüşte)
    }

    [Serializable]
    public class SwarmFrame
    {
        public float t;
        public string strategy;
        public string phase;       // sürünün çoğunluğunun evresi
        public string formation;   // intikal düzeni
        public DroneState[] drones;
        public float[] links;      // [i, j, kalite, i, j, kalite, ...]
        public TaskState[] tasks;
        public JammerState[] jammers;
        public GcsState gcs;
        public float cell;
        public float[] jamCells;   // [x, y, x, y, ...] sürünün ortak karıştırma haritası
        public FrameMetrics m;
        public ControlState ctl;

        // Python: x doğu, y kuzey, z yukarı  ->  Unity: x doğu, y yukarı, z kuzey
        public static Vector3 Enu(float[] a)
        {
            return a == null || a.Length < 3 ? Vector3.zero : new Vector3(a[0], a[2], a[1]);
        }
    }
}
