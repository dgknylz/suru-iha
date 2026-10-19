using System;
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

        void Update()
        {
            string json;
            lock (locker) { json = pending; pending = null; }
            if (json == null) return;
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
