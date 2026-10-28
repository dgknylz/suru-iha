using UnityEngine;

namespace SuruIHA
{
    // Yalnızca belirli bir bölgede açık olan sahne nesnesi (deniz ve göl suyu gibi). SwarmRegions bölge değişince açar/kapatır;
    // sahne kurulurken kapalı kaydedilir.
    public class SwarmRegionObject : MonoBehaviour
    {
        public string region;
    }
}
