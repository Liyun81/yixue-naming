#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字义库全量构建器（v1.4.0 起）

职责：把「已有条目 + 词性补录 + 繁简继承 + 分批新撰数据」合并为统一 schema 的
assets/char_meaning.json，并做全量校验与覆盖率报告。

统一条目 schema（向后兼容：analyze.py 读的 yi/xiang/wuxing/yong 均保留）：
    char      汉字
    pinyin    带调拼音（自动从 assets/pinyin.json 关联，零手工）
    pos       词性（名/动/形/数/量/代/副/介/连/助/叹/拟声/姓）
    yi        释义（通行训释：说文/康熙/现代汉语词典）
    example   例句（常用词、成语或典故出处）
    xiang     取名意象（full 层必备；basic 层沿用 example）
    wuxing    字义五行（木/火/土/金/水；按字所指事物传统归类）
    yong      取名导向（full 层有；basic 层为空串）
    level     条目完整度：full（齐全）/ basic（无专属意象与导向）
    variant_of  仅繁简继承条目有：所继承的简体字

用法：
    python scripts/build_meaning_full.py            # 构建并校验
    python scripts/build_meaning_full.py --report   # 只出覆盖率报告
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")

# 合法取值
WUXING = ("木", "火", "土", "金", "水")
POS = ("名", "动", "形", "数", "量", "代", "副", "介", "连", "助", "叹", "拟声", "姓")

# 条目字段顺序（保证输出稳定）
FIELDS = ("char", "pinyin", "pos", "yi", "example", "xiang",
          "wuxing", "yong", "level")

# 机构/商号用字：笔画、简体、拼音三库（各 2706 字）未按字义库收录这些字，
# 故拼音库无其读音，此处内置补齐，保证「拼音」字段无一为空。
EXTRA_PINYIN = {
    "兴": "xīng", "裕": "yù", "宽": "kuān", "铮": "zhēng", "钊": "zhāo",
    "旭": "xù", "莺": "yīng", "娴": "xián", "姝": "shū", "初": "chū",
    "意": "yì", "紫": "zǐ", "邦": "bāng", "巽": "xùn", "艮": "gèn",
    "兑": "duì", "斋": "zhāi", "源": "yuán", "技": "jì", "医": "yī",
    "饰": "shì", "教": "jiào", "投": "tóu", "创": "chuàng", "众": "zhòng",
    "汇": "huì", "莉": "lì", "炎": "yán", "烈": "liè", "暄": "xuān",
}


def _load(name: str) -> dict:
    with open(os.path.join(ASSETS, name), encoding="utf-8") as f:
        return json.load(f)


