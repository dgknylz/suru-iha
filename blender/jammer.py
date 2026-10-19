"""Elektronik harp (karıştırıcı) aracı: 6x6 askeri kamyon + ekipman kabini + teleskopik anten direği.

    blender -b -P blender/jammer.py -- <çıktı_klasörü>
Çıktı: SuruIHA_Jammer.fbx
"Beacon" boş nesnesi direğin tepesindeki ikaz ışığının yeridir (Unity bunu kullanır).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))
C.reset_scene()

M_CAMO = C.mat("MAT_Camo", (0.135, 0.15, 0.095), rough=0.78)
M_CAMO2 = C.mat("MAT_Camo_Dark", (0.08, 0.09, 0.06), rough=0.8)
M_TIRE = C.mat("MAT_Tire", (0.018, 0.018, 0.018), rough=0.95)
M_RIM = C.mat("MAT_Rim", (0.11, 0.12, 0.085), rough=0.6, metal=0.4)
M_GLASS = C.mat("MAT_Glass", (0.01, 0.014, 0.018), rough=0.04, metal=0.3)
M_METAL = C.mat("MAT_Metal", (0.5, 0.51, 0.52), rough=0.38, metal=1.0)
M_BLACK = C.mat("MAT_Black", (0.02, 0.02, 0.022), rough=0.6)
M_RADOME = C.mat("MAT_Radome", (0.62, 0.63, 0.6), rough=0.5)
M_LAMP = C.mat("MAT_Lamp", (0.9, 0.85, 0.7), rough=0.1, emission=(1.0, 0.9, 0.7), strength=1.0)
M_BEACON = C.mat("MAT_Beacon", (1.0, 0.08, 0.04), emission=(1.0, 0.08, 0.04), strength=12.0)
M_STRIPE = C.mat("MAT_Stripe", (0.75, 0.6, 0.12), rough=0.6)

root = C.empty("SuruIHA_Jammer")
# Kamyonun önü -Y yönünde. Uzunluk ~8 m, genişlik 2.5 m.

# ------------------------------------------------------------------ şasi ve tekerlekler
chassis = []
for sx in (-1, 1):
    chassis.append(C.box(f"Sasi_{sx}", (0.18, 7.4, 0.3), (sx * 0.5, 0.0, 1.0), M_CAMO2, bevel=0.02))
for y in (-3.0, -1.0, 0.6, 2.2, 3.4):
    chassis.append(C.box(f"Travers_{y}", (1.2, 0.12, 0.2), (0, y, 1.0), M_CAMO2))
chassis.append(C.box("Tampon", (2.5, 0.25, 0.32), (0, -3.85, 0.95), M_CAMO2, bevel=0.03))
chassis.append(C.box("Ceki_Kancasi", (0.25, 0.2, 0.2), (0, -4.02, 0.9), M_BLACK, bevel=0.02))
for sx in (-1, 1):
    chassis.append(C.box(f"Basamak_{sx}", (0.35, 0.6, 0.06), (sx * 1.25, -2.6, 0.75), M_BLACK))
    chassis.append(C.box(f"YakitDeposu_{sx}", (0.5, 1.1, 0.55), (sx * 0.95, -1.0, 1.05), M_CAMO, bevel=0.06))
    chassis.append(C.box(f"AletKutusu_{sx}", (0.45, 0.8, 0.5), (sx * 0.95, 1.85, 1.1), M_CAMO, bevel=0.03))
C.join(chassis, "Sasi").parent = root


def wheel(name, x, y):
    parts = []
    r, w = 0.58, 0.44
    tire = C.cyl(name + "_Lastik", r, w, (0, 0, 0), M_TIRE, verts=48, rot=(0, math.pi / 2, 0), bevel=0.09, segments=4)
    parts.append(tire)
    for k in range(28):   # lastik dişleri
        a = k * math.tau / 28
        lug = C.box(f"{name}_Dis{k}", (w * 0.42, 0.07, 0.045), (math.copysign(w * 0.22, (-1) ** k), math.cos(a) * (r + 0.005), math.sin(a) * (r + 0.005)),
                    M_TIRE, rot=(a, 0, 0))
        parts.append(lug)
    side = 1 if x > 0 else -1
    parts.append(C.cyl(name + "_Jant", 0.34, w + 0.02, (side * 0.02, 0, 0), M_RIM, verts=40, rot=(0, math.pi / 2, 0), bevel=0.02))
    parts.append(C.cyl(name + "_Gobek", 0.14, 0.12, (side * (w / 2 + 0.04), 0, 0), M_RIM, verts=24, rot=(0, math.pi / 2, 0), bevel=0.02))
    for k in range(8):
        a = k * math.tau / 8
        parts.append(C.cyl(f"{name}_Bijon{k}", 0.022, 0.05, (side * (w / 2 + 0.03), math.cos(a) * 0.22, math.sin(a) * 0.22), M_METAL,
                           verts=8, rot=(0, math.pi / 2, 0)))
    o = C.join(parts, name)
    o.location = (x, y, r)
    o.parent = root
    return o


for i, y in enumerate((-2.7, 1.0, 2.45)):
    for sx in (-1, 1):
        wheel(f"Teker_{i}_{'L' if sx > 0 else 'R'}", sx * 1.02, y)
        C.box(f"Camurluk_{i}_{sx}", (0.55, 1.45, 0.06), (sx * 1.02, y, 1.27), M_CAMO2, root, bevel=0.02)

# ------------------------------------------------------------------ kabin
cab = []
cab.append(C.box("Kabin_Alt", (2.45, 1.9, 1.1), (0, -2.95, 1.7), M_CAMO, bevel=0.06))
cab.append(C.box("Kabin_Ust", (2.35, 1.6, 1.0), (0, -2.85, 2.75), M_CAMO, bevel=0.08))
cab.append(C.box("Motor_Kaputu", (1.9, 0.5, 0.55), (0, -3.85, 1.55), M_CAMO, bevel=0.05))
for k in range(7):
    cab.append(C.box(f"Izgara_{k}", (1.5, 0.04, 0.035), (0, -4.11, 1.35 + k * 0.07), M_BLACK))
for sx in (-1, 1):
    cab.append(C.cyl(f"Far_{sx}", 0.12, 0.08, (sx * 0.95, -3.92, 1.55), M_BLACK, verts=24, rot=(math.pi / 2, 0, 0), bevel=0.01))
    cab.append(C.cyl(f"Ayna_Kol_{sx}", 0.015, 0.45, (sx * 1.38, -3.4, 2.7), M_BLACK, verts=8, rot=(0, math.pi / 2, 0)))
    cab.append(C.box(f"Ayna_{sx}", (0.06, 0.2, 0.35), (sx * 1.6, -3.4, 2.65), M_BLACK, bevel=0.02))
    cab.append(C.box(f"Kapi_Kolu_{sx}", (0.04, 0.18, 0.04), (sx * 1.23, -2.6, 2.3), M_METAL))
    cab.append(C.box(f"Kapi_Cizgi_{sx}", (0.01, 0.02, 1.7), (sx * 1.225, -2.15, 2.25), M_BLACK))
cab.append(C.box("Tavan_Gozetleme", (0.7, 0.7, 0.15), (0, -2.7, 3.3), M_CAMO2, bevel=0.04))
C.join(cab, "Kabin").parent = root

glass = []
glass.append(C.box("OnCam", (2.05, 0.04, 0.72), (0, -3.66, 2.8), M_GLASS, rot=(math.radians(-8), 0, 0)))
for sx in (-1, 1):
    glass.append(C.box(f"YanCam_{sx}", (0.04, 0.95, 0.6), (sx * 1.18, -2.95, 2.85), M_GLASS))
    glass.append(C.cyl(f"FarCam_{sx}", 0.1, 0.02, (sx * 0.95, -3.965, 1.55), M_LAMP, verts=24, rot=(math.pi / 2, 0, 0)))
C.join(glass, "Camlar").parent = root

# ------------------------------------------------------------------ ekipman kabini (shelter)
sh = []
SY0, SY1 = -1.8, 3.6
sh_len, sh_mid = SY1 - SY0, (SY0 + SY1) / 2
sh.append(C.box("Kabin_Govde", (2.5, sh_len, 2.35), (0, sh_mid, 2.5), M_CAMO, bevel=0.05))
for k in range(9):   # kenar takviyeleri
    y = SY0 + 0.2 + k * (sh_len - 0.4) / 8
    for sx in (-1, 1):
        sh.append(C.box(f"Nervur_{k}_{sx}", (0.05, 0.08, 2.25), (sx * 1.265, y, 2.5), M_CAMO))
for sx in (-1, 1):
    for z in (1.36, 3.64):
        sh.append(C.box(f"Kosebent_{sx}_{z}", (0.1, sh_len, 0.1), (sx * 1.24, sh_mid, z), M_CAMO2, bevel=0.01))
sh.append(C.box("Arka_Kapi", (1.0, 0.05, 1.95), (0.3, SY1 + 0.02, 2.4), M_CAMO2, bevel=0.01))
sh.append(C.box("Kapi_Kolu", (0.05, 0.08, 0.25), (0.7, SY1 + 0.07, 2.4), M_METAL))
for k in range(8):   # arka merdiven
    sh.append(C.box(f"Merdiven_{k}", (0.42, 0.04, 0.035), (-0.75, SY1 + 0.12, 1.4 + k * 0.28), M_METAL))
for sx in (-1, 1):
    sh.append(C.box(f"Merdiven_Ray_{sx}", (0.04, 0.04, 2.3), (-0.75 + sx * 0.21, SY1 + 0.12, 2.45), M_METAL))
sh.append(C.box("Klima", (0.12, 1.0, 0.75), (-1.32, 0.6, 2.7), M_CAMO2, bevel=0.03))
for k in range(10):
    sh.append(C.box(f"Klima_Panjur_{k}", (0.02, 0.9, 0.025), (-1.39, 0.6, 2.4 + k * 0.065), M_BLACK))
sh.append(C.box("Uyari_Seridi", (0.02, 1.2, 0.12), (1.27, 1.2, 1.55), M_STRIPE))
C.join(sh, "EkipmanKabini").parent = root

# Tavan ekipmanı: korna antenler + jeneratör egzozu + kablo kanalı
roof = []
for sx in (-1, 1):
    horn = C.cone(f"Korna_{sx}", 0.32, 0.08, 0.6, (sx * 0.65, -1.2, 4.0), M_RADOME, verts=4,
                  rot=(math.radians(-70), 0, math.radians(45)))
    roof.append(horn)
    roof.append(C.box(f"Korna_Ayak_{sx}", (0.15, 0.15, 0.35), (sx * 0.65, -1.05, 3.8), M_METAL))
roof.append(C.box("Kablo_Kanali", (0.15, 3.0, 0.08), (0.8, 1.2, 3.72), M_CAMO2))
roof.append(C.cyl("Egzoz", 0.05, 0.7, (1.0, -1.6, 4.0), M_BLACK, verts=12))
roof.append(C.box("Tavan_Korkuluk", (2.2, 0.04, 0.04), (0, 3.4, 3.95), M_METAL))
C.join(roof, "TavanEkipmani").parent = root

# ------------------------------------------------------------------ teleskopik direk + anten başlığı
MX, MY = 0.0, 2.3
mast = []
mast.append(C.cyl("Direk_Taban", 0.32, 0.25, (MX, MY, 3.8), M_METAL, verts=32, bevel=0.02))
z = 3.9
for i, (r, h) in enumerate(((0.15, 3.0), (0.12, 2.6), (0.09, 2.2))):
    mast.append(C.cyl(f"Direk_{i}", r, h, (MX, MY, z + h / 2), M_CAMO2, verts=24))
    mast.append(C.cyl(f"Direk_Bilezik_{i}", r + 0.035, 0.12, (MX, MY, z + h), M_METAL, verts=24))
    z += h
top_z = z  # ~11.6
mast.append(C.box("Rotator", (0.4, 0.4, 0.3), (MX, MY, top_z + 0.15), M_CAMO2, bevel=0.03))
# Dört yöne panel antenler
for k in range(4):
    a = k * math.pi / 2
    mast.append(C.box(f"Panel_{k}", (0.45, 0.07, 1.0), (MX + math.sin(a) * 0.32, MY + math.cos(a) * 0.32, top_z + 0.85),
                      M_RADOME, bevel=0.02, rot=(0, 0, -a)))
# Log-periyodik dipol dizisi (LPDA)
mast.append(C.tube_between("LPDA_Bom", (MX - 0.9, MY, top_z + 1.55), (MX + 0.9, MY, top_z + 1.55), 0.03, M_METAL, verts=12))
for k in range(9):
    L = 1.1 * (0.86 ** k)
    x = MX - 0.8 + k * 0.2
    mast.append(C.tube_between(f"LPDA_Eleman_{k}", (x, MY - L / 2, top_z + 1.55), (x, MY + L / 2, top_z + 1.55), 0.012, M_METAL, verts=8))
mast.append(C.cyl("LPDA_Tasiyici", 0.04, 0.25, (MX, MY, top_z + 1.42), M_METAL, verts=12))
mast.append(C.cyl("Omni_Anten", 0.025, 1.0, (MX, MY, top_z + 2.1), M_RADOME, verts=12))
# Gergi halatları
for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
    mast.append(C.tube_between(f"Gergi_{sx}_{sy}", (MX, MY, 9.0), (sx * 1.15, MY + sy * 1.2, 3.7), 0.008, M_BLACK, verts=6))
C.join(mast, "AntenDiregi").parent = root

beacon = C.sphere("Beacon_Lamba", 0.09, (MX, MY, top_z + 2.68), M_BEACON, root, segs=16, rings=8)
C.empty("Beacon", (MX, MY, top_z + 2.68), root)

C.stats(root)
os.makedirs(OUT, exist_ok=True)
C.export_fbx(os.path.join(OUT, "SuruIHA_Jammer.fbx"), root)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SuruIHA_Jammer.blend"))
