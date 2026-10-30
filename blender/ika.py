"""Konvoy koruma görevinin kara unsurları: İKA (insansız kara aracı), düşman pusu mevzisi ve tanksavar mayını.

    blender -b -P blender/ika.py -- <çıktı_klasörü>
Çıktı: SuruIHA_IKA.fbx, SuruIHA_Pusu.fbx, SuruIHA_Mayin.fbx

İKA: 4x4 zırhlı insansız kara aracı (~4,6 m), sensör direğinde EO/IR kamera, uzaktan kumandalı silah istasyonu,
tavanında turuncu dost tanıma paneli (havadaki İHA'lar dost aracı bununla ayırır). Tekerler ("Teker_*") ve
silah kulesi ("Kule") ayrı parça, doğrudan kökün altında: Unity tekerleri döndürür, kuleyi çevirir.
Pusu: kamuflaj ağı altında silahlı arazi aracı, kum torbası siperi. "Namlu" ateşin çıktığı yer.
Mayın: TM-62 benzeri tanksavar mayını, yarı gömülü; "Bayrak" bulununca dikilen ikaz bayrağı (Unity açar).
"""
import math
import os
import random
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
random.seed(7)


def materials():
    return dict(
        camo=C.mat("MAT_Camo", (0.135, 0.15, 0.095), rough=0.78),
        camo2=C.mat("MAT_Camo_Dark", (0.08, 0.09, 0.06), rough=0.8),
        tire=C.mat("MAT_Tire", (0.018, 0.018, 0.018), rough=0.95),
        rim=C.mat("MAT_Rim", (0.11, 0.12, 0.085), rough=0.6, metal=0.4),
        glass=C.mat("MAT_Glass", (0.01, 0.014, 0.018), rough=0.04, metal=0.3),
        metal=C.mat("MAT_Metal", (0.5, 0.51, 0.52), rough=0.38, metal=1.0),
        black=C.mat("MAT_Black", (0.02, 0.02, 0.022), rough=0.6),
        lamp=C.mat("MAT_Lamp", (0.9, 0.85, 0.7), rough=0.1, emission=(1.0, 0.9, 0.7), strength=1.0),
        accent=C.mat("MAT_Accent", (0.75, 0.32, 0.05), rough=0.4, metal=0.6),
        stripe=C.mat("MAT_Stripe", (0.75, 0.6, 0.12), rough=0.6),
        sand=C.mat("MAT_Sandbag", (0.36, 0.31, 0.21), rough=0.95),
        tan=C.mat("MAT_Tan", (0.33, 0.27, 0.18), rough=0.82),
        net=C.mat("MAT_Net", (0.11, 0.115, 0.07), rough=0.95),
        beacon=C.mat("MAT_Beacon", (1.0, 0.08, 0.04), emission=(1.0, 0.08, 0.04), strength=12.0),
    )


def wheel(M, name, x, y, r, w, parent, lugs=26):
    parts = [C.cyl(name + "_Lastik", r, w, (0, 0, 0), M["tire"], verts=44, rot=(0, math.pi / 2, 0), bevel=0.08, segments=3)]
    for k in range(lugs):
        a = k * math.tau / lugs
        parts.append(C.box(f"{name}_Dis{k}", (w * 0.42, 0.075, 0.045),
                           (math.copysign(w * 0.22, (-1) ** k), math.cos(a) * (r + 0.004), math.sin(a) * (r + 0.004)),
                           M["tire"], rot=(a, 0, 0)))
    side = 1 if x > 0 else -1
    parts.append(C.cyl(name + "_Jant", r * 0.55, w + 0.02, (side * 0.02, 0, 0), M["rim"], verts=32, rot=(0, math.pi / 2, 0), bevel=0.02))
    parts.append(C.cyl(name + "_Gobek", r * 0.2, w + 0.08, (side * 0.03, 0, 0), M["metal"], verts=16, rot=(0, math.pi / 2, 0)))
    for k in range(8):
        a = k * math.tau / 8
        parts.append(C.cyl(f"{name}_Bijon{k}", 0.017, 0.04, (side * (w / 2 + 0.03), math.cos(a) * r * 0.36, math.sin(a) * r * 0.36),
                           M["metal"], verts=8, rot=(0, math.pi / 2, 0)))
    o = C.join(parts, name)
    o.location = (x, y, r)
    o.parent = parent
    return o


