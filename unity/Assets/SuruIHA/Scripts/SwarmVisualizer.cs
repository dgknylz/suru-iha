using System.Collections.Generic;
using UnityEngine;

namespace SuruIHA
{
    // Ana görselleştirici: Python'dan gelen her kareyi sahneye uygular.
    // İHA'lar, haberleşme bağlantıları, görev noktaları, karıştırıcılar,
    // yer istasyonu ve sürünün ortak karıştırma haritası burada çizilir.
    [RequireComponent(typeof(SwarmReceiver))]
    public partial class SwarmVisualizer : MonoBehaviour
    {
        [Header("Modeller (boş bırakılırsa kodla basit model kurulur)")]
        public GameObject droneModel;
        public GameObject jammerModel;
        public GameObject gcsModel;
        [Tooltip("İHA'lar istasyonun etrafında kalktığı için model biraz yana kaydırılır")]
        public Vector3 gcsModelOffset = new Vector3(-30f, 0f, -4f);

        [Header("Görünüm")]
        [Tooltip("Uzaktan görünsünler diye İHA'lar büyütülür (gerçek boy = 1)")]
        public float droneScale = 3f;
        public float linkWidth = 0.15f;
        [Tooltip("Parlayan öğelerin şiddeti")]
        public float glow = 1.6f;
        public float trailSeconds = 6f;
        public bool showTrails = true;
        public bool showLinks = true;
        [Tooltip("Yalnızca zayıflamış (karıştırılan) bağlantıları çiz: ekran temiz kalır, EH etkisi yine görünür")]
        public bool onlyWeakLinks;
        public const float WeakLink = 0.6f;   // bu kalitenin altındaki bağlantı "sorunlu" sayılır
        public bool showEstimates = true;
        [Tooltip("Dirençli sürünün ortak karıştırma haritası (J tuşu)")]
        public bool showJamMap = false;
        [Tooltip("Gerçek karıştırma gücü haritası (arazi gölgesiyle), araziye serilir")]
        public bool showHeatMap = true;
        public bool showDome = true;
        [Tooltip("Uzaktan görünen, durum renginde parlayan İHA işaretleri (B tuşu)")]
        public bool showBeacons = true;
        [Tooltip("Her İHA'nın planlı görev rotası (P tuşu)")]
        public bool showPlans = true;

        [Header("Zemin")]
        [Tooltip("Cesium/terrain varsa kökü zemin yüksekliğine oturtur")]
        public bool autoGroundSnap = true;
        public LayerMask groundMask = ~0;

        public SwarmFrame Frame { get; private set; }
        public IReadOnlyList<DroneView> Drones => drones;
        public SwarmReceiver Receiver { get; private set; }
        public Materials Mats => materials;

        // Sahnedeki ana sürü (5065). Karşılaştırma modu ikinci bir görselleştirici ekler; FindAnyObjectByType
        // ikisinden rastgele birini döndürebildiği için ana sürüye her zaman bununla ulaşılır.
        public static SwarmVisualizer Main { get; private set; }

        // Bu sürüyü çizen kamera (yan yana ekranda sağdaki sürü için ikinci kamera). İşaret ve çizgi boyutları
        // bu kameraya olan uzaklığa göre ayarlanır; boşsa ana kamera.
        public Camera ViewCamera;
        public Camera RenderCamera => ViewCamera != null && ViewCamera.isActiveAndEnabled ? ViewCamera : Camera.main;
        void OnEnable() { if (Main == null) Main = this; }
        void OnDestroy() { if (Main == this) Main = null; }

        [Header("Malzemeler (Sahneyi Kur doldurur; boş kalanlar kodla üretilir)")]
        public Materials materials = new Materials();
        bool initialized;
        public Vector3 Centroid { get; private set; }

        readonly List<DroneView> drones = new List<DroneView>();
        readonly List<LineRenderer> links = new List<LineRenderer>();
        readonly List<Vector3Int> linkData = new List<Vector3Int>();
        readonly List<float> linkQ = new List<float>();
        readonly List<TaskMarker> tasks = new List<TaskMarker>();
        readonly List<JammerView> jammers = new List<JammerView>();
        readonly List<GameObject> jamCells = new List<GameObject>();
        readonly List<LineRenderer> gcsLinks = new List<LineRenderer>();
        readonly List<LineRenderer> relayLines = new List<LineRenderer>();
        readonly List<LineRenderer> planLines = new List<LineRenderer>();
        readonly List<EstMarker> estMarkers = new List<EstMarker>();
        readonly List<SpooferMarker> spoofers = new List<SpooferMarker>();
        Transform droneRoot, linkRoot, taskRoot, ewRoot;
        Transform gcs, gcsMastTop;
        MaterialPropertyBlock block;
        SwarmFrame applied;
        float snapTimer;
        bool snapped;

