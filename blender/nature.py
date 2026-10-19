"""Arazi bitki örtüsü ve kayalar (Orta Anadolu: karaçam, meşe, çalı, kaya çıkıntıları).

    blender -b -P blender/nature.py -- <çıktı_klasörü>

Ağaçlar oyun endüstrisindeki gibi kurulur: gövde/dallar gerçek geometri, yapraklar ise
alfa kesimli "kart"lar (Tex_CamIgne / Tex_MeseYaprak dokuları). Kartların normalleri taç
merkezinden dışa doğru ayarlanır, böylece taç hacimli ve yumuşak aydınlanır.
Her ağaç iki ayrıntı seviyesiyle gelir: <ad>_LOD0 (yakın) ve <ad>_LOD1 (uzak);
Unity bu isimlerden LODGroup'u kendisi kurar.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------------- geometri kurucu
class TreeBuilder:
    """Tek bir bmesh'e gövde, dal ve yaprak kartı ekler. Malzeme 0 = kabuk, 1 = yaprak."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.leaf_faces = []

    def _face(self, verts, uvs, mat):
        f = self.bm.faces.new(verts)
        f.material_index = mat
        for loop, uv in zip(f.loops, uvs):
            loop[self.uv].uv = uv
        if mat == 1:
            self.leaf_faces.append(f)
        return f

    def tube(self, path, radii, sides=8, uv_repeat=1.0):
        """Yol boyunca (nokta listesi) daralan boru; kabuk UV'si silindirik."""
        rings = []
        length = 0.0
        for k, p in enumerate(path):
            if k > 0:
                length += (p - path[k - 1]).length
            d = (path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]).normalized()
            side = d.orthogonal().normalized()
            up = d.cross(side).normalized()
            ring = []
            for j in range(sides + 1):
                a = j / sides * math.tau
                off = (side * math.cos(a) + up * math.sin(a)) * radii[k]
                ring.append((self.bm.verts.new(p + off), (j / sides * uv_repeat, length / 1.2)))
            rings.append(ring)
        for r0, r1 in zip(rings[:-1], rings[1:]):
            for j in range(sides):
                self._face([r0[j][0], r0[j + 1][0], r1[j + 1][0], r1[j][0]],
                           [r0[j][1], r0[j + 1][1], r1[j + 1][1], r1[j][1]], 0)

    def card(self, base, direction, size, roll, aspect=1.0):
        """Tabanı `base`ta, `direction` yönünde uzanan kare kart (+ 90° çaprazı)."""
        d = direction.normalized()
        s0 = d.orthogonal().normalized()
        s0 = Matrix.Rotation(roll, 3, d) @ s0
        for s in (s0, d.cross(s0).normalized()):
            w = s * size * aspect * 0.5
            a, b = base - w, base + w
            c, e = b + d * size, a + d * size
            v = [self.bm.verts.new(x) for x in (a, b, c, e)]
            self._face(v, [(0, 0), (1, 0), (1, 1), (0, 1)], 1)

    def finish(self, name, mats, center, squash=0.75):
        o = C.mesh_object(name, self.bm, None, smooth=False)
        for m in mats:
            o.data.materials.append(m)
        # Yaprak normalleri: taç merkezinden dışa (hacimli aydınlanma), kabuk: geometrik
        me = o.data
        me.update()
        normals = []
        for poly in me.polygons:
            for li in poly.loop_indices:
                vco = me.vertices[me.loops[li].vertex_index].co
                if poly.material_index == 1:
                    n = Vector(((vco.x - center.x), (vco.y - center.y), (vco.z - center.z) * squash))
                    n = (n.normalized() * 0.8 + Vector((0, 0, 0.45))).normalized()
                else:
                    n = poly.normal.copy()
                normals.append(n)
        for poly in me.polygons:
            poly.use_smooth = True
        try:
            me.normals_split_custom_set(normals)
        except Exception as e:   # eski Blender sürümleri
            print("özel normal ayarlanamadı:", e)
        return o


