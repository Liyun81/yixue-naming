# -*- coding: utf-8 -*-
"""梅花易数姓名起卦与五行旺衰分析。

起卦法（姓名终身卦）：
    起卦笔画一律取**现代简体字（规范字形）的实际笔画**，不用康熙繁体
    笔画，也不用任何字体变体；用户输入繁体字时先映射为对应简体字再计
    笔画（映射表来自 Unihan kSimplifiedVariant，见 assets/simplified_strokes.json）。

    上卦数 = 姓之简体笔画和      → 先天八卦数取卦（除 8 取余，余 0 为坤）
    下卦数 = 名之简体笔画和      → 同上
    动  爻 = (姓 + 名) 简体笔画和 除 6 取余（余 0 为第六爻）
    本卦 = 上卦 / 下卦；互卦取二三四爻为下互、三四五爻为上互；动爻变则得变卦。

体用与旺衰：
    动爻所在之卦为「用」，另一卦为「体」；体为己身、为根本，用为外境、为所遇。
    旺衰以月令为纲：当令者旺、令生者相、生令者休、克令者囚、令克者死。
    本卦看根基（早年）、互卦看过程（中年）、变卦看结果（晚景）。
"""
import datetime
import json
import os
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
# 旺相休囚死对应分值（体卦得令与否，直接决定"气"的厚薄）
STATE_SCORE = {"旺": 100, "相": 82, "休": 55, "囚": 36, "死": 22}
STATE_DESC = {
    "旺": "当令得权，本源充足，气势最盛",
    "相": "受令所生，气势方兴，进力有余",
    "休": "退气休歇，力有未逮，宜守不宜攻",
    "囚": "受令所制，施展不易，处处掣肘",
    "死": "失令无气，底气偏薄，须借外助",
}
# 地支月建与节气近似分界（公历）
MONTH_BRANCH = [
    ("01-06", "丑", "小寒后"), ("02-04", "寅", "立春后"), ("03-06", "卯", "惊蛰后"),
    ("04-05", "辰", "清明后"), ("05-06", "巳", "立夏后"), ("06-06", "午", "芒种后"),
    ("07-07", "未", "小暑后"), ("08-08", "申", "立秋后"), ("09-08", "酉", "白露后"),
    ("10-09", "戌", "寒露后"), ("11-08", "亥", "立冬后"), ("12-07", "子", "大雪后"),
]
BRANCH_WUXING = {"寅": "木", "卯": "木", "巳": "火", "午": "火", "申": "金", "酉": "金",
                 "亥": "水", "子": "水", "辰": "土", "未": "土", "戌": "土", "丑": "土"}
# 体用关系 → (吉凶判语, 分值 0-30)
TIYONG_SCORE = {
    "用生体": (30, "用卦生体，外力来助，做事有人扶，得助之象最吉"),
    "体用比和": (26, "体用比和，内外相得，气息一贯，顺遂可期"),
    "体克用": (22, "体克用卦，事在掌握，然须亲力经营，成而费力"),
    "体生用": (14, "体生用卦，我之气血外泄，付出多于回报，易见耗损"),
    "用克体": (8, "用克体卦，外势制我，行事宜避锋守拙，强争则伤"),
}
GUA_TENDENCY_SCORE = {"大吉": 10, "吉": 8, "中": 6, "平": 5, "需慎": 3}


class MeihuaError(Exception):
    """梅花易数分析异常。"""