def wedge_hull(M, name, L, W, H, z0, nose, tail):
    """Eğimli zırh gövdesi (V tabanlı, önü -Y): sekizgen kesitli, burun ve kıç eğik."""
    bm = bmesh.new()
    half = W / 2
    # Kesit (x, z): V taban, dik yanlar, içe eğik üst yanlar
    sec = [(-half * 0.55, z0), (half * 0.55, z0), (half, z0 + H * 0.28), (half, z0 + H * 0.7),
           (half * 0.78, z0 + H), (-half * 0.78, z0 + H), (-half, z0 + H * 0.7), (-half, z0 + H * 0.28)]
    rings = []
    for y, sc, dz in ((-L / 2, nose, H * 0.12), (-L / 2 + 0.75, 1.0, 0.0), (L / 2 - 0.35, 1.0, 0.0), (L / 2, tail, 0.05)):
        ring = []
        for x, z in sec:
            zz = z0 + (z - z0) * (sc if z > z0 + H * 0.5 else 1.0) + (dz if z < z0 + H * 0.5 else 0.0)
            ring.append(bm.verts.new((x * (0.93 if sc < 1 else 1.0), y, zz)))
        rings.append(ring)
    n = len(sec)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = C.mesh_object(name, bm, M["camo"], smooth=False)
    C.add_bevel(o, 0.035, 2)
    C.shade_smooth(o, 30.0)
    return o