def curve(a, b, sag, n=5):
    """a'dan b'ye hafif sarkan dal yolu."""
    pts = []
    for k in range(n):
        t = k / (n - 1)
        p = a.lerp(b, t)
        p.z -= sag * math.sin(math.pi * t) * 0.5 + sag * t * t * 0.5
        pts.append(p)
    return pts


def trunk_path(h, bend, seed, n=10):
    return [Vector((bend * math.sin(u * 2.1 + seed) * u, bend * 0.6 * math.cos(u * 1.7 + seed * 2) * u, h * u))
            for u in (k / (n - 1) for k in range(n))]


# ---------------------------------------------------------------------- karaçam
def pine(idx, h, mature):
    C.reset_scene()
    C._materials.clear()
    bark = C.mat("MAT_BarkPine", (0.3, 0.22, 0.17), rough=0.95)
    needles = C.mat("MAT_Needles", (0.12, 0.2, 0.09), rough=0.85)
    root = C.empty(f"SuruIHA_Tree_Pine_{idx}")
    rnd = random.Random(100 + idx)
    bend = h * 0.035

    def build(lod):
        tb = TreeBuilder()
        tp = trunk_path(h, bend, idx, 10 if lod == 0 else 4)
        r0 = h * 0.024
        tb.tube(tp, [r0 * (1.35 if k == 0 else 1.0) * (1 - 0.85 * k / (len(tp) - 1)) + 0.02 for k in range(len(tp))],
                sides=10 if lod == 0 else 6, uv_repeat=2)
        start = 0.5 if mature else 0.25
        whorls = (10 if mature else 12) if lod == 0 else 5
        for w in range(whorls):
            u = start + (0.96 - start) * w / (whorls - 1)
            base = tp[0].lerp(tp[-1], u) + Vector((bend * math.sin(u * 2.1 + idx) * u, 0, 0)) * 0
            base = Vector((bend * math.sin(u * 2.1 + idx) * u, bend * 0.6 * math.cos(u * 1.7 + idx * 2) * u, h * u))
            if mature:   # yaşlı karaçam: düzleşen, yayvan tepe
                rel = (u - start) / (1 - start)
                L = h * (0.16 + 0.2 * math.sin(min(1.0, rel * 1.1) * math.pi * 0.9))
            else:
                L = h * 0.32 * (1 - u) ** 0.8 + h * 0.04
            n_br = rnd.randint(4, 6) if lod == 0 else 4
            phase = rnd.random() * math.tau
            for b in range(n_br):
                a = phase + b * math.tau / n_br + rnd.uniform(-0.3, 0.3)
                up = (0.45 if mature else 0.15) + rnd.uniform(-0.12, 0.12)
                d = Vector((math.cos(a), math.sin(a), up)).normalized()
                tip = base + d * L
                path = curve(base, tip, L * (0.08 if mature else 0.2), 4)
                if lod == 0:
                    tb.tube(path, [h * 0.006 + L * 0.018 * (1 - k / 4) for k in range(4)], sides=5)
                # İğne kümeleri: dalın dış yarısında, uçlarda yoğun ve yukarı kalkık (mum gibi)
                n_cards = (6 if L > h * 0.12 else 4) if lod == 0 else 2
                for c in range(n_cards):
                    t = 0.4 + 0.6 * ((c + 1) / n_cards) ** 0.7
                    p = path[0].lerp(path[-1], t) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * L * 0.06
                    cdir = (d * 0.55 + Vector((0, 0, 0.85)) +
                            Vector((rnd.uniform(-0.35, 0.35), rnd.uniform(-0.35, 0.35), 0))).normalized()
                    size = (L * rnd.uniform(0.28, 0.4) + h * 0.03) * (1.7 if lod else 1.0)
                    tb.card(p - cdir * size * 0.3, cdir, size, rnd.random() * math.pi)
        # Tepe
        top = tp[-1]
        for k in range(4 if lod == 0 else 2):
            cdir = Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 1)).normalized()
            tb.card(top - cdir * h * 0.08, cdir, h * 0.16, rnd.random() * math.pi)
        center = Vector((0, 0, h * (0.78 if mature else 0.6)))
        o = tb.finish(f"Pine{idx}_LOD{lod}", [bark, needles], center)
        o.parent = root

    build(0)
    build(1)
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Tree_Pine_{idx}.fbx"), root)