def load_gua() -> Dict:
    path = os.path.join(ASSETS, "gua64.json")
    if not os.path.exists(path):
        raise MeihuaError("卦象数据缺失，请先运行 build_gua64.py 生成 assets/gua64.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_SIMP_PATH = os.path.join(ASSETS, "simplified_strokes.json")
_SIMP_CACHE: Optional[Dict] = None


def load_simplified() -> Dict:
    """加载简体笔画表（懒加载 + 缓存）。"""
    global _SIMP_CACHE
    if _SIMP_CACHE is None:
        if not os.path.exists(_SIMP_PATH):
            raise MeihuaError("简体笔画数据缺失，请先运行 build_simplified.py "
                              "生成 assets/simplified_strokes.json")
        with open(_SIMP_PATH, encoding="utf-8") as f:
            _SIMP_CACHE = json.load(f)
    return _SIMP_CACHE


def simplified_char(ch: str) -> Tuple[str, str]:
    """返回 (用于计数的简体字, 转换说明)。繁体/异体先映射为简体。"""
    data = load_simplified()
    t2s = data.get("t2s", {})
    if ch in t2s:
        return t2s[ch], "繁转简"
    return ch, ""


def stroke_of_simplified(ch: str) -> int:
    """单字简体笔画；未收录返回 0。"""
    return load_simplified().get("strokes", {}).get(simplified_char(ch)[0], 0)


def name_strokes(name: str) -> Dict[str, Dict]:
    """逐字解析简体笔画：{'刘': {'strokes': 6, 'via': ''}, ...}。

    via='繁转简' 表示原字为繁体，已映射为简体后计笔画。
    未收录的字回退为 0，由调用方决定报错或提示。
    """
    out: Dict[str, Dict] = {}
    for ch in name:
        simp, via = simplified_char(ch)
        n = load_simplified().get("strokes", {}).get(simp, 0)
        out[ch] = {"strokes": n, "via": via}
    return out


def strokes_of_name(name: str) -> List[int]:
    """整名简体笔画列表（未收录字抛错，避免静默错卦）。"""
    detail = name_strokes(name)
    missing = [ch for ch, v in detail.items() if v["strokes"] <= 0]
    if missing:
        raise MeihuaError(f"简体笔画库未收录：{'、'.join(missing)}；"
                          f"请先在 build_simplified.py 语料中增补该字")
    return [detail[ch]["strokes"] for ch in name]


def state_of(target: str, month_wx: str) -> str:
    """目标五行在月令下的旺相休囚死。"""
    if target == month_wx:
        return "旺"
    if SHENG[month_wx] == target:
        return "相"
    if SHENG[target] == month_wx:
        return "休"
    if KE[target] == month_wx:
        return "囚"
    if KE[month_wx] == target:
        return "死"
    return "休"


def ti_yong_relation(ti_wx: str, yong_wx: str) -> str:
    if ti_wx == yong_wx:
        return "体用比和"
    if SHENG[yong_wx] == ti_wx:
        return "用生体"
    if SHENG[ti_wx] == yong_wx:
        return "体生用"
    if KE[ti_wx] == yong_wx:
        return "体克用"
    return "用克体"


def month_context(when: Optional[datetime.date] = None, branch: Optional[str] = None) -> Dict:
    """取月令。branch 可手动指定地支（如“午”），否则按公历日期近似节气判定。"""
    if branch:
        if branch not in BRANCH_WUXING:
            raise MeihuaError(f"地支「{branch}」非法，应为十二支之一")
        wx = BRANCH_WUXING[branch]
        return {"branch": branch, "wuxing": wx, "jieqi": "手动指定",
                "note": f"以{branch}月论，{wx}当令"}
    today = when or datetime.date.today()
    cur = ("12-07", "子", "大雪后")
    for md, br, jq in MONTH_BRANCH:
        mm, dd = md.split("-")
        if (today.month, today.day) >= (int(mm), int(dd)):
            cur = (md, br, jq)
    br, jq = cur[1], cur[2]
    wx = BRANCH_WUXING[br]
    return {"branch": br, "wuxing": wx, "jieqi": jq,
            "note": f"约当{br}月（{jq}），{wx}当令", "date": today.isoformat()}


class MeihuaAnalyzer:
    def __init__(self):
        self.data = load_gua()
        self.bagua = self.data["bagua"]
        self.gua = self.data["gua"]
        self.index = {(g["upper"], g["lower"]): g for g in self.gua.values()}
        self.yao_index = {tuple(v["yao"]): k for k, v in self.bagua.items()}

    # ---------- 基础构件 ----------
    def num_to_gua(self, num: int) -> str:
        rem = num % 8
        return {1: "乾", 2: "兑", 3: "离", 4: "震", 5: "巽", 6: "坎", 7: "艮", 0: "坤"}[rem]

    def gua_of(self, upper: str, lower: str) -> Dict:
        g = self.index.get((upper, lower))
        if not g:
            raise MeihuaError(f"卦象组合不存在：上{upper}下{lower}")
        return g

    @staticmethod
    def yao_lines(upper: str, lower: str, bagua: Dict) -> List[int]:
        return list(bagua[lower]["yao"]) + list(bagua[upper]["yao"])  # 初→上

    @staticmethod
    def render_lines(yao: List[int], moving: Optional[int] = None) -> List[str]:
        """六爻图形（文本自上而下显示，初爻在下）。"""
        names = ["初", "二", "三", "四", "五", "上"]
        out = []
        for i in range(5, -1, -1):
            mark = " ▅▅▅▅▅ " if yao[i] == 1 else " ▅▅ ▅▅ "
            tag = "  ← 动爻" if moving == i + 1 else ""
            label = f"{names[i]}爻" if i in (0, 5) else f"第{names[i]}爻"
            out.append(f"{label}{mark}{tag}")
        return out

    # ---------- 起卦 ----------
    def cast(self, upper_num: int, lower_num: int, moving_num: int) -> Dict:
        upper = self.num_to_gua(upper_num)
        lower = self.num_to_gua(lower_num)
        moving = moving_num % 6 or 6
        ben = self.gua_of(upper, lower)
        yao = self.yao_lines(upper, lower, self.bagua)

        # 互卦：二三四爻为下互、三四五爻为上互
        hu_lower = self.yao_index[tuple(yao[1:4])]
        hu_upper = self.yao_index[tuple(yao[2:5])]
        hu = self.gua_of(hu_upper, hu_lower)
        hu_yao = list(yao[1:4]) + list(yao[2:5])

        # 变卦
        bian_yao = list(yao)
        bian_yao[moving - 1] ^= 1
        b_lower = self.yao_index[tuple(bian_yao[0:3])]
        b_upper = self.yao_index[tuple(bian_yao[3:6])]
        bian = self.gua_of(b_upper, b_lower)

        # 体用：动爻在下卦则下为用、上为体
        if moving <= 3:
            ti_gua, ti_pos = upper, "上卦"
            yong_gua, yong_pos = lower, "下卦"
        else:
            ti_gua, ti_pos = lower, "下卦"
            yong_gua, yong_pos = upper, "上卦"

        return {
            "numbers": {"upper": upper_num, "lower": lower_num, "moving": moving_num,
                        "upper_mod8": upper_num % 8 or 8, "lower_mod8": lower_num % 8 or 8,
                        "moving_mod6": moving},
            "ben": {"gua": ben, "yao": yao, "lines": self.render_lines(yao, moving),
                    "moving_line": moving},
            "hu": {"gua": hu, "yao": hu_yao, "lines": self.render_lines(hu_yao)},
            "bian": {"gua": bian, "lines": self.render_lines(bian_yao)},
            "ti": {"gua": ti_gua, "wuxing": self.bagua[ti_gua]["wuxing"], "pos": ti_pos},
            "yong": {"gua": yong_gua, "wuxing": self.bagua[yong_gua]["wuxing"], "pos": yong_pos},
        }

    def cast_name(self, surname_strokes: List[int], given_strokes: List[int]) -> Dict:
        s_sum, g_sum = sum(surname_strokes), sum(given_strokes)
        if s_sum <= 0 or g_sum <= 0:
            raise MeihuaError("笔画数须为正整数")
        return self.cast(s_sum, g_sum, s_sum + g_sum)

    def cast_org(self, strokes: List[int]) -> Dict:
        """公司/团队名起卦：前半为上卦、后半为下卦，总数取动爻。"""
        n = len(strokes)
        if n < 2:
            raise MeihuaError("机构名至少两字，单字无法分判上下卦")
        cut = n // 2 if n % 2 == 0 else n // 2
        upper_sum, lower_sum = sum(strokes[:cut]), sum(strokes[cut:])
        return self.cast(upper_sum, lower_sum, sum(strokes))

    # ---------- 旺衰与解读 ----------
    def _positions(self, cast: Dict) -> List[Tuple[str, str, bool, str]]:
        """六卦位的五行、是否体卦自身、组别（yong=用卦满权, hu=互卦半权, result=仅看结局）。"""
        bagua = self.bagua
        b = cast["ben"]["gua"]
        h = cast["hu"]["gua"]
        n = cast["bian"]["gua"]
        return [
            ("本卦·上卦", bagua[b["upper"]]["wuxing"], cast["ti"]["pos"] == "上卦", "yong"),
            ("本卦·下卦", bagua[b["lower"]]["wuxing"], cast["ti"]["pos"] == "下卦", "yong"),
            ("上互", bagua[h["upper"]]["wuxing"], False, "hu"),
            ("下互", bagua[h["lower"]]["wuxing"], False, "hu"),
            ("变卦·上卦", bagua[n["upper"]]["wuxing"], False, "result"),
            ("变卦·下卦", bagua[n["lower"]]["wuxing"], False, "result"),
        ]

    GROUP_FACTOR = {"yong": 1.0, "hu": 0.5, "result": 0.0}

    @staticmethod
    def _support_weight(rel: str) -> float:
        """卦位对体卦的受力权重：生体最助，克体最伤。"""
        return {"生体": 1.5, "比和": 1.0, "体克": 0.3, "泄体": -0.8, "克体": -1.5}[rel]

    def _relation_view(self, ti_wx: str, other_wx: str) -> str:
        """从体卦视角描述他与我的关系。"""
        if ti_wx == other_wx:
            return "比和"
        if SHENG[other_wx] == ti_wx:
            return "生体"
        if SHENG[ti_wx] == other_wx:
            return "泄体"
        if KE[other_wx] == ti_wx:
            return "克体"
        return "体克"

    def analyze(self, cast: Dict, month: Optional[Dict] = None,
                subject: str = "姓名") -> Dict:
        month = month or month_context()
        ti_wx = cast["ti"]["wuxing"]
        yong_wx = cast["yong"]["wuxing"]
        bagua = self.bagua
        bian_upper_wx = bagua[cast["bian"]["gua"]["upper"]]["wuxing"]
        bian_lower_wx = bagua[cast["bian"]["gua"]["lower"]]["wuxing"]
        hu_upper_wx = bagua[cast["hu"]["gua"]["upper"]]["wuxing"]
        hu_lower_wx = bagua[cast["hu"]["gua"]["lower"]]["wuxing"]

        # —— 卦局五行配比（终身格局的主依据：用卦满权、互卦半权、变卦不计）——
        positions = self._positions(cast)
        support = []
        acc = 0.0
        for name, wx, is_self, group in positions:
            if is_self:
                support.append({"position": name, "wuxing": wx, "relation": "本体",
                                "weight": 0.0, "group": group})
                continue
            rel = self._relation_view(ti_wx, wx)
            w = round(self._support_weight(rel) * self.GROUP_FACTOR[group], 3)
            acc += w
            support.append({"position": name, "wuxing": wx, "relation": rel,
                            "weight": w, "group": group})
        # acc 理论区间约 ±3（用卦 ±1.5、互卦各 ±0.75），基准 55 略偏于宽，符合取名本有用心的常情
        qi_index = round(max(0.0, min(100.0, 55 + acc * 15)), 1)

        counts: Dict[str, int] = {}
        for _, wx, _, _ in positions:
            counts[wx] = counts.get(wx, 0) + 1
        dominant = max(counts.items(), key=lambda kv: kv[1])
        lacking = [w for w in ("木", "火", "土", "金", "水") if w not in counts]
        helpers = [s["position"] for s in support
                   if s["relation"] in ("生体", "比和") and s["group"] in ("yong", "hu")]
        drainers = [s["position"] for s in support
                    if s["relation"] in ("克体", "泄体") and s["group"] in ("yong", "hu")]

        # —— 月令（当下气候，单列不计入主分）——
        ti_state = state_of(ti_wx, month["wuxing"])
        yong_state = state_of(yong_wx, month["wuxing"])

        rel = ti_yong_relation(ti_wx, yong_wx)
        rel_score, rel_text = TIYONG_SCORE[rel]

        bian_ti_wx = bian_upper_wx if cast["ti"]["pos"] == "上卦" else bian_lower_wx
        bian_rel = ti_yong_relation(ti_wx, bian_ti_wx)
        bian_text = TIYONG_SCORE[bian_rel][1]

        ben_tendency = cast["ben"]["gua"]["tendency"]
        gua_score = GUA_TENDENCY_SCORE.get(ben_tendency, 5)

        # 主分：卦局卦气 (25) + 体用 (25) + 变卦结局 (20) + 卦象倾向 (30)
        score = round(min(100.0, max(0.0,
                                    qi_index * 0.25
                                    + rel_score / 30 * 25
                                    + TIYONG_SCORE[bian_rel][0] / 30 * 20
                                    + gua_score * 3)), 1)

        if score >= 80:
            grade = "上吉"
        elif score >= 65:
            grade = "吉"
        elif score >= 50:
            grade = "平"
        elif score >= 36:
            grade = "偏弱"
        else:
            grade = "需留意"

        # —— 叙述 ——
        narr = []
        narr.append(
            f"本卦「{cast['ben']['gua']['name']}」（{cast['ben']['gua']['symbol']}），"
            f"上{cast['ben']['gua']['upper']}{bagua[cast['ben']['gua']['upper']]['symbol']}、"
            f"下{cast['ben']['gua']['lower']}{bagua[cast['ben']['gua']['lower']]['symbol']}，"
            f"第{cast['ben']['moving_line']}爻动。"
        )
        narr.append(
            f"体卦{cast['ti']['gua']}属{ti_wx}（{cast['ti']['pos']}），主己身与根基；"
            f"用卦{cast['yong']['gua']}属{yong_wx}（{cast['yong']['pos']}），主外境与所遇。"
        )
        if helpers:
            narr.append(f"卦局中{'、'.join(helpers)}之气生助比和体卦，是先天可借之力；")
        if drainers:
            narr.append(f"{'、'.join(drainers)}之气克泄体卦，是耗神受制之处，宜以后天人事补之。")
        else:
            narr.append("六位之中不见克泄体卦之气，卦局对我方较为宽和。")
        narr.append(
            f"体卦气势指数 {qi_index}：{self._qi_comment(qi_index)}"
        )
        narr.append(f"{rel}——{rel_text}")
        if dominant[1] >= 3:
            narr.append(f"卦中{dominant[0]}气出现 {dominant[1]} 次，一家独盛，须防偏旺之弊："
                        f"{dominant[0]}过旺则其所克者易受牵动，宜留一分余地。")
        if lacking:
            narr.append(f"卦中不见{'、'.join(lacking)}气，{lacking[0]}的意象在卦局中偏虚，"
                        f"传统视为该方向先天助力较少，可于后天补。")
        narr.append(
            f"以时令论：值{month['branch']}月，{month['wuxing']}当令，"
            f"体卦{ti_wx}处「{ti_state}」地——{STATE_DESC[ti_state]}；"
            f"此为当下气候，非终身定论，随岁月流转而变。"
        )

        stages = {
            "根基·本卦（早年）": f"{cast['ben']['gua']['name']}：{cast['ben']['gua']['brief']}"
                                 f"（{cast['ben']['gua']['tendency']}）",
            "过程·互卦（中年）": f"{cast['hu']['gua']['name']}：{cast['hu']['gua']['brief']}"
                                 f"上互{hu_upper_wx}、下互{hu_lower_wx}，为中途气候。",
            "结果·变卦（晚景）": f"{cast['bian']['gua']['name']}：{cast['bian']['gua']['brief']}"
                                 f"动而归{bian_ti_wx}，与体{ti_wx}成{ti_yong_relation(ti_wx, bian_ti_wx)}，{bian_text}",
        }

        return {
            "subject": subject,
            "stroke_standard": "现代简体字笔画（非康熙繁体笔画）",
            "cast": cast,
            "month": month,
            "wangshuai": {
                "qi_index": qi_index,
                "positions": support,
                "helpers": helpers,
                "drainers": drainers,
                "distribution": counts,
                "dominant": dominant[0],
                "dominant_count": dominant[1],
                "lacking": lacking,
                "ti_in_month": {"wuxing": ti_wx, "state": ti_state, "score": STATE_SCORE[ti_state]},
                "yong_in_month": {"wuxing": yong_wx, "state": yong_state},
            },
            "tiyong": {"relation": rel, "score": rel_score, "text": rel_text,
                       "bian_relation": bian_rel, "bian_text": bian_text},
            "score": score,
            "grade": grade,
            "narrative": narr,
            "stages": stages,
            "advice": self._advice(cast, qi_index, ti_state, rel, bian_rel),
            "note": "旺衰以卦局五行配比为主、月令为辅，属梅花易数体用法的通行判法；"
                    "月建按公历节气近似，精确请以实际节气交接时刻为准。",
        }

    @staticmethod
    def _qi_comment(qi: float) -> str:
        if qi >= 80:
            return "体气充沛，卦局多来生助，先天底子厚，遇事有人可托。"
        if qi >= 65:
            return "体气中上，生助稍多于克泄，整体能自持。"
        if qi >= 45:
            return "体气平平，生克相当，成败多在人谋。"
        if qi >= 30:
            return "体气偏弱，克泄多于生助，行事易感吃力，宜借势。"
        return "体气虚弱，卦局多克泄，传统视为先天担子较重，宜守成蓄力。"

    def _advice(self, cast: Dict, qi_index: float, ti_state: str,
                rel: str, bian_rel: str) -> List[str]:
        tips = []
        ti_wx = cast["ti"]["wuxing"]
        if qi_index >= 65:
            tips.append(f"体卦{ti_wx}在卦局中得助，自身根基不弱，宜主动进取、把握时机。")
        else:
            tips.append(f"体卦{ti_wx}在卦局中受克泄较多，行事宜稳中蓄力，先固本再图进。")
        if rel == "用克体":
            tips.append("外境克身，宜避正面硬争，借势借力、延后决定往往更省力。")
        elif rel == "体生用":
            tips.append("付出型格局，宜设付出边界，避免长期单向消耗。")
        elif rel == "用生体":
            tips.append("得助之局，善用合作与他方资源，是此名的先天长处。")
        elif rel == "体克用":
            tips.append("掌控型格局，事多由己，然亦须防事必躬亲而劳。")
        if bian_rel in ("用克体", "体生用"):
            tips.append("变卦所示结局略见耗泄，宜在关键节点主动收敛，不使前功外流。")
        elif bian_rel == "用生体":
            tips.append("变卦归于生体，晚境有回护，早年积累会在后段显出价值。")
        if ti_state in ("囚", "死"):
            tips.append(f"当下{ti_state}气，非发力之时，宜蓄势；待体卦得令之月再图施展。")
        tips.append(f"卦象大象：{cast['ben']['gua']['xiang']}此为本名可取之精神方向。")
        return tips


@lru_cache(maxsize=256)
def _analyze_name_cached(surname_tuple: tuple, given_tuple: tuple, month_tuple: Optional[tuple]) -> Dict:
    mh = MeihuaAnalyzer()
    cast = mh.cast_name(list(surname_tuple), list(given_tuple))
    month = dict(month_tuple) if month_tuple else None
    return mh.analyze(cast, month, subject="姓名终身卦")


def analyze_name(surname_strokes: List[int], given_strokes: List[int],
                 month: Optional[Dict] = None) -> Dict:
    """传入的笔画必须是**简体笔画**：请用 strokes_of_name()/name_strokes()
    从姓名字符串取得，不要直接传康熙笔画。"""
    return _analyze_name_cached(tuple(surname_strokes), tuple(given_strokes),
                                tuple(sorted(month.items())) if month else None)


@lru_cache(maxsize=256)
def _analyze_org_cached(strokes_tuple: tuple, month_tuple: Optional[tuple]) -> Dict:
    mh = MeihuaAnalyzer()
    cast = mh.cast_org(list(strokes_tuple))
    month = dict(month_tuple) if month_tuple else None
    return mh.analyze(cast, month, subject="机构名卦")


def analyze_org(strokes: List[int], month: Optional[Dict] = None) -> Dict:
    mh = MeihuaAnalyzer()
    cast = mh.cast_org(strokes)
    return mh.analyze(cast, month, subject="机构名卦")


if __name__ == "__main__":
    r = analyze_name(strokes_of_name("李"), strokes_of_name("明华"))  # 简体笔画：7 / 8,6
    print("本卦", r["cast"]["ben"]["gua"]["name"], "动爻", r["cast"]["ben"]["moving_line"])
    print("互卦", r["cast"]["hu"]["gua"]["name"], "变卦", r["cast"]["bian"]["gua"]["name"])
    print("体", r["cast"]["ti"], "用", r["cast"]["yong"])
    print("月令", r["month"]["branch"], r["month"]["wuxing"], "| 体气", r["wangshuai"]["qi_index"])
    print("体用", r["tiyong"]["relation"], "| 分", r["score"], r["grade"])
    for n in r["narrative"]:
        print(" -", n)
