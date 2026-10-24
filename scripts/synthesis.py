#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""synthesis.py —— 跨体系统合层（五格 · 五音 · 梅花 · 八字）

四个体系本不同源：五格主「数」，五音主「声」，梅花主「象」，八字主「时」。
各自出图时只是四份互不相干的判词；统合层的任务是把它们投影到同一组坐标上，
使彼此可比较、可印证、也可被反驳。

共用四条轴（详见 framework()）：
    五行轴   木火土金水 —— 物质与能量的公共刻度，四体系皆有对应
    刚柔轴   阴／阳、强／弱、平／仄、主／受，取值 −1（刚）… +1（柔）
    时段轴   早／中／晚 —— 柱位 · 格位 · 卦位 · 字位，四者同构
    数象轴   干支序 · 数理 · 卦数 · 音序 —— 形式呼应，不作吉凶

权重三层：体用分工 → 名内分工 → 互证加权（见 WEIGHTS / framework()）。

设计原则：
    1. 任何合成都必须可拆解回原始分，不做黑箱加权；
    2. 只做「同向 / 相悖」的描述，不把跨体系一致当成事实确认；
    3. 数象轴只报形式呼应，明确不参与评分。
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dimension_card as dc  # noqa: E402

WX = ("木", "火", "土", "金", "水")
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
GUA_WX = {"乾": "金", "兑": "金", "离": "火", "震": "木",
          "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
YANG_GUA = {"乾", "震", "坎", "艮"}

PILLAR_NAME = {"year": "年柱", "month": "月柱", "day": "日柱", "time": "时柱"}

# 三层权重（合计 100）。时辰未知时八字精度下降，权重让位给可确定的姓名三项。
WEIGHTS = {
    "full": {"bazi": 34, "wuge": 26, "meihua": 22, "wuyin": 18},
    "no_time": {"bazi": 22, "wuge": 28, "meihua": 26, "wuyin": 24},
}
SOURCE_NAME = {"bazi": "四柱八字", "wuge": "五格剖象",
               "meihua": "梅花易数", "wuyin": "五音纳音"}
SOURCE_NOTE = {"bazi": "时 · 命体", "wuge": "数 · 骨架",
               "meihua": "象 · 机变", "wuyin": "声 · 气韵"}
SOURCE_COLOR = {"bazi": dc.INK, "wuge": dc.CINNABAR,
                "meihua": dc.OCHRE, "wuyin": "#2E5E8C"}

LUCK_SCORE = {"大吉": 92, "吉": 82, "半吉": 70, "凶": 48, "大凶": 34}
TEND_SCORE = {"大吉": 92, "吉": 80, "中": 68, "平": 62, "需慎": 50, "凶": 40}
REL_SCORE = {"比和": 88, "生我": 84, "我生": 74, "我克": 70, "克我": 60}
REL_READ = {
    "比和": "同气", "生我": "来生", "我生": "我泄",
    "我克": "我制", "克我": "受制",
}

# 五音五行 → 音名（用于文字表述）
WY_NAME = {"宫": "土", "商": "金", "角": "木", "徵": "火", "羽": "水"}

SW, SH = 980, 1612


# ---------------------------------------------------------------- 基础工具

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _r(x, n=1):
    return round(float(x), n)


def _sgn(x, nd=1):
    """带符号数字；近零不用 -0.0 这种误导写法。"""
    if abs(float(x)) < 10 ** (-nd) / 2:
        return "±" + ("0." + "0" * nd)
    return f"{float(x):+.{nd}f}"


def wuxing_relation(host, guest):
    """host 为本命/主体，guest 为对象。返回 比和/生我/我生/我克/克我。"""
    if host == guest:
        return "比和"
    if SHENG.get(host) == guest:
        return "我生"
    if SHENG.get(guest) == host:
        return "生我"
    if KE.get(host) == guest:
        return "我克"
    if KE.get(guest) == host:
        return "克我"
    return "无涉"


def _norm(vec):
    s = sum(vec.values())
    if s <= 0:
        return {k: 0.0 for k in WX}
    return {k: vec.get(k, 0.0) / s for k in WX}


def _cos(a, b):
    na = math.sqrt(sum(a[k] ** 2 for k in WX))
    nb = math.sqrt(sum(b[k] ** 2 for k in WX))
    if na <= 0 or nb <= 0:
        return 0.0
    return sum(a[k] * b[k] for k in WX) / (na * nb)


def _dominant(vec):
    """主导五行；并列时全部返回（并旺）。"""
    mx = max(vec.values()) if vec else 0
    if mx <= 0:
        return []
    return [k for k in WX if abs(vec[k] - mx) < 1e-9]


def _share(vec):
    return _norm(vec)


# ---------------------------------------------------------------- 纬度向量

def _vec_bazi(bz):
    st = bz.get("wuxing_stat") or {}
    return {k: float((st.get(k) or {}).get("total", 0.0)) for k in WX}


def _vec_wuge(wg):
    v = {k: 0.0 for k in WX}
    for g in ("tian", "ren", "di", "wai", "zong"):
        cell = (wg.get("grids") or {}).get(g) or {}
        if cell.get("wuxing") in v:
            v[cell["wuxing"]] += 1.0
    for ch in (wg.get("sancai") or {}).get("combo", ""):
        if ch in v:
            v[ch] += 0.5
    return v


def _vec_wuyin(wy):
    v = {k: 0.0 for k in WX}
    for c in wy.get("chars") or []:
        if c.get("wuxing") in v:
            v[c["wuxing"]] += 1.0
    return v


def _vec_meihua(mh):
    dist = ((mh.get("wangshuai") or {}).get("distribution") or {})
    return {k: float(dist.get(k, 0)) for k in WX}


# ---------------------------------------------------------------- 刚柔投影

def _gangrou_bazi(bz):
    st = bz.get("strength") or {}
    ratio = float(st.get("ratio", 0.5))
    return _clamp((ratio - 0.5) * -2.0, -1.0, 1.0)


def _gangrou_wuge(wg):
    g = wg.get("grids") or {}
    ren = (g.get("ren") or {}).get("value", 0)
    zong = (g.get("zong") or {}).get("value", 0)
    return (-0.35 if ren % 2 else 0.35) + (-0.15 if zong % 2 else 0.15)


def _gangrou_wuyin(wy):
    chars = wy.get("chars") or []
    if not chars:
        return 0.0
    ping = sum(1 for c in chars if c.get("pingze") == "平")
    return (ping * 2 - len(chars)) / len(chars)


def _gangrou_meihua(mh):
    ti = ((mh.get("cast") or {}).get("ti") or {}).get("gua", "")
    rel = (mh.get("tiyong") or {}).get("relation", "")
    base = {"体克用": -0.45, "体生用": 0.30, "比和": 0.0,
            "用生体": -0.30, "用克体": 0.45}.get(rel, 0.0)
    tweak = -0.15 if ti in YANG_GUA else 0.15
    return _clamp(base + tweak, -1.0, 1.0)


# ---------------------------------------------------------------- 时段投影

def _bazi_stage(bz, key, use_zhi=False):
    d = (bz.get("pillar_detail") or {}).get(key) or {}
    dw = (bz.get("strength") or {}).get("day_wuxing", "")
    wx = d.get("zhi_wuxing") if use_zhi else d.get("gan_wuxing")
    rel = wuxing_relation(dw, wx or "")
    return {"wx": wx, "rel": rel, "label": REL_READ.get(rel, ""),
            "score": float(REL_SCORE.get(rel, 70))}


def _wuge_stage(wg, keys):
    g = wg.get("grids") or {}
    vals = [LUCK_SCORE.get((g.get(k) or {}).get("luck", ""), 65) for k in keys]
    return sum(vals) / len(vals) if vals else 65.0


def _gua_stage(mh, part):
    g = ((mh.get("cast") or {}).get(part) or {}).get("gua") or {}
    return TEND_SCORE.get(g.get("tendency", ""), 66), g.get("name", "")


# ---------------------------------------------------------------- 用神契合

def _use_god_fit(r):
    bz = r["bazi"]
    xj = bz.get("xi_ji") or {}
    xi = list(xj.get("yongshen") or []) + list(xj.get("xishen") or [])
    ji = list(xj.get("jishen") or []) + list(xj.get("choushen") or [])
    role = {}
    for k in xi:
        role[k] = ("喜用", 1.0)
    for k in ji:
        role[k] = ("忌仇", -1.2)

    items = []
    wg, wy, mh = r["wuge"], r["wuyin"], r["meihua"]

    def add(origin, wx, w=1.0):
        if not wx:
            return
        kind, val = role.get(wx, ("闲", 0.0))
        items.append({"origin": origin, "wuxing": wx, "role": kind,
                      "weight": w, "value": val * w})

    # 五格数理五行（人格/总格/三才）另算，不参与跨体系用神契合
    # 只取梅花体卦与五音
    add("体卦", GUA_WX.get(((mh.get("cast") or {}).get("ti") or {}).get("gua", "")), 3.0)
    for c in wy.get("chars") or []:
        add(f"五音·{c.get('char','')}", c.get("wuxing"), 2.0)

    raw = sum(i["value"] for i in items)
    score = _clamp(50 + raw * 2.2, 0, 100)
    hit_xi = [i for i in items if i["role"] == "喜用"]
    hit_ji = [i for i in items if i["role"] == "忌仇"]
    if score >= 60:
        verdict = "名助命用"
    elif score <= 44:
        verdict = "名逆命用"
    else:
        verdict = "喜忌两平"
    return {"score": _r(score), "verdict": verdict, "raw": _r(raw, 2),
            "items": items, "hit_xi": hit_xi, "hit_ji": hit_ji,
            "yongshen": list(xj.get("yongshen") or []),
            "xishen": list(xj.get("xishen") or []),
            "jishen": list(xj.get("jishen") or []),
            "choushen": list(xj.get("choushen") or [])}


# ---------------------------------------------------------------- 数象呼应

def _jiazhi_index(pillar):
    """干支 → 六十甲子序（1–60）。"""
    gz = "甲乙丙丁戊己庚辛壬癸"
    zz = "子丑寅卯辰巳午未申酉戌亥"
    if len(pillar) != 2 or pillar[0] not in gz or pillar[1] not in zz:
        return 0
    gi, zi = gz.index(pillar[0]), zz.index(pillar[1])
    for i in range(60):
        if i % 10 == gi and i % 12 == zi:
            return i + 1
    return 0


def _echoes(r):
    wg, mh, bz = r["wuge"], r["meihua"], r["bazi"]
    ren = (wg["grids"]["ren"] or {}).get("value", 0)
    zong = (wg["grids"]["zong"] or {}).get("value", 0)
    nos = {}
    for part, label in (("ben", "本卦"), ("hu", "互卦"), ("bian", "变卦")):
        g = ((mh.get("cast") or {}).get(part) or {}).get("gua") or {}
        nos[label] = g.get("no", 0)
    rizhu = _jiazhi_index((bz.get("pillars") or {}).get("day", ""))
    cand = [("人格", ren), ("总格", zong), ("日柱序", rizhu)] + \
           [(k, v) for k, v in nos.items() if v]
    out = []
    seen = set()
    for i in range(len(cand)):
        for j in range(i + 1, len(cand)):
            (na, a), (nb, b) = cand[i], cand[j]
            if not a or not b:
                continue
            key = tuple(sorted((na, nb)))
            if key in seen:
                continue
            why = ""
            if a % 10 == b % 10:
                why = "尾数相同"
            elif len(str(a)) == 2 and str(a) == str(b)[::-1]:
                why = "互为倒序"
            elif abs(a - b) % 10 == 0:
                why = "相差十的倍数"
            elif (a + b) % 10 == 0:
                why = "尾数互补成十"
            elif a % 8 == b % 8:
                why = "同余于八（卦数同宫）"
            if why:
                seen.add(key)
                out.append({"pair": f"{na} {a} · {nb} {b}", "why": why})
    return out[:4]


# ---------------------------------------------------------------- 交叉印证

def _cross_items(r, fit, res, gr, stages):
    bz, wg, wy, mh = r["bazi"], r["wuge"], r["wuyin"], r["meihua"]
    dw = (bz.get("strength") or {}).get("day_wuxing", "")
    items = []

    def add(level, title, detail, dims):
        items.append({"level": level, "title": title,
                      "detail": detail, "dims": dims})

    # 1 用神契合
    xi_s = "、".join(f"{i['origin']}{i['wuxing']}" for i in fit["hit_xi"][:4]) or "无"
    ji_s = "、".join(f"{i['origin']}{i['wuxing']}" for i in fit["hit_ji"][:4]) or "无"
    if fit["verdict"] == "名助命用":
        add("印证", "名助命用",
            f"用神{'、'.join(fit['yongshen']) or '未定'}落于姓名：{xi_s}；忌仇仅见{ji_s}。",
            ["八字", "梅花", "五音"])
    elif fit["verdict"] == "名逆命用":
        add("张力", "名逆命用",
            f"用神{'、'.join(fit['yongshen']) or '未定'}在名中仅见{xi_s}，而忌仇叠见：{ji_s}。",
            ["八字", "五格", "五音"])
    else:
        add("调和", "喜忌两平",
            f"喜用见{xi_s}，忌仇见{ji_s}，补泻大致相抵。", ["八字", "五格"])

    # 2 体卦与日主（梅花与八字同一体系）
    ti = ((mh.get("cast") or {}).get("ti") or {})
    ti_wx = ti.get("wuxing", "")
    rel2 = wuxing_relation(dw, ti_wx)
    if rel2 in ("比和", "生我"):
        add("印证", "卦体同命",
            f"体卦{ti.get('gua','')}属{ti_wx}，与日主{dw}「{rel2}」，自主之力与本命同向。",
            ["梅花", "八字"])
    elif rel2 == "克我":
        add("张力", "卦体克命",
            f"体卦{ti.get('gua','')}属{ti_wx}，克日主{dw}；卦象所示之主动力，恰是本命的耗处。",
            ["梅花", "八字"])
    else:
        add("调和", "卦体异气",
            f"体卦属{ti_wx}，日主{dw}，二者「{rel2}」，卦象另辟一路而非承命。",
            ["梅花", "八字"])

    # 3 变卦与流通
    bian = ((mh.get("cast") or {}).get("bian") or {}).get("gua") or {}
    b_tend = TEND_SCORE.get(bian.get("tendency", ""), 66)
    bal = ((bz.get("balance") or {}).get("score", 70)) or 70
    if b_tend >= 78 and bal >= 78:
        add("印证", "收局与命局同宽",
            f"变卦{bian.get('name','')}（{bian.get('tendency','')}）与八字原盘"
            f"{bal:.1f}（{(bz.get('balance') or {}).get('grade','')}）皆宽，晚景与命局同调。",
            ["梅花", "八字"])
    elif b_tend >= 78 > bal:
        add("调和", "名宽而命窄",
            f"变卦{bian.get('name','')}主{bian.get('tendency','')}，而原盘仅{bal:.1f}，"
            f"卦意胜于命局所能承载，需后天补足。", ["梅花", "八字"])
    elif b_tend < 70 < bal:
        add("张力", "收局转紧",
            f"变卦{bian.get('name','')}（{bian.get('tendency','')}）转紧，"
            f"原盘{bal:.1f}本宽，晚程需主动收敛。", ["梅花", "八字"])
    else:
        add("调和", "收局平顺",
            f"变卦{bian.get('name','')}与八字原盘{bal:.1f}，同处中段。", ["梅花", "八字"])

    # 4 梅花卦局与八字五行（同体系直接比较）
    mh_dist = (mh.get("wangshuai") or {}).get("distribution") or {}
    bz_stat = (bz.get("wuxing_stat") or {})
    # 卦局最旺 vs 八字最旺
    mh_max_wx = max(WX, key=lambda w: float(mh_dist.get(w, 0)))
    bz_max_wx = max(WX, key=lambda w: float((bz_stat.get(w) or {}).get("total", 0)))
    if mh_max_wx == bz_max_wx:
        add("印证", "卦命同旺",
            f"卦局最旺为{mh_max_wx}（{mh_dist.get(mh_max_wx,0):.0f}%），"
            f"八字最旺亦为{bz_max_wx}（{(bz_stat.get(bz_max_wx) or {}).get('total',0):.1f}）；"
            f"卦象与命局同气，旺衰方向一致。",
            ["梅花", "八字"])
    elif wuxing_relation(bz_max_wx, mh_max_wx) in ("生我", "比和"):
        add("调和", "卦旺生局",
            f"卦局最旺{mh_max_wx}生八字最旺{bz_max_wx}，卦象对命局有扶益之象。",
            ["梅花", "八字"])
    elif wuxing_relation(bz_max_wx, mh_max_wx) == "克我":
        add("张力", "卦旺克局",
            f"卦局最旺{mh_max_wx}克八字最旺{bz_max_wx}，卦象与命局旺处相战。",
            ["梅花", "八字"])
    else:
        add("调和", "卦局异旺",
            f"卦局最旺{mh_max_wx}，八字最旺{bz_max_wx}，二者各行其道。",
            ["梅花", "八字"])
    # 用卦与日主关系
    yong = ((mh.get("cast") or {}).get("yong") or {})
    yong_wx = yong.get("wuxing", "")
    rel_yong = wuxing_relation(dw, yong_wx)
    if rel_yong in ("比和", "生我"):
        add("印证", "用卦生助",
            f"用卦{yong.get('gua','')}属{yong_wx}，与日主{dw}「{rel_yong}」；"
            f"外境对命主有扶持之象。", ["梅花", "八字"])
    elif rel_yong == "克我":
        add("张力", "用卦压制",
            f"用卦{yong.get('gua','')}属{yong_wx}，克日主{dw}；"
            f"外境对命主成消耗之势。", ["梅花", "八字"])

    # 5 五音末字与总格
    last = (wy.get("chars") or [{}])[-1]
    zong_wx = (wg["grids"]["zong"] or {}).get("wuxing", "")
    if last.get("wuxing") == zong_wx:
        add("印证", "收束归元",
            f"末字「{last.get('char','')}」属{last.get('wuxing','')}，与总格{zong_wx}同气，"
            f"称呼落点与后运一致。", ["五音", "五格"])
    else:
        r3 = wuxing_relation(zong_wx, last.get("wuxing", ""))
        lv = "调和" if r3 in ("我生", "生我") else "张力"
        add(lv, "收束异气",
            f"末字「{last.get('char','')}」属{last.get('wuxing','')}，总格属{zong_wx}，"
            f"二者「{r3}」，称呼落点与后运略见错位。", ["五音", "五格"])

    # 6 五行共振（五格另算，三源：梅花·八字·五音）
    if res["score"] >= 84:
        add("印证", "三源同气",
            f"梅花·八字·五音三体系共振 {res['score']:.0f}%，主导之行为"
            f"{'、'.join(res['consensus_wx']) or '各有所主'}，指向一致。",
            ["梅花", "八字", "五音"])
    elif res["score"] >= 72:
        add("调和", "三源大体同调",
            f"共振 {res['score']:.0f}%，主导五行{'、'.join(res['consensus_wx']) or '分散'}，"
            f"方向相近而侧重不同。", ["梅花", "八字", "五音"])
    else:
        add("张力", "三源各有所主",
            f"共振仅 {res['score']:.0f}%，三体系所重不同，须分别看待，不宜强合。",
            ["梅花", "八字", "五音"])

    # 7 卦局缺用神
    lacking = ((mh.get("wangshuai") or {}).get("lacking") or [])
    if lacking:
        if any(x in lacking for x in fit["yongshen"]):
            add("张力", "卦局缺用神",
                f"卦局不见{'、'.join(lacking)}，而用神正取{'、'.join(fit['yongshen'])}；"
                f"卦象一路未能补命局所急。", ["梅花", "八字"])
        elif any(x in lacking for x in fit["jishen"] + fit["choushen"]):
            add("印证", "卦局去忌",
                f"卦局不见{'、'.join(lacking)}，正为命局忌仇之神，卦象自然避忌。",
                ["梅花", "八字"])

    # 8 分数共识
    parts = r["parts"]
    spread = max(parts.values()) - min(parts.values())
    if spread <= 12 and min(parts.values()) >= 70:
        add("印证", "四维同调",
            f"四项得分 {min(parts.values()):.1f}–{max(parts.values()):.1f}，极差 {spread:.1f}，"
            f"彼此互证，无孤证之嫌。", ["梅花", "八字", "五音", "五格"])
    elif spread >= 24:
        lo = min(parts, key=parts.get)
        hi = max(parts, key=parts.get)
        add("张力", "长短悬殊",
            f"{SOURCE_NAME[hi]} {parts[hi]:.1f} 与 {SOURCE_NAME[lo]} {parts[lo]:.1f} "
            f"相差 {spread:.1f}，一强一弱，不可只取其一。",
            [SOURCE_NAME[hi], SOURCE_NAME[lo]])

    order = {"印证": 0, "张力": 1, "调和": 2}
    items.sort(key=lambda x: order.get(x["level"], 3))

    # 去重：同题同层只留一条
    seen, out = set(), []
    for it in items:
        if it["title"] in seen:
            continue
        seen.add(it["title"])
        out.append(it)
    return out


# ---------------------------------------------------------------- 主入口

def framework():
    """返回框架说明（供文档 / JSON 输出）。"""
    return {
        "axes": [
            {"key": "wuxing", "name": "五行轴",
             "range": "木·火·土·金·水（占比 0–100%）",
             "map": {"bazi": "四柱五行力量分布、日主", "wuge": "五格数理五行 + 三才",
                     "meihua": "卦局五行分布、体用",
                     "wuyin": "宫商角徵羽 → 五行"},
             "use": "判断梅花·八字·五音三源是否同气，并核姓名是否补到命局用神"},
            {"key": "gangrou", "name": "刚柔轴",
             "range": "−1（刚／强／主）… +1（柔／弱／受）",
             "map": {"bazi": "日主生助 / 克泄之比", "wuge": "人格与总格奇偶阴阳",
                     "meihua": "体用生克 + 体卦阴阳", "wuyin": "三字平仄配比"},
             "use": "看内外是否同调：骨架硬而气韵软，是常见的错位"},
            {"key": "period", "name": "时段轴",
             "range": "早 · 中 · 晚",
             "map": {"bazi": "年柱 / 月柱·日支 / 时柱", "wuge": "天格·地格 / 人格·三才 / 总格·外格",
                     "meihua": "本卦 / 互卦 / 变卦", "wuyin": "首字 / 中字 / 尾字（起·承·收）"},
             "use": "三段同看，得出一条趋势线而非单一吉凶"},
            {"key": "number", "name": "数象轴",
             "range": "干支序 1–60 · 数理 1–81 · 卦数 1–64 · 音序 1–5",
             "map": {"bazi": "日柱六十甲子序", "wuge": "人格 / 总格数理",
                     "meihua": "本卦 / 互卦 / 变卦卦数", "wuyin": "宫1 商2 角3 徵4 羽5"},
             "use": "仅报形式呼应（同尾、倒序、成十、同余），不参与评分"},
        ],
        "weights": {
            "layers": [
                {"layer": "一层 · 体用", "rows": {"体（八字，先天）": 34, "用（姓名，后天）": 66},
                 "why": "命为体、名为用：八字定禀赋与喜忌基准，姓名是后天呼召与修饰；"
                        "然二者非同权——八字不可改、姓名可择，故体不过半。"},
                {"layer": "二层 · 名内三面",
                 "rows": {"五格（数理骨架）": 26, "梅花（卦象机变）": 22, "五音（音声气韵）": 18},
                 "why": "五格最稳定（只看笔画，无读音与起卦的随机性），故权重最高；"
                        "梅花含变，动态信息量最大；五音最贴日常，但判据最主观，故最低。"},
                {"layer": "三层 · 互证加权",
                 "rows": {"同向者增益": 18, "相悖者减损": 18},
                 "why": "以各维方向分（score−60）/40 求他维加权同向度 c ∈ [−1,1]，"
                        "令 w′ = w·(1+0.18c)。孤证降权、互证升权，是集成式的置信度校正，"
                        "只在合成层生效，不改原始分。"},
            ],
            "full": dict(WEIGHTS["full"]),
            "no_time": dict(WEIGHTS["no_time"]),
            "note": "三层同位相加即 100。若时辰未知，八字仅三柱，权重降至 22，"
                    "让位给可确定的三项姓名维度。",
            "redundancy": "五格、五音、梅花同源于同一个名字，信息高度相关；"
                          "按独立信息量折算，姓名三项的等效权重约当 45–50，"
                          "其余为同源冗余——故合成时刻意压低单项、并设互证校正。",
        },
        "scales": {
            "parts": "各维原始分（0–100），语义不同：八字分是「原局流通度」而非吉凶，"
                     "五格/五音/梅花分是「该维度的顺逆度」。合成时统一为百分位后再加权。",
            "grade": "≥80 上佳 / ≥70 佳 / ≥60 平 / ≥50 偏弱 / <50 宜斟酌",
        },
    }


def cross_analysis(r):
    """四体系统合分析。缺任一维（尤其八字）或出生信息不完整时返回 None。"""
    if not r:
        return None
    # 出生时间与出生地缺一不可
    if r.get("birth_missing") or r.get("city_missing"):
        return None
    bz, wg, wy, mh = r.get("bazi"), r.get("wuge"), r.get("wuyin"), r.get("meihua")
    if not (bz and wg and wy and mh):
        return None
    if bz.get("error") or wy.get("error") or mh.get("error"):
        return None

    wkey = "full" if bz.get("time_known") else "no_time"
    weights = dict(WEIGHTS[wkey])

    raw_parts = {"bazi": float((bz.get("balance") or {}).get("score", 0)),
                 "wuge": float(wg.get("score", 0)),
                 "meihua": float(mh.get("score", 0)),
                 "wuyin": float(wy.get("score", 0))}

    # ---- 互证加权
    d = {k: _clamp((v - 60) / 40.0, -1, 1) for k, v in raw_parts.items()}
    agree = {}
    for i in raw_parts:
        others = [(j, w) for j, w in weights.items() if j != i]
        tot = sum(w for _, w in others) or 1
        acc = sum(w * (1 if d[i] * d[j] > 0 else (-1 if d[i] * d[j] < 0 else 0))
                  for j, w in others)
        agree[i] = acc / tot
    factor = {k: 1 + 0.18 * agree[k] for k in raw_parts}
    base = sum(weights[k] * raw_parts[k] for k in raw_parts) / sum(weights.values())
    adj_w = {k: weights[k] * factor[k] for k in raw_parts}
    adjusted = sum(adj_w[k] * raw_parts[k] for k in raw_parts) / sum(adj_w.values())
    consensus = sum(weights[k] * max(0.0, agree[k]) for k in raw_parts) / sum(weights.values())

    # ---- 五行向量与共振
    # 五行共振：五格数理五行另算，不与其他体系共振
    # 只取梅花、八字、五音三源
    vecs = {"bazi": _vec_bazi(bz),
            "meihua": _vec_meihua(mh), "wuyin": _vec_wuyin(wy)}
    shares = {k: _share(v) for k, v in vecs.items()}
    pairs = []
    keys = ["bazi", "meihua", "wuyin"]
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            pairs.append({"pair": f"{SOURCE_NAME[a]}·{SOURCE_NAME[b]}",
                          "a": a, "b": b, "cos": _r(_cos(shares[a], shares[b]), 3)})
    res_score = sum(p["cos"] for p in pairs) / len(pairs) * 100

    dom = {k: _dominant(shares[k]) for k in keys}
    # 三源共同主导：在各源主导集合中出现次数最多者
    tally = {}
    for k in keys:
        for wx in dom[k]:
            tally[wx] = tally.get(wx, 0) + 1
    top = max(tally.values()) if tally else 0
    # 共主须被至少两源共同推举；仅一源推举（含各源平局时各得 1 票）不算共识，
    # 否则五行各 1 票并列会全部列出，「共主」语义失效
    consensus_wx = ([k for k in WX if tally.get(k, 0) == top]
                   if tally and top >= 2 else [])
    consensus_missing = [] if not consensus_wx else [
        SOURCE_NAME[k] for k in keys
        if not any(w in dom[k] for w in consensus_wx)]
    lacking_all = [w for w in WX if all(shares[k][w] < 1e-9 for k in keys)]
    # 五格五行主导（仅供报告参考，不入共振）
    wuge_vec = _vec_wuge(wg)
    wuge_share = _share(wuge_vec)

    # ---- 刚柔
    gr = {"bazi": _r(_gangrou_bazi(bz), 2), "wuge": _r(_gangrou_wuge(wg), 2),
          "meihua": _r(_gangrou_meihua(mh), 2), "wuyin": _r(_gangrou_wuyin(wy), 2)}
    gr_mean = sum(gr[k] * weights[k] for k in gr) / sum(weights.values())
    gr_vals = list(gr.values())
    gr_spread = max(gr_vals) - min(gr_vals)
    pos = sum(1 for v in gr_vals if v > 0.03)
    neg = sum(1 for v in gr_vals if v < -0.03)
    gr_sign = "同向" if (pos >= 3 or neg >= 3) else ("分裂" if pos and neg else "居中")

    # ---- 三段
    def bz_pt(k, use_zhi=False):
        s = _bazi_stage(bz, k, use_zhi)
        return s["score"]
    late_key_ok = bool(bz.get("time_known"))
    bz_pts = [bz_pt("year"), bz_pt("month"), bz_pt("time") if late_key_ok else bz_pt("day", True)]

    t1, _ = _gua_stage(mh, "ben")
    t2, _ = _gua_stage(mh, "hu")
    t3, _ = _gua_stage(mh, "bian")
    sancai_score = float((wg.get("sancai") or {}).get("score", 70))
    nm_pts = [
        0.5 * _wuge_stage(wg, ("tian", "di")) + 0.5 * t1,
        0.5 * (0.6 * _wuge_stage(wg, ("ren",)) + 0.4 * sancai_score) + 0.5 * t2,
        0.5 * _wuge_stage(wg, ("zong", "wai")) + 0.5 * t3,
    ]
    wb = weights["bazi"] / 100.0
    wn = 1 - wb
    comb = [bz_pts[i] * wb + nm_pts[i] * wn for i in range(3)]
    stages = []
    for i, label in enumerate(("早 · 根基", "中 · 主运", "晚 · 后景")):
        stages.append({"label": label, "bazi": _r(bz_pts[i]), "name": _r(nm_pts[i]),
                       "mix": _r(comb[i])})
    slope = comb[2] - comb[0]

    fit = _use_god_fit(r)
    echoes = _echoes(r)
    res = {"score": _r(res_score), "pairs": pairs, "dominant": dom,
           "consensus_wx": consensus_wx, "consensus_missing": consensus_missing,
           "lacking": lacking_all}
    cross = _cross_items(r, fit, res, gr, stages)

    tens = {"印证": 0, "张力": 0, "调和": 0}
    for it in cross:
        tens[it["level"]] = tens.get(it["level"], 0) + 1

    out = {
        "version": "1.0",
        "framework": framework(),
        "weights": weights,
        "weight_mode": wkey,
        "parts": {k: _r(v) for k, v in raw_parts.items()},
        "grades": {"bazi": (bz.get("balance") or {}).get("grade", ""),
                   "wuge": wg.get("grade", ""), "meihua": mh.get("grade", ""),
                   "wuyin": wy.get("grade", "")},
        "agree": {k: _r(v, 3) for k, v in agree.items()},
        "factor": {k: _r(v, 3) for k, v in factor.items()},
        "score_base": _r(base),
        "score": _r(adjusted),
        "grade": _grade(adjusted),
        "delta": _r(adjusted - base, 2),
        "consensus": {"score": _r(consensus * 100), "wuxing": res["score"],
                      "gangrou": gr_sign, "spread": _r(gr_spread, 2)},
        "wuxing": {"vectors": {k: {w: _r(v, 3) for w, v in shares[k].items()}
                               for k in keys},
                   "raw": {k: {w: _r(v, 2) for w, v in vecs[k].items()} for k in keys},
                   "pairs": pairs, "score": res["score"],
                   "dominant": dom, "consensus_wx": consensus_wx,
                   "consensus_missing": consensus_missing, "lacking": lacking_all,
                   # 五格数理五行另算，不入共振，仅作参考
                   "wuge": {"vectors": {w: _r(v, 3) for w, v in wuge_share.items()},
                            "dominant": _dominant(wuge_share)}},
        "gangrou": {"values": gr, "mean": _r(gr_mean, 2), "spread": _r(gr_spread, 2),
                    "sign": gr_sign, "pos": pos, "neg": neg},
        "stages": {"points": stages, "slope": _r(slope, 1),
                   "late_estimated": not late_key_ok},
        "use_god": {k: v for k, v in fit.items() if k != "items"},
        "use_god_items": fit["items"],
        "echoes": echoes,
        "cross": cross,
        "tension": tens,
    }
    out["trend"] = _trend(out, r)
    return out


def _grade(s):
    if s >= 80:
        return "上佳"
    if s >= 70:
        return "佳"
    if s >= 60:
        return "平"
    if s >= 50:
        return "偏弱"
    return "宜斟酌"


def _trend(syn, r):
    """整体趋势解读：3–4 句，全部由数值驱动，不添断语。"""
    lines = []
    t = syn["tension"]
    lines.append(
        f"合成 {syn['score']:.1f}（{syn['grade']}）：互证率 {syn['consensus']['score']:.0f}%、"
        f"五行共振 {syn['wuxing']['score']:.0f}%、刚柔{syn['consensus']['gangrou']}。"
        f"印证 {t.get('印证', 0)} 条、张力 {t.get('张力', 0)} 条、调和 {t.get('调和', 0)} 条。")

    ug = syn["use_god"]
    if ug["verdict"] == "名助命用":
        s2 = f"喜忌取向一致：姓名所带五行落于用神一侧，命局所急在名中有着落。"
    elif ug["verdict"] == "名逆命用":
        s2 = (f"喜忌取向相悖：用神{'、'.join(ug['yongshen']) or '未定'}在名中着落单薄，"
              f"而忌仇之气象已成形，属「名不副命」一路，宜在取用上另作调整。")
    else:
        s2 = (f"喜忌取向持平：用神{'、'.join(ug['yongshen']) or '未定'}与忌仇在名中各占其位，"
              f"补泻互抵，姓名对命局既不助势、亦不为累。")
    lines.append(s2)

    st = syn["stages"]["points"]
    slope = syn["stages"]["slope"]
    if slope >= 4:
        shape = "由早及晚渐宽，属后成之局"
    elif slope <= -4:
        shape = "由早及晚渐紧，早段力足而晚程宜守"
    else:
        shape = "三段大致持平，属匀速之局"
    lines.append(
        f"时段走势：{st[0]['mix']:.0f} → {st[1]['mix']:.0f} → {st[2]['mix']:.0f}"
        f"（{shape}）；其中命线 {st[0]['bazi']:.0f}/{st[1]['bazi']:.0f}/{st[2]['bazi']:.0f}、"
        f"名线 {st[0]['name']:.0f}/{st[1]['name']:.0f}/{st[2]['name']:.0f}，"
        f"二者{'同向' if (st[2]['bazi'] - st[0]['bazi']) * (st[2]['name'] - st[0]['name']) > 0 else '分途'}。")

    tens = [c for c in syn["cross"] if c["level"] == "张力"]
    if tens:
        lines.append("宜留意：" + "、".join(c["title"] for c in tens[:2])
                     + "——详见交叉印证，宜择时而动。")
    else:
        lines.append("三源无明显相悖处，唯「一致」不等于「已验」，仍以行事为准。")
    return {"lines": lines}


# ---------------------------------------------------------------- 绘图

def _bg():
    return (f'<rect width="{SW}" height="{SH}" fill="url(#paperG)"/>'
            f'<rect width="{SW}" height="{SH}" filter="url(#grain)" opacity="0.075"/>'
            f'<rect width="{SW}" height="{SH}" fill="url(#vig)"/>'
            + dc._deity_bg(SW, SH))


def _frame():
    m1, m2 = 26, 34
    g = [f'<g filter="url(#rough)">',
         f'<rect x="{m1}" y="{m1}" width="{SW - 2*m1}" height="{SH - 2*m1}" fill="none"'
         f' stroke="{dc.INK}" stroke-width="2.6" opacity="0.82"/>',
         f'<rect x="{m2}" y="{m2}" width="{SW - 2*m2}" height="{SH - 2*m2}" fill="none"'
         f' stroke="{dc.INK}" stroke-width="0.9" opacity="0.5"/>', '</g>']
    for (x, y, dx, dy) in ((m2, m2, 1, 1), (SW - m2, m2, -1, 1),
                           (m2, SH - m2, 1, -1), (SW - m2, SH - m2, -1, -1)):
        g.append(f'<path d="M {x} {y + dy*16} L {x} {y} L {x + dx*16} {y}"'
                 f' fill="none" stroke="{dc.INK}" stroke-width="3.4" opacity="0.75"/>')
    return "".join(g)


def _sec(idx, y, title, note=""):
    out = [f'<circle cx="86" cy="{y - 5}" r="11.5" fill="none" stroke="{dc.INK}"'
           f' stroke-width="1.4" opacity="0.7"/>',
           dc.htext(86, y - 0.5, idx, 12, dc.INK, "middle", font=dc.FONT_SONG)]
    out.append(dc.htext(108, y, title, 17, dc.INK, spacing=3.5, weight="bold"))
    if note:
        out.append(dc.htext(906, y - 1, note, 10.5, dc.INK_SOFT, "end", spacing=1))
    out.append(f'<path d="M 74 {y + 11} H 906" stroke="{dc.INK}" stroke-width="0.9"'
               f' opacity="0.32"/>')
    return "".join(out)


def _clip(s, n):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


def _bar(x, y, w, h, frac, color, bg=None):
    frac = _clamp(frac, 0, 1)
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg or dc.PAPER_D}"'
            f' opacity="0.85" rx="{h/2}"/>'
            f'<rect x="{x}" y="{y}" width="{max(0.0, w*frac):.1f}" height="{h}"'
            f' fill="{color}" opacity="0.88" rx="{h/2}"/>')


