"""Prosedürel doku üretici (numpy). Hepsi dikişsiz (tileable) ve fotoğraf benzeri olacak şekilde
katmanlı gürültü, Voronoi hücreleri ve fırça darbeleriyle üretilir.

    python tools/gen_textures.py <çıktı_klasörü>

Üretilenler:
  Arazi : Ter_Cimen, Ter_Bozkir, Ter_Tarla, Ter_Aniz, Ter_Kaya, Ter_Cakil  (_Renk.png + _Normal.png)
  Ağaç  : Tex_CamIgne.png, Tex_MeseYaprak.png (RGBA, alfa kesim), Tex_KabukCam / Tex_KabukMese (+ _Normal)
"""
import os
import sys

import numpy as np
from matplotlib import image as mpimg

OUT = sys.argv[1] if len(sys.argv) > 1 else "textures"
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------------- gürültü
def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def perlin(x, y, px, py, seed):
    """Periyodik gradyan gürültüsü. x, y kafes birimiyle; px, py periyot (tam sayı)."""
    rng = np.random.default_rng(seed)
    ang = rng.uniform(0, 2 * np.pi, (py, px))
    gx, gy = np.cos(ang), np.sin(ang)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    x0m, y0m = x0 % px, y0 % py
    x1m, y1m = (x0 + 1) % px, (y0 + 1) % py

    def dot(ix, iy, dx, dy):
        return gx[iy, ix] * dx + gy[iy, ix] * dy

    n00 = dot(x0m, y0m, fx, fy)
    n10 = dot(x1m, y0m, fx - 1, fy)
    n01 = dot(x0m, y1m, fx, fy - 1)
    n11 = dot(x1m, y1m, fx - 1, fy - 1)
    u, v = _fade(fx), _fade(fy)
    return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v   # ~[-0.7, 0.7]


def grid(n, m=None):
    m = m or n
    y, x = np.mgrid[0:m, 0:n]
    return x / n, y / m       # [0,1)


def fbm(u, v, base, octaves, seed, aniso=(1, 1), warp=None):
    """u, v in [0,1). base = en kaba periyot. Sonuç ~[0,1]."""
    if warp is not None:
        u = u + warp[0]
        v = v + warp[1]
    s, a, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        px, py = base * aniso[0] * 2 ** o, base * aniso[1] * 2 ** o
        s = s + a * perlin(u * px, v * py, px, py, seed + o * 101)
        norm += a
        a *= 0.5
    return np.clip(s / norm * 1.4 + 0.5, 0, 1)


def voronoi(u, v, cells, seed, aniso=(1, 1)):
    """Periyodik Voronoi: F1, F2 (hücre birimi) ve hücre kimliği."""
    cx, cy = cells * aniso[0], cells * aniso[1]
    rng = np.random.default_rng(seed)
    jit = rng.random((cy, cx, 2))
    X, Y = u * cx, v * cy
    ix, iy = np.floor(X).astype(int), np.floor(Y).astype(int)
    f1 = np.full(X.shape, 9.0)
    f2 = np.full(X.shape, 9.0)
    cid = np.zeros(X.shape, int)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx, ny = ix + dx, iy + dy
            j = jit[ny % cy, nx % cx]
            px, py = nx + j[..., 0], ny + j[..., 1]
            d = np.hypot(X - px, Y - py)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d))
            cid = np.where(closer, (ny % cy) * cx + (nx % cx), cid)
            f1 = np.where(closer, d, f1)
    return f1, f2, cid


def hash01(ids, seed):
    rng = np.random.default_rng(seed)
    table = rng.random(int(ids.max()) + 1)
    return table[ids]


def normal_from_height(h, strength):
    dx = np.roll(h, -1, 1) - np.roll(h, 1, 1)
    dy = np.roll(h, -1, 0) - np.roll(h, 1, 0)
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(h)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / l * 0.5 + 0.5, ny / l * 0.5 + 0.5, nz / l * 0.5 + 0.5], -1)