        [System.Serializable]
        public class Materials
        {
            public Material Body, Shell, Dark, PropBlur, Led, Trail, Ghost, GhostLine,
                Link, GcsLink, TaskBeam, TaskRing, Dome, DomeRing, JamCell, HeatMap, Snow, Concrete, Metal;

            // Boş olan her malzemeyi kodla üretir (editörde asset olarak kaydedilebilir)
            public void FillMissing(float glow)
            {
                if (Body == null) Body = SwarmMaterials.Lit(new Color(0.23f, 0.25f, 0.24f), 0.3f, 0.45f);
                if (Shell == null) Shell = SwarmMaterials.Lit(new Color(0.42f, 0.45f, 0.40f), 0.1f, 0.6f);
                if (Dark == null) Dark = SwarmMaterials.Lit(new Color(0.05f, 0.05f, 0.06f), 0.2f, 0.4f);
                if (PropBlur == null) PropBlur = SwarmMaterials.Transparent(new Color(0.1f, 0.1f, 0.1f, 0.25f));
                if (Led == null) Led = SwarmMaterials.Glow(DroneView.ColNormal, glow * 2f);
                if (Trail == null) Trail = SwarmMaterials.Transparent(new Color(0.55f, 0.8f, 1f, 0.12f), glow * 0.12f);
                if (Ghost == null) Ghost = SwarmMaterials.Transparent(new Color(1f, 0.25f, 0.2f, 0.18f), glow * 0.25f);
                if (GhostLine == null) GhostLine = SwarmMaterials.Glow(new Color(1f, 0.35f, 0.3f), glow * 0.6f);
                if (Link == null) Link = SwarmMaterials.Glow(new Color(0.2f, 1f, 0.6f), glow);
                if (GcsLink == null) GcsLink = SwarmMaterials.Glow(new Color(0.3f, 0.75f, 1f), glow);
                if (TaskBeam == null) TaskBeam = SwarmMaterials.Transparent(new Color(1f, 1f, 1f, 0.07f), glow * 0.08f);
                if (TaskRing == null) TaskRing = SwarmMaterials.Glow(Color.white, glow * 0.6f);
                if (Dome == null) Dome = SwarmMaterials.Transparent(new Color(1f, 0.18f, 0.1f, 0.045f), glow * 0.05f);
                if (DomeRing == null) DomeRing = SwarmMaterials.Glow(new Color(1f, 0.3f, 0.18f), glow * 0.5f);
                if (JamCell == null) JamCell = SwarmMaterials.Transparent(new Color(1f, 0.3f, 0.1f, 0.07f), glow * 0.05f);
                if (HeatMap == null) HeatMap = SwarmMaterials.Overlay(glow * 0.25f);
                if (Snow == null) Snow = SwarmMaterials.Transparent(new Color(1f, 1f, 1f, 0.9f));   // kar tanesi (parlamasız)
                if (Concrete == null) Concrete = SwarmMaterials.Lit(new Color(0.55f, 0.55f, 0.52f), 0f, 0.2f);
                if (Metal == null) Metal = SwarmMaterials.Lit(new Color(0.6f, 0.62f, 0.65f), 0.8f, 0.5f);
            }
        }

        void Awake() => Init();

        // Film kesmesi: İHA'lar bir sonraki karede yumuşatmadan yerlerine konur
        public void Snap()
        {
            foreach (var d in drones) d.Snap();
        }

        // Editörde (Play'e basmadan) önizleme render'ı almak için de kullanılır
        public void PreviewFrame(SwarmFrame f)
        {
            Init();
            applied = f;
            Frame = f;
            ApplyDrones(f);
            ApplyTasks(f);
            ApplyJammers(f);
            ApplyGcs(f);
            ApplyJamCells(f);
            ApplyHeatMap(f);
            RecordMetrics(f);
            ApplyReport(f);
            ApplyJamEstimates(f);
            ApplySpoofers(f);
            ApplyThreats(f);
            ParseLinks(f);
            LateUpdate();
        }

        // Hava savunma, rüzgâr (SwarmVisualizer.Radar.cs)
        void ApplyThreats(SwarmFrame f)
        {
            ApplyRadars(f);
            ApplyMissiles(f);
            ApplyRadarEstimates(f);
            ApplyRadarField(f);
            ApplyWind(f);
            ApplyConvoy(f);
        }

