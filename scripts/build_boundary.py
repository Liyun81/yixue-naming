#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
边界字补录器（v1.4.0）

背景：字义库为机构/商号模式收录了 30 个用字（众兑兴创初医姝娴宽巽意技投教
斋旭暄汇源炎烈紫艮莉莺裕邦钊铮饰），但这批字未进康熙笔画库、简体笔画库与
拼音库，导致姓名中一旦出现这些字即报 missing_stroke 而无法分析。

本脚本按《康熙字典》部首笔画与现代简体规范笔画补录这 30 字，并生成与既有
拼音库同构的读音条目（五音/平仄/韵母类型/四呼按既有库规则推导），使
「康熙笔画 / 简体笔画 / 拼音 / 字义」四库对齐为 2736 字，零缺失。

改动一律写入各库 _meta._history，便于后续人工校对与追溯。

用法：
    python scripts/build_boundary.py            # 补录并校验
    python scripts/build_boundary.py --dry-run  # 只校验不写盘
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")

# (字, 康熙笔画, 简体笔画, 带调拼音, 无声调音节, 声调, 声母, 韵母)
# 康熙笔画依《康熙字典》部首归部；繁简不同形者取繁体字形笔画（如 众→衆11）。
BOUNDARY = [
    ("众", 11, 6, "zhòng", "zhong", 4, "zh", "ong"),
    ("兑", 7, 7, "duì", "dui", 4, "d", "ui"),
    ("兴", 16, 6, "xīng", "xing", 1, "x", "ing"),
    ("创", 12, 6, "chuàng", "chuang", 4, "ch", "uang"),
    ("初", 7, 7, "chū", "chu", 1, "ch", "u"),
    ("医", 18, 7, "yī", "yi", 1, "", "yi"),
    ("姝", 9, 9, "shū", "shu", 1, "sh", "u"),
    ("娴", 15, 10, "xián", "xian", 2, "x", "ian"),
    ("宽", 14, 10, "kuān", "kuan", 1, "k", "uan"),
    ("巽", 12, 12, "xùn", "xun", 4, "x", "un"),
    ("意", 13, 13, "yì", "yi", 4, "", "yi"),
    ("技", 8, 8, "jì", "ji", 4, "j", "i"),
    ("投", 8, 8, "tóu", "tou", 2, "t", "ou"),
    ("教", 11, 11, "jiào", "jiao", 4, "j", "iao"),
    ("斋", 17, 10, "zhāi", "zhai", 1, "zh", "ai"),
    ("旭", 6, 6, "xù", "xu", 4, "x", "u"),
    ("暄", 13, 13, "xuān", "xuan", 1, "x", "uan"),
    ("汇", 13, 5, "huì", "hui", 4, "h", "ui"),
    ("源", 14, 14, "yuán", "yuan", 2, "", "yuan"),
    ("炎", 8, 8, "yán", "yan", 2, "", "yan"),
    ("烈", 10, 10, "liè", "lie", 4, "l", "ie"),
    ("紫", 11, 11, "zǐ", "zi", 3, "z", "i"),
    ("艮", 6, 6, "gèn", "gen", 4, "g", "en"),
    ("莉", 13, 10, "lì", "li", 4, "l", "i"),
    ("莺", 21, 10, "yīng", "ying", 1, "", "ying"),
    ("裕", 13, 13, "yù", "yu", 4, "", "yu"),
    ("邦", 11, 6, "bāng", "bang", 1, "b", "ang"),
    ("钊", 10, 7, "zhāo", "zhao", 1, "zh", "ao"),
    ("铮", 16, 11, "zhēng", "zheng", 1, "zh", "eng"),
    ("饰", 14, 8, "shì", "shi", 4, "sh", "i"),
]

# 五音：按发音部位（宫=喉/零声母 g k h，商=齿 zh ch sh r z c s，
# 角=牙 j q x，徵=舌 d t n l，羽=唇 b p m f）
WUYIN_BY_INITIAL = {
    "": ("宫", "土"), "g": ("宫", "土"), "k": ("宫", "土"), "h": ("宫", "土"),
    "zh": ("商", "金"), "ch": ("商", "金"), "sh": ("商", "金"), "r": ("商", "金"),
    "z": ("商", "金"), "c": ("商", "金"), "s": ("商", "金"),
    "j": ("角", "木"), "q": ("角", "木"), "x": ("角", "木"),
    "d": ("徵", "火"), "t": ("徵", "火"), "n": ("徵", "火"), "l": ("徵", "火"),
    "b": ("羽", "水"), "p": ("羽", "水"), "m": ("羽", "水"), "f": ("羽", "水"),
}

