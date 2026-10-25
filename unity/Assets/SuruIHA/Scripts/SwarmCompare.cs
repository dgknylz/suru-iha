using UnityEngine;

namespace SuruIHA
{
    // Yan yana karşılaştırma ekranı (python run_compare.py):
    // UDP 5067'den ikinci bir sürü gelince ekran ikiye bölünür. Sol yarı ana sürüyü (korumasız, 5065),
    // sağ yarı ikinci sürüyü (EH dirençli, 5067) gösterir. İki kamera aynı açıdan bakar; her kamera yalnızca
    // kendi sürüsünü görür (katman maskesi), arazi ve köy ikisinde de ortaktır.
    [DefaultExecutionOrder(1000)]   // SwarmCamera'dan sonra çalışır (kamera konumunu kopyalar)
    public class SwarmCompare : MonoBehaviour
    {
        public const int LayerA = 30, LayerB = 31;   // adsız kullanıcı katmanları (indeksle kullanılabilir)

        public static SwarmCompare Instance { get; private set; }
        public SwarmVisualizer A { get; private set; }
        public SwarmVisualizer B { get; private set; }
        public bool Active { get; private set; }

        Camera mainCam, camB;
        public Camera CamB => Active ? camB : null;
        bool bFollowing;
        SwarmHud hud;
        float nextLayer;
        Texture2D line;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (SwarmVisualizer.Main == null) return;
            new GameObject("Karsilastirma").AddComponent<SwarmCompare>();
        }

        void Awake()
        {
            Instance = this;
            A = SwarmVisualizer.Main;
            hud = FindAnyObjectByType<SwarmHud>();
            var cam = FindAnyObjectByType<SwarmCamera>();
            mainCam = cam != null ? cam.GetComponent<Camera>() : Camera.main;

            // İkinci sürü düzeneği: ana görselleştiricinin modelleri ve malzemeleriyle, kapalıyken kurulur
            var go = new GameObject("SuruB_Direncli");
            go.SetActive(false);
            go.transform.SetParent(A.transform.parent, false);
            var rx = go.AddComponent<SwarmReceiver>();
            rx.port = 5067;
            rx.commandPort = 5066;
            B = go.AddComponent<SwarmVisualizer>();
            B.droneModel = A.droneModel;
            B.jammerModel = A.jammerModel;
            B.gcsModel = A.gcsModel;
            B.gcsModelOffset = A.gcsModelOffset;
            B.droneScale = A.droneScale;
            B.linkWidth = A.linkWidth;
            B.glow = A.glow;
            B.materials = A.materials;
            B.autoGroundSnap = false;
            B.groundMask = A.groundMask;
            go.SetActive(true);
            if (mainCam != null) mainCam.cullingMask &= ~(1 << LayerB);   // tek ekranda ikinci sürü görünmez
        }

        void LateUpdate()
        {
            if (A == null || B == null || mainCam == null) return;
            // İkinci düzenek ana düzenekle aynı yerde durur (ana düzenek zemine oturtulmuş olabilir)
            B.transform.SetPositionAndRotation(A.transform.position, A.transform.rotation);
            B.showLinks = A.showLinks; B.onlyWeakLinks = A.onlyWeakLinks; B.showEstimates = A.showEstimates; B.showJamMap = A.showJamMap;
            B.showBeacons = A.showBeacons; B.showPlans = A.showPlans; B.showTrails = A.showTrails;

            if (Time.unscaledTime > nextLayer)
            {
                nextLayer = Time.unscaledTime + 0.5f;
                SetLayer(A.transform, LayerA);
                SetLayer(B.transform, LayerB);
            }
            bool want = B.Receiver != null && B.Receiver.Connected;
            if (want != Active) Switch(want);
            if (Active && camB != null)
            {
                // İHA kamerasında sağ ekran kendi sürüsündeki aynı numaralı İHA'yı izler (aynı açıyla);
                // diğer kameralarda iki ekran birebir aynı yerden bakar
                var sc = mainCam.GetComponent<SwarmCamera>();
                if (sc != null && sc.mode == SwarmCamera.Mode.Follow && sc.FollowIndex < B.Drones.Count)
                {
                    if (!bFollowing) sc.RigB.Begin(camB.transform.position, camB.transform.rotation);   // süzülerek gelsin
                    bFollowing = true;
                    var (p, r) = sc.RigB.Step(B, B.Drones[sc.FollowIndex], Time.deltaTime, sc.TppYaw, sc.TppPitch, sc.TppDistance);
                    camB.transform.SetPositionAndRotation(p, r);
                }
                else
                {
                    bFollowing = false;
                    camB.transform.SetPositionAndRotation(mainCam.transform.position, mainCam.transform.rotation);
                }
            }
        }