# ======================================================================= İKA
def build_ika():
    C.reset_scene()
    M = materials()
    root = C.empty("SuruIHA_IKA")
    L, W = 4.6, 2.1
    hull = [wedge_hull(M, "Govde_Zirh", L, W, 1.05, 0.62, 0.55, 0.85)]
    # Çamurluklar, basamaklar, kancalar
    for sx in (-1, 1):
        for y in (-1.45, 1.35):
            hull.append(C.box(f"Camurluk_{sx}_{y}", (0.5, 1.15, 0.06), (sx * 1.12, y, 1.32), M["camo2"], bevel=0.015))
            hull.append(C.box(f"Camurluk_Lastik_{sx}_{y}", (0.48, 0.04, 0.3), (sx * 1.12, y + 0.56, 1.15), M["black"]))
        hull.append(C.box(f"Yan_Kutu_{sx}", (0.18, 1.3, 0.4), (sx * 1.13, 0.0, 1.2), M["camo"], bevel=0.02))
        for y in (-0.35, 0.35):
            hull.append(C.box(f"Yan_Kutu_Mandal_{sx}_{y}", (0.03, 0.08, 0.12), (sx * 1.23, y, 1.25), M["metal"]))
        hull.append(C.box(f"Cekme_Kanca_On_{sx}", (0.12, 0.15, 0.18), (sx * 0.6, -2.33, 0.85), M["black"], bevel=0.02))
        hull.append(C.box(f"Cekme_Kanca_Arka_{sx}", (0.12, 0.15, 0.18), (sx * 0.6, 2.33, 0.85), M["black"], bevel=0.02))
        # Farlar ve koruma kafesi
        hull.append(C.cyl(f"Far_{sx}", 0.09, 0.08, (sx * 0.72, -2.22, 1.32), M["lamp"], verts=20, rot=(math.pi / 2, 0, 0)))
        hull.append(C.cyl(f"Far_Cerceve_{sx}", 0.11, 0.06, (sx * 0.72, -2.2, 1.32), M["black"], verts=20, rot=(math.pi / 2, 0, 0)))
        for k in range(3):
            hull.append(C.box(f"Far_Kafes_{sx}_{k}", (0.24, 0.02, 0.018), (sx * 0.72, -2.29, 1.25 + k * 0.07), M["black"]))
        hull.append(C.box(f"Stop_{sx}", (0.12, 0.03, 0.08), (sx * 0.85, 2.31, 1.3), M["beacon"]))
    # Ön kamera kutuları (sürüş kameraları) ve LIDAR
    for sx in (-1, 0, 1):
        hull.append(C.box(f"Surus_Kamera_{sx}", (0.16, 0.12, 0.1), (sx * 0.42, -1.78, 1.73), M["black"], bevel=0.015))
        hull.append(C.cyl(f"Surus_Mercek_{sx}", 0.035, 0.03, (sx * 0.42, -1.85, 1.73), M["glass"], verts=16, rot=(math.pi / 2, 0, 0)))
    hull.append(C.cyl("Lidar_Govde", 0.11, 0.14, (0.0, -1.45, 1.76), M["black"], verts=28))
    hull.append(C.cyl("Lidar_Pencere", 0.112, 0.06, (0.0, -1.45, 1.79), M["glass"], verts=28))
    # Arka kapak, egzoz panjuru, motor ızgarası
    hull.append(C.box("Arka_Kapak", (1.2, 0.05, 0.6), (0, 2.32, 1.2), M["camo2"], bevel=0.01))
    for k in range(7):
        hull.append(C.box(f"Motor_Izgara_{k}", (0.9, 0.05, 0.018), (0, 1.3 + k * 0.1, 1.68), M["black"]))
    # Tavan: dost tanıma paneli (turuncu, VS-17 benzeri) ve yük rafı
    hull.append(C.box("Dost_Paneli", (1.0, 0.65, 0.012), (0, 0.55, 1.678), M["accent"]))
    for sx in (-1, 1):
        hull.append(C.box(f"Raf_{sx}", (0.04, 1.4, 0.04), (sx * 0.72, 0.6, 1.78), M["black"]))
        for y in (0.0, 1.2):
            hull.append(C.box(f"Raf_Ayak_{sx}_{y}", (0.04, 0.04, 0.12), (sx * 0.72, y, 1.72), M["black"]))
    hull.append(C.box("Yedek_Teker_Yuvasi", (0.9, 0.5, 0.06), (0, 1.75, 1.7), M["camo2"]))
    # Haberleşme antenleri (arka köşelerde, yay tabanlı kamçı)
    for sx in (-1, 1):
        hull.append(C.cyl(f"Anten_Yay_{sx}", 0.04, 0.16, (sx * 0.82, 2.0, 1.78), M["black"], verts=12))
        hull.append(C.tube_between(f"Anten_{sx}", (sx * 0.82, 2.0, 1.85), (sx * 0.86, 2.15, 3.3), 0.008, M["black"], verts=6))
    hull.append(C.box("Mesh_Radyo", (0.2, 0.16, 0.05), (0.55, 1.75, 1.76), M["black"], bevel=0.01))
    C.join(hull, "Govde").parent = root

    # Sensör direği (EO/IR): gövdenin arka-solunda, katlanır direk + gimbal top
    mast = [C.box("Direk_Kaide", (0.3, 0.3, 0.12), (-0.6, 1.05, 1.73), M["camo2"], bevel=0.02),
            C.cyl("Direk", 0.05, 1.25, (-0.6, 1.05, 2.4), M["camo2"], verts=14),
            C.cyl("Direk_Bilezik", 0.065, 0.08, (-0.6, 1.05, 2.1), M["metal"], verts=14),
            C.box("Gimbal_Catal", (0.34, 0.14, 0.22), (-0.6, 1.05, 3.06), M["camo2"], bevel=0.02),
            C.sphere("Gimbal_Top", 0.17, (-0.6, 1.0, 3.22), M["camo"], segs=24, rings=12),
            C.cyl("Gimbal_Mercek", 0.06, 0.05, (-0.6, 0.84, 3.24), M["glass"], verts=18, rot=(math.pi / 2, 0, 0)),
            C.cyl("Gimbal_IR", 0.04, 0.05, (-0.52, 0.85, 3.13), M["glass"], verts=14, rot=(math.pi / 2, 0, 0))]
    C.join(mast, "Sensor_Diregi").parent = root
    C.empty("Kamera", (-0.6, 0.84, 3.24), root)

    # Uzaktan kumandalı silah istasyonu (SARP benzeri): ayrı parça, orijini dönme ekseninde
    KX, KY, KZ = 0.15, 0.1, 1.69
    rws = [C.cyl("Kule_Tabla", 0.36, 0.08, (0, 0, 0.04), M["camo2"], verts=30, bevel=0.01),
           C.box("Kule_Govde", (0.55, 0.62, 0.36), (0, 0.05, 0.26), M["camo"], bevel=0.035),
           C.box("Kule_Kutu", (0.2, 0.36, 0.28), (0.36, 0.1, 0.27), M["camo2"], bevel=0.02),
           C.box("Kule_Nisangah", (0.22, 0.26, 0.2), (-0.32, -0.05, 0.42), M["camo2"], bevel=0.02),
           C.cyl("Kule_Nisangah_Cam", 0.055, 0.03, (-0.32, -0.19, 0.44), M["glass"], verts=16, rot=(math.pi / 2, 0, 0)),
           C.box("Namlu_Kilif", (0.14, 0.5, 0.14), (0.04, -0.38, 0.33), M["camo2"], bevel=0.015),
           C.cyl("Namlu", 0.022, 0.75, (0.04, -0.98, 0.33), M["black"], verts=12, rot=(math.pi / 2, 0, 0)),
           C.cyl("Namlu_Agiz", 0.035, 0.08, (0.04, -1.36, 0.33), M["black"], verts=12, rot=(math.pi / 2, 0, 0))]
    for k in range(4):
        rws.append(C.cyl(f"Sis_Tup_{k}", 0.035, 0.18, (0.33, -0.05 + k * 0.07, 0.48), M["camo2"], verts=10,
                         rot=(math.radians(-30), 0, 0)))
    kule = C.join(rws, "Kule")
    kule.location = (KX + kule.location.x, KY + kule.location.y, KZ + kule.location.z)
    kule.parent = root

    for sx in (-1, 1):
        for y, tag in ((-1.45, "On"), (1.35, "Arka")):
            wheel(M, f"Teker_{tag}_{'L' if sx > 0 else 'R'}", sx * 1.0, y, 0.52, 0.42, root)
    C.stats(root)
    C.export_fbx(os.path.join(OUT, "SuruIHA_IKA.fbx"), root)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SuruIHA_IKA.blend"))


