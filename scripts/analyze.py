#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze.py —— 易学姓名学解析 CLI（字义 + 五格 + 五音 + 梅花易数 + 八字原盘）

用法示例：
    python analyze.py --surname 李 --given 明华 --gender male
    python analyze.py --full 欧阳明华 --json
    python analyze.py --surname 王 --candidates "浩然,宇轩,子睿"
    python analyze.py --org "同和堂"                    # 公司/团队名
    python analyze.py --surname 李 --given 明华 --branch 午   # 指定月令
    python analyze.py --surname 李 --given 明华 --no-meihua
    python analyze.py --full 李苏翰 --birth "1990-05-20 14:30" --city 成都
    python analyze.py --full 李苏翰 --birth "1990-05-20 14:30" --city 成都 --no-dst
    python analyze.py --full 李苏翰 --birth "1987-07-15 15:00" --city 上海 --tz +8
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import bazi as bz_mod  # noqa: E402
import meihua as mh_mod  # noqa: E402
import synthesis as syn_mod  # noqa: E402
import wuyin as wy_mod  # noqa: E402
from wuge import (WugeConfig, WugeError, analyze as wuge_analyze,  # noqa: E402
                  to_json, wuxing_of)

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

GRID_LABEL = {
    "tian": ("天格", "祖运"),
    "ren": ("人格", "主运"),
    "di": ("地格", "前运"),
    "wai": ("外格", "副运"),
    "zong": ("总格", "后运"),
}

# 六维解读的展示顺序与标题（顺序固定，不随数据键序变化）
DIMENSION_LABEL = (
    ("character", "性格"),
    ("career", "事业"),
    ("wealth", "财运"),
    ("health", "健康"),
    ("marriage", "婚姻"),
    ("family", "家庭"),
)
DISCLAIMER = ("本结果基于周易易理与传统姓名学理论生成，仅供审美与文化参考，"
              "不具备科学预测效力；不构成命运决断，亦不可作为人生、健康、"
              "婚姻、投资等任何实际决策依据。")
# 各段落末尾附带的短免责（与图内免责同文）
SECTION_DISCLAIMER = "※ 仅供审美与文化参考，不具备科学预测效力。"
HAN = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]+$")
STRUCT_LABEL = {
    "SS_GG": "单姓单名",
    "SS_GD": "单姓双名",
    "DS_SG": "复姓单名",
    "DS_GD": "复姓双名",
    "EXTENDED": "多字姓（四字以上）",
}


def _wrap_cn(text: str, width: int = 28) -> list:
    """中文折行：优先在标点处断开，长句无标点时硬断。"""
    out: list = []
    cur = ""
    for ch in text:
        cur += ch
        if len(cur) >= width and ch in "，。；：、！？”』）":
            out.append(cur)
            cur = ""
        elif len(cur) >= width + 14:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)

    # 去掉每段首尾空白（拼接处的空格会落到行首），并合并只剩标点的尾段
    out = [c.strip() for c in out if c.strip()]
    while len(out) > 1 and len(out[-1]) <= 2:
        out[-2] += out[-1]
        out.pop()
    return out


