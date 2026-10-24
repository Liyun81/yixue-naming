#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""易学姓名学解析 · 统一命令行入口

用法：
    python scripts/cli.py <command> [options]

命令：
    analyze     姓名 / 起名筛选 / 机构名解析（完整参数见 cli.py analyze --help）
    stroke      康熙笔画查询、增补、覆盖率统计
    selfcheck   安装自检（资产完整性 + 关键算例 + 文档一致性）
    doccheck    文档一致性校验（版本 / references 索引 / FAQ 格式 / 产物清单）
    test        运行全部回归测试
    info        版本与数据概况

设计说明：
    本文件是**薄封装**，不重复实现任何业务逻辑，只负责把参数原样转发给
    analyze.py / stroke_query.py / tests.py，保证 CLI 与直接调用脚本的行为
    完全一致。因此 --help、退出码、错误码都与底层模块相同。
"""

from __future__ import annotations

import json
import os
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPTS_DIR)

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------- 基础设施

def _prefer_utf8() -> None:
    """Windows 控制台默认 cp936，中文报告可能报编码错。能改则改，改不了不报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _read_version() -> str:
    version_file = os.path.join(ROOT_DIR, "VERSION")
    if os.path.isfile(version_file):
        with open(version_file, encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    manifest = os.path.join(ROOT_DIR, "skill.json")
    if os.path.isfile(manifest):
        try:
            with open(manifest, encoding="utf-8") as f:
                return str(json.load(f).get("version", "0.0.0"))
        except Exception:
            pass
    return "0.0.0"


def _call(module_name: str, argv: list) -> int:
    """把 argv 交给目标模块的 main()，并正确传递退出码。"""
    module = __import__(module_name)
    sys.argv = [f"{module_name}.py"] + argv
    try:
        code = module.main()
    except SystemExit as exc:  # argparse 的 --help 会走这里
        code = exc.code
    return 0 if code is None else int(code)


# ---------------------------------------------------------------- 子命令

def cmd_analyze(argv: list) -> int:
    return _call("analyze", argv)


def cmd_stroke(argv: list) -> int:
    return _call("stroke_query", argv)


def cmd_test(argv: list) -> int:
    return _call("tests", argv)


def cmd_doccheck(argv: list) -> int:
    """文档一致性校验：只读文件，不生成任何产物。"""
    return _call("doc_check", argv)


def cmd_info(argv: list) -> int:
    import platform
    def count(path: str, *keys: str):
        full = os.path.join(ROOT_DIR, "assets", path)
        try:
            with open(full, encoding="utf-8") as f:
                node = json.load(f)
            for k in keys:
                node = node[k]
            return len(node)
        except Exception:
            return -1

    print("=" * 56)
    print("  易学姓名学解析")
    print("=" * 56)
    print(f"  版本        {_read_version()}")
    print(f"  技能根目录  {ROOT_DIR}")
    print(f"  Python      {platform.python_version()} ({platform.system()})")
    print(f"  解释器      {sys.executable}")
    print("-" * 56)
    print("  数据资产")
    print(f"    康熙笔画库      {count('kangxi_strokes.json', 'chars'):>6} 字")
    print(f"    简体笔画库      {count('simplified_strokes.json', 'strokes'):>6} 字"
          f"（繁转简 {count('simplified_strokes.json', 't2s')} 对）")
    print(f"    读音库          {count('pinyin.json', 'chars'):>6} 字")
    print(f"    字义库          {count('char_meaning.json', 'chars'):>6} 字")
    print(f"    八十一数理      {count('eighty_one_numbers.json', 'numbers'):>6} 条")
    print(f"    三才配置        {count('sancai_config.json', 'configs'):>6} 条")
    print(f"    六十四卦        {count('gua64.json', 'gua'):>6} 卦")
    print("-" * 56)
    print("  内置历法内核   scripts/vendor/lunar_python（lunar-python 1.4.8, MIT）")
    print("  八字排盘       真太阳时口径（references/08），--birth/--city 启用")
    print("  运行时依赖     无（仅 Python 标准库 + 内置内核）")
    print("  自检        python scripts/cli.py selfcheck")
    print("  完整参数    python scripts/cli.py analyze --help")
    print("=" * 56)
    return 0


def cmd_selfcheck(argv: list) -> int:
    """安装自检：不依赖任何外部状态，只验证本目录能否独立工作。"""
    results: list = []

    def check(name: str, fn):
        try:
            detail = fn()
            results.append((True, name, detail or "OK"))
        except Exception as exc:
            results.append((False, name, f"{type(exc).__name__}: {exc}"))

    # 1) Python 版本
    def _python():
        if sys.version_info < (3, 9):
            raise RuntimeError(f"需要 Python >= 3.9，当前 {sys.version.split()[0]}")
        return f"Python {sys.version.split()[0]}"

    # 2) 资产完整性
    EXPECT = {
        "kangxi_strokes.json": (("chars",), 2000),
        "simplified_strokes.json": (("strokes",), 2000),
        "pinyin.json": (("chars",), 2000),
        "char_meaning.json": (("chars",), 400),
        "eighty_one_numbers.json": (("numbers",), 81),
        "sancai_config.json": (("configs",), 125),
        "gua64.json": (("gua",), 64),
    }

    def _assets():
        summary = []
        for fname, (keys, floor) in EXPECT.items():
            path = os.path.join(ROOT_DIR, "assets", fname)
            if not os.path.isfile(path):
                raise FileNotFoundError(f"缺少资产 {fname}")
            with open(path, encoding="utf-8") as f:
                node = json.load(f)
            for k in keys:
                node = node[k]
            if len(node) < floor:
                raise ValueError(f"{fname} 条目 {len(node)} < 期望 {floor}")
            summary.append(f"{fname}:{len(node)}")
        return " ".join(summary)

    # 3) 五格算例（四种结构，取自规则文档附录）
    def _wuge():
        import wuge
        cases = {
            ("王", "五"): (5, 8, 5, 2, 8),
            ("李", "明华"): (8, 15, 22, 15, 29),
            ("诸葛", "亮"): (31, 24, 10, 17, 40),
            ("欧阳", "明华"): (32, 25, 22, 29, 54),
        }
        for (s, g), expect in cases.items():
            r = wuge.analyze(s, g)
            got = tuple(r["grids"][k]["value"] for k in ("tian", "ren", "di", "wai", "zong"))
            if got != expect:
                raise AssertionError(f"{s}{g} 得 {got}，应为 {expect}")
        return "4 种结构全部吻合"

    # 4) 五音（含姓氏异读）
    def _wuyin():
        import wuyin
        r = wuyin.analyze_wuyin(list("单雄信"), 1)
        first = r["chars"][0]
        if first["wuyin"] != "商":
            raise AssertionError(f"「单」作姓应为商音，实得 {first['wuyin']}")
        return f"单(姓)={first['pinyin']}→{first['wuyin']}　音律 {r['score']}"

    # 5) 梅花易数（1.3.0 起卦一律用现代简体字笔画）
    def _meihua():
        import meihua
        strokes = meihua.strokes_of_name("李明华")
        if strokes != [7, 8, 6]:
            raise AssertionError(f"李明华简体笔画应为 [7, 8, 6]，实得 {strokes}")
        r = meihua.analyze_name(strokes[:1], strokes[1:])
        name = r["cast"]["ben"]["gua"]["name"]
        if name != "山水蒙":
            raise AssertionError(f"李明华本卦应为山水蒙，实得 {name}")
        if r.get("stroke_standard") != "现代简体字笔画（非康熙繁体笔画）":
            raise AssertionError("起卦口径未标注为现代简体字笔画")
        t = meihua.strokes_of_name("劉")
        if t != [6]:
            raise AssertionError(f"繁体「劉」应映射为简体「刘」6 画，实得 {t}")
        return f"简体起卦 本卦 {name}　体 {r['cast']['ti']['gua']}{r['cast']['ti']['wuxing']}　评分 {r['score']}"

    # 6) 八字排盘（真太阳时；含时区/夏令时还原、经度修正、Meeus 均时差）
    def _bazi():
        import bazi
        # 成都 1990-05-20 14:30：夏令时还原 −1h → 标准 13:30；
        # 经度修正 −63.7 分 + EoT +3.6 分 → 真太阳时 ≈12:29（午时，壬午）
        r = bazi.analyze_bazi("1990-05-20 14:30", city="成都")
        got = tuple(r["pillars"][k] for k in ("year", "month", "day", "time"))
        if got != ("庚午", "辛巳", "乙酉", "壬午"):
            raise AssertionError(f"成都 1990-05-20 14:30 应得 庚午辛巳乙酉壬午，实得 {got}")
        if not r["was_dst"] or not r["true_solar"]["hour"] == 12:
            raise AssertionError("成都例应触发夏令时还原且真太阳时进入午时")
        # 同一时刻北京（116.41°E，同处夏令时）→ 标准 13:30，经度 −14.4 → ≈13:19（未时）
        rb = bazi.analyze_bazi("1990-05-20 14:30", city="北京")
        if rb["pillars"]["time"] != "癸未":
            raise AssertionError(f"北京同时刻应得未时癸未，实得 {rb['pillars']['time']}")
        # 关闭夏令时还原时应回到未时（14:30 −63.7+3.6 ≈13:29）
        rn = bazi.analyze_bazi("1990-05-20 14:30", city="成都", use_dst=False)
        if rn["pillars"]["time"] != "癸未":
            raise AssertionError(f"--no-dst 成都例应得癸未，实得 {rn['pillars']['time']}")
        r2 = bazi.analyze_bazi("1990-02-04 10:13")
        if r2["pillars"]["year"] != "己巳":
            raise AssertionError("立春交接前年柱应为己巳")
        r3 = bazi.analyze_bazi("1990-05-06 02:34")
        if r3["pillars"]["month"] != "庚辰":
            raise AssertionError("立夏交接前月柱应为庚辰")
        return (f"成都例 {''.join(got)}（夏令时还原）　日主{r['strength']['day_wuxing']}"
                f"{r['strength']['label']}　真太阳时 {r['true_solar_text']}")

    # 7) 跨体系统合（四轴投影 + 三层权重 + 交叉印证）
    def _synthesis():
        import analyze as app
        import wuge
        r = app.analyze_person("刘", "雨星", wuge.WugeConfig(gender="male"),
                               birth="1992-09-24 10:15", longitude=104.42)
        sy = r.get("synthesis")
        if not sy:
            raise AssertionError("四维齐备时统合层应生成")
        if sum(sy["weights"].values()) != 100:
            raise AssertionError(f"权重合计应为 100，实得 {sum(sy['weights'].values())}")
        if len(sy["wuxing"]["pairs"]) != 3:
            raise AssertionError("五行共振应含 3 对两两比较")
        if not sy["cross"] or not sy["trend"]["lines"]:
            raise AssertionError("交叉印证或趋势解读为空")
        return (f"合成 {sy['score']}（{sy['grade']}）　共振 {sy['wuxing']['score']:.0f}%"
                f"　印证 {sy['tension'].get('印证', 0)}"
                f"/{sy['tension'].get('张力', 0)}/{sy['tension'].get('调和', 0)}")

    # 8) 文档一致性（版本四方一致 / references 索引 / FAQ 格式 / 产物清单）
    def _docs():
        import doc_check
        r = doc_check.validate()
        bad = [c for c in r["checks"] if not c[0]]
        if bad:
            raise AssertionError(
                "；".join(f"{n}（{d}）" for _, n, d in bad)[:180])
        return f"{len(r['checks'])} 项一致　FAQ {r['stats']['entries']} 条"

    check("Python 版本", _python)
    check("数据资产", _assets)
    check("五格计算", _wuge)
    check("五音平仄", _wuyin)
    check("梅花易数", _meihua)
    check("八字排盘", _bazi)
    check("跨系统合", _synthesis)
    check("文档一致性", _docs)

    print("=" * 56)
    print("  易学姓名学解析 · 安装自检")
    print("=" * 56)
    for ok, name, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<8} {detail}")
    passed = sum(1 for ok, _, _ in results if ok)
    print("-" * 56)
    print(f"  {passed}/{len(results)} 通过")
    if passed == len(results):
        print("  结论：可直接使用。")
    else:
        print("  结论：环境不完整，请检查上方 FAIL 项。")
    print("=" * 56)
    return 0 if passed == len(results) else 1