# ======================================================================= Pusu mevzii
def camo_net(M, name, cx, cy, sx, sy, top, poles):
    """Direklerin üstüne serilmiş, kenarları yere sarkan kamuflaj ağı (gürültülü ızgara + yaprak parçaları)."""
    bm = bmesh.new()
    nx, ny = 28, 22
    verts = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx * 2 - 1, j / ny * 2 - 1
            x, y = cx + u * sx / 2, cy + v * sy / 2
            # Direk tepelerinde yüksek, aralarda sarkık, kenarda yere iner
            h = 0.0
            for (px, py, ph) in poles:
                d = math.hypot((x - px) / 1.6, (y - py) / 1.6)
                h = max(h, ph - 0.35 * d * d)
            edge = max(abs(u), abs(v))
            h = max(0.05, min(h, top) * (1.0 - max(0.0, edge - 0.55) / 0.45 * 0.92))
            h += random.uniform(-0.06, 0.06)
            row.append(bm.verts.new((x + random.uniform(-0.05, 0.05), y + random.uniform(-0.05, 0.05), h)))
        verts.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
    net = C.mesh_object(name, bm, M["net"])
    # Ağa iliştirilmiş kumaş yapraklar (siluet kırıcı)
    parts = [net]
    for k in range(200):
        i, j = random.randrange(nx + 1), random.randrange(ny + 1)
        x = cx + (i / nx * 2 - 1) * sx / 2
        y = cy + (j / ny * 2 - 1) * sy / 2
        z = net.data.vertices[j * (nx + 1) + i].co.z + 0.03
        m = M["camo"] if k % 3 else M["tan"] if k % 2 else M["camo2"]
        parts.append(C.box(f"Yaprak_{k}", (random.uniform(0.25, 0.5), random.uniform(0.18, 0.35), 0.015), (x, y, z), m,
                           rot=(random.uniform(-0.25, 0.25), random.uniform(-0.25, 0.25), random.uniform(0, math.pi))))
    return C.join(parts, name)


