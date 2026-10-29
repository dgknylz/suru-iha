#!/bin/bash
# Unity'yi açmadan C# betiklerini derleyip hata denetimi yapar (~30 s; full_build.ps1'den önce çalıştır).
#   bash tools/cs_check.sh
# Unity'nin kendi Roslyn derleyicisi (dotnet) ile önce Scripts, sonra ona dayanan Editor betikleri derlenir.
# Başvurular: NetStandard 2.1, UnityEngine modülleri ve projenin önceden derlenmiş paket kütüphaneleri
# (C:\SuruIHA\SuruIHA_Unity\Library\ScriptAssemblies; Unity'de proje bir kez açılmış olmalı).
# UnityEditor.dll eklenmez: UnityEditor.CoreModule ile aynı türleri içerir, çakışma hatası verir.
U="/c/Program Files/Unity/Hub/Editor/6000.3.1f1/Editor/Data"
SA="/c/SuruIHA/SuruIHA_Unity/Library/ScriptAssemblies"
REPO="$(cd "$(dirname "$0")/.." && pwd)/unity/Assets/SuruIHA"
OUT="${TMP:-/tmp}/suru_cs_check"
mkdir -p "$OUT"
fail=0

compile() {   # $1: klasör (Scripts | Editor), $2...: ek başvurular
    local dir="$1"; shift
    local rsp="$OUT/$dir.rsp" dll="$OUT/$dir.dll"
    rm -f "$dll"
    echo "-nologo -noconfig -nostdlib+ -target:library -langversion:9 -nowarn:CS0618,CS0649,CS0414,CS0169,CS0067" > "$rsp"
    echo "-define:UNITY_EDITOR;UNITY_STANDALONE_WIN;UNITY_2023_1_OR_NEWER;UNITY_6000_0_OR_NEWER -out:\"$(cygpath -w "$dll")\"" >> "$rsp"
    echo "-r:\"$(cygpath -w "$U/NetStandard/ref/2.1.0/netstandard.dll")\"" >> "$rsp"
    for d in "$U/Managed/UnityEngine/"*.dll; do echo "-r:\"$(cygpath -w "$d")\"" >> "$rsp"; done
    for d in "$SA"/*.dll; do case "$(basename "$d")" in Assembly-CSharp*) ;; *) echo "-r:\"$(cygpath -w "$d")\"" >> "$rsp";; esac; done
    for extra in "$@"; do echo "-r:\"$(cygpath -w "$extra")\"" >> "$rsp"; done
    for f in "$REPO/$dir"/*.cs; do echo "\"$(cygpath -w "$f")\"" >> "$rsp"; done
    "/c/Program Files/dotnet/dotnet" "$U/DotNetSdkRoslyn/csc.dll" "@$(cygpath -w "$rsp")" 2>&1 | grep -E "error CS" | head -30
    if [ -f "$dll" ]; then echo "$dir: derlendi"; else echo "$dir: HATA"; fail=1; fi
}

compile Scripts
[ $fail -eq 0 ] && compile Editor "$OUT/Scripts.dll"
exit $fail
