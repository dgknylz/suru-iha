"""Taşınabilir paket: uygulamanın yanına Python'u ve simülasyonu koyar (başka bilgisayarda kurulum gerekmez).

    python tools/make_portable.py [uygulama klasörü]      (varsayılan C:\\SuruIHA\\Build)

<uygulama>/sim altına: python/ (bu bilgisayardaki Python'un yalın kopyası: yorumlayıcı, DLL'ler, standart kütüphane;
deneme, belge ve arayüz kitaplıkları hariç) + yalnızca simülasyonun kullandığı numpy ve scipy, suru/ (arazi yükseklik
haritalarıyla), run_live.py ve run_compare.py. SimLauncher depoyu bulamazsa (jüri bilgisayarı) bu klasörü kullanır.
Sonunda paketteki Python'la simülasyon gerçekten çalıştırılıp denenir.
"""
import os
import shutil
import stat
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = sys.argv[1] if len(sys.argv) > 1 else r"C:\SuruIHA\Build"
SIM = os.path.join(APP, "sim")
SKIP_LIB = {"site-packages", "test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "venv",
            "pydoc_data", "__pycache__", "sqlite3", "curses", "dbm"}


def base_python():
    cfg = os.path.join(REPO, ".venv", "pyvenv.cfg")
    for line in open(cfg, encoding="utf-8"):
        k, _, v = line.partition("=")
        if k.strip() == "home":
            return v.strip()
    return os.path.dirname(sys.executable)


def copytree(src, dst, skip=()):
    def ignore(_, names):
        return [n for n in names if n in skip or n == "__pycache__" or n.endswith(".pyc")]
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def size_mb(path):
    total = 0
    for root, _, files in os.walk(path):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return total / 1e6


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    home = base_python()
    if os.path.exists(SIM):
        def unlock(func, path, _):                  # salt okunur dosyalar (site-packages'tan gelen) silinebilsin
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(SIM, onexc=unlock)
    py = os.path.join(SIM, "python")
    os.makedirs(py)
    for f in os.listdir(home):
        if f.lower().endswith((".exe", ".dll")):
            shutil.copy2(os.path.join(home, f), py)
    copytree(os.path.join(home, "DLLs"), os.path.join(py, "DLLs"))
    copytree(os.path.join(home, "Lib"), os.path.join(py, "Lib"), SKIP_LIB)
    site = os.path.join(REPO, ".venv", "Lib", "site-packages")
    for pkg in ("numpy", "numpy.libs", "scipy", "scipy.libs"):
        if os.path.exists(os.path.join(site, pkg)):
            copytree(os.path.join(site, pkg), os.path.join(py, "Lib", "site-packages", pkg), {"tests"})
    copytree(os.path.join(REPO, "suru"), os.path.join(SIM, "suru"))
    for f in ("run_live.py", "run_compare.py"):
        shutil.copy2(os.path.join(REPO, f), SIM)
    with open(os.path.join(SIM, "BENIOKU.txt"), "w", encoding="utf-8") as f:
        f.write("Sürü İHA simülasyonu (taşınabilir): uygulama bu klasördeki Python'la simülasyonu kendisi başlatır.\n"
                "Kurulum gerekmez. Elle denemek için: python\\python.exe -s run_live.py\n")
    print(f"paket: {SIM} ({size_mb(SIM):.0f} MB)")

    # Deneme: paketteki Python, kullanıcı ortamından bağımsız (-s -E) simülasyonu çalıştırabiliyor mu?
    code = ("import numpy, scipy.optimize, suru; from suru import World, make_config; "
            "w = World(make_config('resilient', 20.0, 0.0, 1, region='divrigi')); "
            "[w.step() for _ in range(200)]; print('deneme tamam', round(w.t, 1), 's, bölge', w.frame()['region'])")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV")}
    env["PATH"] = py + os.pathsep + os.environ.get("SystemRoot", r"C:\Windows")
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([os.path.join(py, "python.exe"), "-s", "-E", "-c", code], cwd=SIM, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.strip() or r.stderr.strip()[-800:])
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
