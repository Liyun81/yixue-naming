#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_sancai.py —— 三才配置表生成器

125 种三才（5×5×5）不可能逐条手写且保证内部一致，故采用：
    规则引擎（五行生克打分）生成基线 + SPECIAL 特殊判语人工校准
输出 assets/sancai_config.json；若存在 assets/sancai_overrides.json 则最后合并覆盖。

用法：
    python gen_sancai.py
"""

import itertools
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE_DIR, "assets")
OUT = os.path.join(ASSETS, "sancai_config.json")
OVERRIDE = os.path.join(ASSETS, "sancai_overrides.json")

WUXING = ["木", "火", "土", "金", "水"]
IDX = {w: i for i, w in enumerate(WUXING)}
SHENG = {WUXING[i]: WUXING[(i + 1) % 5] for i in range(5)}   # 木→火→土→金→水→木
KE = {WUXING[i]: WUXING[(i + 2) % 5] for i in range(5)}      # 木→土→水→火→金→木


def relation(sub: str, obj: str) -> str:
    """sub 对 obj 的作用关系：生 / 克 / 比和 / 被生 / 被克"""
    if sub == obj:
        return "比和"
    if SHENG[sub] == obj:
        return "生"
    if KE[sub] == obj:
        return "克"
    if SHENG[obj] == sub:
        return "被生"
    return "被克"


# 成功运：天格 → 人格
SUCCESS = {
    "生": (100, "天生人", "得长辈、上级提携，贵人相扶，事顺而易成。"),
    "比和": (88, "天人比和", "上下同气，和谐无争，稳步而进。"),
    "被克": (72, "人克天", "不甘受制，能自立突破，然与上多摩擦，劳心而成。"),
    "被生": (62, "人生天", "付出多而得助少，为长辈家业操劳，成事较缓。"),
    "克": (40, "天克人", "受上压制，阻碍偏多，须借他力与地格扶持。"),
}

# 基础运：人格 → 地格
BASE = {
    "被生": (100, "地生人", "根基稳固，得家人与下属之力，安若磐石。"),
    "比和": (90, "人地比和", "内外一致，家宅平顺，无内耗之虞。"),
    "克": (86, "人克地", "能掌控局面与部属，主动进取而不失稳。"),
    "生": (64, "人生地", "为家庭子女付出良多，自身易感耗损。"),
    "被克": (42, "地克人", "根基浮动，家庭或下属易成牵累。"),
}

# 特殊组合人工校准（覆盖规则引擎的判语与等级）
SPECIAL = {
    "木火木": ("大吉", "木火通明，文秀聪敏，主文教、艺术、名誉之贵。"),
    "木火土": ("大吉", "木生火、火生土，三才顺生，福泽绵长。"),
    "火土木": ("吉", "火生土、土培木根，稳重有成，宜实业与地产。"),
    "土火木": ("吉", "火土相生而木得养，中正平和，家业可守。"),
    "金水木": ("吉", "金生水、水生木，智谋清贵，宜金融、谋划、学术。"),
    "水金水": ("吉", "金水相涵，聪慧机敏，宜技艺、外交。"),
    "木土水": ("凶", "木克土、土克水，中隔相制，一生多变动，宜守不宜进。"),
    "土水土": ("凶", "水泛土崩，根基易动，家宅多变，宜稳守。"),
    "水水水": ("凶", "水多无制，漂泊多思，宜借木土之格以固根基。"),
    "火火火": ("半吉", "火气过旺，热情而急躁，宜养柔德以济刚。"),
    "金金金": ("凶", "金气过刚，义而寡合，易伤和气，宜以水润之。"),
    "木木木": ("吉", "木气纯厚，仁德有守，然须防固执，宜纳火土。"),
    "土土土": ("吉", "土德厚载，稳重诚信，守成有余而进取稍缓。"),
}


def grade(score: int) -> str:
    if score >= 90:
        return "大吉"
    if score >= 80:
        return "吉"
    if score >= 68:
        return "半吉"
    if score >= 52:
        return "凶"
    return "大凶"


def advice(luck: str, combo: str) -> str:
    table = {
        "大吉": "三才顺遂，可顺势进取，宜择与五行相合之行业以尽其长。",
        "吉": "格局平和，稳中求进为佳，忌躁进贪多。",
        "半吉": "吉凶互见，宜以柔济刚、守正待时，中年后渐入佳境。",
        "凶": "格局多阻，宜安分守成、积德养性；起名时可优先调整地格用字笔画。",
        "大凶": "三才相制过甚，传统视为格局欠安；起名时建议重择用字，使三才趋生。",
    }
    return table[luck]


def build() -> dict:
    configs = {}
    for t, r, d in itertools.product(WUXING, repeat=3):
        s_score, s_name, s_text = SUCCESS[relation(t, r)]
        b_score, b_name, b_text = BASE[relation(r, d)]
        score = round(s_score * 0.5 + b_score * 0.5)
        combo = f"{t}{r}{d}"
        luck = grade(score)
        note = ""
        if combo in SPECIAL:
            luck, note = SPECIAL[combo]
        configs[combo] = {
            "combo": combo,
            "tian": t,
            "ren": r,
            "di": d,
            "success": {"relation": s_name, "score": s_score, "text": s_text},
            "base": {"relation": b_name, "score": b_score, "text": b_text},
            "score": score,
            "luck": luck,
            "note": note,
            "advice": advice(luck, combo),
        }
    return configs


def main() -> int:
    configs = build()
    if os.path.exists(OVERRIDE):
        with open(OVERRIDE, encoding="utf-8") as f:
            ov = json.load(f)
        applied = 0
        for combo, patch in ov.get("overrides", {}).items():
            if combo in configs:
                configs[combo].update(patch)
                applied += 1
        print(f"[gen] 已应用人工覆盖 {applied} 条")

    dist = {}
    for v in configs.values():
        dist[v["luck"]] = dist.get(v["luck"], 0) + 1

    payload = {
        "_meta": {
            "count": len(configs),
            "version": "1.0",
            "generator": "gen_sancai.py（五行生克规则引擎）",
            "success_weight": 0.5,
            "base_weight": 0.5,
            "distribution": dist,
            "note": "等级由规则引擎打分得出，SPECIAL 与 overrides 可人工校准",
        },
        "configs": configs,
    }
    os.makedirs(ASSETS, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"[gen] 生成 {len(configs)} 条三才配置")
    print(f"[gen] 吉凶分布：{dist}")
    print(f"[gen] 已写入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