def lerp(a, b, t):
    t = np.asarray(t)[..., None]
    return np.asarray(a) * (1 - t) + np.asarray(b) * t


def save(name, rgb, alpha=None):
    rgb = np.clip(rgb, 0, 1)
    if alpha is not None:
        rgb = np.concatenate([rgb, np.clip(alpha, 0, 1)[..., None]], -1)
    mpimg.imsave(os.path.join(OUT, name + ".png"), rgb.astype(np.float32))
    print("doku:", name)


def strokes(img, hmap, n, length, width, colors, seed, angle=None, wrap=True, tip=None):
    """Kısa fırça darbeleri (ot yaprağı, saman, iğne). Dikişsiz için kenardan sarar."""
    H, W = img.shape[:2]
    rng = np.random.default_rng(seed)
    for k in range(n):
        x0, y0 = rng.uniform(0, W), rng.uniform(0, H)
        L = rng.uniform(*length)
        a = rng.uniform(0, 2 * np.pi) if angle is None else angle + rng.normal(0, 0.35)
        x1, y1 = x0 + np.cos(a) * L, y0 + np.sin(a) * L
        w = rng.uniform(*width)
        c = np.asarray(colors[rng.integers(len(colors))]) * rng.uniform(0.85, 1.15)
        xa, xb = int(min(x0, x1) - w - 1), int(max(x0, x1) + w + 2)
        ya, yb = int(min(y0, y1) - w - 1), int(max(y0, y1) + w + 2)
        yy, xx = np.mgrid[ya:yb, xa:xb]
        dx, dy = x1 - x0, y1 - y0
        t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / (dx * dx + dy * dy + 1e-9), 0, 1)
        d = np.hypot(xx - (x0 + t * dx), yy - (y0 + t * dy))
        ww = w * (1 - 0.7 * t)                         # uca doğru incelir
        cov = np.clip(ww - d + 0.5, 0, 1)
        if not cov.any():
            continue
        col = c if tip is None else c * (1 - t[..., None]) + np.asarray(tip) * t[..., None]
        ys, xs = (yy % H, xx % W) if wrap else (np.clip(yy, 0, H - 1), np.clip(xx, 0, W - 1))
        img[ys, xs] = img[ys, xs] * (1 - cov[..., None]) + col * cov[..., None]
        hmap[ys, xs] = np.maximum(hmap[ys, xs], cov * (0.6 + 0.4 * t))


# ---------------------------------------------------------------------- arazi
N = 1024


def ter_grass():
    u, v = grid(N)
    big = fbm(u, v, 3, 4, 1)
    mid = fbm(u, v, 12, 4, 2)
    base = lerp((0.20, 0.26, 0.10), (0.33, 0.38, 0.15), big)
    base = lerp(base, (0.30, 0.25, 0.14), np.clip((mid - 0.62) * 3, 0, 1) * 0.6)   # toprak lekeleri
    h = mid * 0.3
    img = base.copy()
    cols = [(0.22, 0.33, 0.10), (0.30, 0.40, 0.13), (0.38, 0.44, 0.17), (0.17, 0.26, 0.08), (0.45, 0.45, 0.22)]
    strokes(img, h, 26000, (6, 18), (0.7, 1.4), cols, 3, tip=(0.55, 0.55, 0.3))
    img *= (0.85 + 0.3 * fbm(u, v, 32, 3, 4))[..., None]
    save("Ter_Cimen_Renk", img)
    save("Ter_Cimen_Normal", normal_from_height(h, 3.0))