# 四呼：与既有库一致——只分开口/齐齿/合口三呼（ü 类并入合口）
def hu_of(initial: str, final: str) -> str:
    if final.startswith(("u", "ü")):
        return "合口"
    if final.startswith(("i", "y")):
        return "齐齿"
    return "开口"


def final_type_of(final: str) -> str:
    return "鼻" if final.endswith(("n", "ng")) else "元"


def load(name: str) -> dict:
    with open(os.path.join(ASSETS, name), encoding="utf-8") as f:
        return json.load(f)


def dump(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def add_history(data: dict, note: str) -> None:
    meta = data.setdefault("_meta", {})
    meta.setdefault("_history", []).append(note)


def main() -> int:
    ap = argparse.ArgumentParser(description="边界字（机构/商号用字）四库补录")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    kx = load("kangxi_strokes.json")
    sm = load("simplified_strokes.json")
    py = load("pinyin.json")
    me = load("char_meaning.json")

    kx_chars = kx.setdefault("chars", {})
    sm_strokes = sm.setdefault("strokes", {})
    py_chars = py.setdefault("chars", {})

    added_kx = added_sm = added_py = 0
    for ch, kx_n, sm_n, pny, plain, tone, init, fin in BOUNDARY:
        if ch not in kx_chars:
            kx_chars[ch] = kx_n
            added_kx += 1
        if ch not in sm_strokes:
            sm_strokes[ch] = sm_n
            added_sm += 1
        if ch not in py_chars:
            wuyin, wx = WUYIN_BY_INITIAL[init]
            py_chars[ch] = {
                "pinyin": pny,
                "plain": plain,
                "tone": tone,
                "initial": init,
                "final": fin,
                "wuyin": wuyin,
                "wuxing": wx,
                "pingze": "平" if tone in (1, 2) else "仄",
                "final_type": final_type_of(fin),
                "hu": hu_of(init, fin),
            }
            added_py += 1

    # 校验：四库对齐 + 字义库覆盖
    base = set(kx_chars) | set(sm_strokes) | set(py_chars)
    missing = sorted(base - set(me.get("chars", {})))
    err = []
    if missing:
        err.append(f"字义库仍缺 {len(missing)} 字：{''.join(missing)}")
    for ch, _, _, _, _, _, _, _ in BOUNDARY:
        if not (ch in kx_chars and ch in sm_strokes and ch in py_chars and ch in me["chars"]):
            err.append(f"「{ch}」四库未齐")

    print(f"补录：康熙笔画 +{added_kx}，简体笔画 +{added_sm}，拼音 +{added_py}")
    print(f"四库并集：{len(base)} 字　字义库：{len(me['chars'])} 条"
          f"　字义库缺失：{len(missing)}")

    if err:
        print("\n校验失败：")
        for e in err[:20]:
            print("  ✗", e)
        return 1
    print("校验：四库齐备、字义零缺失")

    if a.dry_run:
        print("（--dry-run，未写盘）")
        return 0

    add_history(kx, "v1.4.0 补录 30 个机构/商号边界字（康熙笔画依《康熙字典》部首归部，"
                    "繁简异形者取繁体字形笔画），四库对齐 2736 字")
    add_history(sm, "v1.4.0 补录 30 个机构/商号边界字的现代简体规范笔画")
    add_history(py, "v1.4.0 补录 30 个机构/商号边界字读音（五音/平仄/韵母类型/四呼"
                    " 按既有库规则推导）")
    dump(os.path.join(ASSETS, "kangxi_strokes.json"), kx)
    dump(os.path.join(ASSETS, "simplified_strokes.json"), sm)
    dump(os.path.join(ASSETS, "pinyin.json"), py)
    print("已写盘：kangxi_strokes.json / simplified_strokes.json / pinyin.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
