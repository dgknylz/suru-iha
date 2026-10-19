"""Yer kontrol istasyonu: operatör konteyneri, anten direği, takip anteni, jeneratör, kum torbaları.

    blender -b -P blender/gcs.py -- <çıktı_klasörü>
Çıktı: SuruIHA_GCS.fbx   ("Mast_Top" boş nesnesi direk tepesidir, ~12 m)
"""
import math
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))
C.reset_scene()

M_CAMO = C.mat("MAT_Camo", (0.135, 0.15, 0.095), rough=0.78)
M_CAMO2 = C.mat("MAT_Camo_Dark", (0.08, 0.09, 0.06), rough=0.8)
M_METAL = C.mat("MAT_Metal", (0.5, 0.51, 0.52), rough=0.38, metal=1.0)
M_BLACK = C.mat("MAT_Black", (0.02, 0.02, 0.022), rough=0.6)
M_GLASS = C.mat("MAT_Glass", (0.01, 0.014, 0.018), rough=0.04, metal=0.3)
M_RADOME = C.mat("MAT_Radome", (0.62, 0.63, 0.6), rough=0.5)
M_SAND = C.mat("MAT_Sandbag", (0.36, 0.31, 0.21), rough=0.95)
M_CONCRETE = C.mat("MAT_Concrete", (0.38, 0.37, 0.34), rough=0.9)
M_LAMP = C.mat("MAT_Lamp", (0.9, 0.85, 0.7), rough=0.1, emission=(1.0, 0.9, 0.7), strength=1.0)
M_BEACON = C.mat("MAT_Beacon_Blue", (0.1, 0.4, 1.0), emission=(0.1, 0.4, 1.0), strength=10.0)

root = C.empty("SuruIHA_GCS")

# Beton zemin platformu
C.box("Platform", (14, 10, 0.2), (0, 0, 0.1), M_CONCRETE, root, bevel=0.03)

# ------------------------------------------------------------------ operatör konteyneri (20 ft)
ct = []
ct.append(C.box("Konteyner", (6.0, 2.45, 2.6), (-2.5, 0.5, 1.5), M_CAMO, bevel=0.04))
for k in range(16):
    x = -5.4 + k * 0.39
    for sy in (-1, 1):
        ct.append(C.box(f"Oluk_{k}_{sy}", (0.18, 0.05, 2.4), (x, 0.5 + sy * 1.235, 1.5), M_CAMO))
for sy in (-1, 1):
    for z in (0.25, 2.75):
        ct.append(C.box(f"Kiris_{sy}_{z}", (6.0, 0.12, 0.12), (-2.5, 0.5 + sy * 1.2, z), M_CAMO2))
ct.append(C.box("Kapi", (0.95, 0.06, 2.0), (-1.2, 0.5 - 1.27, 1.25), M_CAMO2, bevel=0.01))
ct.append(C.box("Kapi_Kolu", (0.06, 0.06, 0.2), (-0.85, 0.5 - 1.32, 1.25), M_METAL))
ct.append(C.box("Klima", (0.9, 0.5, 0.6), (-4.2, 0.5 - 1.45, 2.0), M_CAMO2, bevel=0.03))
for k in range(8):
    ct.append(C.box(f"Klima_Izgara_{k}", (0.8, 0.02, 0.025), (-4.2, 0.5 - 1.71, 1.78 + k * 0.06), M_BLACK))
ct.append(C.box("Merdiven", (1.0, 0.9, 0.5), (-1.2, -1.25, 0.45), M_METAL, bevel=0.02))
ct.append(C.box("Lamba_Yuva", (0.3, 0.15, 0.12), (-1.2, 0.5 - 1.3, 2.45), M_BLACK))
C.join(ct, "OperatorKonteyneri").parent = root
win = []
for x in (-3.4, -4.6):
    win.append(C.box(f"Pencere_{x}", (0.8, 0.05, 0.6), (x, 0.5 - 1.25, 1.8), M_GLASS))
win.append(C.box("Lamba", (0.26, 0.04, 0.08), (-1.2, 0.5 - 1.38, 2.42), M_LAMP))
C.join(win, "Pencereler").parent = root

# Tavan uydu anteni
sat = []
sat.append(C.cyl("Uydu_Ayak", 0.06, 0.6, (-4.0, 1.0, 3.1), M_METAL, verts=12))
dish = C.sphere("Uydu_Canak", 0.55, (-4.0, 1.0, 3.55), M_RADOME, scale=(1, 1, 0.35), segs=40, rings=20)
bm = bmesh.new()
bm.from_mesh(dish.data)
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_outer=True)
bm.to_mesh(dish.data)
bm.free()
dish.rotation_euler = (math.radians(-140), 0, math.radians(30))
sat.append(dish)
C.join(sat, "UyduAnteni").parent = root

