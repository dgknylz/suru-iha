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
        public int mode;       // 0 normal, 1 spiral arama, 2 saldırgan, 3 röle, 4 arızalı, 5 GPS kurtarma,
                               // 6 GPS'i aldatılıyor (henüz fark etmedi), 7 aldatmayı fark etti (GPS'e güvenmiyor)
        public int phase;      // 0 kalkış, 1 intikal, 2 görev, 3 toplanma, 4 dönüş, 5 iniş, 6 indi
        public int relay;      // röle ise bağlantısını koruduğu İHA (-1: değil)
        public float sigma;    // konum belirsizliği (m)
        public int[] plan;     // planlanan rota: görev numaraları uçuş sırasıyla (ilki şimdiki hedef)
    }

    [Serializable]
    public class TaskState
    {
        public float[] p;
        public int s;          // -1 henüz belirmedi, 0 açık, 1 sahiplenildi, 2 tamamlandı, 3 yanlış tamamlandı
        public int v;          // değer (öncelik) 1-3
        public float age;      // yeni hedefse belireli kaç saniye oldu (-1: baştan beri var)
        public int k;          // 1 = sürü bu hedefin varlığını biliyor
    }

    [Serializable]
    public class JammerState
    {
        public float[] p;
        public float pw;       // güç (dBm)
        public float r;        // etkili yarıçap (m)
        public string band;    // "genis" (haberleşme + GPS) ya da "nokta" (yalnızca haberleşme kanalı)
        public float[] v;      // hız (hareketli karıştırıcı)
    }

    [Serializable]
    public class JamEstState   // sürünün kestirdiği karıştırıcı konumu
    {
        public float[] p;
        public float pw;
        public float r;
    }

    [Serializable]
    public class JamFieldState // karıştırma ısı haritası (yalnızca değişince ve 2 s'de bir gelir)
    {
        public int rev;
        public float x0, y0, step;  // ilk noktanın konumu (doğu, kuzey) ve nokta aralığı (m)
        public int nx, ny;
        public float agl;           // haritanın yüksekliği: yerden uçuş yüksekliği (m)
        public float db0, dbStep;   // bayt -> dBm: db0 + bayt * dbStep
        public float detect;        // İHA'nın karıştırmayı fark ettiği güç (dBm)
        public float cut;           // 60 m'deki komşuyla bağlantının yarısının koptuğu güç (dBm)
        public string q;            // base64, nx*ny bayt; satır = kuzey, sütun = doğu
    }

    [Serializable]
    public class DroneReport   // uçuş raporunda bir İHA
    {
        public int id;
        public int done;           // tamamladığı hedef
        public int wrong;          // yanlış "bitti" (hedefi görmeden bitti dedi)
        public int search;         // spiral arama sayısı
        public int recover;        // GPS'i geri almaya gitme sayısı
        public float dist;         // uçtuğu yol (m)
        public float nogps;        // GPS'siz uçtuğu süre (s)
        public float jam;          // karıştırmayı fark edecek kadar karıştırıldığı süre (s)
        public float relay;        // röle olduğu süre (s)
        public float spoofed;      // GPS'inin aldatıldığı süre (s)
        public int seen;           // 1 = aldatmayı fark etti
        public int liar;           // 1 = saldırgan (ele geçirilmiş) İHA
        public float fail;         // arızalandığı an (s), -1: arızalanmadı
        public int[] xy;           // iz: [x, y, x, y, ...] (3 s'de bir)
        public string st;          // her iz noktasının durumu: n j g s r a p y f (bkz. suru/world.py _status)
    }

    [Serializable]
    public class FlightReport  // uçuş raporu (yalnızca iniş bitince gelir)
    {
        public float t;            // uçuş süresi (s)
        public float mission;      // görevin bittiği an (s)
        public DroneReport[] drones;
        public int[] taskBy;       // her hedefi tamamlayan İHA (-1: yapılmadı)
    }

    [Serializable]
    public class SpooferState  // GPS aldatıcı
    {
        public float[] p;
        public float r;
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
        public float score;    // görev puanı 0-1 (zamanla azalan görev değerleri)
        public int reassign;   // yeniden planlamada yarım bırakılan hedef sayısı
        public int popups;     // şu ana kadar beliren yeni hedef sayısı
        public int falseDone;
        public int redundant;
        public float pdr;
        public float locErr;
        public int gpsLost;
        public float conn;     // en büyük bağlı grubun oranı
        public float formErr;  // düzen hatası (m)
        public int relays;
        public int alive;
        public float jamErr;   // sürünün karıştırıcı konum kestiriminin hatası (m), -1: kestirim yok
        public int spoofed;    // GPS'i şu an aldatılan İHA
        public int spoofSeen;  // aldatmayı fark edip GPS'e güvenmeyen İHA
        public float liars;    // dürüst İHA'ların saldırganları dışlama oranı (-1: saldırgan yok)
    }

    [Serializable]
    public class ControlState
    {
        public float power;    // karıştırıcı gücü (dBm), -1 = kapalı
        public float spoof;    // saldırgan oranı
        public string spoofMode; // saf | sinsi saldırgan ("naive" | "sneaky")
        public string side;      // karşılaştırmada "sol" / "sag"
        public int seed;       // harita numarası
        public int finished;   // 1 = sürü indi, yeni komut bekleniyor
        public int missionDone; // 1 = görevler bitti (sürü dönüşte)
    }

    [Serializable]
    public class SwarmFrame
    {
        public float t;
        public string strategy;
        public string region;      // harita: "ova" (Orta Anadolu ovası) ya da "kar" (karlı dağlar)
        public string planner;     // görev paylaşım algoritması: greedy | cbba | ai
        public string phase;       // sürünün çoğunluğunun evresi
        public string formation;   // intikal düzeni
        public DroneState[] drones;
        public float[] links;      // [i, j, kalite, i, j, kalite, ...]
        public TaskState[] tasks;
        public JammerState[] jammers;
        public JamEstState[] jamEst;
        public SpooferState[] spoofers;
        public int fhss;           // 1 = dirençli sürü frekans atlıyor
        public GcsState gcs;
        public float cell;
        public float[] jamCells;   // [x, y, x, y, ...] sürünün ortak karıştırma haritası
        public JamFieldState jamField;   // gerçek karıştırma gücü haritası (çoğu karede boş)
        public FlightReport report;      // uçuş raporu (iniş bitince ara ara gelir)
        public FrameMetrics m;
        public ControlState ctl;

        // Python: x doğu, y kuzey, z yukarı  ->  Unity: x doğu, y yukarı, z kuzey
        public static Vector3 Enu(float[] a)
        {
            return a == null || a.Length < 3 ? Vector3.zero : new Vector3(a[0], a[2], a[1]);
        }
    }
}