# ---------------------------------------------------------------------- meşe
def oak(idx, h):
    C.reset_scene()
    C._materials.clear()
    bark = C.mat("MAT_BarkOak", (0.25, 0.23, 0.2), rough=0.95)
    leaves = C.mat("MAT_Leaves", (0.15, 0.24, 0.07), rough=0.8)
    root = C.empty(f"SuruIHA_Tree_Oak_{idx}")
    rnd = random.Random(200 + idx)

    limbs = []
    fork = Vector((0, 0, h * 0.38))
    for k in range(rnd.randint(3, 5)):
        a = k * math.tau / 4 + rnd.uniform(-0.5, 0.5)
        d = Vector((math.cos(a) * 0.8, math.sin(a) * 0.8, 1.0)).normalized()
        end = fork + d * h * rnd.uniform(0.32, 0.42)
        subs = []
        for s in range(4):
            a2 = a + rnd.uniform(-1.3, 1.3)
            d2 = Vector((math.cos(a2), math.sin(a2), rnd.uniform(0.1, 0.8))).normalized()
            mid = fork.lerp(end, rnd.uniform(0.45, 1.0))
            subs.append((mid, mid + d2 * h * rnd.uniform(0.14, 0.26)))
        limbs.append((end, subs))
    center = Vector((0, 0, h * 0.68))

    def build(lod):
        tb = TreeBuilder()
        trunk = trunk_path(h * 0.4, h * 0.04, idx, 5 if lod == 0 else 3)
        tb.tube(trunk, [h * 0.055 * (1.3 if k == 0 else 1) * (1 - 0.3 * k / (len(trunk) - 1)) for k in range(len(trunk))],
                sides=10 if lod == 0 else 6, uv_repeat=2)
        for end, subs in limbs:
            tb.tube(curve(fork, end, h * 0.02, 4), [h * 0.03, h * 0.025, h * 0.02, h * 0.012], sides=7 if lod == 0 else 4)
            for (a, b) in subs:
                if lod == 0:
                    tb.tube([a, a.lerp(b, 0.5), b], [h * 0.012, h * 0.008, h * 0.004], sides=5)
                n_cards = 5 if lod == 0 else 2
                for c in range(n_cards):
                    p = a.lerp(b, 0.4 + 0.6 * rnd.random()) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 1))) * h * 0.05
                    out = (p - center)
                    cdir = (out.normalized() + Vector((0, 0, 0.6)) + Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0))).normalized()
                    size = h * rnd.uniform(0.2, 0.28) * (1.7 if lod else 1.0)
                    tb.card(p - cdir * size * 0.35, cdir, size, rnd.random() * math.pi)
            # Kol ucunda da küme
            for c in range(4 if lod == 0 else 1):
                cdir = ((end - center).normalized() + Vector((0, 0, 0.8))).normalized()
                size = h * 0.25 * (1.5 if lod else 1.0)
                tb.card(end - cdir * size * 0.3 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * h * 0.04, cdir, size, rnd.random() * math.pi)
        o = tb.finish(f"Oak{idx}_LOD{lod}", [bark, leaves], center, squash=0.9)
        o.parent = root

    build(0)
    build(1)
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Tree_Oak_{idx}.fbx"), root)


