"""Tanıtım videosu 3/3: Unity'nin çektiği kareleri, kartları ve alt yazıları Blender'da birleştirip MP4 yapar.

    blender -b --factory-startup --python tools/make_video.py -- C:/SuruIHA/film/kurgu.json

Hiçbir ek program gerekmez: Blender'ın video düzenleyicisi (VSE) ve içindeki FFmpeg kullanılır (H.264).
kurgu.json'u tools/record_film.py yazar; karelerin hangi çekime ait olduğu Unity'nin yazdığı
kareler/film_rapor.txt'den okunur (bir çekim kayıt bitince erken kesildiyse kurgu kaymaz).
"""
import json
import os
import re
import sys

import bpy

FADE = 12                  # kartlarda kararma / açılma (kare)
W, H = 1920, 1080


def font(name):
    p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
    return bpy.data.fonts.load(p, check_existing=True) if os.path.exists(p) else None


def fade(strip, start, end, inn=True, out=True):
    if inn:
        strip.blend_alpha = 0.0
        strip.keyframe_insert("blend_alpha", frame=start)
        strip.blend_alpha = 1.0
        strip.keyframe_insert("blend_alpha", frame=start + FADE)
    if out:
        strip.blend_alpha = 1.0
        strip.keyframe_insert("blend_alpha", frame=end - FADE)
        strip.blend_alpha = 0.0
        strip.keyframe_insert("blend_alpha", frame=end)


def text(ed, name, s, ch, start, length, loc, size, color=(1, 1, 1, 1), box=None, anchor=("CENTER", "BOTTOM"),
         bold=False, wrap=0.86):
    t = ed.strips.new_effect(name=name, type="TEXT", channel=ch, frame_start=start, length=length)
    t.text = s
    t.font_size = size
    t.color = color
    t.location = loc
    t.anchor_x, t.anchor_y = anchor
    t.alignment_x = "CENTER" if anchor[0] == "CENTER" else anchor[0]
    t.wrap_width = wrap
    f = font("segoeuib.ttf" if bold else "segoeui.ttf")
    if f:
        t.font = f
    t.use_shadow = True
    t.shadow_color = (0, 0, 0, 0.8)
    if box:
        t.use_box = True
        t.box_color = box
        t.box_margin = 0.012
        t.box_roundness = 0.35
    t.blend_type = "ALPHA_OVER"
    return t


def main():
    kurgu = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
    fps = kurgu["fps"]
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.fps = fps
    sc.view_settings.view_transform = "Standard"     # JPG/PNG renkleri olduğu gibi kalsın
    ed = sc.sequence_editor_create()

    rapor = open(os.path.join(kurgu["frames"], "film_rapor.txt"), encoding="utf-8").read()
    firsts = [int(x) for x in re.findall(r"ilk_kare=(\d+)", rapor)]
    total = int(re.search(r"toplam (\d+) kare", rapor).group(1))
    counts = [b - a for a, b in zip(firsts, firsts[1:] + [total])]
    assert len(counts) == len(kurgu["shots"]), "film_rapor.txt ile kurgu.json'daki çekim sayısı farklı"

    f = 1
    n = 0

    def card(name, sec):
        nonlocal f, n
        L = int(sec * fps)
        s = ed.strips.new_image(name=f"kart{n}", filepath=os.path.join(kurgu["cards"], name), channel=1,
                                frame_start=f, fit_method="FIT")
        s.frame_final_duration = L
        fade(s, f, f + L)
        f += L
        n += 1

    for name, sec in kurgu["before"]:
        card(name, sec)

    for i, (shot, cnt) in enumerate(zip(kurgu["shots"], counts)):
        if cnt <= 0:
            continue
        files = [f"kare_{k:05d}.jpg" for k in range(firsts[i], firsts[i] + cnt)]
        s = ed.strips.new_image(name=f"cekim{i}", filepath=os.path.join(kurgu["frames"], files[0]), channel=1,
                                frame_start=f, fit_method="FIT")
        for fn in files[1:]:
            s.elements.append(fn)
        s.frame_final_duration = cnt
        fade(s, f, f + cnt, inn=(i == 0), out=(i == len(counts) - 1))
        cap = text(ed, f"yazi{i}", shot["caption"], 4, f + 6, cnt - 6, (0.5, 0.05), 38,
                   box=(0.02, 0.05, 0.08, 0.62))
        fade(cap, f + 6, f + cnt, inn=True, out=False)
        text(ed, f"etiket{i}", "Simülasyon kaydı · 3× hız", 5, f, cnt, (0.985, 0.965), 22, color=(1, 1, 1, 0.75),
             anchor=("RIGHT", "TOP"), wrap=0.3)
        if shot.get("labels"):
            div = ed.strips.new_effect(name=f"ayrac{i}", type="COLOR", channel=2, frame_start=f, length=cnt)
            div.color = (0.92, 0.95, 0.97)
            div.transform.scale_x = 4 / W
            div.blend_type = "ALPHA_OVER"
            for side, (lab, col) in enumerate(zip(shot["labels"], [(0.85, 0.35, 0.19, 0.85), (0.11, 0.62, 0.46, 0.85)])):
                text(ed, f"taraf{i}_{side}", lab, 6 + side, f, cnt, (0.25 + 0.5 * side, 0.955), 40, bold=True,
                     box=col, anchor=("CENTER", "TOP"), wrap=0.4)
        f += cnt

    for name, sec in kurgu["after"]:
        card(name, sec)

    sc.frame_start, sc.frame_end = 1, f - 1
    im = sc.render.image_settings
    im.media_type = "VIDEO"
    im.file_format = "FFMPEG"
    ff = sc.render.ffmpeg
    ff.format, ff.codec = "MPEG4", "H264"
    ff.constant_rate_factor, ff.ffmpeg_preset = "MEDIUM", "GOOD"   # ~80 MB / 2 dk: paylaşmaya uygun
    ff.audio_codec = "NONE"
    os.makedirs(os.path.dirname(kurgu["out"]), exist_ok=True)
    sc.render.filepath = kurgu["out"]
    sc.render.use_file_extension = False
    print(f"[video] {f - 1} kare ({(f - 1) / fps:.0f} s) işleniyor -> {kurgu['out']}", flush=True)
    bpy.ops.render.render(animation=True)
    print("[video] bitti", flush=True)


main()
