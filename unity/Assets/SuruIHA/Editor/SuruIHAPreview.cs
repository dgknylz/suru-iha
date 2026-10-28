using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace SuruIHA.EditorTools
{
    // Play'e basmadan, kaydedilmiş bir simülasyon karesiyle sahnenin ekran görüntüsünü alır.
    // Komut satırı:
    //   Unity -batchmode -projectPath ... -executeMethod SuruIHA.EditorTools.SuruIHAPreview.FromCommandLine
    //         -frame kare.json -out klasor
    public static class SuruIHAPreview
    {
        public static void FromCommandLine()
        {
            var args = Environment.GetCommandLineArgs();
            string Arg(string k, string d) { int i = Array.IndexOf(args, k); return i >= 0 && i + 1 < args.Length ? args[i + 1] : d; }
            string frame = Arg("-frame", "kare.json");
            string outDir = Arg("-out", "Preview");
            Render(frame, outDir);
        }

        public static void Render(string framePath, string outDir)
        {
            Directory.CreateDirectory(outDir);
            var scene = EditorSceneManager.OpenScene("Assets/SuruIHA/Scenes/SuruSahnesi.unity");
            var vis = UnityEngine.Object.FindAnyObjectByType<SwarmVisualizer>();
            var f = JsonUtility.FromJson<SwarmFrame>(File.ReadAllText(framePath));
            vis.PreviewFrame(f);
            DumpDrone(vis);

            var cam = Camera.main;
            Vector3 c = vis.Centroid;
            var j = f.jammers != null && f.jammers.Length > 0 ? SwarmFrame.Enu(f.jammers[0].p) : Vector3.zero;
            var d0 = vis.Drones.Count > 0 ? vis.Drones[0].transform.position : c;
            var shots = new (string name, Vector3 pos, Vector3 look, float fov)[]
            {
                ("1_genel", new Vector3(-260, 150, -330), new Vector3(60, 20, 60), 55),
                ("2_suru", c + new Vector3(-90, 45, -110), c, 50),
                ("3_karistirici", j + new Vector3(-55, 22, -60), j + new Vector3(0, 8, 0), 55),
                ("4_iha_yakin", d0 + new Vector3(-9, 3, -10), d0, 40),
                ("5_taktik", new Vector3(0, 900, -1), new Vector3(0, 0, 0), 60),
                ("6_istasyon", new Vector3(-75, 25, -60), new Vector3(-30, 5, -4), 50),
                ("7_tarla", new Vector3(-420, 18, 200), new Vector3(0, 10, 300), 60),
                ("8_tepeler", new Vector3(200, 60, 500), new Vector3(300, 60, 1000), 60),
                ("9_zemin_bozkir", Ground(-640, 250, 2.5f), Ground(-560, 330, 4f), 60),
                ("10_zemin_ova", Ground(-200, -150, 2.2f), Ground(-60, -60, 6f), 60),
                ("11_koy", Ground(-250, -455, 38f), Ground(-385, -565, 4f), 55),
                ("12_koy_sokak", Ground(-335, -548, 2.5f), Ground(-430, -520, 5f), 60),
                ("13_elektrik_hatti", Ground(-118, -60, 6f), Ground(-150, 140, 8f), 55),
            };
            foreach (var s in shots)
            {
                cam.transform.position = s.pos;
                cam.transform.LookAt(s.look);
                cam.fieldOfView = s.fov;
                foreach (var dv in vis.Drones) dv.UpdateBeacon(cam);
                Capture(cam, Path.Combine(outDir, s.name + ".png"));
            }
            // Karlı bölge (12 km doğu): vadi ve dağlar (kış havası yerel hacimden gelir)
            var o = SwarmRegions.SnowOffset;
            cam.transform.position = o + new Vector3(-260, 150, -330);
            cam.transform.LookAt(o + new Vector3(60, 20, 60));
            cam.fieldOfView = 55;
            Capture(cam, Path.Combine(outDir, "14_kar_genel.png"));
            // Kızılırmak (12 km batı): nehir, köprü ve kızıl yar
            var r = SwarmRegions.RiverOffset;
            cam.transform.position = r + new Vector3(-230, 70, 260);
            cam.transform.LookAt(r + new Vector3(-10, 0, 470));
            cam.fieldOfView = 55;
            Capture(cam, Path.Combine(outDir, "15_kizilirmak.png"));
            // Yeni bölgeler: suları yalnızca kendi çekiminde açık
            void Region(string regionId)
            {
                foreach (var ro in UnityEngine.Object.FindObjectsByType<SwarmRegionObject>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                    ro.gameObject.SetActive(ro.region == regionId);
            }
            void Shot(string file, Vector3 org, Vector2 at, float above, Vector2 to, float toAbove, float viewFov)
            {
                cam.transform.position = RegionGround(org, at.x, at.y, above);
                cam.transform.LookAt(RegionGround(org, to.x, to.y, toAbove));
                cam.fieldOfView = viewFov;
                Capture(cam, Path.Combine(outDir, file + ".png"));
            }
            var dv0 = SwarmRegions.DivrigiOffset;
            Region("divrigi");
            Shot("16_divrigi_genel", dv0, new Vector2(-330, 930), 120, new Vector2(-20, 400), 20, 55);
            Shot("17_ulu_cami", dv0, new Vector2(-150, 540), 14, new Vector2(-110, 452), 8, 50);
            Shot("17b_ulu_cami_bati", dv0, new Vector2(-185, 430), 10, new Vector2(-126, 440), 8, 55);
            Shot("17c_divrigi_kale", dv0, new Vector2(-40, 520), 60, new Vector2(170, 250), 20, 50);
            var gk = SwarmRegions.GokpinarOffset;
            Region("gokpinar");
            Shot("18_gokpinar_golu", gk, new Vector2(-60, 330), 26, new Vector2(-140, 430), -2, 55);
            Shot("18b_gokpinar_yakin", gk, new Vector2(-180, 395), 6, new Vector2(-120, 445), -3, 60);
            var sea = SwarmRegions.SeaOffset;
            Region("deniz");
            Shot("19_akdeniz_koy", sea, new Vector2(330, 360), 45, new Vector2(-120, 420), -15, 60);
            Shot("19b_akdeniz_fener", sea, new Vector2(250, 640), 20, new Vector2(430, 600), 5, 55);
            Shot("19c_akdeniz_liman", sea, new Vector2(-150, 300), 30, new Vector2(-20, 360), -16, 55);
            Region("ova");
            Debug.Log("[SuruIHA] Önizlemeler: " + outDir);
        }

        // Bölgenin (dünya kökü o) yerel x, z noktasında arazinin üstü
        static Vector3 RegionGround(Vector3 o, float x, float z, float above)
        {
            var w = new Vector3(o.x + x, 0f, o.z + z);
            foreach (var t in Terrain.activeTerrains)
            {
                var p = t.transform.position;
                var s = t.terrainData.size;
                if (w.x >= p.x && w.x <= p.x + s.x && w.z >= p.z && w.z <= p.z + s.z)
                    return new Vector3(w.x, t.SampleHeight(w) + p.y + above, w.z);
            }
            return new Vector3(w.x, o.y + above, w.z);
        }

        static Vector3 Ground(float x, float z, float above)
        {
            var go = GameObject.Find("Arazi");
            var t = go != null ? go.GetComponent<Terrain>() : Terrain.activeTerrain;
            float y = t != null ? t.SampleHeight(new Vector3(x, 0, z)) + t.transform.position.y : 0f;
            return new Vector3(x, y + above, z);
        }

        static void DumpDrone(SwarmVisualizer vis)
        {
            if (vis.Drones.Count == 0) return;
            var d = vis.Drones[0];
            foreach (var t in d.GetComponentsInChildren<Transform>().Take(40))
            {
                var r = t.GetComponent<Renderer>();
                Debug.Log($"[SuruIHA][dump] {t.name} lp={t.localPosition} lr={t.localEulerAngles} ls={t.localScale}" +
                          (r != null ? $" b={r.bounds.size}" : ""));
            }
        }

        static void Capture(Camera cam, string path)
        {
            int w = 1920, h = 1080;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32) { antiAliasing = 1 };
            var prev = cam.targetTexture;
            cam.targetTexture = rt;
            // HDRP'nin pozlama, bulut ve TAA geçmişi otursun diye birkaç kare çiz
            for (int i = 0; i < 24; i++) cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            File.WriteAllBytes(path, tex.EncodeToPNG());
            RenderTexture.active = null;
            cam.targetTexture = prev;
            UnityEngine.Object.DestroyImmediate(rt);
            UnityEngine.Object.DestroyImmediate(tex);
        }
    }
}
