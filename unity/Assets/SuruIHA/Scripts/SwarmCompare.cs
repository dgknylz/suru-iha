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
        SwarmHud hud;
        float nextLayer;
        GUIStyle head, val, small;
        Texture2D bg, line, accentA, accentB;

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
            B.showLinks = A.showLinks; B.showEstimates = A.showEstimates; B.showJamMap = A.showJamMap;
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
                camB.transform.SetPositionAndRotation(mainCam.transform.position, mainCam.transform.rotation);
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
                if (hud != null) hud.visible = false;    // ayrıntılı panel H ile açılır
            }
            else
            {
                mainCam.rect = new Rect(0f, 0f, 1f, 1f);
                mainCam.cullingMask = ~(1 << LayerB);
                if (camB != null) camB.gameObject.SetActive(false);
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
            float s = Mathf.Clamp(Screen.height / 1080f, 0.75f, 2f);
            bg ??= Tex(new Color(0.03f, 0.05f, 0.07f, 0.78f));
            line ??= Tex(new Color(1f, 1f, 1f, 0.85f));
            head ??= new GUIStyle { fontStyle = FontStyle.Bold, alignment = TextAnchor.UpperCenter, richText = true };
            val ??= new GUIStyle { alignment = TextAnchor.UpperCenter, richText = true };
            small ??= new GUIStyle { alignment = TextAnchor.LowerCenter, richText = true };
            head.fontSize = (int)(22 * s);
            head.normal.textColor = Color.white;
            val.fontSize = (int)(16 * s);
            val.normal.textColor = new Color(0.85f, 0.9f, 0.95f);
            small.fontSize = (int)(13 * s);
            small.normal.textColor = new Color(0.8f, 0.85f, 0.9f);
            GUI.DrawTexture(new Rect(Screen.width / 2f - 1.5f * s, 0, 3f * s, Screen.height), line);
            accentA ??= Tex(new Color(0.85f, 0.45f, 0.3f));
            accentB ??= Tex(new Color(0.3f, 0.85f, 0.55f));
            Panel(A.Frame, 0f, s, accentA);
            Panel(B.Frame, Screen.width / 2f, s, accentB);
            GUI.Label(new Rect(0, Screen.height - 34 * s, Screen.width, 30 * s),
                      "Aynı harita, aynı saldırı · [H] ayrıntılı panel · [F1]/[F2] sol mimari · [M] [U] [X] [+/-] senaryo · [N] yeni harita", small);
        }

        void Panel(SwarmFrame f, float x, float s, Texture2D accent)
        {
            float w = Screen.width / 2f;
            var r = new Rect(x + w * 0.5f - 260 * s, 14 * s, 520 * s, 92 * s);
            GUI.DrawTexture(r, bg);
            GUI.DrawTexture(new Rect(r.x, r.y, r.width, 4 * s), accent);
            if (f == null || f.m == null)
            {
                GUI.Label(new Rect(r.x, r.y + 12 * s, r.width, 30 * s), "bağlantı bekleniyor…", head);
                return;
            }
            var m = f.m;
            GUI.Label(new Rect(r.x, r.y + 10 * s, r.width, 30 * s), Name(f.strategy), head);
            string gps = m.spoofed > 0 || m.spoofSeen > 0 ? $"  ·  aldatılan {m.spoofed}" : $"  ·  GPS'siz {m.gpsLost}";
            GUI.Label(new Rect(r.x, r.y + 44 * s, r.width, 24 * s),
                      $"görev <b>{m.done}/{m.total}</b>  ·  puan <b>{m.score * 100:0}</b>  ·  yanlış \"bitti\" <b>{m.falseDone}</b>{gps}",
                      val);
            GUI.Label(new Rect(r.x, r.y + 66 * s, r.width, 24 * s),
                      $"t = {f.t:0} s  ·  {f.phase}  ·  paket iletimi %{m.pdr * 100:0}", val);
        }
    }
}