        void Init()
        {
            if (initialized) return;
            initialized = true;
            Receiver = GetComponent<SwarmReceiver>();
            block = new MaterialPropertyBlock();
            if (materials == null) materials = new Materials();
            materials.FillMissing(glow);
            droneRoot = NewChild("Suru");
            linkRoot = NewChild("Baglantilar");
            taskRoot = NewChild("Gorevler");
            ewRoot = NewChild("ElektronikHarp");
        }

        Transform NewChild(string n)
        {
            var t = new GameObject(n).transform;
            t.SetParent(transform, false);
            return t;
        }

        void Update()
        {
            if (autoGroundSnap && !snapped) TryGroundSnap();
            var f = Receiver.Latest;
            if (f == null || f == applied) return;
            applied = f;
            Frame = f;
            ApplyDrones(f);
            ApplyTasks(f);
            ApplyJammers(f);
            ApplyGcs(f);
            ApplyJamCells(f);
            ApplyHeatMap(f);
            if (!SwarmReceiver.Replaying) RecordMetrics(f);     // tekrar izlenirken grafikler canlı uçuşunkini korur
            ApplyReport(f);
            ApplyJamEstimates(f);
            ApplySpoofers(f);
            ApplyThreats(f);
            ParseLinks(f);
        }

        void LateUpdate()
        {
            // Çizgiler, yumuşatılmış İHA konumlarını takip etsin diye her karede güncellenir
            for (int k = 0; k < links.Count; k++)
            {
                // Merkezi mimaride İHA'lar birbirleriyle konuşmaz: yalnızca istasyon bağlantıları (yıldız) çizilir
                bool central = Frame != null && Frame.strategy == "centralized";
                bool on = showLinks && !central && k < linkData.Count && (!onlyWeakLinks || (k < linkQ.Count && linkQ[k] < WeakLink));
                if (links[k].enabled != on) links[k].enabled = on;
                if (!on) continue;
                var d = linkData[k];
                if (d.x >= drones.Count || d.y >= drones.Count) { links[k].enabled = false; continue; }
                Vector3 a = drones[d.x].transform.position, b = drones[d.y].transform.position;
                links[k].SetPosition(0, a);
                links[k].SetPosition(1, b);
                // Kameraya yakın çizgiler incelsin (takip kamerasında ekranı kaplamasın)
                var cam = RenderCamera;
                float near = cam != null ? DistanceToSegment(cam.transform.position, a, b) : 200f;
                // "Sorunlu" kipinde ekranda yalnızca bunlar kalır: ince ve sönük değil, belirgin çizilsin
                float wq = onlyWeakLinks ? 1.4f : Mathf.Lerp(0.4f, 1f, k < linkQ.Count ? linkQ[k] : 1f);
                links[k].widthMultiplier = linkWidth * wq * Mathf.Clamp(near / 120f, 0.08f, 1f);
            }
            if (gcs != null && Frame?.gcs?.up != null)
            {
                Vector3 mast = gcsMastTop != null ? gcsMastTop.position : gcs.position + Vector3.up * 12f;
                for (int i = 0; i < gcsLinks.Count; i++)
                {
                    bool on = showLinks && !onlyWeakLinks && Frame.gcs.on == 1 && i < Frame.gcs.up.Length && Frame.gcs.up[i] == 1 && i < drones.Count;
                    gcsLinks[i].enabled = on;
                    if (!on) continue;
                    gcsLinks[i].SetPosition(0, mast);
                    gcsLinks[i].SetPosition(1, drones[i].transform.position);
                }
            }
            if (Frame?.drones != null)
            {
                while (relayLines.Count < drones.Count) relayLines.Add(MakeLine(linkRoot, Mats.GcsLink, linkWidth * 1.4f, 2, true));
                for (int i = 0; i < relayLines.Count; i++)
                {
                    int k = i < Frame.drones.Length ? Frame.drones[i].relay : -1;
                    bool on = showLinks && k >= 0 && k < drones.Count;
                    relayLines[i].enabled = on;
                    if (!on) continue;
                    relayLines[i].SetPosition(0, drones[i].transform.position);
                    relayLines[i].SetPosition(1, drones[k].transform.position);
                }
            }
            UpdatePlanLines();
            AnimateRadars();
            AnimateMissiles();
            AnimateWindsock();
            AnimateConvoy();
            if (drones.Count > 0)
            {
                Vector3 c = Vector3.zero;
                int n = 0;
                foreach (var d in drones)
                {
                    if (d.State != null && d.State.mode == 4) continue;
                    c += d.transform.position;
                    n++;
                }
                if (n > 0) Centroid = c / n;
            }
        }

        void ApplyDrones(SwarmFrame f)
        {
            if (f.drones == null) return;
            while (drones.Count < f.drones.Length) drones.Add(DroneView.Create(this, droneRoot, drones.Count));
            for (int i = 0; i < drones.Count; i++)
            {
                bool on = i < f.drones.Length;
                drones[i].gameObject.SetActive(on);
                if (on) drones[i].SetState(f.drones[i]);
            }
        }

