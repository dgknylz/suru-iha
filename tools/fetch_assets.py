"""Fotoğraf tabanlı dokuları ve kaya modelini Poly Haven'dan indirir (CC0: ücretsiz, atıf gerekmez).

    python tools/fetch_assets.py [çıktı_klasörü]      (varsayılan C:\\SuruIHA\\assets\\polyhaven)

Her varlık kendi klasörüne iner; dosyalar Poly Haven'ın verdiği MD5 ile doğrulanır. Dokulardan HDRP'nin
istediği maske haritası da üretilir (ARM: R ortam kapatma, G pürüz, B metal -> HDRP maske: R metal,
G ortam kapatma, B yükseklik, A pürüzsüzlük). İndirilmiş dosya varsa ve doğruysa yeniden indirilmez.
tools/sync_unity.ps1 bunları Unity projesine kopyalar (Textures/Photo, Models/Photo).
"""
import hashlib
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\SuruIHA\assets\polyhaven"
API = "https://api.polyhaven.com"
RES = "2k"
UA = {"User-Agent": "SuruIHA-TUBITAK-2204/1.0"}

# Dokular (renk, normal, ARM) ve modeller (glTF)
TEXTURES = ["aerial_grass_rock", "withered_grass", "dry_ground_01", "farm_soil", "dirt_aerial_02", "aerial_rocks_02",
            "gravelly_sand", "bark_brown_02", "pine_bark",
            # Karlı bölge
            "snow_field_aerial", "snow_02", "snow_04", "snow_05",
            # Kızılırmak (Sivas)
            "terrain_red_01", "red_laterite_soil_stones", "river_small_rocks"]
MODELS = ["boulder_01"]


def download(url, tries=6):
    """Parça parça okur. Bağlantı takılırsa (30 s veri gelmezse) ya da hız çok düşerse yeni bağlantıyla dener."""
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                buf, t0 = bytearray(), time.time()
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        return bytes(buf)
                    buf += chunk
                    el = time.time() - t0
                    if el > 20 and len(buf) / el < 50_000:       # 50 KB/s altı: takılmış bağlantı
                        raise TimeoutError("yavaş bağlantı")
        except (TimeoutError, OSError) as e:
            if k == tries - 1:
                raise
            print(f"  yeniden deneniyor ({e}): {os.path.basename(url)}")


def get_json(url):
    return json.loads(download(url))


def fetch(url, path, md5):
    if os.path.exists(path) and hashlib.md5(open(path, "rb").read()).hexdigest() == md5:
        return False
    data = download(url)
    if hashlib.md5(data).hexdigest() != md5:
        raise RuntimeError(f"MD5 tutmadı: {url}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return True


def mask_from_arm(arm_path, out_path):
    a = np.asarray(Image.open(arm_path).convert("RGB"), dtype=np.uint8)
    m = np.empty(a.shape[:2] + (4,), np.uint8)
    m[..., 0] = a[..., 2]                 # metal
    m[..., 1] = a[..., 0]                 # ortam kapatma
    m[..., 2] = 128                       # yükseklik (yok: orta)
    m[..., 3] = 255 - a[..., 1]           # pürüzsüzlük = 1 - pürüz
    Image.fromarray(m, "RGBA").save(out_path)


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest, jobs = {}, []
    for aid in TEXTURES + MODELS:
        info = get_json(f"{API}/info/{aid}")
        files = get_json(f"{API}/files/{aid}")
        d = os.path.join(OUT, aid)
        got = []
        if aid in TEXTURES:
            for key, suffix in (("Diffuse", "diff"), ("nor_gl", "nor_gl"), ("arm", "arm")):
                e = files[key][RES]["jpg"]
                jobs.append((e["url"], os.path.join(d, f"{aid}_{suffix}_{RES}.jpg"), e["md5"]))
                got.append(f"{aid}_{suffix}_{RES}.jpg")
        else:
            g = files["gltf"][RES]["gltf"]
            jobs.append((g["url"], os.path.join(d, os.path.basename(g["url"])), g["md5"]))
            got.append(os.path.basename(g["url"]))
            for rel, e in g["include"].items():
                jobs.append((e["url"], os.path.join(d, rel), e["md5"]))
                got.append(rel)
        manifest[aid] = {"name": info.get("name"), "authors": list(info.get("authors", {}).keys()),
                         "dimensions_mm": info.get("dimensions"), "files": got,
                         "source": f"https://polyhaven.com/a/{aid}", "license": "CC0"}

    def one(job):
        new = fetch(*job)
        print(f"{'indi' if new else 'zaten var'}: {os.path.basename(job[1])}")

    with ThreadPoolExecutor(4) as ex:          # dört dosya aynı anda
        list(ex.map(one, jobs))

    # HDRP maske haritaları (doku setleri ve modelin dokusu)
    for aid in TEXTURES:
        d = os.path.join(OUT, aid)
        mask_from_arm(os.path.join(d, f"{aid}_arm_{RES}.jpg"), os.path.join(d, f"{aid}_mask_{RES}.png"))
        manifest[aid]["files"].append(f"{aid}_mask_{RES}.png")
    for aid in MODELS:
        arm = os.path.join(OUT, aid, "textures", f"{aid}_arm_{RES}.jpg")
        if os.path.exists(arm):                  # modelin dokusu kayalara üç yönlü eşlemeyle de giydirilir
            mask_from_arm(arm, os.path.join(OUT, aid, "textures", f"{aid}_mask_{RES}.png"))
            manifest[aid]["files"].append(f"textures/{aid}_mask_{RES}.png")
    print(f"ok: {len(manifest)} varlık, {len(jobs)} dosya")
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "LISANS.txt"), "w", encoding="utf-8") as f:
        f.write("Bu klasördeki dokular ve modeller Poly Haven'dan (https://polyhaven.com) alınmıştır.\n"
                "Lisans: CC0 1.0 (kamu malı). Ücretsizdir, ticari kullanım dahil serbesttir, atıf gerekmez.\n"
                "Yazarlar ve kaynak bağlantıları manifest.json dosyasındadır.\n")


if __name__ == "__main__":
    main()