def ter_steppe():
    u, v = grid(N)
    big = fbm(u, v, 3, 4, 11)
    base = lerp((0.42, 0.35, 0.21), (0.58, 0.50, 0.32), big)
    soil = np.clip((fbm(u, v, 10, 4, 12) - 0.6) * 4, 0, 1)
    base = lerp(base, (0.36, 0.28, 0.19), soil * 0.8)
    h = fbm(u, v, 20, 3, 13) * 0.2
    img = base.copy()
    cols = [(0.62, 0.54, 0.34), (0.70, 0.62, 0.40), (0.50, 0.43, 0.27), (0.42, 0.40, 0.22), (0.36, 0.38, 0.18)]
    strokes(img, h, 22000, (8, 22), (0.6, 1.2), cols, 14, tip=(0.78, 0.72, 0.5))
    # Küçük taşlar
    f1, f2, cid = voronoi(u, v, 48, 15)
    pebble = (f1 < 0.18) & (hash01(cid, 16) > 0.82)
    img = np.where(pebble[..., None], lerp((0.45, 0.43, 0.40), (0.62, 0.6, 0.56), hash01(cid, 17)), img)
    h = np.where(pebble, h + (0.18 - f1) * 3, h)
    save("Ter_Bozkir_Renk", img)
    save("Ter_Bozkir_Normal", normal_from_height(h, 3.0))


def ter_plowed():
    u, v = grid(N)
    warp = (fbm(u, v, 4, 3, 21) - 0.5) * 0.02
    furrow = 0.5 + 0.5 * np.sin((v + warp) * 2 * np.pi * 20)
    f1, f2, cid = voronoi(u, v, 64, 22)
    clod = np.clip(1 - f1 * 1.6, 0, 1) * (0.5 + 0.5 * hash01(cid, 23))
    h = furrow * 0.6 + clod * 0.5 + fbm(u, v, 24, 3, 24) * 0.3
    base = lerp((0.17, 0.12, 0.08), (0.36, 0.27, 0.19), np.clip(h * 0.9, 0, 1))
    base = lerp(base, (0.42, 0.33, 0.23), fbm(u, v, 3, 3, 25) * 0.5)
    img = base.copy()
    strokes(img, h, 1800, (5, 14), (0.6, 1.0), [(0.55, 0.47, 0.30), (0.48, 0.42, 0.26)], 26)
    save("Ter_Tarla_Renk", img)
    save("Ter_Tarla_Normal", normal_from_height(h, 4.0))


def ter_stubble():
    u, v = grid(N)
    big = fbm(u, v, 3, 3, 31)
    soil = lerp((0.40, 0.32, 0.21), (0.50, 0.41, 0.27), big)
    img = soil.copy()
    h = fbm(u, v, 16, 3, 32) * 0.2
    cols = [(0.78, 0.66, 0.40), (0.85, 0.74, 0.47), (0.70, 0.58, 0.34)]
    strokes(img, h, 16000, (10, 26), (0.6, 1.1), cols, 33, angle=0.0)          # yatık saman
    rows = 24
    rng = np.random.default_rng(34)
    stub = np.zeros((N, N))
    for r in range(rows):                                                      # anız sıraları
        y = (r + 0.5) / rows * N
        for k in range(110):
            x = rng.uniform(0, N)
            yy = int(y + rng.normal(0, 2.5)) % N
            xx = int(x) % N
            stub[yy, xx] = 1
    from scipy.ndimage import maximum_filter, gaussian_filter
    stub = gaussian_filter(maximum_filter(stub, 4, mode="wrap"), 1.2, mode="wrap")
    stub = np.clip(stub * 3, 0, 1)
    img = lerp(img, (0.88, 0.80, 0.55), stub)
    h = h + stub * 0.8
    save("Ter_Aniz_Renk", img)
    save("Ter_Aniz_Normal", normal_from_height(h, 3.0))


def ter_rock():
    u, v = grid(N)
    warp = ((fbm(u, v, 3, 4, 41) - 0.5) * 0.15, (fbm(u, v, 3, 4, 42) - 0.5) * 0.15)
    strata = 0.5 + 0.5 * np.sin((v + warp[1] + 0.3 * warp[0]) * 2 * np.pi * 6)
    wu, wv = u + warp[0] * 0.6, v + warp[1] * 0.6
    f1, f2, cid = voronoi(wu % 1.0, wv % 1.0, 4, 43)
    crack = np.clip((f2 - f1) * 30, 0, 1)            # ince, seyrek çatlaklar
    n = fbm(u, v, 8, 6, 44)
    h = n * 0.7 + strata * 0.25 + crack * 0.2
    base = lerp((0.30, 0.29, 0.27), (0.56, 0.54, 0.50), np.clip(n * 0.7 + strata * 0.3, 0, 1))
    base = base * (0.94 + 0.12 * hash01(cid, 45))[..., None]
    base = lerp((0.18, 0.17, 0.16), base, 0.55 + 0.45 * crack)
    lichen = np.clip((fbm(u, v, 14, 4, 46) - 0.68) * 5, 0, 1)
    base = lerp(base, (0.55, 0.55, 0.35), lichen * 0.6)
    save("Ter_Kaya_Renk", base)
    save("Ter_Kaya_Normal", normal_from_height(h, 5.0))


