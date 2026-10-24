# -*- coding: utf-8 -*-
"""文档一致性校验器（文档门禁）。

解决的问题：文档里最容易腐坏的不是理论，而是**同一事实写在四处、改一处忘三处**——
版本号、用例数、自检项数、产物清单、references 索引。FAQ 也是同理：一旦没有固定
格式与编号，新增条目必然各写各的，读者依旧要自己拼。

本模块把「文档不可自证」变成「文档可自证」，只读文件、不写任何东西。校验六类：

1. 必备文件齐全（SKILL/README/CHANGELOG/VERSION/skill.json/FAQ）
2. 版本号四处一致（VERSION / skill.json / SKILL.md / README.md）
3. references 目录与 skill.json、SKILL.md 索引表三方对齐
4. FAQ 结构合规（分类、编号连续性、五段式字段、字数、引用有效性）
5. FAQ 与 SKILL.md 速查表、README 分类名互相对得上
6. 产物清单与用例数声明不落后（cards 含 05_统合；README 与 skill.json 数字一致）

用法：
    python scripts/doc_check.py            # 打印报告，全通过退出码 0
    python scripts/cli.py doccheck         # 同上（薄封装）
    import doc_check; doc_check.validate() # 取结构化结果（tests.py 用）
"""

from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# FAQ 统一答复格式：五段，顺序固定，缺一不可
FAQ_FIELDS = ("一句话", "依据", "怎么做", "别这样", "相关")
FAQ_MIN_CATEGORIES = 6
FAQ_MIN_ENTRIES = 40
FAQ_MAX_ONELINE = 80          # 一句话答案不超过 80 字，超了就不叫「一句话」

RE_CHECK_HEAD = re.compile(r"^####\s+([A-F])(\d{2})\s+·\s+(.+?)\s*$")
RE_CAT_HEAD = re.compile(r"^##\s+([A-F])\s+·\s+(.+?)（\s*(\d+)\s*条\s*）\s*$")
RE_FIELD = re.compile(r"^-\s+\*\*(.+?)\*\*[：:]\s*(.*)$")
RE_VERSION = re.compile(r"(\d+\.\d+\.\d+)")
RE_TABLE_ROW = re.compile(r"^\|\s*([A-F]\d{2})\s*\|")


