#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_simplified.py —— 现代简体字笔画数据构建器

用途：
    梅花易数姓名起卦一律以**现代简体字（规范字形）的实际笔画**计数，
    不用康熙繁体笔画。本脚本从 Unicode Unihan 数据库的 kTotalStrokes
    字段提取每个字的现代规范总笔画，生成 assets/simplified_strokes.json。

数据来源：
    Unihan_IRGSources.txt 的 kTotalStrokes（覆盖 10 万余字，中国大陆
    规范字形口径）。繁体字/异体字通过 Unihan_Variants.txt 的
    kSimplifiedVariant 建立「繁→简」映射：用户输入繁体时，先映射到
    对应简体字再取简体笔画，确保起卦不受字体变体影响。

用法：
    python build_simplified.py [Unihan.zip 或 Unihan_IRGSources.txt 路径]
    未给路径时依次尝试：本目录上级 assets/Unihan.zip、脚本同目录、
    环境变量 UNIHAN_ZIP；都没有则尝试联网下载（仅构建期需要网络）。

产出（assets/simplified_strokes.json）：
    {
      "_meta": {...},
      "strokes": {简体字: 现代规范笔画},
      "t2s":     {繁体字: 对应简体字}   # 仅收录映射目标在 strokes 内的字对
    }
"""

import json
import os
import sys
import urllib.request
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE_DIR, "assets")
KANGXI_PATH = os.path.join(ASSETS, "kangxi_strokes.json")
OUT_PATH = os.path.join(ASSETS, "simplified_strokes.json")

UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"


def _char_of(cp_field: str) -> str:
    """'U+5218' -> '刘'。取第一个码位（kSimplifiedVariant 可列多个候选）。"""
    first = cp_field.split()[0]
    return chr(int(first[2:], 16))


def _load_kangxi_chars() -> set:
    with open(KANGXI_PATH, encoding="utf-8") as f:
        return set(json.load(f)["chars"].keys())


def _find_irg_source(arg: str = "") -> str:
    """定位 Unihan_IRGSources.txt（支持直接给 txt / 给 zip / 自动下载）。"""
    cand = []
    if arg:
        cand.append(arg)
    for env in ("UNIHAN_ZIP", "UNIHAN_IRG"):
        if os.environ.get(env):
            cand.append(os.environ[env])
    here = os.path.dirname(os.path.abspath(__file__))
    cand += [
        os.path.join(ASSETS, "Unihan.zip"),
        os.path.join(here, "Unihan.zip"),
        os.path.join(here, "Unihan_IRGSources.txt"),
        os.path.join(os.path.dirname(here), ".unihan_tmp", "Unihan.zip"),
    ]
    for p in cand:
        if p and os.path.isfile(p):
            if p.endswith(".zip"):
                try:
                    with zipfile.ZipFile(p) as z:
                        if "Unihan_IRGSources.txt" in z.namelist() \
                                and "Unihan_Variants.txt" in z.namelist():
                            return p
                except zipfile.BadZipFile:
                    continue
            else:
                return p
    # 自动下载（仅构建期）
    dest = os.path.join(ASSETS, "Unihan.zip")
    print(f"[build] 未找到本地 Unihan 数据，开始下载 {UNIHAN_URL}")
    urllib.request.urlretrieve(UNIHAN_URL, dest)
    return dest


def _read_fields(path: str):
    """返回 (irg_text, variants_text)。path 可为 zip 或 txt。"""
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return (z.read("Unihan_IRGSources.txt").decode("utf-8", "ignore"),
                    z.read("Unihan_Variants.txt").decode("utf-8", "ignore"))
    # 纯 txt 时变体表尝试同目录 zip/txt，找不到则无繁转简
    with open(path, encoding="utf-8", errors="ignore") as f:
        irg = f.read()
    var = ""
    for alt in (path.replace("IRGSources", "Variants"),
                os.path.join(os.path.dirname(path), "Unihan_Variants.txt")):
        if os.path.isfile(alt):
            with open(alt, encoding="utf-8", errors="ignore") as f:
                var = f.read()
            break
    return irg, var


def build(arg: str = "") -> dict:
    targets = _load_kangxi_chars()
    print(f"[build] 康熙笔画库 {len(targets)} 字，作为收录范围")

    irg, var = _read_fields(_find_irg_source(arg))

    strokes = {}
    for line in irg.splitlines():
        if "\tkTotalStrokes\t" not in line:
            continue
        cp, _, val = line.split("\t", 2)
        ch = chr(int(cp[2:], 16))
        if ch not in targets:
            continue
        strokes[ch] = int(val.split()[0])   # 首值=中国大陆规范字形笔画

    # 繁→简映射：凡 kSimplifiedVariant 指向另一规范简体字的，都建立映射；
    # 用户输入繁体（如 劉/華）时先映射到简体（刘/华）再取简体笔画，
    # 确保「不得使用繁体笔画起卦」对繁体输入同样成立。
    t2s = {}
    for line in var.splitlines():
        if not line.startswith("U+") or "\tkSimplifiedVariant\t" not in line:
            continue
        cp, _, simp_field = line.split("\t", 2)
        trad = chr(int(cp[2:], 16))
        if trad not in targets:
            continue
        for cand in simp_field.split():
            simp = _char_of(cand)
            if simp != trad and simp in strokes:
                t2s[trad] = simp
                break

    print(f"[build] 简体笔画收录 {len(strokes)} 字；繁→简映射 {len(t2s)} 对")
    missing = sorted(targets - set(strokes) - set(t2s))
    if missing:
        print(f"[WARN] {len(missing)} 字无 kTotalStrokes：{''.join(missing[:40])}"
              + ("…" if len(missing) > 40 else ""))
    return {"strokes": strokes, "t2s": t2s, "missing": missing}


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    data = build(arg)
    missing = data.pop("missing")
    payload = {
        "_meta": {
            "source": "Unicode Unihan kTotalStrokes（现代简体规范笔画）",
            "version": "1.0",
            "char_count": len(data["strokes"]),
            "t2s_count": len(data["t2s"]),
            "missing_count": len(missing),
            "missing": missing,
            "updated": "2026-10-22",
            "note": "梅花易数起卦专用：一律取现代简体字笔画，不用康熙繁体笔画；"
                    "用户输入繁体字时先经 t2s 映射为简体再计笔画",
        },
        "strokes": dict(sorted(data["strokes"].items(), key=lambda kv: (kv[1], kv[0]))),
        "t2s": dict(sorted(data["t2s"].items())),
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"[OK] 已写入 {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