def ter_gravel():
    u, v = grid(N)
    f1, f2, cid = voronoi(u, v, 90, 51)
    stone = np.clip(1 - f1 * 1.4, 0, 1)
    edge = np.clip((f2 - f1) * 6, 0, 1)
    tone = hash01(cid, 52)
    base = lerp((0.44, 0.41, 0.36), (0.66, 0.62, 0.55), tone)
    base = lerp((0.25, 0.22, 0.18), base, edge)
    dust = fbm(u, v, 4, 4, 53)
    base = lerp(base, (0.58, 0.52, 0.42), dust * 0.45)
    h = stone * edge * 0.8 + dust * 0.2
    save("Ter_Cakil_Renk", base)
    save("Ter_Cakil_Normal", normal_from_height(h, 4.0))


# ---------------------------------------------------------------------- kabuk
def bark_pine():
    u, v = grid(512, 1024)
    f1, f2, cid = voronoi(u, v, 6, 61, aniso=(1, 3))
    plate = np.clip((f2 - f1) * 5, 0, 1)
    n = fbm(u, v, 6, 5, 62, aniso=(1, 2))
    tone = hash01(cid, 63)
    base = lerp((0.30, 0.20, 0.15), (0.48, 0.35, 0.27), tone * 0.6 + n * 0.4)   # karaçam: kırmızımsı plakalar
    base = lerp((0.08, 0.06, 0.05), base, plate)
    base = lerp(base, (0.36, 0.34, 0.31), np.clip((n - 0.6) * 3, 0, 1) * 0.5)
    h = plate * 0.8 + n * 0.3
    save("Tex_KabukCam", base)
    save("Tex_KabukCam_Normal", normal_from_height(h, 5.0))


def bark_oak():
    u, v = grid(512, 1024)
    warp = ((fbm(u, v, 4, 3, 71) - 0.5) * 0.08, 0)
    ridge = np.abs(np.sin((u + warp[0]) * 2 * np.pi * 9))
    n = fbm(u, v, 5, 5, 72, aniso=(1, 3))
    h = ridge ** 0.5 * 0.7 + n * 0.4
    base = lerp((0.12, 0.10, 0.08), (0.40, 0.37, 0.32), np.clip(h, 0, 1))
    save("Tex_KabukMese", base)
    save("Tex_KabukMese_Normal", normal_from_height(h, 5.0))


# ---------------------------------------------------------------------- yaprak kartları
def card_canvas(n=1024):
    return np.zeros((n, n, 3)), np.zeros((n, n))


def draw_segment(img, alpha, p0, p1, w0, w1, col, col1=None):
    H, W = alpha.shape
    x0, y0 = p0
    x1, y1 = p1
    m = max(w0, w1) + 2
    xa, xb = int(max(0, min(x0, x1) - m)), int(min(W, max(x0, x1) + m))
    ya, yb = int(max(0, min(y0, y1) - m)), int(min(H, max(y0, y1) + m))
    if xb <= xa or yb <= ya:
        return
    yy, xx = np.mgrid[ya:yb, xa:xb]
    dx, dy = x1 - x0, y1 - y0
    t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / (dx * dx + dy * dy + 1e-9), 0, 1)
    d = np.hypot(xx - (x0 + t * dx), yy - (y0 + t * dy))
    w = w0 + (w1 - w0) * t
    cov = np.clip(w - d + 0.5, 0, 1)
    c = np.asarray(col) if col1 is None else np.asarray(col) * (1 - t[..., None]) + np.asarray(col1) * t[..., None]
    shade = (0.75 + 0.25 * (1 - np.clip(d / np.maximum(w, 1e-3), 0, 1)))[..., None]   # yuvarlak kesit
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - cov[..., None]) + c * shade * cov[..., None]
    alpha[ya:yb, xa:xb] = np.maximum(alpha[ya:yb, xa:xb], cov)