        void Switch(bool on)
        {
            Active = on;
            if (on && camB == null)
            {
                // Ana kameranın kopyası (HDRP kamera ayarları dahil); kontrol betikleri silinir
                var clone = Instantiate(mainCam.gameObject, mainCam.transform.parent);
                clone.name = "KameraB_Direncli";
                foreach (var mb in clone.GetComponents<MonoBehaviour>())
                    if (mb is SwarmCamera || mb is SwarmHud || mb is SwarmCompare) Destroy(mb);
                var al = clone.GetComponent<AudioListener>();
                if (al != null) Destroy(al);
                camB = clone.GetComponent<Camera>();
            }
            if (on)
            {
                mainCam.rect = new Rect(0f, 0f, 0.5f, 1f);
                mainCam.cullingMask = ~(1 << LayerB);
                camB.rect = new Rect(0.5f, 0f, 0.5f, 1f);
                camB.cullingMask = ~(1 << LayerA);
                camB.gameObject.SetActive(true);
                B.ViewCamera = camB;
                if (hud != null) hud.visible = false;    // ayrıntılı panel H ile açılır
            }
            else
            {
                mainCam.rect = new Rect(0f, 0f, 1f, 1f);
                mainCam.cullingMask = ~(1 << LayerB);
                if (camB != null) camB.gameObject.SetActive(false);
                B.ViewCamera = null;
                if (hud != null) hud.visible = true;
            }
        }

        static void SetLayer(Transform t, int layer)
        {
            foreach (var c in t.GetComponentsInChildren<Transform>(true)) c.gameObject.layer = layer;
        }

        static Texture2D Tex(Color c)
        {
            var t = new Texture2D(1, 1);
            t.SetPixel(0, 0, c);
            t.Apply();
            return t;
        }

        static string Name(string s) => s switch
        {
            "centralized" => "MERKEZİ (yer istasyonu)",
            "decentralized" => "MERKEZİYETSİZ (korumasız)",
            "resilient" => "MERKEZİYETSİZ + EH DİRENCİ",
            _ => s ?? "-",
        };

        void OnGUI()
        {
            if (!Active) return;
            line ??= Tex(new Color(1f, 1f, 1f, 0.85f));
            GUI.DrawTexture(new Rect(Screen.width / 2f - 1.5f * Ui.S, 0, 3f * Ui.S, Screen.height), line);
            Panel(A.Frame, 0, new Color(1f, 0.6f, 0.35f));
            Panel(B.Frame, 1, Ui.Good);
            if (SwarmMenu.Instance == null)   // menüsüz modlarda (otomatik test) kısayol hatırlatması
                Ui.Label(Ui.R(0, Ui.H - 34, Ui.W, 26), "Aynı harita, aynı saldırı · [F1]/[F2] sol mimari · [M] [U] [X] [+/-] senaryo · [N] yeni harita",
                         13, Ui.Ink2, false, TextAnchor.MiddleCenter);
        }

        // Üstteki durum paneli: hangi mimari, kaç hedef, puan, yanlış "bitti"
        static void Panel(SwarmFrame f, int side, Color accent)
        {
            float half = Ui.W / 2f, w = 560f, x = side * half + (half - w) / 2f, y = 14f;
            var r = Ui.R(x, y, w, 98);
            Ui.Panel(r, 14, 0.9f);
            Ui.Fill(Ui.R(x + 14, y, w - 28, 4), accent, 2);
            if (f == null || f.m == null)
            {
                Ui.Label(Ui.R(x, y + 30, w, 30), "bağlantı bekleniyor…", 18, Ui.Ink2, true, TextAnchor.UpperCenter);
                return;
            }
            var m = f.m;
            Ui.Label(Ui.R(x, y + 12, w, 30), Name(f.strategy), 19, accent, true, TextAnchor.UpperCenter);
            string gps = m.spoofed > 0 || m.spoofSeen > 0 ? $"  ·  kandırılan {m.spoofed}" : $"  ·  GPS'siz {m.gpsLost}";
            Ui.Label(Ui.R(x, y + 42, w, 26),
                     $"hedef <b>{m.done}/{m.total}</b>  ·  puan <b>{m.score * 100:0}</b>  ·  yanlış \"bitti\" <b>{m.falseDone}</b>{gps}",
                     16, Ui.Ink, false, TextAnchor.UpperCenter);
            Ui.Label(Ui.R(x, y + 68, w, 22), $"t = {f.t:0} s  ·  {SwarmScenarios.PhaseTitle(f.phase)}  ·  paket iletimi %{m.pdr * 100:0}", 13.5f, Ui.Ink3, false, TextAnchor.UpperCenter);
        }
    }
}