        void ParseLinks(SwarmFrame f)
        {
            linkData.Clear();
            linkQ.Clear();
            var L = f.links ?? new float[0];
            for (int k = 0; k + 2 < L.Length; k += 3)
            {
                linkData.Add(new Vector3Int((int)L[k], (int)L[k + 1], 0));
                linkQ.Add(L[k + 2]);
            }
            while (links.Count < linkData.Count) links.Add(MakeLine(linkRoot, Mats.Link, linkWidth, 2, true));
            for (int k = 0; k < linkData.Count; k++)
            {
                // Kalite 1 = yeşil (sağlam), 0 = kırmızı (karıştırılmış)
                float q = linkQ[k];
                Color c = Color.Lerp(new Color(1f, 0.12f, 0.08f), new Color(0.15f, 1f, 0.55f), q);
                SwarmMaterials.SetBlock(block, c * 0.2f, c * glow * (onlyWeakLinks ? 1.3f : Mathf.Lerp(0.35f, 1f, q)));
                links[k].SetPropertyBlock(block);
                links[k].widthMultiplier = linkWidth * Mathf.Lerp(0.4f, 1f, q);
            }
        }

        void ApplyTasks(SwarmFrame f)
        {
            if (f.tasks == null) return;
            while (tasks.Count < f.tasks.Length) tasks.Add(new TaskMarker(this, taskRoot, tasks.Count));
            for (int i = 0; i < tasks.Count; i++)
            {
                if (i < f.tasks.Length) tasks[i].Set(f.tasks[i], block, this);
                else tasks[i].Root.gameObject.SetActive(false);
            }
        }

        void ApplyJammers(SwarmFrame f)
        {
            var J = f.jammers ?? new JammerState[0];
            while (jammers.Count < J.Length) jammers.Add(JammerView.Create(this, ewRoot, jammers.Count));
            for (int i = 0; i < jammers.Count; i++)
            {
                bool on = i < J.Length;
                jammers[i].gameObject.SetActive(on);
                if (on) jammers[i].Set(J[i]);
            }
        }

        void ApplyGcs(SwarmFrame f)
        {
            if (f.gcs == null || f.gcs.p == null) return;
            if (gcs == null)
            {
                if (gcsModel != null)
                {
                    gcs = Instantiate(gcsModel, transform).transform;
                    foreach (var c in gcs.GetComponentsInChildren<Collider>()) SafeDestroy(c);
                    gcsMastTop = FindDeep(gcs, "Mast_Top");
                }
                else
                {
                    gcs = new GameObject("YerIstasyonu").transform;
                    gcs.SetParent(transform, false);
                    Prim(PrimitiveType.Cube, gcs, new Vector3(0, 1.5f, 0), new Vector3(6, 3, 3), Mats.Concrete);
                    Prim(PrimitiveType.Cylinder, gcs, new Vector3(2, 6, 0), new Vector3(0.3f, 6, 0.3f), Mats.Metal);
                    Prim(PrimitiveType.Sphere, gcs, new Vector3(2, 12, 0), new Vector3(1.6f, 0.4f, 1.6f), Mats.Metal);
                }
                gcs.name = "YerIstasyonu";
            }
            var p = SwarmFrame.Enu(f.gcs.p);
            var gp = new Vector3(p.x, 0f, p.z) + gcsModelOffset;
            gcs.localPosition = new Vector3(gp.x, LocalGround(gp.x, gp.z), gp.z);
            while (gcsLinks.Count < (f.drones?.Length ?? 0)) gcsLinks.Add(MakeLine(linkRoot, Mats.GcsLink, linkWidth * 0.6f, 2, true));
        }

        // Sürünün karıştırıcı konum kestirimi: yerde turuncu nişangâh + etki dairesi; gerçek karıştırıcıya hata çizgisi
        class EstMarker
        {
            public Transform Root;
            public LineRenderer Ring, CrossA, CrossB, Err;
        }

