using UnityEngine;

namespace SuruIHA
{
    // Menüdeki senaryolar. Args, run_live.py / run_compare.py komut satırı seçenekleridir.
    // Ref*: aynı senaryonun deneylerdeki görev tamamlama oranı (%; 30 uçuş, results/istatistik.txt).
    public class Scenario
    {
        public string Id, Tag, Title, Short, Watch, Args;
        public Color TagColor;
        public float RefCentral, RefDecentral, RefResilient;
        public bool Custom;     // "Kendi senaryon" sekmesinde kurulan senaryo (deney ortalaması yok)
    }

    public static class SwarmScenarios
    {
        public static readonly Scenario[] All =
        {
            new Scenario
            {
                Id = "temel", Tag = "TEMEL", TagColor = Ui.Ink2, Title = "Temel görev",
                Short = "Karıştırma yok. Sürü zekâsını ve otonom görev paylaşımını izle.",
                Watch = "Sürü lidersiz V düzeninde intikal eder. Görev alanında renkli çizgiler her İHA'nın planıdır (CBBA). " +
                        "Mor dalga yeni bir hedefin belirdiğini gösterir: sürü saniyeler içinde kimin gideceğine kendisi karar verir.",
                Args = "--jammer off", RefCentral = 100f, RefDecentral = 100f, RefResilient = 100f,
            },
            new Scenario
            {
                Id = "sabit20", Tag = "KARIŞTIRMA", TagColor = Ui.Bad, Title = "Karıştırıcı (20 dBm)",
                Short = "Görev alanında haberleşmeyi ve GPS'i bozan bir karıştırıcı var.",
                Watch = "Kırmızı kubbeye giren İHA'nın ışığı kırmızıya döner: GPS'i kesildi. Dirençli İHA hedefi görmeden \"bitti\" demez, " +
                        "mavi ışıkla spiral çizerek arar. Turuncu nişangâh, sürünün ölçümlerden bulduğu karıştırıcı yeridir.",
                Args = "--jammer 20", RefCentral = 86.9f, RefDecentral = 89.4f, RefResilient = 100f,
            },
            new Scenario
            {
                Id = "guclu30", Tag = "KARIŞTIRMA", TagColor = Ui.Bad, Title = "Güçlü karıştırma (30 dBm)",
                Short = "Görev alanının neredeyse tamamı GPS'siz. En zor karıştırma.",
                Watch = "İHA'lar GPS'i olan komşularına menzil ölçerek konumunu düzeltir (işbirlikçi konum). Belirsizliği çok büyüyen İHA " +
                        "görevi bırakıp GPS'i geri almak için bölgeden çıkar. Dirençli sürü burada da görevlerin üçte ikisini yapar.",
                Args = "--jammer 30", RefCentral = 12.3f, RefDecentral = 16.7f, RefResilient = 66.5f,
            },
            new Scenario
            {
                Id = "hareketli", Tag = "KARIŞTIRMA", TagColor = Ui.Bad, Title = "Hareketli karıştırıcı",
                Short = "Karıştırıcı araç görev alanının çevresinde devriye geziyor.",
                Watch = "Kubbe araçla birlikte yer değiştirir. Sürünün tahmini (turuncu nişangâh) aracı izlemeye çalışır; " +
                        "teyit edilmeyen eski karıştırma bölgeleri zamanla unutulur.",
                Args = "--jammer 20 --jammer-mode hareketli", RefCentral = 83.7f, RefDecentral = 85.9f, RefResilient = 100f,
            },
            new Scenario
            {
                Id = "iki", Tag = "KARIŞTIRMA", TagColor = Ui.Bad, Title = "İki karıştırıcı",
                Short = "İki kaynak birden. Farkın en büyük olduğu senaryo.",
                Watch = "Sürü önce tek karıştırıcı varsayar; ölçümler buna uymayınca iki kaynaklı modele geçer. " +
                        "Korumasız sürü bu senaryoda görevlerin yalnızca %39'unu, dirençli sürü %99,5'ini yapar.",
                Args = "--jammer 20 --jammer-mode iki", RefCentral = 40.4f, RefDecentral = 39.4f, RefResilient = 99.5f,
            },
            new Scenario
            {
                Id = "sirt", Tag = "ARAZİ", TagColor = Ui.Good, Title = "Sırt arkasında karıştırıcı",
                Short = "Tepeler sinyali gölgeliyor: arazinin kalkan etkisi.",
                Watch = "30 dBm karıştırıcı tepenin arkasında. Tepe sinyali kırınımla zayıflatır; ısı haritasındaki açık renkli " +
                        "boşluklar tepenin gölgesidir, oradaki İHA'lar etkilenmez. Arazi hesaba katılmasaydı korumasız sürü %65 " +
                        "yapacaktı; tepeler sayesinde %92 yapıyor.",
                Args = "--jammer 30 --jammer-mode sirt", RefCentral = 91.5f, RefDecentral = 92.1f, RefResilient = 100f,
            },
            new Scenario
            {
                Id = "gps", Tag = "GPS ALDATMA", TagColor = Ui.Cyan, Title = "GPS aldatma",
                Short = "Sahte uydu sinyali İHA'ların konumunu yavaşça kaydırıyor.",
                Watch = "Camgöbeği kubbedeki aldatıcı, İHA'ları sahte bir konuma inandırır. Pembe İHA = kandırıldı, sarı İHA = fark etti " +
                        "(IMU ile karşılaştırma, komşu menzil testi, \"hedef yok\" çıkarımı). Korumasız İHA'lar hedefi bulduğunu sanır.",
                Args = "--jammer off --gps-spoof hizli", RefCentral = 51.9f, RefDecentral = 50.5f, RefResilient = 98.6f,
            },
            new Scenario
            {
                Id = "saldirgan", Tag = "SALDIRGAN", TagColor = Ui.Violet, Title = "Sinsi saldırgan İHA'lar",
                Short = "Sürünün %20'si ele geçirilmiş: yalan söylüyorlar.",
                Watch = "Mor İHA'lar saldırgan: sahte \"tamamlandı\" yayar, konumu hakkında yalan söyler. Güven sistemi menzil, hız ve " +
                        "ilerleme kanıtı toplayıp onları dışlar; tek bir yalancı dürüst bir İHA'yı karalayamaz (iki tanık kuralı).",
                Args = "--jammer off --spoof 0.2 --spoof-mode sneaky", RefCentral = 32.4f, RefDecentral = 86.8f, RefResilient = 100f,
            },
        };

