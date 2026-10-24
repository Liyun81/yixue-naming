#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wuge.py —— 姓名学五格剖象法核心计算库

设计原则
    1. 计算与展示分离：本模块只产出结构化数据（dict / dataclass），不打印。
    2. 规则与数据分离：笔画、81 数理、三才配置全部来自 assets/*.json。
    3. 失败可解释：所有异常带 code + 上下文，便于 CLI / Agent 直接呈现给用户。
    4. 可配置流派：外格单姓单名取 2 或 1、三才权重等以 WugeConfig 切换。

对外主要入口
    analyze(surname, given, config) -> NameReport
    StrokeQuery().get(ch) / .require(ch) / .add(ch, strokes)

免责：本模块实现的是传统民俗姓名学，结论不具科学验证效力。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE_DIR, "assets")

STROKE_FILE = os.path.join(ASSETS, "kangxi_strokes.json")
NUMBER_FILE = os.path.join(ASSETS, "eighty_one_numbers.json")
SANCAI_FILE = os.path.join(ASSETS, "sancai_config.json")

DISCLAIMER = "本结果基于传统姓名学理论生成，仅供民俗文化参考，不构成人生决策依据。"

WUXING_BY_LAST_DIGIT = {1: "木", 2: "木", 3: "火", 4: "火", 5: "土",
                        6: "土", 7: "金", 8: "金", 9: "水", 0: "水"}

LUCK_SCORE = {"大吉": 100, "吉": 85, "半吉": 60, "凶": 32, "大凶": 12}

# 常见复姓名录（用于结构判定，非全部）
COMPOUND_SURNAMES = {
    "欧阳", "司马", "上官", "诸葛", "东方", "独孤", "南宫", "万俟", "闻人", "夏侯",
    "赫连", "皇甫", "尉迟", "公孙", "慕容", "长孙", "宇文", "司徒", "司空", "端木",
    "完颜", "令狐", "呼延", "澹台", "太史", "公西", "漆雕", "乐正", "壤驷", "公良",
    "拓跋", "夹谷", "宰父", "谷梁", "段干", "百里", "东郭", "南门", "微生", "梁丘",
    "左丘", "西门", "颛孙", "公冶", "宗政", "濮阳", "淳于", "单于", "太叔", "申屠",
    "叔孙", "仲孙", "轩辕", "鲜于", "钟离", "闾丘", "子车", "亓官", "司寇", "巫马",
    "公仪", "公乘", "南荣", "东门", "商丘", "仲长", "贺兰", "贺若", "若干", "斛律",
}

# 部件回退用：常见部首及其本字笔画（与 kangxi_strokes.json 的 radical_rules 对齐）
RADICAL_FALLBACK = {
    "氵": 4, "忄": 4, "扌": 4, "犭": 4, "礻": 5, "衤": 6, "讠": 7, "纟": 6,
    "钅": 8, "门": 8, "饣": 9, "马": 10, "鸟": 11, "鱼": 11, "车": 7, "贝": 7,
    "页": 9, "见": 7, "牜": 4, "疒": 5, "广": 3, "廴": 3, "灬": 4, "艹": 6,
    "辶": 7, "王": 5, "月": 4, "亻": 2, "女": 3, "木": 4, "火": 4, "土": 3,
    "口": 3, "山": 3, "石": 5, "日": 4, "目": 5, "田": 5, "禾": 5, "虫": 6,
}


# ============================================================
# 异常体系
# ============================================================
class WugeError(Exception):
    """所有本模块异常的基类。"""
    code = "wuge_error"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "context": self.context}


class InvalidNameError(WugeError):
    code = "invalid_name"


class MissingStrokeError(WugeError):
    code = "missing_stroke"


class AmbiguousSurnameError(WugeError):
    code = "ambiguous_surname"


class WugeComputeError(WugeError):
    code = "compute_error"


# ============================================================
# 配置
# ============================================================
@dataclass
class WugeConfig:
    # 外格流派：virtual_2（单姓单名=2，默认） / formula_1（统一公式=1）
    waige_mode: str = "virtual_2"
    # 缺字策略：strict / ask / fallback
    on_missing: str = "ask"
    gender: str = "unknown"           # male / female / unknown
    # 评分权重（自动归一化）
    weights: Dict[str, float] = field(default_factory=lambda: {
        "tian": 0.04, "ren": 0.30, "di": 0.18, "wai": 0.08, "zong": 0.20, "sancai": 0.20,
    })
    sancai_success_weight: float = 0.5
    immature_note: bool = True        # 未成年人只报数理、不做婚姻暗示

    def normalized(self) -> "WugeConfig":
        total = sum(self.weights.values())
        if total <= 0:
            raise WugeComputeError("权重总和必须大于 0")
        self.weights = {k: v / total for k, v in self.weights.items()}
        if self.waige_mode not in ("virtual_2", "formula_1"):
            raise WugeComputeError(f"未知外格流派：{self.waige_mode}")
        if self.on_missing not in ("strict", "ask", "fallback"):
            raise WugeComputeError(f"未知缺字策略：{self.on_missing}")
        return self


# ============================================================
# 数据加载（惰性单例）
# ============================================================
class _Data:
    chars: Dict[str, int] = {}
    numbers: Dict[int, Dict[str, Any]] = {}
    sancai: Dict[str, Dict[str, Any]] = {}
    loaded = False

    @classmethod
    def load(cls) -> None:
        if cls.loaded:
            return
        for path, label in ((STROKE_FILE, "笔画表"), (NUMBER_FILE, "81数理"), (SANCAI_FILE, "三才表")):
            if not os.path.exists(path):
                raise WugeComputeError(
                    f"数据文件缺失：{label}（{path}）。请先运行 build_strokes.py / gen_sancai.py。"
                )
        with open(STROKE_FILE, encoding="utf-8") as f:
            cls.chars = json.load(f)["chars"]
        with open(NUMBER_FILE, encoding="utf-8") as f:
            cls.numbers = {int(n["no"]): n for n in json.load(f)["numbers"]}
        with open(SANCAI_FILE, encoding="utf-8") as f:
            cls.sancai = json.load(f)["configs"]
        cls.loaded = True


# ============================================================
# 笔画查询接口
# ============================================================
class StrokeQuery:
    """康熙笔画查询。支持增补（学习机制）。"""

    def __init__(self) -> None:
        _Data.load()

    def get(self, ch: str) -> Optional[int]:
        self._validate_char(ch)
        return _Data.chars.get(ch)

    def require(self, ch: str) -> int:
        val = self.get(ch)
        if val is None:
            raise MissingStrokeError(
                f"笔画表中未收录「{ch}」，请提供该字的康熙字典笔画后补充。",
                char=ch,
            )
        return val

    def exists(self, ch: str) -> bool:
        return _Data.chars.get(ch) is not None

    def estimate(self, ch: str) -> Optional[Dict[str, Any]]:
        """部件回退估算：部首本字笔画 + 剩余部件笔画（若剩余部件在表中）。"""
        self._validate_char(ch)
        for rad, stroke in sorted(RADICAL_FALLBACK.items(), key=lambda kv: -len(kv[0])):
            if ch.startswith(rad) and len(ch) > len(rad):
                rest = ch[len(rad):]
                if rest in _Data.chars:
                    return {
                        "char": ch,
                        "strokes": stroke + _Data.chars[rest],
                        "confidence": "low",
                        "method": f"部首「{rad}」{stroke}画 + 「{rest}」{_Data.chars[rest]}画",
                    }
        return None

    def add(self, ch: str, strokes: int) -> None:
        self._validate_char(ch)
        if not isinstance(strokes, int) or not 1 <= strokes <= 64:
            raise InvalidNameError(f"笔画数必须为 1–64 的整数，收到：{strokes}")
        _Data.chars[ch] = strokes
        with open(STROKE_FILE, encoding="utf-8") as f:
            payload = json.load(f)
        payload["chars"] = dict(sorted(_Data.chars.items(), key=lambda kv: (kv[1], kv[0])))
        payload.setdefault("_meta", {})
        payload["_meta"]["char_count"] = len(_Data.chars)
        payload["_meta"].setdefault("_history", []).append({"add": ch, "strokes": strokes})
        with open(STROKE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)

    @staticmethod
    def _validate_char(ch: str) -> None:
        if not isinstance(ch, str) or len(ch) != 1:
            raise InvalidNameError(f"笔画查询只接受单个汉字，收到：{ch!r}")
        if not _is_hanzi(ch):
            raise InvalidNameError(f"「{ch}」不是汉字，五格法不适用。")


def _is_hanzi(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0x20000 <= cp <= 0x2A6DF
        or 0xF900 <= cp <= 0xFAFF
    )


# ============================================================
# 姓名解析
# ============================================================
@dataclass
class NameParts:
    surname: str
    given: str
    structure: str          # SS_GG / SS_GD / DS_SG / DS_GD / EXTENDED
    surname_chars: List[str]
    given_chars: List[str]


def split_name(surname: str, given: str) -> NameParts:
    if not surname or not given:
        raise InvalidNameError("姓与名都不能为空。示例：--surname 李 --given 明华")
    for label, val in (("姓", surname), ("名", given)):
        for ch in val:
            if not _is_hanzi(ch):
                raise InvalidNameError(
                    f"{label}「{val}」含非汉字字符「{ch}」，五格法仅适用于汉字姓名。"
                )
    s_chars, g_chars = list(surname), list(given)
    if len(s_chars) > 2:
        raise AmbiguousSurnameError(
            f"姓「{surname}」超过 2 字，五格法难以判定结构，请确认是否为复姓或少数民族长名。",
            surname=surname,
        )
    if len(g_chars) > 2:
        structure = "EXTENDED"
    elif len(s_chars) == 1:
        structure = "SS_GG" if len(g_chars) == 1 else "SS_GD"
    else:
        structure = "DS_SG" if len(g_chars) == 1 else "DS_GD"
    return NameParts(surname, given, structure, s_chars, g_chars)


def detect_compound(full_name: str) -> NameParts:
    """从全名推断结构：命中复姓表且长度≥3 时按复姓处理。"""
    if len(full_name) < 2:
        raise InvalidNameError(f"姓名「{full_name}」过短。")
    head2 = full_name[:2]
    if head2 in COMPOUND_SURNAMES and len(full_name) >= 3:
        return split_name(head2, full_name[2:])
    return split_name(full_name[0], full_name[1:])


# ============================================================
# 五格计算
# ============================================================
def to_number(value: int) -> int:
    if value <= 0:
        raise WugeComputeError(f"格数必须为正整数，收到：{value}")
    r = value % 81
    return 81 if r == 0 else r


def wuxing_of(value: int) -> str:
    if value <= 0:
        raise WugeComputeError(f"格数必须为正整数，收到：{value}")
    return WUXING_BY_LAST_DIGIT[value % 10]


def compute_grids(parts: NameParts, strokes: Dict[str, int], config: WugeConfig) -> Dict[str, int]:
    s = [strokes[c] for c in parts.surname_chars]
    g = [strokes[c] for c in parts.given_chars]

    if len(s) == 1:
        tian = s[0] + 1
    else:
        tian = s[0] + s[1]

    ren = s[-1] + g[0]

    if len(g) == 1:
        di = g[0] + 1
    else:
        di = sum(g)

    zong = sum(s) + sum(g)

    # 外格 = 边缘字之和 + (2 − 边缘字数)
    # 边缘字：姓中除末字的部分 + 名中除首字的部分（人格/地格已占用主字）
    # 四种结构自然收敛为传统取值：2 / 名2+1 / 姓1+1 / 姓1+名2
    edge_chars = s[:-1] + g[1:]
    wai = sum(edge_chars) + (2 - len(edge_chars))
    if parts.structure == "SS_GG" and config.waige_mode == "formula_1":
        wai = zong - ren + 1   # 数理自洽派：单姓单名取 1

    grids = {"tian": tian, "ren": ren, "di": di, "wai": wai, "zong": zong}
    for k, v in grids.items():
        if v <= 0:
            raise WugeComputeError(f"{k} 格计算结果非法：{v}")
    return grids


# ============================================================
# 三才
# ============================================================
def analyze_sancai(tian: int, ren: int, di: int) -> Dict[str, Any]:
    _Data.load()
    combo = f"{wuxing_of(tian)}{wuxing_of(ren)}{wuxing_of(di)}"
    cfg = _Data.sancai.get(combo)
    if cfg is None:
        raise WugeComputeError(f"三才配置表缺失：{combo}")
    return dict(cfg)

analyze_sancai = lru_cache(maxsize=128)(analyze_sancai)


# ============================================================
# 评分
# ============================================================
def score_name(grids: Dict[str, int], numbers: Dict[str, Dict[str, Any]],
               sancai: Dict[str, Any], config: WugeConfig) -> Tuple[float, str, List[str]]:
    """numbers 以格位为键：{"tian": {...81数理对象...}, ...}"""
    w = config.weights
    base = 0.0
    for key in ("tian", "ren", "di", "wai", "zong"):
        base += LUCK_SCORE[numbers[key]["luck"]] * w[key]
    base += sancai["score"] * w["sancai"]

    bonus = 0.0
    penalty = 0.0
    notes: List[str] = []

    ren_n, zong_n, di_n = numbers["ren"], numbers["zong"], numbers["di"]

    if "首领数" in ren_n.get("tags", []):
        bonus += 3
        notes.append("人格为首领数，主统率与担当")
    if "财富数" in zong_n.get("tags", []):
        bonus += 3
        notes.append("总格为财富数，主聚财力")
    if "艺能数" in ren_n.get("tags", []) or "艺能数" in di_n.get("tags", []):
        bonus += 2
        notes.append("人格或地格为艺能数，主才艺")
    good_count = sum(1 for k in ("tian", "ren", "di", "wai", "zong")
                     if numbers[k]["luck"] in ("大吉", "吉"))
    if good_count >= 4:
        bonus += 4
        notes.append("五格中吉数达四个以上，整体偏吉")
    if sancai["luck"] == "大吉" and ren_n["luck"] in ("大吉", "吉"):
        bonus += 4
        notes.append("三才大吉且人格得吉，格局顺畅")
    bonus = min(bonus, 10)

    if ren_n["luck"] == "大凶":
        penalty += 14
        notes.append("人格大凶，主运多阻")
    elif ren_n["luck"] == "凶":
        penalty += 10
        notes.append("人格为凶，主运欠顺")
    if zong_n["luck"] == "大凶":
        penalty += 9
    elif zong_n["luck"] == "凶":
        penalty += 6
    if di_n["luck"] == "大凶":
        penalty += 8
    elif di_n["luck"] == "凶":
        penalty += 5
    if sancai["luck"] == "大凶":
        penalty += 12
    elif sancai["luck"] == "凶":
        penalty += 8
    penalty = min(penalty, 15)

    if config.gender == "female" and "女用宜慎" in (ren_n.get("tags", []) + zong_n.get("tags", [])):
        penalty += 3
        notes.append("传统认为此数过刚，女性用之宜柔济（仅供参考）")

    score = max(0.0, min(100.0, base + bonus - penalty))
    return round(score, 1), grade_of(score), notes


def grade_of(score: float) -> str:
    if score >= 90:
        return "极佳"
    if score >= 80:
        return "优秀"
    if score >= 70:
        return "良好"
    if score >= 60:
        return "一般"
    if score >= 50:
        return "平平"
    return "欠佳"


# ============================================================
# 多维度解读
# ============================================================
WUXING_CHARACTER = {
    "木": "木主仁，性情温和而有主见，重道义、好进取，如草木向阳而生。",
    "火": "火主礼，热情明朗，行动力强，重仪节而富感染力。",
    "土": "土主信，稳重笃实，能容能载，重承诺而耐劳。",
    "金": "金主义，果决明断，原则性强，重信守而富执行力。",
    "水": "水主智，聪慧灵通，善谋多变，重机智而长于应变。",
}
WUXING_SHORT = {"木": "固执", "火": "急躁", "土": "迟缓", "金": "刚硬", "水": "多虑"}

WUXING_INDUSTRY = {
    "木": "文教、出版、医药、林木纺织等成长型行业",
    "火": "能源、电子、传媒、餐饮、演艺等光热型行业",
    "土": "地产、建筑、农业、仓储、保险等承载型行业",
    "金": "金融、机械、法律、军警、精密制造等规整型行业",
    "水": "贸易、物流、旅游、咨询、水产等流动型行业",
}


def _grid_brief(num: Dict[str, Any]) -> str:
    return f"{num['no']}（{num['title']}·{num['luck']}）"


def build_dimensions(grids: Dict[str, int], numbers: Dict[str, Dict[str, Any]],
                     sancai: Dict[str, Any], config: WugeConfig) -> Dict[str, str]:
    ren_n = numbers["ren"]
    di_n = numbers["di"]
    zong_n = numbers["zong"]
    wai_n = numbers["wai"]
    ren_wx = wuxing_of(grids["ren"])

    # 性格
    char = WUXING_CHARACTER[ren_wx]
    char += f"人格 {_grid_brief(ren_n)}，{ren_n['summary']}"
    if ren_n["luck"] in ("凶", "大凶"):
        char += f" 传统认为此数主性情偏{WUXING_SHORT[ren_wx]}，宜以修养化之。"
    else:
        char += " 主运得吉，性格发挥较为顺遂。"

    # 事业
    career = f"成功运看天格与人格：{sancai['success']['text']}"
    career += f"人格五行属{ren_wx}，气质近于{WUXING_INDUSTRY[ren_wx]}。"
    if zong_n["luck"] in ("大吉", "吉"):
        career += f"总格 {_grid_brief(zong_n)}，中晚年事业格局较宽。"
    else:
        career += f"总格 {_grid_brief(zong_n)}，事业宜稳守渐进，忌急于扩张。"

    # 财运
    if "财富数" in zong_n.get("tags", []) or "财富数" in ren_n.get("tags", []):
        wealth = f"总格 {_grid_brief(zong_n)} 属传统「财富数」，主聚财有方、积少成多，宜以稳健理财为主。"
    elif zong_n["luck"] in ("大吉", "吉"):
        wealth = f"总格 {_grid_brief(zong_n)} 得吉，财源平稳，宜以专业与信用累积。"
    else:
        wealth = f"总格 {_grid_brief(zong_n)} 非财数，财运起伏较明显，宜量入为出、避免高杠杆。"

    # 健康
    bad = [k for k in ("ren", "di", "zong") if numbers[k]["luck"] in ("凶", "大凶")]
    if bad or sancai["luck"] in ("凶", "大凶"):
        health = ("五格中见凶数或三才偏克，传统上视为体质易受环境牵动。"
                  "建议规律作息、劳逸有节、注意情绪疏导。此为文化提示，非医学判断。")
    else:
        health = "五格无明显凶数，三才和顺，传统视为体质根基较稳。仍宜规律作息、适度运动。"

    # 婚姻
    parity = "阳" if grids["ren"] % 2 == 1 else "阴"
    marriage = (f"人格 {grids['ren']} 为{parity}数，"
                + ("性格偏主动外向，相处中宜多体谅。" if parity == "阳"
                   else "性格偏内敛包容，相处中宜多表达。"))
    if "女用宜慎" in ren_n.get("tags", []) and config.gender == "female":
        marriage += "传统姓名学认为此数过刚，女性用之宜以柔济刚；此为旧说，仅供参考，不作婚姻断言。"
    marriage += f"外格 {_grid_brief(wai_n)} 主外在人缘，{wai_n['summary']}"

    # 家庭
    family = f"地格 {_grid_brief(di_n)} 主前运与家庭根基，{di_n['family']}。"
    family += f"外格 {_grid_brief(wai_n)} 主与外界及姻亲之缘，宜以诚相待。"
    if config.immature_note and config.gender == "unknown":
        family += "（若为未成年子女，仅作数理参考，不作人生走向推断。）"

    return {"character": char, "career": career, "wealth": wealth,
            "health": health, "marriage": marriage, "family": family}


# ============================================================
# 主流程
# ============================================================
def analyze(surname: str, given: str, config: Optional[WugeConfig] = None,
            full_name: Optional[str] = None) -> Dict[str, Any]:
    config = (config or WugeConfig()).normalized()
    _Data.load()

    parts = detect_compound(full_name) if full_name else split_name(surname, given)

    strokes: Dict[str, int] = {}
    missing: List[str] = []
    low_conf: List[str] = []
    for ch in parts.surname_chars + parts.given_chars:
        val = StrokeQuery().get(ch)
        if val is None:
            if config.on_missing == "strict":
                missing.append(ch)
                continue
            if config.on_missing == "fallback":
                est = StrokeQuery().estimate(ch)
                if est:
                    strokes[ch] = est["strokes"]
                    low_conf.append(f"{ch}={est['strokes']}（{est['method']}，低置信）")
                else:
                    missing.append(ch)
                continue
            missing.append(ch)
            continue
        strokes[ch] = val

    if missing:
        raise MissingStrokeError(
            "以下汉字未收录康熙笔画：" + "、".join(missing) + "。"
            "请告知其康熙字典笔画（可用 stroke_query.py add 字 笔画 补充），或改用他字。",
            missing=missing,
        )

    grids = compute_grids(parts, strokes, config)

    numbers = {k: _Data.numbers[to_number(v)] for k, v in grids.items()}
    sancai = analyze_sancai(grids["tian"], grids["ren"], grids["di"])
    score, grade, notes = score_name(grids, numbers, sancai, config)
    dims = build_dimensions(grids, numbers, sancai, config)

    grid_detail = {}
    for k in ("tian", "ren", "di", "wai", "zong"):
        n = numbers[k]
        grid_detail[k] = {
            "value": grids[k],
            "number": n["no"],
            "luck": n["luck"],
            "title": n["title"],
            "summary": n["summary"],
            "wuxing": wuxing_of(grids[k]),
            "poem": n.get("poem", ""),
            "tags": n.get("tags", []),
        }

    warnings: List[str] = []
    if parts.structure == "EXTENDED":
        warnings.append("名为 3 字以上，已按扩展规则近似计算（地格取全名之和，外格=总格−人格+1），结果仅供参考。")
    if config.waige_mode == "formula_1":
        warnings.append("外格采用「数理自洽派」：单姓单名外格 = 总格−人格+1 = 1。")
    if low_conf:
        warnings.append("以下字采用部件估算笔画，建议人工校准：" + "；".join(low_conf))
    if grids["tian"] and numbers["tian"]["luck"] in ("凶", "大凶"):
        warnings.append("天格为凶数。传统认为天格为祖上既定之数、本人不可改，故不作扣分，仅记录。")

    return {
        "input": {"surname": parts.surname, "given": parts.given,
                  "gender": config.gender, "structure": parts.structure},
        "strokes": strokes,
        "grids": grid_detail,
        "sancai": {
            "combo": sancai["combo"],
            "success": sancai["success"],
            "base": sancai["base"],
            "score": sancai["score"],
            "luck": sancai["luck"],
            "note": sancai.get("note", ""),
            "advice": sancai.get("advice", ""),
        },
        "score": score,
        "grade": grade,
        "highlights": notes,
        "dimensions": dims,
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }


def to_json(report: Dict[str, Any], indent: int = 2) -> str:
    return json.dumps(report, ensure_ascii=False, indent=indent)


if __name__ == "__main__":
    demo = analyze("李", "明华")
    print(to_json(demo))
