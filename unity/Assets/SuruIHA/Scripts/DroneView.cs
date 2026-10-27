using UnityEngine;

namespace SuruIHA
{
    // Tek bir İHA'nın görüntüsü: model, dönen pervaneler, durum LED'i, uçuş izi
    // ve GPS yokken "İHA'nın sandığı konum" hayaleti.
    public class DroneView : MonoBehaviour
    {
        public int Id { get; private set; }
        public DroneState State { get; private set; }
        public Vector3 Velocity => smoothVel;

        SwarmVisualizer vis;
        Transform model;
        Transform[] props;
        Renderer[] leds;
        MaterialPropertyBlock block;
        TrailRenderer trail;
        Transform ghost, beacon;
        Renderer strobe;
        float strobePhase;
        MaterialPropertyBlock strobeBlock;
        Renderer beaconRenderer;
        LineRenderer ghostLine, sigmaRing;
        Vector3 targetLocal, estLocal, smoothVel;
        bool hasState;
        float propAngle;

        public static readonly Color ColNormal = new Color(0.15f, 1f, 0.55f);
        public static readonly Color ColJammed = new Color(1f, 0.62f, 0.1f);
        public static readonly Color ColNoGps = new Color(1f, 0.18f, 0.15f);
        public static readonly Color ColSearch = new Color(0.25f, 0.6f, 1f);
        public static readonly Color ColSpoof = new Color(0.8f, 0.25f, 1f);
        public static readonly Color ColRelay = new Color(0.1f, 0.95f, 1f);
        public static readonly Color ColFailed = new Color(0.05f, 0.05f, 0.05f);
        public static readonly Color ColGpsSpoofed = new Color(1f, 0.35f, 0.75f);   // GPS'i aldatılıyor (fark etmedi)
        public static readonly Color ColSpoofSeen = new Color(1f, 0.92f, 0.25f);    // aldatmayı fark etti

        bool Failed => State != null && State.mode == 4;
        bool Parked => State != null && (State.phase == 6 || (State.phase == 0 && transform.localPosition.y - GroundY < 0.8f));
        float GroundY => vis.GroundAt(transform.position) - vis.transform.position.y;
        float tumble;

        public static DroneView Create(SwarmVisualizer vis, Transform parent, int id)
        {
            var go = new GameObject($"IHA_{id:00}");
            go.transform.SetParent(parent, false);
            var d = go.AddComponent<DroneView>();
            d.Init(vis, id);
            return d;
        }

        void Init(SwarmVisualizer v, int id)
        {
            vis = v;
            Id = id;
            block = new MaterialPropertyBlock();
            strobeBlock = new MaterialPropertyBlock();

            if (vis.droneModel != null)
            {
                model = Instantiate(vis.droneModel, transform).transform;
                model.name = "Model";
                model.localPosition = Vector3.zero;
                model.localRotation = Quaternion.identity;
                foreach (var c in model.GetComponentsInChildren<Collider>()) SwarmVisualizer.SafeDestroy(c);
            }
            else
            {
                model = BuildProceduralModel(transform, vis);
            }
            model.localScale = Vector3.one * vis.droneScale;

            // Modeldeki "Prop" ile başlayan parçalar döner, "LED_Status" durum ışığıdır
            var propList = new System.Collections.Generic.List<Transform>();
            var ledList = new System.Collections.Generic.List<Renderer>();
            foreach (var t in model.GetComponentsInChildren<Transform>())
            {
                if (t.name.StartsWith("Prop")) propList.Add(t);
                if (t.name.StartsWith("LED_Status") && t.TryGetComponent(out Renderer r))
                {
                    r.sharedMaterial = vis.Mats.Led;
                    ledList.Add(r);
                }
            }
            props = propList.ToArray();
            leds = ledList.ToArray();

            // Dönen pervanenin yarı saydam bulanık diski (kamera görüntüsündeki gibi)
            foreach (var p in props)
            {
                var disc = SwarmVisualizer.Prim(PrimitiveType.Cylinder, p.parent, p.localPosition + Vector3.up * 0.004f,
                    new Vector3(0.38f, 0.0015f, 0.38f), vis.Mats.PropBlur);
                disc.name = "PervaneDiski";
                disc.GetComponent<Renderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }

            // Beyaz çarpışma önleme flaşı (gerçek İHA'lardaki gibi çift çakma)
            strobe = SwarmVisualizer.Prim(PrimitiveType.Sphere, model, new Vector3(0f, 0.114f, -0.07f),
                Vector3.one * 0.022f, vis.Mats.Led).GetComponent<Renderer>();
            strobe.name = "CarpismaFlasi";
            strobe.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            strobePhase = (id * 0.37f) % 1.3f;

            trail = gameObject.AddComponent<TrailRenderer>();
            trail.sharedMaterial = vis.Mats.Trail;
            trail.time = vis.trailSeconds;
            trail.minVertexDistance = 1.5f;
            trail.widthCurve = new AnimationCurve(new Keyframe(0, 0.08f * vis.droneScale), new Keyframe(1, 0));
            trail.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            trail.emitting = vis.showTrails;

            // Uzak işaret: kamera uzaklaştıkça büyüyen, durum renginde parlayan nokta
            // (yüzlerce metre öteden de İHA'lar ve durumları seçilebilsin)
            beacon = SwarmVisualizer.Prim(PrimitiveType.Sphere, transform, Vector3.zero, Vector3.one, vis.Mats.Led).transform;
            beacon.name = "UzakIsaret";
            beaconRenderer = beacon.GetComponent<Renderer>();
            beaconRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;

            // Hayalet: GPS kaybolunca İHA'nın kendini sandığı yer
            ghost = SwarmVisualizer.Prim(PrimitiveType.Sphere, transform.parent, Vector3.zero,
                Vector3.one * 0.7f * vis.droneScale, vis.Mats.Ghost).transform;
            ghost.name = $"IHA_{id:00}_Kestirim";
            ghostLine = SwarmVisualizer.MakeLine(ghost, vis.Mats.GhostLine, 0.04f * vis.droneScale, 2, true);
            sigmaRing = SwarmVisualizer.MakeCircle(ghost, 1f, 48, vis.Mats.GhostLine, 0.05f * vis.droneScale);
            ghost.gameObject.SetActive(false);
        }

