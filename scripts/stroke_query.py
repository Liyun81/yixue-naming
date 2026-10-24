#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stroke_query.py —— 康熙笔画查询与维护 CLI

用法：
    python stroke_query.py 李              # 查单字
    python stroke_query.py 李明华           # 查整名（逐字）
    python stroke_query.py add 玥 9         # 增补/覆盖一个字
    python stroke_query.py add-batch words.txt   # 批量，每行「字 笔画」
    python stroke_query.py stats            # 数据统计
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from wuge import StrokeQuery, WugeError, _Data, _is_hanzi, RADICAL_FALLBACK, wuxing_of  # noqa: E402


def cmd_query(arg: str) -> int:
    q = StrokeQuery()
    missing = []
    print(f"《康熙笔画查询》{arg}")
    for ch in arg:
        if not _is_hanzi(ch):
            print(f"  {ch}  —— 非汉字，五格法不适用")
            continue
        v = q.get(ch)
        if v is None:
            est = q.estimate(ch)
            if est:
                print(f"  {ch}  —— 未收录；部件估算 {est['strokes']} 画（低置信：{est['method']}）")
            else:
                print(f"  {ch}  —— 未收录，请用 add 子命令补充")
            missing.append(ch)
        else:
            print(f"  {ch}  —— {v} 画（五行属{wuxing_of(v)}）")
    if missing:
        print(f"\n提示：缺字 {''.join(missing)}。可执行 `python stroke_query.py add 字 笔画` 补充。")
        return 1
    return 0


def cmd_add(ch: str, strokes: str) -> int:
    StrokeQuery().add(ch, int(strokes))
    print(f"[OK] 已写入：{ch} = {strokes} 画")
    return 0


def cmd_add_batch(path: str) -> int:
    if not os.path.exists(path):
        print(f"[FAIL] 文件不存在：{path}")
        return 1
    q = StrokeQuery()
    ok = fail = 0
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 2 or not parts[1].isdigit():
                print(f"  第{lineno}行格式错误，应为「字 笔画」：{line}")
                fail += 1
                continue
            try:
                q.add(parts[0], int(parts[1]))
                ok += 1
            except WugeError as e:
                print(f"  第{lineno}行失败：{e.message}")
                fail += 1
    print(f"[OK] 成功 {ok} 条，失败 {fail} 条")
    return 0 if fail == 0 else 1


def cmd_stats() -> int:
    _Data.load()
    chars = _Data.chars
    print("《康熙笔画数据统计》")
    print(f"  收录字数：{len(chars)}")
    if chars:
        print(f"  笔画区间：{min(chars.values())} – {max(chars.values())} 画")
    dist = {}
    for v in chars.values():
        dist[v] = dist.get(v, 0) + 1
    print("  分布（画:字数为抽样前 12 档）：")
    shown = 0
    for k in sorted(dist):
        if shown >= 12:
            break
        print(f"    {k:>2} 画：{dist[k]:>4} 字")
        shown += 1
    print(f"  部件回退部首：{len(RADICAL_FALLBACK)} 个")
    print(f"  81 数理条目：{len(_Data.numbers)}")
    print(f"  三才配置条目：{len(_Data.sancai)}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 0
    cmd = argv[0]
    try:
        if cmd == "add" and len(argv) == 3:
            return cmd_add(argv[1], argv[2])
        if cmd == "add-batch" and len(argv) == 2:
            return cmd_add_batch(argv[1])
        if cmd == "stats":
            return cmd_stats()
        if cmd in ("-h", "--help"):
            print(__doc__)
            return 0
        return cmd_query("".join(argv))
    except WugeError as e:
        print(f"[ERROR:{e.code}] {e.message}")
        return 2
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
