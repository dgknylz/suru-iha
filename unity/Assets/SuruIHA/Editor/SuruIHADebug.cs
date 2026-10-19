using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace SuruIHA.EditorTools
{
    // Teşhis: arazi katmanları ve karışım ağırlıklarını günlüğe yazar.
    public static class SuruIHADebug
    {
        [MenuItem("SürüİHA/Teşhis/Arazi Bilgisi")]
        public static void TerrainInfo()
        {
            EditorSceneManager.OpenScene("Assets/SuruIHA/Scenes/SuruSahnesi.unity");
            var t = GameObject.Find("Arazi").GetComponent<Terrain>();
            var dps = t.terrainData.detailPrototypes;
            Debug.Log($"[SuruIHA][arazi] detay prototip={dps.Length} mesafe={t.detailObjectDistance} çizilsin={t.drawTreesAndFoliage} res={t.terrainData.detailResolution}");
            for (int i = 0; i < dps.Length; i++)
            {
                bool ok = dps[i].Validate(out string msg);
                int adet = 0;
                var layer = t.terrainData.GetDetailLayer(0, 0, t.terrainData.detailWidth, t.terrainData.detailHeight, i);
                foreach (var v in layer) adet += v;
                Debug.Log($"[SuruIHA][arazi] detay {i}: {dps[i].prototype?.name} geçerli={ok} {msg} toplam={adet} instancing={dps[i].useInstancing} mod={dps[i].renderMode}");
            }
            var td = t.terrainData;
            Debug.Log($"[SuruIHA][arazi] malzeme={t.materialTemplate?.shader?.name} katman={td.terrainLayers.Length} " +
                      $"alphamap={td.alphamapResolution} ağaç={td.treeInstanceCount}");
            foreach (var l in td.terrainLayers)
                Debug.Log($"[SuruIHA][arazi] katman {l.name}: doku={l.diffuseTexture?.name} normal={l.normalMapTexture?.name} tile={l.tileSize}");
            var am = td.GetAlphamaps(0, 0, td.alphamapWidth, td.alphamapHeight);
            int n = td.alphamapLayers;
            var sum = new double[n];
            for (int y = 0; y < td.alphamapHeight; y += 8)
            for (int x = 0; x < td.alphamapWidth; x += 8)
            for (int k = 0; k < n; k++) sum[k] += am[y, x, k];
            double tot = sum.Sum();
            Debug.Log("[SuruIHA][arazi] ortalama ağırlıklar: " + string.Join(", ", sum.Select((s, i) => $"{i}:{s / tot:0.000}")));
        }
    }
}