def _src_card(x, y, w, h, key, score, grade, note, weights=None):
    """四源分数卡。weights 传当前实际权重模型（full/no_time），
    不传时回退 full——时辰未详时不得显示 34/26/22/18 而实际按 22/28/26/24 计算。
    """
    wgt = (weights or WEIGHTS["full"]).get(key, WEIGHTS["full"][key])
    c = SOURCE_COLOR[key]
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{dc.PAPER}"'
           f' opacity="0.72" stroke="{c}" stroke-width="1.1" rx="2"/>',
           f'<rect x="{x}" y="{y}" width="4" height="{h}" fill="{c}" opacity="0.85"/>']
    out.append(dc.htext(x + 16, y + 28, SOURCE_NAME[key], 16.5, dc.INK, weight="bold",
                        spacing=2))
    out.append(dc.htext(x + w - 14, y + 30, f"{wgt}%", 19, c, "end",
                        font=dc.FONT_SONG, weight="bold"))
    out.append(dc.htext(x + 16, y + 50, SOURCE_NOTE[key], 10.5, dc.INK_SOFT, spacing=2))
    out.append(_bar(x + 16, y + 64, w - 30, 7, score / 100.0, c))
    out.append(dc.htext(x + 16, y + 92, f"{score:.1f}", 21, c, font=dc.FONT_SONG,
                        weight="bold"))
    out.append(dc.htext(x + 68, y + 92, f"/100 · {grade}", 11.5, dc.INK_MID))
    out.append(dc.htext(x + 16, y + 114, _clip(note, 18), 10.5, dc.INK_SOFT))
    return "".join(out)