# ---------------- 数据 ----------------
def load_json(name):
    path = os.path.join(ASSETS, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


MEANING = load_json("char_meaning.json").get("chars", {})
NUMBERS = load_json("eighty_one_numbers.json").get("numbers", [])


def number_of(no):
    """按 81 数理查表（超过 81 取模）。"""
    if not NUMBERS:
        return {}
    idx = no % 81 or 81
    for n in NUMBERS:
        if n.get("no") == idx:
            return n
    return {}


def meaning_of(ch):
    return MEANING.get(ch)


# ---------------- 综合评分 ----------------
def grade_person(score):
    if score >= 80:
        return "上佳"
    if score >= 70:
        return "佳"
    if score >= 60:
        return "平"
    if score >= 50:
        return "偏弱"
    return "宜斟酌"


def grade_org(score):
    if score >= 80:
        return "气象佳"
    if score >= 70:
        return "气象正"
    if score >= 60:
        return "中平"
    return "宜斟酌"


# ---------------- 个人分析 ----------------
def analyze_person(surname, given, cfg, full=None, month=None,
                   with_wuyin=True, with_meihua=True,
                   birth=None, city=None, longitude=None, tz_offset=None,
                   use_dst=True):
    report = wuge_analyze(surname, given, cfg, full_name=full)
    inp = report["input"]
    s_name, g_name = inp["surname"], inp["given"]
    all_chars = list(s_name + g_name)
    s_strokes = [report["strokes"][c] for c in s_name]
    g_strokes = [report["strokes"][c] for c in g_name]

    # 字义
    meanings = []
    for i, ch in enumerate(all_chars):
        m = meaning_of(ch)
        meanings.append({
            "char": ch,
            "role": "姓" if i < len(s_name) else "名",
            **({"yi": m["yi"], "xiang": m["xiang"], "wuxing": m["wuxing"], "yong": m["yong"]}
               if m else {"yi": None, "note": "字义库未收录，可查《说文解字》或《康熙字典》"}),
        })

    # 五音（以总格五行作参照，看音气与格气是否同向）
    wuyin = None
    wuyin_err = None
    if with_wuyin:
        try:
            wuyin = wy_mod.analyze_wuyin(
                all_chars, len(s_name), ref_wuxing=report["grids"]["zong"]["wuxing"])
        except Exception as e:  # 读音缺失不应中断整体报告
            wuyin_err = str(e)

    # 梅花易数（起卦一律用现代简体字笔画，不用康熙繁体笔画）
    meihua = None
    meihua_err = None
    meihua_strokes = None
    if with_meihua:
        try:
            ms_detail = mh_mod.name_strokes(s_name + g_name)
            missing = [ch for ch, v in ms_detail.items() if v["strokes"] <= 0]
            if missing:
                raise mh_mod.MeihuaError(
                    f"简体笔画库未收录：{'、'.join(missing)}，无法以简体笔画起卦")
            meihua_strokes = ms_detail
            s_simp = [ms_detail[c]["strokes"] for c in s_name]
            g_simp = [ms_detail[c]["strokes"] for c in g_name]
            meihua = mh_mod.analyze_name(s_simp, g_simp, month)
        except Exception as e:
            meihua_err = str(e)

    # 八字原盘（真太阳时）：独立维度，不并入姓名综合分
    bazi = None
    bazi_err = None
    if birth:
        try:
            bazi = bz_mod.analyze_bazi(birth, city=city, longitude=longitude,
                                      tz_offset=tz_offset, use_dst=use_dst)
        except Exception as e:  # 输入错误不应中断整体报告
            bazi_err = str(e)

    parts = {"wuge": report["score"]}
    weights = {"wuge": 0.50}
    if wuyin:
        parts["wuyin"] = wuyin["score"]
        weights["wuyin"] = 0.20
    if meihua:
        parts["meihua"] = meihua["score"]
        weights["meihua"] = 0.30
    total_w = sum(weights.values())
    overall = round(sum(parts[k] * weights[k] for k in parts) / total_w, 1)

    result = {
        "mode": "person",
        "input": inp,
        "strokes": report["strokes"],
        "meanings": meanings,
        "wuge": report,
        "wuyin": wuyin,
        "wuyin_error": wuyin_err,
        "meihua": meihua,
        "meihua_error": meihua_err,
        "meihua_strokes": meihua_strokes,
        "bazi": bazi,
        "bazi_error": bazi_err,
        "parts": parts,
        "overall": overall,
        "overall_grade": grade_person(overall),
        "disclaimer": DISCLAIMER,
    }
    # 出生信息完整性标记（排八字与测名字缺一不可）
    result["birth_missing"] = not birth
    result["city_missing"] = not city and longitude is None

    # 跨体系统合（四维齐备且出生信息完整才生成；缺一维返回 None，不阻断报告）
    result["synthesis"] = syn_mod.cross_analysis(result)
    return result


# ---------------- 机构名分析 ----------------
def analyze_org(name, month=None, with_wuyin=True, with_meihua=True,
                birth=None, city=None, longitude=None, tz_offset=None,
                use_dst=True):
    if not HAN.match(name):
        raise WugeError(f"机构名「{name}」含非汉字字符，本技能只处理汉字名称",
                        name=name)
    strokes = report_strokes(name)
    s = [strokes[c] for c in name]
    total = sum(s)
    num = number_of(total)

    meanings = []
    for ch in name:
        m = meaning_of(ch)
        meanings.append({"char": ch, **({"yi": m["yi"], "xiang": m["xiang"],
                                         "wuxing": m["wuxing"], "yong": m["yong"]}
                                        if m else {"yi": None, "note": "字义库未收录"})})

    wuyin = None
    wuyin_err = None
    if with_wuyin:
        try:
            wuyin = wy_mod.analyze_wuyin(list(name), 0,
                                        ref_wuxing=(num.get("wuxing") if num else None))
        except Exception as e:
            wuyin_err = str(e)

    meihua = None
    meihua_err = None
    meihua_strokes = None
    if with_meihua:
        try:
            ms_detail = mh_mod.name_strokes(name)
            missing = [ch for ch, v in ms_detail.items() if v["strokes"] <= 0]
            if missing:
                raise mh_mod.MeihuaError(
                    f"简体笔画库未收录：{'、'.join(missing)}，无法以简体笔画起卦")
            meihua_strokes = ms_detail
            meihua = mh_mod.analyze_org(
                [ms_detail[ch]["strokes"] for ch in name], month)
        except Exception as e:
            meihua_err = str(e)

    # 负责人八字排盘（机构由法人/负责人发起，八字维度不可或缺）
    bazi = None
    bazi_err = None
    if birth:
        try:
            bazi = bz_mod.analyze_bazi(birth, city=city, longitude=longitude,
                                      tz_offset=tz_offset, use_dst=use_dst)
        except Exception as e:
            bazi_err = str(e)

    parts, weights = {}, {}
    if num:
        # 数理吉凶换算为分数
        luck_score = {"大吉": 92, "吉": 82, "半吉": 68, "凶": 42, "大凶": 30}
        parts["shuli"] = luck_score.get(num.get("luck"), 60)
        weights["shuli"] = 0.20
    if wuyin:
        parts["wuyin"] = wuyin["score"]
        weights["wuyin"] = 0.30
    if meihua:
        parts["meihua"] = meihua["score"]
        weights["meihua"] = 0.50
    overall = round(sum(parts[k] * weights[k] for k in parts) / sum(weights.values()), 1) if parts else 0

    result = {
        "mode": "org",
        "input": {"name": name, "chars": len(name)},
        "strokes": strokes,
        "total_strokes": total,
        "shuli": {"value": total, "number": total % 81 or 81,
                  "title": num.get("title"), "luck": num.get("luck"),
                  "wuxing": wuxing_of(total), "brief": num.get("summary")},
        "meanings": meanings,
        "wuyin": wuyin,
        "wuyin_error": wuyin_err,
        "meihua": meihua,
        "meihua_error": meihua_err,
        "meihua_strokes": meihua_strokes,
        "bazi": bazi,
        "bazi_error": bazi_err,
        "parts": parts,
        "overall": overall,
        "overall_grade": grade_org(overall),
        "disclaimer": DISCLAIMER,
    }
    # 出生信息完整性标记
    result["birth_missing"] = not birth
    result["city_missing"] = not city and longitude is None
    # 跨体系统合（机构模式暂不生成统合，但保留接口一致性）
    result["synthesis"] = None
    return result


def report_strokes(name):
    """借用五格技能的笔画查询（含缺字策略）。"""
    from wuge import StrokeQuery
    sq = StrokeQuery()
    return {ch: sq.require(ch) for ch in name}


# ---------------- 渲染 ----------------
def _card_line(L, cards, key):
    """在某一维度结论之后附上解读图路径。"""
    c = (cards or {}).get(key)
    if c:
        L.append(f"　图│{c['title']}　{c['display']}")


CARD_META = {
    "wuge": "五格剖象",
    "wuyin": "五音律吕",
    "meihua": "梅花卦象",
    "bazi": "八字原盘",
    "synthesis": "五维统合",
    "synthesis_lite": "统合速览",
    "synthesis_wuxing": "五行平衡",
    "synthesis_cross": "交叉印证",
}


def card_name(r):
    """本次测算的显示名称：机构取 input.name，个人取 姓+名。"""
    inp = (r or {}).get("input") or {}
    if inp.get("name"):
        return str(inp["name"])
    return str(inp.get("surname") or "") + str(inp.get("given") or "")


def build_cards(r, outdir=None, png=False, verify=True):
    """生成维度解读图（水墨太极八卦），返回供报告引用的路径表。

    outdir 默认按「本次测算的名称」建独立目录；机构模式此前因只取 surname+given
    而恒落到兜底目录 output/name，导致连续测算多个名称时产物互相覆盖、显示成
    上一个名称的图。取不到名称时改用唯一临时目录，绝不与他人共用。

    verify=True 时在生成后校验每张图确实写着本次名称（防止读到上一轮产物）。
    """
    import dimension_card as dc
    name = card_name(r)
    if outdir is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if name:
            outdir = os.path.join(root, "output", name)
        else:
            import tempfile
            outdir = tempfile.mkdtemp(prefix="yixue_cards_")
    raw = dc.render_all(r, outdir, png=png)
    if verify and name:
        bad = []
        for k in CARD_META:
            p = raw.get(k)
            if not p or not str(p).lower().endswith(".svg"):
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    if name not in f.read():
                        bad.append(k)
            except OSError:
                bad.append(k)
        if bad:
            raise RuntimeError(
                f"维度图归属校验失败：「{name}」的 "
                + "、".join(CARD_META[k] for k in bad)
                + " 未写成本次名称，疑似读取了上一次测算的产物")
        # 目录内不得残留本次未生成的图（清理被占用时会失败，此处兜底拦截）
        stale_map = {"01_五格": "wuge", "02_五音": "wuyin", "03_梅花": "meihua",
                     "04_八字": "bazi", "05_统合": "synthesis"}
        stale = []
        for stem, key in stale_map.items():
            if raw.get(key):
                continue
            for ext in (".svg", ".png"):
                if os.path.exists(os.path.join(outdir, stem + ext)):
                    stale.append(stem + ext)
        if stale:
            raise RuntimeError(
                f"输出目录残留上一次测算的图：{'、'.join(stale)}（本次未生成）。"
                f"请关闭正在占用这些文件的程序后重试，或改用 --cards-dir 指定新目录")
    cwd = os.getcwd()

    def disp(p):
        try:
            rel = os.path.relpath(p, cwd)
        except Exception:
            return p
        return (p if rel.startswith("..") else rel).replace("\\", "/")

    cards = {}
    for k, title in CARD_META.items():
        if raw.get(k):
            cards[k] = {"title": title, "path": raw[k], "display": disp(raw[k])}
    if raw.get("index"):
        cards["index"] = {"title": "维度图合览", "path": raw["index"],
                          "display": disp(raw["index"])}
    if png:
        cards["_png"] = [raw[k + "_png"] for k in CARD_META if raw.get(k + "_png")]
        cards["_browser"] = raw.get("browser", "")
    return cards


def render_person(r, cards=None):
    inp = r["input"]
    L = []
    gender = {"male": "男", "female": "女"}.get(inp.get("gender"), "")
    L.append("")
    L.append("═" * 46)
    L.append(f"　易学姓名学解析 · {inp['surname']}{inp['given']}"
             + (f"（{gender}）" if gender else ""))
    L.append("═" * 46)
    L.append(f"　结构：{STRUCT_LABEL.get(inp.get('structure'), inp.get('structure', ''))}　"
             f"笔画：" + "　".join(f"{c}{v}" for c, v in r["strokes"].items()))

    # 出生信息完整性醒目提示
    missing_items = []
    if r.get("birth_missing"):
        missing_items.append("出生时间（--birth）")
    if r.get("city_missing"):
        missing_items.append("出生地（--city）")
    if missing_items:
        L.append("")
        L.append("▲" * 23)
        L.append("　【重要提醒】排八字与跨体系统合需要准确的出生时间与出生地，")
        L.append(f"　当前缺失：{'、'.join(missing_items)}。")
        L.append("　请补充完整后重新分析，以获得八字原盘与统合结论。")
        L.append("▲" * 23)

    # 一、字义
    L.append("")
    L.append("一、字义解析")
    for m in r["meanings"]:
        if m.get("yi"):
            L.append(f"　{m['char']}（{m['role']}）：{m['yi']}")
            L.append(f"　　　意象：{m['xiang']}　字义五行：{m['wuxing']}　{m['yong']}")
        else:
            L.append(f"　{m['char']}（{m['role']}）：{m.get('note', '字义未收录')}")
    L.append(f"　{SECTION_DISCLAIMER}")

    # 二、五格
    g = r["wuge"]["grids"]
    sc = r["wuge"]["sancai"]
    L.append("")
    L.append("二、五格格局")
    for k in ("tian", "ren", "di", "wai", "zong"):
        d = g[k]
        label, meaning = GRID_LABEL[k]
        L.append(f"　{label} {d['value']:>3}　{d['number']} {d['title']}·{d['luck']}·{d['wuxing']}"
                 f"　— {meaning}")
    L.append(f"　三才：{sc['combo'][0]}·{sc['combo'][1]}·{sc['combo'][2]}"
             f"（{sc['luck']}，{sc['score']} 分）")
    L.append(f"　　成功运 {sc['success']['relation']}：{sc['success']['text']}")
    L.append(f"　　基础运 {sc['base']['relation']}：{sc['base']['text']}")
    L.append(f"　五格评分：{r['wuge']['score']} / 100（{r['wuge']['grade']}）")
    for h in r["wuge"].get("highlights", []):
        L.append(f"　　· {h}")

    dims = r["wuge"].get("dimensions") or {}
    if dims:
        L.append("　六维解读：")
        for key, label in DIMENSION_LABEL:
            text = (dims.get(key) or "").strip()
            if not text:
                continue
            chunks = _wrap_cn(text)
            L.append(f"　　【{label}】{chunks[0]}")
            for c in chunks[1:]:
                L.append(f"　　　　　　{c}")
    _card_line(L, cards, "wuge")
    L.append(f"　{SECTION_DISCLAIMER}")

    # 三、五音
    L.append("")
    L.append("三、五音（宫商角徵羽）与平仄")
    wy = r["wuyin"]
    if wy:
        L.append("　逐字：")
        for d in wy["chars"]:
            L.append(f"　　{d['char']}　{d['pinyin']}　{d['wuyin']}音（{d['organ']}·{d['wuxing']}）"
                     f"　{d['pingze']}声")
        L.append(f"　音序：{'→'.join(wy['wuyin_seq'])}　五行：{'→'.join(wy['wuxing_seq'])}")
        L.append(f"　平仄：{wy['pingze_seq']}　"
                 f"调值起伏：{'、'.join(str(j) for j in wy['pitch_jumps']) or '—'}")
        for p in wy["pairs"]:
            L.append(f"　　相邻 {p['pair']}：{p['from']} → {p['to']}　"
                     f"{p['relation']}（{p.get('direction', '')}）")
        L.append(f"　音律评分：{wy['score']} / 100（{wy['grade']}）—— {wy['comment']}")
        for s in wy.get("praise", []):
            L.append(f"　　✓ {s}")
        for s in wy.get("issues", []):
            L.append(f"　　！ {s}")
        if wy.get("resonance"):
            rs = wy["resonance"]
            L.append(f"　音气与格气：参照总格五行{rs['ref_wuxing']}，协和度 {rs['harmony']}%"
                     f"—— {rs['note']}")
    else:
        L.append(f"　（未生成：{r['wuyin_error']}）")
    _card_line(L, cards, "wuyin")
    L.append(f"　{SECTION_DISCLAIMER}")

    # 四、梅花易数
    L.append("")
    L.append("四、梅花易数终身卦")
    L.append("　（起卦笔画一律采用现代简体字规范笔画，不用繁体或字体变体）")
    m = r["meihua"]
    if m:
        c = m["cast"]
        ms = r.get("meihua_strokes") or {}
        simp_txt = "　".join(
            f"{ch}{v['strokes']}" + ("(繁)" if v.get("via") else "")
            for ch, v in ms.items()) if ms else "—"
        L.append(f"　简体笔画：{simp_txt}")
        L.append(f"　起卦：姓 {c['numbers']['upper']} 画 → 上卦 {c['ben']['gua']['upper']}"
                 f"（{c['numbers']['upper_mod8']}）；"
                 f"名 {c['numbers']['lower']} 画 → 下卦 {c['ben']['gua']['lower']}"
                 f"（{c['numbers']['lower_mod8']}）；"
                 f"合 {c['numbers']['upper'] + c['numbers']['lower']} 画 → 第 "
                 f"{c['ben']['moving_line']} 爻动")
        L.append(f"　本卦：{c['ben']['gua']['name']}（{c['ben']['gua']['symbol']}）"
                 f"　{c['ben']['gua']['no']}／64")
        L.append(f"　　大象：{c['ben']['gua']['xiang']}")
        L.append(f"　　卦义：{c['ben']['gua']['brief']}")
        L.append("　六爻（上→下）：")
        for line in c["ben"]["lines"]:
            L.append(f"　　{line}")
        L.append(f"　互卦：{c['hu']['gua']['name']}（{c['hu']['gua']['symbol']}）"
                 f"—— {c['hu']['gua']['brief']}")
        L.append(f"　变卦：{c['bian']['gua']['name']}（{c['bian']['gua']['symbol']}）"
                 f"—— {c['bian']['gua']['brief']}")
        L.append(f"　八宫：{c['ben']['gua']['gong']}宫（{c['ben']['gua']['gong_wuxing']}）")
        L.append("")
        L.append(f"　体用：体卦 {c['ti']['gua']}（{c['ti']['pos']}·{c['ti']['wuxing']}）　"
                 f"用卦 {c['yong']['gua']}（{c['yong']['pos']}·{c['yong']['wuxing']}）"
                 f"　→ {m['tiyong']['relation']}")
        L.append("")
        L.append("　卦中五行旺衰：")
        for p in m["wangshuai"]["positions"]:
            mark = {"生体": "生我", "比和": "同我", "体克": "我克",
                    "泄体": "我生", "克体": "克我", "本体": "本体"}[p["relation"]]
            tail = f"　权重 {p['weight']:+.2f}" if p["weight"] else ""
            L.append(f"　　{p['position']:<8}{p['wuxing']}　{mark}{tail}")
        w = m["wangshuai"]
        L.append(f"　体卦气势指数：{w['qi_index']} / 100")
        dom = "独旺" if w.get("dominant_count", 0) >= 3 else "略多"
        L.append(f"　　分布：{'　'.join(f'{k}{v}个' for k, v in w['distribution'].items())}"
                 f"　{dom} {w['dominant']}　不见 {'、'.join(w['lacking']) or '无'}")
        L.append(f"　　生助：{'、'.join(w['helpers']) or '无'}　"
                 f"克泄：{'、'.join(w['drainers']) or '无'}")
        L.append(f"　时令（{m['month']['note']}）：体卦{w['ti_in_month']['wuxing']}"
                 f"处「{w['ti_in_month']['state']}」地，用卦{w['yong_in_month']['wuxing']}"
                 f"处「{w['yong_in_month']['state']}」地")
        L.append(f"　卦象评分：{m['score']} / 100（{m['grade']}）")
        L.append("")
        L.append("　三段推演：")
        for k, v in m["stages"].items():
            L.append(f"　　{k}：{v}")
        L.append("")
        L.append("　卦象提示：")
        for a in m["advice"]:
            L.append(f"　　· {a}")
    else:
        L.append(f"　（未生成：{r['meihua_error']}）")
    _card_line(L, cards, "meihua")
    L.append(f"　{SECTION_DISCLAIMER}")

    # 五、八字原盘
    L.append("")
    L.append("五、八字原盘（真太阳时）与五行喜忌")
    bz = r.get("bazi")
    if bz:
        if r.get("city_missing"):
            L.append("　【注意】已按北京时间基准经度（东经120°）排盘，")
            L.append("　　因未提供出生地，真太阳时修正可能不准；")
            L.append("　　请补充 --city 或 --longitude 以获得精确排盘。")
            L.append("")
        L.extend(bz_mod.render_bazi(bz))
        _card_line(L, cards, "bazi")
        L.append(f"　{SECTION_DISCLAIMER}")
    elif r.get("bazi_error"):
        L.append(f"　（未生成：{r['bazi_error']}）")
        L.append(f"　{SECTION_DISCLAIMER}")
    else:
        L.append("　▲ 未提供出生信息，八字排盘未执行。")
        L.append("")
        L.append("　　若能补充出生时间与出生地，可为您排真太阳时八字原盘，")
        L.append("　　看清命局五行旺衰与喜忌用神，再将姓名用字五行与八字做")
        L.append("　　跨体系交叉印证——这是判断名字是否真正补益命主的关键一步。")
        L.append("")
        L.append("　　请提供：")
        L.append("　　　--birth \"YYYY-MM-DD HH:MM\"　（出生时间，公历）")
        L.append("　　　--city 出生城市　　　　　　　（如 成都 / 上海）")
        L.append("　　时辰未知可只给日期，时柱从略；出生地可用 --longitude 直接给经度。")
        L.append(f"　{SECTION_DISCLAIMER}")

    # 六、统合
    L.append("")
    L.append("六、跨体系统合（五格 · 五音 · 梅花 · 八字）")
    syn = r.get("synthesis")
    if syn:
        L.extend(syn_mod.render_synthesis_text(syn))
        _card_line(L, cards, "synthesis")
        # 三张简化版：按场景各取一张，不必全看
        lite = [(cards or {}).get(k) for k in ("synthesis_lite", "synthesis_wuxing",
                                               "synthesis_cross")]
        if any(lite):
            L.append("　简化版（按场景任选）：" + "　".join(
                f"{c['title']} {c['display']}" for c in lite if c))
        L.append(f"　{SECTION_DISCLAIMER}")
    else:
        if r.get("birth_missing") or r.get("city_missing"):
            L.append("　▲ 统合层未生成：出生时间或出生地缺失，")
            L.append("　　跨体系交叉印证必须以准确的出生信息为前提。")
            L.append("　　请补充 --birth 与 --city（或 --longitude）后重试。")
        else:
            L.append("　（四维未齐备，统合层需要五格、五音、梅花与八字同时成立。）")
        L.append(f"　{SECTION_DISCLAIMER}")

    # 七、综合
    L.append("")
    L.append("七、综合印象")
    label = {"wuge": "五格", "wuyin": "五音", "meihua": "卦象"}
    L.append("　" + "　".join(f"{label[k]} {v}" for k, v in r["parts"].items()))
    if syn:
        # 有统合层时，综合分直接引用四体统合口径（含互证调整），避免双口径并列
        L.append(f"　综合：{syn['score']:.1f} / 100（{syn['grade']}）"
                 "（四体统合口径：含跨体系互证调整，与第六节同源）")
    else:
        L.append(f"　综合：{r['overall']} / 100（{r['overall_grade']}）"
                 "（五格·五音·梅花三维静态加权，未含八字）")
    wuge_level = r["wuge"]["grade"]
    L.append(f"　一句话：五格格局属「{wuge_level}」，"
             + (f"音律{wy['grade']}，" if wy else "")
             + (f"卦象{m['grade']}；" if m else "")
             + "三者合看可见其长短，宜取长补短，不必执一而论。")
    if bz:
        xj = bz["xi_ji"]
        L.append(f"　八字：日主{bz['strength']['day_wuxing']}（{bz['pillars']['day'][0]}）"
                 f"{bz['strength']['label']}，用神 {'、'.join(xj['yongshen']) or '—'}，"
                 f"忌神 {'、'.join(xj['jishen']) or '—'}。")
    if (cards or {}).get("index"):
        L.append(f"　图│维度图合览　{cards['index']['display']}")
    L.append("")
    L.append("　※ " + r["disclaimer"])
    L.append("")
    return "\n".join(L)


def render_org(r, cards=None):
    L = []
    L.append("")
    L.append("═" * 46)
    L.append(f"　易学解析 · 机构名「{r['input']['name']}」")
    L.append("═" * 46)
    L.append(f"　笔画：" + "　".join(f"{c}{v}" for c, v in r["strokes"].items())
             + f"　总 {r['total_strokes']} 画")

    # 出生信息完整性醒目提示
    missing_items = []
    if r.get("birth_missing"):
        missing_items.append("出生时间（--birth）")
    if r.get("city_missing"):
        missing_items.append("出生地（--city）")
    if missing_items:
        L.append("")
        L.append("▲" * 23)
        L.append("　【重要提醒】机构名分析如需八字维度，须提供负责人的出生时间与出生地，")
        L.append(f"　当前缺失：{'、'.join(missing_items)}。")
        L.append("　请补充完整后重新分析，以获得八字原盘结论。")
        L.append("▲" * 23)

    L.append("")
    L.append("一、字义解析")
    for m in r["meanings"]:
        if m.get("yi"):
            L.append(f"　{m['char']}：{m['yi']}　（{m['xiang']}｜{m['wuxing']}）")
        else:
            L.append(f"　{m['char']}：{m.get('note', '字义未收录')}")
    L.append(f"　{SECTION_DISCLAIMER}")
    L.append("")
    L.append("二、总笔画数理")
    s = r["shuli"]
    L.append(f"　总笔画 {s['value']} → 数理 {s['number']} {s['title'] or ''}"
             f"（{s['luck']}·{s['wuxing']}）")
    if s.get("brief"):
        L.append(f"　　{s['brief']}")
    L.append(f"　{SECTION_DISCLAIMER}")
    L.append("")
    L.append("三、五音与平仄")
    wy = r["wuyin"]
    if wy:
        L.append("　" + "　".join(f"{d['char']}{d['pinyin']} {d['wuyin']}/{d['pingze']}"
                                 for d in wy["chars"]))
        L.append(f"　音序 {'→'.join(wy['wuyin_seq'])}　平仄 {wy['pingze_seq']}"
                 f"　评分 {wy['score']}（{wy['grade']}）")
        for s0 in wy.get("issues", []):
            L.append(f"　　！ {s0}")
        for s0 in wy.get("praise", []):
            L.append(f"　　✓ {s0}")
    else:
        L.append(f"　（未生成：{r['wuyin_error']}）")
    L.append(f"　{SECTION_DISCLAIMER}")
    L.append("")
    L.append("四、梅花易数卦象")
    L.append("　（起卦笔画一律采用现代简体字规范笔画，不用繁体或字体变体）")
    m = r["meihua"]
    if m:
        c = m["cast"]
        ms = r.get("meihua_strokes") or {}
        if ms:
            L.append("　简体笔画：" + "　".join(
                f"{ch}{v['strokes']}" + ("(繁)" if v.get("via") else "")
                for ch, v in ms.items()))
        L.append(f"　起卦：前半 {c['numbers']['upper']} 画 → 上卦 {c['ben']['gua']['upper']}；"
                 f"后半 {c['numbers']['lower']} 画 → 下卦 {c['ben']['gua']['lower']}；"
                 f"第 {c['ben']['moving_line']} 爻动")
        L.append(f"　本卦 {c['ben']['gua']['name']}（{c['ben']['gua']['symbol']}）"
                 f"　互卦 {c['hu']['gua']['name']}　变卦 {c['bian']['gua']['name']}")
        L.append(f"　　大象：{c['ben']['gua']['xiang']}")
        L.append("　六爻（上→下）：")
        for line in c["ben"]["lines"]:
            L.append(f"　　{line}")
        L.append(f"　体卦 {c['ti']['gua']}（{c['ti']['wuxing']}）　用卦 {c['yong']['gua']}"
                 f"（{c['yong']['wuxing']}）→ {m['tiyong']['relation']}")
        L.append(f"　体卦气势指数 {m['wangshuai']['qi_index']}　卦象评分 {m['score']}（{m['grade']}）")
        dom = "独旺" if m["wangshuai"].get("dominant_count", 0) >= 3 else "略多"
        L.append(f"　{dom} {m['wangshuai']['dominant']}　不见 "
                 f"{'、'.join(m['wangshuai']['lacking']) or '无'}")
        for n in m["narrative"]:
            L.append(f"　· {n}")
        for a in m["advice"]:
            L.append(f"　　→ {a}")
    else:
        L.append(f"　（未生成：{r['meihua_error']}）")
    L.append(f"　{SECTION_DISCLAIMER}")

    # 五、负责人八字原盘（真太阳时）与五行喜忌
    L.append("")
    L.append("五、负责人八字原盘（真太阳时）与五行喜忌")
    bz = r.get("bazi")
    if bz:
        if r.get("city_missing"):
            L.append("　【注意】已按北京时间基准经度（东经120°）排盘，")
            L.append("　　因未提供出生地，真太阳时修正可能不准；")
            L.append("　　请补充 --city 或 --longitude 以获得精确排盘。")
            L.append("")
        L.extend(bz_mod.render_bazi(bz))
        _card_line(L, cards, "bazi")
        L.append(f"　{SECTION_DISCLAIMER}")
    elif r.get("bazi_error"):
        L.append(f"　（未生成：{r['bazi_error']}）")
        L.append(f"　{SECTION_DISCLAIMER}")
    else:
        L.append("　▲ 未提供负责人出生信息，八字排盘未执行。")
        L.append("")
        L.append("　　作为机构名分析，法人或发起人的生辰八字尤为重要：")
        L.append("　　八字可揭示命局五行喜忌，进而判断机构名称的用字五行")
        L.append("　　是否真正补益负责人，实现名与命的五行平衡与吉祥共振。")
        L.append("　　建议补充后重新分析，以获得最具参考价值的命名建议。")
        L.append("")
        L.append("　　请提供：")
        L.append("　　　--birth \"YYYY-MM-DD HH:MM\"　（负责人出生时间，公历）")
        L.append("　　　--city 出生城市　　　　　　　（如 成都 / 上海）")
        L.append("　　时辰未知可只给日期，时柱从略；出生地可用 --longitude 直接给经度。")
        L.append(f"　{SECTION_DISCLAIMER}")

    L.append("")
    L.append("六、综合")
    label = {"shuli": "数理", "wuyin": "五音", "meihua": "卦象"}
    L.append("　" + "　".join(f"{label[k]} {v}" for k, v in r["parts"].items()))
    L.append(f"　综合：{r['overall']} / 100（{r['overall_grade']}）")
    if bz:
        xj = bz["xi_ji"]
        L.append(f"　八字：日主{bz['strength']['day_wuxing']}（{bz['pillars']['day'][0]}）"
                 f"{bz['strength']['label']}，用神 {'、'.join(xj['yongshen']) or '—'}，"
                 f"忌神 {'、'.join(xj['jishen']) or '—'}。")
    L.append("")
    L.append("　※ " + r["disclaimer"])
    L.append("")
    return "\n".join(L)


def compare(surname, candidates, cfg, month, with_wuyin, with_meihua):
    rows = []
    for name in candidates:
        name = name.strip()
        if not name:
            continue
        try:
            r = analyze_person(surname, name, cfg, month=month,
                              with_wuyin=with_wuyin, with_meihua=with_meihua)
            rows.append((r, name))
        except WugeError as e:
            print(f"[跳过] {surname}{name}：{e.message}")
    if not rows:
        print("没有可用候选。")
        return 1
    rows.sort(key=lambda x: -x[0]["overall"])
    print(f"\n【起名筛选】姓「{surname}」　候选 {len(rows)} 个（按综合分降序）")
    print(f"{'姓名':<8}{'五格':>7}{'五音':>7}{'卦象':>7}{'综合':>7}  等级  本卦")
    print("-" * 62)
    for r, name in rows:
        g = r["wuge"]["grids"]
        wy = r["wuyin"]["score"] if r["wuyin"] else "—"
        mh = r["meihua"]["score"] if r["meihua"] else "—"
        ben = r["meihua"]["cast"]["ben"]["gua"]["name"] if r["meihua"] else "—"
        print(f"{surname + name:<8}{r['wuge']['score']:>7}{wy:>7}{mh:>7}"
              f"{r['overall']:>7}  {r['overall_grade']}  {ben}"
              f"　({g['tian']['value']}/{g['ren']['value']}/{g['di']['value']}"
              f"/{g['wai']['value']}/{g['zong']['value']})")
    print("\n说明：综合分仅用于同一姓氏下候选名的横向比较，不可跨姓比较。")
    print("　" + DISCLAIMER)
    return 0


def main():
    ap = argparse.ArgumentParser(description="易学姓名学解析（字义 / 五格 / 五音 / 梅花易数）")
    ap.add_argument("--surname", help="姓（如 李 / 欧阳）")
    ap.add_argument("--given", help="名（如 明华）")
    ap.add_argument("--full", help="完整姓名（自动判定单/复姓）")
    ap.add_argument("--org", help="公司/团队名称（机构模式）")
    ap.add_argument("--candidates", help="候选名，逗号分隔，用于起名筛选")
    ap.add_argument("--gender", default="unknown", choices=["male", "female", "unknown"])
    ap.add_argument("--branch", help="指定月令地支（如 午），缺省按当前日期近似节气")
    ap.add_argument("--date", help="指定日期 YYYY-MM-DD，用于取月令")
    ap.add_argument("--waige-mode", default="virtual_2", choices=["virtual_2", "formula_1"])
    ap.add_argument("--on-missing", default="fallback", choices=["strict", "ask", "fallback"])
    ap.add_argument("--no-wuyin", action="store_true", help="跳过五音分析")
    ap.add_argument("--no-meihua", action="store_true", help="跳过梅花易数")
    ap.add_argument("--no-bazi", action="store_true", help="跳过八字排盘")
    ap.add_argument("--birth", help="出生时间（公历）：YYYY-MM-DD HH:MM 或 YYYY-MM-DD；"
                                     "排八字时必须同时提供 --city 或 --longitude")
    ap.add_argument("--city", help="出生地（内置城市经度表），如 成都 / 上海；"
                                   "与 --birth 配套使用，二者缺一不可")
    ap.add_argument("--longitude", type=float, help="出生地经度（东经），城市未收录时直接给出；"
                                                     "可作为 --city 的替代，与 --birth 配套使用")
    ap.add_argument("--tz", help="出生地时区偏移（相对 UTC，如 +8 / -5 / +5:30）；"
                                 "默认 +8 北京时间，境外出生时给出")
    ap.add_argument("--no-dst", action="store_true",
                    help="不自动还原 1986–1991 年全国夏令时（出生记录已是标准时间时用）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--no-cards", action="store_true", help="不生成水墨维度解读图")
    ap.add_argument("--cards-dir", help="解读图输出目录（默认 <技能根>/output/<姓名>）")
    ap.add_argument("--png", action="store_true", help="同时导出 PNG（借用本机 Edge/Chrome）")
    args = ap.parse_args()

    if not args.org and not args.full and not (args.surname and (args.given or args.candidates)):
        ap.print_help()
        return 0

    cfg = WugeConfig(waige_mode=args.waige_mode, on_missing=args.on_missing,
                     gender=args.gender)

    try:
        import datetime
        when = datetime.date.fromisoformat(args.date) if args.date else None
        month = mh_mod.month_context(when, args.branch)

        if args.candidates and args.surname:
            cands = [c for c in args.candidates.replace("，", ",").split(",")]
            return compare(args.surname, cands, cfg, month,
                           not args.no_wuyin, not args.no_meihua)

        if args.org:
            tz_offset = None
            if args.tz:
                try:
                    tz_offset = bz_mod.parse_tz(args.tz)
                except Exception as e:
                    print(f"[错误] {e}")
                    return 2
            r = analyze_org(args.org, month,
                            not args.no_wuyin, not args.no_meihua,
                            birth=args.birth, city=args.city,
                            longitude=args.longitude, tz_offset=tz_offset,
                            use_dst=not args.no_dst)
            if args.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
                # JSON 模式同样产出维度图（stdout 仍只输出 JSON，图写盘）
                if not args.no_cards:
                    build_cards(r, args.cards_dir, args.png)
                return 0
            cards = None
            if not args.no_cards:
                cards = build_cards(r, args.cards_dir, args.png)
                if args.png and not (cards or {}).get("_png"):
                    print("　[提示] 未找到 Edge/Chrome，已保留 SVG；SVG 可用浏览器直接打开或打印。\n")
            print(render_org(r, cards))
            return 0

        tz_offset = None
        if args.tz:
            try:
                tz_offset = bz_mod.parse_tz(args.tz)
            except Exception as e:
                print(f"[错误] {e}")
                return 2
        r = analyze_person(args.surname or "", args.given or "", cfg,
                           full=args.full, month=month,
                           with_wuyin=not args.no_wuyin, with_meihua=not args.no_meihua,
                           birth=args.birth, city=args.city,
                           longitude=args.longitude, tz_offset=tz_offset,
                           use_dst=not args.no_dst)
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
            # JSON 模式同样产出维度图（stdout 仍只输出 JSON，图写盘）
            if not args.no_cards:
                build_cards(r, args.cards_dir, args.png)
            return 0
        cards = None
        if not args.no_cards:
            cards = build_cards(r, args.cards_dir, args.png)
            if args.png and not (cards or {}).get("_png"):
                print("　[提示] 未找到 Edge/Chrome，已保留 SVG；SVG 可用浏览器直接打开或打印。\n")
        print(render_person(r, cards))
        return 0
    except WugeError as e:
        if args.json:
            print(to_json(e.to_dict()))
        else:
            print(f"\n[无法分析：{e.code}]\n{e.message}\n")
        return 2
    except (mh_mod.MeihuaError, wy_mod.WuyinError) as e:
        print(f"\n[分析中断]\n{e}\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
