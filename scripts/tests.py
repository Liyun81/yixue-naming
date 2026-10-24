# -*- coding: utf-8 -*-
"""回归测试：五格 / 五音 / 梅花易数 / 字义 / 集成。

运行：python tests.py      （全绿退出码 0，有失败退出码 1）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import meihua  # noqa: E402
import wuyin  # noqa: E402
import wuge  # noqa: E402

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(f"  {'✓' if cond else '✗'} {name}" + (f" — {detail}" if detail and not cond else ""))


def eq(name, got, want):
    check(name, got == want, f"期望 {want}，实际 {got}")


def load(fn):
    with open(os.path.join(ASSETS, fn), encoding="utf-8") as f:
        return json.load(f)


# ---------------- 1. 五格 ----------------
def test_wuge():
    print("\n[1] 五格计算（四种结构）")
    cases = [
        ("王", "五", {"tian": 5, "ren": 8, "di": 5, "wai": 2, "zong": 8}),
        ("李", "明华", {"tian": 8, "ren": 15, "di": 22, "wai": 15, "zong": 29}),
        ("诸葛", "亮", {"tian": 31, "ren": 24, "di": 10, "wai": 17, "zong": 40}),
        ("欧阳", "明华", {"tian": 32, "ren": 25, "di": 22, "wai": 29, "zong": 54}),
    ]
    for s, g, want in cases:
        r = wuge.analyze(s, g)
        got = {k: v["value"] for k, v in r["grids"].items()}
        eq(f"{s}{g} 五格", got, want)

    r = wuge.analyze("王", "五", wuge.WugeConfig(waige_mode="formula_1"))
    eq("王五 外格 formula_1 流派", r["grids"]["wai"]["value"], 1)

    r = wuge.analyze("李", "明华")
    check("评分区间 0-100", 0 <= r["score"] <= 100, str(r["score"]))
    check("数理在 1-81", all(1 <= v["number"] <= 81 for v in r["grids"].values()))
    check("五行合法", all(v["wuxing"] in "木火土金水" for v in r["grids"].values()))


# ---------------- 2. 五音 ----------------
def test_wuyin():
    print("\n[2] 五音与平仄")
    wy = wuyin.WuyinAnalyzer()
    cases = [("李", "徵", "仄"), ("张", "商", "平"), ("王", "宫", "平"),
             ("陈", "商", "平"), ("安", "宫", "平"), ("刘", "徵", "平"),
             ("马", "羽", "仄"), ("徐", "角", "平")]
    for ch, tone_wy, pz in cases:
        d = wy.char_detail(ch)
        eq(f"{ch} 五音", d["wuyin"], tone_wy)
        eq(f"{ch} 平仄", d["pingze"], pz)

    # 姓氏异读：单（shàn）不作 dān，解（xiè）不作 jiě
    eq("单 作姓 读音", wy.char_detail("单", is_surname=True)["pinyin"], "shàn")
    eq("单 作姓 五音", wy.char_detail("单", is_surname=True)["wuyin"], "商")
    eq("解 作姓 读音", wy.char_detail("解", is_surname=True)["pinyin"], "xiè")
    eq("单 非姓默认", wy.char_detail("单")["pinyin"], "dān")

    # 三同调
    r = wuyin.analyze_wuyin(list("张嘉欣"), 1)
    check("检测三字同调", any("同调" in s for s in r["issues"]),
          f"{r['pingze_seq']} {r['issues']}")
    # 双声
    r2 = wuyin.analyze_wuyin(list("张哲"), 1)
    check("检测声母重复", any("声母" in s for s in r2["issues"]), str(r2["issues"]))
    # 叠韵
    r3 = wuyin.analyze_wuyin(list("李丽"), 1)
    check("检测韵母重复", any("韵母" in s or "同音" in s for s in r3["issues"]), str(r3["issues"]))

    r4 = wuyin.analyze_wuyin(list("李明华"), 1)
    check("音律分区间", 0 <= r4["score"] <= 100, str(r4["score"]))
    check("音律维度合计=总分", sum(r4["dims"].values()) == r4["score"], str(r4["dims"]))
    check("相邻关系含方向", all("direction" in p for p in r4["pairs"]))
    eq("方向判定 火→水 逆克", wuyin.direction_of("火", "水"), "逆克")
    eq("方向判定 木→火 顺生", wuyin.direction_of("木", "火"), "顺生")
    eq("方向判定 火→火 同气", wuyin.direction_of("火", "火"), "同气")

    # 姓氏多音字不应破坏整体分析
    r5 = wuyin.analyze_wuyin(list("单雄信"), 1)
    eq("单雄信 首字音", r5["chars"][0]["wuyin"], "商")


# ---------------- 3. 梅花易数 ----------------
def test_meihua():
    print("\n[3] 梅花易数起卦")
    mh = meihua.MeihuaAnalyzer()
    eq("1 取乾", mh.num_to_gua(1), "乾")
    eq("8 取坤", mh.num_to_gua(8), "坤")
    eq("9 取乾（余1）", mh.num_to_gua(9), "乾")
    eq("16 取坤（余0）", mh.num_to_gua(16), "坤")

    # 李明华：李7 / 名22 / 总29
    c = mh.cast_name([7], [8, 14])
    eq("上卦 7→艮", c["ben"]["gua"]["upper"], "艮")
    eq("下卦 22→坎", c["ben"]["gua"]["lower"], "坎")
    eq("本卦 山水蒙", c["ben"]["gua"]["name"], "山水蒙")
    eq("动爻 29%6=5", c["ben"]["moving_line"], 5)
    eq("互卦 地雷复", c["hu"]["gua"]["name"], "地雷复")
    eq("变卦 风水涣", c["bian"]["gua"]["name"], "风水涣")
    eq("体卦 下卦（动爻在上）", c["ti"]["gua"], "坎")
    eq("用卦 上卦", c["yong"]["gua"], "艮")

    r = mh.analyze(c, meihua.month_context(branch="子"))
    eq("体用 用克体", r["tiyong"]["relation"], "用克体")
    eq("子月 水旺", r["wangshuai"]["ti_in_month"]["state"], "旺")
    eq("子月 土囚", meihua.state_of("土", "水"), "囚")
    eq("寅月 木旺", meihua.state_of("木", "木"), "旺")
    eq("寅月 火相", meihua.state_of("火", "木"), "相")
    eq("寅月 水休", meihua.state_of("水", "木"), "休")
    eq("寅月 金囚", meihua.state_of("金", "木"), "囚")
    eq("寅月 土死", meihua.state_of("土", "木"), "死")

    check("卦气指数区间", 0 <= r["wangshuai"]["qi_index"] <= 100, str(r["wangshuai"]["qi_index"]))
    check("评分区间", 0 <= r["score"] <= 100, str(r["score"]))
    check("六位俱全", len(r["wangshuai"]["positions"]) == 6)
    check("体卦自身权重为 0",
          all(p["weight"] == 0 for p in r["wangshuai"]["positions"] if p["relation"] == "本体"))
    check("变卦不计入卦气",
          all(p["weight"] == 0 for p in r["wangshuai"]["positions"] if p["group"] == "result"))

    # 动爻在下卦 → 上卦为体
    c2 = mh.cast_name([7], [5])          # 7+5=12, 12%6=0→6 爻动，在上卦
    eq("12%6 动爻取 6", c2["ben"]["moving_line"], 6)
    c3 = mh.cast_name([8], [1])          # 8+1=9, 9%6=3 动爻在下卦
    eq("动爻 3 在下卦", c3["ti"]["pos"], "上卦")
    eq("动爻 3 下卦为用", c3["yong"]["pos"], "下卦")

    # 机构起卦：同和堂 6 / 8+11=19 / 25%6=1
    c4 = mh.cast_org([6, 8, 11])
    eq("同和堂 上卦 6→坎", c4["ben"]["gua"]["upper"], "坎")
    eq("同和堂 下卦 19%8=3→离", c4["ben"]["gua"]["lower"], "离")
    eq("同和堂 本卦 水火既济", c4["ben"]["gua"]["name"], "水火既济")

    # 卦象数据完整性
    data = load("gua64.json")
    check("64 卦齐备", len(data["gua"]) == 64, str(len(data["gua"])))
    check("上下卦组合唯一",
          len({(g["upper"], g["lower"]) for g in data["gua"].values()}) == 64)
    from collections import Counter
    c_gong = Counter(g["gong"] for g in data["gua"].values())
    check("八宫各 8 卦", all(v == 8 for v in c_gong.values()), str(dict(c_gong)))
    check("八宫五行一致",
          all(data["gong_wuxing"][g["gong"]] == data["bagua"][g["gong"]]["wuxing"]
              for g in data["gua"].values()))

    # —— 1.3.0 整改：起卦底层一律用现代简体字笔画 ——
    simp = load("simplified_strokes.json")
    check("简体笔画库规模 ≥2600", len(simp["strokes"]) >= 2600, str(len(simp["strokes"])))
    for ch, want in (("刘", 6), ("华", 6), ("万", 3), ("云", 4),
                     ("宇", 6), ("鹏", 13), ("阳", 6)):
        eq(f"简体笔画 {ch}={want}", simp["strokes"].get(ch), want)
    check("繁→简映射 ≥600 对", len(simp["t2s"]) >= 600, str(len(simp["t2s"])))
    for t, s in (("劉", "刘"), ("華", "华"), ("雲", "云"), ("萬", "万"), ("陽", "阳")):
        eq(f"繁体 {t}→{s}", simp["t2s"].get(t), s)

    eq("name_strokes 刘宇鹏", [v["strokes"] for v in
                               meihua.name_strokes("刘宇鹏").values()], [6, 6, 13])
    eq("繁体输入 劉 明 華 映射后计数",
       meihua.strokes_of_name("劉明華"), [6, 8, 6])
    eq("繁体字标记 繁转简", meihua.name_strokes("劉")["劉"]["via"], "繁转简")
    try:
        meihua.strokes_of_name("ﬂ")
        check("未收录字应抛错", False)
    except meihua.MeihuaError:
        check("未收录字抛 MeihuaError", True)

    # 刘宇鹏（简体笔画：姓 6 / 名 6+13=19 / 合 25 → 第 1 爻动）
    c5 = mh.cast_name([6], [6, 13])
    eq("刘宇鹏 上卦 6→坎", c5["ben"]["gua"]["upper"], "坎")
    eq("刘宇鹏 下卦 19%8=3→离", c5["ben"]["gua"]["lower"], "离")
    eq("刘宇鹏 本卦 水火既济", c5["ben"]["gua"]["name"], "水火既济")
    eq("刘宇鹏 动爻 25%6=1", c5["ben"]["moving_line"], 1)

    # 繁体起卦必须等于对应简体的卦（不得用繁体笔画）
    c_liu_simp = mh.cast_name(meihua.strokes_of_name("刘"), [13])
    c_liu_trad = mh.cast_name(meihua.strokes_of_name("劉"), [13])
    eq("劉 与 刘 起卦一致", c_liu_trad["ben"]["gua"]["name"],
       c_liu_simp["ben"]["gua"]["name"])

    # —— 1.3.1 笔画勘误：艹部字康熙值 = 简体 + 3 ——
    kang = load("kangxi_strokes.json")["chars"]
    for ch in ("芃", "芷", "茗", "茜"):
        eq(f"康熙笔画 {ch}={simp['strokes'][ch] + 3}",
           kang.get(ch), simp["strokes"][ch] + 3)
    eq("芃 简体笔画 6", simp["strokes"].get("芃"), 6)

    # —— 1.3.2 常用字补录：希／前／松／杉／艳／璞／琛／穑 三库齐备 ——
    py = load("pinyin.json")["chars"]
    for ch, kx, sp, pn in (("希", 7, 7, "xī"), ("前", 9, 9, "qián"),
                           ("松", 8, 8, "sōng"), ("杉", 7, 7, "shān"),
                           ("艳", 24, 10, "yàn"), ("璞", 17, 16, "pú"),
                           ("琛", 13, 12, "chēn"), ("穑", 18, 16, "sè")):
        eq(f"康熙笔画 {ch}={kx}", kang.get(ch), kx)
        eq(f"简体笔画 {ch}={sp}", simp["strokes"].get(ch), sp)
        eq(f"读音 {ch}={pn}", py[ch]["pinyin"], pn)
    eq("希 五音归角（x 声母）", py["希"]["wuyin"], "角")
    eq("希 平声", py["希"]["pingze"], "平")


# ---------------- 4. 字义 ----------------
def test_meaning():
    print("\n[4] 字义库")
    m = load("char_meaning.json")["chars"]
    eq("字义库字数", len(m), 2739)
    for ch in ("李", "王", "明", "华", "轩", "涵", "婷", "同", "堂", "芃", "希", "昶", "韦", "歧", "懿", "翰",
               "爱", "贝", "龙", "凤", "兴", "源", "医", "众"):
        check(f"{ch} 已收录", ch in m)
    check("字义五行合法", all(v["wuxing"] in "木火土金水" for v in m.values()))

    # ---- 统一 schema（v1.4.0 起）----
    need = {"char", "pinyin", "pos", "yi", "example", "xiang", "wuxing", "yong", "level"}
    check("统一字段齐全", all(need <= set(v) for v in m.values()))
    check("字段皆为字符串",
          all(isinstance(v[k], str) for v in m.values() for k in need))
    check("层级标记合法", all(v["level"] in ("full", "basic") for v in m.values()))
    check("full 层必有意象与导向",
          all(v["yong"] and v["xiang"] for v in m.values() if v["level"] == "full"))
    check("释义无一为空", all(v["yi"] for v in m.values()))
    check("拼音无一为空", all(v["pinyin"] for v in m.values()))
    check("词性无一为空", all(v["pos"] for v in m.values()))
    POS_OK = {"名", "动", "形", "数", "量", "代", "副", "介", "连", "助", "叹", "拟声", "姓", ""}
    check("词性取值合法", all(v["pos"] in POS_OK for v in m.values()))
    # 拼音须与拼音库一致（机构用字不在拼音库，走内置补录，跳过）
    py = load("pinyin.json")["chars"]
    bad = [c for c, v in m.items()
           if c in py and py[c].get("pinyin") and v["pinyin"] != py[c]["pinyin"]]
    check(f"拼音与拼音库一致（不一致 {len(bad)} 字）", not bad)
    # 繁简继承
    inh = {c: v for c, v in m.items() if v.get("variant_of")}
    check(f"繁简继承条目存在（{len(inh)} 条）", len(inh) >= 600)
    check("继承条目字义与简体一致",
          all(m[c]["yi"] == m[v["variant_of"]]["yi"] for c, v in inh.items()))
    # 覆盖率：以三库并集为基准须零遗漏
    st = load("kangxi_strokes.json")["chars"]
    si = load("simplified_strokes.json")["strokes"]
    base = set(st) | set(si) | set(py)
    missing = base - set(m)
    check(f"覆盖三库并集无遗漏（缺 {len(missing)} 字）", not missing)


# ---------------- 5. 数据资产 ----------------
def test_assets():
    print("\n[5] 数据资产")
    st = load("kangxi_strokes.json")
    check("笔画库规模 ≥2600", len(st["chars"]) >= 2600, str(len(st["chars"])))
    py = load("pinyin.json")
    check("读音覆盖笔画库", set(st["chars"]) <= set(py["chars"]),
          f"缺 {len(set(st['chars']) - set(py['chars']))} 字")
    check("拼音字段齐全",
          all({"pinyin", "tone", "initial", "final", "wuyin", "pingze"} <= set(v)
              for v in py["chars"].values()))
    check("姓氏读音已结构化", len(py.get("surname_sound", {})) >= 40,
          str(len(py.get("surname_sound", {}))))
    nb = load("eighty_one_numbers.json")["numbers"]
    eq("81 数理全量", len(nb), 81)
    sc = load("sancai_config.json")["configs"]
    eq("125 三才全量", len(sc), 125)


# ---------------- 6. 集成 ----------------
def test_integration():
    print("\n[6] 集成（analyze.py）")
    import analyze as app
    r = app.analyze_person("李", "明华", wuge.WugeConfig(gender="male"),
                           month=meihua.month_context(branch="午"))
    check("含字义", len(r["meanings"]) == 3)
    check("含五音", r["wuyin"] is not None)
    check("含卦象", r["meihua"] is not None)
    check("三项分数齐备", set(r["parts"]) == {"wuge", "wuyin", "meihua"}, str(r["parts"]))
    check("综合分区间", 0 <= r["overall"] <= 100, str(r["overall"]))
    check("含免责声明", "不构成命运决断" in r["disclaimer"])
    check("免责含科学效力表述", "不具备科学预测效力" in r["disclaimer"]
          and "仅供审美与文化参考" in r["disclaimer"])
    # 1.3.0：起卦一律简体笔画（李7 明8 华6 → 姓7 名14 合21）
    eq("梅花起卦用简体笔画",
       [v["strokes"] for v in r["meihua_strokes"].values()], [7, 8, 6])
    eq("简体起卦 本卦", r["meihua"]["cast"]["ben"]["gua"]["name"], "山水蒙")
    eq("简体起卦 动爻 21%6=3", r["meihua"]["cast"]["ben"]["moving_line"], 3)
    eq("起卦口径标注", r["meihua"]["stroke_standard"], "现代简体字笔画（非康熙繁体笔画）")
    txt = app.render_person(r)
    check("报告含全部段落", all(k in txt for k in ("一、字义", "二、五格", "三、五音",
                                              "四、梅花易数", "五、八字原盘",
                                              "六、跨体系统合", "七、综合")))
    check("报告含免责", "不构成命运决断" in txt)
    check("报告含科学效力免责", "不具备科学预测效力" in txt)
    check("报告各段落末均有免责", txt.count("不具备科学预测效力") >= 5,
          f"出现 {txt.count('不具备科学预测效力')} 次")
    check("报告标注简体起卦", "现代简体字规范笔画" in txt)
    check("报告含逐字简体笔画", "简体笔画：李7　明8　华6" in txt)

    # 六维解读必须落到文本报告（1.0.1 修复：此前只在 JSON 里，文本漏渲染）
    check("报告含六维", "六维解读" in txt)
    check("六维六项齐备", all(f"【{x}】" in txt
                              for x in ("性格", "事业", "财运", "健康", "婚姻", "家庭")))
    check("六维报告无断命式表述",
          not any(w in txt for w in ("孤寡", "灾祸频仍", "克夫", "克子")))

    # 刘宇鹏：实测暴露过「六维未渲染」与「性别判命」两个问题，锁为回归样例
    r3 = app.analyze_person("刘", "宇鹏", wuge.WugeConfig(gender="male"),
                            month=meihua.month_context(branch="戌"))
    got = [r3["wuge"]["grids"][k]["value"] for k in ("tian", "ren", "di", "wai", "zong")]
    eq("刘宇鹏五格 16/21/25/20/40", got, [16, 21, 25, 20, 40])
    t3 = app.render_person(r3)
    check("刘宇鹏六维入报告", "【婚姻】" in t3)
    check("刘宇鹏报告无孤寡断言", "孤寡" not in t3)
    check("刘宇鹏报告无灾祸断言", "灾祸频仍" not in t3)

    o = app.analyze_org("同和堂", meihua.month_context(branch="午"))
    check("机构模式有数理", o["shuli"]["number"] == 25, str(o["shuli"]))
    check("机构模式有卦", o["meihua"]["cast"]["ben"]["gua"]["name"] == "水火既济")
    check("机构起卦用简体笔画",
          [v["strokes"] for v in o["meihua_strokes"].values()], [6, 8, 11])
    otxt = app.render_org(o)
    check("机构报告可渲染", "机构名" in otxt)
    check("机构报告含科学效力免责", otxt.count("不具备科学预测效力") >= 4,
          f"出现 {otxt.count('不具备科学预测效力')} 次")

    # 跳过某维度仍可出报告
    r2 = app.analyze_person("王", "五", wuge.WugeConfig(), with_wuyin=False, with_meihua=False)
    check("可跳过五音与卦象", r2["wuyin"] is None and r2["meihua"] is None)
    check("跳过后仍能评分", 0 <= r2["overall"] <= 100)


# ---------------- 7. 异常 ----------------
def test_errors():
    print("\n[7] 异常处理")
    try:
        wuge.analyze("李", "A1")
        check("非汉字应抛错", False)
    except wuge.WugeError as e:
        check("非汉字抛 WugeError", True, e.message)

    try:
        wuge.analyze("李", "A1", None, full_name="李A1")
        check("full 非汉字应抛错", False)
    except wuge.WugeError:
        check("full 非汉字抛错", True)

    try:
        wuyin.analyze_wuyin([], 1)
        check("空输入应抛错", False)
    except wuyin.WuyinError:
        check("空输入抛 WuyinError", True)

    try:
        meihua.MeihuaAnalyzer().cast_name([], [5])
        check("空笔画应抛错", False)
    except meihua.MeihuaError:
        check("空笔画抛 MeihuaError", True)

    try:
        meihua.MeihuaAnalyzer().cast_org([6])
        check("机构单字应抛错", False)
    except meihua.MeihuaError:
        check("机构单字抛错", True)


# ---------------- 8. 表述边界 ----------------
def test_ethics():
    print("\n[8] 表述边界（1.0.1 中性化）")
    nums = load("eighty_one_numbers.json")["numbers"]

    # 渲染字段不得含断命式表述；legacy_note 是学术留档，不进报告，故不在此列
    banned = ("孤寡", "灾祸频仍", "克夫", "克子", "夭折", "绝嗣")
    bad = []
    for n in nums:
        for f in ("summary", "family", "health", "detail", "base"):
            v = n.get(f) or ""
            for w in banned:
                if w in v:
                    bad.append(f"{n['no']}.{f}:{w}")
    check("81 数理渲染字段无断命式表述", not bad, "、".join(bad[:5]))

    # 中性化只允许改措辞：吉凶判定与标签必须原样
    by_no = {n["no"]: n for n in nums}
    check("21 仍判大吉", by_no[21]["luck"] == "大吉", by_no[21]["luck"])
    check("20 仍判凶", by_no[20]["luck"] == "凶", by_no[20]["luck"])
    check("21 仍带首领数标签", "首领数" in by_no[21].get("tags", []))

    # 旧说须以 legacy_note 留档，不是删掉不认
    check("旧说已留档", all(by_no[x].get("legacy_note") for x in (20, 21, 23, 33, 39)),
          "缺失：" + "、".join(str(x) for x in (20, 21, 23, 33, 39)
                              if not by_no[x].get("legacy_note")))


def test_cards():
    print("\n[8] 维度解读图（水墨太极八卦）")
    import shutil
    import tempfile
    import xml.etree.ElementTree as ET

    import analyze as app
    import dimension_card as dc

    r = app.analyze_person("刘", "宇鹏", wuge.WugeConfig())
    outdir = tempfile.mkdtemp(prefix="card_test_")
    try:
        paths = dc.render_all(r, outdir)
        eq("出图数量（三图 + 合览）", len(paths), 4)
        check("图一存在", os.path.exists(paths["wuge"]))
        check("图二存在", os.path.exists(paths["wuyin"]))
        check("图三存在", os.path.exists(paths["meihua"]))
        check("合览页存在", os.path.exists(paths["index"]))

        svgs = {}
        for k in ("wuge", "wuyin", "meihua"):
            with open(paths[k], encoding="utf-8") as f:
                svgs[k] = f.read()
        # XML 合法性：不能有未转义字符、标签必须闭合
        ok_xml = True
        for k, s in svgs.items():
            try:
                ET.fromstring(s.encode("utf-8"))
            except Exception as e:
                ok_xml = False
                eq(f"{k} SVG 可解析", str(e), "")
        check("三张 SVG 均为合法 XML", ok_xml)

        check("图一含姓名", "刘宇鹏" in svgs["wuge"])
        check("图一含五格数值", all(str(r["wuge"]["grids"][k]["value"]) in svgs["wuge"]
                                    for k in ("tian", "ren", "di", "wai", "zong")))
        check("图一含三才", r["wuge"]["sancai"]["combo"] in svgs["wuge"])
        # 1.3.0：五格图五行色彩设计 + 全图免责声明
        check("图一含五行色标", "五行色标" in svgs["wuge"])
        check("图一五行元素配色齐全",
              all(c in svgs["wuge"] for c in dc.WUXING_COLOR.values()))
        check("图一含五行徽记", svgs["wuge"].count('stroke-width="1.6" opacity="0.95"') >= 5)
        # 1.7.1：五格图人生阶段影响带
        check("图一含人生阶段影响带", "人生階段影響" in svgs["wuge"])
        check("图一阶段带五格齐备",
              all(g in svgs["wuge"] for g in ("天格", "地格", "人格", "外格", "总格")))
        check("图一阶段带注明流派通说", "傳統流派通說" in svgs["wuge"])
        check("图一阶段带含 0–80 岁刻度",
              all(a in svgs["wuge"] for a in ("0", "16", "32", "48", "64", "80")))
        check("图一高度加高 40", 'height="1160"' in svgs["wuge"])
        check("三图均含免责声明",
              all("不具备科学预测效力" in svgs[k] for k in svgs))
        check("图三标注简体起卦", "简体笔画" in svgs["meihua"])
        check("图二含五音名", all(y in svgs["wuyin"] for y in "宫商角徵羽"))
        check("图二含逐字拼音", all(c["pinyin"] in svgs["wuyin"] for c in r["wuyin"]["chars"]))
        # 1.4.1：五音图补齐五音分析结论（音序/相邻关系/音气与格气/判据/完整评论）
        check("图二含音序与五行序", "音序" in svgs["wuyin"] and "五行" in svgs["wuyin"])
        check("图二含相邻关系", all(p["pair"] in svgs["wuyin"] for p in r["wuyin"]["pairs"]))
        check("图二标相邻顺逆", all(p["direction"] in svgs["wuyin"] for p in r["wuyin"]["pairs"]))
        if r["wuyin"].get("resonance"):
            check("图二含音气与格气",
                  "音气与格气" in svgs["wuyin"]
                  and f"协和度 {r['wuyin']['resonance']['harmony']}%" in svgs["wuyin"])
        check("图二含音律判据", "音律判据" in svgs["wuyin"])
        check("图二含完整评论（不再中部截断）", r["wuyin"]["comment"] in svgs["wuyin"])
        check("图三含本卦名", r["meihua"]["cast"]["ben"]["gua"]["name"] in svgs["meihua"])
        check("图三含变卦名", r["meihua"]["cast"]["bian"]["gua"]["name"] in svgs["meihua"])
        check("图三含五行旺衰", "卦中五行旺衰" in svgs["meihua"])
        check("图三含起卦三数",
              f"姓 {r['meihua']['cast']['numbers']['upper']} 画" in svgs["meihua"])

        # 可移植性：不得含本机绝对路径，不得外链资源
        bad_path = ("C:\\", "C:/Users", "/Users/", "/home/")
        check("无本机绝对路径", not any(b in s for s in svgs.values() for b in bad_path))
        check("无外链资源", not any("xlink:href" in s or "http://" in s.replace(
            'xmlns="http://www.w3.org/2000/svg"', "") for s in svgs.values()))

        # 1.3.3：单独打开也必须显图——SVG 补 XML 声明
        check("三张 SVG 均有 XML 声明",
              all(s.lstrip().startswith('<?xml version="1.0" encoding="utf-8"?>')
                  for s in svgs.values()))

        # 1.3.3：合览页自包含（内嵌 data URI），脱离同目录文件仍可显示
        html = open(paths["index"], encoding="utf-8").read()
        eq("合览页内嵌 3 张图", html.count("data:image/svg+xml;base64,"), 3)
        check("合览页无相对图片引用",
              not any(f'src="{n}"' in html for n in
                      ("01_五格.svg", "02_五音.svg", "03_梅花.svg")))
        import base64 as _b64
        ok_embed = True
        for chunk in html.split('src="data:image/svg+xml;base64,')[1:]:
            raw = chunk.split('"')[0]
            try:
                dec = _b64.b64decode(raw).decode("utf-8")
                ET.fromstring(dec.encode("utf-8"))
                if "http://www.w3.org/2000/svg" not in dec:
                    ok_embed = False
            except Exception as e:
                ok_embed = False
                eq("内嵌图可解析", str(e), "")
        check("内嵌图均为合法 SVG", ok_embed)

        # 报告内引用
        cards = app.build_cards(r, outdir)
        txt = app.render_person(r, cards)
        eq("报告内图引 3 条", txt.count("图│"), 4)  # 三图 + 合览
        check("图引指向五格图", "01_五格.svg" in txt)
        check("图引指向五音图", "02_五音.svg" in txt)
        check("图引指向梅花图", "03_梅花.svg" in txt)
        check("图引位于五格段内",
              txt.index("01_五格.svg") < txt.index("三、五音"))
        check("图引位于五音段内",
              txt.index("02_五音.svg") < txt.index("四、梅花易数"))
        txt2 = app.render_person(r, None)
        check("不传 cards 时无图引", "图│" not in txt2)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


# ---------------- 9. 八字（真太阳时） ----------------
def test_bazi():
    print("\n[9] 八字排盘（真太阳时）与五行喜忌")
    import bazi as bz

    # --- 排盘基准（内置硬编码验证值；与公开历书/天文锚点核对）---
    # 北京 1990-05-20 14:30：夏令时还原 → 标准 13:30；经度 −14.4 分 →
    # 真太阳时 ≈13:19（未时，癸未）
    r = bz.analyze_bazi("1990-05-20 14:30", city="北京")
    eq("北京 1990-05-20 14:30 四柱（夏令时还原）",
       (r["pillars"]["year"], r["pillars"]["month"], r["pillars"]["day"],
        r["pillars"]["time"]), ("庚午", "辛巳", "乙酉", "癸未"))
    # 成都 1990-05-20 14:30：夏令时还原 → 13:30；经度 −63.7 分 + EoT →
    # 真太阳时 ≈12:29（午时，壬午）
    r = bz.analyze_bazi("1990-05-20 14:30", city="成都")
    eq("成都 1990-05-20 14:30 四柱（夏令时+经度修正）",
       (r["pillars"]["year"], r["pillars"]["month"], r["pillars"]["day"],
        r["pillars"]["time"]), ("庚午", "辛巳", "乙酉", "壬午"))
    eq("成都例真太阳时", r["true_solar_text"], "1990-05-20 12:29")
    check("成都例触发夏令时还原", r["was_dst"])
    r = bz.analyze_bazi("2000-01-01 12:00")
    eq("2000-01-01 日柱（戊午基准）", r["pillars"]["day"], "戊午")
    r = bz.analyze_bazi("1990-02-04 10:13")
    eq("立春前 10:13 年柱", r["pillars"]["year"], "己巳")
    r = bz.analyze_bazi("1990-02-04 10:15")
    eq("立春后 10:15 年柱", r["pillars"]["year"], "庚午")
    # 立夏 1990-05-06 02:35:26；02:34/02:36 均在夏令时窗口内，还原 −1h
    # 后分别为 01:34/01:36，都早于立夏 → 辰月；03:36 还原为 02:36 才过界
    r = bz.analyze_bazi("1990-05-06 02:34")
    eq("立夏前 02:34 月柱（夏令时还原）", r["pillars"]["month"], "庚辰")
    r = bz.analyze_bazi("1990-05-06 02:36")
    eq("立夏日 02:36+夏令时→辰月", r["pillars"]["month"], "庚辰")
    r = bz.analyze_bazi("1990-05-06 03:36")
    eq("立夏日 03:36+夏令时→巳月", r["pillars"]["month"], "辛巳")
    r = bz.analyze_bazi("1993-05-06 02:36")   # 1993 无夏令时
    eq("非夏令时年 02:36→巳月（癸酉年丁巳）", r["pillars"]["month"], "丁巳")
    # 晚子时（真太阳时 23:00–24:00）日时柱算次日：2024-06-21 23:30 北京 →
    # TST 23:13 → 次日丁巳 + 丁日子时庚子
    r = bz.analyze_bazi("2024-06-21 23:30", city="北京")
    eq("晚子时日柱算次日", r["pillars"]["day"], "丁巳")
    eq("晚子时时柱（五鼠遁）", r["pillars"]["time"], "庚子")
    # 夏令时年份的 23:30 被还原为 22:30 → TST ≈22:29，不进晚子时（亥时）
    r = bz.analyze_bazi("1990-05-20 23:30", city="成都")
    eq("夏令时年 23:30 还原后为亥时", r["pillars"]["time"], "丁亥")
    # 跨零时：1990-05-21 00:30 成都 → 还原为 05-20 23:30 → 与上相同盘面
    r = bz.analyze_bazi("1990-05-21 00:30", city="成都")
    eq("跨零时日柱", r["pillars"]["day"], "乙酉")
    eq("跨零时时柱", r["pillars"]["time"], "丁亥")
    # 日柱 JDN 自算锚点（与内置历法内核一致）
    eq("日柱锚点 1949-10-01 甲子", bz.day_ganzhi(1949, 10, 1), "甲子")
    eq("日柱锚点 2000-01-01 戊午", bz.day_ganzhi(2000, 1, 1), "戊午")
    eq("日柱锚点 2024-01-01 甲子", bz.day_ganzhi(2024, 1, 1), "甲子")
    eq("日柱锚点 1990-05-20 乙酉", bz.day_ganzhi(1990, 5, 20), "乙酉")
    eq("日柱锚点 1990-05-21 丙戌", bz.day_ganzhi(1990, 5, 21), "丙戌")
    # 时柱五鼠遁锚点：甲己日起甲子、乙庚日起丙子…；午时、未时、子时
    eq("时柱锚点 甲日午时=庚午", bz.time_ganzhi("甲子", 11), "庚午")
    eq("时柱锚点 乙日未时=癸未", bz.time_ganzhi("乙酉", 13), "癸未")
    eq("时柱锚点 丁日子时=庚子", bz.time_ganzhi("丁巳", 23), "庚子")

    # --- 均时差 EoT（Meeus 天文算法；公开天文锚点 ±0.2 分钟）---
    for (yy, mm, dd), ref in [((2024, 2, 11), -14.2), ((2024, 5, 14), 3.7),
                              ((2024, 7, 26), -6.4), ((2024, 11, 3), 16.4),
                              ((2024, 4, 15), 0.0), ((2024, 6, 13), 0.0),
                              ((2024, 9, 1), 0.0), ((2024, 12, 25), 0.0)]:
        eot = bz.equation_of_time_minutes(yy, mm, dd)
        check(f"EoT {yy}-{mm:02d}-{dd:02d} ≈ {ref:+.1f} 分", abs(eot - ref) <= 0.2,
              f"{eot:+.2f}")

    # --- 真太阳时：经度修正方向回归（西经更早、东经更晚）---
    _, _, _, h_cd, mi_cd, meta_cd = bz.true_solar_time(1990, 5, 20, 12, 0, 104.07)
    eq("成都正午→真太阳时 10:59", (h_cd, mi_cd), (10, 59))
    eq("成都经度修正量", meta_cd["lon_delta"], -63.7)
    _, _, _, h_wlmq, _, _ = bz.true_solar_time(1990, 5, 20, 12, 0, 87.62)
    eq("乌鲁木齐正午→真太阳时 09 时", h_wlmq, 9)
    _, _, _, h_heb, mi_heb, _ = bz.true_solar_time(1990, 5, 20, 12, 0, 126.64)
    eq("哈尔滨正午→真太阳时 12:30", (h_heb, mi_heb), (12, 30))
    _, _, _, h_bj, _, _ = bz.true_solar_time(1990, 5, 20, 12, 0, 116.41)
    eq("北京正午→真太阳时 11 时", h_bj, 11)
    # 方向回归：西部城市真太阳时必须早于（数值小于）标准时间
    r_cd = bz.analyze_bazi("1990-05-20 14:30", city="成都")
    std_min = 13 * 60 + 30          # 夏令时还原后的标准时间
    tst_min = (int(r_cd["true_solar_text"][11:13]) * 60
               + int(r_cd["true_solar_text"][14:16]))
    check("成都真太阳时早于标准时间（符号回归）", tst_min < std_min,
          f"标准 13:30 → 真太阳时 {r_cd['true_solar_text'][11:16]}")

    # --- 夏令时还原（1986–1991，全国实行；references/08）---
    r = bz.analyze_bazi("1990-05-06 02:40", city="北京")
    eq("夏令时还原 02:40→01:40", r["standard_text"], "1990-05-06 01:40")
    eq("还原后月柱（立夏前）", r["pillars"]["month"], "庚辰")
    r = bz.analyze_bazi("1987-07-15 15:00", city="上海")
    check("1987 窗口内触发还原", r["was_dst"])
    eq("1987 还原后标准 14:00", r["standard_text"], "1987-07-15 14:00")
    check("1992 已停止夏令时不还原",
          not bz.analyze_bazi("1992-07-15 15:00", city="上海")["was_dst"])
    r = bz.analyze_bazi("1990-04-15 02:30", city="北京")
    check("夏令时开始日 02:30（被跳过）按标准", not r["was_dst"])
    r = bz.analyze_bazi("1990-09-16 00:30", city="北京")
    eq("结束日 00:30 仍夏令时→跨日前一日", r["standard_text"], "1990-09-15 23:30")
    check("结束日 00:30 标记还原", r["was_dst"])
    r = bz.analyze_bazi("1990-09-16 01:30", city="北京")
    check("结束日 01:30 重复时刻按标准", not r["was_dst"])

    # --- 时区换算（--tz；境外出生不套中国夏令时）---
    r = bz.analyze_bazi("1990-05-20 14:30", tz_offset=-8)
    eq("UTC-8 换算为标准时间", r["standard_text"], "1990-05-21 06:30")
    eq("UTC-8 例日柱", r["pillars"]["day"], "丙戌")
    eq("UTC-8 例时柱", r["pillars"]["time"], "辛卯")
    check("境外出生不套中国夏令时", not r["was_dst"])
    r = bz.analyze_bazi("1990-05-20 14:30", tz_offset=5.5)
    eq("UTC+5:30 换算为标准时间", r["standard_text"], "1990-05-20 17:00")
    eq("时区解析 +8", bz.parse_tz("+8"), 8.0)
    eq("时区解析 UTC-5", bz.parse_tz("UTC-5"), -5.0)
    eq("时区解析 +5:30", bz.parse_tz("+5:30"), 5.5)
    try:
        bz.parse_tz("bad")
        check("非法时区应抛错", False)
    except bz.BaziError:
        check("非法时区应抛错", True)

    # --- 节气时刻定位（内置历法内核；北京时间，与公开时刻核对）---
    from lunar_python import Lunar, Solar  # noqa: E402
    tbl = Lunar.fromSolar(Solar.fromYmdHms(1990, 5, 6, 12, 0, 0)).getJieQiTable()
    eq("1990 立夏时刻（公开 02:35）", tbl["立夏"].toYmdHms(), "1990-05-06 02:35:26")
    tbl = Lunar.fromSolar(Solar.fromYmdHms(2024, 2, 4, 12, 0, 0)).getJieQiTable()
    eq("2024 立春时刻（公开 16:27）", tbl["立春"].toYmdHms(), "2024-02-04 16:27:07")
    tbl = Lunar.fromSolar(Solar.fromYmdHms(2025, 2, 3, 12, 0, 0)).getJieQiTable()
    eq("2025 立春时刻（公开 22:10）", tbl["立春"].toYmdHms(), "2025-02-03 22:10:28")

    # --- 城市经度与输入校验 ---
    lon, place = bz.longitude_of("成都市")
    eq("城市后缀容错（成都市→成都）", lon, 104.07)
    lon2, _ = bz.longitude_of(None, 104.07)
    eq("longitude 直给", lon2, 104.07)
    _, place_hk = bz.longitude_of("香港")
    eq("香港显示全称", place_hk, "中国香港")
    try:
        bz.longitude_of("月球")
        check("未收录城市应抛错", False)
    except bz.BaziError:
        check("未收录城市应抛错", True)
    try:
        bz.longitude_of(None, 200.0)
        check("超范围经度应抛错", False)
    except bz.BaziError:
        check("超范围经度应抛错", True)
    try:
        bz.parse_birth("1990-13-01 10:00")
        check("非法月份应抛错", False)
    except bz.BaziError:
        check("非法月份应抛错", True)
    try:
        bz.parse_birth("1899-01-01 10:00")
        check("超范围年份应抛错", False)
    except bz.BaziError:
        check("超范围年份应抛错", True)
    r_unknown = bz.analyze_bazi("1990-05-20")
    check("时辰未知时柱留空", r_unknown["pillars"]["time"] is None)
    check("时辰未知日柱不取晚子时修正", r_unknown["pillars"]["day"] == "乙酉")
    check("时辰未知真太阳时显示正午", r_unknown["true_solar_text"].endswith("12:00"))


    # --- 强弱与喜忌（纯函数构造盘面） ---
    def mk(y, mo, d, t):
        return {"year": y, "month": mo, "day": d, "time": t}
    eq("旺相休囚死：木逢寅月", bz.month_state("木", "木"), "旺")
    eq("旺相休囚死：火逢寅月", bz.month_state("火", "木"), "相")
    eq("旺相休囚死：木逢巳月", bz.month_state("木", "火"), "休")
    eq("旺相休囚死：金逢寅月", bz.month_state("金", "木"), "囚")
    eq("旺相休囚死：土逢寅月", bz.month_state("土", "木"), "死")

    weak = mk("庚午", "辛巳", "乙酉", "甲申")
    st = bz.strength_of(weak)
    eq("乙酉日巳月 判身弱", st["label"], "身弱")
    xj = bz.xi_ji(weak)
    eq("身弱用神=印（水）", xj["yongshen"], ["水"])
    eq("身弱喜神=比劫（木）", xj["xishen"], ["木"])
    eq("身弱忌神=最旺克泄（金）", xj["jishen"], ["金"])
    eq("仇神=生金之土", xj["choushen"], ["土"])
    eq("闲神=火", xj["xianshen"], ["火"])
    check("调候触发（巳月水弱）", bool(xj["tiaohou"]))

    strong = mk("甲寅", "丙寅", "甲寅", "甲子")
    st2 = bz.strength_of(strong)
    check("甲寅日寅月 判身强", st2["label"] in ("身强", "中和偏强"), st2["label"])
    xj2 = bz.xi_ji(strong)
    check("身强喜克泄耗（忌印比）",
          set(xj2["like_wx"]) <= {"火", "土", "金", "水"} and "木" in xj2["avoid_wx"],
          f"喜{xj2['like_wx']} 忌{xj2['avoid_wx']}")
    mid = mk("戊子", "辛酉", "戊辰", "丙辰")
    st3 = bz.strength_of(mid)
    check("强弱分可复算", 0 <= st3["ratio"] <= 1, str(st3["ratio"]))

    # --- 与 PyPI lunar-python 交叉验证（按还原后的标准时间比较）---
    try:
        from lunar_python import Lunar, Solar  # type: ignore
    except Exception:
        check("lunar-python 交叉验证（未安装，跳过）", True)
    else:
        import random
        random.seed(20241023)
        bad = []
        for _ in range(300):
            y = random.randint(1901, 2099)
            mo = random.randint(1, 12)
            d = random.randint(1, 28)
            h = random.randint(0, 23)
            mi = random.randint(0, 59)
            rr = bz.analyze_bazi(f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}")
            # 年/月柱：以夏令时还原后的北京标准时间喂内核，比 Exact 系列
            std = rr["standard_text"]
            sy, sm, sd, sh, smi = (int(x) for x in
                                   std.replace("-", " ").replace(":", " ").split())
            s = Lunar.fromSolar(Solar.fromYmdHms(sy, sm, sd, sh, smi, 0))
            exp = (s.getYearInGanZhiExact(), s.getMonthInGanZhiExact())
            got = (rr["pillars"]["year"], rr["pillars"]["month"])
            if exp != got:
                bad.append(("ym", y, mo, d, h, mi, exp, got))
            # 日柱：JDN 自算 vs 内核（按真太阳时日期；晚子时双方均滚次日）
            ts = rr["true_solar"]
            s2 = Lunar.fromSolar(Solar.fromYmdHms(ts["year"], ts["month"], ts["day"],
                                                  ts["hour"], ts["minute"], 0))
            if s2.getDayInGanZhiExact() != rr["pillars"]["day"]:
                bad.append(("day", y, mo, d, h, mi,
                            s2.getDayInGanZhiExact(), rr["pillars"]["day"]))
            # 时柱：五鼠遁自算 vs 内核
            if s2.getTimeInGanZhi() != rr["pillars"]["time"]:
                bad.append(("time", y, mo, d, h, mi,
                            s2.getTimeInGanZhi(), rr["pillars"]["time"]))
        check("lunar-python 300 组年/月/日/时柱交叉验证", not bad,
              f"{len(bad)} 处不一致: {bad[:2]}" if bad else "")

    # --- 集成 ---
    import wuge
    import analyze as app
    r = app.analyze_person("李", "苏翰", wuge.WugeConfig(),
                           birth="1990-05-20 14:30", city="成都")
    check("analyze_person 产出 bazi", bool(r.get("bazi")))
    check("八字不并入姓名综合分", set(r["parts"]) == {"wuge", "wuyin", "meihua"},
          str(sorted(r["parts"])))
    txt = app.render_person(r, None)
    check("报告含八字段", "五、八字原盘" in txt and "五行喜忌" in txt)
    check("综合段顺延为七", "七、综合印象" in txt)
    check("八字段带免责声明", txt.count("不具备科学预测效力") >= 3)
    r2 = app.analyze_person("李", "苏翰", wuge.WugeConfig())
    check("无 birth 时 bazi 为空", r2["bazi"] is None)
    txt2 = app.render_person(r2, None)
    check("无 birth 时给出参数提示", "--birth" in txt2)
    try:
        bz.analyze_bazi("1990-05-20 14:30", city="月球")
        check("城市未收录时报错", False)
    except bz.BaziError:
        check("城市未收录时报错", True)

    # --- 八字维度图 ---
    import shutil
    import xml.etree.ElementTree as ET
    import dimension_card as dc
    outdir = os.path.join(ASSETS, "..", "output", "_test_bazi_card")
    shutil.rmtree(outdir, ignore_errors=True)
    try:
        paths = dc.render_all(r, outdir)
        check("图四存在", os.path.exists(paths["bazi"]))
        svg = open(paths["bazi"], encoding="utf-8").read()
        ET.fromstring(svg.encode("utf-8"))
        check("图四为合法 XML", True)
        for key in ("八字原盤", "真太陽時", "日主", "五行力量", "用神", "忌神",
                    "仇神", "閒神", "原盤評分", "月令", "藏干"):
            check(f"图四含[{key}]", key in svg)
        check("图四四柱干支在图上",
              all(g in svg for g in r["bazi"]["pillars"]["year"]
                  + r["bazi"]["pillars"]["month"] + r["bazi"]["pillars"]["day"]
                  + r["bazi"]["pillars"]["time"]))
        check("图四含免责声明", "不具备科学预测效力" in svg)
        cards = app.build_cards(r, outdir)
        txt3 = app.render_person(r, cards)
        eq("报告内图引 6 条（五图+合览）", txt3.count("图│"), 6)
        check("图引指向八字图", "04_八字.svg" in txt3)
        check("八字图引位于八字段内", "04_八字.svg" in txt3)
        html = open(paths["index"], encoding="utf-8").read()
        check("合览页内嵌图 8 张（五图 + 统合三张简化版）",
              html.count("data:image/svg+xml;base64") == 8,
              str(html.count("data:image/svg+xml;base64")))
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


# ---------------- 10. 跨体系统合 ----------------
def test_synthesis():
    print("\n[10] 跨体系统合（四轴 · 三层权重 · 交叉印证）")
    import shutil
    import tempfile
    import xml.etree.ElementTree as ET

    import analyze as app
    import synthesis as syn

    FRAMEWORK = syn.framework()
    eq("四轴齐备", [a["key"] for a in FRAMEWORK["axes"]],
       ["wuxing", "gangrou", "period", "number"])
    eq("权重三层", len(FRAMEWORK["weights"]["layers"]), 3)
    eq("全权重合计 100", sum(syn.WEIGHTS["full"].values()), 100)
    eq("缺时辰权重合计 100", sum(syn.WEIGHTS["no_time"].values()), 100)
    check("缺时辰时八字降权",
          syn.WEIGHTS["no_time"]["bazi"] < syn.WEIGHTS["full"]["bazi"])
    check("数象轴明示不作吉凶", "不参与评分" in FRAMEWORK["axes"][3]["use"])

    r = app.analyze_person("刘", "雨星", wuge.WugeConfig(gender="male"),
                           birth="1992-09-24 10:15", longitude=104.42)
    sy = r["synthesis"]
    check("统合层已生成", sy is not None)
    if not sy:
        return

    eq("权重取全量模型", sy["weight_mode"], "full")
    eq("权重合计 100", sum(sy["weights"].values()), 100)
    check("四源分与原始分一致",
          all(abs(sy["parts"][k] - r["parts"][k]) < 0.051
              for k in ("wuge", "wuyin", "meihua")))
    check("八字分取自原盘流通度",
          abs(sy["parts"]["bazi"] - r["bazi"]["balance"]["score"]) < 0.051)
    check("合成分区间", 0 <= sy["score"] <= 100, str(sy["score"]))
    check("合成分可复算", abs(sy["score"] - sy["score_base"]) <= 3.0,
          f"{sy['score']} vs {sy['score_base']}")
    check("互证率区间", 0 <= sy["consensus"]["score"] <= 100)
    check("五行共振区间", 0 <= sy["wuxing"]["score"] <= 100)

    for k in ("bazi", "meihua", "wuyin"):
        tot = sum(sy["wuxing"]["vectors"][k].values())
        check(f"{k} 五行向量归一", abs(tot - 1.0) < 0.005, f"{tot}")
    eq("两两共振 3 对", len(sy["wuxing"]["pairs"]), 3)
    check("余弦在 [0,1]",
          all(0 <= p["cos"] <= 1.0001 for p in sy["wuxing"]["pairs"]))
    check("共主五行非空", bool(sy["wuxing"]["consensus_wx"]))
    check("共振分等于两两余弦均值",
          abs(sy["wuxing"]["score"]
              - sum(p["cos"] for p in sy["wuxing"]["pairs"]) / 3 * 100) < 0.6)

    g = sy["gangrou"]
    check("刚柔取值在 [-1,1]", all(-1 <= v <= 1 for v in g["values"].values()))
    check("刚柔主轴由加权求得", abs(g["mean"]) <= 1)
    check("刚柔离散非负", g["spread"] >= 0)
    check("刚柔符号判定合法", g["sign"] in ("同向", "分裂", "居中"))

    st = sy["stages"]
    eq("三段齐备", len(st["points"]), 3)
    for p in st["points"]:
        check(f"{p['label']} 合线居中", min(p["bazi"], p["name"]) - 0.1
              <= p["mix"] <= max(p["bazi"], p["name"]) + 0.1,
              f"{p['bazi']}/{p['name']} → {p['mix']}")
    check("斜率等于末段减首段",
          abs(st["slope"] - (st["points"][2]["mix"] - st["points"][0]["mix"])) < 0.15)
    check("三段时间已知", st["late_estimated"] is False)

    ug = sy["use_god"]
    check("用神契合区间", 0 <= ug["score"] <= 100)
    check("用神判定合法", ug["verdict"] in ("名助命用", "名逆命用", "喜忌两平"))
    check("用神取自八字", ug["yongshen"] == r["bazi"]["xi_ji"]["yongshen"])

    lv = [c["level"] for c in sy["cross"]]
    check("交叉印证非空", len(lv) >= 4, str(len(lv)))
    check("层级取值合法", set(lv) <= {"印证", "张力", "调和"}, str(set(lv)))
    check("印证排在张力之前",
          lv == sorted(lv, key=lambda x: {"印证": 0, "张力": 1, "调和": 2}[x]))
    check("每条均有标题与说明",
          all(c["title"] and len(c["detail"]) >= 8 for c in sy["cross"]))
    check("条目无重复标题",
          len({c["title"] for c in sy["cross"]}) == len(sy["cross"]))
    check("张力与印证计数一致",
          sy["tension"]["印证"] + sy["tension"]["张力"] + sy["tension"]["调和"] == len(lv))
    check("数象呼应带判据",
          all(e["why"] and e["pair"] for e in sy["echoes"]))

    r2 = app.analyze_person("刘", "雨星", wuge.WugeConfig(gender="male"),
                            birth="1992-09-24 10:15", longitude=104.42)
    check("结果确定（同输入同输出）",
          r2["synthesis"]["score"] == sy["score"]
          and r2["synthesis"]["cross"] == sy["cross"])

    txt = app.render_person(r)
    check("报告含统合段", "六、跨体系统合" in txt)
    check("报告含交叉印证", "交叉印证" in txt and "整体趋势" in txt)
    check("报告统合段含免责", txt.count("不具备科学预测效力") >= 6,
          str(txt.count("不具备科学预测效力")))

    no_bz = app.analyze_person("刘", "雨星", wuge.WugeConfig(gender="male"))
    check("无八字不生成统合", no_bz["synthesis"] is None)
    check("无八字报告仍完整", "七、综合印象" in app.render_person(no_bz))

    nt = app.analyze_person("刘", "雨星", wuge.WugeConfig(gender="male"),
                            birth="1992-09-24", longitude=104.42)
    check("时辰未详走降权模型", nt["synthesis"]["weight_mode"] == "no_time")
    check("时辰未详八字权重 22", nt["synthesis"]["weights"]["bazi"] == 22)
    check("时辰未详末段以日支代", nt["synthesis"]["stages"]["late_estimated"] is True)

    # 权重显示随模型：图卡与一层/二层条须按实际权重渲染，不得写死 full 值
    pn = syn.render_synthesis(nt, os.path.join(tempfile.gettempdir(), "syn_no_time_check.svg"))
    svg_nt = open(pn, encoding="utf-8").read()
    check("时辰未详图卡显示降权 22%", ">22%<" in svg_nt, "图卡无 22% 权重")
    check("时辰未详一层条标注 22/78", "一層　體 22 ／ 用 78" in svg_nt)
    check("时辰未详二层条标注 28/26/24",
          "二層　名內 28 ／ 26 ／ 24" in svg_nt)
    check("时辰未详图不显示 full 权重 34",
          ">34%<" not in svg_nt and "體 34" not in svg_nt)
    os.remove(pn)

    outdir = tempfile.mkdtemp(prefix="syn_test_")
    try:
        p = syn.render_synthesis(r, os.path.join(outdir, "05_统合.svg"))
        check("统合图已生成", bool(p) and os.path.exists(p))
        svg = open(p, encoding="utf-8").read()
        check("时辰已知图卡显示 34%", ">34%<" in svg)
        check("时辰已知一层条标注 34/66", "一層　體 34 ／ 用 66" in svg)
        try:
            ET.fromstring(svg.encode("utf-8"))
            ok = True
        except Exception as e:
            ok = False
            eq("统合图 SVG 可解析", str(e), "")
        check("统合图为合法 XML", ok)
        check("统合图尺寸正确", f'width="{syn.SW}" height="{syn.SH}"' in svg)
        check("统合图无占位残留", "None" not in svg and "nan" not in svg)
        for key in ("五維統合圖", "四源分數與權重", "五行共振", "剛柔對照",
                    "三段走勢", "交叉印證", "整體趨勢解讀", "權重邏輯"):
            check(f"统合图含[{key}]", key in svg)
        check("统合图含三源名（五行共振不含五格）",
              all(n in svg for n in ("四柱八字", "梅花易數", "五音納音")))
        check("统合图含四柱干支",
              all(g in svg for g in r["bazi"]["pillars"].values() if g))
        check("统合图含免责声明", "不具备科学预测效力" in svg)
        check("统合图无本机绝对路径",
              not any(b in svg for b in ("C:////", "C:/Users", "/Users/", "/home/")))
        paths = __import__("dimension_card").render_all(r, outdir)
        check("出图清单含统合", "synthesis" in paths)

        # --- 三张简化版（05a/05b/05c）
        for key, stem, must in (
                ("synthesis_lite", "05a_统合速览",
                 ("統合速覽", "統合加權", "四源評分與權重", "一句話")),
                ("synthesis_wuxing", "05b_五行平衡",
                 ("五行平衡", "五行共振度", "八字喜忌", "姓名五行落點")),
                ("synthesis_cross", "05c_交叉印证",
                 ("交叉印證", "三段走勢", "合線斜率", "趨勢解讀"))):
            p2 = getattr(syn, f"render_{key}")(r, os.path.join(outdir, stem + ".svg"))
            check(f"{stem} 已生成", bool(p2) and os.path.exists(p2))
            svg2 = open(p2, encoding="utf-8").read()
            try:
                ET.fromstring(svg2.encode("utf-8"))
                ok2 = True
            except Exception as e:
                ok2 = False
                eq(f"{stem} SVG 可解析", str(e), "")
            check(f"{stem} 为合法 XML", ok2)
            for k in must:
                check(f"{stem} 含[{k}]", k in svg2)
            check(f"{stem} 含名称", (r["input"]["surname"] + r["input"]["given"]) in svg2)
            check(f"{stem} 无占位残留", "None" not in svg2 and "nan" not in svg2)
            check(f"{stem} 含免责声明", "不具备科学预测效力" in svg2)
        paths2 = __import__("dimension_card").render_all(r, outdir)
        check("出图清单含三张简化版",
              all(k in paths2 for k in ("synthesis_lite", "synthesis_wuxing",
                                        "synthesis_cross")))
        # tension 统计键必须与 cross 的 level 用字一致（简体），否则图上恒显 0
        tg = r["synthesis"]["tension"]
        check("tension 计数非全零",
              any(tg.get(k, 0) for k in ("印证", "张力", "调和")),
              str(tg))
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


def test_card_isolation():
    """图片产物归属隔离：连续测算多个名称时不得串用上一轮的图。"""
    print("\n[11] 图片产物归属隔离（连续测算）")
    import subprocess
    import tempfile
    import shutil
    import analyze
    import dimension_card as dc

    cfg = analyze.WugeConfig()

    # --- 1) 同一目录连续测算：缺维度时不得残留上一轮产物
    outdir = tempfile.mkdtemp(prefix="card_iso_")
    try:
        r1 = analyze.analyze_person("刘", "雨星", cfg,
                                    birth="1992-09-24 10:15", longitude=104.42)
        analyze.build_cards(r1, outdir, png=False)
        first = set(os.listdir(outdir))
        check("首个姓名出图含八字", "04_八字.svg" in first)
        check("首个姓名出图含统合", "05_统合.svg" in first)

        r2 = analyze.analyze_person("吕", "锦瑜", cfg)
        analyze.build_cards(r2, outdir, png=False)
        second = set(os.listdir(outdir))
        check("换姓名后不残留上一个姓名的八字图", "04_八字.svg" not in second)
        check("换姓名后不残留上一个姓名的统合图", "05_统合.svg" not in second)
        check("换姓名后仅保留本次产物", len(second) == 4, f"实得 {sorted(second)}")

        svgs = [n for n in second if n.endswith(".svg")]
        leaked = []
        for n in svgs:
            with open(os.path.join(outdir, n), encoding="utf-8") as f:
                if "刘雨星" in f.read():
                    leaked.append(n)
        check("所有 SVG 均不含上一个姓名", not leaked, f"残留 {leaked}")

        cur = []
        for n in svgs:
            with open(os.path.join(outdir, n), encoding="utf-8") as f:
                if "吕锦瑜" in f.read():
                    cur.append(n)
        check("所有 SVG 均写成本次姓名", len(cur) == len(svgs))
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    # --- 2) 归属校验：把结果指向旧姓名的图必须被拦截
    outdir = tempfile.mkdtemp(prefix="card_guard_")
    try:
        old = os.path.join(outdir, "01_五格.svg")
        with open(old, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0"?>'
                    '<svg xmlns="http://www.w3.org/2000/svg">刘雨星</svg>')
        real = dc.render_all
        dc.render_all = lambda r, outdir, prefix="", png=False, clean=True: {"wuge": old}
        try:
            r = analyze.analyze_person("吕", "锦瑜", cfg)
            try:
                analyze.build_cards(r, outdir, png=False)
                check("串图被归属校验拦截", False, "未抛异常")
            except RuntimeError:
                check("串图被归属校验拦截", True)
        finally:
            dc.render_all = real
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    # --- 3) to_png：截图未产出新文件时不得复用旧图
    outdir = tempfile.mkdtemp(prefix="card_png_")
    real_run = subprocess.run
    try:
        svg = os.path.join(outdir, "01_五格.svg")
        with open(svg, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0"?>'
                    '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"/>')
        png = os.path.join(outdir, "01_五格.png")

        for label, rc in (("非零退出", 1), ("零退出但无产物", 0)):
            with open(png, "wb") as f:
                f.write(b"OLD-PNG-FROM-PREVIOUS-NAME")

            def fake_run(*a, **k):
                class P:
                    returncode = rc
                return P()

            subprocess.run = fake_run
            got = dc.to_png(svg, browser="dummy-browser")
            check(f"to_png {label} 时返回空串", got == "")
            check(f"to_png {label} 时清除旧 PNG", not os.path.exists(png))
        subprocess.run = real_run
    finally:
        subprocess.run = real_run
        shutil.rmtree(outdir, ignore_errors=True)

    # --- 4) 机构模式出图与名称归属
    outdir = tempfile.mkdtemp(prefix="card_org_")
    try:
        ro = analyze.analyze_org("康颐源", birth="1990-05-20 14:30", city="成都")
        cards = analyze.build_cards(ro, outdir, png=False)
        names = set(os.listdir(outdir))
        svgs = [n for n in names if n.endswith(".svg")]
        check("机构模式可出图", bool(cards))
        check("机构模式出三张图（五音／梅花／八字）", len(svgs) == 3, f"实得 {sorted(svgs)}")
        ok = True
        for n in svgs:
            with open(os.path.join(outdir, n), encoding="utf-8") as f:
                if "康颐源" not in f.read():
                    ok = False
        check("机构图均写成机构名", ok)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    # --- 5) 清理只动已知产物，不碰用户其他文件
    outdir = tempfile.mkdtemp(prefix="card_clean_")
    try:
        keep = os.path.join(outdir, "我的笔记.txt")
        with open(keep, "w", encoding="utf-8") as f:
            f.write("keep")
        stale = os.path.join(outdir, "04_八字.svg")
        with open(stale, "w", encoding="utf-8") as f:
            f.write("old")
        dc.clean_outputs(outdir)
        check("清理删除历史产物", not os.path.exists(stale))
        check("清理不动无关文件", os.path.exists(keep))
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    # --- 6) 卡片名称来源统一（机构取 input.name，个人取姓+名）
    check("机构模式名称取 input.name",
          analyze.card_name({"input": {"name": "康颐源"}}) == "康颐源")
    check("个人模式名称取姓+名",
          analyze.card_name({"input": {"surname": "吕", "given": "锦瑜"}}) == "吕锦瑜")


def test_docs():
    """文档门禁：版本四方一致、references 索引对齐、FAQ 结构与格式合规。"""
    print("\n[13] 文档一致性与集中 FAQ")
    import doc_check
    r = doc_check.validate()
    for ok, name, detail in r["checks"]:
        check(name, ok, detail)

    faq = doc_check.parse_faq(
        open(os.path.join(os.path.dirname(ASSETS), "references",
                          "10_常见疑问FAQ.md"), encoding="utf-8").read())
    cats, entries = faq["categories"], faq["entries"]
    check("FAQ 分类数 = 6", len(cats) == 6, f"实得 {len(cats)}")
    check("FAQ 条目数 ≥ 40", len(entries) >= 40, f"实得 {len(entries)}")
    check("FAQ 覆盖 A–F 全部六类",
          [c["code"] for c in cats] == ["A", "B", "C", "D", "E", "F"],
          f"实得 {[c['code'] for c in cats]}")
    check("FAQ 每条五段齐全且非空",
          all(set(e["fields"]) == set(doc_check.FAQ_FIELDS)
              and all(e["fields"][k].strip() for k in doc_check.FAQ_FIELDS)
              for e in entries),
          "存在缺项或空值")
    check("FAQ 条目均带标题",
          all(e["title"] and len(e["title"]) >= 4 for e in entries),
          "存在空标题")


def test_flow_fixes():
    """端到端流程验证后的三项修复回归（v1.7.2 流程实测发现）。

    1) --json 模式同样产出维度图（stdout 仍为纯 JSON）；
    2) 有统合层时第七节「综合」直接引用四体统合口径，不与静态加权双口径并列；
    3) 共主五行须被至少两源推举，杜绝各 1 票平局时五行全列的伪共识。
    """
    print("\n[13] 流程修复回归（json 出图 / 综合分口径 / 共主门槛）")
    import subprocess
    import tempfile
    import shutil
    import analyze

    # --- 1) --json + --cards-dir：图必须落盘，stdout 必须仍是合法 JSON
    outdir = tempfile.mkdtemp(prefix="flow_json_")
    try:
        cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "cli.py"),
               "analyze", "--full", "王梓涵", "--birth", "1988-03-12 14:20",
               "--city", "北京", "--cards-dir", outdir, "--json"]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           timeout=180)
        check("json 模式退出码 0", p.returncode == 0, p.stderr[-300:])
        try:
            json.loads(p.stdout)
            ok = True
        except Exception:
            ok = False
        check("json 模式 stdout 为纯 JSON", ok)
        made = set(os.listdir(outdir)) if os.path.isdir(outdir) else set()
        check("json 模式仍产出统合图", "05_统合.svg" in made, f"实得 {sorted(made)}")
        check("json 模式产出三简化版", "05a_统合速览.svg" in made)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)

    # --- 2) 第七节综合分与第六节合成分同源
    cfg = analyze.WugeConfig()
    r = analyze.analyze_person("李", "明轩", cfg, birth="1990-05-20 08:30", city="成都")
    sy = r["synthesis"]
    check("李明轩统合层已生成", sy is not None)
    txt = analyze.render_person(r)
    if sy:
        want = f"综合：{sy['score']:.1f} / 100（{sy['grade']}）"
        check("第七节综合分引用统合口径", want in txt, want)
        check("第七节注明四体统合口径", "四体统合口径" in txt)
    no_bz = analyze.analyze_person("刘", "雨星", cfg)
    txt2 = analyze.render_person(no_bz)
    check("无八字时第七节回退三维加权", "三维静态加权" in txt2)
    check("无八字时第七节无统合口径字样", "四体统合口径" not in txt2)

    # --- 3) 共主门槛：李明轩三源各有所主（原 bug：五行全列）
    if sy:
        cw = sy["wuxing"]["consensus_wx"]
        check("平局各 1 票不算共主", cw == [], f"实得 {cw}")
        check("平局文案为各有所主", "各有所主" in txt)
    # 正向：刘雨星案例确有被多源共同推举的共主（门槛不能一刀切为空）
    r2 = analyze.analyze_person("刘", "雨星", cfg,
                                birth="1992-09-24 10:15", longitude=104.42)
    if r2["synthesis"]:
        check("真实共主仍能入选",
              bool(r2["synthesis"]["wuxing"]["consensus_wx"]))


def main():
    print("=" * 50)
    print("易学姓名学解析 · 回归测试")
    print("=" * 50)
    test_wuge()
    test_wuyin()
    test_meihua()
    test_meaning()
    test_assets()
    test_integration()
    test_errors()
    test_ethics()
    test_cards()
    test_bazi()
    test_synthesis()
    test_card_isolation()
    test_flow_fixes()
    test_docs()

    total = len(PASS) + len(FAIL)
    print("\n" + "=" * 50)
    print(f"结果：{len(PASS)}/{total} 通过" + (f"，{len(FAIL)} 失败" if FAIL else "，全绿"))
    if FAIL:
        print("\n失败项：")
        for n, d in FAIL:
            print(f"  ✗ {n} — {d}")
    print("=" * 50)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