def dilate_color(img, alpha):
    """Saydam piksellerin rengini yaprak ortalamasıyla doldur (mip kenarlarında siyah hale olmasın)."""
    m = alpha > 0.5
    mean = img[m].mean(0) if m.any() else np.array([0.2, 0.3, 0.1])
    out = img.copy()
    out[~m] = mean
    return out


def pine_needles():
    """Karaçam dalı: ortada hafif kavisli sürgün, etrafında uzun ikili iğneler (şişe fırçası)."""
    img, alpha = card_canvas()
    rng = np.random.default_rng(81)
    n = 1024
    greens = [(0.10, 0.17, 0.08), (0.13, 0.21, 0.09), (0.16, 0.25, 0.11), (0.08, 0.14, 0.07)]
    # Üç sürgün: ortada ana sürgün, iki yanda açılı yan sürgünler (dal ucu görünümü)
    twigs = []
    for (x0, y0, x1, y1, bend) in ((0.5, 0.99, 0.5, 0.12, 25), (0.5, 0.75, 0.2, 0.3, -30), (0.5, 0.65, 0.8, 0.22, 30)):
        twigs.append([(n * (x0 + (x1 - x0) * t) + bend * np.sin(t * 3), n * (y0 + (y1 - y0) * t)) for t in np.linspace(0, 1, 30)])
    for ti, pts in enumerate(twigs):
        count = 1700 if ti == 0 else 1000
        for k in range(count):
            t = rng.uniform(0.08, 1.0) ** 0.7
            i = min(int(t * 29), 28)
            bx, by = pts[i]
            tx, ty = pts[i + 1][0] - bx, pts[i + 1][1] - by
            base_ang = np.arctan2(ty, tx)
            side = rng.choice((-1, 1))
            ang = base_ang + side * rng.uniform(0.3, 1.1) + rng.normal(0, 0.12)     # sürgünden öne-yana
            L = rng.uniform(130, 230) * (0.5 + 0.5 * (1 - abs(t - 0.5))) * (1 if ti == 0 else 0.8)
            ex, ey = bx + np.cos(ang) * L, by + np.sin(ang) * L
            c = np.asarray(greens[rng.integers(len(greens))]) * rng.uniform(0.85, 1.25)
            draw_segment(img, alpha, (bx, by), (ex, ey), 2.4, 1.0, c, c * 1.35)
    for pts in twigs:
        for a, b in zip(pts[:-1], pts[1:]):
            draw_segment(img, alpha, a, b, 8, 6, (0.26, 0.18, 0.12))
        draw_segment(img, alpha, pts[-1], (pts[-1][0], pts[-1][1] - 35), 7, 3, (0.45, 0.35, 0.25))
    save("Tex_CamIgne", dilate_color(img, alpha), alpha)


