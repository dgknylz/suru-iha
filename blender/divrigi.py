"""Divriği (Sivas): Ulu Camii ve Darüşşifası (1228-29, Mengücekli), kale burçları ve surları, Divriği evleri.

    blender -b --factory-startup -P blender/divrigi.py -- <çıktı_klasörü> [önizleme.blend] [cami|kale|ev ...]
Çıktı: SuruIHA_Yapi_UluCami.fbx (+ ../textures/Yapi_UluCami_Detay.png), SuruIHA_Yapi_KaleKule.fbx,
       SuruIHA_Yapi_KaleBurc.fbx, SuruIHA_Yapi_KaleSur.fbx, SuruIHA_Yapi_DivrigiEv_0..3.fbx

Ulu Camii, yapının yayımlanmış fotoğraflarına (Wikimedia Commons: kaleden kuşbakışı, batı cephesi, kuzey ve batı
kapıları, darüşşifa kapısı, minare) bakılarak kodla kuruldu; ölçüler yaklaşıktır:
  * 32 x 64 m kesme taş külliye: kuzeyde 40 m'lik cami (beden duvarı 10 m), güneyde kıble duvarına dayanan 24 m'lik
    iki katlı darüşşifa (11,4 m). Duvarlar sağır, az ve küçük dikdörtgen demir parmaklıklı pencereli.
  * Örtü: alçak eğimli (12°) kurşun kaplı kırma çatılar, ahşap saçaklar ve yağmur iniş boruları; caminin ortasında
    ışıklık feneri, darüşşifanın ortasında aydınlık feneri; mihrap önü kubbesinin üstünde kare kaideden "Türk
    üçgenleri"yle sekizgene geçen taş külah, darüşşifanın kuzeydoğusunda türbenin küçük taş külahı.
  * Kuzey taç kapısı: duvardan 3,8 m yükselen, derin sivri kemerli niş; nişte ızgaralı kapı, üstünde altıgen yıldız,
    çıkıntılı mukarnaslı saçak ve mukarnas kavsara; başlıklı sütunlar ve Divriği'ye özgü yüksek kabartma bitkisel
    kitleler, madalyonlar, kitabe kuşağı; üstünde kendi saçaklı örtüsü.
  * Batı kapısı: pahlı yan yüzlü, dokuma gibi sık geometrik oymalı çerçeveler, küçük mukarnaslı niş, iki yanda
    basamaklı taş sekiler, duvarda rozet. Darüşşifa kapısı: üç kademeli iç içe sivri kemer, kapı ve üstünde pencere,
    çıkıntılı başlıklar. Doğuda Şah kapısı (pencere-kapı).
  * Kuzeybatı köşesinde yuvarlak payanda (kurşun külahlı) ve arkasından yükselen kare kürsülü silindir minare
    (mukarnaslı şerefe, taş korkuluk, petek, taş külah).
  * Batıda avlu ve külliyeyi taşıyan taş döşeli taraça (istinat duvarı ve korkuluklu).
Yüzeyler: UV0 dünya ölçekli (taş sıraları her yüzde yatay, Unity'de 4 m'lik kesme taş, 1 m'lik oyma, kurşun ve döşeme
dokuları), UV1 bütün külliyenin tek atlası: Cycles ile pişirilen ortam kapatma + zemin nemi, yağmur akıntısı, leke ve
toz (Unity'de HDRP ayrıntı haritası olarak taşı koyulaştırır). Blender'da önü (kuzey) -Y yönüne bakar.
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else os.path.dirname(os.path.abspath(__file__))
BLEND = ARGS[1] if len(ARGS) > 1 and ARGS[1].endswith(".blend") else None
os.makedirs(OUT, exist_ok=True)
TEX_OUT = os.path.join(os.path.dirname(os.path.abspath(OUT)), "textures")


def mats():
    M = dict(
        stone=C.mat("MAT_KesmeTas", (0.8, 0.7, 0.53), rough=0.85),
        carve=C.mat("MAT_Oyma", (0.8, 0.7, 0.53), rough=0.88),
        earth=C.mat("MAT_Toprak", (0.45, 0.38, 0.3), rough=0.95),
        lead=C.mat("MAT_Lead", (0.33, 0.35, 0.37), rough=0.45, metal=0.6),
        door=C.mat("MAT_Door", (0.22, 0.12, 0.06), rough=0.7),
        wood=C.mat("MAT_Wood", (0.25, 0.17, 0.1), rough=0.85),
        glass=C.mat("MAT_Glass", (0.01, 0.014, 0.018), rough=0.04, metal=0.3),
        black=C.mat("MAT_Black", (0.02, 0.02, 0.022), rough=0.6),
        metal=C.mat("MAT_Metal", (0.5, 0.51, 0.52), rough=0.38, metal=1.0),
        castle=C.mat("MAT_KaleTas", (0.55, 0.48, 0.4), rough=0.9),
        roof=C.mat("MAT_RoofTile", (0.42, 0.15, 0.07), rough=0.75),
        frame=C.mat("MAT_Frame", (0.8, 0.8, 0.78), rough=0.5),
    )
    return M


def mosque_mats():
    """Ulu Camii'ye özgü malzemeler (Unity'de dokulu, ayrıntı atlaslı HDRP malzemelerine eşlenir)."""
    M = mats()
    M.update(
        tas=C.mat("MAT_UC_Tas", (0.8, 0.7, 0.55), rough=0.8),
        oyma=C.mat("MAT_UC_Oyma", (0.82, 0.72, 0.57), rough=0.85),
        oyma2=C.mat("MAT_UC_Oyma2", (0.8, 0.69, 0.55), rough=0.85),
        kursun=C.mat("MAT_UC_Kursun", (0.47, 0.49, 0.5), rough=0.6, metal=0.2),
        ahsap=C.mat("MAT_UC_Ahsap", (0.2, 0.12, 0.07), rough=0.75),
        doseme=C.mat("MAT_UC_Doseme", (0.6, 0.57, 0.5), rough=0.85),
        meydan=C.mat("MAT_UC_TasMeydan", (0.72, 0.65, 0.53), rough=0.85),
        demir=C.mat("MAT_UC_Demir", (0.04, 0.04, 0.045), rough=0.55, metal=0.7),
        karanlik=C.mat("MAT_UC_Karanlik", (0.012, 0.011, 0.01), rough=0.9),
        kapi=C.mat("MAT_UC_Kapi", (0.2, 0.11, 0.055), rough=0.65),
    )
    M["carve"], M["stone"] = M["oyma"], M["tas"]          # eski yardımcılar (madalyon) aynı malzemeyi kullansın
    return M


# ---------------------------------------------------------------------------- geometri yardımcıları
def arch_outline(w, spring, pointed=True, n=14):
    """Kemer dış çizgisi (XZ düzleminde, tabanı z=0, ortası x=0): sivri (iki merkezli) ya da yuvarlak."""
    pts = [(-w / 2, 0.0), (-w / 2, spring)]
    if pointed:
        R = 0.8 * w
        cx = -w / 2 + R                             # sol yayın merkezi (sağda)
        th0, th1 = math.pi, math.acos(-cx / R)
        for i in range(1, n):
            t = th0 + (th1 - th0) * i / n
            pts.append((cx + R * math.cos(t), spring + R * math.sin(t)))
        apex = spring + R * math.sin(th1)
        pts.append((0.0, apex))
        right = [(-x, z) for x, z in reversed(pts[2:-1])]
        pts += right
    else:
        r = w / 2
        for i in range(1, 2 * n):
            t = math.pi - math.pi * i / (2 * n)
            pts.append((r * math.cos(t), spring + r * math.sin(t)))
    pts += [(w / 2, spring), (w / 2, 0.0)]
    return pts


def arch_top(w, spring, pointed=True):
    if not pointed:
        return spring + w / 2
    R = 0.8 * w
    cx = -w / 2 + R
    return spring + R * math.sin(math.acos(-cx / R))


def arch_half(w, spring, z):
    """Sivri kemerin z yüksekliğindeki yarı açıklığı."""
    if z <= spring:
        return w / 2
    R = 0.8 * w
    cx = -w / 2 + R
    q = (z - spring) / R
    if q >= 1.0:
        return 0.0
    return max(0.0, R * math.sqrt(1 - q * q) - cx)


def prism_xz(name, outline, y0, depth, material=None):
    """XZ düzlemindeki çokgeni y0'dan +Y yönünde depth kadar uzatır (duvara gömülü niş, kemer kesici...)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y0, z)) for x, z in outline]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    moved = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=(0, depth, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return C.mesh_object(name, bm, material, smooth=False)