def _radar(cx, cy, R, shares, extra_share=None, labels=True):
    out = []
    ang = [-90 + i * 72 for i in range(5)]
    pts = [(cx + math.cos(math.radians(a)) * R, cy + math.sin(math.radians(a)) * R)
           for a in ang]
    for f in (0.25, 0.5, 0.75, 1.0):
        p = " ".join(f"{cx + (x-cx)*f:.1f},{cy + (y-cy)*f:.1f}" for x, y in pts)
        out.append(f'<polygon points="{p}" fill="none" stroke="{dc.INK}"'
                   f' stroke-width="{0.9 if f == 1 else 0.6}"'
                   f' opacity="{0.26 if f == 1 else 0.14}"/>')
    for (x, y) in pts:
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"'
                   f' stroke="{dc.INK}" stroke-width="0.6" opacity="0.16"/>')
    if labels:
        for i, wx in enumerate(WX):
            lx = cx + math.cos(math.radians(ang[i])) * (R + 20)
            ly = cy + math.sin(math.radians(ang[i])) * (R + 20) + 5
            out.append(dc.htext(lx, ly, wx, 14, dc.WUXING_COLOR[wx], "middle", weight="bold"))
    # 面：由外向内叠（先画大，后画小），最外层八字
    order = ["bazi", "meihua", "wuyin"]
    for key in order:
        v = shares[key]
        p = []
        for i, wx in enumerate(WX):
            r = min(1.0, v.get(wx, 0) / 0.40) * R
            p.append(f"{cx + math.cos(math.radians(ang[i]))*r:.1f},"
                     f"{cy + math.sin(math.radians(ang[i]))*r:.1f}")
        out.append(f'<polygon points="{" ".join(p)}" fill="{SOURCE_COLOR[key]}"'
                   f' fill-opacity="0.07" stroke="{SOURCE_COLOR[key]}" stroke-width="1.6"'
                   f' opacity="0.9" stroke-linejoin="round"/>')
    # 五格另算：虚线轮廓，不填面，仅作视觉参照
    if extra_share:
        p = []
        for i, wx in enumerate(WX):
            r = min(1.0, extra_share.get(wx, 0) / 0.40) * R
            p.append(f"{cx + math.cos(math.radians(ang[i]))*r:.1f},"
                     f"{cy + math.sin(math.radians(ang[i]))*r:.1f}")
        out.append(f'<polygon points="{" ".join(p)}" fill="none"'
                   f' stroke="{SOURCE_COLOR["wuge"]}" stroke-width="2.0"'
                   f' stroke-dasharray="4 3" opacity="0.75" stroke-linejoin="round"/>')
    return "".join(out)


