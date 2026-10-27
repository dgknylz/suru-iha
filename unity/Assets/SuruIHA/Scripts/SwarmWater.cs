using UnityEngine;

namespace SuruIHA
{
    // Kızılırmak'ın akışı: su yüzeyinin dalgacık dokusu akış yönünde (batıdan doğuya) kayar
    public class SwarmWater : MonoBehaviour
    {
        [Tooltip("Doku tekrarı / s (16 m'lik dokuda 0,06 ≈ 1 m/s akış)")]
        public float speed = 0.06f;
        Material mat;

        void Start()
        {
            if (TryGetComponent(out Renderer r)) mat = r.material;
        }

        void Update()
        {
            if (mat != null) mat.SetTextureOffset("_BaseColorMap", new Vector2(0f, -Time.time * speed));
        }
    }
}