        public static readonly string[] Strategies = { "centralized", "decentralized", "resilient" };
        public static readonly string[] StrategyTitles = { "Merkezi", "Merkeziyetsiz", "EH dirençli" };
        public static readonly string[] StrategyInfo =
        {
            "Yer istasyonu herkesin bilgisini toplar ve görevleri dağıtır. İstasyonla bağlantısı kopan İHA eski planla kalır.",
            "Lider yok: İHA'lar komşularıyla uzlaşarak görev paylaşır (CBBA). Ama gelen her bilgiye güvenir; EH önlemi yok.",
            "Merkeziyetsiz sürüye 11 EH savunması eklenir: karıştırma haritası, spiral arama, karıştırıcı bulma, aldatma tespiti, güven sistemi…",
        };

        public static readonly string[] Planners = { "greedy", "cbba", "ai" };
        public static readonly string[] PlannerTitles = { "Açgözlü", "CBBA", "CBBA + yapay zekâ" };
        public static readonly string[] PlannerInfo =
        {
            "Eski yöntem: her İHA en yakın tek hedefi alır. Karşılaştırma için.",
            "Her İHA 3 hedeflik rota planlar ve komşularıyla çakışmasız bir plana uzlaşır (Choi vd. 2009).",
            "Sinir ağı her İHA'nın hedefi başarma olasılığını tahmin eder; CBBA beklenen ödülü en büyütür.",
        };

        public static string StrategyTitle(string s) => s switch
        {
            "centralized" => "Merkezi (yer istasyonu)",
            "decentralized" => "Merkeziyetsiz (korumasız)",
            "resilient" => "Merkeziyetsiz + EH direnci",
            _ => s ?? "-",
        };

        public static string PhaseTitle(string p) => p switch
        {
            "kalkis" => "kalkış",
            "intikal" => "düzende intikal",
            "gorev" => "görev",
            "toplanma" => "toplanma",
            "donus" => "düzende dönüş",
            "inis" => "iniş",
            "indi" => "indi",
            _ => p ?? "-",
        };

        public static string PlannerTitle(string p, string strategy) => p switch
        {
            "greedy" => "açgözlü tek görev",
            "cbba" => strategy == "centralized" ? "SGA (merkezi paket planlama)" : "CBBA paket planlama",
            "ai" => "CBBA + yapay zekâ",
            _ => p ?? "-",
        };
    }
}
