"""Hava savunma sistemi: römork üstünde dönen arama radarı + yanında dört tüplü füze rampası.

    blender -b -P blender/radar.py -- <çıktı_klasörü>
Çıktı: SuruIHA_Radar.fbx
"Anten" nesnesinin orijini dönme ekseni (Unity onu döndürür; anten yüzü -Y = Unity'de +Z);
"Beacon" ikaz ışığının, "FuzeCikis" füzenin çıktığı yerdir.
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))
C.reset_scene()

# Karıştırıcı aracıyla aynı malzeme adları (Unity aynı HDRP malzemelerine eşler)
M_CAMO = C.mat("MAT_Camo", (0.135, 0.15, 0.095), rough=0.78)
M_CAMO2 = C.mat("MAT_Camo_Dark", (0.08, 0.09, 0.06), rough=0.8)
M_TIRE = C.mat("MAT_Tire", (0.018, 0.018, 0.018), rough=0.95)
M_RIM = C.mat("MAT_Rim", (0.11, 0.12, 0.085), rough=0.6, metal=0.4)
M_METAL = C.mat("MAT_Metal", (0.5, 0.51, 0.52), rough=0.38, metal=1.0)
M_BLACK = C.mat("MAT_Black", (0.02, 0.02, 0.022), rough=0.6)
M_RADOME = C.mat("MAT_Radome", (0.62, 0.63, 0.6), rough=0.5)
M_BEACON = C.mat("MAT_Beacon", (1.0, 0.08, 0.04), emission=(1.0, 0.08, 0.04), strength=12.0)
M_STRIPE = C.mat("MAT_Stripe", (0.75, 0.6, 0.12), rough=0.6)
M_GLASS = C.mat("MAT_Glass", (0.01, 0.014, 0.018), rough=0.04, metal=0.3)

root = C.empty("SuruIHA_Radar")


def wheel(name, x, y, parent):
    parts = []
    r, w = 0.46, 0.32
    parts.append(C.cyl(name + "_Lastik", r, w, (0, 0, 0), M_TIRE, verts=40, rot=(0, math.pi / 2, 0), bevel=0.07, segments=3))
    for k in range(22):
        a = k * math.tau / 22
        parts.append(C.box(f"{name}_Dis{k}", (w * 0.8, 0.06, 0.035), (0, math.cos(a) * (r + 0.004), math.sin(a) * (r + 0.004)),
                           M_TIRE, rot=(a, 0, 0)))
    side = 1 if x > 0 else -1
    parts.append(C.cyl(name + "_Jant", 0.27, w + 0.02, (side * 0.02, 0, 0), M_RIM, verts=32, rot=(0, math.pi / 2, 0), bevel=0.02))
    for k in range(6):
        a = k * math.tau / 6
        parts.append(C.cyl(f"{name}_Bijon{k}", 0.018, 0.04, (side * (w / 2 + 0.03), math.cos(a) * 0.16, math.sin(a) * 0.16), M_METAL,
                           verts=8, rot=(0, math.pi / 2, 0)))
    o = C.join(parts, name)
    o.location = (x, y, r)
    o.parent = parent
    return o


# ------------------------------------------------------------------ radar römorku (önü -Y)
trailer = C.empty("RadarRomorku", (0, 0, 0), root)
ch = []
for sx in (-1, 1):
    ch.append(C.box(f"Kiris_{sx}", (0.16, 5.6, 0.26), (sx * 0.62, 0.4, 0.95), M_CAMO2, bevel=0.015))
for y in (-2.0, -0.8, 0.4, 1.6, 2.9):
    ch.append(C.box(f"Travers_{y}", (1.4, 0.12, 0.18), (0, y, 0.95), M_CAMO2))
# Çeki oku ve halkası
for sx in (-1, 1):
    ch.append(C.tube_between(f"CekiOku_{sx}", (sx * 0.6, -2.4, 0.95), (0, -4.0, 0.8), 0.06, M_CAMO2, verts=10))
ch.append(C.cyl("CekiHalkasi", 0.12, 0.05, (0, -4.1, 0.8), M_METAL, verts=20))
ch.append(C.cyl("Kriko", 0.05, 0.75, (0, -3.6, 0.45), M_METAL, verts=12))
ch.append(C.cyl("Kriko_Teker", 0.09, 0.06, (0, -3.6, 0.09), M_TIRE, verts=16, rot=(0, math.pi / 2, 0)))
# Platform (tabla) ve korkuluk
ch.append(C.box("Tabla", (2.3, 5.4, 0.12), (0, 0.4, 1.14), M_CAMO, bevel=0.02))
for sx in (-1, 1):
    ch.append(C.box(f"Tabla_Kenar_{sx}", (0.06, 5.4, 0.16), (sx * 1.15, 0.4, 1.12), M_CAMO2))
# Dengeleme ayakları (açık): köşelerde çapraz kol + yer tabanı
for sx in (-1, 1):
    for sy in (-1, 1):
        y = 0.4 + sy * 2.4
        foot = (sx * 2.25, y + sy * 0.5, 0.06)
        ch.append(C.tube_between(f"Ayak_Kol_{sx}_{sy}", (sx * 0.7, y, 0.95), (foot[0], foot[1], 0.95), 0.07, M_CAMO2, verts=10))
        ch.append(C.cyl(f"Ayak_Silindir_{sx}_{sy}", 0.075, 0.95, (foot[0], foot[1], 0.55), M_METAL, verts=14))
        ch.append(C.cyl(f"Ayak_Taban_{sx}_{sy}", 0.28, 0.08, foot, M_BLACK, verts=20, bevel=0.01))
# Çamurluklar
for sx in (-1, 1):
    ch.append(C.box(f"Camurluk_{sx}", (0.42, 1.95, 0.05), (sx * 1.03, 1.4, 1.02), M_CAMO2, bevel=0.015))
C.join(ch, "Sasi").parent = trailer
for i, y in enumerate((0.9, 1.9)):
    for sx in (-1, 1):
        wheel(f"Teker_{i}_{'L' if sx > 0 else 'R'}", sx * 1.03, y, trailer)

# Jeneratör ve ekipman kabini
eq = []
eq.append(C.box("Jenerator", (1.9, 1.3, 1.0), (0, -1.6, 1.7), M_CAMO, bevel=0.05))
for k in range(9):
    eq.append(C.box(f"Jenerator_Panjur_{k}", (0.025, 0.95, 0.03), (-0.96, -1.6, 1.4 + k * 0.07), M_BLACK))
eq.append(C.cyl("Egzoz", 0.05, 0.6, (0.7, -1.95, 2.45), M_BLACK, verts=12))
eq.append(C.box("Kabin", (2.1, 1.6, 1.45), (0, -0.1, 1.93), M_CAMO, bevel=0.05))
for sx in (-1, 1):
    eq.append(C.box(f"Kabin_Kapak_{sx}", (0.03, 1.1, 1.0), (sx * 1.06, -0.1, 1.95), M_CAMO2, bevel=0.01))
    eq.append(C.box(f"Kabin_Kol_{sx}", (0.04, 0.05, 0.22), (sx * 1.09, 0.35, 1.95), M_METAL))
eq.append(C.box("Uyari_Seridi", (2.12, 0.02, 0.1), (0, -0.91, 1.3), M_STRIPE))
eq.append(C.box("Kablo_Makarasi_Govde", (0.6, 0.5, 0.5), (0.6, 2.95, 1.45), M_CAMO2, bevel=0.03))
eq.append(C.cyl("Kablo_Makarasi", 0.28, 0.4, (0.6, 2.95, 1.75), M_BLACK, verts=24, rot=(0, math.pi / 2, 0)))
C.join(eq, "Ekipman").parent = trailer

# Kaide (dönen başlığın altı)
PX, PY, PZ = 0.0, 1.55, 2.25      # dönme ekseninin tepesi
ped = []
ped.append(C.cyl("Kaide", 0.55, 1.0, (PX, PY, 1.7), M_CAMO2, verts=32, bevel=0.03))
ped.append(C.cyl("Kaide_Flans", 0.68, 0.1, (PX, PY, 2.18), M_METAL, verts=40, bevel=0.01))
for k in range(12):
    a = k * math.tau / 12
    ped.append(C.cyl(f"Kaide_Civata_{k}", 0.025, 0.04, (PX + math.cos(a) * 0.6, PY + math.sin(a) * 0.6, 2.24), M_METAL, verts=8))
C.join(ped, "Kaide").parent = trailer

# ------------------------------------------------------------------ dönen anten başlığı (yerel koordinat: eksen üstü)
ap = []
ap.append(C.cyl("Doner_Tabla", 0.62, 0.14, (0, 0, 0.07), M_CAMO, verts=40, bevel=0.02))
ap.append(C.box("Doner_Govde", (0.9, 0.8, 0.55), (0, 0.05, 0.42), M_CAMO, bevel=0.04))
for sx in (-1, 1):
    ap.append(C.box(f"Catal_{sx}", (0.12, 0.35, 1.1), (sx * 0.55, 0.1, 0.95), M_CAMO2, bevel=0.02))
# Düzlemsel dizi anten: 3,8 x 1,9 m, geriye 14 derece yatık, yüzü -Y
TILT = math.radians(14)
AY, AZ = -0.25, 1.75
ap.append(C.box("Dizi_Panel", (3.8, 0.24, 1.9), (0, AY, AZ), M_RADOME, bevel=0.04, rot=(-TILT, 0, 0)))
# Panelin önünde ızgara (dizinin eleman satırları) ve çerçeve
for k in range(13):
    z = -0.84 + k * 0.14
    y, zz = AY - 0.125 - z * math.sin(TILT), AZ + z * math.cos(TILT)
    ap.append(C.box(f"Dizi_Satir_{k}", (3.66, 0.012, 0.02), (0, y, zz), M_CAMO2, rot=(-TILT, 0, 0)))
for sx in (-1, 1):
    ap.append(C.box(f"Dizi_Cerceve_{sx}", (0.08, 0.3, 1.96), (sx * 1.92, AY, AZ), M_CAMO2, rot=(-TILT, 0, 0)))
# Arka kafes
for sx in (-1, 0, 1):
    ap.append(C.tube_between(f"Kafes_{sx}", (sx * 1.3, AY + 0.2, AZ + 0.6), (sx * 0.35, 0.25, 0.75), 0.035, M_METAL, verts=8))
    ap.append(C.tube_between(f"Kafes2_{sx}", (sx * 1.3, AY + 0.0, AZ - 0.7), (sx * 0.35, 0.25, 0.75), 0.035, M_METAL, verts=8))
# IFF (dost/düşman tanıma) dizisi: panelin üstünde ince uzun çubuk
iz = AZ + 1.08
ap.append(C.box("IFF_Dizi", (3.9, 0.12, 0.2), (0, AY + 0.25 * math.sin(TILT), iz), M_CAMO2, bevel=0.015, rot=(-TILT, 0, 0)))
for k in range(16):
    ap.append(C.box(f"IFF_Eleman_{k}", (0.05, 0.05, 0.14), (-1.85 + k * 0.247, AY - 0.06, iz), M_METAL))
for sx in (-1, 1):
    ap.append(C.tube_between(f"IFF_Ayak_{sx}", (sx * 1.6, AY + 0.1, AZ + 0.9), (sx * 1.6, AY + 0.15, iz - 0.05), 0.03, M_METAL, verts=8))
# Yan kulaklar (yan lob bastırma antenleri)
for sx in (-1, 1):
    ap.append(C.cone(f"Kulak_{sx}", 0.16, 0.05, 0.35, (sx * 2.05, AY - 0.05, AZ), M_RADOME, verts=4,
                     rot=(math.radians(90 - 14), 0, math.radians(45))))
# Tek parça, orijini dönme ekseninde, doğrudan kökün altında: FBX'te boş nesnenin altındaki parçaya eksen
# çevirimi yanlış uygulanıyor (anten yere yatıyordu)
anten = C.join(ap, "Anten")
anten.location = (PX + anten.location.x, PY + anten.location.y, PZ + anten.location.z)
anten.parent = root
C.sphere("Beacon_Lamba", 0.08, (PX, PY - 0.6, PZ + 0.75), M_BEACON, root, segs=16, rings=8)
C.empty("Beacon", (PX, PY - 0.6, PZ + 0.75), root)

# ------------------------------------------------------------------ füze rampası (radarın yanında, 4 tüp)
LX, LY = 7.0, 1.5
launch = C.empty("Rampa", (0, 0, 0), root)
lp = []
lp.append(C.box("Rampa_Kizak", (2.3, 3.4, 0.25), (LX, LY, 0.15), M_CAMO2, bevel=0.03))
lp.append(C.box("Rampa_Govde", (2.0, 2.6, 0.9), (LX, LY, 0.72), M_CAMO, bevel=0.05))
lp.append(C.cyl("Rampa_Tabla", 0.85, 0.2, (LX, LY, 1.27), M_CAMO2, verts=32, bevel=0.02))
lp.append(C.box("Rampa_Kule", (1.1, 1.0, 0.7), (LX, LY + 0.1, 1.7), M_CAMO, bevel=0.04))
ELEV = math.radians(38)
cz, cy = 2.25, LY - 0.1
for kx in (-1, 1):
    for kz in (0, 1):
        x = LX + kx * 0.36
        y0 = cy - math.cos(ELEV) * 0.0
        z0 = cz + kz * 0.42
        a = (x, y0 + math.cos(ELEV) * 1.6, z0 - math.sin(ELEV) * 1.6)
        b = (x, y0 - math.cos(ELEV) * 1.6, z0 + math.sin(ELEV) * 1.6)
        lp.append(C.tube_between(f"Tup_{kx}_{kz}", a, b, 0.17, M_CAMO, verts=20))
        lp.append(C.tube_between(f"Tup_Agiz_{kx}_{kz}", b, (b[0], b[1] - math.cos(ELEV) * 0.05, b[2] + math.sin(ELEV) * 0.05), 0.15,
                                 M_BLACK, verts=20))
        lp.append(C.tube_between(f"Tup_Bilezik_{kx}_{kz}", (x, y0 + math.cos(ELEV) * 0.4, z0 - math.sin(ELEV) * 0.4),
                                 (x, y0 + math.cos(ELEV) * 0.3, z0 - math.sin(ELEV) * 0.3), 0.185, M_CAMO2, verts=20))
lp.append(C.box("Tup_Kafes", (1.1, 0.12, 1.0), (LX, cy + 0.2, cz + 0.2), M_CAMO2, rot=(-ELEV, 0, 0)))
lp.append(C.box("Rampa_Uyari", (2.02, 0.02, 0.1), (LX, LY - 1.31, 0.5), M_STRIPE))
C.join(lp, "RampaGovde").parent = launch
C.empty("FuzeCikis", (LX - 0.36, cy - math.cos(ELEV) * 1.7, cz + 0.42 + math.sin(ELEV) * 1.7), root)

# Kablolar: rampa ile radar arası yerde
cab = [C.tube_between("Kablo_1", (1.2, 2.9, 0.05), (LX - 1.1, LY + 0.2, 0.05), 0.025, M_BLACK, verts=6),
       C.tube_between("Kablo_2", (1.2, -0.4, 0.05), (LX - 1.1, LY - 0.6, 0.05), 0.025, M_BLACK, verts=6)]
C.join(cab, "Kablolar").parent = root

C.stats(root)
os.makedirs(OUT, exist_ok=True)
C.export_fbx(os.path.join(OUT, "SuruIHA_Radar.fbx"), root)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SuruIHA_Radar.blend"))