def oak_leaves():
    img, alpha = card_canvas()
    rng = np.random.default_rng(91)
    n = 1024
    yy, xx = np.mgrid[0:n, 0:n]
    # Dallanan ince dal
    stems = []
    main = [(n * 0.5 + 20 * np.sin(t * 3), n * (0.99 - 0.85 * t)) for t in np.linspace(0, 1, 20)]
    stems.append(main)
    for k in range(5):
        t0 = 0.2 + 0.15 * k
        i = int(t0 * 19)
        sx, sy = main[i]
        side = -1 if k % 2 else 1
        stems.append([(sx + side * s * 280, sy - s * 200) for s in np.linspace(0, 1, 10)])
    leaf_cols = [(0.16, 0.25, 0.07), (0.20, 0.30, 0.09), (0.25, 0.33, 0.10), (0.13, 0.21, 0.06)]
    leaf_points = []
    for st in stems:
        for j in range(2, len(st)):
            leaf_points.append(st[j])
    rng.shuffle(leaf_points)
    for (px, py) in leaf_points[:70]:
        ang = rng.uniform(-np.pi, 0)                 # çoğunlukla yukarı
        L = rng.uniform(110, 170)
        Wd = L * rng.uniform(0.28, 0.36)
        lobes = rng.integers(4, 6)
        ca, sa = np.cos(ang), np.sin(ang)
        r = L + 4
        xa, xb = int(max(0, px - r)), int(min(n, px + r))
        ya, yb = int(max(0, py - r)), int(min(n, py + r))
        if xb <= xa or yb <= ya:
            continue
        X = xx[ya:yb, xa:xb] - px
        Y = yy[ya:yb, xa:xb] - py
        uu = (X * ca + Y * sa) / L               # yaprak boyunca 0..1
        vv = (-X * sa + Y * ca)                  # enine (piksel)
        width = Wd * np.clip(np.sin(np.pi * np.clip(uu, 0, 1)), 0, 1) ** 0.75 * \
            (0.62 + 0.38 * np.abs(np.sin(lobes * np.pi * np.clip(uu, 0, 1))))
        inside = (uu > 0.02) & (uu < 1) & (np.abs(vv) < width)
        cov = np.clip((width - np.abs(vv)) * 0.8, 0, 1) * inside
        c = np.asarray(leaf_cols[rng.integers(len(leaf_cols))]) * rng.uniform(0.85, 1.2)
        shade = 0.8 + 0.25 * (vv / (width + 1e-3))          # bir yarısı daha aydınlık
        vein = np.exp(-(vv ** 2) / 2.0) * (uu < 0.95)
        col = c[None, None, :] * shade[..., None] * (1 - 0.35 * vein[..., None])
        reg = img[ya:yb, xa:xb]
        img[ya:yb, xa:xb] = reg * (1 - cov[..., None]) + col * cov[..., None]
        alpha[ya:yb, xa:xb] = np.maximum(alpha[ya:yb, xa:xb], cov)
    for st in stems:
        for a, b in zip(st[:-1], st[1:]):
            draw_segment(img, alpha, a, b, 4, 3, (0.25, 0.19, 0.13))
    save("Tex_MeseYaprak", dilate_color(img, alpha), alpha)


def grass_card(name, cols, tip, seed, n_blades=900):
    """Ot öbeği kartı: alttan yelpaze gibi açılan, hafif kıvrık ince yapraklar (RGBA)."""
    img, alpha = card_canvas(512)
    rng = np.random.default_rng(seed)
    n = 512
    for k in range(n_blades):
        x0 = n * 0.5 + rng.normal(0, n * 0.12)
        y0 = n * 0.995
        ang = -np.pi / 2 + rng.normal(0, 0.38)
        L = rng.uniform(0.35, 0.95) * n * (1 - 0.4 * abs(ang + np.pi / 2))
        bend = rng.normal(0, 0.5)
        c = np.asarray(cols[rng.integers(len(cols))]) * rng.uniform(0.8, 1.2)
        pts = []
        for t in np.linspace(0, 1, 7):
            a = ang + bend * t * t
            pts.append((x0 + np.cos(a) * L * t, y0 + np.sin(a) * L * t))
        w0 = rng.uniform(1.6, 3.0)
        for i in range(len(pts) - 1):
            t0, t1 = i / 6, (i + 1) / 6
            draw_segment(img, alpha, pts[i], pts[i + 1], w0 * (1 - 0.8 * t0), w0 * (1 - 0.8 * t1),
                         c * (0.7 + 0.5 * t0), np.asarray(tip) * t1 + c * (1 - t1))
    save(name, dilate_color(img, alpha), alpha)


def grass_green():
    grass_card("Tex_OtYesil", [(0.16, 0.24, 0.07), (0.22, 0.30, 0.09), (0.28, 0.34, 0.12), (0.34, 0.36, 0.14)],
               (0.55, 0.52, 0.28), 501)


