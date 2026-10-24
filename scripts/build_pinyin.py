# -*- coding: utf-8 -*-
"""读音数据构建器：为笔画库中的每个汉字生成拼音/声母/韵母/声调，供五音分析使用。

设计要点：
- pypinyin 只在**构建期**用于取得带调拼音字符串；
- 声母/韵母/声调由本脚本自行解析（不依赖 pypinyin 的多音索引），保证一致可核对；
- 运行时只读 assets/pinyin.json，零第三方依赖。

用法：python build_pinyin.py
"""
import json
import os
import sys
import unicodedata

try:
    from pypinyin import pinyin, Style
except ImportError:
    sys.exit("需要 pypinyin：pip install pypinyin（仅构建期依赖）")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE, "assets")

# 五音归类（按发音部位，对应传统宫商角徵羽）
INITIAL_WUYIN = {
    "g": "宫", "k": "宫", "h": "宫", "": "宫",          # 喉音（含零声母/影喻母）
    "z": "商", "c": "商", "s": "商",                     # 齿音
    "zh": "商", "ch": "商", "sh": "商", "r": "商",
    "j": "角", "q": "角", "x": "角",                    # 牙音（见组细音）
    "d": "徵", "t": "徵", "n": "徵", "l": "徵",          # 舌音（舌尖中）
    "b": "羽", "p": "羽", "m": "羽", "f": "羽",          # 唇音
}
WUYIN_WUXING = {"宫": "土", "商": "金", "角": "木", "徵": "火", "羽": "水"}
INITIALS_ORDER = ["zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
                  "g", "k", "h", "j", "q", "x", "r", "z", "c", "s"]
TONE_MARKS = {"\u0304": 1, "\u0301": 2, "\u030c": 3, "\u0300": 4}  # ˉ ˊ ˇ ˋ

# 姓氏多音字校准：作“姓”使用时的读音（影响五音归类与平仄判断）
SURNAME_READING = {
    "单": "shàn", "解": "xiè", "区": "ōu", "仇": "qiú", "查": "zhā", "朴": "piáo",
    "乐": "yuè", "曾": "zēng", "缪": "miào", "覃": "qín", "翟": "zhái", "盖": "gě",
    "繁": "pó", "员": "yùn", "尉": "yù", "秘": "bì", "种": "chóng", "隗": "wěi",
    "郗": "xī", "句": "gōu", "过": "guō", "华": "huà", "任": "rén", "燕": "yān",
    "纪": "jǐ", "召": "shào", "祭": "zhài", "折": "shé", "黑": "hè", "相": "xiàng",
    "长": "zhǎng", "重": "chóng", "都": "dū", "宁": "nìng", "阚": "kàn", "訾": "zī",
    "冼": "xiǎn", "蕃": "pí", "藏": "zàng", "贲": "bēn", "六": "lù", "不": "fǒu",
    "綦": "qí", "迮": "zé", "笪": "dá", "圈": "quān", "宓": "fú", "蘧": "qú",
}


def parse_syllable(syl: str) -> dict:
    """解析带调拼音字符串为 (无调拼音, 声母, 韵母, 声调)。"""
    nfd = unicodedata.normalize("NFD", syl)
    buf, tone = [], 5
    for ch in nfd:
        if ch in TONE_MARKS:
            tone = TONE_MARKS[ch]
            continue
        buf.append(ch)
    plain = unicodedata.normalize("NFC", "".join(buf)).lower()
    ini = ""
    for cand in INITIALS_ORDER:
        if plain.startswith(cand):
            ini = cand
            break
    fin = plain[len(ini):]
    return {"plain": plain, "initial": ini, "final": fin, "tone": tone}


def final_meta(fin: str) -> dict:
    """韵母的音律属性：韵尾类型与四呼口型。"""
    nasal = "鼻" if fin.endswith(("n", "ng")) else "元"
    if fin.startswith(("u", "ü")) or fin in ("u",):
        hu = "合口"
    elif fin.startswith(("i", "ü")):
        hu = "齐齿" if fin.startswith("i") else "撮口"
    elif fin.startswith("y"):
        hu = "齐齿"
    elif fin.startswith("w"):
        hu = "合口"
    else:
        hu = "开口"
    return {"final_type": nasal, "hu": hu}


def build_info(syl: str) -> dict:
    p = parse_syllable(syl)
    wuyin = INITIAL_WUYIN.get(p["initial"], "宫")
    tone = p["tone"]
    meta = final_meta(p["final"])
    return {
        "pinyin": syl,
        "plain": p["plain"],
        "tone": tone,
        "initial": p["initial"],
        "final": p["final"],
        "wuyin": wuyin,
        "wuxing": WUYIN_WUXING[wuyin],
        "pingze": "平" if tone in (1, 2) else ("仄" if tone in (3, 4) else "轻"),
        "final_type": meta["final_type"],
        "hu": meta["hu"],
    }


def default_reading(ch: str) -> dict:
    syl = pinyin(ch, style=Style.TONE, strict=True, errors=lambda x: ["?"])[0][0]
    if not syl or syl == "?":
        return {}
    return build_info(syl)


def readings_of(ch: str) -> list:
    """该字所有候选读音（用于校验姓氏读音是否存在）。"""
    return pinyin(ch, style=Style.TONE, heteronym=True, strict=True,
                  errors=lambda x: ["?"])[0]


def main():
    with open(os.path.join(ASSETS, "kangxi_strokes.json"), encoding="utf-8") as f:
        chars = list(json.load(f)["chars"].keys())

    out, failed = {}, []
    for ch in chars:
        info = default_reading(ch)
        if info:
            out[ch] = info
        else:
            failed.append(ch)

    # 姓氏读音：按目标读音直接解析，并校验该读音确为多音候选之一
    sur_sound, sur_diff, sur_bad = {}, {}, []
    for ch, reading in SURNAME_READING.items():
        cands = readings_of(ch)
        if reading not in cands:
            sur_bad.append(f"{ch}:{reading}(候选{','.join(cands)})")
            continue
        info = build_info(reading)
        sur_sound[ch] = info
        if ch in out and out[ch]["pinyin"] != reading:
            sur_diff[ch] = {"default": out[ch]["pinyin"], "as_surname": reading}

    payload = {
        "meta": {
            "source": "pypinyin 取带调拼音 + 自解析声韵调（构建期生成，运行时零依赖）",
            "count": len(out),
            "note": "声调 1-4 为四声、5 为轻声；平仄按普通话四声判定，入声字已派入平声",
        },
        "chars": out,
        "surname_reading": SURNAME_READING,
        "surname_sound": sur_sound,
        "surname_diff": sur_diff,
    }
    with open(os.path.join(ASSETS, "pinyin.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"生成 {len(out)} 字读音，失败 {len(failed)}：{''.join(failed[:20])}")
    print(f"姓氏读音 {len(sur_sound)} 条，音库中实际异读 {len(sur_diff)} 条，异常 {len(sur_bad)} 条")
    for b in sur_bad:
        print("  异常：", b)
    print("  抽样：" + "  ".join(f"{c}{v['pinyin']}={v['initial']}-{v['final']}/{v['wuyin']}"
                               for c, v in list(sur_sound.items())[:10]))
    print("  单字：" + "  ".join(f"{c} {out[c]['pinyin']} {out[c]['initial']}-{out[c]['final']}"
                               f" {out[c]['wuyin']}音/{out[c]['wuxing']} {out[c]['pingze']}"
                               for c in ("李", "明", "华", "张", "王", "欧", "曾") if c in out))


if __name__ == "__main__":
    main()