        // Film kesmesi: bir sonraki karede yumuşatmadan yeni konuma geç
        public void Snap()
        {
            hasState = false;
            if (trail != null) trail.Clear();     // kesmede (ya da bölge değişince) iz uzun bir çizgi bırakmasın
        }

        // Durum ışığının rengi (arayüzdeki İHA seçici ve bilgi kartı da aynısını kullanır)
        public static Color StatusColor(DroneState s) =>
            s.mode == 4 ? ColFailed : s.mode == 2 ? ColSpoof : s.mode == 3 ? ColRelay
            : s.mode == 7 ? ColSpoofSeen : s.mode == 6 ? ColGpsSpoofed
            : s.gps == 0 ? ColNoGps : s.mode == 1 ? ColSearch : s.jam > 0.35f ? ColJammed : ColNormal;

        public static string StatusName(DroneState s) =>
            s.mode == 4 ? "arızalı" : s.mode == 2 ? "saldırgan" : s.mode == 3 ? "röle"
            : s.mode == 7 ? "aldatmayı fark etti" : s.mode == 6 ? "GPS'i aldatılıyor"
            : s.mode == 5 ? "GPS'i geri almaya gidiyor" : s.gps == 0 ? "GPS yok, tahminle uçuyor"
            : s.mode == 1 ? "spiral arama yapıyor" : s.jam > 0.35f ? "karıştırılıyor" : "normal";

        public static string PhaseName(int phase) => phase switch
        {
            0 => "kalkış", 1 => "düzende intikal", 2 => "görev", 3 => "toplanma", 4 => "düzende dönüş", 5 => "iniş", _ => "indi",
        };

        public void SetState(DroneState s)
        {
            State = s;
            targetLocal = SwarmFrame.Enu(s.p);
            estLocal = SwarmFrame.Enu(s.e);
            if (!hasState)
            {
                transform.localPosition = targetLocal;
                trail.Clear();
                hasState = true;
            }
            Color c = StatusColor(s);
            SwarmMaterials.SetBlock(block, c * 0.3f, c * vis.glow * 2f);
            foreach (var r in leds) r.SetPropertyBlock(block);
            beaconRenderer.SetPropertyBlock(block);
            trail.emitting = vis.showTrails && s.mode != 4 && s.phase != 6;
            if (!Application.isPlaying)
            {
                // Editör önizlemesi: yumuşatma yok, her şeyi hemen yerine koy
                var v = SwarmFrame.Enu(s.v);
                Vector3 flat = new Vector3(v.x, 0, v.z);
                if (flat.sqrMagnitude > 0.5f)
                    model.localRotation = Quaternion.LookRotation(flat.normalized) *
                                          Quaternion.Euler(Mathf.Clamp(flat.magnitude * 1.6f, 0f, 22f), 0, 0);
                ghost.localPosition = estLocal;
                UpdateGhost();
            }
        }