def _dump(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load_batches() -> List[Tuple[str, str, str, str, str, str]]:
    """载入 scripts/meaning_data/ 下所有分批数据（batch_*.py 的 ROWS）。

    行格式（6 元组）：
        (char, pos, yi, example, wuxing, yong)
    yong 为空串即判为 basic 层。
    """
    import importlib.util

    d = os.path.join(HERE, "meaning_data")
    rows: List[Tuple[str, str, str, str, str, str]] = []
    if not os.path.isdir(d):
        return rows
    for fn in sorted(os.listdir(d)):
        if not (fn.startswith("batch_") and fn.endswith(".py")):
            continue
        spec = importlib.util.spec_from_file_location("bd_" + fn[:-3], os.path.join(d, fn))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows.extend(getattr(mod, "ROWS", []))
    return rows


def load_legacy_pos() -> Dict[str, str]:
    """载入已有条目的词性补录（legacy_pos.py 的 POS_ROWS：[(char, pos), ...]）"""
    import importlib.util

    p = os.path.join(HERE, "meaning_data", "legacy_pos.py")
    if not os.path.exists(p):
        return {}
    spec = importlib.util.spec_from_file_location("legacy_pos", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(getattr(mod, "POS_ROWS", []))


def norm(entry: dict) -> dict:
    """按 FIELDS 排序输出，缺字段补空串。"""
    out = {k: entry.get(k, "") for k in FIELDS}
    if entry.get("variant_of"):
        out["variant_of"] = entry["variant_of"]
    return out


def build() -> Tuple[dict, List[str]]:
    """合并全部来源，返回 (新字义库, 警告列表)"""
    warn: List[str] = []

    me = _load("char_meaning.json")
    pinyin = _load("pinyin.json")
    simp = _load("simplified_strokes.json")

    py_chars: Dict[str, dict] = pinyin.get("chars", {})
    t2s: Dict[str, str] = simp.get("t2s") or {}

    old: Dict[str, dict] = me.get("chars", {})

    # ① 已有条目升级：补 pinyin / pos / example / level，保留 yi/xiang/wuxing/yong
    out: Dict[str, dict] = {}
    legacy_pos = load_legacy_pos()
    for ch, e in old.items():
        p = py_chars.get(ch, {}).get("pinyin", "") or EXTRA_PINYIN.get(ch, "")
        if not p:
            warn.append(f"拼音库缺「{ch}」，pinyin 留空")
        ent = dict(e)
        ent["char"] = ch
        ent["pinyin"] = p
        # 幂等：已有字段保留，缺失才补（否则重复构建会把继承条目的字段抹空）
        ent["pos"] = ent.get("pos") or legacy_pos.get(ch, "")
        if not ent["pos"]:
            warn.append(f"已有条目「{ch}」缺词性")
        ent["example"] = ent.get("example") or ent.get("xiang", "")
        ent["level"] = "full" if (ent.get("yong") and ent.get("xiang")) else "basic"
        out[ch] = norm(ent)

    # ② 分批新撰数据（覆盖式；pinyin 自动关联）
    rows = load_batches()
    seen: Dict[str, int] = {}
    for char, pos, yi, example, wuxing, yong in rows:
        if char in seen:
            warn.append(f"重复定义「{char}」（第 {seen[char]} 行与当前行），保留后者")
        seen[char] = seen.get(char, 0) + 1
        p = py_chars.get(char, {}).get("pinyin", "") or EXTRA_PINYIN.get(char, "")
        if not p:
            warn.append(f"拼音库缺「{char}」，pinyin 留空")
        ent = {
            "char": char,
            "pinyin": p,
            "pos": pos,
            "yi": yi,
            "example": example,
            "xiang": example,
            "wuxing": wuxing,
            "yong": yong,
            "level": "full" if (yong and example) else "basic",
        }
        out[char] = norm(ent)

    # ③ 繁简继承：缺字若在 t2s 映射中且简体已有条目，则复制字义
    inherited = 0
    repaired = 0
    for ch in list(py_chars):
        s = t2s.get(ch)
        if not s or s not in out:
            continue
        src = out[s]
        if ch in out:
            # 已在库中的继承条目：若字段缺失（重复构建所致），从源字修补（自愈）
            cur = out[ch]
            if cur.get("variant_of") == s and (
                    not cur.get("pos") or not cur.get("example")):
                fixed = dict(cur)
                fixed["pos"] = cur.get("pos") or src.get("pos", "")
                fixed["example"] = cur.get("example") or src.get("example", "")
                fixed["xiang"] = cur.get("xiang") or src.get("xiang", "")
                out[ch] = norm(fixed)
                repaired += 1
            continue
        ent = dict(src)
        ent["char"] = ch
        ent["pinyin"] = (py_chars.get(ch, {}).get("pinyin", "")
                         or EXTRA_PINYIN.get(ch, ""))
        ent["variant_of"] = s
        out[ch] = norm(ent)
        inherited += 1

    out = dict(sorted(out.items()))

    meta = {
        "count": len(out),
        "note": (
            "「wuxing」为字义五行（按字所指事物的传统归类），与五格数理五行、"
            "五音五行各为体系；字义取通行训释，仅供取名参考。"
        ),
        "schema": list(FIELDS),
        "levels": {
            "full": sum(1 for v in out.values() if v.get("level") == "full"),
            "basic": sum(1 for v in out.values() if v.get("level") == "basic"),
        },
        "sources": {
            "legacy": len(old),
            "batches": len(rows),
            "inherited": inherited,
            "repaired": repaired,
        },
    }
    return {"meta": meta, "chars": out}, warn


def validate(data: dict) -> List[str]:
    """schema 校验：字段齐全、类型一致、拼音对齐、五行与词性合法、层级合法"""
    err: List[str] = []
    pinyin = _load("pinyin.json")
    py_chars = pinyin.get("chars", {})
    chars = data.get("chars", {})

    for ch, e in chars.items():
        tag = f"「{ch}」"
        for k in FIELDS:
            if k not in e:
                err.append(f"{tag} 缺字段 {k}")
            elif not isinstance(e[k], str):
                err.append(f"{tag} 字段 {k} 非字符串")
        if not e.get("yi"):
            err.append(f"{tag} 释义为空")
        if e.get("wuxing") and e["wuxing"] not in WUXING:
            err.append(f"{tag} 五行非法：{e['wuxing']}")
        if e.get("pos") and e["pos"] not in POS:
            err.append(f"{tag} 词性非法：{e['pos']}")
        if e.get("level") not in ("full", "basic"):
            err.append(f"{tag} 层级非法：{e.get('level')}")
        if e.get("level") == "full" and not (e.get("yong") and e.get("xiang")):
            err.append(f"{tag} 标为 full 但缺 yong/xiang")
        # 拼音必须与 pinyin.json 一致
        p = py_chars.get(ch, {}).get("pinyin")
        if p and e.get("pinyin") and e["pinyin"] != p:
            err.append(f"{tag} 拼音与拼音库不一致：{e['pinyin']} != {p}")
    return err


def coverage(data: dict) -> dict:
    """覆盖率报告：以三库并集为基准"""
    ka = _load("kangxi_strokes.json")
    si = _load("simplified_strokes.json")
    py = _load("pinyin.json")
    base = set(ka.get("chars", {})) | set(si.get("strokes", {})) | set(py.get("chars", {}))
    have = set(data.get("chars", {}))
    missing = sorted(base - have)
    extra = sorted(have - base)
    lv = {"full": 0, "basic": 0}
    for c in have:
        lv[data["chars"][c].get("level", "basic")] = lv.get(
            data["chars"][c].get("level", "basic"), 0) + 1
    return {
        "基准(三库并集)": len(base),
        "已覆盖": len(base & have),
        "覆盖中但不在基准(机构/姓氏用字)": len(extra),
        "仍缺": len(missing),
        "缺失字": "".join(missing),
        "full 层": lv["full"],
        "basic 层": lv["basic"],
        "覆盖率": f"{(len(base & have) / len(base) * 100) if base else 0:.2f}%",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="字义库全量构建器")
    ap.add_argument("--report", action="store_true", help="只输出覆盖率报告")
    ap.add_argument("--dry-run", action="store_true", help="只校验不写盘")
    a = ap.parse_args()

    if a.report:
        print(json.dumps(coverage(_load("char_meaning.json")), ensure_ascii=False, indent=2))
        return 0

    data, warn = build()
    err = validate(data)

    print(f"合并完成：{data['meta']['count']} 条"
          f"（已有 {data['meta']['sources']['legacy']} + "
          f"新撰 {data['meta']['sources']['batches']} + "
          f"繁简继承 {data['meta']['sources']['inherited']}）")

    if warn:
        print(f"\n警告 {len(warn)} 条：")
        for w in warn[:30]:
            print("  ！", w)
        if len(warn) > 30:
            print(f"  … 另有 {len(warn) - 30} 条")

    cov = coverage(data)
    print("\n覆盖率报告：")
    for k, v in cov.items():
        if k == "缺失字" and len(str(v)) > 200:
            print(f"  {k}: {str(v)[:200]}…（共 {cov['仍缺']} 字）")
        else:
            print(f"  {k}: {v}")

    if err:
        print(f"\n校验失败 {len(err)} 项：")
        for e in err[:30]:
            print("  ✗", e)
        if len(err) > 30:
            print(f"  … 另有 {len(err) - 30} 项")
        return 1

    print("\n校验：schema 全通过")
    if a.dry_run:
        print("（--dry-run，未写盘）")
        return 0

    p = os.path.join(ASSETS, "char_meaning.json")
    _dump(p, data)
    print(f"已写入 {p}（{os.path.getsize(p)} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
