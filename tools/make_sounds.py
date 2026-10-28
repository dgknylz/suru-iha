"""Uygulamanın seslerini sentezler (indirme yok, lisans derdi yok): İHA pervanelerinin uğultusu,
iki çeşit rüzgâr (ova, karlı dağlar), Kızılırmak'ın akışı ve arayüzün yumuşak tonları.

    python tools/make_sounds.py [çıkış klasörü]      (varsayılan C:\\SuruIHA\\audio)

Döngü sesleri baştan sona dikişsiz döner: bütün frekanslar döngü süresinin tam katıdır ve gürültü
frekans uzayında (dairesel) süzülür. Kulak yormasın diye yüksek frekanslar yumuşakça kesilir, seviyeler
RMS'e göre ayarlanır ve tonlarda sert başlangıç yoktur.
"""
import os
import sys
import wave

import numpy as np

SR = 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\SuruIHA\audio"


def lp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order))


def hp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-3)) ** (2 * order))


def shaped_noise(rng, n, shape):
    """Dairesel süzülmüş gürültü: shape(f) genlik yanıtı; sonuç n örnekte kusursuz döner."""
    spec = np.fft.rfft(rng.standard_normal(n))
    spec *= shape(np.fft.rfftfreq(n, 1.0 / SR))
    x = np.fft.irfft(spec, n)
    return x / np.sqrt(np.mean(x ** 2))


def filt(x, shape):
    """Döngüyü bozmadan (dairesel) süzgeç."""
    spec = np.fft.rfft(x) * shape(np.fft.rfftfreq(len(x), 1.0 / SR))
    return np.fft.irfft(spec, len(x))


def slow(rng, t, period, harmonics, tilt=1.0):
    """Döngü süresinin tam katı frekanslardan yavaş, ortalaması sıfır dalgalanma (-1..1 civarı)."""
    m = np.zeros_like(t)
    for j in harmonics:
        m += j ** -tilt * np.sin(2 * np.pi * j * t / period + rng.uniform(0, 2 * np.pi))
    return m / np.max(np.abs(m))


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


def set_rms(x, db):
    return x * 10 ** ((db - rms_db(x)) / 20)


def set_peak(x, db):
    return x * 10 ** (db / 20) / np.max(np.abs(x))


def fade(n, ms):
    k = max(1, int(SR * ms / 1000))
    w = np.ones(n)
    w[:k] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, k))
    return w


def save(name, x):
    os.makedirs(OUT, exist_ok=True)
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    peak = 20 * np.log10(np.max(np.abs(x)) + 1e-12)
    print(f"{name:16s} {len(x) / SR:5.1f} s  RMS {rms_db(x):6.1f} dBFS  tepe {peak:6.1f} dBFS")


# ------------------------------------------------------------------ pervane
def rotor(rng, period=6.0):
    """Dört pervaneli İHA: her pervanenin kanat geçiş frekansı ve harmonikleri (kanat sayısı 2), pervanelerin
    birbirinden biraz farklı devri (vuru), uçuş kontrolcüsünün devir düzeltmeleri ve kanatlardan kopan
    türbülans gürültüsü (kanat geçişiyle kıyılmış)."""
    n = int(SR * period)
    t = np.arange(n) / SR
    tonal = np.zeros(n)
    chop = np.zeros(n)
    for f_hz in (174.0, 179.5, 183.0, 177.0):
        f0 = round(f_hz * period / 2) * 2 / period      # yarısı (mil devri) da döngüye tam otursun
        # devir düzeltmesi: % ±1,2; fazı kapalı biçimde entegre edilir (döngü sonunda faz tam katta)
        dev = np.zeros(n)
        amps = []
        for j in range(1, 6):
            a, ph = j ** -1.3, rng.uniform(0, 2 * np.pi)
            amps.append(a)
            dev += a * -period / (2 * np.pi * j) * (np.cos(2 * np.pi * j * t / period + ph) - np.cos(ph))
        dev *= 0.012 / max(amps)
        phase = 2 * np.pi * f0 * (t + dev)
        thrust = 1.0 + 0.15 * slow(rng, t, period, range(1, 5))
        # kanat geçişi harmonikleri + mil devrinde dengesizlik bileşenleri (yarım katlar)
        for k, a in [(0.5, 0.22), (1, 1.0), (1.5, 0.10), (2, 0.55), (3, 0.30), (4, 0.20), (5, 0.12),
                     (6, 0.08), (7, 0.05), (8, 0.035), (10, 0.02), (12, 0.012)]:
            a *= lp(k * f0, 1600, 2)
            tonal += thrust * a * np.sin(k * phase + rng.uniform(0, 2 * np.pi))
        chop += np.cos(phase)
    tonal /= np.sqrt(np.mean(tonal ** 2))
    broad = shaped_noise(rng, n, lambda f: hp(f, 110, 2) * lp(f, 2400, 2) / np.sqrt(np.maximum(f, 20) / 200))
    broad *= 1.0 + 0.3 * chop / 4
    x = tonal + 0.45 * broad
    x = filt(x, lambda f: hp(f, 70, 2) * lp(f, 3200, 2))
    return set_rms(x, -18)