        void ApplyJamEstimates(SwarmFrame f)
        {
            var E = f.jamEst ?? new JamEstState[0];
            while (estMarkers.Count < E.Length)
            {
                var m = new EstMarker { Root = NewChildOf(ewRoot, "KaristiriciTahmini") };
                m.Ring = MakeCircle(m.Root, 1f, 96, Mats.TaskRing, 0.5f);
                m.CrossA = MakeLine(m.Root, Mats.TaskRing, 0.7f, 2, false);
                m.CrossB = MakeLine(m.Root, Mats.TaskRing, 0.7f, 2, false);
                m.CrossA.SetPositions(new[] { new Vector3(-18, 0, 0), new Vector3(18, 0, 0) });
                m.CrossB.SetPositions(new[] { new Vector3(0, 0, -18), new Vector3(0, 0, 18) });
                m.Err = MakeLine(ewRoot, Mats.GhostLine, 0.35f, 2, true);
                Color c = new Color(1f, 0.55f, 0.1f);
                SwarmMaterials.SetBlock(block, c, c * glow);
                foreach (var lr in new[] { m.Ring, m.CrossA, m.CrossB }) lr.SetPropertyBlock(block);
                estMarkers.Add(m);
            }
            for (int i = 0; i < estMarkers.Count; i++)
            {
                var m = estMarkers[i];
                bool on = i < E.Length;
                m.Root.gameObject.SetActive(on);
                m.Err.enabled = on && f.jammers != null && f.jammers.Length > 0;
                if (!on) continue;
                var p = SwarmFrame.Enu(E[i].p);
                float g = LocalGround(p.x, p.z) + 1.5f;
                m.Root.localPosition = new Vector3(p.x, g, p.z);
                m.Ring.transform.localScale = Vector3.one * Mathf.Max(E[i].r, 10f);
                // Uzaktan (kuşbakışı) da seçilsin: çizgiler kamera uzaklığıyla kalınlaşır, nişangâh büyür
                var cam = RenderCamera;
                float far = cam != null ? Mathf.Clamp(Vector3.Distance(cam.transform.position, m.Root.position) / 150f, 1f, 5f) : 1f;
                m.Ring.widthMultiplier = 0.5f * far;
                m.CrossA.widthMultiplier = m.CrossB.widthMultiplier = 0.7f * far;
                m.CrossA.transform.localScale = m.CrossB.transform.localScale = Vector3.one * Mathf.Sqrt(far);
                m.Err.widthMultiplier = 0.35f * far;
                if (m.Err.enabled)
                {
                    // En yakın gerçek karıştırıcıya hata çizgisi
                    Vector3 best = Vector3.zero;
                    float bd = float.MaxValue;
                    foreach (var j in f.jammers)
                    {
                        var q = SwarmFrame.Enu(j.p);
                        float d = (new Vector2(q.x, q.z) - new Vector2(p.x, p.z)).sqrMagnitude;
                        if (d < bd) { bd = d; best = q; }
                    }
                    m.Err.SetPosition(0, transform.TransformPoint(new Vector3(p.x, g + 1f, p.z)));
                    m.Err.SetPosition(1, transform.TransformPoint(new Vector3(best.x, LocalGround(best.x, best.z) + 2.5f, best.z)));
                }
            }
        }

        // GPS aldatıcı: yerde anten direği + camgöbeği yarı saydam kubbe + yerde yayılan halkalar
        class SpooferMarker
        {
            public Transform Root, Dome;
            public LineRenderer Edge, Wave;
        }

        void ApplySpoofers(SwarmFrame f)
        {
            var S = f.spoofers ?? new SpooferState[0];
            while (spoofers.Count < S.Length)
            {
                var m = new SpooferMarker { Root = NewChildOf(ewRoot, "GpsAldatici") };
                Prim(PrimitiveType.Cylinder, m.Root, new Vector3(0, 5f, 0), new Vector3(0.25f, 5f, 0.25f), Mats.Metal);
                Prim(PrimitiveType.Cube, m.Root, new Vector3(0, 0.6f, 0), new Vector3(2.4f, 1.2f, 1.6f), Mats.Body);
                var dish = Prim(PrimitiveType.Sphere, m.Root, new Vector3(0, 10.2f, 0), new Vector3(1.6f, 0.35f, 1.6f), Mats.Metal);
                dish.name = "Anten";
                var d = Prim(PrimitiveType.Sphere, m.Root, Vector3.zero, Vector3.one, Mats.Dome);
                d.GetComponent<Renderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                m.Dome = d.transform;
                m.Edge = MakeCircle(m.Root, 1f, 128, Mats.DomeRing, 0.45f);
                m.Wave = MakeCircle(m.Root, 1f, 128, Mats.DomeRing, 0.3f);
                Color c = new Color(0.1f, 0.75f, 1f);
                SwarmMaterials.SetBlock(block, new Color(c.r, c.g, c.b, 0.09f), c * glow * 0.12f);
                d.GetComponent<Renderer>().SetPropertyBlock(block);
                SwarmMaterials.SetBlock(block, c * 0.3f, c * glow * 0.6f);
                m.Edge.SetPropertyBlock(block);
                m.Wave.SetPropertyBlock(block);
                spoofers.Add(m);
            }
            for (int i = 0; i < spoofers.Count; i++)
            {
                var m = spoofers[i];
                bool on = i < S.Length;
                m.Root.gameObject.SetActive(on);
                if (!on) continue;
                var p = SwarmFrame.Enu(S[i].p);
                m.Root.localPosition = new Vector3(p.x, LocalGround(p.x, p.z), p.z);
                float r = Mathf.Max(S[i].r, 5f);
                m.Dome.gameObject.SetActive(showDome);
                m.Dome.localScale = Vector3.one * r * 2f;
                m.Edge.transform.localPosition = Vector3.up * 0.6f;
                m.Edge.transform.localScale = new Vector3(r, 1, r);
                float ph = Mathf.Repeat(Time.time * 0.25f, 1f);
                m.Wave.transform.localPosition = Vector3.up * 0.8f;
                m.Wave.transform.localScale = new Vector3(r * ph, 1, r * ph);
            }
        }