def _gangrou_axis(x0, x1, y, val, color, label, sub):
    cx = (x0 + x1) / 2
    half = (x1 - x0) / 2
    out = [f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{dc.INK}"'
           f' stroke-width="0.8" opacity="0.28"/>',
           f'<line x1="{cx}" y1="{y-6}" x2="{cx}" y2="{y+6}" stroke="{dc.INK}"'
           f' stroke-width="0.9" opacity="0.42"/>']
    px = cx + val * half
    out.append(f'<line x1="{cx}" y1="{y}" x2="{px:.1f}" y2="{y}" stroke="{color}"'
               f' stroke-width="2.6" opacity="0.75"/>')
    out.append(f'<circle cx="{px:.1f}" cy="{y}" r="7" fill="{color}" opacity="0.92"'
               f' stroke="{dc.PAPER}" stroke-width="1.6"/>')
    out.append(dc.htext(x0 - 12, y + 5, label, 12.5, dc.INK, "end", spacing=1))
    out.append(dc.htext(x0 - 74, y + 5, sub, 10, dc.INK_SOFT, "end"))
    out.append(dc.htext(px + (14 if val >= 0 else -14), y + 4.5, f"{val:+.2f}", 10.5,
                        color, "start" if val >= 0 else "end", font=dc.FONT_SONG))
    return "".join(out)


