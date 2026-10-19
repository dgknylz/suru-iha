"""Orta Anadolu köyü: kiremit çatılı sıvalı evler (4 çeşit), minareli cami, elektrik direği.

    blender -b -P blender/village.py -- <çıktı_klasörü>
Çıktı: SuruIHA_House_0..3.fbx, SuruIHA_Mosque.fbx, SuruIHA_Pole.fbx
Modellerin tabanında toprağa gömülen bir temel var; Unity eğimli zeminde de boşluk bırakmadan oturtur.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)

PLASTERS = [("MAT_Plaster_A", (0.72, 0.66, 0.55)), ("MAT_Plaster_B", (0.78, 0.76, 0.72)),
            ("MAT_Plaster_C", (0.70, 0.55, 0.40)), ("MAT_Plaster_D", (0.62, 0.64, 0.60))]


def mats():
    return dict(
        roof=C.mat("MAT_RoofTile", (0.42, 0.15, 0.07), rough=0.75),
        window=C.mat("MAT_Glass", (0.01, 0.014, 0.018), rough=0.04, metal=0.3),
        frame=C.mat("MAT_Frame", (0.8, 0.8, 0.78), rough=0.5),
        door=C.mat("MAT_Door", (0.22, 0.12, 0.06), rough=0.7),
        stone=C.mat("MAT_Stone", (0.42, 0.39, 0.34), rough=0.9),
        lead=C.mat("MAT_Lead", (0.33, 0.35, 0.37), rough=0.45, metal=0.6),
        wood=C.mat("MAT_Wood", (0.25, 0.17, 0.1), rough=0.85),
        black=C.mat("MAT_Black", (0.02, 0.02, 0.022), rough=0.6),
        metal=C.mat("MAT_Metal", (0.5, 0.51, 0.52), rough=0.38, metal=1.0),
    )


def hip_roof(name, w, d, z, h, overhang, mat, parent):
    """Kırma çatı: dört eğimli yüzey, mahya hattı uzun kenar boyunca."""
    bm = bmesh.new()
    W, D = w / 2 + overhang, d / 2 + overhang
    ridge = max(0.0, D - W) if d > w else max(0.0, W - D)
    if d >= w:
        r0, r1 = Vector((0, -ridge, z + h)), Vector((0, ridge, z + h))
    else:
        r0, r1 = Vector((-ridge, 0, z + h)), Vector((ridge, 0, z + h))
    c = [Vector((-W, -D, z)), Vector((W, -D, z)), Vector((W, D, z)), Vector((-W, D, z))]
    v = [bm.verts.new(p) for p in c]
    a, b = bm.verts.new(r0), bm.verts.new(r1)
    if d >= w:
        bm.faces.new((v[0], v[1], a))
        bm.faces.new((v[1], v[2], b, a))
        bm.faces.new((v[2], v[3], b))
        bm.faces.new((v[3], v[0], a, b))
    else:
        bm.faces.new((v[0], v[1], b, a))
        bm.faces.new((v[1], v[2], b))
        bm.faces.new((v[2], v[3], a, b))
        bm.faces.new((v[3], v[0], a))
    bm.faces.new(list(reversed(v)))     # saçak altı
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # Kiremit sıraları: çatı yüzeyini ince kabartma bantlarla zenginleştir
    o = C.mesh_object(name, bm, mat, parent, smooth=False)
    return o


def house(idx, w, d, floors, plaster, rnd):
    C.reset_scene()
    C._materials.clear()
    M = mats()
    pm = C.mat(*plaster, rough=0.85) if False else C.mat(plaster[0], plaster[1], rough=0.88)
    root = C.empty(f"SuruIHA_House_{idx}")
    H = 2.9 * floors
    parts = []
    parts.append(C.box("Temel", (w + 0.3, d + 0.3, 2.0), (0, 0, -0.6), M["stone"]))
    parts.append(C.box("Duvar", (w, d, H), (0, 0, H / 2 + 0.4), pm, bevel=0.03, segments=1))
    parts.append(C.box("Kat_Silmesi", (w + 0.08, d + 0.08, 0.12), (0, 0, 0.4 + 2.9), M["frame"])) if floors > 1 else None
    # Pencereler: uzun cephelerde düzenli aralıkla
    for fl in range(floors):
        zc = 0.4 + fl * 2.9 + 1.6
        for side in (-1, 1):
            n = max(2, int(w // 2.6))
            for k in range(n):
                x = -w / 2 + (k + 0.5) * w / n
                if fl == 0 and side == -1 and k == n // 2:
                    continue     # kapının yeri
                parts.append(C.box(f"Pencere_{fl}_{side}_{k}", (0.9, 0.08, 1.15), (x, side * (d / 2 + 0.01), zc), M["window"]))
                parts.append(C.box(f"Cerceve_{fl}_{side}_{k}", (1.05, 0.06, 1.3), (x, side * (d / 2 + 0.005), zc), M["frame"]))
                parts.append(C.box(f"Denizlik_{fl}_{side}_{k}", (1.15, 0.18, 0.06), (x, side * (d / 2 + 0.06), zc - 0.66), M["frame"]))
        for side in (-1, 1):
            parts.append(C.box(f"YanPencere_{fl}_{side}", (0.08, 0.8, 1.0), (side * (w / 2 + 0.01), 0, zc), M["window"]))
    # Kapı ve sundurma
    parts.append(C.box("Kapi", (1.0, 0.1, 2.1), (0, -d / 2 - 0.02, 0.4 + 1.05), M["door"]))
    parts.append(C.box("Basamak", (1.6, 0.6, 0.35), (0, -d / 2 - 0.3, 0.2), M["stone"]))
    parts.append(C.box("Sundurma", (1.8, 1.0, 0.08), (0, -d / 2 - 0.45, 0.4 + 2.35), M["roof"], rot=(math.radians(-12), 0, 0)))
    body = C.join([p for p in parts if p is not None], "Ev")
    body.parent = root
    hip_roof("Cati", w, d, 0.4 + H, min(w, d) * 0.28, 0.45, M["roof"], root)
    C.box("Baca", (0.5, 0.5, 1.6), (w * 0.25, d * 0.15, 0.4 + H + 0.9), pm, root)
    C.box("Baca_Kapak", (0.65, 0.65, 0.08), (w * 0.25, d * 0.15, 0.4 + H + 1.72), M["roof"], root)
    if rnd.random() < 0.6:    # çatıda güneş enerjili su ısıtıcısı (Anadolu'da çok yaygın)
        tank = C.cyl("GunesTank", 0.28, 1.6, (-w * 0.2, -d * 0.1, 0.4 + H + min(w, d) * 0.16 + 0.6), M["metal"], verts=16, rot=(0, math.pi / 2, 0))
        panel = C.box("GunesPanel", (1.8, 1.1, 0.05), (-w * 0.2, -d * 0.1 - 0.6, 0.4 + H + min(w, d) * 0.16 + 0.25), M["window"],
                      rot=(math.radians(35), 0, 0))
        C.join([tank, panel], "GunesEnerjisi").parent = root
    C.export_fbx(os.path.join(OUT, f"SuruIHA_House_{idx}.fbx"), root)


def mosque():
    C.reset_scene()
    C._materials.clear()
    M = mats()
    wall = C.mat("MAT_Plaster_B", (0.78, 0.76, 0.72), rough=0.88)
    root = C.empty("SuruIHA_Mosque")
    parts = [C.box("Temel", (13, 13, 2.0), (0, 0, -0.6), M["stone"])]
    parts.append(C.box("Harim", (12, 12, 7.5), (0, 0, 4.15), wall, bevel=0.04, segments=1))
    parts.append(C.box("Kasnak", (8.6, 8.6, 1.2), (0, 0, 8.5), wall))
    for side in range(4):
        a = side * math.pi / 2
        for k in (-1, 0, 1):
            off = Vector((math.cos(a), math.sin(a), 0)) * 6.01
            tang = Vector((-math.sin(a), math.cos(a), 0)) * k * 3.2
            p = off + tang
            for z, hh in ((2.6, 2.2), (5.6, 1.6)):
                parts.append(C.box(f"Pencere_{side}_{k}_{z}", (0.9 if abs(math.cos(a)) < 0.5 else 0.08,
                                                                 0.08 if abs(math.cos(a)) < 0.5 else 0.9, hh),
                                   (p.x, p.y, z), M["window"]))
    # Son cemaat yeri (revaklı giriş)
    parts.append(C.box("Revak_Dosemesi", (12, 4, 0.4), (0, -8, 0.2), M["stone"]))
    for k in range(4):
        parts.append(C.cyl(f"Sutun_{k}", 0.22, 3.6, (-4.5 + k * 3, -9.6, 2.2), M["stone"], verts=16))
    parts.append(C.box("Revak_Cati", (12.6, 4.4, 0.4), (0, -8, 4.2), wall))
    body = C.join(parts, "Cami")
    body.parent = root
    dome = C.sphere("Kubbe", 4.6, (0, 0, 9.1), M["lead"], root, scale=(1, 1, 0.82), segs=48, rings=24)
    bm = bmesh.new()
    bm.from_mesh(dome.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True)
    bm.to_mesh(dome.data)
    bm.free()
    C.cyl("Alem", 0.05, 1.4, (0, 0, 9.1 + 4.6 * 0.82 + 0.6), M["metal"], root, verts=8)
    # Minare: kaide, gövde, şerefe, petek, külah, alem
    mx, my = 7.6, -5.0
    mn = []
    mn.append(C.box("Minare_Kaide", (2.4, 2.4, 6.0), (mx, my, 2.4), wall, bevel=0.03, segments=1))
    mn.append(C.cyl("Minare_Govde", 1.05, 16.0, (mx, my, 5.4 + 8.0), wall, verts=16))
    mn.append(C.cyl("Serefe", 1.6, 0.5, (mx, my, 18.6), wall, verts=24, bevel=0.05))
    mn.append(C.cyl("Serefe_Korkuluk", 1.55, 0.9, (mx, my, 19.3), M["frame"], verts=24))
    mn.append(C.cyl("Petek", 0.9, 4.5, (mx, my, 21.6), wall, verts=16))
    C.join(mn, "Minare").parent = root
    C.cone("Kulah", 1.0, 0.05, 5.5, (mx, my, 26.6), M["lead"], root, verts=16)
    C.cyl("Minare_Alem", 0.04, 1.2, (mx, my, 29.9), M["metal"], root, verts=8)
    C.export_fbx(os.path.join(OUT, "SuruIHA_Mosque.fbx"), root)


def pole():
    """Ahşap elektrik direği + travers + izolatörler. Tel bağlantı noktaları 'Tel_0..2' boş nesneleri."""
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Pole")
    parts = [C.cyl("Direk", 0.14, 10.5, (0, 0, 4.25), M["wood"], verts=10)]
    parts.append(C.box("Travers", (2.4, 0.12, 0.12), (0, 0, 8.6), M["wood"]))
    parts.append(C.tube_between("Payanda_L", (-0.8, 0, 8.55), (0, 0, 7.9), 0.03, M["metal"], verts=6))
    parts.append(C.tube_between("Payanda_R", (0.8, 0, 8.55), (0, 0, 7.9), 0.03, M["metal"], verts=6))
    for i, x in enumerate((-1.05, 0.0, 1.05)):
        z = 8.75 if x != 0 else 9.6
        if x == 0:
            parts.append(C.cyl("Tepe_Izolator_Ayak", 0.03, 0.9, (0, 0, 9.15), M["metal"], verts=6))
        parts.append(C.cyl(f"Izolator_{i}", 0.07, 0.22, (x, 0, z), M["frame"], verts=12))
        C.empty(f"Tel_{i}", (x, 0, z + 0.12), root)
    C.join(parts, "Direk").parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Pole.fbx"), root)


rnd = random.Random(11)
for i, (w, d, fl) in enumerate(((8, 10, 1), (9, 11, 2), (7, 9, 1), (10, 12, 2))):
    house(i, w, d, fl, PLASTERS[i], rnd)
mosque()
pole()
print("Köy modelleri tamam")