# ---------------------------------------------------------------------- çalı
def shrub(idx, h):
    C.reset_scene()
    C._materials.clear()
    bark = C.mat("MAT_BarkOak", (0.25, 0.23, 0.2), rough=0.95)
    leaves = C.mat("MAT_Leaves", (0.15, 0.24, 0.07), rough=0.8)
    root = C.empty(f"SuruIHA_Shrub_{idx}")
    rnd = random.Random(400 + idx)
    tb = TreeBuilder()
    for k in range(14):
        a = rnd.random() * math.tau
        r = rnd.uniform(0, h * 0.5)
        p = Vector((math.cos(a) * r, math.sin(a) * r, rnd.uniform(-0.1, 0.3) * h))
        cdir = Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 1)).normalized()
        tb.card(p, cdir, h * rnd.uniform(0.7, 1.0), rnd.random() * math.pi)
    o = tb.finish(f"Shrub{idx}_LOD0", [bark, leaves], Vector((0, 0, 0)), squash=1.2)
    o.parent = root
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Shrub_{idx}.fbx"), root)


# ---------------------------------------------------------------------- ot öbeği
def grass(idx, mat_name, color):
    """Üç çapraz dikey karttan ot öbeği (arazi detay mesh'i). Normaller yukarı bakar,
    böylece zeminle aynı tonda aydınlanır."""
    C.reset_scene()
    C._materials.clear()
    m = C.mat(mat_name, color, rough=0.85)
    tb = TreeBuilder()
    w, h = 0.9, 0.55
    for k in range(3):
        a = k * math.pi / 3
        d = Vector((math.cos(a), math.sin(a), 0)) * w / 2
        vs = [tb.bm.verts.new(p) for p in (-d + Vector((0, 0, -0.03)), d + Vector((0, 0, -0.03)),
                                          d + Vector((0, 0, h)), -d + Vector((0, 0, h)))]
        tb._face(vs, [(0, 0), (1, 0), (1, 1), (0, 1)], 1)
    o = tb.finish(f"Grass{idx}", [m, m], Vector((0, 0, -4.0)), squash=1.0)
    root = C.empty(f"SuruIHA_Grass_{idx}")
    o.parent = root
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Grass_{idx}.fbx"), root)


# ---------------------------------------------------------------------- kaya
def displace(o, amount, scale, seed):
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    for v in o.data.vertices:
        v.co += v.normal * noise.noise(v.co * scale + off) * amount


def rock(idx, size):
    C.reset_scene()
    C._materials.clear()
    stone = C.mat("MAT_Rock", (0.3, 0.29, 0.27), rough=0.9)
    rnd = random.Random(300 + idx)
    root = C.empty(f"SuruIHA_Rock_{idx}")
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=size)
    r = bpy.context.active_object
    r.scale = (1.0 + rnd.random() * 0.5, 0.8 + rnd.random() * 0.4, 0.5 + rnd.random() * 0.25)
    C.apply_transform(r)
    displace(r, size * 0.35, 1.3 / size, idx + 30)
    displace(r, size * 0.1, 4.0 / size, idx + 60)
    step = size * 0.18
    for v in r.data.vertices:          # tortul tabakalanma ve gömülü taban
        if v.co.z > 0:
            v.co.z = v.co.z * 0.6 + round(v.co.z / step) * step * 0.4
        if v.co.z < -size * 0.15:
            v.co.z = -size * 0.15
    # Üstten izdüşüm UV (kaya dokusu için)
    me = r.data
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (co.x / 3.0 + co.z / 6.0, co.y / 3.0 + co.z / 4.0)
    r.name = f"Rock{idx}_LOD0"
    r.data.name = r.name
    r.data.materials.append(stone)
    C.shade_smooth(r, 40)
    r.parent = root
    C.export_fbx(os.path.join(OUT, f"SuruIHA_Rock_{idx}.fbx"), root)


for i, (h, mature) in enumerate(((12.0, False), (16.0, True), (9.0, False), (14.0, True))):
    pine(i, h, mature)
for i, h in enumerate((8.0, 10.0, 6.5)):
    oak(i, h)
for i, h in enumerate((1.4, 2.0, 1.0)):
    shrub(i, h)
for i, s in enumerate((1.2, 2.2, 3.5, 1.6)):
    rock(i, s)
grass(0, "MAT_GrassGreen", (0.25, 0.32, 0.1))
grass(1, "MAT_GrassDry", (0.55, 0.47, 0.28))
print("Doğa modelleri tamam")