def build_pusu():
    C.reset_scene()
    M = materials()
    root = C.empty("SuruIHA_Pusu")
    # Silahlı arazi aracı (pikap), önü -Y; kasada tanksavar füze rampası
    car = []
    for sx in (-1, 1):
        car.append(C.box(f"Sasi_{sx}", (0.12, 4.8, 0.18), (sx * 0.5, 0.0, 0.62), M["black"]))
    car.append(C.box("Kaput", (1.75, 1.4, 0.45), (0, -1.65, 1.0), M["tan"], bevel=0.06))
    car.append(C.box("Kabin", (1.75, 1.35, 0.8), (0, -0.35, 1.38), M["tan"], bevel=0.07))
    car.append(C.box("Kabin_Tavan", (1.6, 1.0, 0.05), (0, -0.3, 1.8), M["tan"], bevel=0.02))
    car.append(C.box("On_Cam", (1.5, 0.05, 0.42), (0, -1.0, 1.52), M["glass"], rot=(math.radians(-28), 0, 0)))
    for sx in (-1, 1):
        car.append(C.box(f"Yan_Cam_{sx}", (0.03, 0.9, 0.36), (sx * 0.88, -0.3, 1.52), M["glass"]))
        car.append(C.box(f"Kasa_Yan_{sx}", (0.06, 1.9, 0.5), (sx * 0.86, 1.3, 1.05), M["tan"], bevel=0.015))
        car.append(C.box(f"Camurluk_{sx}", (0.28, 1.0, 0.4), (sx * 0.85, -1.55, 0.9), M["tan"], bevel=0.05))
        car.append(C.cyl(f"Far_{sx}", 0.08, 0.05, (sx * 0.62, -2.36, 1.02), M["lamp"], verts=16, rot=(math.pi / 2, 0, 0)))
    car.append(C.box("Kasa_Taban", (1.7, 1.9, 0.08), (0, 1.3, 0.84), M["tan"]))
    car.append(C.box("Kasa_Arka", (1.7, 0.06, 0.5), (0, 2.25, 1.05), M["tan"], bevel=0.015))
    car.append(C.box("Tampon", (1.85, 0.16, 0.22), (0, -2.4, 0.78), M["black"], bevel=0.02))
    car.append(C.box("Izgara", (1.2, 0.04, 0.3), (0, -2.36, 1.0), M["black"]))
    # Kasadaki rampa ve kalkanlı ağır makineli
    car.append(C.box("Rampa_Kaide", (0.5, 0.5, 0.4), (0, 1.25, 1.08), M["camo2"], bevel=0.02))
    for kx in (-1, 1):
        car.append(C.cyl(f"Fuze_Tup_{kx}", 0.09, 1.3, (kx * 0.12, 1.1, 1.45), M["camo"], verts=16, rot=(math.radians(80), 0, 0)))
    car.append(C.box("Kalkan", (0.7, 0.05, 0.45), (0, 0.6, 1.55), M["camo2"], bevel=0.01))
    for sx in (-1, 1):
        car.append(C.cyl(f"Paspal_{sx}", 0.05, 0.1, (sx * 0.4, -2.45, 0.85), M["black"], verts=10, rot=(math.pi / 2, 0, 0)))
    pick = C.join(car, "Pikap")
    pick.parent = root
    for sx in (-1, 1):
        for y, tag in ((-1.55, "On"), (1.35, "Arka")):
            wheel(M, f"Teker_{tag}_{'L' if sx > 0 else 'R'}", sx * 0.82, y, 0.38, 0.28, root, lugs=20)
    C.empty("Namlu", (0.0, 0.45, 1.95), root)

    # Kum torbası siperi (aracın önünde, yola bakan yarım ay)
    bags = []
    for row in range(3):
        n = 13 - row
        for k in range(n):
            a = math.radians(-70 + 140 * (k + 0.5 * row) / 13)
            r = 3.6
            x, y = math.sin(a) * r, -1.0 - math.cos(a) * r
            bags.append(C.box(f"Torba_{row}_{k}", (0.62, 0.36, 0.2), (x, y, 0.1 + row * 0.19), M["sand"], bevel=0.07,
                              rot=(0, 0, -a + random.uniform(-0.08, 0.08))))
    C.join(bags, "Siper").parent = root
    # Mühimmat sandıkları ve bidonlar
    stuff = [C.box("Sandik_1", (0.9, 0.4, 0.3), (2.0, 1.6, 0.15), M["camo"], bevel=0.02),
             C.box("Sandik_2", (0.9, 0.4, 0.3), (2.05, 1.65, 0.45), M["camo2"], bevel=0.02, rot=(0, 0, 0.12)),
             C.cyl("Bidon_1", 0.22, 0.85, (-2.0, 1.9, 0.43), M["camo2"], verts=20),
             C.cyl("Bidon_2", 0.22, 0.85, (-1.55, 2.1, 0.43), M["tan"], verts=20)]
    C.join(stuff, "Teçhizat").parent = root
    # Kamuflaj ağı: dört direk, ortada araç
    # Ağ aracın arkasını ve kasasını örter, burnu ve siper dışarıda kalır (yoldan bakınca kaput seçilir)
    poles = [(-1.7, -0.7, 2.4), (1.7, -0.7, 2.4), (-1.7, 2.9, 2.2), (1.7, 2.9, 2.2), (0.0, 1.1, 2.65)]
    pp = [C.cyl(f"Ag_Diregi_{k}", 0.03, h, (x, y, h / 2), M["black"], verts=8) for k, (x, y, h) in enumerate(poles)]
    C.join(pp, "Ag_Direkleri").parent = root
    camo_net(M, "Kamuflaj_Agi", 0.0, 1.1, 6.2, 5.4, 2.65, poles).parent = root
    C.stats(root)
    C.export_fbx(os.path.join(OUT, "SuruIHA_Pusu.fbx"), root)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SuruIHA_Pusu.blend"))


