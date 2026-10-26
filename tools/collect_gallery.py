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
    (r"C:\SuruIHA\livecheck\3_ariza.png", "14_arayuz_paneli.jpg"),
    (r"C:\SuruIHA\preview\2_suru.png", "20_V_duzeninde_intikal.jpg"),
    (r"C:\SuruIHA\autotest\e_sinematik2.png", "21_duzende_donus.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\ariza_karistirici20.png", "22_grafik_uye_kaybi.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\role_etkisi.png", "23_grafik_role.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\formation_err_saldirgan0.png", "24_grafik_duzen_hatasi.jpg"),
    (r"C:\SuruIHA\preview\11_koy.png", "17_anadolu_koyu.jpg"),
    (r"C:\SuruIHA\preview\12_koy_sokak.png", "18_koy_sokagi.jpg"),
    (r"C:\SuruIHA\models\preview_village.png", "19_koy_modelleri_blender.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\completion_saldirgan0.png", "15_grafik_tamamlama_saldirgansiz.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\completion_saldirgan20.png", "16_grafik_tamamlama_saldirganli.jpg"),
    (r"C:\SuruIHA\autotest\i_yeni_hedef.png", "25_yeni_hedef_ve_planlar.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\karar_puan.png", "26_grafik_karar_puan.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\karar_yol.png", "27_grafik_karar_yol.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\paket_boyutu.png", "28_grafik_paket_boyutu.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\ai_dogruluk.png", "29_grafik_yapay_zeka_dogruluk.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\ai_ne_ogrendi.png", "30_grafik_yapay_zeka_ne_ogrendi.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\yapay_zeka.png", "31_grafik_yapay_zeka_karsilastirma.jpg"),
    (r"C:\SuruIHA\autotest\j_eh_kusbakisi.png", "32_eh_hareketli_karistirici_ve_gps_aldatici.jpg"),
    (r"C:\SuruIHA\autotest\k_eh_sinematik.png", "33_eh_sinematik.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\eh_senaryolar.png", "34_grafik_eh_senaryolar.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\ablasyon.png", "35_grafik_ablasyon.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\olcekleme.png", "36_grafik_olcekleme.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\ayar_duyarlilik.png", "37_grafik_ayar_duyarlilik.jpg"),
    (r"C:\Users\Doğukan Yılmaz\OneDrive\Desktop\sürü_iha\results\figures\eh_arazi_golgesi.png", "38_grafik_arazi_golgesi.jpg"),
    # Aşama 5: film modunda çekilen kareler (tools/record_film.py + SuruIHA.exe -suruFilm)
    (r"C:\SuruIHA\film\poster2\kare_00000.jpg", "39_suru_karistirma_alanina_giriyor.jpg"),
    (r"C:\SuruIHA\film\kareler\kare_01200.jpg", "40_takip_karistirma_bolgesinde.jpg"),
    (r"C:\SuruIHA\film\poster\kare_00004.jpg", "41_cbba_planlari_tepeden.jpg"),
    (r"C:\SuruIHA\film\poster\kare_00006.jpg", "42_yan_yana_gps_aldatma.jpg"),
    (r"C:\SuruIHA\film\poster\kare_00008.jpg", "43_yan_yana_iki_karistirici.jpg"),
    (r"C:\SuruIHA\film\kareler\kare_02100.jpg", "44_yan_yana_sinematik.jpg"),
    # Yarışma arayüzü (tools/ui_test.ps1)
    (r"C:\SuruIHA\arayuz_testi\01_sekme_proje.png", "45_arayuz_ana_ekran.jpg"),
    (r"C:\SuruIHA\arayuz_testi\09_sekme_simulasyon.png", "46_arayuz_senaryo_sec.jpg"),
    (r"C:\SuruIHA\arayuz_testi\12_senaryo_kutusu.png", "47_arayuz_simulasyon.jpg"),
    (r"C:\SuruIHA\arayuz_testi\17_sonuc.png", "48_arayuz_gorev_sonu.jpg"),
    (r"C:\SuruIHA\arayuz_testi\18_yan_yana.png", "49_arayuz_yan_yana.jpg"),
    (r"C:\SuruIHA\arayuz_testi\02_sekme_nasil_calisir.png", "50_arayuz_nasil_calisir.jpg"),
    (r"C:\SuruIHA\arayuz_testi\03_sekme_kullanilanlar.png", "51_arayuz_kullanilanlar.jpg"),
    (r"C:\SuruIHA\arayuz_testi\04_bulgu_eh.png", "52_arayuz_bulgular_eh.jpg"),
    (r"C:\SuruIHA\arayuz_testi\07_bulgu_ablasyon.png", "53_arayuz_bulgular_ablasyon.jpg"),
    (r"C:\SuruIHA\arayuz_testi\13b_iha_kamerasi.png", "54_iha_kamerasi_tpp.jpg"),
    (r"C:\SuruIHA\arayuz_testi\19_yan_yana_iha_kamerasi.png", "55_yan_yana_iha_kamerasi.jpg"),
    (r"C:\SuruIHA\arayuz_testi\13c_taktik_numaralar.png", "56_taktik_iha_numaralari.jpg"),
    (r"C:\SuruIHA\arayuz_testi\13d_katmanlar.png", "57_gorunum_katmanlari.jpg"),
    (r"C:\SuruIHA\arayuz_testi\13a_sorunlu_baglantilar.png", "58_yalnizca_sorunlu_baglantilar.jpg"),
    (r"C:\SuruIHA\arayuz_testi\20_isi_haritasi_tepeden.png", "59_isi_haritasi_arazi_golgesi.jpg"),
    (r"C:\SuruIHA\arayuz_testi\21_isi_haritasi_sinematik.png", "60_isi_haritasi_sinematik.jpg"),
    (r"C:\SuruIHA\arayuz_testi\17b_ucus_raporu.png", "61_ucus_raporu.jpg"),
    (r"C:\SuruIHA\arayuz_testi\17c_ucus_raporu_secili_iha.png", "62_ucus_raporu_secili_iha.jpg"),
    (r"C:\SuruIHA\arayuz_testi\22_kendi_senaryon_kurulu.png", "63_kendi_senaryon.jpg"),
    (r"C:\SuruIHA\arayuz_testi\23_kendi_senaryon_ucus.png", "64_kendi_senaryon_ucus.jpg"),
]

os.makedirs(OUT, exist_ok=True)
for src, name in SHOTS:
    if not os.path.exists(src):
        print("yok:", src)
        continue
    Image.open(src).convert("RGB").save(os.path.join(OUT, name), quality=90, optimize=True)
    print("ok:", name)