        Transform NewChildOf(Transform parent, string n)
        {
            var t = new GameObject(n).transform;
            t.SetParent(parent, false);
            return t;
        }

        void ApplyJamCells(SwarmFrame f)
        {
            var C = f.jamCells ?? new float[0];
            int n = showJamMap ? C.Length / 2 : 0;
            while (jamCells.Count < n)
            {
                var q = Prim(PrimitiveType.Cube, ewRoot, Vector3.zero, Vector3.one, Mats.JamCell);
                q.name = "KaristirmaHucresi";
                q.GetComponent<Renderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                jamCells.Add(q);
            }
            float s = f.cell > 0 ? f.cell : 50f;
            for (int i = 0; i < jamCells.Count; i++)
            {
                bool on = i < n;
                jamCells[i].SetActive(on);
                if (!on) continue;
                jamCells[i].transform.localPosition = new Vector3(C[2 * i], 0.6f, C[2 * i + 1]);
                jamCells[i].transform.localScale = new Vector3(s * 0.96f, 0.05f, s * 0.96f);
            }
        }

        void TryGroundSnap()
        {
            snapTimer -= Time.deltaTime;
            if (snapTimer > 0) return;
            snapTimer = 1f;
            var origin = new Vector3(transform.position.x, transform.position.y + 3000f, transform.position.z);
            if (Physics.Raycast(origin, Vector3.down, out var hit, 10000f, groundMask, QueryTriggerInteraction.Ignore))
            {
                transform.position = new Vector3(transform.position.x, hit.point.y, transform.position.z);
                snapped = true;
            }
            else if (Time.time > 60f)
            {
                snapped = true;
            }
        }

        static float DistanceToSegment(Vector3 p, Vector3 a, Vector3 b)
        {
            Vector3 ab = b - a;
            float t = Mathf.Clamp01(Vector3.Dot(p - a, ab) / Mathf.Max(ab.sqrMagnitude, 1e-4f));
            return Vector3.Distance(p, a + ab * t);
        }

        // Dünya konumunun altındaki arazi yüksekliği (arazi çarpıştırıcısına ışın atar)
        public float GroundAt(Vector3 world)
        {
            var o = new Vector3(world.x, 3000f, world.z);
            if (Physics.Raycast(o, Vector3.down, out var hit, 6000f, groundMask, QueryTriggerInteraction.Ignore))
                return Mathf.Max(hit.point.y, SwarmRegions.WaterFloor);
            return transform.position.y;
        }

        float LocalGround(float x, float z) => GroundAt(transform.TransformPoint(new Vector3(x, 0, z))) - transform.position.y;

        // ---------------------------------------------------------- yardımcılar
        public static void SafeDestroy(Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }

        public static Transform FindDeep(Transform t, string name)
        {
            foreach (var c in t.GetComponentsInChildren<Transform>(true))
                if (c.name == name) return c;
            return null;
        }

        public static GameObject Prim(PrimitiveType type, Transform parent, Vector3 localPos, Vector3 localScale,
            Material mat, Quaternion? rot = null)
        {
            var g = GameObject.CreatePrimitive(type);
            SafeDestroy(g.GetComponent<Collider>());
            g.transform.SetParent(parent, false);
            g.transform.localPosition = localPos;
            g.transform.localScale = localScale;
            if (rot.HasValue) g.transform.localRotation = rot.Value;
            g.GetComponent<Renderer>().sharedMaterial = mat;
            return g;
        }

        public static LineRenderer MakeLine(Transform parent, Material mat, float width, int count, bool world)
        {
            var g = new GameObject("Cizgi");
            g.transform.SetParent(parent, false);
            var lr = g.AddComponent<LineRenderer>();
            lr.sharedMaterial = mat;
            lr.useWorldSpace = world;
            lr.positionCount = count;
            lr.widthMultiplier = width;
            lr.numCapVertices = 2;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            return lr;
        }

