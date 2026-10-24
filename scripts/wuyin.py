# -*- coding: utf-8 -*-
"""五音（宫商角徵羽）与平仄分析模块。

用途：以传统五音音系（喉宫、齿商、牙角、舌徵、唇羽）与四声平仄，
佐证姓名整体读音是否谐和顺畅。输出量化评分 + 可解释的判据，不做绝对断言。

传统依据：
- 五音配五行为 角木、徵火、宫土、商金、羽水；
- 五音相生同五行相生（角→徵→宫→商→羽→角），相克同五行相克；
- 姓名音律讲"起伏有节、五音相济"，忌三字同调、同音堆叠。
"""
import json
import os
from functools import lru_cache
from typing import Dict, List, Optional

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

WUYIN_WUXING = {"宫": "土", "商": "金", "角": "木", "徵": "火", "羽": "水"}
WUYIN_ORGAN = {"宫": "喉音", "商": "齿音", "角": "牙音", "徵": "舌音", "羽": "唇音"}
WUYIN_IMAGE = {
    "宫": "浑厚居中，如土之载物",
    "商": "清劲收敛，如金之肃杀",
    "角": "舒展开张，如木之生发",
    "徵": "明亮上扬，如火之炎上",
    "羽": "轻扬流转，如水之润下",
}
# 五行相生 / 相克（音气关系）
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
# 四声调值（起点, 终点），用于量化音高起伏
TONE_PITCH = {1: (5, 5), 2: (3, 5), 3: (2, 4), 4: (5, 1), 5: (3, 3)}


class WuyinError(Exception):
    """五音分析异常。"""