def _trend_chart(x0, x1, y0, y1, points):
    lo, hi = 40, 100
    xs = [x0 + i * (x1 - x0) / 2 for i in range(3)]

    def py(v):
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    out = []
    for g in (50, 60, 70, 80, 90, 100):
        yy = py(g)
        out.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}"'
                   f' stroke="{dc.INK}" stroke-width="0.5" opacity="{0.16 if g%20 else 0.24}"/>')
        out.append(dc.htext(x0 - 12, yy + 4, str(g), 9.5, dc.INK_SOFT, "end"))
    for i, lab in enumerate(("早 · 根基", "中 · 主运", "晚 · 后景")):
        out.append(dc.htext(xs[i], y1 + 22, lab, 11, dc.INK_SOFT, "middle", spacing=1))
    series = (("命线", "bazi", dc.INK, 1.5, "5 3"),
              ("名线", "name", dc.CINNABAR, 1.8, "6 4"),
              ("合线", "mix", dc.OCHRE, 3.0, ""))
    for name, key, color, wid, dash in series:
        seq = [py(p[key]) for p in points]
        d = " ".join(("M" if i == 0 else "L") + f" {xs[i]:.1f} {seq[i]:.1f}"
                     for i in range(3))
        da = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{wid}"'
                   f'{da} opacity="0.9" stroke-linecap="round"/>')
        for i in range(3):
            out.append(f'<circle cx="{xs[i]:.1f}" cy="{seq[i]:.1f}"'
                       f' r="{3.6 if key != "mix" else 4.6}" fill="{color}"'
                       f' stroke="{dc.PAPER}" stroke-width="1.4"/>')
        if key == "mix":
            for i in range(3):
                out.append(f'<rect x="{xs[i]-15:.1f}" y="{seq[i]-24:.1f}" width="30"'
                           f' height="15" rx="3" fill="{dc.PAPER}" opacity="0.92"/>')
                out.append(dc.htext(xs[i], seq[i] - 12, f"{points[i][key]:.0f}", 11,
                                    color, "middle", font=dc.FONT_SONG, weight="bold"))
    # 图例
    lx = x1 - 168
    for i, (name, key, color, wid, dash) in enumerate(series):
        yy = y0 + 6 + i * 18
        out.append(f'<line x1="{lx}" y1="{yy}" x2="{lx + 26}" y2="{yy}" stroke="{color}"'
                   f' stroke-width="{wid}"' + (f' stroke-dasharray="{dash}"' if dash else "")
                   + '/>')
        out.append(dc.htext(lx + 34, yy + 4, name, 10.5, dc.INK_MID))
    return "".join(out)


def _mark(level):
    sym = {"印证": "✓", "张力": "!", "调和": "≈"}.get(level, "·")
    col = {"印证": dc.CINNABAR, "张力": dc.ASH, "调和": dc.OCHRE}.get(level, dc.INK)
    return sym, col


