using System.Collections.Generic;
using UnityEngine;

namespace SuruIHA
{
    // Ana görselleştirici: Python'dan gelen her kareyi sahneye uygular.
    // İHA'lar, haberleşme bağlantıları, görev noktaları, karıştırıcılar,
    // yer istasyonu ve sürünün ortak karıştırma haritası burada çizilir.
    [RequireComponent(typeof(SwarmReceiver))]
    public class SwarmVisualizer : MonoBehaviour
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
        public bool showEstimates = true;
        [Tooltip("Dirençli sürünün ortak karıştırma haritası (J tuşu)")]
        public bool showJamMap = false;
        public bool showDome = true;
        [Tooltip("Uzaktan görünen, durum renginde parlayan İHA işaretleri (B tuşu)")]
        public bool showBeacons = true;

        [Header("Zemin")]
        [Tooltip("Cesium/terrain varsa kökü zemin yüksekliğine oturtur")]
        public bool autoGroundSnap = true;
        public LayerMask groundMask = ~0;

        public SwarmFrame Frame { get; private set; }
        public IReadOnlyList<DroneView> Drones => drones;
        public SwarmReceiver Receiver { get; private set; }
        public Materials Mats => materials;

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
                Link, GcsLink, TaskBeam, TaskRing, Dome, DomeRing, JamCell, Concrete, Metal;

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
                if (Concrete == null) Concrete = SwarmMaterials.Lit(new Color(0.55f, 0.55f, 0.52f), 0f, 0.2f);
                if (Metal == null) Metal = SwarmMaterials.Lit(new Color(0.6f, 0.62f, 0.65f), 0.8f, 0.5f);
            }
        }

        void Awake() => Init();

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
            ParseLinks(f);
            LateUpdate();
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
            ParseLinks(f);
        }

        void LateUpdate()
        {
            // Çizgiler, yumuşatılmış İHA konumlarını takip etsin diye her karede güncellenir
            for (int k = 0; k < links.Count; k++)
            {
                // Merkezi mimaride İHA'lar birbirleriyle konuşmaz: yalnızca istasyon bağlantıları (yıldız) çizilir
                bool central = Frame != null && Frame.strategy == "centralized";
                bool on = showLinks && !central && k < linkData.Count;
                if (links[k].enabled != on) links[k].enabled = on;
                if (!on) continue;
                var d = linkData[k];
                if (d.x >= drones.Count || d.y >= drones.Count) { links[k].enabled = false; continue; }
                Vector3 a = drones[d.x].transform.position, b = drones[d.y].transform.position;
                links[k].SetPosition(0, a);
                links[k].SetPosition(1, b);
                // Kameraya yakın çizgiler incelsin (takip kamerasında ekranı kaplamasın)
                var cam = Camera.main;
                float near = cam != null ? DistanceToSegment(cam.transform.position, a, b) : 200f;
                links[k].widthMultiplier = linkWidth * Mathf.Lerp(0.4f, 1f, k < linkQ.Count ? linkQ[k] : 1f)
                                           * Mathf.Clamp(near / 120f, 0.08f, 1f);
            }
            if (gcs != null && Frame?.gcs?.up != null)
            {
                Vector3 mast = gcsMastTop != null ? gcsMastTop.position : gcs.position + Vector3.up * 12f;
                for (int i = 0; i < gcsLinks.Count; i++)
                {
                    bool on = showLinks && Frame.gcs.on == 1 && i < Frame.gcs.up.Length && Frame.gcs.up[i] == 1 && i < drones.Count;
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
                SwarmMaterials.SetBlock(block, c * 0.2f, c * glow * Mathf.Lerp(0.35f, 1f, q));
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
                bool on = i < f.tasks.Length;
                tasks[i].Root.gameObject.SetActive(on);
                if (on) tasks[i].Set(f.tasks[i], block, this);
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
                return hit.point.y;
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

        // Görev noktası: yerden yükselen ışık sütunu + seyir irtifasında halka
        class TaskMarker
        {
            public Transform Root;
            readonly Renderer beam;
            readonly LineRenderer ring;
            readonly Transform beamT;

            public static readonly Color[] StateColors =
            {
                new Color(0.85f, 0.88f, 0.95f),   // açık
                new Color(1f, 0.78f, 0.2f),       // bir İHA yolda
                new Color(0.2f, 1f, 0.45f),       // tamamlandı
                new Color(1f, 0.15f, 0.25f),      // yanlış tamamlandı (İHA bitti sandı)
            };

            public TaskMarker(SwarmVisualizer v, Transform parent, int id)
            {
                Root = new GameObject($"Gorev_{id:00}").transform;
                Root.SetParent(parent, false);
                var b = Prim(PrimitiveType.Cylinder, Root, Vector3.zero, Vector3.one, v.Mats.TaskBeam);
                beamT = b.transform;
                beam = b.GetComponent<Renderer>();
                beam.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                ring = MakeCircle(Root, 6f, 48, v.Mats.TaskRing, 0.22f);
            }

            float ground = float.NaN;

            public void Set(TaskState s, MaterialPropertyBlock block, SwarmVisualizer v)
            {
                var p = SwarmFrame.Enu(s.p);
                if (float.IsNaN(ground)) ground = v.LocalGround(p.x, p.z);
                float h = Mathf.Max(p.y - ground, 1f);
                Root.localPosition = new Vector3(p.x, ground, p.z);
                beamT.localPosition = new Vector3(0, h * 0.5f, 0);
                beamT.localScale = new Vector3(s.s == 2 ? 0.3f : 0.6f, h * 0.5f, s.s == 2 ? 0.3f : 0.6f);
                ring.transform.localPosition = new Vector3(0, h, 0);
                Color c = StateColors[Mathf.Clamp(s.s, 0, 3)];
                SwarmMaterials.SetBlock(block, new Color(c.r, c.g, c.b, 0.07f), c * 0.15f);
                beam.SetPropertyBlock(block);
                SwarmMaterials.SetBlock(block, c * 0.3f, c * 1.4f);
                ring.SetPropertyBlock(block);
            }
        }
    }
}
