"""Sunum ve rapor için en iyi görüntüleri gorseller/ klasörüne JPEG olarak toplar.

    python tools/collect_gallery.py
"""
import os

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "gorseller")
SHOTS = [
    (r"C:\SuruIHA\autotest\h_zemin_ova.png", "01_yer_istasyonu_ve_suru.jpg"),
    (r"C:\SuruIHA\autotest_merkezi\h_zemin_ova.png", "02_merkezi_mimari_yildiz_baglanti.jpg"),
    (r"C:\SuruIHA\autotest\b_takip.png", "03_takip_kamerasi_gps_sapmasi.jpg"),
    (r"C:\SuruIHA\autotest\d_takip2.png", "04_takip_kamerasi_2.jpg"),
    (r"C:\SuruIHA\autotest\a_sinematik.png", "05_sinematik_kamera.jpg"),
    (r"C:\SuruIHA\autotest\c_taktik.png", "06_taktik_kusbakisi.jpg"),
    (r"C:\SuruIHA\autotest\g_zemin_bozkir.png", "07_bozkir_yamac.jpg"),
    (r"C:\SuruIHA\preview\1_genel.png", "08_genel_gorunum.jpg"),
    (r"C:\SuruIHA\preview\3_karistirici.png", "09_karistirici_araci.jpg"),
    (r"C:\SuruIHA\preview\4_iha_yakin.png", "10_iha_yakin_plan.jpg"),
    (r"C:\SuruIHA\preview\10_zemin_ova.png", "11_surulmus_tarla.jpg"),
    (r"C:\SuruIHA\models\preview_drone_a.png", "12_iha_modeli_blender.jpg"),
    (r"C:\SuruIHA\models\preview_trees.png", "13_bitki_modelleri_blender.jpg"),
    (r"C:\SuruIHA\soak3\pencere2.png", "14_arayuz_paneli.jpg"),
    (r"C:\SuruIHA\preview\11_koy.png", "17_anadolu_koyu.jpg"),
    (r"C:\SuruIHA\preview\12_koy_sokak.png", "18_koy_sokagi.jpg"),
    (r"C:\SuruIHA\models\preview_village.png", "19_koy_modelleri_blender.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\completion_saldirgan0.png", "15_grafik_tamamlama_saldirgansiz.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\completion_saldirgan20.png", "16_grafik_tamamlama_saldirganli.jpg"),
]

os.makedirs(OUT, exist_ok=True)
for src, name in SHOTS:
    if not os.path.exists(src):
        print("yok:", src)
        continue
    Image.open(src).convert("RGB").save(os.path.join(OUT, name), quality=90, optimize=True)
    print("ok:", name)