def grass_dry():
    grass_card("Tex_OtKuru", [(0.48, 0.40, 0.22), (0.58, 0.50, 0.30), (0.40, 0.34, 0.18), (0.36, 0.36, 0.20)],
               (0.78, 0.70, 0.48), 502)


# ---------------------------------------------------------------------- yüzey ayrıntı dokuları
# Bunlar "çarpan" dokulardır: ortalaması ~0.9, malzemenin kendi rengiyle çarpılır (Unity'de
# üç yönlü/triplanar eşlenir, UV gerekmez). Amaç: düz renkli yüzeylere gerçek malzeme dokusu.
def _gray(v):
    v = np.clip(v, 0, 1)
    return np.stack([v, v, v], -1)


def surf_composite():
    """Mat kompozit gövde: ince boya tanesi, hafif lekeler, ince çizikler."""
    u, v = grid(N)
    grain = fbm(u, v, 96, 3, 201)
    blot = fbm(u, v, 6, 4, 202)
    h = grain * 0.4 + blot * 0.2
    img = 0.86 + 0.08 * (grain - 0.5) + 0.10 * (blot - 0.5)
    rgb = _gray(img)
    hh = h.copy()
    strokes(rgb, hh, 140, (20, 90), (0.4, 0.9), [(1.0, 1.0, 1.0), (0.97, 0.97, 0.97)], 203)   # çizikler
    save("Srf_Kompozit", rgb)
    save("Srf_Kompozit_Normal", normal_from_height(hh, 1.5))