def render_synthesis(r, path):
    syn = r.get("synthesis") or cross_analysis(r)
    if not syn:
        return ""
    inp = r.get("input") or {}
    # 名称来源统一：个人 姓+名，机构 input.name（此前机构恒显示「—」）
    name = ((inp.get("surname", "") + inp.get("given", "")) or inp.get("name") or "—")
    bz = r["bazi"]
    pillars = bz.get("pillars") or {}

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{SW}" height="{SH}"'
         f' viewBox="0 0 {SW} {SH}" font-family="{dc.FONT}">',
         dc._defs(), _bg(), _frame()]

    # ---------------- 标题
    p.append(dc.htext(74, 78, "五維統合圖", 32, dc.INK, spacing=8, weight="bold"))
    p.append(dc.htext(76, 102, "五格剖象 · 五音納音 · 梅花易數 · 四柱八字　跨體系合成", 12.5,
                      dc.INK_SOFT, spacing=2.2))
    p.append(f'<path d="M 74 114 Q 170 110 262 115 T 372 113" fill="none"'
             f' stroke="{dc.INK}" stroke-width="2.2" opacity="0.55" filter="url(#rough)"/>')
    p.append(dc.htext(906, 74, name, 26, dc.INK, "end", spacing=5))
    p.append(dc.htext(906, 100, "　".join((pillars.get(k) or "--") for k in
                                        ("year", "month", "day", "time")), 12.5,
                      dc.INK_MID, "end", spacing=3, font=dc.FONT_SONG))
    p.append(dc.htext(906, 118, f"真太陽時 {bz.get('true_solar_text', '')[:16]}　"
                                f"{'時辰已知' if bz.get('time_known') else '時辰未詳'}", 10,
                      dc.INK_SOFT, "end", spacing=1))
    p.append(dc._seal(880, 1534, "統合", 40, -5))

    # ---------------- 一 · 四源与权重
    p.append(_sec("一", 168, "四源分數與權重", "原始分語義不同，先歸一再合成"))
    # 权重按当前模型显示（时辰未详走 no_time：八字 22、名内 28/26/24）
    wgt_now = syn.get("weights") or WEIGHTS["full"]
    w_bazi = wgt_now["bazi"]
    w_name = 100 - w_bazi
    cards = [("bazi", r["bazi"]["balance"]["score"], r["bazi"]["balance"]["grade"],
              f"流通度·{(r['bazi']['strength'] or {}).get('label','')}"),
             ("wuge", r["wuge"]["score"], r["wuge"]["grade"],
              f"三才{(r['wuge'].get('sancai') or {}).get('luck','')}·{(r['wuge'].get('sancai') or {}).get('combo','')}"),
             ("meihua", r["meihua"]["score"], r["meihua"]["grade"],
              f"{(r['meihua']['cast']['bian']['gua']['name'])}收局"),
             ("wuyin", r["wuyin"]["score"], r["wuyin"]["grade"],
              f"{r['wuyin'].get('wuyin_seq','')}·{r['wuyin'].get('pingze_seq','')}")]
    pos = [(74, 196), (300, 196), (74, 334), (300, 334)]
    for (key, sc, gd, note), (x, y) in zip(cards, pos):
        p.append(_src_card(x, y, 212, 126, key, float(sc), gd, note, weights=wgt_now))

    # 右：三层权重（按实际模型绘制，不再写死 full）
    bx, bw = 540, 366
    p.append(dc.htext(bx, 206, "權重邏輯 · 三層", 13, dc.INK, spacing=2, weight="bold"))
    # 一层
    p.append(dc.htext(bx, 232, f"一層　體 {w_bazi} ／ 用 {w_name}", 10.5,
                      dc.INK_SOFT, spacing=1))
    p.append(_bar(bx, 238, bw, 15, w_bazi / 100.0, dc.INK))
    p.append(f'<rect x="{bx + bw*w_bazi/100:.1f}" y="238" width="{bw*w_name/100:.1f}"'
             f' height="15" fill="{dc.CINNABAR}" opacity="0.72" rx="3"/>')
    p.append(dc.htext(bx + bw * w_bazi / 200, 249, "體", 10.5, dc.PAPER, "middle"))
    p.append(dc.htext(bx + bw * (w_bazi + w_name / 2) / 100, 249,
                      "用（姓名三面）", 10.5, dc.PAPER, "middle"))
    # 二层
    seg = [("五格", wgt_now["wuge"], dc.CINNABAR), ("梅花", wgt_now["meihua"], dc.OCHRE),
           ("五音", wgt_now["wuyin"], "#2E5E8C")]
    p.append(dc.htext(bx, 280, "二層　名內 "
                      + " ／ ".join(str(v) for _, v, _ in seg), 10.5,
                      dc.INK_SOFT, spacing=1))
    acc = 0
    for label, wgt, col in seg:
        frac = wgt / float(w_name)
        p.append(f'<rect x="{bx + bw*acc:.1f}" y="286" width="{bw*frac:.1f}" height="15"'
                 f' fill="{col}" opacity="0.78"/>')
        p.append(dc.htext(bx + bw * (acc + frac / 2), 297, f"{label} {wgt}", 9.5,
                          dc.PAPER, "middle"))
        acc += frac
    # 三层
    p.append(dc.htext(bx, 328, "三層　互證加權 ×0.82–1.18", 10.5, dc.INK_SOFT, spacing=1))
    p.append(_prose_syn(bx, 344, "同向者升權、孤證者降權；權重只在合成層生效，不改原始分。",
                        34, 10, 15, 1))

    # 综合
    p.append(f'<path d="M {bx} 362 H 906" stroke="{dc.INK}" stroke-width="0.8" opacity="0.25"/>')
    p.append(dc.htext(bx, 386, "統合加權", 11, dc.INK_SOFT, spacing=2))
    p.append(dc.htext(bx, 440, f"{syn['score']:.1f}", 46, dc.CINNABAR,
                      font=dc.FONT_SONG, weight="bold"))
    p.append(dc.htext(bx + 116, 440, "/ 100", 11, dc.INK_SOFT))
    p.append(dc.htext(bx + 116, 418, syn["grade"], 14, dc.CINNABAR, spacing=2))
    p.append(dc.htext(bx + 178, 416, f"基準 {syn['score_base']:.1f}", 10.5, dc.INK_SOFT))
    p.append(dc.htext(bx + 178, 434, f"互證調整 {_sgn(syn['delta'])}", 10.5, dc.INK_SOFT))
    p.append(dc.htext(bx + 178, 452, f"互證率 {syn['consensus']['score']:.0f}%", 10.5,
                      dc.INK_SOFT))

    # ---------------- 二 · 五行共振
    p.append(_sec("二", 492, "五行共振 · 四源疊圖", "五格虛線參照，不計入共振；三源實面為共振主體"))
    wuge_vec = (syn["wuxing"].get("wuge") or {}).get("vectors")
    p.append(_radar(226, 654, 106, syn["wuxing"]["vectors"], extra_share=wuge_vec))
    p.append(dc.htext(214, 792, "外圈＝佔比 40%（滿格）", 9.5, dc.INK_SOFT, "middle"))

    # 图例：三源主导 + 五格参照
    lx, ly = 398, 566
    for i, key in enumerate(("bazi", "meihua", "wuyin")):
        yy = ly + i * 34
        col = SOURCE_COLOR[key]
        p.append(f'<line x1="{lx}" y1="{yy}" x2="{lx+22}" y2="{yy}" stroke="{col}"'
                 f' stroke-width="2.4" opacity="0.9"/>')
        p.append(dc.htext(lx + 30, yy + 4, SOURCE_NAME[key], 11, dc.INK))
        dw = syn["wuxing"]["dominant"].get(key) or []
        p.append(dc.htext(lx + 30, yy + 18, "主 " + ("、".join(dw) if dw else "均衡"),
                          9.5, col))
    # 五格虚线图例
    yy_wg = ly + 3 * 34
    p.append(f'<line x1="{lx}" y1="{yy_wg}" x2="{lx+22}" y2="{yy_wg}"'
             f' stroke="{SOURCE_COLOR["wuge"]}" stroke-width="2.0"'
             f' stroke-dasharray="4 3" opacity="0.75"/>')
    p.append(dc.htext(lx + 30, yy_wg + 4, f"{SOURCE_NAME['wuge']}（另算）", 11, dc.INK))
    dw_wg = "、".join((syn["wuxing"].get("wuge") or {}).get("dominant") or [])
    p.append(dc.htext(lx + 30, yy_wg + 18, "主 " + (dw_wg if dw_wg else "均衡"),
                      9.5, SOURCE_COLOR["wuge"]))

    p.append(dc.htext(398, 720, "三源共主", 9.5, dc.INK_SOFT, spacing=1))
    p.append(dc.htext(398, 742, "、".join(syn["wuxing"]["consensus_wx"]) or "無", 15,
                      dc.CINNABAR, font=dc.FONT_SONG, weight="bold"))
    if syn["wuxing"]["consensus_missing"]:
        p.append(dc.htext(398, 760, "未見 " + "、".join(syn["wuxing"]["consensus_missing"]),
                          9, dc.INK_SOFT))
    if syn["wuxing"]["lacking"]:
        p.append(dc.htext(398, 782, "三源俱缺 " + "、".join(syn["wuxing"]["lacking"]),
                          10, dc.ASH))

    # 右：共振度 + 两两
    rx = 560
    p.append(dc.htext(rx, 552, "五行共振度", 11, dc.INK_SOFT, spacing=2))
    p.append(dc.htext(rx, 602, f"{syn['wuxing']['score']:.0f}", 44, dc.OCHRE,
                      font=dc.FONT_SONG, weight="bold"))
    p.append(dc.htext(rx + 86, 602, "%", 13, dc.INK_SOFT))
    p.append(dc.htext(rx + 106, 600, "兩兩餘弦均值", 9.5, dc.INK_SOFT))
    for i, pr in enumerate(syn["wuxing"]["pairs"]):
        yy = 632 + i * 29
        p.append(dc.htext(rx, yy, pr["pair"], 9.5, dc.INK_MID))
        p.append(_bar(rx + 158, yy - 8, 150, 7, pr["cos"], dc.INK if pr["cos"] >= 0.8 else dc.OCHRE))
        p.append(dc.htext(rx + 344, yy, f"{pr['cos']*100:.0f}", 10.5, dc.INK_MID, "end",
                          font=dc.FONT_SONG))

    # ---------------- 三 · 刚柔
    p.append(_sec("三", 822, "剛柔對照 · 內外是否同調", "左剛右柔；四點分散則表裡不一"))
    gv = syn["gangrou"]["values"]
    ax0, ax1 = 186, 546
    for i, (key, label) in enumerate((("bazi", "八字"), ("wuge", "五格"),
                                      ("meihua", "梅花"), ("wuyin", "五音"))):
        yy = 862 + i * 27
        sub = {"bazi": "身強弱", "wuge": "格陰陽", "meihua": "體用", "wuyin": "平仄"}[key]
        p.append(_gangrou_axis(ax0, ax1, yy, gv[key], SOURCE_COLOR[key], label, sub))
    p.append(dc.htext(ax0 - 6, 958, "剛", 10, dc.INK_SOFT))
    p.append(dc.htext((ax0 + ax1) / 2, 958, "中和", 10, dc.INK_SOFT, "middle"))
    p.append(dc.htext(ax1 + 6, 958, "柔", 10, dc.INK_SOFT, "end"))
    p.append(dc.htext(560, 878, f"剛柔主軸 {syn['gangrou']['mean']:+.2f}", 13, dc.INK,
                      font=dc.FONT_SONG, weight="bold"))
    p.append(dc.htext(560, 900, f"離散 {syn['gangrou']['spread']:.2f}　"
                                f"{'同向' if syn['gangrou']['sign'] == '同向' else syn['gangrou']['sign']}",
                      11, dc.INK_MID))
    gr_txt = ("四點同側：骨架與氣韻一致，內外少牴牾。" if syn["gangrou"]["sign"] == "同向"
              else "兩側分立：一部分偏剛、一部分偏柔，屬「表裡不一」之象——"
                   "行事偏剛而氣韻偏柔，或反之，須看哪一層更貼近日常使用。")
    p.append(_prose_syn(560, 922, gr_txt, 32, 10, 14, 2))

    # ---------------- 四 · 三段趋势
    p.append(_sec("四", 978, "三段走勢 · 早／中／晚", "命線取自柱位，名線取格位與卦位"))
    pts = syn["stages"]["points"]
    p.append(_trend_chart(126, 520, 1010, 1150, pts))
    # 右侧数值表
    tx = 560
    p.append(dc.htext(tx, 1018, "段　命線　名線　合線", 9.5, dc.INK_SOFT, spacing=1))
    for i, pt in enumerate(pts):
        yy = 1042 + i * 30
        p.append(dc.htext(tx, yy, pt["label"], 10.5, dc.INK_MID))
        for j, (key, col) in enumerate((("bazi", dc.INK), ("name", dc.CINNABAR),
                                        ("mix", dc.OCHRE))):
            p.append(dc.htext(tx + 112 + j * 62, yy, f"{pt[key]:.0f}", 12.5, col,
                              font=dc.FONT_SONG, weight="bold" if key == "mix" else "normal"))
    p.append(dc.htext(tx, 1142, f"合線斜率 {syn['stages']['slope']:+.1f}", 12, dc.INK,
                      font=dc.FONT_SONG, weight="bold"))
    shape = ("後成之局" if syn["stages"]["slope"] >= 4 else
             "早強晚守" if syn["stages"]["slope"] <= -4 else "勻速之局")
    p.append(dc.htext(tx + 156, 1142, shape, 12, dc.CINNABAR, spacing=1))
    p.append(_prose_syn(tx, 1162, "命線（柱位生克）與名線（格運卦象）走勢不必相同；"
                                  "同向則趨勢可信度較高，分途則以合線為主、不強斷。",
                        33, 9.8, 14, 2))

    # ---------------- 五 · 交叉印证
    n = min(8, len(syn["cross"]))
    _rows = (1226, 1280, 1334, 1388)
    p.append(_sec("五", 1210, "交叉印證", f"印證 {syn['tension'].get('印证',0)}"
                                        f" · 張力 {syn['tension'].get('张力',0)}"
                                        f" · 調和 {syn['tension'].get('调和',0)}"))
    for i in range(n):
        it = syn["cross"][i]
        col = 74 if i % 2 == 0 else 500
        row = _rows[i // 2]
        sym, scc = _mark(it["level"])
        p.append(f'<circle cx="{col + 14}" cy="{row + 14}" r="10.5" fill="none"'
                 f' stroke="{scc}" stroke-width="1.4"/>')
        p.append(dc.htext(col + 14, row + 18, sym, 11, scc, "middle"))
        p.append(dc.htext(col + 34, row + 18, it["title"], 13.5, dc.INK, weight="bold",
                          spacing=1.5))
        p.append(dc.htext(col + 406, row + 18, it["level"], 9.5, scc, "end", spacing=1))
        for j, ln in enumerate(dc.wrap_cn(it["detail"], 33, 2)):
            p.append(dc.htext(col + 34, row + 33 + j * 15, ln, 9.8, dc.INK_MID))

    # ---------------- 六 · 趋势解读
    if syn.get("echoes"):
        ech = "；".join(f"{e['pair']} {e['why']}" for e in syn["echoes"][:3])
        p.append(dc.htext(74, 1454, "數象（形式層，不作吉凶）：", 9.5, dc.INK_SOFT, spacing=1))
        p.append(dc.htext(222, 1454, _clip(ech, 52), 9.5, dc.INK_MID))

    p.append(_sec("六", 1478, "整體趨勢解讀", ""))
    for i, line in enumerate(syn["trend"]["lines"][:4]):
        p.append(_prose_syn(74, 1498 + i * 17, line, 62, 10.2, 17, 1))

    p.append(dc.htext(SW / 2, 1570, dc.DISCLAIMER_NOTE, 10.5, dc.INK_SOFT, "middle", spacing=1))
    p.append("</svg>")
    svg = "\n".join(p)
    return dc._write(path, svg)


def _prose_syn(x, y, text, width=38, size=12, gap=18, max_lines=2, color=None):
    lines = dc.wrap_cn(text, width, max_lines)
    return "".join(dc.htext(x, y + i * gap, ln, size, color or dc.INK_MID)
                   for i, ln in enumerate(lines))


# ---------------------------------------------------------------- 简化版统合图（三选一）

def _lite_head(p, w, title, sub, name, pillars, bz):
    """三张简化版统合图共用的头部：标题 + 名称 + 四柱 + 真太阳时。"""
    p.append(dc.htext(56, 66, title, 27, dc.INK, spacing=6, weight="bold"))
    p.append(dc.htext(58, 90, sub, 11.5, dc.INK_SOFT, spacing=2))
    p.append(f'<path d="M 56 102 Q 140 98 224 103 T 320 101" fill="none"'
             f' stroke="{dc.INK}" stroke-width="1.8" opacity="0.5" filter="url(#rough)"/>')
    p.append(dc.htext(w - 56, 62, name, 22, dc.INK, "end", spacing=4))
    p.append(dc.htext(w - 56, 86, "　".join((pillars.get(k) or "--") for k in
                                            ("year", "month", "day", "time")), 11.5,
                      dc.INK_MID, "end", spacing=2, font=dc.FONT_SONG))
    p.append(dc.htext(w - 56, 102, f"真太陽時 {bz.get('true_solar_text', '')[:16]}　"
                                   f"{'時辰已知' if bz.get('time_known') else '時辰未詳'}",
                      9.5, dc.INK_SOFT, "end"))


def _lite_bg(w, h):
    return (f'<rect width="{w}" height="{h}" fill="url(#paperG)"/>'
            f'<rect width="{w}" height="{h}" filter="url(#grain)" opacity="0.075"/>'
            f'<rect width="{w}" height="{h}" fill="url(#vig)"/>'
            + dc._deity_bg(w, h))


def _lite_frame(w, h):
    m1, m2 = 20, 26
    return (f'<g filter="url(#rough)">'
            f'<rect x="{m1}" y="{m1}" width="{w - 2*m1}" height="{h - 2*m1}"'
            f' fill="none" stroke="{dc.INK}" stroke-width="2.0" opacity="0.78"/>'
            f'<rect x="{m2}" y="{m2}" width="{w - 2*m2}" height="{h - 2*m2}"'
            f' fill="none" stroke="{dc.INK}" stroke-width="0.8" opacity="0.45"/>'
            f'</g>')


def _lite_svg_open(w, h):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"'
            f' viewBox="0 0 {w} {h}" font-family="{dc.FONT}">',
            dc._defs(), _lite_bg(w, h), _lite_frame(w, h)]


def _lite_meta(r):
    syn = r.get("synthesis") or cross_analysis(r)
    if not syn:
        return None, None, None, None
    bz = r["bazi"]
    pillars = bz.get("pillars") or {}
    inp = r.get("input") or {}
    name = ((inp.get("surname", "") + inp.get("given", "")) or inp.get("name") or "—")
    return syn, bz, pillars, name