        public static LineRenderer MakeCircle(Transform parent, float radius, int segments, Material mat, float width)
        {
            var lr = MakeLine(parent, mat, width, segments, false);
            lr.loop = true;
            for (int i = 0; i < segments; i++)
            {
                float a = i * Mathf.PI * 2f / segments;
                lr.SetPosition(i, new Vector3(Mathf.Cos(a) * radius, 0, Mathf.Sin(a) * radius));
            }
            return lr;
        }

        // Görev noktası: yerden yükselen ışık sütunu + seyir irtifasında iç içe halkalar
        // (halka sayısı = görevin değeri/önceliği). Yeni beliren hedeften dışa doğru bir dalga yayılır.
        class TaskMarker
        {
            public Transform Root;
            public Vector3 Top => ring[0].transform.position;   // halkanın dünya konumu (plan çizgileri buraya)
            public bool Visible { get; private set; }
            readonly Renderer beam;
            readonly LineRenderer[] ring = new LineRenderer[3];
            readonly LineRenderer wave;
            readonly Transform beamT;

            public static readonly Color[] StateColors =
            {
                new Color(0.85f, 0.88f, 0.95f),   // açık
                new Color(1f, 0.78f, 0.2f),       // bir İHA yolda
                new Color(0.2f, 1f, 0.45f),       // tamamlandı
                new Color(1f, 0.15f, 0.25f),      // yanlış tamamlandı (İHA bitti sandı)
            };
            public static readonly Color ColUnknown = new Color(0.75f, 0.3f, 1f);   // belirdi ama sürü henüz bilmiyor
            public static readonly Color ColMark = new Color(1f, 0.32f, 0.12f);     // pusuyu işaretleme görevi

            public TaskMarker(SwarmVisualizer v, Transform parent, int id)
            {
                Root = new GameObject($"Gorev_{id:00}").transform;
                Root.SetParent(parent, false);
                var b = Prim(PrimitiveType.Cylinder, Root, Vector3.zero, Vector3.one, v.Mats.TaskBeam);
                beamT = b.transform;
                beam = b.GetComponent<Renderer>();
                beam.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                for (int k = 0; k < ring.Length; k++)
                    ring[k] = MakeCircle(Root, 6f + 3.2f * k, 48, v.Mats.TaskRing, 0.22f - 0.03f * k);
                wave = MakeCircle(Root, 1f, 64, v.Mats.TaskRing, 0.6f);
                wave.enabled = false;
            }

            float ground = float.NaN;

            public void Set(TaskState s, MaterialPropertyBlock block, SwarmVisualizer v)
            {
                Visible = s.s >= 0;
                Root.gameObject.SetActive(Visible);
                if (!Visible) return;
                var p = SwarmFrame.Enu(s.p);
                if (float.IsNaN(ground) || (Root.localPosition - new Vector3(p.x, ground, p.z)).sqrMagnitude > 1f)
                    ground = v.LocalGround(p.x, p.z);    // canlı eklenen hedef yeni bir yere konabilir
                float h = Mathf.Max(p.y - ground, 1f);
                Root.localPosition = new Vector3(p.x, ground, p.z);
                int val = Mathf.Clamp(s.v, 1, 3);
                float sz = s.ty == 1 ? 0.55f : 1f;            // konvoy yol taraması: küçük işaret
                float wBeam = (s.s == 2 ? 0.3f : 0.45f + 0.2f * val) * sz;
                beamT.localPosition = new Vector3(0, h * 0.5f, 0);
                beamT.localScale = new Vector3(wBeam, h * 0.5f, wBeam);
                bool unknown = s.s == 0 && s.k == 0;
                float pulse = unknown ? 0.55f + 0.45f * Mathf.Sin(Time.time * 5f) : 1f;
                Color c = unknown ? ColUnknown : StateColors[Mathf.Clamp(s.s, 0, 3)];
                if (s.ty == 2 && s.s <= 1 && !unknown) c = ColMark;   // pusu işaretleme görevi
                // Yeni hedef: ilk saniyelerde ışık sütunu parlar
                float fresh = s.age >= 0 ? Mathf.Clamp01(1f - s.age / 6f) : 0f;
                SwarmMaterials.SetBlock(block, new Color(c.r, c.g, c.b, 0.07f + 0.25f * fresh), c * (0.15f + 1.5f * fresh));
                beam.SetPropertyBlock(block);
                for (int k = 0; k < ring.Length; k++)
                {
                    ring[k].enabled = k < val;
                    ring[k].transform.localPosition = new Vector3(0, h, 0);
                    ring[k].transform.localScale = Vector3.one * sz;
                    SwarmMaterials.SetBlock(block, c * 0.3f, c * (1.4f - 0.25f * k) * pulse);
                    ring[k].SetPropertyBlock(block);
                }
                // Belirme dalgası: 5 saniyede 90 m'ye yayılıp söner
                bool waveOn = s.age >= 0 && s.age < 5f;
                wave.enabled = waveOn;
                if (waveOn)
                {
                    float k = s.age / 5f;
                    wave.transform.localPosition = new Vector3(0, h, 0);
                    wave.transform.localScale = Vector3.one * Mathf.Lerp(6f, 90f, Mathf.Sqrt(k));
                    // Uzaktan (kuşbakışı) da görünsün: kalınlık kamera uzaklığıyla büyür
                    var cam = v.RenderCamera;
                    float far = cam != null ? Vector3.Distance(cam.transform.position, Root.position) / 150f : 1f;
                    wave.widthMultiplier = Mathf.Lerp(0.7f, 0.15f, k) * Mathf.Clamp(far, 0.6f, 6f);
                    // Taban rengi de parlak: gündüz ışığında ışıma (emission) tek başına sönük kalıyor
                    Color wc = ColUnknown * (1f - k) * 3f;
                    SwarmMaterials.SetBlock(block, Color.Lerp(ColUnknown, Color.white, 0.25f), wc);
                    wave.SetPropertyBlock(block);
                }
            }
        }

