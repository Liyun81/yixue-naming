#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""易学姓名学解析 · 安装脚本

把整个技能目录复制到用户级技能目录，并做安装后自检。

用法：
    python install.py                     # 安装到 ~/.workbuddy/skills/易学姓名学解析
    python install.py --force             # 已存在时覆盖
    python install.py --target /path/x    # 自定义目标目录
    python install.py --no-check          # 只复制，不跑自检

特性：
    - 跨平台（Windows / macOS / Linux），纯标准库
    - 不写注册表、不改环境变量、不改 PATH，卸载只需删除目录
    - 复制时跳过 __pycache__ / *.pyc / dist / 打包产物
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILL_NAME = "易学姓名学解析"

SKIP_DIRS = {"__pycache__", "dist", ".git", ".idea", ".vscode", ".pytest_cache",
             "output", ".browser"}
# 重装时保留的目录：用户产物不随版本更新被清除
KEEP_DIRS = {"output", ".browser"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
SKIP_SUFFIX = (".pyc", ".pyo", ".zip")


def prefer_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def read_version() -> str:
    path = os.path.join(ROOT, "VERSION")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip() or "unknown"
    return "unknown"


def default_target() -> str:
    return os.path.join(os.path.expanduser("~"), ".workbuddy", "skills", SKILL_NAME)


def preflight() -> list:
    """安装前先确认源目录是完整的，避免装出半个技能。"""
    problems = []
    if not os.path.isfile(os.path.join(ROOT, "SKILL.md")):
        problems.append("缺少 SKILL.md（技能主文档）")
    if not os.path.isfile(os.path.join(ROOT, "skill.json")):
        problems.append("缺少 skill.json（打包清单）")
    if not os.path.isfile(os.path.join(ROOT, "scripts", "cli.py")):
        problems.append("缺少 scripts/cli.py（统一入口）")

    expect = {
        "kangxi_strokes.json": ("chars", 2000),
        "simplified_strokes.json": ("strokes", 2000),
        "pinyin.json": ("chars", 2000),
        "char_meaning.json": ("chars", 400),
        "eighty_one_numbers.json": ("numbers", 81),
        "sancai_config.json": ("configs", 125),
        "gua64.json": ("gua", 64),
    }
    for fname, (key, floor) in expect.items():
        path = os.path.join(ROOT, "assets", fname)
        if not os.path.isfile(path):
            problems.append(f"缺少资产 assets/{fname}")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                node = json.load(f)[key]
            if len(node) < floor:
                problems.append(f"assets/{fname} 条目 {len(node)} < {floor}")
        except Exception as exc:
            problems.append(f"assets/{fname} 无法解析：{exc}")

    if sys.version_info < (3, 9):
        problems.append(f"需要 Python >= 3.9，当前 {sys.version.split()[0]}")
    return problems


def copy_tree(target: str) -> int:
    copied = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, ROOT)
        dest_dir = target if rel == "." else os.path.join(target, rel)
        os.makedirs(dest_dir, exist_ok=True)
        for name in filenames:
            if name in SKIP_FILES or name.endswith(SKIP_SUFFIX):
                continue
            shutil.copy2(os.path.join(dirpath, name), os.path.join(dest_dir, name))
            copied += 1
    return copied


def main() -> int:
    prefer_utf8()
    ap = argparse.ArgumentParser(description="安装「易学姓名学解析」技能")
    ap.add_argument("--target", help="安装目标目录，缺省 ~/.workbuddy/skills/易学姓名学解析")
    ap.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    ap.add_argument("--no-check", action="store_true", help="跳过安装后自检")
    args = ap.parse_args()

    version = read_version()
    target = os.path.abspath(args.target or default_target())

    print("=" * 60)
    print(f"  安装「{SKILL_NAME}」 v{version}")
    print("=" * 60)
    print(f"  源目录   {ROOT}")
    print(f"  目标目录 {target}")
    print(f"  解释器   {sys.executable}")
    print("-" * 60)

    problems = preflight()
    if problems:
        print("  [中止] 源目录不完整：")
        for p in problems:
            print(f"    - {p}")
        print("=" * 60)
        return 1

    if os.path.exists(target) and not args.force:
        print("  [中止] 目标目录已存在。")
        print("  如需覆盖请加 --force，或先用 --target 指定其他位置。")
        print("=" * 60)
        return 1

    if os.path.exists(target) and args.force:
        # 不清空整个目录：output/ 里是用户已生成的报告与图，重装不该连产物一起删
        # （曾因此导致合览页引用不到图片、外部浏览器打开时图裂）。
        for name in os.listdir(target):
            if name in KEEP_DIRS:
                continue
            p = os.path.join(target, name)
            (shutil.rmtree(p) if os.path.isdir(p) else os.remove(p))

    os.makedirs(target, exist_ok=True)
    n = copy_tree(target)
    print(f"  [完成] 已复制 {n} 个文件")

    if args.no_check:
        print("  [跳过] 安装后自检（--no-check）")
        print("=" * 60)
        return 0

    cli = os.path.join(target, "scripts", "cli.py")
    print("  [自检] 运行安装后检查 ...")
    print("-" * 60)
    sys.stdout.flush()  # 子进程直接写 fd，不刷新会把父进程输出挤到后面
    code = subprocess.call([sys.executable, cli, "selfcheck"])
    sys.stdout.flush()
    print("-" * 60)

    if code == 0:
        print("  安装成功。调用方式：")
        print(f"    python \"{cli}\" --version")
        print(f"    python \"{cli}\" analyze --surname 李 --given 明华")
        print(f"    python \"{cli}\" info")
    else:
        print("  [警告] 自检未通过，安装目录已写入但可能不可用。")
        print("         请把上面的 FAIL 项反馈给维护者。")
    print("=" * 60)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