# ------------------------------------------------------------------ rüzgâr
def wind(rng, period=40.0, snowy=False):
    """Bozkır rüzgârı: alçak frekanslı uğultu ve ara ara gelen esintiler (esinti gelince ses parlaklaşır).
    Karlı dağlarda kar sesi yutar: daha boğuk, esintiler daha belirgin, çok hafif kar tanesi hışırtısı."""
    n = int(SR * period)
    t = np.arange(n) / SR
    g = 0.58 + 0.42 * slow(rng, t, period, range(1, 14), tilt=0.8)
    if snowy:
        g = 0.5 + 0.5 * slow(rng, t, period, range(1, 12), tilt=0.7)
    g = np.clip(g, 0.15, 1.0)
    body = shaped_noise(rng, n, lambda f: hp(f, 28, 2) * lp(f, 520 if snowy else 800, 2) / np.maximum(f, 30) ** 0.5)
    air = shaped_noise(rng, n, lambda f: hp(f, 260, 2) * lp(f, 1100 if snowy else 1500, 2))
    x = body * g + 0.45 * air * g ** 2.2
    if snowy:
        hiss = shaped_noise(rng, n, lambda f: hp(f, 2500, 2) * lp(f, 6000, 2))
        x += 0.05 * hiss * g ** 3
    return set_rms(x, -22)


# ------------------------------------------------------------------ ırmak
def river(rng, period=30.0):
    """Geniş ve sakin akan ırmak: sürekli su hışırtısı ve küçük kabarcık/çağıltı sesleri
    (yükselen perdeli, hızla sönen kısa tonlar; Minnaert kabarcık titreşimi gibi)."""
    n = int(SR * period)
    t = np.arange(n) / SR
    wash = shaped_noise(rng, n, lambda f: hp(f, 90, 2) * lp(f, 1700, 2) / np.sqrt(np.maximum(f, 40) / 100))
    wash *= 0.9 + 0.1 * slow(rng, t, period, range(2, 20))
    babble = np.zeros(n)
    for _ in range(int(period * 26)):
        f0 = np.exp(rng.uniform(np.log(260), np.log(1150)))
        tau = rng.uniform(0.006, 0.022)
        m = int(SR * tau * 6)
        tt = np.arange(m) / SR
        blip = np.sin(2 * np.pi * f0 * (tt + 0.5 * 9.0 * tt ** 2)) * np.exp(-tt / tau) * (1 - np.exp(-tt / 0.0015))
        s = rng.integers(n)
        idx = (s + np.arange(m)) % n                       # döngünün sonundan başa sarar
        babble[idx] += rng.uniform(0.2, 1.0) * blip
    babble /= np.sqrt(np.mean(babble ** 2))
    x = wash + 0.32 * babble
    x = filt(x, lambda f: hp(f, 60, 2) * lp(f, 2600, 2))
    return set_rms(x, -20)