def surf_carbon():
    """2x2 dimi örgü karbon fiber."""
    n = N
    yy, xx = np.mgrid[0:n, 0:n]
    cells = 32
    cx, cy = (xx * cells // n), (yy * cells // n)
    fx, fy = (xx * cells / n) % 1, (yy * cells / n) % 1
    warp = ((cx + cy) // 2) % 2 == 0                 # dimi deseni: çapraz kayan bloklar
    along = np.where(warp, fx, fy)
    across = np.where(warp, fy, fx)
    tow = np.sin(across * np.pi) ** 0.6              # lif demeti kesiti
    fibers = 0.5 + 0.5 * np.sin(along * np.pi * 2 * 6 + across * 3)
    h = tow * 0.8 + fibers * 0.1
    sheen = 0.55 + 0.45 * tow * (0.7 + 0.3 * np.where(warp, 1.0, 0.6))
    save("Srf_Karbon", _gray(sheen))
    save("Srf_Karbon_Normal", normal_from_height(h, 3.0))


def surf_paint_wear():
    """Askeri araç boyası: toz, aşağı akan kir izleri, kenar aşınması lekeleri."""
    u, v = grid(N)
    dust = fbm(u, v, 5, 5, 211)
    streak = fbm(u * 0.25, v, 3, 4, 212, aniso=(4, 1))   # dikey akıntılar
    chips = np.clip((fbm(u, v, 24, 4, 213) - 0.72) * 6, 0, 1)
    img = 0.92 - 0.12 * np.clip((streak - 0.5) * 2.5, 0, 1) + 0.06 * (dust - 0.5) + 0.25 * chips
    h = dust * 0.2 - chips * 0.4
    save("Srf_BoyaYipranma", _gray(img))
    save("Srf_BoyaYipranma_Normal", normal_from_height(h, 2.0))


def surf_plaster():
    """Kaba sıva: pütürlü yüzey, nem lekeleri, alt kısımda kir."""
    u, v = grid(N)
    bump = fbm(u, v, 48, 4, 221)
    stain = fbm(u, v, 4, 5, 222)
    img = 0.9 + 0.08 * (bump - 0.5) - 0.12 * np.clip((stain - 0.55) * 3, 0, 1)
    save("Srf_Siva", _gray(img))
    save("Srf_Siva_Normal", normal_from_height(bump * 0.6 + stain * 0.2, 2.5))


def surf_roof_tile():
    """Alaturka kiremit sıraları: oluklu kesit, tek tek kiremit ton farkı."""
    u, v = grid(N)
    rows, cols = 16, 10
    ru, rv = u * cols, v * rows
    tile_id = (np.floor(rv).astype(int) * 97 + np.floor(ru + 0.5 * (np.floor(rv) % 2)).astype(int) * 31) % 997
    tone = hash01(tile_id, 231)
    wave = np.abs(np.sin((ru + 0.5 * (np.floor(rv) % 2)) * np.pi))     # yarım silindir kesit
    overlap = (rv % 1) ** 2                                             # alt kenar gölgesi
    h = wave * 0.7 + overlap * 0.3
    img = (0.78 + 0.2 * tone) * (0.75 + 0.25 * wave) * (0.8 + 0.2 * overlap)
    moss = np.clip((fbm(u, v, 6, 4, 232) - 0.66) * 4, 0, 1)
    rgb = _gray(img)
    rgb = lerp(rgb, np.array([0.55, 0.6, 0.45]) * rgb, moss * 0.6)
    save("Srf_Kiremit", rgb)
    save("Srf_Kiremit_Normal", normal_from_height(h, 4.0))


def surf_concrete():
    u, v = grid(N)
    n = fbm(u, v, 16, 5, 241)
    f1, f2, cid = voronoi(u, v, 8, 242)
    crack = np.clip((f2 - f1) * 40, 0, 1)
    pits = np.clip((fbm(u, v, 128, 2, 243) - 0.7) * 5, 0, 1)
    img = 0.88 + 0.12 * (n - 0.5) - 0.18 * (1 - crack) * 0.4 - 0.1 * pits
    save("Srf_Beton", _gray(img))
    save("Srf_Beton_Normal", normal_from_height(n * 0.4 + crack * 0.2 - pits * 0.3, 2.0))


def turkish_flag():
    """Türk bayrağı (Türk Bayrağı Kanunu oranları: G yükseklik, boy 1.5G)."""
    G, W = 400, 600
    ss = 3                                     # kenar yumuşatma için 3x örnekleme
    yy, xx = np.mgrid[0:G * ss, 0:W * ss] / ss
    red = np.array([0.89, 0.04, 0.09])
    white = np.array([1.0, 1.0, 1.0])
    cy = G / 2
    outer = (xx - 0.5 * G) ** 2 + (yy - cy) ** 2 < (0.25 * G) ** 2
    inner = (xx - (0.5 + 0.0625) * G) ** 2 + (yy - cy) ** 2 < (0.2 * G) ** 2
    crescent = outer & ~inner
    sx, sr = (0.5 + 0.0625 + 1 / 3) * G, 0.125 * G
    # Beş köşeli yıldız (bir ucu gönder tarafına bakar): 10 köşeli çokgen, çift-tek kuralı
    inner_r = sr * 0.382
    pts = []
    for i in range(10):
        t = np.pi + i * np.pi / 5
        r = sr if i % 2 == 0 else inner_r
        pts.append((sx + r * np.cos(t), cy + r * np.sin(t)))
    star = np.zeros(xx.shape, bool)
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cond = ((y1 > yy) != (y2 > yy)) & (xx < (x2 - x1) * (yy - y1) / (y2 - y1 + 1e-12) + x1)
        star ^= cond
    m = (crescent | star).astype(float)
    m = m.reshape(G, ss, W, ss).mean((1, 3))
    img = red[None, None] * (1 - m[..., None]) + white[None, None] * m[..., None]
    save("Tex_Bayrak", img)


if __name__ == "__main__":
    only = sys.argv[2:]
    funcs = (ter_grass, ter_steppe, ter_plowed, ter_stubble, ter_rock, ter_gravel,
             bark_pine, bark_oak, pine_needles, oak_leaves, turkish_flag, grass_green, grass_dry, surf_composite, surf_carbon, surf_paint_wear,
             surf_plaster, surf_roof_tile, surf_concrete)
    for f in funcs:
        if not only or f.__name__ in only:
            f()