# ======================================================================= Mayın
def build_mayin():
    C.reset_scene()
    M = materials()
    root = C.empty("SuruIHA_Mayin")
    mine = [C.cyl("Govde", 0.16, 0.1, (0, 0, 0.03), M["camo"], verts=32, bevel=0.015),
            C.cyl("Ust_Halka", 0.13, 0.03, (0, 0, 0.09), M["camo2"], verts=32),
            C.cyl("Tapa", 0.045, 0.05, (0, 0, 0.11), M["black"], verts=16, bevel=0.008),
            C.box("Tasima_Kulpu", (0.12, 0.02, 0.02), (0.13, 0, 0.07), M["black"])]
    C.join(mine, "Mayin_Govde").parent = root
    # Toprak tümseği (yarı gömülü)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=8, radius=0.32)
    for v in bm.verts:
        v.co.z = max(0.0, v.co.z) * 0.18 - 0.01
        v.co.x *= 1 + random.uniform(-0.06, 0.06)
        v.co.y *= 1 + random.uniform(-0.06, 0.06)
    C.mesh_object("Toprak", bm, M["tan"]).parent = root
    # İkaz bayrağı (bulununca dikilir): kırmızı üçgen bayraklı çubuk
    flag = [C.cyl("Bayrak_Cubuk", 0.012, 1.2, (0.35, 0.0, 0.6), M["black"], verts=8)]
    bm = bmesh.new()                       # iki yüzlü üçgen bez (iki ayrı, 4 mm aralıklı yüz)
    for y, order in ((-0.002, (0, 1, 2)), (0.002, (2, 1, 0))):
        tri = [bm.verts.new((0.36, y, 1.18)), bm.verts.new((0.36, y, 0.88)), bm.verts.new((0.78, y, 1.03))]
        bm.faces.new([tri[k] for k in order])
    flag.append(C.mesh_object("Bayrak_Bez", bm, M["beacon"], smooth=False))
    C.join(flag, "Bayrak").parent = root
    C.stats(root)
    C.export_fbx(os.path.join(OUT, "SuruIHA_Mayin.fbx"), root)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SuruIHA_Mayin.blend"))


build_ika()
build_pusu()
build_mayin()