# ------------------------------------------------------------------ deniz
def surf(rng, period=40.0):
    """Akdeniz kıyısı: 7-10 saniyede bir yumuşakça kıyıya vuran dalga (yükselen uğultu, kırılma, köpüklü çekilme)
    ve arada çakıllar arasından çekilen suyun hışırtısı. Sert patlama yok: dalgalar yavaş yükselir, yavaş söner."""
    n = int(SR * period)
    t = np.arange(n) / SR
    body = shaped_noise(rng, n, lambda f: hp(f, 40, 2) * lp(f, 900, 2) / np.maximum(f, 30) ** 0.4)
    foam = shaped_noise(rng, n, lambda f: hp(f, 400, 2) * lp(f, 3000, 2))
    env_b = np.zeros(n)
    env_f = np.zeros(n)
    k, tk = 0, 0.0
    while tk < period - 0.5:
        rise, fall = rng.uniform(1.4, 2.2), rng.uniform(3.0, 4.5)
        amp = rng.uniform(0.6, 1.0)
        dt = (t - tk) % period                       # döngünün sonundan başa sarar
        e = np.where(dt < rise, (dt / rise) ** 2, np.exp(-(dt - rise) / fall))
        e = np.where(dt < rise + 6 * fall, e, 0.0)
        env_b += amp * e
        ef = np.where((dt > rise * 0.8) & (dt < rise + 5 * fall), np.exp(-(dt - rise * 0.8) / (fall * 0.8)), 0.0)
        env_f += amp * ef * np.clip((dt - rise * 0.8) / 0.4, 0, 1)
        tk += rng.uniform(7.0, 10.0)
        k += 1
    x = body * (0.25 + env_b) + 0.55 * foam * env_f
    x = filt(x, lambda f: hp(f, 35, 2) * lp(f, 3200, 2))
    return set_rms(x, -21)


# ------------------------------------------------------------------ tonlar
def note(f, dur, tau, partials=((1, 1.0), (2, 0.18), (3, 0.05))):
    """Yumuşak çan/kalimba benzeri nota: 8 ms yumuşak giriş, üst harmonikler daha çabuk söner."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for k, a in partials:
        x += a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * k ** 0.7 / tau)
    k = int(n * 0.35)                                  # notanın sonu yumuşakça sıfıra iner (tık yok)
    x[-k:] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, k))
    return x * fade(n, 8)


def seq(notes, total):
    x = np.zeros(int(SR * total))
    for start, y in notes:
        s = int(SR * start)
        x[s:s + len(y)] += y[:len(x) - s]
    x = filt(x, lambda f: lp(f, 4500, 2))
    x[-int(SR * 0.05):] *= np.linspace(1, 0, int(SR * 0.05))
    return x


def cues():
    tri = ((1, 1.0), (3, 0.08), (5, 0.025))           # üçgen dalgaya yakın: yumuşak ama "uyarı" rengi
    out = {
        # olumlu: iki nota yukarı (Mi5 → La5)
        "olumlu.wav": set_peak(seq([(0.0, note(659.3, 0.9, 0.32)), (0.11, note(880.0, 1.0, 0.36))], 1.15), -10),
        # uyarı: iki nota aşağı (La4 → Fa4), daha kalın
        "uyari.wav": set_peak(seq([(0.0, note(440.0, 0.8, 0.28, tri)), (0.16, note(349.2, 0.9, 0.32, tri))], 1.1), -10),
        # görev tamam: Do-Mi-Sol-Do arpej, son nota uzun
        "tamam.wav": set_peak(seq([(0.0, note(523.3, 1.2, 0.4)), (0.12, note(659.3, 1.2, 0.4)),
                                   (0.24, note(784.0, 1.2, 0.45)), (0.36, note(1046.5, 1.8, 0.6))], 2.3), -9),
    }
    # düğme tıkı: çok kısa, boğuk "tık" (yüksek frekans yok)
    n = int(SR * 0.04)
    t = np.arange(n) / SR
    tik = np.sin(2 * np.pi * 1250 * t) * np.exp(-t / 0.004) + 0.5 * np.sin(2 * np.pi * 620 * t) * np.exp(-t / 0.006)
    tik = filt(tik * fade(n, 0.6), lambda f: lp(f, 3500, 2))
    out["tik.wav"] = set_peak(tik, -16)
    return out


def main():
    rng = np.random.default_rng(2204)
    save("pervane.wav", rotor(rng))
    save("ruzgar.wav", wind(rng))
    save("ruzgar_kar.wav", wind(rng, snowy=True))
    save("irmak.wav", river(rng))
    save("dalga.wav", surf(rng))
    for name, x in cues().items():
        save(name, x)


if __name__ == "__main__":
    main()