def prism_xy(name, plan, z0, z1, material=None):
    """XY düzlemindeki plan çokgenini z0..z1 arasında dik prizma yapar."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z0)) for x, y in plan]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    moved = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return C.mesh_object(name, bm, material, smooth=False)


def cut(target, cutter):
    """Boolean fark: target'tan cutter'ı oyar, cutter silinir."""
    m = target.modifiers.new("Oy", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.object = cutter
    try:
        m.solver = "EXACT"
    except Exception:
        pass
    C.apply_modifiers(target)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return target


def arch_ring(name, w_out, s_out, w_in, s_in, y0, depth, material, pointed=True):
    """Kemer çerçevesi (archivolt): dış kemer prizması eksi iç kemer prizması."""
    o = prism_xz(name, arch_outline(w_out, s_out, pointed, n=20), y0, depth, material)
    c = prism_xz(name + "_ic", arch_outline(w_in, s_in, pointed, n=20), y0 - 0.5, depth + 1.0)
    return cut(o, c)


def rect_ring(name, w, h, band, y0, depth, z0, material):
    """Dikdörtgen bordür: dört kenar kutusu (ön yüz y0, -Y'ye doğru depth kadar çıkıntı)."""
    yc = y0 - depth / 2
    parts = [C.box(name + "_a", (w, depth, band), (0, yc, z0 + band / 2), material),
             C.box(name + "_u", (w, depth, band), (0, yc, z0 + h - band / 2), material),
             C.box(name + "_s", (band, depth, h - 2 * band), (-w / 2 + band / 2, yc, z0 + h / 2), material),
             C.box(name + "_r", (band, depth, h - 2 * band), (w / 2 - band / 2, yc, z0 + h / 2), material)]
    return C.join(parts, name)


def polygon_prism(name, sides, r, z0, z1, loc, material, rot=0.0):
    return C.cyl(name, r, z1 - z0, (loc[0], loc[1], (z0 + z1) / 2), material, verts=sides, smooth=False,
                 rot=(0, 0, rot))


def polygon_pyramid(name, sides, r, z0, h, loc, material, rot=0.0):
    bpy.ops.mesh.primitive_cone_add(vertices=sides, radius1=r, radius2=0.0, depth=h, location=(loc[0], loc[1], z0 + h / 2),
                                    rotation=(0, 0, rot))
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(material)
    return o


def orient_faces(bm, center):
    """Açık yüzeylerde normalleri merkezden dışarı çevirir."""
    for f in bm.faces:
        if f.normal.dot(f.calc_center_median() - center) < 0:
            f.normal_flip()


def medallion(name, r, loc, M, petals=12, depth=0.28, crescent=False):
    """Yüksek kabartma madalyon (-Y'ye bakar): disk, iki sıra yaprak, göbek; istenirse hilal çerçeve."""
    x, y, z = loc
    parts = [C.cyl(name + "_disk", r, depth, (x, y - depth / 2, z), M["carve"], verts=40, rot=(math.pi / 2, 0, 0))]
    parts.append(C.cyl(name + "_kenar", r * 1.08, depth * 0.5, (x, y - depth * 0.25, z), M["stone"], verts=40,
                       rot=(math.pi / 2, 0, 0)))
    for ring, (rr, n, sc) in enumerate([(0.62, petals, 0.34), (0.32, petals // 2 + 2, 0.24)]):
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * ring) / n
            px, pz = x + math.cos(a) * r * rr, z + math.sin(a) * r * rr
            p = C.sphere(f"{name}_y{ring}_{k}", 1.0, (px, y - depth - 0.06 * (ring + 1), pz), M["carve"],
                         scale=(r * sc * 0.42, 0.11 + 0.05 * ring, r * sc), segs=10, rings=6)
            p.rotation_euler = (0, -a + math.pi / 2, 0)
            C.apply_transform(p, location=False)
            parts.append(p)
    parts.append(C.sphere(name + "_gobek", r * 0.16, (x, y - depth - 0.12, z), M["carve"], scale=(1, 0.8, 1), segs=16, rings=8))
    if crescent:
        bpy.ops.mesh.primitive_torus_add(major_radius=r * 1.32, minor_radius=r * 0.1, major_segments=36, minor_segments=8,
                                         location=(x, y - 0.12, z), rotation=(math.pi / 2, 0, 0))
        t = bpy.context.active_object
        t.name = name + "_hilal"
        t.data.materials.append(M["carve"])
        parts.append(t)
    return C.join(parts, name)


def boss(name, r, loc, M, seed, lobes=9, depth=0.62):
    """Divriği'ye özgü yüksek kabartma (barok) bitkisel kitle: duvara gömülü, şişkin; sarmal kıvrılan yaprak dilimleri,
    dilimler arasında oluklar, düzensiz kabarıklıklar. İnce yüzey ayrıntısı oyma dokusundan gelir."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0, location=(0, 0, 0))
    o = bpy.context.active_object
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 2 * math.pi)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    tw = rnd.uniform(1.2, 2.4) * rnd.choice((-1, 1))
    for v in o.data.vertices:
        d = v.co.normalized()
        fwd = max(0.0, -d.y)
        phi = math.atan2(d.z, d.x)
        side = math.sqrt(max(0.0, 1 - fwd * fwd))
        a = lobes * phi + ph + tw * lobes * 0.3 * fwd
        groove = math.exp(-(math.sin(a * 0.5) / 0.22) ** 2)
        rr = (1.0 + 0.1 * math.cos(a) * side ** 0.6 - 0.07 * groove * side
              + 0.2 * noise.noise(d * 1.2 + off) + 0.06 * noise.noise(d * 4.0 - off) - 0.28 * (1 - fwd) ** 3)
        v.co = Vector((d.x * rr, d.y * rr * depth, d.z * rr))
    o.scale = (r, r, r)
    C.apply_transform(o, location=False, rotation=False)
    o.location = loc
    return C._finish(o, name, M["oyma"], None, True)


def muq_cell(bm, x0, x1, ya, yb, za, zb, ns=6, nt=4):
    """Mukarnas hücresi: önde sivri kemer ağzı (üzengileri kademenin altında, tepesi üstünde), içeri ve yukarı kaçan
    içbükey tonoz, kemerin iki yanında ön yüzde üçgen aynalar, arkada kapalı dip. Önü yb (-Y), arkası ya."""
    xm, w, dz = (x0 + x1) / 2, x1 - x0, zb - za

    def arch(s):
        return (1 - abs(2 * s - 1)) ** 0.75
    grid = []
    for j in range(nt + 1):
        t = j / nt
        row = []
        for i in range(ns + 1):
            s = i / ns
            xf, zf = x0 + w * s, za + 0.9 * dz * arch(s)
            xb, zk = xm + (s - 0.5) * w * 0.35, za + dz * (0.45 + 0.4 * arch(s))
            z = zf + (zk - zf) * t + 0.2 * dz * math.sin(math.pi * t) * (0.4 + 0.6 * arch(s))
            row.append(bm.verts.new((xf + (xb - xf) * t, yb + (ya - yb) * t, z)))
        grid.append(row)
    for j in range(nt):
        for i in range(ns):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    back = [bm.verts.new((grid[nt][i].co.x, ya, za)) for i in range(ns + 1)]
    for i in range(ns):
        bm.faces.new((back[i], back[i + 1], grid[nt][i + 1], grid[nt][i]))
    h = ns // 2
    cl, cr, top = bm.verts.new((x0, yb, zb)), bm.verts.new((x1, yb, zb)), bm.verts.new((xm, yb, zb))
    for i in range(h):
        bm.faces.new((cl, grid[0][i], grid[0][i + 1]))
    for i in range(h, ns):
        bm.faces.new((cr, grid[0][i], grid[0][i + 1]))
    bm.faces.new((cl, grid[0][h], top))
    bm.faces.new((cr, top, grid[0][h]))


def muqarnas_hood(name, nw, ns, z1, y_back, y_front, M, tiers=5, cell=0.62, mat="oyma"):
    """Mukarnas kavsara: sivri kemerli nişin tepesini, kademe kademe öne taşan içbükey hücre sıralarıyla doldurur.
    Kademeler yarım hücre kayar; hücre birleşimlerinde küçük sarkıtlar."""
    bm = bmesh.new()
    dz = (z1 - ns) / tiers
    proj = (y_front - y_back) / tiers
    for k in range(tiers):
        za, zb = ns + k * dz, ns + (k + 1) * dz
        ya, yb = y_back + k * proj, y_back + (k + 1) * proj
        hw = arch_half(nw, ns, za + 0.3 * dz)
        if hw < 0.08:
            break
        n = max(1, round(2 * hw / cell))
        if k % 2 == 1 and n > 2:
            n -= 1
        w = 2 * hw / n
        for i in range(n):
            x0 = -hw + i * w
            muq_cell(bm, x0, x0 + w, ya, yb, za, zb)
            if i > 0:
                tip = bm.verts.new((x0, yb, za - 0.3 * dz))
                q = [bm.verts.new((x0 + 0.06 * math.cos(a), yb + 0.06 * math.sin(a), za + 0.02)) for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]
                for m in range(4):
                    bm.faces.new((q[m], q[(m + 1) % 4], tip))
    ref = Vector((0, -1, -0.8))
    for f in bm.faces:
        if f.normal.dot(ref) < 0:
            f.normal_flip()
    return C.mesh_object(name, bm, M[mat], smooth=False)


def hip_roof(name, x0, x1, y0, y1, z, pitch, M, fascia=0.28, caps=True):
    """Kırma çatı: kurşun kaplı dört eğik yüz, mahya ve kırma kenarlarında kurşun başlık, ahşap saçak alnı ve altlığı."""
    t = math.tan(math.radians(pitch))
    W, D = x1 - x0, y1 - y0
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    bm = bmesh.new()
    c = [bm.verts.new(p) for p in ((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))]
    if W >= D:
        h = D / 2 * t
        a, b = bm.verts.new((x0 + D / 2, ym, z + h)), bm.verts.new((x1 - D / 2, ym, z + h))
        faces = [(c[0], c[1], b, a), (c[1], c[2], b), (c[2], c[3], a, b), (c[3], c[0], a)]
        lines = [(a, b), (c[0], a), (c[3], a), (c[1], b), (c[2], b)]
    else:
        h = W / 2 * t
        a, b = bm.verts.new((xm, y0 + W / 2, z + h)), bm.verts.new((xm, y1 - W / 2, z + h))
        faces = [(c[0], c[1], a), (c[1], c[2], b, a), (c[2], c[3], b), (c[3], c[0], a, b)]
        lines = [(a, b), (c[0], a), (c[1], a), (c[2], b), (c[3], b)]
    for f in faces:
        bm.faces.new(f)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    pts = [(p.co.copy(), q.co.copy()) for p, q in lines]
    parts = [C.mesh_object(name, bm, M["kursun"], smooth=False)]
    if caps:
        for k, (p, q) in enumerate(pts):
            if (p - q).length > 0.2:
                parts.append(C.tube_between(f"{name}_Baslik{k}", p + Vector((0, 0, 0.04)), q + Vector((0, 0, 0.04)), 0.06, M["kursun"], verts=8))
    parts.append(C.box(name + "_Altlik", (W, D, 0.05), (xm, ym, z - fascia), M["ahsap"]))
    for side in (-1, 1):
        parts.append(C.box(f"{name}_AlinX{side}", (W + 0.08, 0.06, fascia), (xm, y0 if side < 0 else y1, z - fascia / 2), M["ahsap"]))
        parts.append(C.box(f"{name}_AlinY{side}", (0.06, D, fascia), (x0 if side < 0 else x1, ym, z - fascia / 2), M["ahsap"]))
    return parts


def lantern(name, cx, cy, r, z0, z1, M):
    """Işıklık feneri: sekizgen taş kasnak, dört yüzünde sivri kemerli pencere, taş silme, kurşun külah ve alem."""
    parts = [polygon_prism(name + "_Kasnak", 8, r, z0, z1, (cx, cy), M["tas"], rot=math.pi / 8),
             polygon_prism(name + "_Silme", 8, r * 1.09, z1, z1 + 0.25, (cx, cy), M["tas"], rot=math.pi / 8),
             polygon_pyramid(name + "_Kulah", 8, r * 1.17, z1 + 0.25, r * 0.5, (cx, cy), M["kursun"], rot=math.pi / 8)]
    ap = r * math.cos(math.pi / 8)
    for k in range(0, 8, 2):
        a = k * math.pi / 4
        w = prism_xz(f"{name}_Pen{k}", arch_outline(0.5, 0.55, n=8), -0.04, 0.06, M["karanlik"])
        place(w, a + math.pi / 2, (cx + math.cos(a) * ap, cy + math.sin(a) * ap, z1 - 1.25))
        parts.append(w)
    top = z1 + 0.25 + r * 0.5
    parts.append(C.cyl(name + "_Alem", 0.035, 0.9, (cx, cy, top + 0.4), M["metal"], verts=8))
    parts.append(C.sphere(name + "_AlemTop", 0.1, (cx, cy, top + 0.55), M["metal"], segs=10, rings=6))
    return parts


def stone_pyramid(name, cx, cy, s, z0, z1, h_tr, h_pyr, M):
    """Taş külah: kare kaide, köşelerde eğik üçgen yüzlerle ("Türk üçgenleri") sekizgene geçiş, silme ve kesme taş
    sekizgen piramit; tepede taş başlık ve alem."""
    parts = [C.box(name + "_Kaide", (s, s, z1 - z0), (cx, cy, (z0 + z1) / 2), M["tas"])]
    R8 = s / 2 / math.cos(math.pi / 8)
    z2 = z1 + h_tr
    bm = bmesh.new()
    sq = [bm.verts.new((cx + sx * s / 2, cy + sy * s / 2, z1)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    oc = [bm.verts.new((cx + R8 * math.cos(math.pi / 8 + k * math.pi / 4), cy + R8 * math.sin(math.pi / 8 + k * math.pi / 4), z2))
          for k in range(8)]
    for f in ((sq[3], sq[0], oc[0], oc[7]), (sq[0], oc[1], oc[0]), (sq[0], sq[1], oc[2], oc[1]), (sq[1], oc[3], oc[2]),
              (sq[1], sq[2], oc[4], oc[3]), (sq[2], oc[5], oc[4]), (sq[2], sq[3], oc[6], oc[5]), (sq[3], oc[7], oc[6])):
        bm.faces.new(f)
    orient_faces(bm, Vector((cx, cy, z1)))
    parts.append(C.mesh_object(name + "_Gecis", bm, M["tas"], smooth=False))
    parts.append(polygon_prism(name + "_Silme", 8, R8 * 1.05, z2, z2 + 0.24, (cx, cy), M["tas"], rot=math.pi / 8))
    parts.append(polygon_pyramid(name + "_Kulah", 8, R8 * 1.0, z2 + 0.24, h_pyr, (cx, cy), M["tas"], rot=math.pi / 8))
    top = z2 + 0.24 + h_pyr
    parts.append(C.cone(name + "_Basl", 0.32, 0.12, 0.6, (cx, cy, top - 0.2), M["tas"], verts=12))
    parts.append(C.cyl(name + "_Alem", 0.04, 1.3, (cx, cy, top + 0.65), M["metal"], verts=8))
    parts.append(C.sphere(name + "_AlemTop", 0.14, (cx, cy, top + 0.75), M["metal"], segs=12, rings=8))
    return parts


def rect_window(name, w, h, zc, M, depth=0.45):
    """Duvara oyulan dikdörtgen pencere (yerel: duvar yüzü y=0, dışarısı -Y): oyuk (kesici), içeride koyu cam, demir
    parmaklık, taş eşik ve lento. (kesici, pencere) döndürür."""
    cutter = C.box(name + "_Oyuk", (w, 1.2, h), (0, 0.0, zc), None)
    parts = [C.box(name + "_Cam", (w, 0.04, h), (0, depth, zc), M["karanlik"]),
             C.box(name + "_Esik", (w + 0.36, 0.3, 0.14), (0, -0.08, zc - h / 2 - 0.07), M["tas"]),
             C.box(name + "_Lento", (w + 0.36, 0.1, 0.22), (0, -0.03, zc + h / 2 + 0.11), M["tas"])]
    nb = max(2, int(w / 0.15))
    for k in range(nb):
        parts.append(C.box(f"{name}_d{k}", (0.025, 0.025, h), (-w / 2 + (k + 0.5) * w / nb, 0.12, zc), M["demir"]))
    for k in range(int(h / 0.32)):
        parts.append(C.box(f"{name}_y{k}", (w, 0.02, 0.022), (0, 0.13, zc - h / 2 + (k + 0.7) * 0.32), M["demir"]))
    return cutter, C.join(parts, name)


def grille_door(name, w, h, y, M):
    """Karanlık kapı boşluğu ve önünde demir ızgara kanat (kuzey kapısındaki gibi)."""
    parts = [C.box(name + "_Bosluk", (w, 0.06, h), (0, y + 0.06, h / 2), M["karanlik"])]
    for k in range(int(w / 0.19) + 1):
        parts.append(C.box(f"{name}_d{k}", (0.035, 0.035, h), (-w / 2 + k * w / int(w / 0.19), y, h / 2), M["demir"]))
    for k in range(int(h / 0.3) + 1):
        parts.append(C.box(f"{name}_y{k}", (w, 0.03, 0.035), (0, y - 0.01, 0.05 + k * (h - 0.1) / int(h / 0.3)), M["demir"]))
    parts.append(C.box(name + "_Orta", (0.06, 0.05, h), (0, y - 0.02, h / 2), M["demir"]))
    return C.join(parts, name)


def wood_door(name, w, h, y, M):
    """Çift kanatlı ahşap kapı: kabarık panolar ve demir çivi sıraları."""
    parts = [C.box(name, (w, 0.08, h), (0, y, h / 2), M["kapi"])]
    for sx in (-1, 1):
        for k in range(4):
            parts.append(C.box(f"{name}_Pano{sx}{k}", (w / 2 - 0.22, 0.05, h / 4 - 0.18), (sx * w / 4, y - 0.05, (k + 0.5) * h / 4), M["kapi"]))
    parts.append(C.box(name + "_Orta", (0.04, 0.1, h), (0, y - 0.02, h / 2), M["black"]))
    return C.join(parts, name)


def hex_star(name, r, z, y, M):
    """Altıgen yıldız madalyon: altıgen levha, üstünde altı köşeli yıldız ve ortada altıgen göbek (-Y'ye bakar)."""
    def star(rr, ri):
        return [(math.cos(math.pi / 2 + k * math.pi / 6) * (rr if k % 2 == 0 else ri),
                 z + math.sin(math.pi / 2 + k * math.pi / 6) * (rr if k % 2 == 0 else ri)) for k in range(12)]

    def hexa(rr):
        return [(math.cos(k * math.pi / 3) * rr, z + math.sin(k * math.pi / 3) * rr) for k in range(6)]
    return C.join([prism_xz(name + "_Levha", hexa(r), y - 0.08, 0.08, M["oyma2"]),
                   prism_xz(name + "_Yildiz", star(r * 0.86, r * 0.5), y - 0.17, 0.1, M["oyma"]),
                   prism_xz(name + "_Gobek", hexa(r * 0.34), y - 0.25, 0.1, M["oyma"]),
                   C.sphere(name + "_Top", r * 0.13, (0, y - 0.27, z), M["oyma"], segs=12, rings=8)], name)


def mirror_for_unity(root):
    """FBX'ten Unity'ye geçişte Blender'ın -X'i doğuya düşer: çizimde batı = -X kabul edildiği için bütün parçalar
    X'te aynalanır (normaller çevrilir). Böylece minare ve batı kapıları Unity'de gerçekten batıda kalır."""
    for o in root.children_recursive:
        if o.type != "MESH":
            continue
        o.data.transform(Matrix.Translation(o.location))
        o.location = (0, 0, 0)
        o.data.transform(Matrix.Scale(-1, 4, (1, 0, 0)))
        o.data.flip_normals()


def place(obj, rot_z, offset):
    """Yerel çizilen parçayı döndürüp (Z ekseni) yerine taşır (veriye uygular). Önce nesnenin konumu veriye
    katılır: dönüş nesnenin kendi merkezi değil, yerel çizimin sıfır noktası etrafında olsun."""
    obj.data.transform(Matrix.Translation(obj.location))
    obj.location = (0, 0, 0)
    obj.data.transform(Matrix.Translation(Vector(offset)) @ Matrix.Rotation(rot_z, 4, "Z"))
    return obj


# ---------------------------------------------------------------------------- dünya ölçekli UV, atlas, pişirme
TILE = {"MAT_UC_Tas": (8.0, 4.0), "MAT_UC_TasMeydan": (8.0, 4.0), "MAT_UC_Oyma": (2.0, 2.0),
        "MAT_UC_Oyma2": (2.0, 3.4641016), "MAT_UC_Kursun": (4.0, 4.0), "MAT_UC_Doseme": (4.0, 4.0)}


def bake_xforms(root):
    """Bütün parçaların konum/dönüş/ölçeğini veriye uygular (veri = dünya koordinatı)."""
    for o in root.children_recursive:
        if o.type == "MESH":
            o.data.transform(o.matrix_world)
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.rotation_mode = "XYZ"
            o.location, o.rotation_euler, o.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)


def uv_world(o):
    """UV0: dünya ölçekli; 1 UV birimi = malzemenin döşeme ölçüsü. Dik yüzlerde u yüz boyunca yatay, v yükseklik (taş
    sıraları her yüzde yatay ve köşelerde buluşur); düze yakın yüzlerde üstten izdüşüm; yumuşak (silindir, koni)
    yüzlerde açı x yarıçap (dikişsiz sarılır); kurşun çatıda u saçak boyunca, v eğim boyunca (fitiller eğimden akar)."""
    me = o.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = [v.co.copy() for v in me.vertices]
    try:
        cn = [c.vector.copy() for c in me.corner_normals]
    except AttributeError:
        me.calc_normals_split()
        cn = [lp.normal.copy() for lp in me.loops]
    names = [m.name if m else "" for m in me.materials]
    for p in me.polygons:
        mname = names[p.material_index] if names else ""
        tu, tv = TILE.get(mname, (1.0, 1.0))
        n = p.normal
        ls = list(range(p.loop_start, p.loop_start + p.loop_total))
        pts = [co[me.loops[lp].vertex_index] for lp in ls]
        res = None
        hn = Vector((n.x, n.y))
        if mname == "MAT_UC_Kursun" and hn.length > 0.05:
            h = hn.normalized()
            k = 1.0 / max(0.3, abs(n.z))
            res = [(-q.x * h.y + q.y * h.x, (q.x * h.x + q.y * h.y) * k) for q in pts]
        elif abs(n.z) > 0.72:
            res = [(q.x, q.y) for q in pts]
        elif p.use_smooth:
            th = [math.atan2(cn[lp].y, cn[lp].x) for lp in ls]
            if max(th) - min(th) > math.pi:
                th = [t + 2 * math.pi if t < 0 else t for t in th]
            i0, i1 = th.index(min(th)), th.index(max(th))
            dth = th[i1] - th[i0]
            if dth > 1e-3:
                chord = (Vector((pts[i1].x, pts[i1].y)) - Vector((pts[i0].x, pts[i0].y))).length
                R = chord / (2 * math.sin(dth / 2))
                if 0.02 < R < 50:
                    off = random.Random(round(R * 20)).uniform(0, tu)
                    res = [(t * R + off, q.z) for t, q in zip(th, pts)]
        if res is None:
            h = hn.normalized() if hn.length > 1e-4 else Vector((0, -1))
            c = p.center
            # aynı düzlemdeki yüzler aynı kaydırmayı alır: taş deseni her duvarda başka yerden başlar (tekrar seçilmez)
            key = (round(h.x * 8), round(h.y * 8), round((c.x * h.x + c.y * h.y) * 2))
            off = random.Random(hash(key) & 0xFFFFFFFF).uniform(0, tu)
            res = [(-q.x * h.y + q.y * h.x + off, q.z) for q in pts]
        for lp, (a, b) in zip(ls, res):
            uv[lp].uv = (a / tu, b / tv)


def remove_hidden(obj, others, n_dirs=28):
    """Dışarıdan görünmeyen yüzleri siler (iç içe geçen kutuların gömülü yüzleri, çatı altında kalan duvar üstleri,
    temel altları): yüzün ortasından ve köşelerinin yakınından yarıküreye ışın atılır; hiçbiri sahneden kaçamıyorsa
    yüz kapalıdır. Atlasın yeri görünen yüzlere kalır."""
    from mathutils.bvhtree import BVHTree
    ball = bmesh.new()
    for o in [obj] + others:
        ball.from_mesh(o.data)
    tree = BVHTree.FromBMesh(ball)
    ga = math.pi * (3 - math.sqrt(5))
    hemi = []
    for k in range(n_dirs):
        zz = 0.12 + 0.88 * (k + 0.5) / n_dirs
        rr = math.sqrt(1 - zz * zz)
        hemi.append((rr * math.cos(ga * k), rr * math.sin(ga * k), zz))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    hidden = []
    for f in bm.faces:
        n = f.normal
        if n.length < 0.5:
            continue
        t = (n.cross(Vector((0, 0, 1))) if abs(n.z) < 0.9 else n.cross(Vector((1, 0, 0)))).normalized()
        b = n.cross(t)
        dirs = [t * x + b * y + n * zz for x, y, zz in hemi]
        cen = f.calc_center_median()
        pts = [cen] + [v.co.lerp(cen, 0.1) for v in f.verts]
        seen = False
        for p in pts:
            o = p + n * 0.004
            for d in dirs:
                if tree.ray_cast(o, d, 400.0)[0] is None:
                    seen = True
                    break
            if seen:
                break
        if not seen:
            hidden.append(f)
    bmesh.ops.delete(bm, geom=hidden, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    ball.free()
    print(f"görünmeyen yüz silindi: {len(hidden)}")


def atlas_uv(o):
    """UV1 ("Atlas"): bütün külliyenin örtüşmesiz tek açılımı (ayrıntı haritası için)."""
    me = o.data
    at = me.uv_layers.new(name="Atlas")
    me.uv_layers.active = at
    C.select_only(o)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(80), island_margin=0.001, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=0.0016, shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin=0.0016)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers.active = me.uv_layers[0]
    me.uv_layers[0].active_render = True


def gpu_cycles(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            try:
                prefs.refresh_devices()
            except AttributeError:
                prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = "GPU"
                print("Cycles", kind, [d.name for d in devs])
                break
    except Exception as e:  # GPU yoksa işlemciyle pişirilir
        print("Cycles işlemcide:", e)
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False


def _vnoise(P, seed):
    """Üç boyutlu değer gürültüsü (karma kafes, yumuşak ara değer), P: (n, 3)."""
    Pi = np.floor(P).astype(np.int64)
    f = P - Pi
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(P), np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                n = ((Pi[:, 0] + dx) * 73856093) ^ ((Pi[:, 1] + dy) * 19349663) ^ ((Pi[:, 2] + dz) * 83492791) ^ seed
                n = (n ^ (n >> 13)) * 1274126177
                n = n ^ (n >> 16)
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += (w * ((n & 0xFFFF).astype(np.float32) / 65535.0)).astype(np.float32)
    return out


def _fbm(P, seed, octaves=4):
    s, a, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        s = s + a * _vnoise(P * (2 ** o), seed + 101 * o)
        norm += a
        a *= 0.5
    return s / norm


def bake_detail(obj, path, res=4096):
    """Atlasa ortam kapatma, konum ve normal pişirir (Cycles), yıpranmayı hesaplar ve HDRP ayrıntı haritası yazar:
    R = albedo koyulaştırma (0,5 nötr), G/A = normal (nötr), B = pürüzsüzlük (nötr)."""
    sc = bpy.context.scene
    gpu_cycles(64)
    w = bpy.data.worlds.new("Pisirme")
    sc.world = w
    w.light_settings.distance = 2.6
    dup = obj.copy()
    dup.data = obj.data.copy()
    bpy.context.collection.objects.link(dup)
    obj.hide_render = True
    bm_mat = bpy.data.materials.new("Pisir")
    try:
        bm_mat.use_nodes = True
    except Exception:
        pass
    nt = bm_mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    tex = nt.nodes.new("ShaderNodeTexImage")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    nt.nodes.active = tex
    dup.data.materials.clear()
    dup.data.materials.append(bm_mat)
    for p in dup.data.polygons:
        p.material_index = 0
    dup.data.uv_layers.active = dup.data.uv_layers["Atlas"]
    C.select_only(dup)
    buf = np.zeros(res * res * 4, np.float32)

    def run(kind, socket=None):
        img = bpy.data.images.new(kind, res, res, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set(np.zeros(res * res * 4, np.float32))
        tex.image = img
        if socket:
            nt.links.new(geo.outputs[socket], em.inputs["Color"])
            sc.cycles.samples = 1
        else:
            sc.cycles.samples = 96
        bpy.ops.object.bake(type="EMIT" if socket else "AO", margin=12, margin_type="EXTEND", use_clear=False)
        img.pixels.foreach_get(buf)
        print("pişirildi:", kind)
        return buf.reshape(res, res, 4).copy()

    ao = run("AO")
    pos = run("Konum", "Position")
    nrm = run("Normal", "Normal")
    bpy.data.objects.remove(dup, do_unlink=True)
    obj.hide_render = False

    valid = ao[..., 3] > 0.5
    P = pos[valid, :3].astype(np.float32)
    N = nrm[valid, :3]
    A = np.clip(ao[valid, 0], 0, 1)
    z = P[:, 2]
    vert = np.clip(1.0 - np.abs(N[:, 2]) * 1.4, 0, 1)
    # 1) ortam kapatma: oyuklar, nişler, saçak altı, pencere içleri, duvar dibi
    f_ao = 0.4 + 0.6 * A ** 1.15
    # 2) zemin nemi ve sıçrayan çamur: dipte koyu, düzensiz sınır
    damp_h = 0.8 + 0.8 * _fbm(P * 0.4, 11, 3)
    f_damp = 1 - 0.3 * np.clip((damp_h - z) / 0.8, 0, 1) * (0.4 + 0.6 * vert)
    # 3) yağmur akıntıları: düşey uzamış gürültü, yukarıda (saçak, silme altı) daha yoğun
    st = _fbm(P * np.array([1.4, 1.4, 0.045], np.float32), 23, 3)
    streak = np.clip((st - 0.5) * 3.0, 0, 1) * vert * (0.3 + 0.7 * np.clip((z - 2.0) / 8.0, 0, 1))
    f_streak = 1 - 0.22 * streak
    # 4) geniş lekeler (onarım farkı, yaşlanma)
    bl = _fbm(P * 0.1, 37, 3)
    f_blot = 0.86 + 0.14 * np.clip((bl - 0.3) * 1.8, 0, 1)
    # 5) yukarı bakan çıkıntılarda (sekiler, silmeler, başlıklar) toz ve liken
    up = np.clip((N[:, 2] - 0.6) * 2.5, 0, 1)
    f_up = 1 - 0.2 * up * _fbm(P * 2.0, 41, 2)
    D = np.clip(f_ao * f_damp * f_streak * f_blot * f_up, 0.15, 1.0)
    R = 0.5 - 0.5 * np.sqrt(1 - np.sqrt(D))
    img = np.full((res, res, 4), 0.5, np.float32)
    img[valid, 0] = R
    out_img = bpy.data.images.new("Detay", res, res, alpha=True)
    out_img.colorspace_settings.name = "Non-Color"
    out_img.pixels.foreach_set(img.ravel())
    out_img.filepath_raw = path
    out_img.file_format = "PNG"
    out_img.save()
    # kontrol için koyulaşma görüntüsü
    dbg = np.ones((res, res, 4), np.float32)
    dbg[valid, 0] = dbg[valid, 1] = dbg[valid, 2] = D
    di = bpy.data.images.new("DetayKontrol", res, res, alpha=True)
    di.pixels.foreach_set(dbg.ravel())
    di.filepath_raw = os.path.join(os.path.dirname(path), "..", "Yapi_UluCami_Detay_kontrol.png")
    di.file_format = "PNG"
    di.save()
    print(f"ayrıntı atlası: {path} (doluluk %{100 * valid.mean():.0f}, koyulaşma ort. {D.mean():.2f})")


# ---------------------------------------------------------------------------- taç kapılar (yerel: duvar yüzü y=0, kapı -Y'ye bakar)
def north_portal(M):
    """Kuzey taç kapısı ("Cennet Kapısı"): 10,4 x 13,8 m, duvardan 1,6 m çıkıntılı, beden duvarından 3,8 m yükselir."""
    W, H, P = 10.4, 13.8, 1.6
    nw, ns = 5.2, 7.4
    top = arch_top(nw, ns)
    parts = []
    block = C.box("KK_Govde", (W, P + 0.3, H), (0, -(P + 0.3) / 2 + 0.3, H / 2), M["tas"])
    cut(block, prism_xz("KK_Nis", arch_outline(nw, ns, n=20), -P - 0.5, P + 0.48))
    parts.append(block)
    # üç sıra bordür (dışta dokuma gibi geçme, ortada yıldız geçme, içte sade silme) ve kemer yüzleri
    parts.append(rect_ring("KK_Bordur1", W - 0.1, H - 0.7, 0.62, -P, 0.12, 0.6, M["oyma2"]))
    parts.append(rect_ring("KK_Bordur2", W - 1.5, H - 1.9, 0.42, -P, 0.16, 1.1, M["oyma"]))
    parts.append(arch_ring("KK_Kemer1", nw + 0.9, ns, nw + 0.2, ns, -P, 0.18, M["oyma"]))
    parts.append(arch_ring("KK_Kemer2", nw + 0.2, ns, nw, ns, -P, 0.06, M["tas"]))
    # nişin içi: yan yüzlerde ve dipte oyma panolar
    for sx in (-1, 1):
        parts.append(C.box(f"KK_Yan{sx}", (0.05, P - 0.1, ns - 0.4), (sx * (nw / 2 - 0.02), -P / 2 - 0.02, (ns - 0.4) / 2 + 0.2), M["oyma"]))
    parts.append(C.box("KK_Dip", (nw - 0.08, 0.05, ns - 0.6), (0, -0.045, (ns - 0.6) / 2 + 0.3), M["oyma2"]))
    # ızgaralı kapı, kapı çerçevesi, üstünde altıgen yıldız
    gd = grille_door("KK_Kapi", 2.3, 3.9, -0.13, M)
    parts.append(gd)
    parts.append(rect_ring("KK_KapiCerceve", 3.1, 4.4, 0.32, -0.07, 0.1, 0.0, M["oyma"]))
    parts.append(hex_star("KK_Altigen", 0.82, 5.35, -0.07, M))
    # çıkıntılı saçak (altında iki kademe mukarnas) ve kemerin tepesindeki mukarnas kavsara
    parts.append(C.box("KK_Sacak", (nw - 0.06, 1.15, 0.38), (0, -0.6, ns - 0.17), M["oyma"]))
    parts.append(C.box("KK_SacakAlin", (nw - 0.06, 0.12, 0.42), (0, -1.2, ns - 0.55), M["oyma2"]))
    parts.append(muqarnas_hood("KK_SacakMuk", nw - 0.1, 6.35, ns - 0.36, -0.05, -1.1, M, tiers=2, cell=0.5))
    parts.append(muqarnas_hood("KK_Kavsara", nw - 0.06, ns, top - 0.12, -0.03, -P + 0.25, M, tiers=6, cell=0.58))
    # başlıklı sütunlar (üstte ince ikinci sütun)
    for sx in (-1, 1):
        x = sx * (nw / 2 + 0.7)
        parts.append(C.box(f"KK_Kaide{sx}", (0.82, 0.8, 0.75), (x, -P - 0.18, 0.375), M["tas"]))
        parts.append(C.cyl(f"KK_Sutun{sx}", 0.3, 6.15, (x, -P - 0.18, 0.75 + 3.075), M["oyma2"], verts=24))
        parts.append(C.box(f"KK_Baslik{sx}", (0.98, 0.92, 0.85), (x, -P - 0.2, 7.3), M["oyma"]))
        parts.append(C.cyl(f"KK_UstSutun{sx}", 0.21, 2.3, (x, -P - 0.18, 7.75 + 1.15), M["oyma2"], verts=20))
        parts.append(C.box(f"KK_UstBaslik{sx}", (0.62, 0.6, 0.42), (x, -P - 0.18, 10.26), M["oyma"]))
    # yüksek kabartma bitkisel kitleler (sütunla bordür arasında, kemer omuzlarında) ve madalyonlar
    rnd = random.Random(1228)
    for sx in (-1, 1):
        z, k = 1.25, 0
        while z < 12.3:
            r = (0.56 if k % 2 == 0 else 0.42) * rnd.uniform(0.9, 1.1)
            parts.append(boss(f"KK_Kabartma{sx}{k}", r, (sx * (3.98 + rnd.uniform(-0.08, 0.08)), -P - 0.1, z), M, rnd.randint(0, 9999),
                              lobes=rnd.choice((7, 8, 9, 10, 11))))
            z += r * 1.45
            k += 1
        parts.append(medallion(f"KK_Madalyon{sx}", 0.62, (sx * 2.55, -P - 0.12, 11.1), M, petals=14))
        parts.append(boss(f"KK_KemerKabartma{sx}", 0.36, (sx * 1.75, -P - 0.2, 12.3), M, rnd.randint(0, 9999), lobes=9))
    parts.append(C.box("KK_Kitabe", (2.6, 0.12, 0.5), (0, -P - 0.1, 12.32), M["oyma2"]))
    # tepe silmesi ve kapının kendi saçaklı örtüsü
    parts.append(C.box("KK_Silme", (W + 0.3, P + 0.6, 0.3), (0, -(P + 0.6) / 2 + 0.3, H + 0.15), M["tas"]))
    parts += hip_roof("KK_Cati", -W / 2 - 0.5, W / 2 + 0.5, -P - 0.75, 0.6, H + 0.32, 22.0, M, fascia=0.22)
    # önünde seki ve basamaklar
    parts.append(C.box("KK_Seki", (W - 1.0, 2.2, 0.36), (0, -P - 1.1, 0.18), M["tas"]))
    parts.append(C.box("KK_Basamak", (W - 2.2, 0.42, 0.18), (0, -P - 2.41, 0.09), M["tas"]))
    return C.join(parts, "KuzeyTacKapi")


def west_portal(M):
    """Batı kapısı: 7,8 x 10,7 m, pahlı yan yüzlü; dokuma gibi geçmeli üç çerçeve, sivri kemerli küçük niş, mukarnas,
    ahşap kapı, iki yanda basamaklı taş sekiler; solunda duvarda büyük rozet."""
    W, H, P, F = 7.8, 10.7, 1.0, 6.2
    plan = [(-W / 2, 0.3), (-W / 2, 0.0), (-F / 2, -P), (F / 2, -P), (W / 2, 0.0), (W / 2, 0.3)]
    nw, ns = 2.2, 4.4
    top = arch_top(nw, ns)
    block = prism_xy("BK_Govde", plan, 0.0, H, M["tas"])
    cut(block, prism_xz("BK_Nis", arch_outline(nw, ns, n=16), -P - 0.5, 0.5 + P - 0.38))
    parts = [block]
    parts.append(rect_ring("BK_Bordur1", F - 0.25, H - 1.4, 0.45, -P, 0.1, 0.9, M["oyma2"]))
    parts.append(rect_ring("BK_Bordur2", F - 1.4, H - 2.6, 0.34, -P, 0.14, 1.4, M["oyma"]))
    parts.append(rect_ring("BK_Bordur3", F - 2.4, H - 4.0, 0.22, -P, 0.07, 1.9, M["oyma2"]))
    pano = C.box("BK_Pano", (F - 2.84, 0.04, H - 4.44), (0, -P - 0.02, 1.9 + 0.22 + (H - 4.44) / 2), M["oyma2"])
    cut(pano, prism_xz("BK_PanoNis", arch_outline(nw + 0.5, ns, n=16), -P - 0.5, 1.2))
    parts.append(pano)
    parts.append(arch_ring("BK_Kemer", nw + 0.5, ns, nw, ns, -P, 0.16, M["oyma"]))
    parts.append(muqarnas_hood("BK_Mukarnas", nw - 0.04, ns, top - 0.08, -0.4, -P + 0.08, M, tiers=4, cell=0.45))
    parts.append(wood_door("BK_Kapi", 1.5, 2.6, -0.42, M))
    parts.append(rect_ring("BK_KapiCerceve", 1.9, 2.85, 0.2, -0.44, 0.06, 0.0, M["oyma"]))
    parts.append(C.box("BK_Alinlik", (nw - 0.06, 0.04, ns - 2.85), (0, -0.4, 2.85 + (ns - 2.85) / 2), M["oyma"]))
    for sx in (-1, 1):
        for k in range(3):
            d = 0.85 - 0.22 * k
            parts.append(C.box(f"BK_Seki{sx}{k}", (1.25, d, 0.32), (sx * 1.85, -P - d / 2, 0.16 + 0.32 * k), M["tas"]))
    parts.append(medallion("BK_Rozet", 0.85, (-5.4, -0.02, 7.2), M, petals=16, depth=0.22))
    parts.append(boss("BK_Kabartma", 0.32, (5.0, -0.1, 7.6), M, 77, lobes=8))
    parts.append(prism_xy("BK_Silme", [(-W / 2 - 0.15, 0.3), (-W / 2 - 0.15, 0.0), (-F / 2 - 0.1, -P - 0.15), (F / 2 + 0.1, -P - 0.15),
                                       (W / 2 + 0.15, 0.0), (W / 2 + 0.15, 0.3)], H, H + 0.28, M["tas"]))
    parts += hip_roof("BK_Cati", -W / 2 - 0.4, W / 2 + 0.4, -P - 0.6, 0.6, H + 0.3, 22.0, M, fascia=0.2)
    return C.join(parts, "BatiKapi")


def hospital_portal(M):
    """Darüşşifa taç kapısı: 10 x 13,4 m; üç kademeli iç içe sivri kemerli derin girinti, nişte ahşap kapı ve üstünde
    parmaklıklı pencere, kemer üzengilerinde çıkıntılı oymalı başlıklar, omuzlarda madalyonlar."""
    W, H, P = 10.0, 13.4, 1.4
    ns = 6.4
    parts = []
    block = C.box("DK_Govde", (W, P + 0.3, H), (0, -(P + 0.3) / 2 + 0.3, H / 2), M["tas"])
    steps = ((7.4, 0.3), (6.2, 0.65), (4.8, P - 0.02))
    for k, (w, d) in enumerate(steps):
        cut(block, prism_xz(f"DK_Girinti{k}", arch_outline(w, ns, n=20), -P - 0.5, d + 0.5))
    parts.append(block)
    parts.append(rect_ring("DK_Bordur", W - 0.1, H - 0.7, 0.45, -P, 0.12, 0.6, M["oyma2"]))
    parts.append(arch_ring("DK_DisKemer", 7.4 + 0.6, ns, 7.4, ns, -P, 0.14, M["oyma"]))
    parts.append(arch_ring("DK_Kademe1", 7.38, ns, 6.22, ns, -P + 0.28, 0.04, M["oyma2"]))
    parts.append(arch_ring("DK_Kademe2", 6.18, ns, 4.82, ns, -P + 0.63, 0.04, M["oyma"]))
    for sx in (-1, 1):
        parts.append(C.box(f"DK_Yan{sx}", (0.05, 0.7, ns - 0.3), (sx * 2.38, -0.4, (ns - 0.3) / 2 + 0.15), M["oyma"]))
        parts.append(C.cyl(f"DK_Sutun{sx}", 0.22, 5.6, (sx * 3.1, -P + 0.5, 0.5 + 2.8), M["oyma2"], verts=20))
        parts.append(C.box(f"DK_Baslik{sx}", (0.85, 0.95, 1.05), (sx * 3.85, -P - 0.3, ns + 0.45), M["oyma"]))
        parts.append(boss(f"DK_Kabartma{sx}", 0.42, (sx * 3.85, -P - 0.25, ns - 0.45), M, 400 + sx, lobes=9))
        parts.append(medallion(f"DK_Madalyon{sx}", 0.58, (sx * 3.8, -P - 0.1, 10.0), M, petals=16, crescent=False))
        parts.append(medallion(f"DK_IcMadalyon{sx}", 0.42, (sx * 1.55, -0.05, 5.1), M, petals=12, depth=0.18))
    parts.append(C.box("DK_Dip", (4.7, 0.05, ns - 0.4), (0, -0.045, (ns - 0.4) / 2 + 0.2), M["oyma2"]))
    parts.append(wood_door("DK_Kapi", 2.0, 3.2, -0.1, M))
    parts.append(rect_ring("DK_KapiCerceve", 2.5, 3.5, 0.25, -0.08, 0.08, 0.0, M["oyma"]))
    parts.append(C.box("DK_Pencere", (1.2, 0.04, 1.4), (0, -0.09, 5.1), M["karanlik"]))
    for k in range(6):
        parts.append(C.box(f"DK_Demir{k}", (0.025, 0.03, 1.4), (-0.5 + k * 0.2, -0.13, 5.1), M["demir"]))
    parts.append(rect_ring("DK_PencereCerceve", 1.7, 1.9, 0.24, -0.08, 0.1, 4.15, M["oyma"]))
    parts.append(muqarnas_hood("DK_Mukarnas", 4.74, ns, arch_top(4.8, ns) - 0.12, -0.04, -0.68, M, tiers=5, cell=0.56))
    parts.append(C.box("DK_Silme", (W + 0.3, P + 0.6, 0.3), (0, -(P + 0.6) / 2 + 0.3, H + 0.15), M["tas"]))
    parts += hip_roof("DK_Cati", -W / 2 - 0.5, W / 2 + 0.5, -P - 0.7, 0.6, H + 0.32, 22.0, M, fascia=0.22)
    return C.join(parts, "DarussifaTacKapisi")


def shah_portal(M):
    """Doğu (Şah) kapısı: hükümdar mahfiline açılan pencere-kapı; çerçeveli, sivri kemerli niş, mukarnas, parmaklıklı
    büyük pencere."""
    W, H, P = 5.6, 8.2, 0.7
    nw, ns = 2.2, 4.6
    block = C.box("SK_Govde", (W, P + 0.3, H), (0, -(P + 0.3) / 2 + 0.3, H / 2), M["tas"])
    cut(block, prism_xz("SK_Nis", arch_outline(nw, ns, n=16), -P - 0.5, 0.5 + P - 0.25))
    parts = [block,
             rect_ring("SK_Bordur", W - 0.1, H - 0.5, 0.4, -P, 0.1, 0.3, M["oyma2"]),
             rect_ring("SK_Bordur2", W - 1.2, H - 1.4, 0.26, -P, 0.12, 0.7, M["oyma"]),
             arch_ring("SK_Kemer", nw + 0.5, ns, nw, ns, -P, 0.14, M["oyma"]),
             C.box("SK_Pencere", (1.5, 0.04, 2.0), (0, -0.27, 3.3), M["karanlik"]),
             C.box("SK_Esik", (1.9, 0.3, 0.14), (0, -0.35, 2.23), M["tas"]),
             C.box("SK_AltPano", (nw - 0.06, 0.04, 2.1), (0, -0.27, 1.1), M["oyma2"]),
             muqarnas_hood("SK_Mukarnas", nw - 0.04, ns, arch_top(nw, ns) - 0.08, -0.27, -P + 0.06, M, tiers=3, cell=0.48),
             C.box("SK_Silme", (W + 0.2, P + 0.5, 0.26), (0, -(P + 0.5) / 2 + 0.3, H + 0.13), M["tas"])]
    for k in range(8):
        parts.append(C.box(f"SK_Demir{k}", (0.025, 0.03, 2.0), (-0.66 + k * 0.19, -0.33, 3.3), M["demir"]))
    parts += hip_roof("SK_Cati", -W / 2 - 0.35, W / 2 + 0.35, -P - 0.5, 0.5, H + 0.26, 22.0, M, fascia=0.18)
    return C.join(parts, "SahKapisi")


def minaret(M, cx, cy):
    """Minare (1523): beden duvarının köşesinde kare kürsü, pahla sekizgene ve silindire geçiş, iki bilezikli kesme taş
    gövde, kademeli (mukarnaslı) şerefe altı, taş korkuluk, petek ve taş külah."""
    p = [C.box("Minare_Kursu", (3.4, 3.4, 12.2), (cx, cy, 12.2 / 2 - 0.4), M["tas"]),
         polygon_prism("Minare_Pah", 8, 1.84, 11.8, 12.4, (cx, cy), M["tas"], rot=math.pi / 8),
         C.cyl("Minare_Govde", 1.3, 11.75, (cx, cy, 12.4 + 11.75 / 2), M["tas"], verts=40)]
    for z in (16.8, 20.9):
        p.append(C.cyl(f"Minare_Bilezik{z}", 1.37, 0.32, (cx, cy, z), M["oyma"], verts=40))
    p.append(C.cone("Minare_SerefeAlti", 1.3, 1.62, 0.55, (cx, cy, 24.4), M["oyma"], verts=40))
    p.append(C.cyl("Minare_Kademe1", 1.66, 0.22, (cx, cy, 24.78), M["oyma2"], verts=40))
    p.append(C.cone("Minare_SerefeAlti2", 1.66, 1.92, 0.35, (cx, cy, 25.06), M["oyma"], verts=40))
    p.append(C.cyl("Minare_Serefe", 1.98, 0.2, (cx, cy, 25.33), M["tas"], verts=40))
    kor = C.cyl("Minare_Korkuluk", 1.95, 0.95, (cx, cy, 25.9), M["oyma2"], verts=40)
    cut(kor, C.cyl("Minare_KorkulukIc", 1.8, 1.4, (cx, cy, 25.95), None, verts=40))
    p.append(kor)
    p.append(C.cyl("Minare_Petek", 1.0, 2.6, (cx, cy, 25.43 + 1.3), M["tas"], verts=32))
    p.append(C.cyl("Minare_PetekSilme", 1.08, 0.22, (cx, cy, 28.1), M["oyma"], verts=32))
    p.append(C.cone("Minare_Kulah", 1.08, 0.08, 1.6, (cx, cy, 28.21 + 0.8), M["tas"], verts=32))
    p.append(C.cyl("Minare_Alem", 0.04, 1.1, (cx, cy, 30.4), M["metal"], verts=8))
    p.append(C.sphere("Minare_AlemTop", 0.12, (cx, cy, 30.55), M["metal"], segs=12, rings=8))
    return p


# ---------------------------------------------------------------------------- külliye
def ulu_cami():
    C.reset_scene()
    C._materials.clear()
    M = mosque_mats()
    root = C.empty("SuruIHA_Yapi_UluCami")
    WX, YN, YQ, YS = 16.0, -32.0, 8.0, 32.0      # yarı genişlik; kuzey, kıble (cami/darüşşifa), güney duvarları
    HM, HD = 10.0, 11.4                         # cami ve darüşşifa beden duvarı
    EV, PITCH = 0.9, 12.0                       # saçak taşması, çatı eğimi
    main, roofs = [], []

    # beden duvarları (taraça z=0; dipleri döşemenin altına iner), pencere boşlukları oyulur
    cami = C.box("Cami", (2 * WX, YQ - YN, HM + 0.6), (0, (YN + YQ) / 2, (HM - 0.6) / 2), M["tas"])
    dar = C.box("Darussifa", (2 * WX, YS - YQ, HD + 0.6), (0, (YQ + YS) / 2, (HD - 0.6) / 2), M["tas"])
    walls = {"N": (0.0, lambda s: (s, YN)), "S": (math.pi, lambda s: (s, YS)),
             "W": (-math.pi / 2, lambda s: (-WX, s)), "E": (math.pi / 2, lambda s: (WX, s))}
    wins = [("N", -10.5, 5.2, 1.0, 1.3), ("N", 10.5, 5.2, 1.0, 1.3),
            ("W", -25.0, 5.2, 1.0, 1.3), ("W", -1.5, 5.2, 1.0, 1.3), ("E", -24.0, 5.2, 1.0, 1.3), ("E", -12.0, 5.2, 1.0, 1.3),
            ("W", 12.0, 4.6, 0.9, 1.2), ("W", 28.0, 4.6, 0.9, 1.2), ("W", 28.0, 8.6, 0.8, 1.0),
            ("E", 13.0, 4.6, 0.9, 1.2), ("E", 22.0, 4.6, 0.9, 1.2), ("E", 22.0, 8.6, 0.8, 1.0), ("E", 29.0, 8.6, 0.8, 1.0),
            ("S", -11.0, 4.4, 0.9, 1.2), ("S", -4.0, 4.4, 0.9, 1.2), ("S", 4.0, 4.4, 0.9, 1.2), ("S", 11.0, 4.4, 0.9, 1.2),
            ("S", -11.0, 8.6, 0.8, 1.0), ("S", -4.0, 8.6, 0.8, 1.0), ("S", 4.0, 8.6, 0.8, 1.0), ("S", 11.0, 8.6, 0.8, 1.0)]
    cut_m, cut_d = [], []
    for k, (wall, s, z, w, h) in enumerate(wins):
        rot, at = walls[wall]
        c, win = rect_window(f"Pen{k}", w, h, z, M)
        x, y = at(s)
        place(c, rot, (x, y, 0))
        place(win, rot, (x, y, 0))
        main.append(win)
        (cut_d if (y > YQ + 0.5 or wall == "S") else cut_m).append(c)
    cut(cami, C.join(cut_m, "Kesici_Cami"))
    cut(dar, C.join(cut_d, "Kesici_Darussifa"))
    main += [cami, dar]
    for sx in (-1, 1):
        main.append(C.box(f"Subasman_X{sx}", (0.4, YS - YN + 0.24, 0.6), (sx * (WX - 0.08), (YN + YS) / 2, 0.2), M["tas"]))
        main.append(C.box(f"Subasman_Y{sx}", (2 * WX - 0.4, 0.4, 0.6), (0, (YN if sx < 0 else YS) - sx * 0.08, 0.2), M["tas"]))
    # yağmur iniş boruları (saçaktan zemine, kelepçeli)
    pipes = [("N", -7.0), ("N", 7.5), ("N", 14.5), ("W", -19.5), ("W", 3.5), ("W", 30.5), ("E", -29.0), ("E", -6.0),
             ("E", 6.5), ("E", 17.5), ("E", 30.5), ("S", -14.5), ("S", 0.0), ("S", 14.5)]
    for k, (wall, s) in enumerate(pipes):
        rot, at = walls[wall]
        x, y = at(s)
        h = HD if (wall == "S" or (wall in "WE" and s > YQ)) else HM
        pp = [C.cyl(f"Boru{k}", 0.075, h - 0.35, (0, -0.17, (h - 0.35) / 2 + 0.05), M["demir"], verts=10),
              C.cyl(f"Boru{k}_Dirsek", 0.075, 0.5, (0, -0.42, h - 0.32), M["demir"], verts=10, rot=(math.pi / 2, 0, 0))]
        for b in range(int(h / 2.2)):
            pp.append(C.box(f"Boru{k}_Kelepce{b}", (0.2, 0.18, 0.05), (0, -0.09, 1.6 + b * 2.2), M["demir"]))
        main.append(place(C.join(pp, f"Boru{k}"), rot, (x, y, 0)))

    # taç kapılar
    main.append(place(north_portal(M), 0.0, (0, YN, 0)))
    main.append(place(west_portal(M), -math.pi / 2, (-WX, -10.0, 0)))
    main.append(place(hospital_portal(M), -math.pi / 2, (-WX, 20.0, 0)))
    main.append(place(shah_portal(M), math.pi / 2, (WX, 0.0, 0)))

    # örtü: kurşun kaplı kırma çatılar; ışıklık fenerleri; taş külahlar
    roofs += hip_roof("CamiCati", -WX - EV, WX + EV, YN - EV, YQ, HM + 0.02, PITCH, M)
    roofs += hip_roof("DarussifaCati", -WX - EV, WX + EV, YQ - EV, YS + EV, HD + 0.02, PITCH, M)
    main += lantern("CamiFener", 0.0, -14.0, 2.3, 12.9, 15.0, M)
    main += lantern("DarussifaFener", 0.0, 20.0, 2.0, 13.6, 15.6, M)
    main += stone_pyramid("MihrapKulah", 0.0, YQ - 5.2, 9.4, 9.0, 12.9, 1.1, 8.3, M)
    main += stone_pyramid("TurbeKulah", 10.0, YQ + 4.6, 6.2, 10.5, 13.6, 0.8, 5.2, M)

    # kuzeybatı köşesi: yuvarlak payanda (kurşun külahlı) ve minare
    bx, by = -WX, YN
    main.append(C.cyl("Payanda", 3.6, 7.6, (bx, by, 3.4), M["tas"], verts=64))
    main.append(C.cyl("Payanda_Subasman", 3.72, 0.6, (bx, by, 0.2), M["tas"], verts=64))
    roofs.append(C.cone("Payanda_Kulah", 3.98, 1.2, 0.95, (bx, by, 7.2 + 0.47), M["kursun"], verts=64))
    roofs.append(C.cyl("Payanda_Alin", 3.98, 0.2, (bx, by, 7.12), M["ahsap"], verts=64))
    main += minaret(M, -WX + 1.7, YN + 1.7)

    # taraça: batıda avlu, çevrede taş döşeme; altında istinat duvarı, kenarlarında korkuluk duvarı
    X0, X1, Y0, Y1 = -WX - 15.0, WX + 6.0, YN - 9.0, YS + 5.0
    pl = [C.box("Meydan_Doseme", (X1 - X0, Y1 - Y0, 0.3), ((X0 + X1) / 2, (Y0 + Y1) / 2, -0.13), M["doseme"]),
          C.box("Meydan_Istinat", (X1 - X0 + 0.2, Y1 - Y0 + 0.2, 7.0), ((X0 + X1) / 2, (Y0 + Y1) / 2, -0.28 - 3.5), M["meydan"])]
    for a, b, y in ((X0, -4.6, Y0), (4.6, X1, Y0)):
        pl.append(C.box(f"Korkuluk_K{a}", (b - a, 0.5, 0.75), ((a + b) / 2, y + 0.25, 0.375), M["meydan"]))
        pl.append(C.box(f"Korkuluk_KB{a}", (b - a + 0.1, 0.62, 0.1), ((a + b) / 2, y + 0.25, 0.8), M["tas"]))
    for x, y0_, y1_ in ((X0, Y0, -2.0), (X0, 6.0, Y1), (X1, Y0, Y1)):
        pl.append(C.box(f"Korkuluk_Y{x}{y0_}", (0.5, y1_ - y0_, 0.75), (x + (0.25 if x == X0 else -0.25), (y0_ + y1_) / 2, 0.375), M["meydan"]))
        pl.append(C.box(f"Korkuluk_YB{x}{y0_}", (0.62, y1_ - y0_, 0.1), (x + (0.25 if x == X0 else -0.25), (y0_ + y1_) / 2, 0.8), M["tas"]))
    for k in range(5):
        pl.append(C.box(f"Merdiven{k}", (9.2, 0.36, 0.2), (0, Y0 - 0.18 - 0.36 * k, -0.1 - 0.2 * k), M["meydan"]))

    for o in main + roofs + pl:
        o.parent = root
    bake_xforms(root)
    for o in root.children_recursive:
        if o.type == "MESH":
            uv_world(o)
    mirror_for_unity(root)
    body = C.join(main, "UluCami")
    C.join(roofs, "Catilar")
    C.join(pl, "Meydan")
    for o in root.children:
        o.parent = root
    remove_hidden(body, [o for o in root.children if o is not body and o.type == "MESH"])
    atlas_uv(body)
    C.stats(root)
    os.makedirs(TEX_OUT, exist_ok=True)
    bake_detail(body, os.path.join(TEX_OUT, "Yapi_UluCami_Detay.png"))
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_UluCami.fbx"), root)
    if BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)


# ---------------------------------------------------------------------------- kale
def crenels(name, length, thick, z, M, rnd, broken=0.25, width=0.9, gap=0.7, h=1.2):
    """Mazgallı siper dişleri (bir kısmı yıkık)."""
    parts = []
    x = -length / 2 + gap
    k = 0
    while x + width < length / 2:
        if rnd.random() > broken:
            hh = h * (0.55 + 0.45 * rnd.random()) if rnd.random() < 0.3 else h
            parts.append(C.box(f"{name}_{k}", (width, thick, hh), (x + width / 2, 0, z + hh / 2), M["castle"]))
        x += width + gap
        k += 1
    return parts


def castle_pieces():
    rnd = random.Random(1228)
    # yuvarlak burç: aşağı doğru genişleyen gövde, yıkık siper
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_KaleKule")
    parts = [C.cone("Kule_Etek", 5.2, 4.3, 4.0, (0, 0, -1.0), M["castle"], verts=28),
             C.cyl("Kule_Govde", 4.3, 9.0, (0, 0, 5.5), M["castle"], verts=28),
             C.cyl("Kule_Silme", 4.5, 0.4, (0, 0, 10.2), M["castle"], verts=28)]
    for k in range(14):
        if rnd.random() < 0.3:
            continue
        a = 2 * math.pi * k / 14
        hh = 1.3 if rnd.random() > 0.3 else 0.7
        parts.append(C.box(f"Kule_Dis{k}", (1.2, 0.8, hh), (math.cos(a) * 4.05, math.sin(a) * 4.05, 10.4 + hh / 2), M["castle"],
                           rot=(0, 0, a + math.pi / 2)))
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        parts.append(C.box(f"Kule_Mazgal{k}", (0.25, 0.4, 1.4), (math.cos(a) * 4.31, math.sin(a) * 4.31, 6.0 + k), M["black"],
                           rot=(0, 0, a + math.pi / 2)))
    C.join(parts, "Kule").parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_KaleKule.fbx"), root)

    # kare burç
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_KaleBurc")
    parts = [C.box("Burc_Etek", (8.6, 8.6, 4.0), (0, 0, -1.0), M["castle"]),
             C.box("Burc_Govde", (7.4, 7.4, 11.0), (0, 0, 6.5), M["castle"]),
             C.box("Burc_Silme", (7.8, 7.8, 0.4), (0, 0, 12.2), M["castle"])]
    for side in range(4):
        rot = side * math.pi / 2
        for c in crenels(f"Burc_Dis{side}", 7.4, 0.7, 12.4, M, rnd):
            place(c, rot, (math.cos(rot - math.pi / 2) * 3.35, math.sin(rot - math.pi / 2) * 3.35, 0))
            parts.append(c)
        parts.append(place(C.box(f"Burc_Mazgal{side}", (0.3, 0.2, 1.5), (0, -3.72, 7.5), M["black"]), rot, (0, 0, 0)))
    C.join(parts, "Burc").parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_KaleBurc.fbx"), root)

    # sur parçası: 12 m, kalın, dişleri yer yer yıkık; tabanı aşağı uzar (eğimde boşluk kalmasın)
    C.reset_scene()
    C._materials.clear()
    M = mats()
    root = C.empty("SuruIHA_Yapi_KaleSur")
    parts = [C.box("Sur_Govde", (12.4, 2.4, 11.0), (0, 0, 2.5), M["castle"]),
             C.box("Sur_Yuruyus", (12.4, 0.5, 1.0), (0, 1.0, 8.5), M["castle"])]
    parts += [place(c, 0.0, (0, -0.85, 0)) for c in crenels("Sur_Dis", 12.4, 0.7, 8.0, M, rnd, broken=0.3)]
    C.join(parts, "Sur").parent = root
    C.export_fbx(os.path.join(OUT, "SuruIHA_Yapi_KaleSur.fbx"), root)


# ---------------------------------------------------------------------------- Divriği evleri
def divrigi_house(idx, rnd):
    """Geleneksel Divriği evi: taş zemin kat, üstte ahşap karkas sıvalı kat ve ahşap konsollu cumba,
    çok pencereli cephe, geniş saçaklı kırma kiremit çatı (ya da toprak dam)."""
    C.reset_scene()
    C._materials.clear()
    M = mats()
    plasters = [("MAT_Plaster_A", (0.72, 0.66, 0.55)), ("MAT_Plaster_B", (0.78, 0.76, 0.72)),
                ("MAT_Plaster_C", (0.70, 0.55, 0.40))]
    pm = C.mat(plasters[idx % 3][0], plasters[idx % 3][1], rough=0.88)
    root = C.empty(f"SuruIHA_Yapi_DivrigiEv_{idx}")
    w, d = rnd.uniform(9, 12), rnd.uniform(7.5, 9.5)
    g, u = 3.0, 3.0                           # zemin ve üst kat yüksekliği
    parts = [C.box("Temel", (w + 0.4, d + 0.4, 3.0), (0, 0, -1.2), M["castle"]),
             C.box("ZeminKat", (w, d, g), (0, 0, g / 2 + 0.3), M["castle"]),
             C.box("UstKat", (w + 0.3, d + 0.3, u), (0, 0, g + 0.3 + u / 2), pm),
             C.box("KatSilmesi", (w + 0.5, d + 0.5, 0.18), (0, 0, g + 0.3), M["wood"])]
    # ahşap karkas izleri (dikmeler)
    for k in range(int(w // 1.6) + 1):
        x = -w / 2 - 0.15 + k * (w + 0.3) / int(w // 1.6)
        parts.append(C.box(f"Dikme{k}", (0.12, d + 0.36, u), (x, 0, g + 0.3 + u / 2), M["wood"]))
    # cumba: ön cephede, konsollar üstünde
    cw = rnd.uniform(3.2, 4.4)
    cx = rnd.uniform(-w / 2 + cw / 2 + 0.6, w / 2 - cw / 2 - 0.6)
    parts.append(C.box("Cumba", (cw, 1.0, u - 0.2), (cx, -d / 2 - 0.65, g + 0.3 + u / 2), pm))
    for k in range(3):
        parts.append(C.box(f"Konsol{k}", (0.14, 0.9, 0.5), (cx - cw / 2 + 0.3 + k * (cw - 0.6) / 2, -d / 2 - 0.5, g + 0.05), M["wood"],
                           rot=(math.radians(-30), 0, 0)))
    nwin = max(3, int(cw // 0.9))
    for k in range(nwin):
        x = cx - cw / 2 + (k + 0.5) * cw / nwin
        parts.append(C.box(f"CumbaPen{k}", (cw / nwin - 0.25, 0.06, 1.35), (x, -d / 2 - 1.16, g + 0.3 + 1.55), M["glass"]))
        parts.append(C.box(f"CumbaKasa{k}", (cw / nwin - 0.1, 0.05, 1.5), (x, -d / 2 - 1.14, g + 0.3 + 1.55), M["frame"]))
    for side in (-1, 1):
        for k in range(int(w // 2.4)):
            x = -w / 2 + (k + 0.5) * w / int(w // 2.4)
            if side < 0 and abs(x - cx) < cw / 2 + 0.3:
                continue
            parts.append(C.box(f"Pen{side}{k}", (0.8, 0.06, 1.2), (x, side * (d / 2 + 0.16), g + 0.3 + 1.6), M["glass"]))
            parts.append(C.box(f"Kasa{side}{k}", (0.95, 0.05, 1.35), (x, side * (d / 2 + 0.15), g + 0.3 + 1.6), M["frame"]))
            if rnd.random() < 0.5:
                parts.append(C.box(f"ZPen{side}{k}", (0.6, 0.06, 0.8), (x, side * (d / 2 + 0.01), 1.9), M["black"]))
    parts.append(C.box("Kapi", (1.3, 0.12, 2.3), (-cx * 0.5, -d / 2 - 0.02, 1.45), M["door"]))
    parts.append(C.box("KapiSundurma", (2.0, 1.1, 0.1), (-cx * 0.5, -d / 2 - 0.5, 2.9), M["wood"], rot=(math.radians(-10), 0, 0)))
    body = C.join(parts, "Ev")
    body.parent = root
    top = g + 0.3 + u
    if idx == 3:
        # toprak damlı ev: düz dam, ahşap saçak kirişleri
        C.box("Dam", (w + 0.9, d + 0.9, 0.35), (0, 0, top + 0.17), M["earth"], root)
        C.box("DamSacak", (w + 1.0, d + 1.0, 0.12), (0, 0, top + 0.02), M["wood"], root)
    else:
        bm = bmesh.new()
        W, D, oh = (w + 0.3) / 2 + 0.8, (d + 0.3) / 2 + 0.8, 0.0
        h = min(w, d) * 0.22
        ridge = max(0.0, W - D)
        cs = [Vector((-W, -D, top)), Vector((W, -D, top)), Vector((W, D, top)), Vector((-W, D, top))]
        v = [bm.verts.new(p) for p in cs]
        a, b = bm.verts.new((-ridge, 0, top + h)), bm.verts.new((ridge, 0, top + h))
        bm.faces.new((v[0], v[1], b, a))
        bm.faces.new((v[1], v[2], b))
        bm.faces.new((v[2], v[3], a, b))
        bm.faces.new((v[3], v[0], a))
        bm.faces.new(list(reversed(v)))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        C.mesh_object("Cati", bm, M["roof"], root, smooth=False)
        C.box("Baca", (0.5, 0.5, 1.4), (w * 0.28, d * 0.12, top + h * 0.6 + 0.4), pm, root)
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Yapi_DivrigiEv_{idx}.fbx"), root)


if __name__ == "__main__":
    only = [a for a in ARGS[1:] if not a.endswith(".blend")]
    if not only or "cami" in only:
        ulu_cami()
    if not only or "kale" in only:
        castle_pieces()
    if not only or "ev" in only:
        rnd = random.Random(1229)
        for i in range(4):
            divrigi_house(i, rnd)