# ---------------------------------------------------------------- 分发

COMMANDS = {
    "analyze": ("解析姓名 / 起名筛选 / 机构名", cmd_analyze),
    "stroke": ("康熙笔画查询 / 增补 / 统计", cmd_stroke),
    "selfcheck": ("安装自检（资产 + 关键算例 + 文档）", cmd_selfcheck),
    "doctor": ("selfcheck 的别名", cmd_selfcheck),
    "doccheck": ("文档一致性校验（版本 / 索引 / FAQ）", cmd_doccheck),
    "test": ("运行全部回归测试", cmd_test),
    "info": ("版本与数据概况", cmd_info),
}


def print_help() -> None:
    print(__doc__.strip())
    print("\n当前版本：" + _read_version())
    print("\n提示：analyze 子命令的完整选项请运行  python scripts/cli.py analyze --help")


def main() -> int:
    _prefer_utf8()
    argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help", "help"):
        print_help()
        return 0
    if argv[0] in ("-V", "--version", "version"):
        print(_read_version())
        return 0

    name, rest = argv[0], argv[1:]
    entry = COMMANDS.get(name)
    if entry is None:
        print(f"[未知命令] {name}\n", file=sys.stderr)
        print_help()
        return 2
    return entry[1](rest)


if __name__ == "__main__":
    raise SystemExit(main())
