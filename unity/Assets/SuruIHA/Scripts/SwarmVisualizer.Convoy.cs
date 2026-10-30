using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace SuruIHA
{
    // Konvoy koruma: araziye oturan, tekerleri dönen ve toz kaldıran İKA'lar; rota (taranmış kısmı yeşil, taranmamışı
    // soluk); gizli tehditler (sürü bilmiyorsa mor halka, bulununca kırmızı; pusunun menzili, konvoya ateşi, lazerle
    // işaretlenip topçuyla vurulması; mayının ikaz bayrağı); HSS bastırma rolleri (karıştırıcının radara huzmesi, yemin
    // koşusu, kamikazelerin dalışı) ve vurulan araçların, pusunun ve radarın patlaması ve dumanı.
    public partial class SwarmVisualizer
    {
        [Header("Konvoy koruma")]
        public GameObject ikaModel;
        public GameObject pusuModel;
        public GameObject mayinModel;
        [Tooltip("Kara araçları uzaktan seçilsin diye büyütülür (gerçek boy = 1)")]
        public float groundScale = 2f;

        static readonly Color RouteCol = new Color(0.25f, 1f, 0.5f);       // taranmış (temiz bilinen) yol
        static readonly Color RouteOpenCol = new Color(0.8f, 0.82f, 0.9f); // henüz taranmamış yol
        static readonly Color ThreatCol = new Color(1f, 0.18f, 0.1f);      // bulunan tehdit
        static readonly Color JamBeamCol = new Color(0.72f, 0.3f, 1f);     // karıştırıcı İHA'nın huzmesi
        static readonly Color DecoyCol = new Color(1f, 0.62f, 0.12f);      // yem İHA
        static readonly Color StrikeCol = new Color(1f, 0.12f, 0.08f);     // kamikaze İHA
        const float AmbushRange = 160f;                                    // suru/convoy.py AMBUSH_RANGE

        class VehicleView
        {
            public Transform Root, Turret;
            public Transform[] Wheels;
            public Quaternion[] WheelBase;
            public Quaternion TurretBase;
            public Renderer[] Rends;
            public Vector3 Target, Fwd = Vector3.forward;
            public float WheelAngle, DustT, Speed, TurretYaw;
            public bool Alive = true, Placed;
        }

        class ThreatView
        {
            public Transform Root, Flag, Muzzle;
            public Renderer[] Rends;
            public LineRenderer Ring, Range, Laser, Tracer;
            public string Kind;
            public bool Found, Dead, Marked;
            public float Fire = -1f, DeadT = -1f, FoundT = -1f;
        }

        class Puff
        {
            public Transform T;
            public Renderer R;
            public Vector3 V;
            public float Born, Life, Size, Spin;
            public Color C;
        }

        // Duman ve toz kartı: ortası dolu, kenara doğru yumuşakça sönen, biraz pürüzlü yuvarlak leke
        static Material MakePuffMaterial()
        {
            const int N = 64;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { name = "DumanLekesi", wrapMode = TextureWrapMode.Clamp };
            var px = new Color32[N * N];
            for (int j = 0; j < N; j++)
            for (int i = 0; i < N; i++)
            {
                float x = (i + 0.5f) / N * 2f - 1f, y = (j + 0.5f) / N * 2f - 1f;
                float a = Mathf.Atan2(y, x);
                float r = Mathf.Sqrt(x * x + y * y) / (0.82f + 0.1f * Mathf.Sin(3f * a) + 0.06f * Mathf.Sin(7f * a + 1f));
                float k = Mathf.Clamp01(1f - r);
                float n = Mathf.PerlinNoise(i * 0.12f, j * 0.12f);
                px[j * N + i] = new Color32(255, 255, 255, (byte)(255f * k * k * (3f - 2f * k) * (0.7f + 0.3f * n)));
            }
            tex.SetPixels32(px);
            tex.Apply(false);
            var m = SwarmMaterials.Transparent(Color.white);
            foreach (var p in new[] { "_BaseColorMap", "_MainTex", "_BaseMap" })
                if (m.HasProperty(p)) m.SetTexture(p, tex);
            return m;
        }

        class Blast
        {
            public Transform T;
            public Light L;
            public float Born, Size, Delay;
        }

        class SmokeSource
        {
            public Vector3 P;              // yerel konum
            public float Until, Next, Size, Rate;
            public Color C;
        }

        class SeadView
        {
            public LineRenderer Jam, Decoy;
            public LineRenderer[] Strike = new LineRenderer[2];
            public LineRenderer[] Station = new LineRenderer[4];
        }

        Transform convoyRoot;
        readonly List<VehicleView> vehicles = new List<VehicleView>();
        readonly List<ThreatView> threatViews = new List<ThreatView>();
        readonly List<SeadView> seadViews = new List<SeadView>();
        readonly List<Puff> puffs = new List<Puff>();
        readonly List<Puff> puffPool = new List<Puff>();
        readonly List<Blast> blasts = new List<Blast>();
        readonly List<SmokeSource> smokes = new List<SmokeSource>();
        LineRenderer routeDone, routeOpen, goalRing;
        readonly List<Vector3> routePts = new List<Vector3>();
        readonly List<float> routeS = new List<float>();
        string routeKey;
        float convoyLastT = -1f, routeCleared = -1f;
        Material puffMat, beamMat, blastMat;

        public ConvoyState Convoy => Frame?.convoy != null && Frame.convoy.v != null && Frame.convoy.v.Length >= 5 ? Frame.convoy : null;

        // ------------------------------------------------------------------ kare
        void ApplyConvoy(SwarmFrame f)
        {
            var C = f.convoy != null && f.convoy.v != null && f.convoy.v.Length >= 5 ? f.convoy : null;
            if (convoyRoot == null) convoyRoot = NewChildOf(transform, "Konvoy");
            if (f.t < convoyLastT - 0.5f) ResetConvoyFx();   // yeni uçuş
            convoyLastT = f.t;
            convoyRoot.gameObject.SetActive(C != null);
            if (C == null) return;
            ApplyRoute(C);
            int n = C.v.Length / 5;
            while (vehicles.Count < n) vehicles.Add(MakeVehicle(vehicles.Count));
            for (int k = 0; k < vehicles.Count; k++)
            {
                var v = vehicles[k];
                v.Root.gameObject.SetActive(k < n);
                if (k >= n) continue;
                float x = C.v[5 * k], z = C.v[5 * k + 1], hd = C.v[5 * k + 3];
                bool alive = C.v[5 * k + 4] > 0.5f;
                v.Target = new Vector3(x, LocalGround(x, z), z);
                v.Fwd = Quaternion.Euler(0f, hd, 0f) * Vector3.forward;
                if (!v.Placed) { v.Root.localPosition = v.Target; v.Placed = true; }
                if (v.Alive && !alive)
                {
                    // Araç vuruldu: patlama, kararır, yana yatar, uzun süre tüter
                    AddBlast(v.Target + Vector3.up * 2f, 16f, 0f);
                    AddBlast(v.Target + Vector3.up * 4f, 9f, 0.25f);
                    smokes.Add(new SmokeSource { P = v.Target + Vector3.up * 2f, Until = Time.time + 60f, Size = 5f, Rate = 0.12f,
                                                 C = new Color(0.12f, 0.12f, 0.12f, 0.55f) });
                    Char(v.Rends, true);
                }
                else if (!v.Alive && alive) Char(v.Rends, false);
                v.Alive = alive;
            }
            ApplyConvoyThreats(f, C);
            ApplySead(f);
        }

        void ResetConvoyFx()
        {
            smokes.Clear();
            foreach (var p in puffs) { p.T.gameObject.SetActive(false); puffPool.Add(p); }
            puffs.Clear();
            foreach (var b in blasts) b.T.gameObject.SetActive(false);
            foreach (var v in vehicles) { v.Placed = false; if (!v.Alive) Char(v.Rends, false); v.Alive = true; }
            foreach (var t in threatViews) { t.Found = t.Dead = t.Marked = false; t.Fire = -1f; Char(t.Rends, false); }
            foreach (var r in radarViews) if (r.Dead) { r.Dead = false; Char(r.Rends, false); }
            routeKey = null;
        }

        // Yanmış görünüm: bütün parçalar kömür rengine döner (kapatılınca özgün malzeme)
        void Char(Renderer[] rends, bool on)
        {
            if (rends == null) return;
            if (on) SwarmMaterials.SetBlock(block, new Color(0.035f, 0.033f, 0.03f), Color.black);
            foreach (var r in rends)
                if (r != null) r.SetPropertyBlock(on ? block : null);
        }

        VehicleView MakeVehicle(int id)
        {
            var v = new VehicleView { Root = NewChildOf(convoyRoot, $"IKA_{id + 1}") };
            Transform m;
            if (ikaModel != null)
            {
                var g = Instantiate(ikaModel, v.Root);
                foreach (var c in g.GetComponentsInChildren<Collider>()) SafeDestroy(c);
                m = g.transform;
            }
            else
            {
                m = NewChildOf(v.Root, "Model");
                Prim(PrimitiveType.Cube, m, new Vector3(0, 1.1f, 0), new Vector3(2.1f, 1.1f, 4.6f), Mats.Body);
                for (int k = 0; k < 4; k++)
                    Prim(PrimitiveType.Cylinder, m, new Vector3(k % 2 == 0 ? -1f : 1f, 0.52f, k < 2 ? 1.45f : -1.35f),
                         new Vector3(1.04f, 0.21f, 1.04f), Mats.Dark, Quaternion.Euler(0, 0, 90f)).name = "Teker_" + k;
            }
            m.name = "Model";
            m.localScale = Vector3.one * groundScale;
            var wheels = new List<Transform>();
            foreach (var t in m.GetComponentsInChildren<Transform>(true))
                if (t.name.StartsWith("Teker_")) wheels.Add(t);
            v.Wheels = wheels.ToArray();
            v.WheelBase = new Quaternion[v.Wheels.Length];
            for (int k = 0; k < v.Wheels.Length; k++) v.WheelBase[k] = Quaternion.Inverse(v.Root.rotation) * v.Wheels[k].rotation;
            v.Turret = FindDeep(m, "Kule");
            if (v.Turret != null) v.TurretBase = Quaternion.Inverse(v.Root.rotation) * v.Turret.rotation;
            v.Rends = m.GetComponentsInChildren<Renderer>();
            foreach (var r in v.Rends) r.shadowCastingMode = ShadowCastingMode.On;
            return v;
        }

        // ------------------------------------------------------------------ rota
        void ApplyRoute(ConvoyState C)
        {
            var R = C.route;
            if (R == null || R.Length < 4) return;
            string key = string.Join(",", R);
            if (key != routeKey)
            {
                routeKey = key;
                routeCleared = -1f;
                routePts.Clear();
                routeS.Clear();
                float s = 0f;
                for (int k = 0; k + 3 < R.Length; k += 2)
                {
                    var a = new Vector2(R[k], R[k + 1]);
                    var b = new Vector2(R[k + 2], R[k + 3]);
                    float L = Vector2.Distance(a, b);
                    int n = Mathf.Max(1, Mathf.CeilToInt(L / 6f));
                    for (int i = 0; i < n; i++)
                    {
                        var p = Vector2.Lerp(a, b, (float)i / n);
                        routePts.Add(new Vector3(p.x, LocalGround(p.x, p.y) + 0.7f, p.y));
                        routeS.Add(s + L * i / n);
                    }
                    s += L;
                }
                var e = new Vector2(R[R.Length - 2], R[R.Length - 1]);
                routePts.Add(new Vector3(e.x, LocalGround(e.x, e.y) + 0.7f, e.y));
                routeS.Add(s);
                if (routeDone == null)
                {
                    routeDone = MakeLine(convoyRoot, Mats.TaskRing, 1f, 2, false);
                    routeDone.name = "TaranmisYol";
                    routeOpen = MakeLine(convoyRoot, Mats.TaskRing, 1f, 2, false);
                    routeOpen.name = "TaranmamisYol";
                    goalRing = MakeCircle(convoyRoot, 1f, 64, Mats.TaskRing, 1f);
                    goalRing.name = "KonvoyHedefi";
                    SwarmMaterials.SetBlock(block, RouteCol * 0.3f, RouteCol * glow * 0.5f);
                    routeDone.SetPropertyBlock(block);
                    goalRing.SetPropertyBlock(block);
                    SwarmMaterials.SetBlock(block, RouteOpenCol * 0.2f, RouteOpenCol * glow * 0.25f);
                    routeOpen.SetPropertyBlock(block);
                }
                goalRing.transform.localPosition = routePts[routePts.Count - 1] + Vector3.up * 0.3f;
                goalRing.transform.localScale = Vector3.one * 9f;
            }
            if (Mathf.Abs(C.cleared - routeCleared) < 0.01f) return;
            routeCleared = C.cleared;
            var done = new List<Vector3>();
            var open = new List<Vector3>();
            for (int k = 0; k < routePts.Count; k++)
            {
                if (routeS[k] <= C.cleared) done.Add(routePts[k]);
                else
                {
                    if (open.Count == 0 && k > 0)
                    {
                        // Taranmış kısmın tam bittiği nokta: iki çizgi birleşsin
                        float u = Mathf.InverseLerp(routeS[k - 1], routeS[k], C.cleared);
                        var cut = Vector3.Lerp(routePts[k - 1], routePts[k], u);
                        done.Add(cut);
                        open.Add(cut);
                    }
                    open.Add(routePts[k]);
                }
            }
            SetLine(routeDone, done);
            SetLine(routeOpen, open);
        }

        static void SetLine(LineRenderer lr, List<Vector3> pts)
        {
            lr.enabled = pts.Count >= 2;
            lr.positionCount = pts.Count;
            lr.SetPositions(pts.ToArray());
        }

        // ------------------------------------------------------------------ tehditler
        void ApplyConvoyThreats(SwarmFrame f, ConvoyState C)
        {
            var T = C.threats ?? new ConvoyThreatState[0];
            while (threatViews.Count < T.Length) threatViews.Add(MakeThreat(T[threatViews.Count].k, threatViews.Count));
            for (int k = 0; k < threatViews.Count; k++)
            {
                var v = threatViews[k];
                bool on = k < T.Length;
                v.Root.gameObject.SetActive(on);
                if (!on) continue;
                var s = T[k];
                if (s.k != v.Kind) { SafeDestroy(v.Root.gameObject); threatViews[k] = v = MakeThreat(s.k, k); }
                var p = SwarmFrame.Enu(s.p);
                var g = new Vector3(p.x, LocalGround(p.x, p.z), p.z);
                v.Root.localPosition = g;
                if (v.Kind == "pusu" && routePts.Count > 0)
                {
                    // Mevzi (siperi ve aracın burnu) yola bakar
                    var near = routePts[0];
                    foreach (var q in routePts)
                        if ((q - g).sqrMagnitude < (near - g).sqrMagnitude) near = q;
                    var dir = new Vector3(near.x - g.x, 0f, near.z - g.z);
                    if (dir.sqrMagnitude > 1f) v.Root.localRotation = Quaternion.LookRotation(dir);
                }
                if (s.f == 1 && !v.Found) v.FoundT = Time.time;
                v.Found = s.f == 1;
                if (s.d == 1 && !v.Dead)
                {
                    v.DeadT = Time.time;
                    if (v.Kind == "pusu")
                    {
                        // Topçu: işaretlenen mevziye üç mermi
                        for (int i = 0; i < 3; i++)
                            AddBlast(g + new Vector3(Random.Range(-5f, 5f), 2f, Random.Range(-5f, 5f)), 18f - 3f * i, 0.3f * i);
                        smokes.Add(new SmokeSource { P = g + Vector3.up * 2f, Until = Time.time + 90f, Size = 7f, Rate = 0.1f,
                                                     C = new Color(0.1f, 0.1f, 0.1f, 0.55f) });
                    }
                    else
                    {
                        AddBlast(g + Vector3.up, 12f, 0f);
                        smokes.Add(new SmokeSource { P = g + Vector3.up, Until = Time.time + 25f, Size = 4f, Rate = 0.15f,
                                                     C = new Color(0.35f, 0.3f, 0.24f, 0.45f) });
                    }
                    Char(v.Rends, true);
                }
                else if (s.d == 0 && v.Dead) Char(v.Rends, false);
                v.Dead = s.d == 1;
                // Yeni atış: son atıştan geçen süre sıfırlandı -> namlu alevi
                bool shot = s.fire >= 0f && (v.Fire < 0f || s.fire + 1e-3f < v.Fire);
                if (shot && !v.Dead && v.Muzzle != null) AddBlast(convoyRoot.InverseTransformPoint(v.Muzzle.position), 4f, 0f);
                v.Fire = s.fire;
                v.Marked = s.m == 1 && !v.Dead;
                v.Laser.enabled = false;
                v.Tracer.enabled = false;
                if (v.Flag != null) v.Flag.gameObject.SetActive(v.Found && !v.Dead);
                // Halka: sürü bilmiyorsa mor (gizli), bulununca kırmızı, imha edilince gri
                Color c = v.Dead ? new Color(0.45f, 0.45f, 0.45f) : v.Found ? ThreatCol : TaskMarker.ColUnknown;
                SwarmMaterials.SetBlock(block, c * 0.3f, c * glow * (v.Dead ? 0.15f : v.Found ? 1.1f : 0.35f));
                v.Ring.SetPropertyBlock(block);
                v.Range.enabled = v.Kind == "pusu" && v.Found && !v.Dead;
                if (v.Range.enabled)
                {
                    SwarmMaterials.SetBlock(block, ThreatCol * 0.2f, ThreatCol * glow * 0.35f);
                    v.Range.SetPropertyBlock(block);
                }
            }
        }

        ThreatView MakeThreat(string kind, int id)
        {
            var v = new ThreatView { Kind = kind, Root = NewChildOf(convoyRoot, $"Tehdit_{id}_{kind}") };
            var src = kind == "pusu" ? pusuModel : mayinModel;
            Transform m;
            if (src != null)
            {
                var g = Instantiate(src, v.Root);
                foreach (var c in g.GetComponentsInChildren<Collider>()) SafeDestroy(c);
                m = g.transform;
            }
            else
            {
                m = NewChildOf(v.Root, "Model");
                if (kind == "pusu") Prim(PrimitiveType.Sphere, m, new Vector3(0, 1f, 0), new Vector3(7f, 2.6f, 6f), Mats.Body);
                else Prim(PrimitiveType.Cylinder, m, new Vector3(0, 0.05f, 0), new Vector3(0.32f, 0.05f, 0.32f), Mats.Dark);
            }
            m.name = "Model";
            m.localScale = Vector3.one * (kind == "pusu" ? groundScale * 0.8f : 3f);
            v.Flag = FindDeep(m, "Bayrak");
            v.Muzzle = FindDeep(m, "Namlu");
            v.Rends = m.GetComponentsInChildren<Renderer>();
            if (v.Flag != null) v.Flag.gameObject.SetActive(false);
            v.Ring = MakeCircle(v.Root, kind == "pusu" ? 16f : 7f, 64, Mats.TaskRing, 0.6f);
            v.Ring.transform.localPosition = Vector3.up * 0.8f;
            v.Range = MakeCircle(v.Root, AmbushRange, 160, Mats.DomeRing, 0.8f);
            v.Range.transform.localPosition = Vector3.up * 1.2f;
            var bm = Mat(ref beamMat, () => SwarmMaterials.Glow(Color.white, glow));
            v.Laser = MakeLine(convoyRoot, bm, 0.25f, 2, true);
            v.Tracer = MakeLine(convoyRoot, bm, 0.35f, 2, true);
            return v;
        }

        // ------------------------------------------------------------------ HSS bastırma
        void ApplySead(SwarmFrame f)
        {
            var S = f.sead ?? new SeadState[0];
            if (f.strategy != "resilient") S = new SeadState[0];
            while (seadViews.Count < S.Length) seadViews.Add(MakeSead());
            for (int k = 0; k < seadViews.Count; k++)
            {
                var v = seadViews[k];
                bool on = k < S.Length && S[k].st != "bitti";
                if (!on)
                {
                    v.Jam.enabled = v.Decoy.enabled = false;
                    foreach (var l in v.Strike) l.enabled = false;
                    foreach (var l in v.Station) l.enabled = false;
                    continue;
                }
                var s = S[k];
                bool prep = s.st == "hazırlık";
                var pts = new List<Vector3> { SwarmFrame.Enu(s.jam), SwarmFrame.Enu(s.dec) };
                for (int i = 0; s.str != null && i + 2 < s.str.Length; i += 3) pts.Add(new Vector3(s.str[i], s.str[i + 2], s.str[i + 1]));
                Color[] cols = { JamBeamCol, DecoyCol, StrikeCol, StrikeCol };
                for (int i = 0; i < v.Station.Length; i++)
                {
                    var l = v.Station[i];
                    l.enabled = prep && i < pts.Count;
                    if (!l.enabled) continue;
                    l.transform.localPosition = new Vector3(pts[i].x, LocalGround(pts[i].x, pts[i].z) + 1.5f, pts[i].z);
                    SwarmMaterials.SetBlock(block, cols[i] * 0.3f, cols[i] * glow * 0.9f);
                    l.SetPropertyBlock(block);
                }
            }
        }

        SeadView MakeSead()
        {
            var bm = Mat(ref beamMat, () => SwarmMaterials.Glow(Color.white, glow));
            var v = new SeadView
            {
                Jam = MakeLine(ewRoot, bm, 1f, 2, true),
                Decoy = MakeLine(ewRoot, bm, 1f, 2, true),
            };
            v.Jam.name = "KaristirmaHuzmesi";
            v.Decoy.name = "YemKosusu";
            for (int i = 0; i < 2; i++) { v.Strike[i] = MakeLine(ewRoot, bm, 1f, 2, true); v.Strike[i].name = "KamikazeDalisi"; }
            for (int i = 0; i < 4; i++) { v.Station[i] = MakeCircle(ewRoot, 10f, 40, Mats.TaskRing, 0.6f); v.Station[i].name = "RolNoktasi"; }
            return v;
        }

        // ------------------------------------------------------------------ her kare
        void AnimateConvoy()
        {
            var cam = RenderCamera;
            float dt = Time.deltaTime;
            var C = convoyRoot != null && convoyRoot.gameObject.activeSelf ? Convoy : null;
            if (C != null)
            {
                // Çizgi kalınlığı rotanın kameraya en yakın yerine göre: yakın planda yolu kaplamasın, tepeden seçilsin
                float near = float.MaxValue;
                if (cam != null)
                    for (int k = 0; k < routePts.Count; k += 4)
                        near = Mathf.Min(near, Vector3.Distance(cam.transform.position, transform.TransformPoint(routePts[k])));
                float far = cam != null ? Mathf.Clamp(near / 250f, 0.12f, 5f) : 1f;
                if (routeDone != null)
                {
                    routeDone.widthMultiplier = 0.9f * far;
                    routeOpen.widthMultiplier = 0.5f * far;
                    goalRing.widthMultiplier = 0.6f * far;
                }
                foreach (var v in vehicles) if (v.Root.gameObject.activeSelf) AnimateVehicle(v, dt);
                AnimateThreats(cam);
                AnimateSead(cam);
            }
            AnimateFx(dt);
        }

        void AnimateVehicle(VehicleView v, float dt)
        {
            var p0 = v.Root.localPosition;
            var p = v.Alive ? Vector3.Lerp(p0, v.Target, 1f - Mathf.Exp(-dt * 8f)) : p0;
            float moved = new Vector2(p.x - p0.x, p.z - p0.z).magnitude;
            v.Speed = Mathf.Lerp(v.Speed, dt > 0 ? moved / dt : 0f, 1f - Mathf.Exp(-dt * 4f));
            // Araziye otur: önde-arkada ve sağda-solda zemin yüksekliği
            var fwd = v.Fwd;
            var right = new Vector3(fwd.z, 0f, -fwd.x);
            float L = 2f * groundScale, W = 0.9f * groundScale;
            float hF = LocalGround(p.x + fwd.x * L, p.z + fwd.z * L), hB = LocalGround(p.x - fwd.x * L, p.z - fwd.z * L);
            float hR = LocalGround(p.x + right.x * W, p.z + right.z * W), hL = LocalGround(p.x - right.x * W, p.z - right.z * W);
            p.y = Mathf.Max(LocalGround(p.x, p.z), 0.5f * (hF + hB));
            var f = (fwd * 2f * L + Vector3.up * (hF - hB)).normalized;
            var r = (right * 2f * W + Vector3.up * (hR - hL)).normalized;
            var up = Vector3.Cross(f, r);
            var rot = Quaternion.LookRotation(f, up);
            if (!v.Alive) rot *= Quaternion.Euler(0f, 0f, 9f);
            v.Root.localPosition = p;
            v.Root.localRotation = Quaternion.Slerp(v.Root.localRotation, rot, 1f - Mathf.Exp(-dt * 6f));
            // Tekerler yol kadar döner
            v.WheelAngle += moved / (0.52f * groundScale) * Mathf.Rad2Deg;
            for (int k = 0; k < v.Wheels.Length; k++)
                v.Wheels[k].rotation = v.Root.rotation * Quaternion.AngleAxis(v.WheelAngle, Vector3.right) * v.WheelBase[k];
            // Silah kulesi en yakın bulunmuş, imha edilmemiş pusuya döner
            if (v.Turret != null)
            {
                float want = 0f, best = 260f;
                foreach (var t in threatViews)
                {
                    if (t.Kind != "pusu" || !t.Found || t.Dead || !t.Root.gameObject.activeSelf) continue;
                    var d = t.Root.localPosition - p;
                    float dist = new Vector2(d.x, d.z).magnitude;
                    if (dist < best) { best = dist; want = Vector3.SignedAngle(fwd, new Vector3(d.x, 0f, d.z), Vector3.up); }
                }
                if (!v.Alive) want = v.TurretYaw;
                v.TurretYaw = Mathf.MoveTowardsAngle(v.TurretYaw, want, 60f * dt);
                v.Turret.rotation = v.Root.rotation * Quaternion.AngleAxis(v.TurretYaw, Vector3.up) * v.TurretBase;
            }
            // Toz: hareket eden aracın arkasında
            if (v.Alive && v.Speed > 0.8f && Time.time > v.DustT)
            {
                v.DustT = Time.time + 0.14f;
                var dust = SwarmRegions.Current == "kar" ? new Color(0.92f, 0.94f, 0.97f, 0.3f) : new Color(0.66f, 0.58f, 0.45f, 0.26f);
                AddPuff(p - fwd * 2.4f * groundScale + Vector3.up * 0.6f, new Vector3(Random.Range(-0.6f, 0.6f), 0.7f, Random.Range(-0.6f, 0.6f)),
                        2.6f, 2.8f, dust);
            }
        }

        void AnimateThreats(Camera cam)
        {
            var D = Frame?.drones;
            foreach (var t in threatViews)
            {
                if (!t.Root.gameObject.activeSelf) continue;
                float far = cam != null ? Mathf.Clamp(Vector3.Distance(cam.transform.position, t.Root.position) / 200f, 0.3f, 6f) : 1f;
                float pulse = t.Found && !t.Dead ? 0.8f + 0.2f * Mathf.Sin(Time.time * 6f) : 1f;
                t.Ring.widthMultiplier = 0.6f * far * pulse;
                // Bulunma anında halka büyüyüp oturur
                float k = t.FoundT >= 0f ? Mathf.Clamp01((Time.time - t.FoundT) / 0.8f) : 1f;
                t.Ring.transform.localScale = Vector3.one * (t.Found ? Mathf.Lerp(3f, 1f, k) : 1f);
                t.Range.widthMultiplier = 0.7f * far;
                // Lazer işaretleme: pusu işaretlendiyse en yakın İHA'dan mevziye kızıl huzme (topçu bu noktayı vurur)
                if (t.Marked && D != null)
                {
                    int best = -1;
                    float bd = 400f;
                    for (int i = 0; i < Mathf.Min(D.Length, drones.Count); i++)
                    {
                        if (D[i].mode == 4) continue;
                        float d = Vector3.Distance(drones[i].transform.position, t.Root.position);
                        if (d < bd) { bd = d; best = i; }
                    }
                    t.Laser.enabled = best >= 0;
                    if (best >= 0)
                    {
                        t.Laser.SetPosition(0, drones[best].transform.position);
                        t.Laser.SetPosition(1, t.Root.position + Vector3.up * 1.5f);
                        t.Laser.widthMultiplier = 0.18f * Mathf.Clamp(far, 0.5f, 4f) * (0.7f + 0.3f * Mathf.Sin(Time.time * 30f));
                        SwarmMaterials.SetBlock(block, ThreatCol, ThreatCol * glow * 2f);
                        t.Laser.SetPropertyBlock(block);
                    }
                }
                // Ateş: namludan en yakın araca iz mermisi
                if (!t.Dead && t.Fire >= 0f && t.Fire < 0.5f)
                {
                    VehicleView tgt = null;
                    float bd = AmbushRange * 1.3f;
                    foreach (var v in vehicles)
                    {
                        if (!v.Root.gameObject.activeSelf) continue;
                        float d = Vector3.Distance(v.Root.localPosition, t.Root.localPosition);
                        if (d < bd) { bd = d; tgt = v; }
                    }
                    if (tgt != null)
                    {
                        var a = t.Muzzle != null ? t.Muzzle.position : t.Root.position + Vector3.up * 2f;
                        var b = tgt.Root.position + Vector3.up * 1.5f * groundScale;
                        float u = Mathf.Clamp01(t.Fire / 0.35f);
                        t.Tracer.enabled = true;
                        t.Tracer.SetPosition(0, Vector3.Lerp(a, b, Mathf.Max(0f, u - 0.25f)));
                        t.Tracer.SetPosition(1, Vector3.Lerp(a, b, u));
                        t.Tracer.widthMultiplier = 0.35f * Mathf.Clamp(far, 0.6f, 4f);
                        var c = new Color(1f, 0.75f, 0.3f);
                        SwarmMaterials.SetBlock(block, c, c * glow * 3f);
                        t.Tracer.SetPropertyBlock(block);
                    }
                }
            }
        }

        void AnimateSead(Camera cam)
        {
            var S = Frame?.sead;
            var D = Frame?.drones;
            for (int k = 0; k < seadViews.Count; k++)
            {
                var v = seadViews[k];
                bool on = S != null && k < S.Length && S[k].st != "bitti" && Frame.strategy == "resilient" && D != null;
                if (!on) continue;
                var s = S[k];
                var qa = SwarmFrame.Enu(s.q);
                var q = transform.TransformPoint(new Vector3(qa.x, LocalGround(qa.x, qa.z) + 6f, qa.z));
                foreach (var st in v.Station)
                    if (st.enabled) st.widthMultiplier = 0.5f * (cam != null ? Mathf.Clamp(Vector3.Distance(cam.transform.position, st.transform.position) / 200f, 0.3f, 5f) : 1f);
                // Karıştırıcı: nöbet noktasına varınca radara titreşen mor huzme
                bool jam = Valid(s.ij, D) && Vector3.Distance(drones[s.ij].transform.localPosition, Flat(SwarmFrame.Enu(s.jam), drones[s.ij].transform.localPosition.y)) < 90f;
                Beam(v.Jam, jam, jam ? drones[s.ij].transform.position : q, q, JamBeamCol, 1.6f, cam, 18f);
                // Yem: saldırıda radara koşar
                bool dec = Valid(s.id, D) && D[s.id].dash == 1;
                Beam(v.Decoy, dec, dec ? drones[s.id].transform.position : q, q, DecoyCol, 0.7f, cam, 6f);
                for (int n = 0; n < v.Strike.Length; n++)
                {
                    int i = s.@is != null && n < s.@is.Length ? s.@is[n] : -1;
                    bool dive = Valid(i, D) && D[i].dash == 1;
                    Beam(v.Strike[n], dive, dive ? drones[i].transform.position : q, q, StrikeCol, 1.1f, cam, 9f);
                }
            }
        }

        bool Valid(int i, DroneState[] D) => i >= 0 && i < drones.Count && i < D.Length && D[i].mode != 4;

        static Vector3 Flat(Vector3 p, float y) => new Vector3(p.x, y, p.z);

        void Beam(LineRenderer lr, bool on, Vector3 a, Vector3 b, Color c, float w, Camera cam, float flicker)
        {
            lr.enabled = on;
            if (!on) return;
            lr.SetPosition(0, a);
            lr.SetPosition(1, b);
            float near = cam != null ? DistanceToSegment(cam.transform.position, a, b) : 200f;
            lr.widthMultiplier = w * Mathf.Clamp(near / 150f, 0.2f, 4f) * (0.75f + 0.25f * Mathf.Sin(Time.time * flicker));
            SwarmMaterials.SetBlock(block, c * 0.4f, c * glow * 1.4f);
            lr.SetPropertyBlock(block);
        }

        // ------------------------------------------------------------------ patlama, duman, toz
        void AddBlast(Vector3 localPos, float size, float delay)
        {
            Blast b = null;
            foreach (var x in blasts)
                if (!x.T.gameObject.activeSelf) { b = x; break; }
            if (b == null)
            {
                var g = Prim(PrimitiveType.Sphere, ewRoot, Vector3.zero, Vector3.one, Mat(ref blastMat,
                    () => SwarmMaterials.Transparent(new Color(1f, 0.55f, 0.15f, 0.65f), glow * 3f)));
                g.name = "Patlama";
                g.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
                b = new Blast { T = g.transform, L = new GameObject("Isik").AddComponent<Light>() };
                b.L.transform.SetParent(b.T, false);
                b.L.type = LightType.Point;
                b.L.color = new Color(1f, 0.6f, 0.25f);
                b.L.range = 60f;
                blasts.Add(b);
            }
            b.T.localPosition = localPos;
            b.T.localScale = Vector3.zero;
            b.Born = Time.time + delay;
            b.Size = size;
            b.T.gameObject.SetActive(true);
        }

        void AddPuff(Vector3 localPos, Vector3 vel, float size, float life, Color c)
        {
            if (puffs.Count > 500) return;
            Puff p;
            if (puffPool.Count > 0) { p = puffPool[puffPool.Count - 1]; puffPool.RemoveAt(puffPool.Count - 1); }
            else
            {
                var g = Prim(PrimitiveType.Quad, transform, Vector3.zero, Vector3.one, Mat(ref puffMat, MakePuffMaterial));
                g.name = "Duman";
                p = new Puff { T = g.transform, R = g.GetComponent<Renderer>(), Spin = Random.Range(0f, 360f) };
                p.R.shadowCastingMode = ShadowCastingMode.Off;
                p.R.receiveShadows = false;
            }
            p.T.localPosition = localPos;
            p.V = vel;
            p.Born = Time.time;
            p.Life = life;
            p.Size = size;
            p.C = c;
            p.T.gameObject.SetActive(true);
            puffs.Add(p);
        }

        void AnimateFx(float dt)
        {
            float lum = SwarmMaterials.IsHdrp ? 80000f : 8f;
            var cam = RenderCamera;
            var look = cam != null ? cam.transform.forward : Vector3.forward;
            foreach (var b in blasts)
            {
                if (!b.T.gameObject.activeSelf) continue;
                float k = Time.time - b.Born;
                if (k < 0f) { b.T.localScale = Vector3.zero; b.L.intensity = 0f; continue; }
                if (k > 0.9f) { b.T.gameObject.SetActive(false); continue; }
                b.T.localScale = Vector3.one * b.Size * Mathf.Clamp01(k / 0.3f + 0.15f);
                b.L.intensity = lum * (1f - k / 0.9f);
                if (k < dt * 1.5f)   // patlamanın ilk anında bir tutam koyu duman
                    for (int i = 0; i < 4; i++)
                        AddPuff(b.T.localPosition + Random.insideUnitSphere * b.Size * 0.2f, Vector3.up * Random.Range(2f, 5f) + Random.insideUnitSphere * 2f,
                                b.Size * 0.45f, 4f, new Color(0.16f, 0.15f, 0.14f, 0.6f));
            }
            for (int i = smokes.Count - 1; i >= 0; i--)
            {
                var s = smokes[i];
                if (Time.time > s.Until) { smokes.RemoveAt(i); continue; }
                if (Time.time < s.Next) continue;
                s.Next = Time.time + s.Rate;
                float fade = Mathf.Clamp01((s.Until - Time.time) / 15f);
                var c = s.C;
                c.a *= fade;
                AddPuff(s.P + new Vector3(Random.Range(-1f, 1f), 0f, Random.Range(-1f, 1f)), new Vector3(windNow.x * 0.6f + 0.8f, 3.2f, windNow.y * 0.6f)
                        + Random.insideUnitSphere * 0.8f, s.Size * 1.5f, 8f, c);
            }
            for (int i = puffs.Count - 1; i >= 0; i--)
            {
                var p = puffs[i];
                float k = (Time.time - p.Born) / p.Life;
                if (k >= 1f)
                {
                    p.T.gameObject.SetActive(false);
                    puffs.RemoveAt(i);
                    puffPool.Add(p);
                    continue;
                }
                p.T.localPosition += p.V * dt;
                p.V *= 1f - 0.35f * dt;
                p.T.localScale = Vector3.one * p.Size * (0.6f + 1.8f * Mathf.Sqrt(k));
                p.T.rotation = Quaternion.LookRotation(look) * Quaternion.Euler(0f, 0f, p.Spin + 25f * k);   // kameraya bakar, yavaşça döner
                var c = p.C;
                c.a *= (1f - k) * Mathf.Clamp01(k * 8f);
                SwarmMaterials.SetBlock(block, c, Color.black);
                p.R.SetPropertyBlock(block);
            }
        }

        // Radar vuruldu (kamikaze): büyük patlama, kararır, sürekli tüter
        void RadarDestroyed(RadarView v)
        {
            var p = v.Root.localPosition;
            AddBlast(p + Vector3.up * 3f, 26f, 0f);
            AddBlast(p + new Vector3(7f, 2f, 1.5f), 16f, 0.35f);   // füze rampası da infilak eder
            smokes.Add(new SmokeSource { P = p + Vector3.up * 3f, Until = Time.time + 1e6f, Size = 8f, Rate = 0.09f,
                                         C = new Color(0.08f, 0.08f, 0.08f, 0.6f) });
            Char(v.Rends, true);
        }
    }
}