# ------------------------------------------------------------------ anten direği (kafes)
MX, MY = 2.0, 0.0
mast = []
mast.append(C.box("Direk_Taban", (1.2, 1.2, 0.3), (MX, MY, 0.35), M_CONCRETE, bevel=0.03))
H = 12.0
s = 0.22
for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
    mast.append(C.tube_between(f"Dikme_{sx}_{sy}", (MX + sx * s, MY + sy * s, 0.5), (MX + sx * s * 0.6, MY + sy * s * 0.6, H), 0.025, M_METAL, verts=8))
z = 0.5
k = 0
while z < H - 0.6:
    f = 1 - 0.4 * z / H
    corners = [(MX + sx * s * f, MY + sy * s * f) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        mast.append(C.tube_between(f"Capraz_{k}_{i}", (a[0], a[1], z), (b[0], b[1], z + 0.6), 0.01, M_METAL, verts=6))
    z += 0.6
    k += 1
mast.append(C.box("Direk_Ust", (0.5, 0.5, 0.1), (MX, MY, H), M_METAL))
for i, (dx, dy, h) in enumerate(((0.2, 0.2, 2.2), (-0.2, 0.2, 1.6), (0.2, -0.2, 1.6), (-0.2, -0.2, 1.2))):
    mast.append(C.cyl(f"Omni_{i}", 0.03, h, (MX + dx, MY + dy, H + h / 2), M_RADOME, verts=12))
for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
    mast.append(C.tube_between(f"Gergi_{sx}_{sy}", (MX, MY, 9.0), (MX + sx * 4.5, MY + sy * 4.0, 0.2), 0.008, M_BLACK, verts=6))
C.join(mast, "AntenDiregi").parent = root
C.sphere("Ikaz_Lambasi", 0.08, (MX + 0.2, MY + 0.2, H + 2.35), M_BEACON, root, segs=12, rings=8)
C.empty("Mast_Top", (MX, MY, H), root)

# ------------------------------------------------------------------ yönlü takip anteni (tripod + çanak)
TX, TY = 4.5, 3.0
tr = []
for k in range(3):
    a = k * math.tau / 3
    tr.append(C.tube_between(f"Tripod_{k}", (TX, TY, 1.6), (TX + math.cos(a) * 0.9, TY + math.sin(a) * 0.9, 0.2), 0.03, M_METAL, verts=8))
tr.append(C.box("PanTilt", (0.35, 0.35, 0.3), (TX, TY, 1.75), M_CAMO2, bevel=0.03))
tdish = C.sphere("Takip_Canak", 0.75, (0, 0, 0), M_RADOME, scale=(1, 1, 0.3), segs=48, rings=24)
bm = bmesh.new()
bm.from_mesh(tdish.data)
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_outer=True)
bm.to_mesh(tdish.data)
bm.free()
tdish.location = (TX, TY, 2.35)
tdish.rotation_euler = (math.radians(-125), 0, math.radians(-35))
tr.append(tdish)
tr.append(C.tube_between("Besleyici", (TX, TY, 2.35), (TX + 0.25, TY - 0.4, 2.9), 0.02, M_METAL, verts=8))
C.join(tr, "TakipAnteni").parent = root

# ------------------------------------------------------------------ jeneratör + kum torbaları
gen = []
gen.append(C.box("Jenerator", (2.0, 1.1, 1.2), (3.8, -3.0, 0.8), M_CAMO, bevel=0.05))
for k in range(9):
    gen.append(C.box(f"Jen_Panjur_{k}", (0.02, 0.9, 0.04), (4.81, -3.0, 0.55 + k * 0.07), M_BLACK))
gen.append(C.cyl("Jen_Egzoz", 0.05, 0.6, (3.2, -2.7, 1.65), M_BLACK, verts=12))
gen.append(C.box("Jen_Kablo", (3.0, 0.08, 0.06), (1.5, -2.3, 0.23), M_BLACK))
C.join(gen, "Jenerator").parent = root

bags = []
n = 0
for row in range(3):
    for k in range(9 - row):
        x = 2.4 + k * 0.62 + row * 0.31
        bags.append(C.sphere(f"Torba_{n}", 0.5, (x, -4.0, 0.33 + row * 0.24), M_SAND, scale=(0.62, 0.36, 0.26), segs=16, rings=8))
        n += 1
C.join(bags, "KumTorbalari").parent = root

C.stats(root)
os.makedirs(OUT, exist_ok=True)
C.export_fbx(os.path.join(OUT, "SuruIHA_GCS.fbx"), root)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SuruIHA_GCS.blend"))