# 05a · 统合速览：一页只看大分数、四源评分与一句话结论
def render_synthesis_lite(r, path):
    syn, bz, pillars, name = _lite_meta(r)
    if not syn:
        return ""
    LW, LH = 820, 640
    p = _lite_svg_open(LW, LH)
    _lite_head(p, LW, "統合速覽", "一頁看總分 · 四源評分 · 一句話結論", name, pillars, bz)
    p.append(dc._seal(LW - 60, LH - 48, "統合", 34, -5))

    # 左：大分数卡
    gx, gy, gw, gh = 56, 142, 420, 190
    p.append(f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" fill="{dc.PAPER}"'
             f' opacity="0.78" stroke="{dc.CINNABAR}" stroke-width="1.3" rx="3"/>')
    p.append(dc.htext(gx + 22, gy + 34, "統合加權", 13, dc.INK_SOFT, spacing=3))
    p.append(dc.htext(gx + 22, gy + 112, f"{syn['score']:.1f}", 64, dc.CINNABAR,
                      font=dc.FONT_SONG, weight="bold"))
    p.append(dc.htext(gx + 22 + 150, gy + 112, "/ 100", 13, dc.INK_SOFT))
    p.append(dc.htext(gx + 22 + 150, gy + 88, syn["grade"], 17, dc.CINNABAR,
                      spacing=2, weight="bold"))
    p.append(dc.htext(gx + 22, gy + 150, f"基準 {syn['score_base']:.1f}　"
                                        f"互證調整 {_sgn(syn['delta'])}",
                      12, dc.INK_MID))
    p.append(dc.htext(gx + 22, gy + 172,
                      f"{'時辰已知' if syn['weight_mode'] == 'full' else '時辰未詳'}"
                      f"　權重模式 {syn['weight_mode']}", 10, dc.INK_SOFT))

    # 右：三个小指标
    kpis = [("互證率", f"{syn['consensus']['score']:.0f}", "%",
             f"剛柔{syn['consensus']['gangrou']}"),
            ("五行共振", f"{syn['wuxing']['score']:.0f}", "%",
             "、".join(syn["wuxing"]["consensus_wx"]) or "均衡"),
            ("用神契合", f"{syn['use_god']['score']:.0f}", "分",
             syn["use_god"]["verdict"])]
    for i, (lab, val, unit, note) in enumerate(kpis):
        kx = 496 + (i % 2) * 152
        ky = 142 + (i // 2) * 98
        kw, kh = (140, 90) if i < 2 else (292, 90)
        p.append(f'<rect x="{kx}" y="{ky}" width="{kw}" height="{kh}" fill="{dc.PAPER}"'
                 f' opacity="0.72" stroke="{dc.INK}" stroke-width="0.9" rx="3"/>')
        p.append(dc.htext(kx + 14, ky + 26, lab, 11.5, dc.INK_SOFT, spacing=2))
        p.append(dc.htext(kx + 14, ky + 66, val, 30, dc.OCHRE, font=dc.FONT_SONG,
                          weight="bold"))
        p.append(dc.htext(kx + 14 + 62, ky + 66, unit, 11, dc.INK_SOFT))
        p.append(dc.htext(kx + 14, ky + 82, _clip(note, 16), 9.5, dc.INK_MID))

    # 中：四源评分横条
    p.append(dc.htext(56, 348, "四源評分與權重", 13, dc.INK, spacing=2, weight="bold"))
    rows = [("bazi", "四柱八字"), ("wuge", "五格剖象"),
            ("meihua", "梅花易數"), ("wuyin", "五音納音")]
    for i, (key, label) in enumerate(rows):
        yy = 368 + i * 42
        sc = syn["parts"].get(key, 0)
        c = SOURCE_COLOR[key]
        wgt = (syn["weights"] or WEIGHTS["full"]).get(key, 0)
        p.append(dc.htext(56, yy + 16, label, 13, dc.INK, spacing=1))
        p.append(dc.htext(150, yy + 16, f"權重 {wgt}%", 10, dc.INK_SOFT))
        p.append(_bar(228, yy + 4, 420, 14, sc / 100.0, c))
        p.append(dc.htext(664, yy + 16, f"{sc:.1f}", 17, c, font=dc.FONT_SONG,
                          weight="bold"))
        p.append(dc.htext(716, yy + 16, syn["grades"].get(key, ""), 10.5, dc.INK_SOFT))

    # 底：一句话结论
    p.append(f'<path d="M 56 546 H 764" stroke="{dc.INK}" stroke-width="0.8"'
             f' opacity="0.28"/>')
    ug = syn["use_god"]
    head = ("喜忌取向一致：姓名所帶五行落於用神一側。" if ug["verdict"] == "名助命用"
            else "喜忌相悖：忌仇氣象已成，用神着落單薄。" if ug["verdict"] == "名逆命用"
            else "喜忌兩平：補瀉互抵，不助勢亦不為累。")
    p.append(dc.htext(56, 576, "一句話", 11, dc.INK_SOFT, spacing=2))
    p.append(dc.htext(56, 600, head, 13, dc.INK, weight="bold"))
    p.append(dc.htext(56, 622, _clip(syn["trend"]["lines"][0], 56), 10.5, dc.INK_MID))
    p.append(dc.htext(LW / 2, 636 - 4, dc.DISCLAIMER_NOTE, 9.5, dc.INK_SOFT, "middle"))
    p.append("</svg>")
    return dc._write(path, "\n".join(p))


# 05b · 五行平衡：雷达 + 喜忌对照 + 共振度
def render_synthesis_wuxing(r, path):
    syn, bz, pillars, name = _lite_meta(r)
    if not syn:
        return ""
    WW, WH = 820, 980
    p = _lite_svg_open(WW, WH)
    _lite_head(p, WW, "五行平衡", "三源共振 · 五格另算 · 喜忌對照", name, pillars, bz)
    p.append(dc._seal(WW - 60, WH - 48, "統合", 34, -5))

    # 左：雷达图
    p.append(dc.htext(56, 130, "五行佔比 · 三源疊圖", 13, dc.INK, spacing=2,
                      weight="bold"))
    wuge_vec = (syn["wuxing"].get("wuge") or {}).get("vectors")
    p.append(_radar(230, 400, 150, syn["wuxing"]["vectors"], extra_share=wuge_vec))
    p.append(dc.htext(230, 580, "外圈＝佔比 40%（滿格）", 9.5, dc.INK_SOFT, "middle"))
    # 图例
    for i, key in enumerate(("bazi", "meihua", "wuyin")):
        yy = 610 + i * 26
        p.append(f'<line x1="96" y1="{yy}" x2="118" y2="{yy}" stroke="{SOURCE_COLOR[key]}"'
                 f' stroke-width="2.4" opacity="0.9"/>')
        p.append(dc.htext(126, yy + 4, SOURCE_NAME[key], 11, dc.INK))
        dw = syn["wuxing"]["dominant"].get(key) or []
        p.append(dc.htext(216, yy + 4, "主 " + ("、".join(dw) if dw else "均衡"),
                          9.5, SOURCE_COLOR[key]))
    yy = 610 + 3 * 26
    p.append(f'<line x1="96" y1="{yy}" x2="118" y2="{yy}" stroke="{SOURCE_COLOR["wuge"]}"'
             f' stroke-width="2.0" stroke-dasharray="4 3" opacity="0.75"/>')
    p.append(dc.htext(126, yy + 4, f"{SOURCE_NAME['wuge']}（另算）", 11, dc.INK))
    dw_wg = "、".join((syn["wuxing"].get("wuge") or {}).get("dominant") or [])
    p.append(dc.htext(216, yy + 4, "主 " + (dw_wg if dw_wg else "均衡"), 9.5,
                      SOURCE_COLOR["wuge"]))

    # 右上：共振度
    rx = 480
    p.append(dc.htext(rx, 130, "五行共振度", 13, dc.INK, spacing=2, weight="bold"))
    p.append(f'<rect x="{rx}" y="146" width="284" height="112" fill="{dc.PAPER}"'
             f' opacity="0.74" stroke="{dc.OCHRE}" stroke-width="1.1" rx="3"/>')
    p.append(dc.htext(rx + 20, 208, f"{syn['wuxing']['score']:.0f}", 52, dc.OCHRE,
                      font=dc.FONT_SONG, weight="bold"))
    p.append(dc.htext(rx + 20 + 96, 208, "%", 14, dc.INK_SOFT))
    p.append(dc.htext(rx + 20 + 118, 206, "兩兩餘弦均值", 10, dc.INK_SOFT))
    p.append(dc.htext(rx + 20, 240, "三源共主　", 10.5, dc.INK_SOFT))
    p.append(dc.htext(rx + 92, 240, "、".join(syn["wuxing"]["consensus_wx"]) or "均衡",
                      13, dc.CINNABAR, font=dc.FONT_SONG, weight="bold"))
    if syn["wuxing"]["consensus_missing"]:
        p.append(dc.htext(rx + 20, 254, "未見 "
                          + "、".join(syn["wuxing"]["consensus_missing"]), 9.5,
                          dc.INK_SOFT))
    if syn["wuxing"]["lacking"]:
        p.append(dc.htext(rx + 160, 254, "三源俱缺 "
                          + "、".join(syn["wuxing"]["lacking"]), 9.5, dc.ASH))

    # 右中：两两余弦
    p.append(dc.htext(rx, 292, "兩兩餘弦", 11.5, dc.INK_SOFT, spacing=2))
    for i, pr in enumerate(syn["wuxing"]["pairs"]):
        yy = 312 + i * 34
        p.append(dc.htext(rx, yy, pr["pair"], 10.5, dc.INK_MID))
        p.append(_bar(rx + 150, yy - 8, 104, 8, pr["cos"],
                      dc.INK if pr["cos"] >= 0.8 else dc.OCHRE))
        p.append(dc.htext(rx + 268, yy, f"{pr['cos']*100:.0f}", 11, dc.INK_MID, "end",
                          font=dc.FONT_SONG))

    # 右下：喜忌对照卡
    xj = bz.get("xi_ji") or {}
    ug = syn["use_god"]
    kx, ky, kw, kh = 480, 424, 284, 200
    p.append(f'<rect x="{kx}" y="{ky}" width="{kw}" height="{kh}" fill="{dc.PAPER}"'
             f' opacity="0.74" stroke="{dc.INK}" stroke-width="1.0" rx="3"/>')
    p.append(dc.htext(kx + 16, ky + 28, "八字喜忌 × 姓名落點", 13, dc.INK,
                      spacing=1.5, weight="bold"))
    rows = [("用神", xj.get("yongshen"), dc.CINNABAR),
            ("喜神", xj.get("xishen"), "#8E4A2C"),
            ("忌神", xj.get("jishen"), dc.ASH),
            ("仇神", xj.get("choushen"), dc.OCHRE)]
    for i, (lab, lst, col) in enumerate(rows):
        yy = ky + 54 + i * 24
        p.append(dc.htext(kx + 16, yy, lab, 11, dc.INK_SOFT, spacing=1))
        p.append(dc.htext(kx + 60, yy, "、".join(lst) if lst else "—", 12.5, col,
                          font=dc.FONT_SONG, weight="bold"))
    p.append(f'<path d="M {kx + 16} {ky + 156} H {kx + kw - 16}" stroke="{dc.INK}"'
             f' stroke-width="0.7" opacity="0.25"/>')
    vcol = {"名助命用": dc.CINNABAR, "名逆命用": dc.ASH}.get(ug["verdict"], dc.OCHRE)
    p.append(dc.htext(kx + 16, ky + 180, f"契合 {ug['verdict']}", 13, vcol,
                      weight="bold", spacing=1))
    p.append(dc.htext(kx + kw - 16, ky + 180, f"{ug['score']:.1f} 分", 13, vcol, "end",
                      font=dc.FONT_SONG, weight="bold"))

    # 底部：姓名五行落点（体卦 + 五音逐字）
    p.append(dc.htext(56, 700, "姓名五行落點（體卦與五音逐字）", 13, dc.INK,
                      spacing=2, weight="bold"))
    items = syn.get("use_god_items") or []
    for i, it in enumerate(items[:8]):
        yy = 726 + i * 30
        role_col = {"喜用": dc.CINNABAR, "忌仇": dc.ASH}.get(it["role"], dc.INK_SOFT)
        p.append(f'<circle cx="66" cy="{yy - 4}" r="4" fill="{role_col}" opacity="0.9"/>')
        p.append(dc.htext(80, yy, it["origin"], 12, dc.INK))
        p.append(dc.htext(210, yy, it["wuxing"], 13, dc.WUXING_COLOR.get(it["wuxing"], dc.INK),
                          font=dc.FONT_SONG, weight="bold"))
        p.append(dc.htext(252, yy, it["role"], 11, role_col, spacing=1))
        p.append(dc.htext(330, yy, f"權值 {it['value']:+.1f}", 10.5, dc.INK_SOFT,
                          font=dc.FONT_SONG))
        p.append(dc.htext(430, yy, f"權重 {it['weight']:.0f}", 10, dc.INK_SOFT))
    if not items:
        p.append(dc.htext(80, 726, "（無落點數據）", 11, dc.INK_SOFT))
    p.append(dc.htext(WW / 2, WH - 40, dc.DISCLAIMER_NOTE, 9.5, dc.INK_SOFT, "middle"))
    p.append("</svg>")
    return dc._write(path, "\n".join(p))


# 05c · 交叉印证：三段走势 + 印证条目 + 张力调和统计
def render_synthesis_cross(r, path):
    syn, bz, pillars, name = _lite_meta(r)
    if not syn:
        return ""
    CW, CH = 820, 980
    p = _lite_svg_open(CW, CH)
    _lite_head(p, CW, "交叉印證", "三段走勢 · 印證／張力／調和 · 趨勢解讀", name, pillars, bz)
    p.append(dc._seal(CW - 60, CH - 48, "統合", 34, -5))

    # 上：三段走势
    p.append(dc.htext(56, 130, "三段走勢 · 早／中／晚", 13, dc.INK, spacing=2,
                      weight="bold"))
    pts = syn["stages"]["points"]
    p.append(_trend_chart(120, 560, 156, 400, pts))
    # 右侧统计
    slope = syn["stages"]["slope"]
    shape = ("後成之局" if slope >= 4 else
             "早強晚守" if slope <= -4 else "勻速之局")
    tx = 600
    p.append(f'<rect x="{tx}" y="150" width="164" height="252" fill="{dc.PAPER}"'
             f' opacity="0.74" stroke="{dc.INK}" stroke-width="0.9" rx="3"/>')
    p.append(dc.htext(tx + 14, 178, "合線斜率", 11, dc.INK_SOFT, spacing=1))
    p.append(dc.htext(tx + 14, 214, f"{slope:+.1f}", 34, dc.CINNABAR, font=dc.FONT_SONG,
                      weight="bold"))
    p.append(dc.htext(tx + 14, 248, shape, 13, dc.CINNABAR, spacing=1, weight="bold"))
    if syn["stages"].get("late_estimated"):
        p.append(dc.htext(tx + 14, 274, "時辰未詳，晚段命線", 9.5, dc.INK_SOFT))
        p.append(dc.htext(tx + 14, 290, "以日柱代估", 9.5, dc.INK_SOFT))
    else:
        p.append(dc.htext(tx + 14, 274, "時辰已知，晚段命線", 9.5, dc.INK_SOFT))
        p.append(dc.htext(tx + 14, 290, "以時柱計", 9.5, dc.INK_SOFT))
    p.append(dc.htext(tx + 14, 312, "剛柔主軸", 11, dc.INK_SOFT, spacing=1))
    p.append(dc.htext(tx + 14, 336, f"{syn['gangrou']['mean']:+.2f}", 22, dc.INK,
                      font=dc.FONT_SONG, weight="bold"))
    p.append(dc.htext(tx + 14, 360, f"離散 {syn['gangrou']['spread']:.2f}", 10.5,
                      dc.INK_MID))
    p.append(dc.htext(tx + 14, 384, f"互證率 {syn['consensus']['score']:.0f}%", 11,
                      dc.INK_MID))

    # 中：印证条目
    p.append(dc.htext(56, 442, "交叉印證條目", 13, dc.INK, spacing=2, weight="bold"))
    t = syn["tension"]
    p.append(dc.htext(200, 442, f"印證 {t.get('印证',0)}　張力 {t.get('张力',0)}"
                                f"　調和 {t.get('调和',0)}", 11, dc.INK_SOFT, spacing=1))
    n = min(6, len(syn["cross"]))
    for i in range(n):
        it = syn["cross"][i]
        col = 56 if i % 2 == 0 else 438
        row = 462 + (i // 2) * 96
        sym, scc = _mark(it["level"])
        p.append(f'<rect x="{col}" y="{row}" width="326" height="82" fill="{dc.PAPER}"'
                 f' opacity="0.72" stroke="{scc}" stroke-width="1.0" rx="3"/>')
        p.append(f'<circle cx="{col + 22}" cy="{row + 22}" r="10" fill="none"'
                 f' stroke="{scc}" stroke-width="1.3"/>')
        p.append(dc.htext(col + 22, row + 26, sym, 11, scc, "middle"))
        p.append(dc.htext(col + 40, row + 26, it["title"], 12.5, dc.INK, weight="bold",
                          spacing=1))
        p.append(dc.htext(col + 314, row + 26, it["level"], 9.5, scc, "end"))
        for j, ln in enumerate(dc.wrap_cn(it["detail"], 30, 3)[:3]):
            p.append(dc.htext(col + 40, row + 46 + j * 14, ln, 9.5, dc.INK_MID))

    # 下：三栏统计 + 趋势解读
    for i, (lab, key, col) in enumerate((("印證", "印证", dc.CINNABAR),
                                        ("張力", "张力", dc.ASH),
                                        ("調和", "调和", dc.OCHRE))):
        bx = 56 + i * 244
        p.append(f'<rect x="{bx}" y="770" width="228" height="72" fill="{dc.PAPER}"'
                 f' opacity="0.74" stroke="{col}" stroke-width="1.0" rx="3"/>')
        p.append(dc.htext(bx + 16, 796, lab, 11.5, dc.INK_SOFT, spacing=2))
        p.append(dc.htext(bx + 16, 832, str(t.get(key, 0)), 30, col, font=dc.FONT_SONG,
                          weight="bold"))
        p.append(dc.htext(bx + 62, 832, "條", 10.5, dc.INK_SOFT))
    p.append(dc.htext(56, 876, "趨勢解讀", 11.5, dc.INK_SOFT, spacing=2))
    for i, line in enumerate(syn["trend"]["lines"][1:3]):
        for j, ln in enumerate(dc.wrap_cn(line, 66, 2)[:2]):
            p.append(dc.htext(56, 898 + i * 34 + j * 15, ln, 10.2, dc.INK_MID))
    p.append(dc.htext(CW / 2, CH - 40, dc.DISCLAIMER_NOTE, 9.5, dc.INK_SOFT, "middle"))
    p.append("</svg>")
    return dc._write(path, "\n".join(p))


# ---------------------------------------------------------------- 文字报告

def render_synthesis_text(syn):
    """供 analyze.render_person 使用：统合段的纯文本（每行独立，含缩进）。"""
    L = []
    w = syn["weights"]
    mode = "时辰已知" if syn["weight_mode"] == "full" else "时辰未详，八字降权"
    L.append(f"　权重：八字 {w['bazi']}　五格 {w['wuge']}　梅花 {w['meihua']}　"
             f"五音 {w['wuyin']}（{mode}）")
    L.append("　　" + "　".join(f"{SOURCE_NAME[k]} {syn['parts'][k]:.1f}"
                               f"（{syn['grades'][k]}）" for k in
                               ("bazi", "wuge", "meihua", "wuyin")))
    L.append(f"　合成：{syn['score']:.1f} / 100（{syn['grade']}）　"
             f"基准 {syn['score_base']:.1f}　互证调整 {_sgn(syn['delta'])}　"
             f"互证率 {syn['consensus']['score']:.0f}%")

    wu = syn["wuxing"]
    dom = "、".join(wu["consensus_wx"]) or "各有所主"
    lack = ("；三源俱缺 " + "、".join(wu["lacking"])) if wu["lacking"] else ""
    miss = ("（" + "、".join(wu.get("consensus_missing") or []) + " 未见）"
            if wu.get("consensus_missing") else "")
    L.append(f"　五行共振：{wu['score']:.0f}%　三源共主 {dom}{miss}{lack}")
    for k in ("bazi", "meihua", "wuyin"):
        dv = "、".join(wu["dominant"].get(k) or [])
        L.append(f"　　{SOURCE_NAME[k]}：主 {dv or '均衡'}　"
                 + "　".join(f"{x}{wu['vectors'][k][x]*100:.0f}%" for x in WX
                             if wu["vectors"][k][x] > 0.001))
    # 五格数理五行另算，不入共振，仅作参考
    if "wuge" in wu:
        dv_wg = "、".join(wu["wuge"].get("dominant") or [])
        wg_vec = wu["wuge"].get("vectors", {})
        L.append(f"　　{SOURCE_NAME['wuge']}（另算）：主 {dv_wg or '均衡'}　"
                 + "　".join(f"{x}{wg_vec[x]*100:.0f}%" for x in WX
                             if wg_vec.get(x, 0) > 0.001))

    g = syn["gangrou"]
    L.append(f"　刚柔：八字 {g['values']['bazi']:+.2f}　五格 {g['values']['wuge']:+.2f}　"
             f"梅花 {g['values']['meihua']:+.2f}　五音 {g['values']['wuyin']:+.2f}")
    L.append(f"　　→ 主轴 {g['mean']:+.2f}，离散 {g['spread']:.2f}（{g['sign']}）；"
             + ("四点同侧，骨架与气韵一致" if g["sign"] == "同向"
                else "两侧分立，表里不一"))

    ug = syn["use_god"]
    xi = "、".join(f"{i['origin']}{i['wuxing']}" for i in ug["hit_xi"][:4]) or "无"
    ji = "、".join(f"{i['origin']}{i['wuxing']}" for i in ug["hit_ji"][:4]) or "无"
    L.append(f"　用神契合：{ug['score']:.1f} / 100（{ug['verdict']}）　"
             f"用神 {'、'.join(ug['yongshen']) or '—'}")
    L.append(f"　　喜用见：{xi}　│　忌仇见：{ji}")

    st = syn["stages"]
    pts = st["points"]
    shape = ("后成之局" if st["slope"] >= 4 else "早强晚守" if st["slope"] <= -4 else "匀速之局")
    L.append(f"　三段走势：早 {pts[0]['mix']:.0f} → 中 {pts[1]['mix']:.0f} → "
             f"晚 {pts[2]['mix']:.0f}（斜率 {st['slope']:+.1f}，{shape}）")
    L.append("　　命线 " + " / ".join(f"{p['bazi']:.0f}" for p in pts)
             + "　名线 " + " / ".join(f"{p['name']:.0f}" for p in pts)
             + ("　（晚段以日支代时柱，时辰未详）" if st["late_estimated"] else ""))

    if syn["echoes"]:
        L.append("　数象呼应（形式层，不作吉凶）：")
        for e in syn["echoes"]:
            L.append(f"　　· {e['pair']}　{e['why']}")

    L.append("　交叉印证：")
    mark = {"印证": "✓", "张力": "!", "调和": "≈"}
    for it in syn["cross"]:
        L.append(f"　　{mark.get(it['level'], '·')} {it['level']}｜{it['title']}")
        L.append(f"　　　{it['detail']}")

    L.append("　整体趋势：")
    for ln in syn["trend"]["lines"]:
        L.append(f"　　· {ln}")
    return L


if __name__ == "__main__":
    print("synthesis.py：由 analyze.py 调用（r['synthesis']）或直接 render_synthesis(r, path)")