def _read(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def _strip_md(text: str) -> str:
    """去掉反引号与强调符，便于做字数与空值判断。"""
    return re.sub(r"[`*_]", "", text).strip()


# ---------------------------------------------------------------- 解析

def parse_faq(text: str) -> dict:
    """把 FAQ 文档解析成结构化条目，供格式校验与索引核对。"""
    cats, entries = [], []
    cur_entry = None
    for line in text.splitlines():
        s = line.strip()
        # 任何新章节（## / ###）都终止上一条目的字段收集，
        # 否则文末「维护规则」「本文件不覆盖什么」的加粗列表会被误读成字段。
        if s.startswith("## "):
            cur_entry = None
        m = RE_CAT_HEAD.match(s)
        if m:
            cats.append({"code": m.group(1), "title": m.group(2).strip(),
                         "declared": int(m.group(3))})
            continue
        m = RE_CHECK_HEAD.match(s)
        if m:
            cur_entry = {"code": m.group(1), "seq": m.group(2),
                         "id": m.group(1) + m.group(2),
                         "title": m.group(3).strip(),
                         "fields": {}, "qid": len(entries)}
            entries.append(cur_entry)
            continue
        if cur_entry is not None:
            fm = RE_FIELD.match(s)
            if fm:
                cur_entry["fields"].setdefault(fm.group(1).strip(), fm.group(2).strip())
    return {"categories": cats, "entries": entries}


# ---------------------------------------------------------------- 校验

def validate() -> dict:
    """执行全部校验，返回 {"checks": [(ok, name, detail)], "stats": {...}}。"""
    checks: list = []

    def add(ok, name, detail=""):
        checks.append((bool(ok), name, detail))

    # 1) 必备文件
    required = ["SKILL.md", "README.md", "CHANGELOG.md", "VERSION", "skill.json",
                "references/10_常见疑问FAQ.md", "scripts/doc_check.py"]
    missing = [p for p in required if not os.path.isfile(os.path.join(ROOT, p))]
    add(not missing, "必备文档齐全",
        "缺少：" + "、".join(missing) if missing else f"{len(required)} 项均在")

    # 2) 版本号四处一致
    version = _read("VERSION").strip()
    manifest = json.loads(_read("skill.json"))
    skill_md, readme = _read("SKILL.md"), _read("README.md")
    m_skill = re.search(r"\*\*版本\*\*\s*([0-9.]+)", skill_md)
    m_readme = re.search(r"当前版本\s*\*\*([0-9.]+)\*\*", readme)
    found = {
        "VERSION": version,
        "skill.json": str(manifest.get("version", "")),
        "SKILL.md": m_skill.group(1) if m_skill else "(未找到)",
        "README.md": m_readme.group(1) if m_readme else "(未找到)",
    }
    uniq = set(found.values())
    add(len(uniq) == 1 and version != "(未找到)", "版本号四处一致",
        f"不一致：{found}" if len(uniq) != 1 else f"{version}")

    # 3) references 三方对齐
    ref_dir = os.path.join(ROOT, "references")
    on_disk = sorted(f for f in os.listdir(ref_dir) if f.endswith(".md"))
    in_manifest = {os.path.basename(r.get("path", ""))
                   for r in manifest.get("references", [])}
    not_in_manifest = [f for f in on_disk if f not in in_manifest]
    add(not not_in_manifest, "references 全部登记于 skill.json",
        "未登记：" + "、".join(not_in_manifest) if not_in_manifest
        else f"{len(on_disk)} 篇")

    not_indexed = [f for f in on_disk if f not in skill_md]
    add(not not_indexed, "references 全部见于 SKILL.md 索引",
        "未索引：" + "、".join(not_indexed) if not_indexed else f"{len(on_disk)} 篇")

    ghost = sorted(f for f in in_manifest if f and f not in on_disk)
    add(not ghost, "skill.json 无幽灵引用",
        "记录存在但文件缺失：" + "、".join(ghost) if ghost else "无")

    # 4) FAQ 结构
    faq_text = _read("references/10_常见疑问FAQ.md")
    faq = parse_faq(faq_text)
    cats, entries = faq["categories"], faq["entries"]
    add(len(cats) >= FAQ_MIN_CATEGORIES, "FAQ 分类数达标",
        f"{len(cats)} 类（要求 ≥{FAQ_MIN_CATEGORIES}）")
    add(len(entries) >= FAQ_MIN_ENTRIES, "FAQ 条目数达标",
        f"{len(entries)} 条（要求 ≥{FAQ_MIN_ENTRIES}）")

    ids = [e["id"] for e in entries]
    add(len(ids) == len(set(ids)), "FAQ 编号唯一",
        "重复：" + "、".join(sorted({i for i in ids if ids.count(i) > 1})) if
        len(ids) != len(set(ids)) else f"{len(ids)} 个编号")

    declared_ok = all(
        sum(1 for e in entries if e["code"] == c["code"]) == c["declared"] for c in cats)
    add(declared_ok, "FAQ 分类声明条数与实际一致",
        "；".join(f"{c['code']}={c['declared']}"
                 f"/{sum(1 for e in entries if e['code'] == c['code'])}" for c in cats))

    seq_bad = []
    for c in cats:
        seqs = [int(e["seq"]) for e in entries if e["code"] == c["code"]]
        if seqs != list(range(1, len(seqs) + 1)):
            seq_bad.append(c["code"])
    add(not seq_bad, "FAQ 各类内编号连续", "异常分类：" + "、".join(seq_bad) if seq_bad else "A–F 连续")

    field_bad, order_bad, long_bad, empty_bad = [], [], [], []
    for e in entries:
        keys = list(e["fields"].keys())
        if set(keys) != set(FAQ_FIELDS):
            field_bad.append(f"{e['id']}（缺 {'、'.join(k for k in FAQ_FIELDS if k not in e['fields'])}"
                             f"／多 {'、'.join(k for k in keys if k not in FAQ_FIELDS)}）")
            continue
        if tuple(keys) != FAQ_FIELDS:
            order_bad.append(e["id"])
        if len(_strip_md(e["fields"]["一句话"])) > FAQ_MAX_ONELINE:
            long_bad.append(e["id"])
        for k in FAQ_FIELDS:
            if len(_strip_md(e["fields"][k])) < 2:
                empty_bad.append(f"{e['id']}.{k}")
    add(not field_bad, "FAQ 五段式字段齐全", "；".join(field_bad) if field_bad else f"{len(entries)} 条齐备")
    add(not order_bad, "FAQ 字段顺序统一",
        "；".join(order_bad) if order_bad else "／".join(FAQ_FIELDS))
    add(not long_bad, f"FAQ 一句话答案 ≤{FAQ_MAX_ONELINE} 字",
        "超额：" + "、".join(long_bad) if long_bad else "全部达标")
    add(not empty_bad, "FAQ 无空字段", "空值：" + "、".join(empty_bad) if empty_bad else "无")

    trace_bad = [e["id"] for e in entries
                 if not any(t in e["fields"].get("依据", "")
                            for t in ("references/", "scripts/", "§"))]
    add(not trace_bad, "FAQ 依据均可回溯",
        "缺来源：" + "、".join(trace_bad) if trace_bad else "全部注明文件或章节")

    ref_bad = []
    for e in entries:
        for q in re.findall(r"[A-F]\d{2}", e["fields"].get("相关", "")):
            if q not in ids:
                ref_bad.append(f"{e['id']}→{q}")
    add(not ref_bad, "FAQ 相关引用有效",
        "指向不存在：" + "、".join(ref_bad) if ref_bad else "全部可解析")

    # 5) FAQ 与 SKILL/README 对齐
    table_ids = [m.group(1) for m in (RE_TABLE_ROW.match(l.strip())
                                      for l in skill_md.splitlines()) if m]
    add(bool(table_ids), "SKILL.md 含 FAQ 速查表", f"{len(table_ids)} 行索引")
    bad_ids = [i for i in table_ids if i not in ids]
    add(not bad_ids, "速查表编号均存在于 FAQ",
        "悬空：" + "、".join(bad_ids) if bad_ids else "全部命中")
    add("references/10_常见疑问FAQ.md" in skill_md, "SKILL.md 指向完整 FAQ", "已在文档索引中登记")

    cat_names = [c["title"] for c in cats]
    readme_miss = [n for n in cat_names if n not in readme]
    add(not readme_miss, "README 分类名与 FAQ 一致",
        "未出现：" + "、".join(readme_miss) if readme_miss else f"{len(cat_names)} 类一致")

    # 6) 产物清单与数字声明
    cards = manifest.get("entry", {}).get("outputs", {}).get("cards", [])
    add("05_统合.svg" in cards, "skill.json 产物清单含统合图",
        "缺 05_统合.svg" if "05_统合.svg" not in cards else f"{len(cards)} 张")
    text_desc = str(manifest.get("entry", {}).get("outputs", {}).get("text", ""))
    add("七段" in text_desc, "skill.json 报告段数表述为七段", text_desc[:40])

    m_cases = re.search(r"回归测试（\s*(\d+)\s*项", readme)
    declared_cases = readme_cases = None
    if m_cases:
        readme_cases = int(m_cases.group(1))
    declared_cases = manifest.get("checks", {}).get("regression_cases")
    same = readme_cases is not None and declared_cases == readme_cases
    add(same, "用例数 README 与 skill.json 一致",
        f"README={readme_cases} skill.json={declared_cases}" if not same else f"{declared_cases} 项")

    return {"checks": checks, "stats": {
        "version": version,
        "categories": len(cats),
        "entries": len(entries),
        "references": len(on_disk),
        "cases": declared_cases,
    }}


def main() -> int:
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    r = validate()
    checks, stats = r["checks"], r["stats"]
    print("=" * 58)
    print("  易学姓名学解析 · 文档一致性校验（doccheck）")
    print("=" * 58)
    for ok, name, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<22} {detail}")
    passed = sum(1 for ok, _, _ in checks if ok)
    print("-" * 58)
    print(f"  {passed}/{len(checks)} 通过　版本 {stats['version']}　"
          f"FAQ {stats['entries']} 条 / {stats['categories']} 类　"
          f"references {stats['references']} 篇　用例 {stats['cases']}")
    print("  结论：" + ("文档与实现一致。" if passed == len(checks)
                      else "文档存在腐坏项，请修文档或同步版本号。"))
    print("=" * 58)
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
