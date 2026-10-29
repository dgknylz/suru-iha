using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

namespace SuruIHA
{
    // Python'un UDP ile yolladığı kareleri arka plan iş parçacığında dinler.
    // Ana iş parçacığında (Update) en son kareyi JSON'dan çözer.
    public class SwarmReceiver : MonoBehaviour
    {
        public int port = 5065;
        [Tooltip("Python'un klavye komutlarını dinlediği port (senaryo değiştirme)")]
        public int commandPort = 5066;

        public SwarmFrame Latest { get; private set; }
        public float LastFrameTime { get; private set; } = -999f;
        public int FramesReceived { get; private set; }
        public bool Connected => Time.time - LastFrameTime < 1.5f;

        UdpClient client;
        Thread thread;
        volatile bool running;
        string pending;
        readonly object locker = new object();

        void OnEnable()
        {
            try
            {
                client = new UdpClient(port);
                client.Client.ReceiveBufferSize = 1 << 20;
                running = true;
                thread = new Thread(Listen) { IsBackground = true, Name = "SwarmUDP" };
                thread.Start();
                Debug.Log($"[SuruIHA] UDP {port} portu dinleniyor. Python: python run_live.py");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[SuruIHA] UDP portu açılamadı ({port}): {ex.Message}");
            }
        }

        void Listen()
        {
            var endpoint = new IPEndPoint(IPAddress.Any, 0);
            while (running)
            {
                try
                {
                    byte[] data = client.Receive(ref endpoint);
                    string json = Encoding.UTF8.GetString(data);
                    lock (locker) pending = json;   // sadece en yeni kare önemli
                }
                catch (SocketException) { if (!running) break; }
                catch (ObjectDisposedException) { break; }
            }
        }

        // Film modu: kaydedilmiş kareyi UDP yerine doğrudan verir
        public void Feed(SwarmFrame f)
        {
            Latest = f;
            LastFrameTime = Time.time;
            FramesReceived++;
        }

        // Film modu: bu kaynak artık yayın yapmıyor (karşılaştırma ekranı hemen kapansın)
        public void Disconnect() => LastFrameTime = -999f;

        // Python'a senaryo komutu yolla (ör. {"cmd":"strategy","value":"centralized"})
        public void SendCommand(string json)
        {
            if (client == null) return;
            try
            {
                var bytes = Encoding.UTF8.GetBytes(json);
                client.Send(bytes, bytes.Length, "127.0.0.1", commandPort);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[SuruIHA] Komut gönderilemedi: " + ex.Message);
            }
        }

        // ------------------------------------------------------------------ uçuş tekrarı (SwarmMenu.Replay.cs)
        // Canlı kareler simülasyon zamanında 0,2 s'de bir saklanır (yeni uçuş başlayınca, yani zaman geri gidince sıfırlanır).
        // Tekrar sırasında (Replaying) gelen canlı kareler kaydedilir ama ekrana uygulanmaz.
        public static bool Replaying;
        readonly List<string> rec = new List<string>();
        readonly List<float> recT = new List<float>();
        public int RecCount => rec.Count;
        public float RecStart => rec.Count > 0 ? recT[0] : 0f;
        public float RecEnd => rec.Count > 0 ? recT[rec.Count - 1] : 0f;
        const int RecMax = 6000;                 // ~20 dakikalık uçuş

        void Record(string json)
        {
            // Kare {"t": 12.3, ...} diye başlar: zamanı bütün JSON'u çözmeden oku
            int a = json.IndexOf("\"t\":", StringComparison.Ordinal);
            if (a < 0 || a > 8) return;
            int b = json.IndexOf(',', a);
            if (b < 0 || !float.TryParse(json.Substring(a + 4, b - a - 4), NumberStyles.Float, CultureInfo.InvariantCulture, out float t)) return;
            int n = recT.Count;
            if (n > 0 && t < recT[n - 1] - 0.5f) { rec.Clear(); recT.Clear(); n = 0; }
            if (n > 0 && t < recT[n - 1] + 0.2f) return;
            if (n >= RecMax) return;
            rec.Add(json);
            recT.Add(t);
        }

        // Zamanı t'yi geçmeyen son kaydın sırası
        public int RecIndexAt(float t)
        {
            int lo = 0, hi = recT.Count - 1;
            if (hi < 0) return -1;
            while (lo < hi)
            {
                int mid = (lo + hi + 1) / 2;
                if (recT[mid] <= t) lo = mid; else hi = mid - 1;
            }
            return lo;
        }

        public float RecTime(int k) => recT[k];

        public SwarmFrame RecFrame(int k)
        {
            try { return JsonUtility.FromJson<SwarmFrame>(rec[k]); }
            catch (Exception) { return null; }
        }

        void Update()
        {
            string json;
            lock (locker) { json = pending; pending = null; }
            if (json == null) return;
            Record(json);
            if (Replaying) return;
            try
            {
                Latest = JsonUtility.FromJson<SwarmFrame>(json);
                LastFrameTime = Time.time;
                FramesReceived++;
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[SuruIHA] Kare çözülemedi: " + ex.Message);
            }
        }

        void OnDisable()
        {
            running = false;
            client?.Close();
            client = null;
            thread?.Join(200);
        }
    }
}