def load_pinyin() -> Dict:
    path = os.path.join(ASSETS, "pinyin.json")
    if not os.path.exists(path):
        raise WuyinError("读音数据缺失，请先运行 build_pinyin.py 生成 assets/pinyin.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def relation_of(a: str, b: str) -> str:
    """判断两个五行（音气）之间的关系（不分方向）。"""
    if a == b:
        return "比和"
    if SHENG.get(a) == b or SHENG.get(b) == a:
        return "相生"
    if KE.get(a) == b or KE.get(b) == a:
        return "相克"
    return "无涉"


def direction_of(a: str, b: str) -> str:
    """关系方向：顺生（前生后，气脉相续）／逆生（后生前，前气外泄）
    ／顺克（前制后）／逆克（后制前，后者受制）。"""
    if a == b:
        return "同气"
    if SHENG.get(a) == b:
        return "顺生"
    if SHENG.get(b) == a:
        return "逆生"
    if KE.get(a) == b:
        return "顺克"
    if KE.get(b) == a:
        return "逆克"
    return "无涉"


class WuyinAnalyzer:
    def __init__(self):
        self.data = load_pinyin()
        self.chars_map = self.data["chars"]
        self.surname_sound = self.data.get("surname_sound", {})

    # ---------- 单字 ----------
    def char_detail(self, ch: str, is_surname: bool = False) -> Dict:
        src = None
        # 姓氏多音字：优先取构建期算好的“作姓读音”，避免运行时依赖拼音库
        if is_surname and ch in self.surname_sound:
            src = self.surname_sound[ch]
        elif ch in self.chars_map:
            src = self.chars_map[ch]
        if not src:
            raise WuyinError(f"读音库中缺少「{ch}」，请先用 stroke_query.py add 补录笔画后重建读音库")
        detail = dict(src)
        detail["char"] = ch
        detail["organ"] = WUYIN_ORGAN[detail["wuyin"]]
        detail["wuyin_image"] = WUYIN_IMAGE[detail["wuyin"]]
        return detail

    @staticmethod
    def _wuyin_of(initial: str) -> str:
        mapping = {
            "g": "宫", "k": "宫", "h": "宫", "": "宫",
            "z": "商", "c": "商", "s": "商", "zh": "商", "ch": "商", "sh": "商", "r": "商",
            "j": "角", "q": "角", "x": "角",
            "d": "徵", "t": "徵", "n": "徵", "l": "徵",
            "b": "羽", "p": "羽", "m": "羽", "f": "羽",
        }
        return mapping.get(initial, "宫")

    # ---------- 整体 ----------
    def analyze(self, chars: List[str], surname_len: int = 1,
                ref_wuxing: Optional[str] = None) -> Dict:
        """分析整名读音。

        chars: 姓名逐字列表（按顺序）
        surname_len: 姓的字数（用于姓氏读音校正）
        ref_wuxing: 参照五行（如总格五行），用于判断音气与格气是否协和
        """
        if not chars:
            raise WuyinError("姓名为空")
        details = [self.char_detail(c, is_surname=(i < surname_len))
                   for i, c in enumerate(chars)]

        tones = [d["tone"] for d in details]
        pingze = [d["pingze"] for d in details]
        wuyin = [d["wuyin"] for d in details]
        wx = [d["wuxing"] for d in details]
        initials = [d["initial"] for d in details]
        finals = [d["final"] for d in details]
        ftypes = [d["final_type"] for d in details]

        n = len(details)
        issues: List[str] = []
        praise: List[str] = []

        # --- A. 声调起伏 (30) ---
        distinct = len(set(tones))
        if n == 1:
            a = 22
        elif distinct == 1:
            a = 8
            issues.append(f"三字同调（{'、'.join(sorted(set(pingze)))}声一顺），读来平板少起伏")
        elif distinct == 2:
            a = 24
        else:
            a = 30
            praise.append("四声错落，调值起伏有致，诵读有节奏感")
        dup_tone = sum(1 for i in range(n - 1) if tones[i] == tones[i + 1])
        a = max(0, a - 3 * dup_tone)

        # 音高起伏量化（调值首尾落差，仅作说明不占分）
        pitch_jumps = []
        for i in range(n - 1):
            drop = abs(TONE_PITCH[tones[i]][1] - TONE_PITCH[tones[i + 1]][0])
            pitch_jumps.append(drop)

        # --- B. 五音搭配 (25) ---
        pairs = []
        for i in range(n - 1):
            rel = relation_of(wx[i], wx[i + 1])
            pairs.append({
                "pair": f"{details[i]['char']}·{details[i+1]['char']}",
                "from": f"{wuyin[i]}({wx[i]})",
                "to": f"{wuyin[i+1]}({wx[i+1]})",
                "relation": rel,
                "direction": direction_of(wx[i], wx[i + 1]),
            })
        if n == 1:
            b = 18
        elif len(set(wuyin)) == 1:
            b = 8
            issues.append(f"三字同属{wuyin[0]}音（{WUYIN_ORGAN[wuyin[0]]}），咬字着力点单一，缺乏音色层次")
        elif any(p["relation"] == "相克" for p in pairs):
            b = 14
            kp = [p["pair"] for p in pairs if p["relation"] == "相克"]
            issues.append(f"五音相克（{'、'.join(kp)}）：音气互制，读来略觉转折生硬")
        elif all(p["relation"] == "相生" for p in pairs):
            b = 25
            praise.append("五音相生（" + "→".join(wuyin) + "），音气相续，听感顺畅")
        else:
            b = 20

        # --- C. 声母避重 (15) ---
        c = 15
        same_ini = [f"{details[i]['char']}{details[i+1]['char']}" for i in range(n - 1)
                    if initials[i] == initials[i + 1] and initials[i] != ""]
        if same_ini:
            c = max(0, 15 - 6 * len(same_ini))
            issues.append(f"声母重复（{'、'.join(same_ini)}），属双声，连续发音略显黏连")
        elif n >= 3:
            praise.append("声母各不相同，字头清晰，咬字不打架")

        # --- D. 韵母避重 (15) ---
        d = 15
        same_fin = [f"{details[i]['char']}{details[i+1]['char']}" for i in range(n - 1)
                    if finals[i] == finals[i + 1]]
        if same_fin:
            d = max(0, 15 - 6 * len(same_fin))
            issues.append(f"韵母重复（{'、'.join(same_fin)}），属叠韵，尾音回环易含混")
        elif n >= 3:
            praise.append("韵母各异，字腹有余地，尾音不撞")

        # 同音字（声母+韵母+声调全同）
        for i in range(n - 1):
            if initials[i] == initials[i + 1] and finals[i] == finals[i + 1] and tones[i] == tones[i + 1]:
                issues.append(f"「{details[i]['char']}」与「{details[i+1]['char']}」完全同音，称呼时易混")
                d = max(0, d - 5)

        # --- E. 韵尾与口型变化 (15) ---
        if n == 1:
            e = 12
        elif len(set(ftypes)) == 1 and n >= 3:
            e = 8
            kind = "鼻韵尾" if ftypes[0] == "鼻" else "元音收尾"
            issues.append(f"三字均以{kind}作结，收声方式雷同，余韵稍闷")
        else:
            e = 15
            if n >= 3 and len(set(ftypes)) > 1:
                praise.append("鼻韵与元音收尾相间，收音有开有合")

        score = a + b + c + d + e
        if score >= 85:
            grade, comment = "谐和", "音律整体谐和，诵读顺口，称呼响亮有余韵。"
        elif score >= 70:
            grade, comment = "尚可", "音律基本顺畅，个别处略有黏连，不影响使用。"
        elif score >= 55:
            grade, comment = "偏涩", "音律偏涩，连读时有拗口之感，可考虑调整用字。"
        else:
            grade, comment = "拗口", "音律不协，读来吃力，建议换字重排。"

        # --- 五音与格气呼应（可选）---
        resonance = None
        if ref_wuxing:
            rel = relation_of(wx[0], ref_wuxing) if n == 1 else None
            rels = [relation_of(w, ref_wuxing) for w in wx]
            sheng_cnt = sum(1 for r in rels if r in ("相生", "比和"))
            resonance = {
                "ref_wuxing": ref_wuxing,
                "per_char": [{"char": d0["char"], "wuyin_wuxing": w0, "relation": r0}
                             for d0, w0, r0 in zip(details, wx, rels)],
                "harmony": round(sheng_cnt / len(rels) * 100),
                "note": ("五音五行与格气多相生比和，音气与格局同向" if sheng_cnt >= len(rels) * 0.7
                         else "五音五行与格气有相克处，音气与格局略见拉扯（传统视为需留意处）"),
            }

        return {
            "chars": details,
            "tone_seq": tones,
            "pingze_seq": "".join(pingze),
            "pitch_jumps": pitch_jumps,
            "wuyin_seq": "".join(wuyin),
            "wuxing_seq": "".join(wx),
            "pairs": pairs,
            "score": score,
            "grade": grade,
            "comment": comment,
            "dims": {"声调起伏": a, "五音搭配": b, "声母避重": c, "韵母避重": d, "韵尾变化": e},
            "issues": issues,
            "praise": praise,
            "resonance": resonance,
            "note": "平仄按普通话四声判定（一二声平、三四声仄），入声字已派入平声，与中古四声略有差异。",
        }


@lru_cache(maxsize=256)
def _analyze_wuyin_cached(chars_tuple: tuple, surname_len: int, ref_wuxing: Optional[str]) -> Dict:
    return WuyinAnalyzer().analyze(list(chars_tuple), surname_len, ref_wuxing)


def analyze_wuyin(chars: List[str], surname_len: int = 1,
                  ref_wuxing: Optional[str] = None) -> Dict:
    return _analyze_wuyin_cached(tuple(chars), surname_len, ref_wuxing)


if __name__ == "__main__":
    demo = analyze_wuyin(list("李明华"), 1)
    print("音序：", demo["wuyin_seq"], "| 平仄：", demo["pingze_seq"], "| 分：", demo["score"], demo["grade"])
    for d0 in demo["chars"]:
        print(f"  {d0['char']} {d0['pinyin']} {d0['wuyin']}音/{d0['wuxing']} {d0['pingze']}")
