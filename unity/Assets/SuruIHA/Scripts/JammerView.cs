using UnityEngine;

namespace SuruIHA
{
    // Karıştırıcı (jammer): araç/kule modeli, etki alanını gösteren yarı saydam kubbe
    // ve yerde dışa doğru yayılan sinyal halkaları.
    public class JammerView : MonoBehaviour
    {
        SwarmVisualizer vis;
        Transform dome;
        LineRenderer[] waves;
        LineRenderer edge;
        float radius = 100f;
        Light beacon;

        public static JammerView Create(SwarmVisualizer vis, Transform parent, int id)
        {
            var go = new GameObject($"Karistirici_{id}");
            go.transform.SetParent(parent, false);
            var j = go.AddComponent<JammerView>();
            j.Init(vis);
            return j;
        }

        void Init(SwarmVisualizer v)
        {
            vis = v;
            var M = v.Mats;
            Vector3 tipPos = new Vector3(0, 12.3f, -1.5f);
            if (v.jammerModel != null)
            {
                var m = Instantiate(v.jammerModel, transform);
                m.name = "Model";
                foreach (var c in m.GetComponentsInChildren<Collider>()) SwarmVisualizer.SafeDestroy(c);
                var b = SwarmVisualizer.FindDeep(m.transform, "Beacon");
                if (b != null) tipPos = transform.InverseTransformPoint(b.position);
            }
            else
            {
                SwarmVisualizer.Prim(PrimitiveType.Cube, transform, new Vector3(0, 1.2f, 0), new Vector3(3, 2.4f, 6), M.Body);
                SwarmVisualizer.Prim(PrimitiveType.Cylinder, transform, new Vector3(0, 7f, -1.5f), new Vector3(0.25f, 5f, 0.25f), M.Metal);
                for (int k = 0; k < 3; k++)
                    SwarmVisualizer.Prim(PrimitiveType.Cube, transform, new Vector3(0, 10f - k * 1.2f, -1.5f),
                        new Vector3(2.2f - k * 0.5f, 0.12f, 0.12f), M.Metal, Quaternion.Euler(0, k * 60f, 0));
            }
            var tip = SwarmVisualizer.Prim(PrimitiveType.Sphere, transform, tipPos, Vector3.one * 0.35f, M.GhostLine);
            tip.name = "IkazLambasi";

            beacon = new GameObject("IkazIsigi").AddComponent<Light>();
            beacon.transform.SetParent(tip.transform, false);
            beacon.type = LightType.Point;
            beacon.color = new Color(1f, 0.2f, 0.1f);
            beacon.range = 40f;
            beacon.intensity = 0f;

            var d = SwarmVisualizer.Prim(PrimitiveType.Sphere, transform, Vector3.zero, Vector3.one, M.Dome);
            d.name = "EtkiKubbesi";
            d.GetComponent<Renderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            dome = d.transform;
            edge = SwarmVisualizer.MakeCircle(transform, 1f, 128, M.DomeRing, 0.45f);
            edge.transform.localPosition = Vector3.up * 0.6f;
            waves = new LineRenderer[3];
            for (int k = 0; k < waves.Length; k++)
            {
                waves[k] = SwarmVisualizer.MakeCircle(transform, 1f, 128, M.DomeRing, 0.3f);
                waves[k].transform.localPosition = Vector3.up * (0.8f + k * 0.1f);
            }
        }

        public void Set(JammerState s)
        {
            var p = SwarmFrame.Enu(s.p);
            transform.localPosition = new Vector3(p.x, 0f, p.z);
            radius = Mathf.Max(s.r, 5f);
            if (!Application.isPlaying) Animate(1.3f);
        }

        void Update() => Animate(Time.time);

        void Animate(float t)
        {
            dome.gameObject.SetActive(vis.showDome);
            dome.localScale = Vector3.one * radius * 2f;
            edge.transform.localScale = new Vector3(radius, 1, radius);
            for (int k = 0; k < waves.Length; k++)
            {
                float ph = Mathf.Repeat(t * 0.35f + k / (float)waves.Length, 1f);
                waves[k].transform.localScale = new Vector3(radius * ph, 1, radius * ph);
                waves[k].widthMultiplier = Mathf.Lerp(0.5f, 0.05f, ph);
            }
            float on = SwarmMaterials.IsHdrp ? 20000f : 4f;   // HDRP fiziksel birim (lümen) kullanır
            beacon.intensity = Mathf.Sin(t * 8f) > 0 ? on : 0f;
        }
    }
}