        void Update()
        {
            if (!hasState) return;
            float dt = Time.deltaTime;
            Vector3 prev = transform.localPosition;
            transform.localPosition = Vector3.Lerp(prev, targetLocal, 1f - Mathf.Exp(-10f * dt));
            Vector3 v = (transform.localPosition - prev) / Mathf.Max(dt, 1e-4f);
            smoothVel = Vector3.Lerp(smoothVel, v, 1f - Mathf.Exp(-4f * dt));

            // Arızalanan İHA dönerek düşer
            if (Failed && transform.localPosition.y - GroundY > 0.6f)
            {
                tumble += 400f * dt;
                model.localRotation = Quaternion.Euler(tumble * 0.7f, tumble, tumble * 0.3f);
            }
            // Gövde, hız yönüne bakar ve hızlandıkça öne yatar (gerçek quadcopter gibi)
            Vector3 flat = new Vector3(smoothVel.x, 0, smoothVel.z);
            if (!Failed && flat.sqrMagnitude > 0.5f)
            {
                float tilt = Mathf.Clamp(flat.magnitude * 1.6f, 0f, 22f);
                Quaternion want = Quaternion.LookRotation(flat.normalized) * Quaternion.Euler(tilt, 0, 0);
                model.localRotation = Quaternion.Slerp(model.localRotation, want, 1f - Mathf.Exp(-3f * dt));
            }

            float st = (Time.time + strobePhase) % 1.3f;
            bool flash = st < 0.05f || (st > 0.16f && st < 0.21f);
            if (Failed || Parked) flash = false;
            SwarmMaterials.SetBlock(strobeBlock, Color.white * 0.4f, flash ? Color.white * vis.glow * 10f : Color.black);
            strobe.SetPropertyBlock(strobeBlock);

            // İndikten sonra motorlar durur (gerçek İHA'lar inişte motoru kilitler)
            float rpm = Failed || Parked ? 0f : transform.localPosition.y - GroundY > 1.5f ? 2400f : 900f;
            propAngle = (propAngle + rpm * 6f * dt) % 360f;
            for (int i = 0; i < props.Length; i++)
            {
                // Çapraz pervaneler ters yönde döner
                float dir = (i % 2 == 0) ? 1f : -1f;
                props[i].localRotation = Quaternion.Euler(0, propAngle * dir, 0);
            }

            UpdateGhost();
        }

        void LateUpdate() => UpdateBeacon(vis.RenderCamera);

        public void UpdateBeacon(Camera cam)
        {
            if (cam == null || beacon == null) return;
            float d = Vector3.Distance(cam.transform.position, transform.position);
            // Yakında gizli (model zaten görünüyor), uzakta ekranda sabit boyutlu bir nokta
            bool show = vis.showBeacons && d > 45f;
            if (beacon.gameObject.activeSelf != show) beacon.gameObject.SetActive(show);
            if (show) beacon.localScale = Vector3.one * d * 0.0065f * Mathf.Clamp01((d - 45f) / 40f);
            beacon.localPosition = Vector3.up * 0.4f * vis.droneScale;
        }

        void UpdateGhost()
        {
            bool show = vis.showEstimates && State != null && State.mode != 2 &&
                        (State.gps == 0 || (estLocal - targetLocal).magnitude > 4f);
            if (ghost.gameObject.activeSelf != show) ghost.gameObject.SetActive(show);
            if (!show) return;
            ghost.localPosition = Vector3.Lerp(ghost.localPosition, estLocal, 0.3f);
            ghostLine.SetPosition(0, ghost.position);
            ghostLine.SetPosition(1, transform.position);
            float r = Mathf.Max(State.sigma, 1f) / ghost.lossyScale.x;
            sigmaRing.transform.localScale = new Vector3(r, 1f, r);
        }

        // Blender modeli yoksa kodla basit ama düzgün bir quadcopter kurar
        static Transform BuildProceduralModel(Transform parent, SwarmVisualizer vis)
        {
            var root = new GameObject("Model").transform;
            root.SetParent(parent, false);
            var M = vis.Mats;
            SwarmVisualizer.Prim(PrimitiveType.Cube, root, Vector3.zero, new Vector3(0.32f, 0.08f, 0.22f), M.Body);
            SwarmVisualizer.Prim(PrimitiveType.Sphere, root, new Vector3(0, 0.05f, 0.02f), new Vector3(0.2f, 0.08f, 0.18f), M.Shell);
            SwarmVisualizer.Prim(PrimitiveType.Sphere, root, new Vector3(0, -0.06f, 0.09f), Vector3.one * 0.06f, M.Dark);
            for (int k = 0; k < 4; k++)
            {
                float a = (45f + 90f * k) * Mathf.Deg2Rad;
                var dir = new Vector3(Mathf.Sin(a), 0, Mathf.Cos(a));
                SwarmVisualizer.Prim(PrimitiveType.Cube, root, dir * 0.17f, new Vector3(0.025f, 0.025f, 0.32f), M.Dark,
                    Quaternion.LookRotation(dir));
                SwarmVisualizer.Prim(PrimitiveType.Cylinder, root, dir * 0.32f + Vector3.up * 0.02f, new Vector3(0.05f, 0.025f, 0.05f), M.Body);
                var prop = new GameObject($"Prop_{k}").transform;
                prop.SetParent(root, false);
                prop.localPosition = dir * 0.32f + Vector3.up * 0.055f;
                SwarmVisualizer.Prim(PrimitiveType.Cube, prop, Vector3.zero, new Vector3(0.24f, 0.004f, 0.025f), M.Dark);
                SwarmVisualizer.Prim(PrimitiveType.Cylinder, prop, Vector3.zero, new Vector3(0.24f, 0.001f, 0.24f), M.PropBlur);
            }
            var led = SwarmVisualizer.Prim(PrimitiveType.Sphere, root, new Vector3(0, -0.04f, -0.12f), Vector3.one * 0.05f, M.Led);
            led.name = "LED_Status";
            return root;
        }
    }
}
