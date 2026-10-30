using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace SuruIHA
{
    // Hava savunma ve rüzgâr: radar (dönen anten, tarama çizgisi, izlenen İHA'ya kırmızı kilit çizgisi), füzeler
    // (duman izi, vurunca patlama), sürünün radar kestirimi (kerteriz), radar görüş örtüsü (taramada tespit
    // olasılığı, araziye serili), dirençli İHA'ların radardan kaçan rotaları ve üsteki rüzgâr tulumu.
    public partial class SwarmVisualizer
    {
        [Header("Hava savunma")]
        public GameObject radarModel;
        [Tooltip("Radarın görüş alanı (bir taramada İHA'yı görme olasılığı) araziye serilir")]
        public bool showRadarMap = true;

        static readonly Color RadarCol = new Color(1f, 0.78f, 0.2f);      // tarama ve görüş örtüsü: kehribar
        static readonly Color LockCol = new Color(1f, 0.08f, 0.3f);       // kilit (iz) çizgisi: kızıl
        static readonly Color RadarEstCol = new Color(1f, 0.35f, 0.75f);  // sürünün radar kestirimi

        class RadarView
        {
            public Transform Root, Antenna, Model;
            public Quaternion AntennaBase = Quaternion.identity;   // antenin kökteki ilk duruşu (modelin eksen çevirimi dahil)
            public LineRenderer[] Sweep;
            public LineRenderer Ring;
            public readonly List<LineRenderer> Locks = new List<LineRenderer>();
            public Light Beacon;
            public float Az, Rate = 180f, FrameT, R = 400f;
            public bool On, Dead;
            public Renderer[] Rends;   // modelin parçaları (imha edilince kararır)
            public int[] Trk;
        }

        class MissileView
        {
            public int Id, St;
            public Transform Root, Flash;
            public TrailRenderer Trail;
            public Light Glow;
            public Vector3 P, V;
            public float FrameT, EndT = -1f, SeenT;
        }

        readonly List<RadarView> radarViews = new List<RadarView>();
        readonly Dictionary<int, MissileView> missileViews = new Dictionary<int, MissileView>();
        readonly List<MissileView> missilePool = new List<MissileView>();
        readonly List<EstMarker> radarEst = new List<EstMarker>();
        Material lockMat, sweepMat, smokeMat, flashMat, exhaustMat;
        Transform windsock;
        Vector2 windNow;

        Material Mat(ref Material m, System.Func<Material> make) => m != null ? m : (m = make());

        // ------------------------------------------------------------------ radar
        void ApplyRadars(SwarmFrame f)
        {
            var R = f.radars ?? new RadarState[0];
            while (radarViews.Count < R.Length) radarViews.Add(MakeRadar(radarViews.Count));
            for (int i = 0; i < radarViews.Count; i++)
            {
                var v = radarViews[i];
                bool show = i < R.Length && (R[i].on == 1 || R[i].known == 1 || R[i].dead == 1);   // pusu radarı açılana kadar görünmez
                v.Root.gameObject.SetActive(show);
                if (!show) continue;
                var s = R[i];
                var p = SwarmFrame.Enu(s.p);
                v.Root.localPosition = new Vector3(p.x, LocalGround(p.x, p.z), p.z);
                bool dead = s.dead == 1;
                if (dead && !v.Dead) RadarDestroyed(v);                 // SwarmVisualizer.Convoy.cs
                else if (!dead && v.Dead) Char(v.Rends, false);
                v.Dead = dead;
                float dt = Time.time - v.FrameT;
                if (v.On && s.on == 1 && dt > 1e-3f)
                    v.Rate = Mathf.Clamp(Mathf.Repeat(s.az - v.Az, 360f) / dt, 30f, 2000f);   // simülasyon hızlanınca anten de hızlanır
                v.Az = s.az;
                v.FrameT = Time.time;
                v.On = s.on == 1;
                v.R = Mathf.Max(s.r, 50f);
                v.Trk = s.trk;
            }
        }

        RadarView MakeRadar(int id)
        {
            var v = new RadarView { Root = NewChildOf(ewRoot, $"Radar_{id}") };
            Vector3 beaconPos = new Vector3(0, 3f, 0);
            if (radarModel != null)
            {
                var m = Instantiate(radarModel, v.Root);
                m.name = "Model";
                foreach (var c in m.GetComponentsInChildren<Collider>()) SafeDestroy(c);
                v.Model = m.transform;
                v.Antenna = FindDeep(m.transform, "Anten");
                var b = FindDeep(m.transform, "Beacon");
                if (b != null) beaconPos = v.Root.InverseTransformPoint(b.position);
            }
            if (v.Antenna != null) v.AntennaBase = Quaternion.Inverse(v.Root.rotation) * v.Antenna.rotation;
            if (v.Antenna == null)
            {
                Prim(PrimitiveType.Cube, v.Root, new Vector3(0, 0.9f, 0), new Vector3(2.4f, 1.8f, 5f), Mats.Body);
                var a = new GameObject("Anten").transform;
                a.SetParent(v.Root, false);
                a.localPosition = new Vector3(0, 2.4f, 0);
                Prim(PrimitiveType.Cube, a, new Vector3(0, 1f, 0.2f), new Vector3(3.6f, 1.8f, 0.25f), Mats.Metal, Quaternion.Euler(-14f, 0, 0));
                v.Antenna = a;
            }
            v.Rends = v.Root.GetComponentsInChildren<Renderer>();
            v.Beacon = new GameObject("RadarIsigi").AddComponent<Light>();
            v.Beacon.transform.SetParent(v.Root, false);
            v.Beacon.transform.localPosition = beaconPos;
            v.Beacon.type = LightType.Point;
            v.Beacon.color = new Color(1f, 0.25f, 0.1f);
            v.Beacon.range = 35f;
            v.Beacon.intensity = 0f;
            var sm = Mat(ref sweepMat, () => SwarmMaterials.Glow(RadarCol, glow * 0.7f));
            v.Sweep = new LineRenderer[4];
            for (int k = 0; k < v.Sweep.Length; k++)
            {
                v.Sweep[k] = MakeLine(v.Root, sm, 1.2f, 2, false);
                v.Sweep[k].name = "Tarama";
                var c = RadarCol * (1f - k * 0.24f);
                SwarmMaterials.SetBlock(block, c * 0.2f, c * glow * (0.7f - k * 0.16f));
                v.Sweep[k].SetPropertyBlock(block);
            }
            v.Ring = MakeCircle(v.Root, 1f, 160, Mats.DomeRing, 0.6f);
            v.Ring.name = "Menzil";
            SwarmMaterials.SetBlock(block, RadarCol * 0.25f, RadarCol * glow * 0.35f);
            v.Ring.SetPropertyBlock(block);
            return v;
        }

        void AnimateRadars()
        {
            var cam = RenderCamera;
            var D = Frame?.drones;
            for (int i = 0; i < radarViews.Count; i++)
            {
                var v = radarViews[i];
                if (!v.Root.gameObject.activeSelf) continue;
                float az = v.On ? v.Az + v.Rate * (Time.time - v.FrameT) : v.Az;
                // Dünyanın dikey ekseni etrafında döndür: FBX düğümlerinin kendi eksen çevirimi (Blender Z-yukarı)
                // yerel eksenleri yatırır; yerel eksende döndürülen anten yere yatar
                if (v.Antenna != null) v.Antenna.rotation = v.Root.rotation * Quaternion.AngleAxis(az, Vector3.up) * v.AntennaBase;
                float far = cam != null ? Mathf.Clamp(Vector3.Distance(cam.transform.position, v.Root.position) / 200f, 0.08f, 5f) : 1f;
                float top = 45f;   // tarama çizgisi uçuş yüksekliğinde (yerden 40 m)
                for (int k = 0; k < v.Sweep.Length; k++)
                {
                    var lr = v.Sweep[k];
                    lr.enabled = v.On;
                    if (!v.On) continue;
                    float a = (az - k * 4f) * Mathf.Deg2Rad;
                    var dir = new Vector3(Mathf.Sin(a), 0f, Mathf.Cos(a));
                    lr.SetPosition(0, new Vector3(0f, 5f, 0f));
                    lr.SetPosition(1, dir * v.R * 1.25f + Vector3.up * top);
                    lr.widthMultiplier = (0.9f - k * 0.18f) * far;
                }
                v.Ring.enabled = v.On && showDome;
                v.Ring.transform.localPosition = Vector3.up * 1f;
                v.Ring.transform.localScale = new Vector3(v.R, 1f, v.R);
                v.Ring.widthMultiplier = 0.6f * Mathf.Max(far, 0.3f);
                float on = SwarmMaterials.IsHdrp ? 18000f : 4f;
                v.Beacon.intensity = v.On && Mathf.Sin(Time.time * 7f) > 0 ? on : 0f;
                // Kilit çizgileri: anten -> izlenen İHA (kalın, nabız gibi)
                int n = v.On && v.Trk != null ? v.Trk.Length : 0;
                var lm = Mat(ref lockMat, () => SwarmMaterials.Glow(LockCol, glow * 1.2f));
                while (v.Locks.Count < n) { var l = MakeLine(linkRoot, lm, 0.5f, 2, true); l.name = "Kilit"; v.Locks.Add(l); }
                Vector3 src = v.Antenna != null ? v.Antenna.position + Vector3.up * 1.8f : v.Root.position + Vector3.up * 4f;
                for (int k = 0; k < v.Locks.Count; k++)
                {
                    int d = k < n ? v.Trk[k] : -1;
                    bool ok = d >= 0 && d < drones.Count && D != null && d < D.Length && D[d].mode != 4;
                    v.Locks[k].enabled = ok;
                    if (!ok) continue;
                    var b = drones[d].transform.position;
                    v.Locks[k].SetPosition(0, src);
                    v.Locks[k].SetPosition(1, b);
                    float near = cam != null ? DistanceToSegment(cam.transform.position, src, b) : 200f;
                    v.Locks[k].widthMultiplier = 0.45f * Mathf.Clamp(near / 120f, 0.15f, 3f) * (0.75f + 0.25f * Mathf.Sin(Time.time * 12f));
                }
            }
        }

        // ------------------------------------------------------------------ füzeler
        void ApplyMissiles(SwarmFrame f)
        {
            var M = f.missiles ?? new MissileState[0];
            var seen = new HashSet<int>();
            foreach (var s in M)
            {
                seen.Add(s.id);
                if (!missileViews.TryGetValue(s.id, out var v))
                {
                    v = GetMissile();
                    v.Id = s.id;
                    v.St = 0;
                    v.EndT = -1f;
                    v.P = SwarmFrame.Enu(s.p);
                    v.Root.localPosition = v.P;
                    v.Trail.Clear();
                    v.Trail.emitting = true;
                    v.Flash.gameObject.SetActive(false);
                    v.Root.gameObject.SetActive(true);
                    missileViews[s.id] = v;
                }
                v.P = SwarmFrame.Enu(s.p);
                v.V = SwarmFrame.Enu(s.v);
                v.FrameT = Time.time;
                v.SeenT = Time.time;
                if (s.st != 0 && v.St == 0)
                {
                    // Patlama: vurduysa büyük, ıskaladıysa (kendini imha) küçük
                    v.St = s.st;
                    v.EndT = Time.time;
                    v.Trail.emitting = false;
                    v.Flash.gameObject.SetActive(true);
                    v.Root.localPosition = v.P;
                }
            }
            // Listeden çıkan füzeler (iz söndükten sonra) havuza döner
            var gone = new List<int>();
            foreach (var kv in missileViews)
                if (!seen.Contains(kv.Key) && Time.time - kv.Value.SeenT > 3f) gone.Add(kv.Key);
            foreach (int id in gone)
            {
                missileViews[id].Root.gameObject.SetActive(false);
                missilePool.Add(missileViews[id]);
                missileViews.Remove(id);
            }
        }

        MissileView GetMissile()
        {
            if (missilePool.Count > 0)
            {
                var r = missilePool[missilePool.Count - 1];
                missilePool.RemoveAt(missilePool.Count - 1);
                return r;
            }
            var v = new MissileView { Root = NewChildOf(ewRoot, "Fuze") };
            var body = Prim(PrimitiveType.Capsule, v.Root, Vector3.zero, new Vector3(0.35f, 1.4f, 0.35f), Mats.Shell, Quaternion.Euler(90f, 0, 0));
            body.name = "Govde";
            var ex = Prim(PrimitiveType.Sphere, v.Root, new Vector3(0, 0, -1.5f), Vector3.one * 0.7f,
                          Mat(ref exhaustMat, () => SwarmMaterials.Glow(new Color(1f, 0.6f, 0.2f), glow * 4f)));
            ex.name = "Alev";
            v.Trail = v.Root.gameObject.AddComponent<TrailRenderer>();
            v.Trail.sharedMaterial = Mat(ref smokeMat, () => SwarmMaterials.Transparent(new Color(0.92f, 0.92f, 0.9f, 0.55f), 0.05f));
            v.Trail.time = 3.5f;
            v.Trail.minVertexDistance = 1.5f;
            v.Trail.widthCurve = new AnimationCurve(new Keyframe(0f, 0.5f), new Keyframe(0.3f, 1.6f), new Keyframe(1f, 3.2f));
            v.Trail.colorGradient = new Gradient
            {
                colorKeys = new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                alphaKeys = new[] { new GradientAlphaKey(0.85f, 0f), new GradientAlphaKey(0.35f, 0.4f), new GradientAlphaKey(0f, 1f) },
            };
            v.Trail.shadowCastingMode = ShadowCastingMode.Off;
            v.Glow = new GameObject("Isik").AddComponent<Light>();
            v.Glow.transform.SetParent(v.Root, false);
            v.Glow.type = LightType.Point;
            v.Glow.color = new Color(1f, 0.6f, 0.25f);
            v.Glow.range = 30f;
            var fl = Prim(PrimitiveType.Sphere, v.Root, Vector3.zero, Vector3.one, Mat(ref flashMat,
                () => SwarmMaterials.Transparent(new Color(1f, 0.55f, 0.15f, 0.6f), glow * 3f)));
            fl.name = "Patlama";
            fl.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
            v.Flash = fl.transform;
            return v;
        }

        void AnimateMissiles()
        {
            float lum = SwarmMaterials.IsHdrp ? 60000f : 6f;
            foreach (var v in missileViews.Values)
            {
                if (v.St == 0)
                {
                    // Kareler arasında hızla ileri kestir (füze 180 m/s: kare kare atlamasın)
                    v.Root.localPosition = v.P + v.V * Mathf.Min(Time.time - v.FrameT, 0.1f);
                    if (v.V.sqrMagnitude > 1f) v.Root.localRotation = Quaternion.LookRotation(v.V.normalized);
                    v.Glow.intensity = lum * 0.3f;
                    v.Root.GetChild(0).gameObject.SetActive(true);
                    v.Root.GetChild(1).gameObject.SetActive(true);
                    continue;
                }
                float k = Time.time - v.EndT;
                float big = v.St == 1 ? 16f : 6f;
                v.Root.GetChild(0).gameObject.SetActive(false);
                v.Root.GetChild(1).gameObject.SetActive(false);
                v.Flash.gameObject.SetActive(k < 0.8f);
                v.Flash.localScale = Vector3.one * big * Mathf.Clamp01(k / 0.35f + 0.15f);
                v.Glow.intensity = k < 0.6f ? lum * (v.St == 1 ? 2.5f : 0.8f) * (1f - k / 0.6f) : 0f;
            }
        }

        // ------------------------------------------------------------------ sürünün radar kestirimi
        void ApplyRadarEstimates(SwarmFrame f)
        {
            var E = f.radarEst ?? new RadarEstState[0];
            if (f.strategy != "resilient") E = new RadarEstState[0];
            while (radarEst.Count < E.Length)
            {
                var m = new EstMarker { Root = NewChildOf(ewRoot, "RadarTahmini") };
                m.Ring = MakeCircle(m.Root, 1f, 96, Mats.TaskRing, 0.5f);
                m.CrossA = MakeLine(m.Root, Mats.TaskRing, 0.7f, 2, false);
                m.CrossB = MakeLine(m.Root, Mats.TaskRing, 0.7f, 2, false);
                m.CrossA.SetPositions(new[] { new Vector3(-14, 0, -14), new Vector3(14, 0, 14) });
                m.CrossB.SetPositions(new[] { new Vector3(-14, 0, 14), new Vector3(14, 0, -14) });
                m.Err = MakeLine(ewRoot, Mats.GhostLine, 0.35f, 2, true);
                SwarmMaterials.SetBlock(block, RadarEstCol, RadarEstCol * glow);
                foreach (var lr in new[] { m.Ring, m.CrossA, m.CrossB }) lr.SetPropertyBlock(block);
                radarEst.Add(m);
            }
            var cam = RenderCamera;
            for (int i = 0; i < radarEst.Count; i++)
            {
                var m = radarEst[i];
                bool on = i < E.Length;
                m.Root.gameObject.SetActive(on);
                m.Err.enabled = false;
                if (!on) continue;
                var p = SwarmFrame.Enu(E[i].p);
                float g = LocalGround(p.x, p.z) + 1.5f;
                m.Root.localPosition = new Vector3(p.x, g, p.z);
                m.Ring.transform.localScale = Vector3.one * Mathf.Max(E[i].e, 8f);
                // Uzaktan seçilsin, yakından (radara yakın plan) modeli örtmesin: kalınlık kamera uzaklığıyla
                float far = cam != null ? Mathf.Clamp(Vector3.Distance(cam.transform.position, m.Root.position) / 150f, 0.15f, 5f) : 1f;
                m.Ring.widthMultiplier = 0.5f * far;
                m.CrossA.widthMultiplier = m.CrossB.widthMultiplier = 0.7f * far;
                m.CrossA.transform.localScale = m.CrossB.transform.localScale = Vector3.one * Mathf.Sqrt(Mathf.Max(far, 0.5f));
                // Gerçek radara hata çizgisi
                var R = f.radars;
                if (R != null && E[i].id >= 0 && E[i].id < R.Length)
                {
                    var q = SwarmFrame.Enu(R[E[i].id].p);
                    m.Err.enabled = true;
                    m.Err.widthMultiplier = 0.35f * far;
                    m.Err.SetPosition(0, transform.TransformPoint(new Vector3(p.x, g + 1f, p.z)));
                    m.Err.SetPosition(1, transform.TransformPoint(new Vector3(q.x, LocalGround(q.x, q.z) + 3f, q.z)));
                }
            }
        }

        // ------------------------------------------------------------------ radar görüş örtüsü
        GameObject rfGo;
        Mesh rfMesh;
        Material rfMat;
        Texture2D rfTex, rfEmit;
        string rfQ, rfGeom;
        Vector3 rfBuiltPos;
        public RadarFieldState RadarField { get; private set; }

        void ApplyRadarField(SwarmFrame f)
        {
            var F = f.radarField;
            if (F != null && F.nx > 1 && F.ny > 1 && !string.IsNullOrEmpty(F.q) && F.q != rfQ)
            {
                byte[] q = null;
                try { q = System.Convert.FromBase64String(F.q); }
                catch (System.FormatException) { }
                if (q != null && q.Length == F.nx * F.ny)
                {
                    rfQ = F.q;
                    RadarField = F;
                    string geom = $"{F.x0}|{F.y0}|{F.step}|{F.nx}|{F.ny}";
                    if (geom != rfGeom || (transform.position - rfBuiltPos).sqrMagnitude > 0.01f)
                    {
                        BuildRadarMesh(F);
                        rfGeom = geom;
                    }
                    PaintRadarField(F, q);
                }
            }
            if (f.radars == null || f.radars.Length == 0) { RadarField = null; rfQ = null; }
            if (RadarField != null && rfGo != null && (transform.position - rfBuiltPos).sqrMagnitude > 0.01f) BuildRadarMesh(RadarField);
            if (rfGo != null) rfGo.SetActive(showRadarMap && RadarField != null);
        }

        void BuildRadarMesh(RadarFieldState F)
        {
            if (rfGo == null)
            {
                rfGo = new GameObject("RadarGorusHaritasi");
                rfGo.transform.SetParent(ewRoot, false);
                rfMesh = new Mesh { name = "RadarGorus", indexFormat = IndexFormat.UInt32 };
                rfGo.AddComponent<MeshFilter>().sharedMesh = rfMesh;
                var mr = rfGo.AddComponent<MeshRenderer>();
                mr.shadowCastingMode = ShadowCastingMode.Off;
                rfMat = new Material(Mats.HeatMap) { name = "RadarGorus" };
                if (SwarmMaterials.IsHdrp && !rfMat.IsKeywordEnabled("_EMISSIVE_COLOR_MAP")) SwarmMaterials.SetEmission(rfMat, Color.black, 0f);
                mr.sharedMaterial = rfMat;
            }
            int vx = (F.nx - 1) * FieldSub + 1, vy = (F.ny - 1) * FieldSub + 1;
            int W = (F.nx - 1) * FieldUp + 1, H = (F.ny - 1) * FieldUp + 1;
            float d = F.step / FieldSub;
            var verts = new Vector3[vx * vy];
            var uv = new Vector2[vx * vy];
            var terrains = Terrain.activeTerrains;
            for (int j = 0, k = 0; j < vy; j++)
            for (int i = 0; i < vx; i++, k++)
            {
                float x = F.x0 + i * d, z = F.y0 + j * d;
                verts[k] = new Vector3(x, HeatGround(terrains, x, z) + FieldLift + 0.3f, z);   // karıştırma örtüsünün az üstü
                uv[k] = new Vector2(((float)i / FieldSub * FieldUp + 0.5f) / W, ((float)j / FieldSub * FieldUp + 0.5f) / H);
            }
            var tris = new int[(vx - 1) * (vy - 1) * 6];
            for (int j = 0, t = 0; j < vy - 1; j++)
            for (int i = 0; i < vx - 1; i++)
            {
                int a = j * vx + i;
                tris[t++] = a; tris[t++] = a + vx; tris[t++] = a + 1;
                tris[t++] = a + 1; tris[t++] = a + vx; tris[t++] = a + vx + 1;
            }
            rfMesh.Clear();
            rfMesh.vertices = verts;
            rfMesh.uv = uv;
            rfMesh.triangles = tris;
            rfMesh.RecalculateNormals();
            rfMesh.RecalculateBounds();
            rfBuiltPos = transform.position;
        }

        float[] rfVals;
        Color32[] rfPx, rfEmitPx;

        // Kehribar tek ton: olasılık arttıkça koyulaşır; Pd = 0,5 (yarı yarıya görülür) parlak bir çizgiyle çizilir
        void PaintRadarField(RadarFieldState F, byte[] q)
        {
            int nx = F.nx, ny = F.ny;
            int W = (nx - 1) * FieldUp + 1, H = (ny - 1) * FieldUp + 1;
            if (rfTex == null || rfTex.width != W || rfTex.height != H)
            {
                SafeDestroy(rfTex);
                SafeDestroy(rfEmit);
                rfTex = NewHeatTexture(W, H, "RadarGorus");
                rfEmit = NewHeatTexture(W, H, "RadarGorusParlama");
                SwarmMaterials.SetOverlayTexture(rfMat, rfTex, rfEmit);
                rfVals = new float[W * H];
                rfPx = new Color32[W * H];
                rfEmitPx = new Color32[W * H];
            }
            for (int b = 0, k = 0; b < H; b++)
            {
                float gy = (float)b / FieldUp;
                int j0 = Mathf.Min((int)gy, ny - 2);
                float fy = gy - j0;
                for (int a = 0; a < W; a++, k++)
                {
                    float gx = (float)a / FieldUp;
                    int i0 = Mathf.Min((int)gx, nx - 2);
                    float fx = gx - i0;
                    int r0 = j0 * nx + i0, r1 = r0 + nx;
                    rfVals[k] = ((q[r0] * (1 - fx) + q[r0 + 1] * fx) * (1 - fy) + (q[r1] * (1 - fx) + q[r1 + 1] * fx) * fy) / 255f;
                }
            }
            var light = new Color(1f, 0.93f, 0.55f);
            var deep = new Color(1f, 0.68f, 0.08f);       // kehribar sarısı: kırmızı karıştırma örtüsüyle karışmasın
            float fade = 6f * FieldUp;
            float regionK = SwarmRegions.Current == "kar" ? 0.6f : 1f;
            for (int b = 0, k = 0; b < H; b++)
            for (int a = 0; a < W; a++, k++)
            {
                float pd = rfVals[k];
                Color32 c;
                if (RadarCross(k, a, b, W, H, 0.5f)) c = new Color32(255, 236, 170, 210);
                else if (pd < 0.05f) c = new Color32(0, 0, 0, 0);
                else
                {
                    var col = Color.Lerp(light, deep, Mathf.Clamp01((pd - 0.05f) / 0.9f));
                    col.a = Mathf.Lerp(0.05f, 0.34f, Mathf.Clamp01((pd - 0.05f) / 0.9f));
                    c = col;
                }
                float e = Mathf.Clamp01(Mathf.Min(Mathf.Min(a, W - 1 - a), Mathf.Min(b, H - 1 - b)) / fade);
                c.a = (byte)(c.a * e * e * (3f - 2f * e) * regionK);
                rfPx[k] = c;
                rfEmitPx[k] = new Color32((byte)(c.r * c.a / 255), (byte)(c.g * c.a / 255), (byte)(c.b * c.a / 255), 255);
            }
            rfTex.SetPixels32(rfPx);
            rfTex.Apply(false);
            rfEmit.SetPixels32(rfEmitPx);
            rfEmit.Apply(false);
        }

        bool RadarCross(int k, int a, int b, int W, int H, float level)
        {
            bool s = rfVals[k] >= level;
            if (!s) return false;
            if (a + 1 < W && rfVals[k + 1] < level) return true;
            if (a > 0 && rfVals[k - 1] < level) return true;
            if (b + 1 < H && rfVals[k + W] < level) return true;
            if (b > 0 && rfVals[k - W] < level) return true;
            return false;
        }

        // ------------------------------------------------------------------ rüzgâr
        void ApplyWind(SwarmFrame f)
        {
            windNow = f.wind != null && f.wind.Length >= 2 ? new Vector2(f.wind[0], f.wind[1]) : Vector2.zero;
            if (this == Main) SwarmRegions.SetWind(windNow);
            if (windsock == null && gcs != null) windsock = MakeWindsock();
        }

        // Üsteki rüzgâr tulumu: kırmızı-beyaz bant, rüzgâr güçlendikçe yataylaşır ve esintiyle salınır
        Transform MakeWindsock()
        {
            var root = NewChildOf(transform, "RuzgarTulumu");
            Prim(PrimitiveType.Cylinder, root, new Vector3(0, 3.5f, 0), new Vector3(0.12f, 3.5f, 0.12f), Mats.Metal);
            var pivot = NewChildOf(root, "Tulum");
            pivot.localPosition = new Vector3(0, 6.8f, 0);
            var red = SwarmMaterials.Lit(new Color(0.85f, 0.12f, 0.08f), 0f, 0.3f);
            var white = SwarmMaterials.Lit(new Color(0.92f, 0.92f, 0.9f), 0f, 0.3f);
            for (int k = 0; k < 5; k++)
            {
                float r = Mathf.Lerp(0.42f, 0.22f, k / 4f);
                Prim(PrimitiveType.Cylinder, pivot, new Vector3(0, 0, 0.45f + k * 0.62f), new Vector3(r * 2f, 0.31f, r * 2f),
                     k % 2 == 0 ? red : white, Quaternion.Euler(90f, 0, 0));
            }
            return root;
        }

        void AnimateWindsock()
        {
            if (windsock == null || gcs == null) return;
            windsock.localPosition = gcs.localPosition + new Vector3(14f, 0f, -10f);
            var w = new Vector3(windNow.x, 0f, windNow.y);
            float s = w.magnitude;
            var pivot = windsock.GetChild(1);
            float sway = Mathf.Sin(Time.time * 1.7f) * 6f + Mathf.Sin(Time.time * 4.3f) * 2f;
            float droop = Mathf.Lerp(80f, 4f, Mathf.Clamp01(s / 9f));
            var dir = s > 0.3f ? Quaternion.LookRotation(w / s) : Quaternion.identity;
            pivot.localRotation = dir * Quaternion.Euler(droop, sway * Mathf.Clamp01(s / 3f), 0f);
        }

        // ------------------------------------------------------------------ dirençli İHA'nın radardan kaçan rotası
        // Plan çizgisinin ilk ayağı, düz çizgi yerine İHA'nın izleyeceği rotadan (tepelerin ardı, vadiler) çizilir.
        int RouteStart(int[] route, Vector3 a)
        {
            int n = route.Length / 2, best = 1;
            float bd = float.MaxValue;
            for (int k = 0; k + 1 < n; k++)
            {
                var p = new Vector2(route[2 * k], route[2 * k + 1]);
                var q = new Vector2(route[2 * k + 2], route[2 * k + 3]);
                var x = new Vector2(a.x, a.z);
                var ab = q - p;
                float t = ab.sqrMagnitude > 1e-3f ? Mathf.Clamp01(Vector2.Dot(x - p, ab) / ab.sqrMagnitude) : 0f;
                float d = (p + t * ab - x).sqrMagnitude;
                if (d < bd) { bd = d; best = k + 1; }
            }
            return best;
        }

        Vector3 RoutePoint(int[] route, int k, float y) =>
            transform.TransformPoint(new Vector3(route[2 * k], y, route[2 * k + 1]));
    }
}