        // Her İHA'nın planlı rotası: İHA -> 1. hedef -> 2. hedef ... (P tuşu)
        static readonly Color[] PlanColors =
        {
            new Color(0.35f, 0.75f, 1f), new Color(1f, 0.55f, 0.25f), new Color(0.6f, 1f, 0.35f), new Color(1f, 0.35f, 0.7f),
            new Color(0.95f, 0.9f, 0.3f), new Color(0.45f, 0.45f, 1f), new Color(0.3f, 1f, 0.85f), new Color(1f, 0.3f, 0.3f),
            new Color(0.8f, 0.55f, 1f), new Color(0.7f, 0.85f, 0.6f),
        };

        void UpdatePlanLines()
        {
            var D = Frame?.drones;
            int n = D?.Length ?? 0;
            while (planLines.Count < n) planLines.Add(MakeLine(linkRoot, Mats.TaskRing, 0.35f, 2, true));
            var cam = RenderCamera;
            for (int i = 0; i < planLines.Count; i++)
            {
                var lr = planLines[i];
                int[] plan = i < n ? D[i].plan : null;
                bool on = showPlans && plan != null && plan.Length > 0 && i < drones.Count && D[i].mode != 4;
                if (on)
                    foreach (int t in plan)
                        if (t < 0 || t >= tasks.Count || !tasks[t].Visible) { on = false; break; }
                lr.enabled = on;
                if (!on) continue;
                Vector3 a = drones[i].transform.position;
                // Dirençli İHA radardan kaçan bir rota izliyorsa ilk ayak o rotadan (ara noktalar) çizilir
                int[] route = D[i].route;
                int r0 = route != null && route.Length >= 4 ? RouteStart(route, transform.InverseTransformPoint(a)) : 0;
                int mid = route != null && route.Length >= 4 ? route.Length / 2 - 1 - r0 : 0;
                if (mid < 0) mid = 0;
                lr.positionCount = plan.Length + 1 + mid;
                lr.SetPosition(0, a);
                float ry = transform.InverseTransformPoint(a).y;
                for (int k = 0; k < mid; k++) lr.SetPosition(k + 1, RoutePoint(route, r0 + k, ry));
                for (int k = 0; k < plan.Length; k++) lr.SetPosition(k + 1 + mid, tasks[plan[k]].Top);
                // Önce gidilecek hedefe giden kısım kalın, sonraki hedefler incelerek
                float first = (1f + mid) / (lr.positionCount - 1);
                var curve = new AnimationCurve(new Keyframe(0f, 1f), new Keyframe(Mathf.Min(first, 0.999f), 1f),
                                               new Keyframe(Mathf.Min(1f, first + 0.5f / lr.positionCount), 0.45f), new Keyframe(1f, 0.3f));
                lr.widthCurve = curve;
                float near = cam != null ? Vector3.Distance(cam.transform.position, a) : 200f;
                lr.widthMultiplier = 0.3f * Mathf.Clamp(near / 180f, 0.12f, 2.2f);
                Color c = PlanColors[i % PlanColors.Length];
                SwarmMaterials.SetBlock(block, c * 0.15f, c * glow * 0.6f);
                lr.SetPropertyBlock(block);
            }
        }
    }
}
