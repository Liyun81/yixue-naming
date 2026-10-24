#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""维度解读图 · 水墨道家太极八卦风格 SVG 生成器。

设计原则
--------
1. **零第三方依赖**：只用标准库拼 SVG 字符串，任何 Python 3.9+ 环境可直接出图。
2. **图随文走**：一图对一节（五格 / 五音 / 梅花），数据全部取自 analyze()
   的结构化结果，不在绘图层二次推断，避免图文不符。
3. **版式取法卷轴**：宣纸底、墨线双框、楷体竖题、朱砂印记、飞白圆盘。
4. **判据可见**：图上只放已有结论（数理、吉凶、五行、旺衰），不新增判断。

用法
----
    from dimension_card import render_all
    paths = render_all(result, "output/刘宇鹏")
"""

from __future__ import annotations

import math
import os
import re

# ---------------------------------------------------------------- 版面常量

W, H = 820, 1120
WUGE_H = H + 40  # 五格图：底部多一条人生阶段影响带，单独加高

PAPER = "#F3EBDC"      # 宣纸
PAPER_D = "#E7DCC4"    # 纸背
INK = "#1B1815"        # 焦墨
INK_MID = "#443B30"    # 中墨
INK_SOFT = "#6F6353"   # 淡墨
CINNABAR = "#A63226"   # 朱砂（吉）
SEAL = "#9C2B22"       # 印泥
OCHRE = "#8A6A3C"      # 赭石（半吉）
ASH = "#5A5A56"        # 灰墨（凶）

FONT = "'KaiTi','STKaiti','Kaiti SC','SimSun','Songti SC',serif"
FONT_SONG = "'SimSun','Songti SC','SimHei',serif"

GRID_LABEL = {
    "tian": ("天格", "祖运"),
    "ren": ("人格", "主运"),
    "di": ("地格", "前运"),
    "wai": ("外格", "副运"),
    "zong": ("总格", "后运"),
}

# 五格主导的人生阶段（岁）——传统流派通说，仅作阶段示意，不参与评分
STAGE_SPANS = {
    "tian": (0, 16, "祖运"),
    "di": (0, 32, "前运"),
    "ren": (16, 48, "主运"),
    "wai": (32, 64, "副运"),
    "zong": (48, 80, "后运"),
}
STAGE_MAX = 80  # 横轴上限（岁）

WUXING_COLOR = {
    "木": "#2F7A4D",   # 青绿
    "火": "#C0392B",   # 赤红
    "土": "#C08A2E",   # 赭黄
    "金": "#8E97A3",   # 银灰（金尚白，纸上以银灰示金）
    "水": "#2E5E8C",   # 深蓝
}
WUXING_ORDER = ("木", "火", "土", "金", "水")
DISCLAIMER_NOTE = "※ 本图仅供审美与文化参考，不具备科学预测效力"

STRUCT_LABEL = {
    "SS_GG": "单姓单名", "SS_GD": "单姓双名",
    "DS_SG": "复姓单名", "DS_GD": "复姓双名",
    "EXTENDED": "多字姓",
}

LUCK_COLOR = {
    "大吉": CINNABAR, "吉": "#8E4A2C", "半吉": OCHRE,
    "凶": ASH, "大凶": "#3A3A38",
}

# 先天八卦：自正上顺时针 乾巽坎艮坤震离兑
BAGUA_ORDER = [
    ("乾", [1, 1, 1]), ("巽", [0, 1, 1]), ("坎", [0, 1, 0]), ("艮", [0, 0, 1]),
    ("坤", [0, 0, 0]), ("震", [1, 0, 0]), ("离", [1, 0, 1]), ("兑", [1, 1, 0]),
]

WUYIN_INFO = {
    "宫": ("土", "喉音", "中"),
    "商": ("金", "齿音", "西"),
    "角": ("木", "牙音", "东"),
    "徵": ("火", "舌音", "南"),
    "羽": ("水", "唇音", "北"),
}

BAGUA_LINES = {n: l for n, l in BAGUA_ORDER}


def yao_of(gua: dict) -> list:
    """由上下卦名拼六爻（自下而上）。变卦结果只带 gua 不带 yao，此处补齐。"""
    lower = BAGUA_LINES.get(gua.get("lower"), [1, 1, 1])
    upper = BAGUA_LINES.get(gua.get("upper"), [1, 1, 1])
    return list(lower) + list(upper)


# ---------------------------------------------------------------- 基础工具

def esc(s) -> str:
    """XML 转义。"""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def wrap_cn(text: str, width: int, max_lines: int = 0) -> list:
    """中文折行：优先在标点处断开。不做两端对齐，保持题跋的自然断句。"""
    text = re.sub(r"\s+", "", str(text or ""))
    if not text:
        return []
    out, cur, last_break = [], "", -1
    for ch in text:
        cur += ch
        if ch in "，。；：、！？）」』":
            last_break = len(cur)
        if len(cur) >= width:
            if last_break > width * 0.55:
                out.append(cur[:last_break])
                cur = cur[last_break:]
            else:
                out.append(cur)
                cur = ""
            last_break = -1
    if cur:
        if out and len(cur) <= 2 and cur[0] in "，。；：、！？）」』":
            out[-1] += cur
        else:
            out.append(cur)
    if max_lines and len(out) > max_lines:
        out = out[:max_lines]
        out[-1] = out[-1].rstrip("，。；：、") + "……"
    return out


def htext(x, y, s, size=16, fill=INK, anchor="start", spacing=0,
          font=FONT, weight="normal", opacity=1.0) -> str:
    sp = f' letter-spacing="{spacing}"' if spacing else ""
    op = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}"'
            f' fill="{fill}" text-anchor="{anchor}" font-weight="{weight}"{sp}{op}'
            f'>{esc(s)}</text>')


def vtext(x, y, s, size=30, fill=INK, gap=None, font=FONT, weight="normal",
          opacity=1.0, anchor="middle") -> str:
    """竖排：逐字定位，避免各渲染器 writing-mode 差异。"""
    gap = gap if gap is not None else size * 1.16
    parts = []
    for i, ch in enumerate(s):
        parts.append(f'<text x="{x:.1f}" y="{y + i * gap:.1f}" font-family="{font}"'
                     f' font-size="{size}" fill="{fill}" text-anchor="{anchor}"'
                     f' font-weight="{weight}" opacity="{opacity}">{esc(ch)}</text>')
    return "".join(parts)


# ---------------------------------------------------------------- 纸与框

def _defs() -> str:
    return f'''<defs>
  <linearGradient id="paperG" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{PAPER}"/>
    <stop offset="45%" stop-color="#F6EFE1"/>
    <stop offset="100%" stop-color="{PAPER_D}"/>
  </linearGradient>
  <radialGradient id="vig" cx="50%" cy="46%" r="78%">
    <stop offset="55%" stop-color="#7A6A4E" stop-opacity="0"/>
    <stop offset="100%" stop-color="#7A6A4E" stop-opacity="0.20"/>
  </radialGradient>
  <radialGradient id="washG" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="{INK}" stop-opacity="0.16"/>
    <stop offset="70%" stop-color="{INK}" stop-opacity="0.05"/>
    <stop offset="100%" stop-color="{INK}" stop-opacity="0"/>
  </radialGradient>
  <filter id="rough" x="-8%" y="-8%" width="116%" height="116%">
    <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="3" seed="11" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="2.0"
      xChannelSelector="R" yChannelSelector="G"/>
  </filter>
  <filter id="roughSoft" x="-12%" y="-12%" width="124%" height="124%">
    <feTurbulence type="fractalNoise" baseFrequency="0.028" numOctaves="4" seed="5" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="3.4"
      xChannelSelector="R" yChannelSelector="G"/>
  </filter>
  <filter id="wash" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="26"/>
  </filter>
  <filter id="soft" x="-25%" y="-25%" width="150%" height="150%">
    <feGaussianBlur stdDeviation="1.5"/>
  </filter>
  <filter id="grain">
    <feTurbulence type="fractalNoise" baseFrequency="0.82" numOctaves="2" seed="7"/>
    <feColorMatrix type="saturate" values="0"/>
  </filter>
  <radialGradient id="haloG" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#C9A227" stop-opacity="0.13"/>
    <stop offset="62%" stop-color="#C9A227" stop-opacity="0.07"/>
    <stop offset="100%" stop-color="#C9A227" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="sunG" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#E3B93C" stop-opacity="0.24"/>
    <stop offset="55%" stop-color="#C9A227" stop-opacity="0.11"/>
    <stop offset="100%" stop-color="#C9A227" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="moonG" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#8FA3B8" stop-opacity="0.16"/>
    <stop offset="60%" stop-color="#8FA3B8" stop-opacity="0.06"/>
    <stop offset="100%" stop-color="#8FA3B8" stop-opacity="0"/>
  </radialGradient>
</defs>'''


def _paper_bg(w=W, h=H) -> str:
    return (f'<rect width="{w}" height="{h}" fill="url(#paperG)"/>'
            f'<rect width="{w}" height="{h}" filter="url(#grain)" opacity="0.075"/>'
            f'<rect width="{w}" height="{h}" fill="url(#vig)"/>')


def _wash(cx, cy, rx, ry, op=0.30) -> str:
    """墨晕：三团错位的柔边椭圆，模拟宣纸上的淡墨扩散（避免完美椭圆的数码感）。"""
    blobs = [(0.00, 0.00, 1.00, 1.00), (-0.16, 0.10, 0.78, 0.86),
             (0.14, -0.08, 0.62, 0.72)]
    out = []
    for dx, dy, kx, ky in blobs:
        out.append(f'<ellipse cx="{cx + rx * dx:.0f}" cy="{cy + ry * dy:.0f}"'
                   f' rx="{rx * kx:.0f}" ry="{ry * ky:.0f}" fill="{INK}"'
                   f' opacity="{op * (1.0 if kx == 1 else 0.75):.3f}"'
                   f' filter="url(#wash)"/>')
    return "".join(out)


def _frame(w=W, h=H) -> str:
    m1, m2 = 30, 38
    g = [f'<g filter="url(#rough)">',
         f'<rect x="{m1}" y="{m1}" width="{w - 2*m1}" height="{h - 2*m1}" fill="none"'
         f' stroke="{INK}" stroke-width="2.6" opacity="0.82"/>',
         f'<rect x="{m2}" y="{m2}" width="{w - 2*m2}" height="{h - 2*m2}" fill="none"'
         f' stroke="{INK}" stroke-width="0.9" opacity="0.5"/>',
         '</g>']
    # 四角短脚，取古籍鱼尾意
    for (x, y, dx, dy) in ((m2, m2, 1, 1), (W - m2, m2, -1, 1),
                           (m2, H - m2, 1, -1), (W - m2, H - m2, -1, -1)):
        g.append(f'<path d="M {x} {y + dy*16} L {x} {y} L {x + dx*16} {y}"'
                 f' fill="none" stroke="{INK}" stroke-width="3.4" opacity="0.75"/>')
    return "".join(g)


def _cloud(cx, cy, s, op=0.085) -> str:
    """饱满祥云：一笔轮廓（三道圆隆 + 平底），roughSoft 出水墨毛边。"""
    d = (f'M {cx - s*0.95:.0f} {cy + s*0.16:.0f} '
         f'C {cx - s*0.98:.0f} {cy - s*0.30:.0f} {cx - s*0.34:.0f} {cy - s*0.46:.0f} '
         f'{cx - s*0.04:.0f} {cy - s*0.26:.0f} '
         f'C {cx + s*0.00:.0f} {cy - s*0.58:.0f} {cx + s*0.46:.0f} {cy - s*0.52:.0f} '
         f'{cx + s*0.52:.0f} {cy - s*0.20:.0f} '
         f'C {cx + s*0.94:.0f} {cy - s*0.10:.0f} {cx + s*1.00:.0f} {cy + s*0.22:.0f} '
         f'{cx + s*0.62:.0f} {cy + s*0.24:.0f} '
         f'C {cx + s*0.30:.0f} {cy + s*0.44:.0f} {cx - s*0.62:.0f} {cy + s*0.46:.0f} '
         f'{cx - s*0.95:.0f} {cy + s*0.16:.0f} Z')
    return f'<path d="{d}" fill="{INK}" opacity="{op}" filter="url(#roughSoft)"/>'


def _deity_bg(w=W, h=H) -> str:
    """「元始天尊」像素水墨模板层：背光八卦环 · 日月轮 · 祥云 · 远山 · 莲花座。

    取参考图五项核心视觉：头后金色大光环（双环 + 放射纹 + 居中太极 + 八卦均布）、
    右上日轮左上月轮、两侧饱满祥云、双层远山、底部大莲座。一律按画布比例定位、
    中低透明度，内容浮于其上如天尊浮于背光前，只增氛围不减可读性。
    """
    m = min(w, h)
    o = []

    # ① 背光大光环：天尊头光意，全幅中央，内容浮其上
    hx, hy, hr = w * 0.50, h * 0.42, m * 0.44
    o.append(f'<circle cx="{hx:.0f}" cy="{hy:.0f}" r="{hr*1.16:.0f}" fill="url(#haloG)"/>')
    o.append(f'<circle cx="{hx:.0f}" cy="{hy:.0f}" r="{hr:.0f}" fill="none"'
             f' stroke="{INK}" stroke-width="1.8" opacity="0.15"/>')
    o.append(f'<circle cx="{hx:.0f}" cy="{hy:.0f}" r="{hr*0.93:.0f}" fill="none"'
             f' stroke="#B8860B" stroke-width="1.1" opacity="0.16"/>')
    for k in range(24):  # 放射纹
        a = math.radians(k * 15)
        r0, r1 = hr * 0.95, hr * (1.13 if k % 2 == 0 else 1.06)
        o.append(f'<line x1="{hx + math.cos(a)*r0:.1f}" y1="{hy + math.sin(a)*r0:.1f}"'
                 f' x2="{hx + math.cos(a)*r1:.1f}" y2="{hy + math.sin(a)*r1:.1f}"'
                 f' stroke="#B8860B" stroke-width="{1.4 if k % 2 == 0 else 0.9}"'
                 f' opacity="{0.11 if k % 2 == 0 else 0.07}" stroke-linecap="round"/>')
    o.append(taiji(hx, hy, m * 0.062, ink=INK, paper=PAPER, opacity=0.11))
    for i, (_gname, lines) in enumerate(BAGUA_ORDER):
        a = math.radians(-90 + i * 45)
        tx = hx + math.cos(a) * hr * 0.965
        ty = hy + math.sin(a) * hr * 0.965
        o.append(trigram(tx, ty, lines, w=m * 0.072, th=3.0, gap=m * 0.017,
                         ink=INK, op=0.13))

    # ② 日轮（右上·暖金大光晕）与月轮（左上·淡青柔光）
    sx, sy, sr = w * 0.885, h * 0.145, m * 0.058
    o.append(f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{sr*2.6:.0f}" fill="url(#sunG)"/>')
    for k in range(12):
        a = math.radians(k * 30)
        o.append(f'<line x1="{sx + math.cos(a)*sr*1.22:.1f}"'
                 f' y1="{sy + math.sin(a)*sr*1.22:.1f}"'
                 f' x2="{sx + math.cos(a)*sr*1.62:.1f}"'
                 f' y2="{sy + math.sin(a)*sr*1.62:.1f}"'
                 f' stroke="#B8860B" stroke-width="2.0" opacity="0.14"'
                 f' stroke-linecap="round"/>')
    o.append(f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{sr:.0f}" fill="#C9A227"'
             f' opacity="0.17" filter="url(#soft)"/>')
    mx, my, mr = w * 0.115, h * 0.125, m * 0.046
    o.append(f'<circle cx="{mx:.0f}" cy="{my:.0f}" r="{mr*2.5:.0f}" fill="url(#moonG)"/>')
    o.append(f'<circle cx="{mx:.0f}" cy="{my:.0f}" r="{mr:.0f}" fill="#7E8FA0"'
             f' opacity="0.13" filter="url(#soft)"/>')

    # ③ 祥云六朵：两侧自下而上渐小，环伺如侍立
    clouds = [(w * 0.16, h * 0.24, m * 0.085, 0.09),
              (w * 0.84, h * 0.21, m * 0.080, 0.085),
              (w * 0.10, h * 0.47, m * 0.062, 0.075),
              (w * 0.90, h * 0.44, m * 0.058, 0.07),
              (w * 0.14, h * 0.70, m * 0.072, 0.085),
              (w * 0.86, h * 0.68, m * 0.068, 0.08)]
    for cx, cy, s, op in clouds:
        o.append(_cloud(cx, cy, s, op))

    # ④ 远山两层：远淡近深，左右各一双
    for flip in (0, 1):
        px = (lambda x: w - x) if flip else (lambda x: x)
        far = (f'M {px(20):.0f} {h*0.92:.0f} '
               f'C {px(w*0.05):.0f} {h*0.80:.0f} {px(w*0.09):.0f} {h*0.64:.0f} '
               f'{px(w*0.17):.0f} {h*0.74:.0f} '
               f'C {px(w*0.21):.0f} {h*0.68:.0f} {px(w*0.24):.0f} {h*0.66:.0f} '
               f'{px(w*0.31):.0f} {h*0.78:.0f} '
               f'L {px(w*0.31):.0f} {h*0.92:.0f} Z')
        o.append(f'<path d="{far}" fill="{INK}" opacity="0.05"/>')
        near = (f'M {px(14):.0f} {h*0.96:.0f} '
                f'C {px(w*0.06):.0f} {h*0.88:.0f} {px(w*0.10):.0f} {h*0.76:.0f} '
                f'{px(w*0.18):.0f} {h*0.84:.0f} '
                f'C {px(w*0.22):.0f} {h*0.80:.0f} {px(w*0.25):.0f} {h*0.79:.0f} '
                f'{px(w*0.30):.0f} {h*0.88:.0f} '
                f'L {px(w*0.30):.0f} {h*0.96:.0f} Z')
        o.append(f'<path d="{near}" fill="{INK}" opacity="0.075"/>')

    # ⑤ 大莲座：四层花瓣 + 金莲心 + 水下波纹
    fx, fy, pr = w * 0.50, h * 0.965, m * 0.150
    for ring in range(4):
        n = 8 - ring
        rr = pr * (1 - ring * 0.19)
        pw = rr * 0.28
        for i in range(n):
            a = -90 + i * (360.0 / n) + ring * 9
            o.append(f'<ellipse cx="{fx:.0f}" cy="{fy - rr*0.40:.0f}"'
                     f' rx="{pw:.0f}" ry="{rr*0.50:.0f}" fill="{INK}"'
                     f' opacity="{0.055 + 0.012*(3-ring):.3f}"'
                     f' stroke="#2F7A4D" stroke-opacity="{0.12 - ring*0.02:.3f}"'
                     f' stroke-width="0.9"'
                     f' transform="rotate({a:.0f} {fx:.0f} {fy:.0f})"/>')
    o.append(f'<circle cx="{fx:.0f}" cy="{fy:.0f}" r="{pr*0.20:.0f}" fill="#C9A227"'
             f' opacity="0.14"/>')
    o.append(f'<circle cx="{fx:.0f}" cy="{fy:.0f}" r="{pr*0.10:.0f}" fill="#C9A227"'
             f' opacity="0.20"/>')
    for i, wl in enumerate((m * 0.34, m * 0.26, m * 0.18)):  # 水波纹三叠
        wy = fy + pr * (0.30 + i * 0.16)
        o.append(f'<path d="M {fx - wl:.0f} {wy:.0f} q {wl*0.25:.0f} {-m*0.012:.0f}'
                 f' {wl*0.5:.0f} 0 q {wl*0.25:.0f} {-m*0.012:.0f} {wl*0.5:.0f} 0"'
                 f' fill="none" stroke="#2E5E8C" stroke-width="1.0"'
                 f' opacity="{0.14 - i*0.03:.2f}" stroke-linecap="round"/>')
    return "".join(o)


def _stage_band(x0, x1, y) -> str:
    """五格人生阶段影响带：各格主导的年龄段区间条。

    条长＝该格主导的人生阶段跨度（传统流派通说，图上注明、不参与评分），
    一眼看清「哪格管哪段」；人格为主运，朱砂加粗并标「主」。
    整条带衬半透明纸色，压住背景莲座墨韵，保证刻度与数值清晰。
    """
    out = []
    label_w, note_w = 50, 58
    bx0, bx1 = x0 + label_w, x1 - note_w
    band_h = 5 * 12 + 22
    out.append(f'<rect x="{x0 - 6}" y="{y - 12}" width="{x1 - x0 + 12}" height="{band_h}"'
               f' rx="3" fill="{PAPER}" opacity="0.66" stroke="{INK}"'
               f' stroke-width="0.8" stroke-opacity="0.16"/>')
    out.append(htext(x0, y, "人生階段影響 · 五格各管哪段", 12, INK_SOFT, spacing=1.5))
    out.append(htext(x1, y, "傳統流派通說，非評分依據", 9, INK_SOFT, "end", spacing=1))
    ty = y + 15
    for age in range(0, STAGE_MAX + 1, 16):
        gx = bx0 + (bx1 - bx0) * age / STAGE_MAX
        out.append(f'<line x1="{gx:.1f}" y1="{ty - 2}" x2="{gx:.1f}" y2="{ty + 5*12 + 6}"'
                   f' stroke="{INK}" stroke-width="0.5" opacity="0.13"/>')
        out.append(htext(gx, ty - 5, str(age), 9, INK_SOFT, "middle"))
    out.append(htext(bx1 + 4, ty - 5, "歲", 9, INK_SOFT, "start"))
    for i, key in enumerate(("tian", "di", "ren", "wai", "zong")):
        ry = ty + 3 + i * 12
        a, b, _note = STAGE_SPANS[key]
        sx = bx0 + (bx1 - bx0) * a / STAGE_MAX
        ex = bx0 + (bx1 - bx0) * b / STAGE_MAX
        main = (key == "ren")
        col = CINNABAR if main else INK_MID
        hgt = 9 if main else 7
        label, _role = GRID_LABEL[key]
        out.append(htext(x0, ry + hgt - 1, label, 11.5, col, "start",
                         weight="bold" if main else "normal", spacing=1))
        out.append(f'<rect x="{sx:.1f}" y="{ry}" width="{ex - sx:.1f}" height="{hgt}"'
                   f' rx="{hgt/2}" fill="{col}" opacity="{0.88 if main else 0.42}"/>')
        if main:
            out.append(htext((sx + ex) / 2, ry + hgt - 1.5, "主", 8, PAPER, "middle"))
        out.append(htext(ex + 5, ry + hgt - 1, f"{a}–{b} 岁", 9.5, INK_SOFT, "start"))
    return "".join(out)


def _title(main, sub, name="") -> str:
    out = [htext(74, 84, main, 30, INK, spacing=7, weight="bold")]
    out.append(htext(76, 108, sub, 12.5, INK_SOFT, spacing=2.5))
    out.append(f'<path d="M 74 122 Q 150 118 224 123 T 352 121" fill="none"'
               f' stroke="{INK}" stroke-width="2.2" opacity="0.55" filter="url(#rough)"/>')
    if name:
        out.append(htext(W - 74, 88, name, 25, INK, anchor="end", spacing=4))
    return "".join(out)


def _seal(cx, cy, chars="易學參攷", size=58, rot=-4.0) -> str:
    """白文印：朱地白字，两字一行。"""
    n = len(chars)
    cols = 2 if n > 2 else 1
    rows = (n + cols - 1) // cols
    fs = size / max(rows, cols) * 0.72
    out = [f'<g transform="rotate({rot} {cx} {cy})">',
           f'<rect x="{cx - size/2:.1f}" y="{cy - size/2:.1f}" width="{size}" height="{size}"'
           f' rx="3" fill="{SEAL}" opacity="0.88" filter="url(#roughSoft)"/>',
           f'<rect x="{cx - size/2 + 4:.1f}" y="{cy - size/2 + 4:.1f}"'
           f' width="{size - 8}" height="{size - 8}" fill="none"'
           f' stroke="{PAPER}" stroke-width="1" opacity="0.55"/>']
    for i, ch in enumerate(chars):
        r, c = divmod(i, cols)
        x = cx - size / 2 + size / cols * (c + 0.5)
        y = cy - size / 2 + size / rows * (r + 0.62)
        out.append(htext(x, y, ch, fs, PAPER, anchor="middle", font=FONT))
    out.append("</g>")
    return "".join(out)


# ---------------------------------------------------------------- 卦象构件

def taiji(cx, cy, r, rot=0.0, ink=INK, paper=PAPER, opacity=1.0, sw=None) -> str:
    k = r / 2
    sw = sw if sw is not None else max(1.0, r * 0.028)
    d = (f"M {cx:.2f} {cy - r:.2f} A {r} {r} 0 0 1 {cx:.2f} {cy + r:.2f} "
         f"A {k} {k} 0 0 1 {cx:.2f} {cy:.2f} A {k} {k} 0 0 0 {cx:.2f} {cy - r:.2f} Z")
    return (f'<g transform="rotate({rot} {cx} {cy})" opacity="{opacity}">'
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{paper}"'
            f' stroke="{ink}" stroke-width="{sw:.2f}"/>'
            f'<path d="{d}" fill="{ink}"/>'
            f'<circle cx="{cx:.2f}" cy="{cy - k / 2:.2f}" r="{r / 6:.2f}" fill="{paper}"/>'
            f'<circle cx="{cx:.2f}" cy="{cy + k / 2:.2f}" r="{r / 6:.2f}" fill="{ink}"/>'
            f'</g>')


def trigram(cx, cy, lines, w=36, th=5, gap=8, ink=INK, op=0.34) -> str:
    """三爻：lines 自下而上，1 阳 0 阴。"""
    total = 3 * th + 2 * gap
    out = [f'<g opacity="{op}" fill="{ink}">']
    for i in range(3):
        y = cy - total / 2 + i * (th + gap)
        if lines[2 - i]:
            out.append(f'<rect x="{cx - w/2:.1f}" y="{y:.1f}" width="{w}"'
                       f' height="{th}" rx="{th/2:.1f}"/>')
        else:
            seg = (w - gap * 1.5) / 2
            out.append(f'<rect x="{cx - w/2:.1f}" y="{y:.1f}" width="{seg:.1f}"'
                       f' height="{th}" rx="{th/2:.1f}"/>')
            out.append(f'<rect x="{cx + w/2 - seg:.1f}" y="{y:.1f}" width="{seg:.1f}"'
                       f' height="{th}" rx="{th/2:.1f}"/>')
    out.append("</g>")
    return "".join(out)


def bagua_ring(cx, cy, r, w=34, th=5, gap=8, op=0.26) -> str:
    out = []
    for i, (_, lines) in enumerate(BAGUA_ORDER):
        a = i * 45 * 3.141592653589793 / 180
        x = cx + r * math.sin(a)
        y = cy - r * math.cos(a)
        out.append(trigram(x, y, lines, w, th, gap, INK, op))
    return "".join(out)


def hexagram(cx, y0, yao, bar_w=200, th=13, gap=15, ink=INK, moving=None,
             opacity=1.0) -> str:
    """六爻卦画：自下而上，y0 为初爻中线。粗笔触模拟墨条。"""
    out = [f'<g opacity="{opacity}" filter="url(#rough)">']
    half = bar_w / 2
    for i in range(6):
        y = y0 - i * (th + gap)  # 自下往上
        c = CINNABAR if (moving is not None and moving == i + 1) else ink
        if yao[i]:
            out.append(f'<rect x="{cx - half:.1f}" y="{y - th/2:.1f}" width="{bar_w}"'
                       f' height="{th}" rx="{th*0.32:.1f}" fill="{c}"/>')
        else:
            seg = bar_w * 0.42
            out.append(f'<rect x="{cx - half:.1f}" y="{y - th/2:.1f}" width="{seg:.1f}"'
                       f' height="{th}" rx="{th*0.32:.1f}" fill="{c}"/>')
            out.append(f'<rect x="{cx + half - seg:.1f}" y="{y - th/2:.1f}" width="{seg:.1f}"'
                       f' height="{th}" rx="{th*0.32:.1f}" fill="{c}"/>')
    out.append("</g>")
    return "".join(out)


# ---------------------------------------------------------------- 部件组合

def node(cx, cy, r, label, value, sub="", accent=INK, sub2="") -> str:
    """圆牌：格名 / 数值 / 数理 / 吉凶。字号随半径收缩，避免贴边。"""
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PAPER}" opacity="0.95"'
           f' filter="url(#rough)" stroke="{INK}" stroke-width="1.6"/>',
           f'<circle cx="{cx}" cy="{cy}" r="{r - 5}" fill="none" stroke="{accent}"'
           f' stroke-width="0.9" opacity="0.42"/>']
    if label:
        out.append(htext(cx, cy - r * 0.50, label, min(r * 0.27, 19), INK_SOFT,
                         "middle", spacing=1))
    out.append(htext(cx, cy + r * 0.12, str(value), min(r * 0.58, 56), accent,
                     "middle", font=FONT_SONG, weight="bold"))
    if sub:
        out.append(htext(cx, cy + r * 0.56, sub, min(r * 0.215, 13), INK_MID, "middle"))
    if sub2:
        out.append(htext(cx, cy + r * 0.79, sub2, min(r * 0.195, 12), accent, "middle"))
    return "".join(out)


def _rule(x1, x2, y, op=0.45) -> str:
    return (f'<path d="M {x1} {y} Q {(x1+x2)/2} {y-2} {x2} {y}" fill="none"'
            f' stroke="{INK}" stroke-width="1.1" opacity="{op}" filter="url(#rough)"/>')


def _disclaimer(y: float, anchor: str = "middle", x: float = W / 2) -> str:
    """图内免责声明（所有维度解读图一律附带）。"""
    return htext(x, y, DISCLAIMER_NOTE, 10.5, INK_SOFT, anchor, spacing=1)


def _wuxing_legend(x: float, y: float) -> str:
    """五行色标：五个彩点 + 字，确保五行色彩与元素的对应一眼可辨。"""
    out = [htext(x, y + 4, "五行色标", 10.5, INK_SOFT, spacing=2)]
    for i, wx in enumerate(WUXING_ORDER):
        cx = x + 78 + i * 56
        c = WUXING_COLOR[wx]
        out.append(f'<circle cx="{cx}" cy="{y}" r="9" fill="{c}" opacity="0.92"'
                   f' stroke="{INK}" stroke-width="0.8" filter="url(#rough)"/>')
        out.append(htext(cx, y + 3.8, wx, 10.5, PAPER, "middle"))
        out.append(htext(cx + 15, y + 3.8, wx, 10, INK_SOFT, "start"))
    return "".join(out)


def _element_badge(cx, cy, wx: str, r: float = 12.5) -> str:
    """五行徽记：元素色实心圆 + 反白字，贴在圆牌右上角。"""
    c = WUXING_COLOR.get(wx, INK)
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{c}"'
            f' stroke="{PAPER}" stroke-width="1.6" opacity="0.95"'
            f' filter="url(#roughSoft)"/>'
            + htext(cx, cy + r * 0.42, wx, r * 1.25, PAPER, "middle"))


def _element_ring(cx, cy, r, wx: str) -> str:
    """元素色环 + 内晕：让五行色彩在圆牌上直接可见。"""
    c = WUXING_COLOR.get(wx, INK)
    return (f'<circle cx="{cx}" cy="{cy}" r="{r - 2}" fill="none"'
            f' stroke="{c}" stroke-width="3.4" opacity="0.88"'
            f' filter="url(#roughSoft)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r - 7}" fill="{c}" opacity="0.10"/>')


def _score_line(x, y, label, value, grade, color=CINNABAR) -> str:
    out = [htext(x, y, label, 13.5, INK_SOFT, spacing=2),
           htext(x, y + 42, str(value), 38, color, font=FONT_SONG, weight="bold"),
           htext(x + 82, y + 42, "/ 100", 11.5, INK_SOFT)]
    if grade:
        out.append(htext(x, y + 62, grade, 14, color, spacing=2))
    return "".join(out)


def _prose(x, y, text, width=38, size=14.5, gap=23, max_lines=3,
           color=INK_MID) -> str:
    lines = wrap_cn(text, width, max_lines)
    return "".join(htext(x, y + i * gap, line, size, color)
                   for i, line in enumerate(lines))


# ---------------------------------------------------------------- 图一：五格

def render_wuge(r, path) -> str:
    w = r["wuge"]
    g = w["grids"]
    sc = w["sancai"]
    inp = r["input"]
    name = _display_name(r)
    structure = STRUCT_LABEL.get(inp.get("structure"), "")
    WH = WUGE_H

    cx, cy = 470, 512
    parts = [_paper_bg(W, WH), _defs(), _deity_bg(W, WH), _frame(W, WH),
             _title("五格剖象", "TIAN · REN · DI · WAI · ZONG", name)]

    # 墨晕与太极水印
    parts.append(_wash(cx - 30, cy + 10, 252, 236, 0.085))
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="220" fill="none" stroke="{INK}"'
                 f' stroke-width="0.9" opacity="0.22" stroke-dasharray="1 6"/>')
    parts.append(bagua_ring(cx, cy, 300, 32, 5, 8, 0.28))

    # 三才轴（天—人—地）
    parts.append(f'<path d="M {cx} {cy - 284} L {cx} {cy + 284}" fill="none"'
                 f' stroke="{INK}" stroke-width="1" stroke-dasharray="2 7"'
                 f' opacity="0.42"/>')
    # 副运/后运横轴
    parts.append(f'<path d="M {cx - 284} {cy} L {cx + 284} {cy}" fill="none"'
                 f' stroke="{INK}" stroke-width="0.9" stroke-dasharray="2 8"'
                 f' opacity="0.28"/>')

    pos = {"tian": (cx, cy - 220), "di": (cx, cy + 220),
           "wai": (cx - 220, cy), "zong": (cx + 220, cy)}
    radii = {"tian": 68, "di": 68, "wai": 64, "zong": 64, "ren": 90}

    for k, (px, py) in pos.items():
        d = g[k]
        label, role = GRID_LABEL[k]
        color = LUCK_COLOR.get(d["luck"], INK)
        wx_color = WUXING_COLOR.get(d["wuxing"], INK)
        sub = (f"{d['number']}·" if d["number"] != d["value"] else "") + d["title"][:5]
        parts.append(htext(px, py - radii[k] - 14, role, 11, INK_SOFT, "middle", spacing=3))
        parts.append(node(px, py, radii[k], label, d["value"], sub, color, d["luck"]))
        # 五行元素色环 + 内晕：五行色彩直接铺在格位上
        parts.append(_element_ring(px, py, radii[k], d["wuxing"]))
        # 五行徽记（右上角彩章）
        parts.append(_element_badge(px + radii[k] * 0.74, py - radii[k] * 0.74,
                                    d["wuxing"]))
        # 五行小字
        parts.append(htext(px + radii[k] + 3, py + 4, d["wuxing"],
                           14, wx_color, "start", font=FONT_SONG, weight="bold"))

    # 人格：主运，居中压太极
    d = g["ren"]
    parts.append(taiji(cx, cy, 122, rot=12, ink=INK, opacity=0.085, sw=1.0))
    parts.append(htext(cx, cy - radii["ren"] - 16, "主运", 11.5, INK_SOFT, "middle", spacing=3))
    parts.append(node(cx, cy, radii["ren"], "人格", d["value"],
                      (f"{d['number']}·" if d["number"] != d["value"] else "") + d["title"][:6],
                      LUCK_COLOR.get(d["luck"], CINNABAR), d["luck"]))
    parts.append(_element_ring(cx, cy, radii["ren"], d["wuxing"]))
    parts.append(_element_badge(cx + radii["ren"] * 0.72, cy - radii["ren"] * 0.72,
                                d["wuxing"], 13.5))
    parts.append(htext(cx + radii["ren"] + 6, cy + 4, d["wuxing"], 15,
                       WUXING_COLOR.get(d["wuxing"], INK_MID),
                       font=FONT_SONG, weight="bold"))

    # 三才：贴竖轴右侧，八字小注，不压圆牌
    parts.append(vtext(cx + 14, cy - 196, "三才", 11, INK_SOFT, 15, opacity=0.75))

    # 底部信息区
    base_y = 890
    parts.append(_rule(74, 746, base_y - 26))
    parts.append(_score_line(76, base_y + 6, "五格评分", w["score"], w["grade"]))
    parts.append(htext(300, base_y + 8, "三才", 13, INK_SOFT, spacing=3))
    parts.append(htext(300, base_y + 48, sc["combo"], 30, INK, font=FONT_SONG, spacing=2))
    parts.append(htext(300, base_y + 74, f"{sc['luck']} · {sc['score']} 分", 13,
                       LUCK_COLOR.get(sc["luck"], INK_MID)))
    parts.append(htext(452, base_y + 8, "结构", 13, INK_SOFT, spacing=3))
    parts.append(htext(452, base_y + 32, structure or "—", 14, INK_MID))
    parts.append(htext(452, base_y + 54, "笔画 " + "·".join(
        f"{c}{v}" for c, v in r["strokes"].items()), 13, INK_SOFT))

    summary = (f"五格 {w['score']} 分，三才{sc['combo']}为{sc['luck']}。"
               + (w.get("highlights") or [""])[0])
    # 人生阶段影响带：五格各管哪段，一眼看清主次
    parts.append(_rule(74, 746, 966))
    parts.append(_stage_band(76, 700, 978))
    parts.append(_wuxing_legend(76, 1062))
    parts.append(_prose(76, 1084, summary, 40, 12.5, 18, 1))
    parts.append(_seal(712, 1076, "五格剖象", 52, -5))
    parts.append(htext(76, 1132, "易學姓名學解析 · 維度解讀圖 一", 10.5, INK_SOFT, spacing=2))
    parts.append(_disclaimer(1132, anchor="end", x=W - 76))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{WH}"'
           f' viewBox="0 0 {W} {WH}">'
           f'<title>{esc(name)} · 五格剖象</title>' + "".join(parts) + "</svg>")
    return _write(path, svg)


# ---------------------------------------------------------------- 图二：五音

# 相邻音气关系配色：相生用青绿（顺）、比和用墨、相克用赭（警）
REL_COLOR = {"相生": "#2F7A4D", "比和": INK_MID, "相克": OCHRE, "无涉": INK_SOFT}


def _pack_judgements(items, max_lines=3, line_width=56, item_cap=36):
    """把 ✓/！ 判据贪心装进少数几行：超长截断、行满换行、总量封顶。"""
    out, cur = [], ""
    for mark, text in items:
        t = text if len(text) <= item_cap else text[:item_cap - 1] + "…"
        piece = f"{mark} {t}"
        if not cur:
            cur = piece
        elif len(cur) + 1 + len(piece) <= line_width:
            cur = f"{cur}　{piece}"
        else:
            out.append(cur)
            cur = piece
            if len(out) >= max_lines:
                break
    if cur and len(out) < max_lines:
        out.append(cur)
    return out[:max_lines]


def render_wuyin(r, path) -> str:
    wy = r["wuyin"]
    inp = r["input"]
    name = _display_name(r)
    chars = wy["chars"]
    n = len(chars)

    cx, cy = 470, 398
    parts = [_paper_bg(), _defs(), _deity_bg(), _frame(),
             _title("五音律吕", "GONG · SHANG · JUE · ZHI · YU", name)]
    parts.append(_wash(cx + 20, cy, 250, 232, 0.082))

    # 十二律刻度（装饰，示意律吕周天）
    ring_r = 214
    for i in range(12):
        a = i * 30 * math.pi / 180
        r1, r2 = ring_r, ring_r - 12 if i % 3 else ring_r - 20
        x1, y1 = cx + r1 * math.sin(a), cy - r1 * math.cos(a)
        x2, y2 = cx + r2 * math.sin(a), cy - r2 * math.cos(a)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"'
                     f' stroke="{INK}" stroke-width="{1.6 if i % 3 == 0 else 0.8}"'
                     f' opacity="{0.42 if i % 3 == 0 else 0.26}"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{ring_r}" fill="none" stroke="{INK}"'
                 f' stroke-width="0.7" opacity="0.18"/>')

    # 四音方位 + 宫居中（朱点标记本名实际用到的音）
    off = 136
    spots = {"徵": (cx, cy - off), "羽": (cx, cy + off),
             "角": (cx - off, cy), "商": (cx + off, cy)}
    for yin, (px, py) in spots.items():
        wx, organ, _ = WUYIN_INFO[yin]
        color = WUXING_COLOR.get(wx, INK)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{px}" y2="{py}" stroke="{INK}"'
                     f' stroke-width="0.8" stroke-dasharray="2 6" opacity="0.30"/>')
        parts.append(node(px, py, 48, wx, yin, organ, color))
        if any(c["wuyin"] == yin for c in chars):
            parts.append(f'<circle cx="{px}" cy="{py - 62}" r="4"'
                         f' fill="{CINNABAR}" opacity="0.9"/>')

    parts.append(taiji(cx, cy, 74, rot=-30, ink=INK, opacity=0.12, sw=1.5))
    parts.append(node(cx, cy, 62, "土", "宫", "喉音·中", OCHRE))
    if any(c["wuyin"] == "宫" for c in chars):
        parts.append(f'<circle cx="{cx}" cy="{cy - 76}" r="4" fill="{CINNABAR}" opacity="0.9"/>')

    # 音序 · 五行序（逐字上五行色，一眼看清宫商角徵羽的流转）
    seq_y = 636
    slot = 40
    seq_w = 2 * (40 + n * slot - 20) + 28
    sx = cx - seq_w / 2
    parts.append(htext(sx, seq_y, "音序", 12, INK_SOFT, spacing=2))
    sx += 40
    for i, yin_ch in enumerate(wy["wuyin_seq"]):
        parts.append(htext(sx, seq_y, yin_ch, 13,
                           WUXING_COLOR.get(wy["wuxing_seq"][i], INK),
                           "middle", font=FONT_SONG, weight="bold"))
        if i < n - 1:
            parts.append(htext(sx + 20, seq_y, "→", 11, INK_SOFT, "middle"))
        sx += slot
    parts.append(htext(sx + 14, seq_y, "｜", 11, INK_SOFT, "middle"))
    sx += 28
    parts.append(htext(sx, seq_y, "五行", 12, INK_SOFT, spacing=2))
    sx += 40
    for i, wx_ch in enumerate(wy["wuxing_seq"]):
        parts.append(htext(sx, seq_y, wx_ch, 13, WUXING_COLOR.get(wx_ch, INK),
                           "middle", font=FONT_SONG, weight="bold"))
        if i < n - 1:
            parts.append(htext(sx + 20, seq_y, "→", 11, INK_SOFT, "middle"))
        sx += slot

    # 逐字音牌
    gap, th_ = 22, 90
    tw = min(156.0, (600 - (n - 1) * gap) / max(n, 1))   # 复姓双名等长名自动收窄
    total = n * tw + (n - 1) * gap
    x0 = cx - total / 2
    ty = 658
    for i, c in enumerate(chars):
        bx = x0 + i * (tw + gap)
        color = WUXING_COLOR.get(c["wuxing"], INK)
        parts.append(f'<g filter="url(#rough)"><rect x="{bx:.1f}" y="{ty}"'
                     f' width="{tw}" height="{th_}" rx="3" fill="{PAPER}"'
                     f' opacity="0.94" stroke="{INK}" stroke-width="1.2"/></g>')
        parts.append(htext(bx + 34, ty + 60, c["char"], 41, INK, "middle", font=FONT))
        parts.append(htext(bx + 66, ty + 32, c["pinyin"], 15.5, INK_MID, font=FONT_SONG))
        parts.append(htext(bx + 66, ty + 52, f"{c['wuyin']}·{c['wuxing']}", 12.5, color))
        parts.append(htext(bx + 66, ty + 72, f"{c['pingze']}声", 12, INK_SOFT))
        if i < n - 1:
            parts.append(htext(bx + tw + gap / 2, ty + 52, "→", 15, INK_SOFT, "middle"))

    # 平仄谱 + 音律评分
    parts.append(_rule(74, 746, 766))
    py_ = 778
    parts.append(htext(76, py_, "平仄", 12, INK_SOFT, spacing=3))
    for i, pz in enumerate(wy["pingze_seq"]):
        px = 128 + i * 44
        fill = INK if pz == "平" else "none"
        parts.append(f'<circle cx="{px}" cy="{py_ + 14}" r="6.5" fill="{fill}"'
                     f' stroke="{INK}" stroke-width="1.1"/>')
        parts.append(htext(px, py_ + 36, str(wy["tone_seq"][i]), 10.5, INK_SOFT, "middle"))

    parts.append(htext(452, py_, "音律评分", 12, INK_SOFT, spacing=3))
    parts.append(htext(452, py_ + 34, str(wy["score"]), 32, CINNABAR,
                       font=FONT_SONG, weight="bold"))
    parts.append(htext(502, py_ + 34, "/ 100", 10.5, INK_SOFT))
    parts.append(htext(540, py_ + 30, wy["grade"], 13.5, CINNABAR))
    for j, line in enumerate(wrap_cn(wy["comment"], 24, 2)):
        parts.append(htext(452, py_ + 54 + j * 15, line, 10.5, INK_MID))

    # 相邻音气关系（相生/相克 + 顺逆）+ 音气与格气协和度
    ry = 872
    parts.append(htext(76, ry, "相邻关系", 11, INK_SOFT, spacing=2))
    for j, p in enumerate(wy["pairs"][:3]):
        rc = REL_COLOR.get(p["relation"], INK_MID)
        y = ry + 16 + j * 16
        parts.append(htext(76, y, f"{p['relation']}·{p['direction']}", 11.5, rc,
                           weight="bold"))
        parts.append(htext(142, y, f"{p['pair']}　{p['from']}→{p['to']}", 11.5, INK_MID))
    rs = wy.get("resonance")
    if rs:
        parts.append(htext(452, ry, "音气与格气", 11, INK_SOFT, spacing=2))
        parts.append(htext(452, ry + 16,
                           f"参照总格五行 {rs['ref_wuxing']}　协和度 {rs['harmony']}%",
                           11.5, INK_MID))
        note = rs["note"]
        if len(note) > 24:
            note = note[:23] + "…"
        parts.append(htext(452, ry + 32, note, 10.5, INK_SOFT))

    # 音律判据（！问题在前、✓ 亮点随后；完整上文，装不下的才截尾）
    jy = 940
    parts.append(htext(76, jy, "音律判据", 11, INK_SOFT, spacing=2))
    items = ([("！", s) for s in wy.get("issues", [])]
             + [("✓", s) for s in wy.get("praise", [])])
    for j, line in enumerate(_pack_judgements(items)):
        parts.append(htext(76, jy + 14 + j * 13, line, 10.5, INK_MID))

    # 分项：横排五格，避免与评分文字相撞
    dims = wy.get("dims") or {}
    if dims:
        dy = 998
        parts.append(htext(76, dy, "音律分项", 10.5, INK_SOFT, spacing=2))
        for i, (k, v) in enumerate(dims.items()):
            x = 76 + i * 116
            parts.append(htext(x, dy + 12, k, 10, INK_MID))
            parts.append(f'<rect x="{x}" y="{dy + 18}" width="84" height="4"'
                         f' fill="{INK}" opacity="0.10"/>')
            parts.append(f'<rect x="{x}" y="{dy + 18}" width="{84 * v / 100:.1f}"'
                         f' height="4" fill="{CINNABAR}" opacity="0.70"/>')
            parts.append(htext(x + 90, dy + 12, str(v), 10, INK_SOFT))

    parts.append(_seal(700, 1026, "五音律呂", 56, -4))
    parts.append(htext(76, 1042, "易學姓名學解析 · 維度解讀圖 二", 10.5, INK_SOFT, spacing=2))
    parts.append(_disclaimer(1064))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"'
           f' viewBox="0 0 {W} {H}">'
           f'<title>{esc(name)} · 五音律吕</title>' + "".join(parts) + "</svg>")
    return _write(path, svg)


# ---------------------------------------------------------------- 图三：梅花

def render_meihua(r, path) -> str:
    m = r["meihua"]
    c = m["cast"]
    inp = r["input"]
    name = _display_name(r)

    parts = [_paper_bg(), _defs(), _deity_bg(), _frame(),
             _title("梅花卦象", "MEIHUA YISHU · BEN · HU · BIAN", name)]
    parts.append(_wash(280, 430, 240, 260, 0.075))
    parts.append(taiji(700, 190, 138, rot=8, ink=INK, opacity=0.075, sw=1.1))

    # 本卦：六爻大图
    bx, y0 = 250, 560
    parts.append(htext(bx, 292, "本卦", 13, INK_SOFT, "middle", spacing=4))
    parts.append(htext(bx, 322, c["ben"]["gua"]["name"], 25, INK, "middle", spacing=3))
    parts.append(hexagram(bx, y0, c["ben"]["yao"], 204, 15, 19, INK,
                          c["ben"]["moving_line"]))
    # 体用括号
    def bracket(y_top, y_bot, x, text, color):
        return (f'<path d="M {x} {y_top} L {x + 12} {y_top} M {x} {y_top} L {x} {y_bot}'
                f' M {x} {y_bot} L {x + 12} {y_bot}" fill="none" stroke="{color}"'
                f' stroke-width="1.6" opacity="0.8"/>'
                + vtext(x + 30, (y_top + y_bot) / 2 - 18, text, 12, color, 15))
    step = 15 + 19
    yong_top, yong_bot = y0 - 5 * step - 8, y0 - 3 * step + 8
    ti_top, ti_bot = y0 - 2 * step - 8, y0 + 8
    parts.append(bracket(yong_top, yong_bot, bx + 118,
                         f"用 {c['yong']['gua']}{c['yong']['wuxing']}",
                         WUXING_COLOR.get(c["yong"]["wuxing"], INK)))
    parts.append(bracket(ti_top, ti_bot, bx + 118,
                         f"体 {c['ti']['gua']}{c['ti']['wuxing']}",
                         WUXING_COLOR.get(c["ti"]["wuxing"], CINNABAR)))
    parts.append(htext(bx, y0 + 48, f"第 {c['ben']['moving_line']} 爻动（朱）", 12,
                       CINNABAR, "middle"))

    # 互卦 / 变卦：右上一列
    for i, (key, tag) in enumerate((("hu", "互卦"), ("bian", "变卦"))):
        ox = 560
        oy = 300 + i * 250
        parts.append(htext(ox, oy, tag, 11.5, INK_SOFT, "middle", spacing=3))
        parts.append(htext(ox, oy + 22, c[key]["gua"]["name"], 16.5, INK, "middle"))
        parts.append(hexagram(ox, oy + 150, yao_of(c[key]["gua"]), 126, 9, 11, INK_MID))
        parts.append(htext(ox, oy + 186, c[key]["gua"]["brief"][:16], 10.5, INK_SOFT, "middle"))

    # 五行旺衰
    ws = m["wangshuai"]
    wx_y = 790
    parts.append(_rule(74, 746, wx_y - 34))
    parts.append(htext(76, wx_y - 6, "卦中五行旺衰", 12.5, INK_SOFT, spacing=3))
    dist = ws["distribution"]
    for i, wx in enumerate(["木", "火", "土", "金", "水"]):
        yy = wx_y + 26 + i * 26
        cnt = dist.get(wx, 0)
        color = WUXING_COLOR.get(wx, INK)
        parts.append(htext(76, yy, wx, 15, color if cnt else INK_SOFT,
                           font=FONT_SONG, weight="bold" if cnt else "normal"))
        if cnt:
            parts.append(f'<rect x="104" y="{yy - 11}" width="{min(cnt, 5) * 34}"'
                         f' height="11" rx="2" fill="{color}" opacity="0.62"/>')
            parts.append(htext(112 + min(cnt, 5) * 34, yy, f"{cnt}", 11, INK_SOFT))
        else:
            parts.append(f'<rect x="104" y="{yy - 11}" width="34" height="11" rx="2"'
                         f' fill="none" stroke="{INK_SOFT}" stroke-width="0.9"'
                         f' stroke-dasharray="3 3"/>')
            parts.append(htext(146, yy, "缺", 10.5, INK_SOFT))

    # 右侧数据
    rx = 470
    parts.append(htext(rx, wx_y - 6, "体用", 12.5, INK_SOFT, spacing=3))
    parts.append(htext(rx, wx_y + 24, m["tiyong"]["relation"], 21, INK, spacing=2))
    parts.append(htext(rx, wx_y + 48, f"变卦：{m['tiyong']['bian_relation']}", 11.5, INK_MID))
    parts.append(htext(rx, wx_y + 76, "气势指数", 11.5, INK_SOFT, spacing=2))
    parts.append(htext(rx + 74, wx_y + 80, str(ws["qi_index"]), 24, CINNABAR, font=FONT_SONG))
    parts.append(htext(rx, wx_y + 104, f"独旺 {ws['dominant']}　不见 "
                                       f"{'、'.join(ws['lacking']) or '无'}", 11, INK_MID))

    parts.append(_score_line(616, 852, "卦象评分", m["score"], m["grade"]))
    n = c["numbers"]
    parts.append(htext(76, 940, "起卦 · 简体笔画", 10.5, INK_SOFT, spacing=3))
    parts.append(htext(76, 964, f"姓 {n['upper']} 画 → 上卦 {c['ben']['gua']['upper']}"
                       f"（{n['upper_mod8']}）", 11.5, INK_MID))
    parts.append(htext(76, 986, f"名 {n['lower']} 画 → 下卦 {c['ben']['gua']['lower']}"
                       f"（{n['lower_mod8']}）", 11.5, INK_MID))
    parts.append(htext(76, 1008, f"合 {n['upper'] + n['lower']} 画 → 第 "
                       f"{c['ben']['moving_line']} 爻动", 11.5, CINNABAR))
    parts.append(_prose(76, 1040, c["ben"]["gua"]["xiang"], 34, 12.5, 19, 1))
    parts.append(_seal(700, 1006, "梅花心易", 56, -5))
    parts.append(htext(76, 1064, "易學姓名學解析 · 維度解讀圖 三", 10.5, INK_SOFT, spacing=2))
    parts.append(_disclaimer(1064, anchor="end", x=W - 76))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"'
           f' viewBox="0 0 {W} {H}">'
           f'<title>{esc(name)} · 梅花卦象</title>' + "".join(parts) + "</svg>")
    return _write(path, svg)


# ---------------------------------------------------------------- 图四：八字

BAZI_LABEL = {"year": "年柱", "month": "月柱", "day": "日柱", "time": "时柱"}
BAZI_POS_ORDER = ("year", "month", "day", "time")


def render_bazi(r, path) -> str:
    """八字原盘（真太阳时）：四柱命盘 + 五行力量 + 强弱 + 喜忌链。"""
    bz = r["bazi"]
    inp = r["input"]
    name = _display_name(r)
    p = bz["pillars"]
    detail = bz["pillar_detail"]
    st = bz["strength"]
    xj = bz["xi_ji"]
    stat = bz["wuxing_stat"]
    bal = bz["balance"]
    ts = bz["true_solar"]

    cx = W / 2
    parts = [_paper_bg(), _defs(), _deity_bg(), _frame(),
             _title("八字原盤", "BAZI · WU XING", name)]
    parts.append(_wash(cx + 20, 300, 300, 260, 0.080))

    # ---- 真太阳时标注带 ----
    band_y = 172
    parts.append(f'<g filter="url(#rough)"><rect x="76" y="{band_y - 26}"'
                 f' width="{W - 152}" height="68" rx="3" fill="{PAPER}"'
                 f' opacity="0.9" stroke="{INK}" stroke-width="1"/></g>')
    if bz["time_known"]:
        std_tag = "（夏令時還原）" if bz.get("was_dst") else (
            f"（UTC{bz['tz_offset']:+.0f} 換算）" if bz.get("tz_offset") else "")
        parts.append(htext(92, band_y - 8, "真太陽時", 12, INK_SOFT, spacing=3))
        parts.append(htext(176, band_y - 8, bz["place"], 12, INK_MID))
        parts.append(htext(392, band_y - 8, f"標準時 {bz['standard_text']}{std_tag}",
                           12, INK_MID))
        parts.append(htext(92, band_y + 12,
                           f"均時差 {ts['eot']:+.1f} 分　經度修正 {ts['lon_delta']:+.1f} 分"
                           f"　合計 {ts['total_delta']:+.1f} 分", 11.5, INK_MID))

        # 真太阳时是否跨入另一时辰：子时起点 23:00，故 (h+1)//2 归支
        def _zhi_idx(hour):
            return ((hour + 1) // 2) % 12

        try:
            std_hour = int(bz["standard_text"][11:13])
        except (ValueError, TypeError):
            std_hour = ts["hour"]
        shift_note = "時辰不變" if _zhi_idx(ts["hour"]) == _zhi_idx(std_hour) else "時辰已改"
        parts.append(htext(92, band_y + 32,
                           f"→ 真太陽時 {bz['true_solar_text']}"
                           f"　（校正 {ts['total_delta']:+.0f} 分，{shift_note}）",
                           12.5, CINNABAR, font=FONT_SONG, weight="bold"))
    else:
        parts.append(htext(92, band_y + 6, "出生時辰未知，年月日以正午定盤，時柱從略",
                           12, INK_MID, spacing=1))

    # ---- 命盘四柱 ----
    col_x = [cx + d for d in (-247.5, -82.5, 82.5, 247.5)]
    top_y, col_h = 232, 208
    for i, pos in enumerate(BAZI_POS_ORDER):
        d = detail[pos]
        x = col_x[i]
        is_day = pos == "day"
        # 柱框（日柱双线高亮）
        parts.append(f'<g filter="url(#rough)"><rect x="{x - 74:.1f}" y="{top_y}"'
                     f' width="148" height="{col_h}" rx="3" fill="{PAPER}"'
                     f' opacity="0.94" stroke="{INK}"'
                     f' stroke-width="{1.8 if is_day else 1.1}"/></g>')
        if is_day:
            parts.append(f'<rect x="{x - 68:.1f}" y="{top_y + 6}" width="136"'
                         f' height="{col_h - 12}" rx="2" fill="none"'
                         f' stroke="{CINNABAR}" stroke-width="0.9" opacity="0.55"/>')
            parts.append(htext(x, top_y + 20, "日主", 11, CINNABAR, "middle", spacing=2))
        parts.append(htext(x, top_y + 40, BAZI_LABEL[pos], 14,
                           INK_MID if not is_day else CINNABAR, "middle", spacing=3))
        if not d:
            parts.append(htext(x, top_y + 118, "未知", 26, INK_SOFT, "middle",
                               font=FONT_SONG))
            parts.append(htext(x, top_y + 150, "時柱從略", 11, INK_SOFT, "middle"))
            continue
        gan_wx, zhi_wx = d["gan_wuxing"], d["zhi_wuxing"]
        # 干支大字（天干在上、地支在下）
        parts.append(htext(x, top_y + 96, d["gan"], 44,
                           WUXING_COLOR.get(gan_wx, INK), "middle",
                           font=FONT_SONG, weight="bold"))
        parts.append(htext(x, top_y + 146, d["zhi"], 44,
                           WUXING_COLOR.get(zhi_wx, INK), "middle",
                           font=FONT_SONG, weight="bold"))
        # 五行徽记贴左右
        parts.append(_element_badge(x - 56, top_y + 86, gan_wx, 11))
        parts.append(_element_badge(x + 56, top_y + 136, zhi_wx, 11))
        # 藏干 + 十神
        cang_txt = "、".join(c["gan"] for c in d["cang"])
        ss_txt = "、".join(c["shishen"] for c in d["cang"])
        parts.append(htext(x, top_y + 174, f"藏干 {cang_txt}", 10.5, INK_MID, "middle"))
        parts.append(htext(x, top_y + 192, ss_txt, 10, INK_SOFT, "middle"))
    # 月令注
    parts.append(htext(cx, top_y + col_h + 30,
                       f"月令 {st['month_wuxing']}（{p['month'][1]}）·"
                       f"日主{st['day_wuxing']}處「{st['month_state']}」地",
                       12.5, INK_MID, "middle", spacing=1))

    # ---- 五行力量条 ----
    bar_y = 556
    parts.append(htext(76, bar_y - 26, "五行力量", 12, INK_SOFT, spacing=3))
    parts.append(htext(168, bar_y - 26,
                       "（天干各一，地支藏干本氣/中氣/餘氣 1.0/0.6/0.4，月令再加權）",
                       9.5, INK_SOFT))
    max_v = max(stat[w]["total"] for w in WUXING_ORDER) or 1.0
    for i, wx in enumerate(WUXING_ORDER):
        y = bar_y + i * 26
        v = stat[wx]["total"]
        c = WUXING_COLOR[wx]
        tag = "（日主）" if wx == st["day_wuxing"] else ""
        parts.append(f'<circle cx="92" cy="{y - 4}" r="8" fill="{c}"'
                     f' opacity="0.92" stroke="{INK}" stroke-width="0.7"'
                     f' filter="url(#rough)"/>')
        parts.append(htext(92, y - 0.8, wx, 9.5, PAPER, "middle"))
        parts.append(htext(108, y, f"{wx}{tag}", 12, INK_MID if wx != st["day_wuxing"] else c))
        bw = 150 + 320 * (v / max_v)
        parts.append(f'<rect x="200" y="{y - 13}" width="{bw:.1f}" height="15" rx="2"'
                     f' fill="{c}" opacity="0.30" filter="url(#rough)"/>')
        parts.append(f'<rect x="200" y="{y - 13}" width="{bw:.1f}" height="15" rx="2"'
                     f' fill="none" stroke="{c}" stroke-width="0.9" opacity="0.6"/>')
        parts.append(htext(200 + bw + 10, y, f"{v:.1f}", 12, INK_MID,
                           font=FONT_SONG))

    # ---- 强弱判定 ----
    st_y = 690
    parts.append(htext(76, st_y, "日主強弱", 12, INK_SOFT, spacing=3))
    parts.append(htext(76, st_y + 44, st["label"], 30,
                       CINNABAR if st["label"] in ("身强", "中和偏强") else "#2E5E8C",
                       font=FONT_SONG, weight="bold"))
    parts.append(htext(200, st_y + 40,
                       f"生助 {st['support']}　／　克泄 {st['drain']}"
                       f"　（月令{st['month_wuxing']}{st['month_state']}）",
                       12.5, INK_MID))
    # 得令/得地/得势 三徽
    for i, (k, label) in enumerate((("de_ling", "得令"), ("de_di", "得地"),
                                    ("de_shi", "得勢"))):
        x = 200 + i * 118
        ok = st[k]
        parts.append(f'<circle cx="{x}" cy="{st_y + 66}" r="6.5"'
                     f' fill="{"none" if not ok else CINNABAR}"'
                     f' stroke="{INK}" stroke-width="1.1"/>')
        parts.append(htext(x + 14, st_y + 70, f"{label}：{'是' if ok else '否'}",
                           12, INK_MID if ok else INK_SOFT))

    # ---- 喜忌链 ----
    xj_y = 790
    parts.append(htext(76, xj_y - 22, "喜忌", 12, INK_SOFT, spacing=3))
    chain = [("用神", xj["yongshen"], "solid"), ("喜神", xj["xishen"], "ring"),
             ("忌神", xj["jishen"], "ink_solid"), ("仇神", xj["choushen"], "ink_ring"),
             ("閒神", xj["xianshen"], "soft")]
    step = (W - 152) / 5
    for i, (label, wxs, style) in enumerate(chain):
        x = 76 + step * i + step / 2
        if i:
            parts.append(htext(x - step / 2, xj_y + 8, "→", 13, INK_SOFT, "middle"))
        parts.append(htext(x, xj_y - 6, label, 12, INK_SOFT, "middle", spacing=2))
        wx = wxs[0] if wxs else None
        if wx:
            c = WUXING_COLOR.get(wx, INK)
            if style == "solid":
                parts.append(f'<circle cx="{x}" cy="{xj_y + 30}" r="21" fill="{c}"'
                             f' stroke="{INK}" stroke-width="1.2" opacity="0.95"'
                             f' filter="url(#rough)"/>')
                parts.append(htext(x, xj_y + 37, wx, 20, PAPER, "middle",
                                   font=FONT_SONG, weight="bold"))
            elif style == "ring":
                parts.append(f'<circle cx="{x}" cy="{xj_y + 30}" r="21" fill="{PAPER}"'
                             f' stroke="{c}" stroke-width="2.6" opacity="0.95"'
                             f' filter="url(#rough)"/>')
                parts.append(htext(x, xj_y + 37, wx, 20, c, "middle",
                                   font=FONT_SONG, weight="bold"))
            elif style == "ink_solid":
                parts.append(f'<circle cx="{x}" cy="{xj_y + 30}" r="21" fill="{INK}"'
                             f' opacity="0.78" stroke="{INK}" stroke-width="1.2"'
                             f' filter="url(#rough)"/>')
                parts.append(htext(x, xj_y + 37, wx, 20, PAPER, "middle",
                                   font=FONT_SONG, weight="bold"))
            elif style == "ink_ring":
                parts.append(f'<circle cx="{x}" cy="{xj_y + 30}" r="21" fill="{PAPER}"'
                             f' stroke="{INK}" stroke-width="1.6" opacity="0.9"'
                             f' filter="url(#rough)"/>')
                parts.append(htext(x, xj_y + 37, wx, 20, INK, "middle",
                                   font=FONT_SONG, weight="bold"))
            else:
                parts.append(f'<circle cx="{x}" cy="{xj_y + 30}" r="21" fill="none"'
                             f' stroke="{INK_SOFT}" stroke-width="1.1" opacity="0.7"'
                             f' filter="url(#rough)"/>')
                parts.append(htext(x, xj_y + 37, wx, 18, INK_SOFT, "middle",
                                   font=FONT_SONG))
        else:
            parts.append(htext(x, xj_y + 37, "—", 18, INK_SOFT, "middle"))
        if wxs and len(wxs) > 1:
            parts.append(htext(x, xj_y + 62, "兼".join(wxs[1:]), 10.5,
                               INK_SOFT, "middle"))
    parts.append(_rule(76, W - 76, xj_y + 76))

    # ---- 判据 / 调候 ----
    parts.append(htext(76, xj_y + 100, "判據", 11, INK_SOFT, spacing=2))
    parts.append(_prose(120, xj_y + 100, xj["reason"], 40, 12, 19, 2))
    if xj.get("tiaohou"):
        parts.append(htext(76, xj_y + 142, "調候", 11, INK_SOFT, spacing=2))
        parts.append(_prose(120, xj_y + 142, xj["tiaohou"], 40, 12, 19, 2))

    # ---- 原盘评分 ----
    parts.append(_score_line(76, 985, "原盤評分", bal["score"], bal["grade"],
                             CINNABAR))
    parts.append(_wuxing_legend(360, 1010))
    parts.append(_seal(712, 1010, "子平命盤", 56, -5))
    parts.append(htext(76, 1064, "易學姓名學解析 · 維度解讀圖 四", 10.5, INK_SOFT, spacing=2))
    parts.append(_disclaimer(1064, anchor="end", x=W - 76))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"'
           f' viewBox="0 0 {W} {H}">'
           f'<title>{esc(name)} · 八字原盘</title>' + "".join(parts) + "</svg>")
    return _write(path, svg)


# ---------------------------------------------------------------- 输出

XML_DECL = '<?xml version="1.0" encoding="utf-8"?>\n'


def _display_name(r) -> str:
    """统一的名称来源：机构模式取 input.name，个人模式取 姓+名。

    此前各处硬编码 inp["surname"] + inp["given"]，机构模式（input 只有 name）
    会 KeyError；build_cards 也因此取不到名称，落到兜底目录导致多人共用。
    """
    inp = (r or {}).get("input") or {}
    if inp.get("name"):
        return str(inp["name"])
    return str(inp.get("surname") or "") + str(inp.get("given") or "")


def _write(path, svg) -> str:
    """写盘。SVG 补 XML 声明——缺声明时部分浏览器按纯文本处理，单独打开不显图。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    if str(path).lower().endswith(".svg") and not svg.lstrip().startswith("<?xml"):
        svg = XML_DECL + svg
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return path


def _data_uri(path: str) -> str:
    """把 SVG 转 base64 data URI，使合览页自包含、拷到任何位置都能显图。"""
    import base64
    with open(path, "rb") as f:
        raw = f.read()
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")


# ---------------------------------------------------------------- 可选：转 PNG

def find_browser() -> str:
    """找本机可用的 Chromium 内核浏览器，用于 SVG→PNG。找不到返回空串。"""
    cands = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    import shutil
    for n in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        p = shutil.which(n)
        if p:
            return p
    return ""


def to_png(svg_path, width=W, height=H, browser="") -> str:
    """用无头浏览器把 SVG 截成 PNG。失败返回空串，绝不抛异常。

    关键修复：截图先落到**同目录临时文件**，校验「退出码为 0 + 文件存在 + 大小 > 0」
    后才原子替换到目标路径；截图前先删除旧 PNG。此前直接以目标路径截图、再用
    「文件是否存在」判成功——旧产物存在时，任何一次截图未产出新文件（浏览器单实例
    复用／参数被拒／超时被杀）都会静默返回上一轮（上一个姓名）的图。
    """
    exe = browser or find_browser()
    if not exe:
        return ""
    svg_path = os.path.abspath(svg_path)
    out = os.path.splitext(svg_path)[0] + ".png"
    url = "file:///" + svg_path.replace("\\", "/")
    import subprocess
    import tempfile
    import shutil

    # 先移除旧 PNG：本次若截图失败，目录里不得留下上一轮的图
    try:
        if os.path.exists(out):
            os.remove(out)
    except OSError:
        pass

    # 临时文件与目标同目录，保证 os.replace 是同一文件系统内的原子操作。
    # 必须保留 .png 后缀：Chromium 依扩展名判定截图格式，无后缀会报
    # "Unsupported screenshot image file type" 且不产出文件。
    tmp_png = f"{out}.part{os.getpid()}.png"
    try:
        if os.path.exists(tmp_png):
            os.remove(tmp_png)
    except OSError:
        pass

    profile = tempfile.mkdtemp(prefix="card_png_")
    cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--disable-extensions",
           f"--user-data-dir={profile}",
           f"--window-size={width},{height}",
           f"--screenshot={tmp_png}", url]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=90)
        if proc.returncode != 0:
            return ""
        if not os.path.exists(tmp_png) or os.path.getsize(tmp_png) <= 0:
            return ""
        os.replace(tmp_png, out)
        return out
    except Exception:
        return ""
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        try:
            if os.path.exists(tmp_png):
                os.remove(tmp_png)
        except OSError:
            pass


def render_index(entries, path, title="维度解读图") -> str:
    """维度图合览页：便于一次看完、也便于打印。"""
    cards = []
    for label, p in entries:
        # 内嵌 data URI：合览页自包含，拷到任意目录／用外部浏览器打开都能显图，
        # 不再依赖同目录下存在同名 .svg 文件（此前重装技能会清空 output，导致图裂）。
        try:
            src = _data_uri(p)
        except OSError:
            src = esc(os.path.basename(p))
        cards.append(f'<figure><img src="{src}" alt="{esc(label)}">'
                     f'<figcaption>{esc(label)}</figcaption></figure>')
    html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{esc(title)}</title>
<style>
  body {{ margin:0; padding:32px 20px 56px; background:#2A2622;
         font-family:"KaiTi","STKaiti",serif; color:#E8E0CE; }}
  h1 {{ font-size:20px; font-weight:normal; letter-spacing:6px; text-align:center;
        margin:0 0 6px; }}
  p.sub {{ text-align:center; font-size:12px; letter-spacing:2px;
           color:#9C9384; margin:0 0 28px; }}
  .row {{ display:flex; gap:20px; justify-content:center; flex-wrap:wrap; }}
  figure {{ margin:0; }}
  img {{ width:360px; display:block; box-shadow:0 10px 30px rgba(0,0,0,.55);
         border:1px solid #4B443B; }}
  figcaption {{ text-align:center; font-size:13px; letter-spacing:3px;
                color:#B9AE99; padding-top:10px; }}
</style></head><body>
<h1>{esc(title)}</h1>
<p class="sub">水墨 · 太极 · 八卦　｜　易學姓名學解析</p>
<div class="row">{''.join(cards)}</div>
<p class="sub" style="margin-top:34px">※ 仅供审美与文化参考，不具备科学预测效力</p>
</body></html>'''
    return _write(path, html)


# 各图固定文件名主干（01 五格 … 05 统合、00 合览；05a/b/c 为统合三张简化版）
CARD_STEMS = ("00_合览", "01_五格", "02_五音", "03_梅花", "04_八字", "05_统合",
              "05a_统合速览", "05b_五行平衡", "05c_交叉印证")


def clean_outputs(outdir, prefix="") -> list:
    """删除本前缀下的历史产物（svg/png/html），返回被删文件名。

    同一目录连续测算时，本轮缺失的维度（未给 birth → 无八字图；统合层未生成
    → 无统合图）若不清除，目录里会留着上一轮的文件，内容属于上一个姓名。
    """
    removed = []
    try:
        names = os.listdir(outdir)
    except OSError:
        return removed
    stems = {f"{prefix}{s}" for s in CARD_STEMS}
    for n in names:
        base, ext = os.path.splitext(n)
        if ext.lower() not in (".svg", ".png", ".html"):
            continue
        # 截图临时文件：正常情况下 finally 已清理，进程被强杀才可能残留，
        # 此处一并清掉（清理发生在渲染开始前，不会有正在写的 part 文件）
        if ".part" in base:
            try:
                os.remove(os.path.join(outdir, n))
            except OSError:
                pass
            continue
        if base in stems:
            try:
                os.remove(os.path.join(outdir, n))
                removed.append(n)
            except OSError:
                pass
    return removed


def render_all(r, outdir, prefix="", png=False, clean=True) -> dict:
    """按报告章节顺序出图，并附合览页。返回 {键: 绝对路径}。

    clean=True（默认）时先清除本前缀的历史产物，确保目录内只存在本次测算的图。
    """
    os.makedirs(outdir, exist_ok=True)
    if clean:
        clean_outputs(outdir, prefix)
    out = {}
    if r.get("wuge"):
        out["wuge"] = render_wuge(r, os.path.join(outdir, f"{prefix}01_五格.svg"))
    if r.get("wuyin"):
        out["wuyin"] = render_wuyin(r, os.path.join(outdir, f"{prefix}02_五音.svg"))
    if r.get("meihua"):
        out["meihua"] = render_meihua(r, os.path.join(outdir, f"{prefix}03_梅花.svg"))
    if r.get("bazi"):
        out["bazi"] = render_bazi(r, os.path.join(outdir, f"{prefix}04_八字.svg"))
    if r.get("synthesis"):
        import synthesis as syn_mod
        p = syn_mod.render_synthesis(r, os.path.join(outdir, f"{prefix}05_统合.svg"))
        if p:
            out["synthesis"] = p
        # 三张简化版（各有所重，可按场景选用；均随统合层一并生成）
        for key, stem, fn in (("synthesis_lite", "05a_统合速览",
                               syn_mod.render_synthesis_lite),
                              ("synthesis_wuxing", "05b_五行平衡",
                               syn_mod.render_synthesis_wuxing),
                              ("synthesis_cross", "05c_交叉印证",
                               syn_mod.render_synthesis_cross)):
            q = fn(r, os.path.join(outdir, f"{prefix}{stem}.svg"))
            if q:
                out[key] = q
    entries = [n for n in (("一 · 五格剖象", out.get("wuge")),
                           ("二 · 五音律吕", out.get("wuyin")),
                           ("三 · 梅花卦象", out.get("meihua")),
                           ("四 · 八字原盤", out.get("bazi")),
                           ("五 · 五維統合", out.get("synthesis")),
                           ("六 · 統合速覽", out.get("synthesis_lite")),
                           ("七 · 五行平衡", out.get("synthesis_wuxing")),
                           ("八 · 交叉印證", out.get("synthesis_cross"))) if n[1]]
    if entries:
        out["index"] = render_index(entries, os.path.join(outdir, f"{prefix}00_合览.html"))
    if png:
        exe = find_browser()
        for k, kw, kh in (("wuge", W, WUGE_H), ("wuyin", W, H),
                          ("meihua", W, H), ("bazi", W, H)):
            if out.get(k):
                p = to_png(out[k], width=kw, height=kh, browser=exe)
                if p:
                    out[k + "_png"] = p
        if out.get("synthesis"):
            import synthesis as syn_mod
            p = to_png(out["synthesis"], width=syn_mod.SW, height=syn_mod.SH, browser=exe)
            if p:
                out["synthesis_png"] = p
        # 简化版尺寸各自不同，截图按各自画布
        for k, kw, kh in (("synthesis_lite", 820, 640),
                          ("synthesis_wuxing", 820, 980),
                          ("synthesis_cross", 820, 980)):
            if out.get(k):
                p = to_png(out[k], width=kw, height=kh, browser=exe)
                if p:
                    out[k + "_png"] = p
        out["browser"] = exe
    return out


if __name__ == "__main__":
    print("dimension_card：请通过 analyze.py --cards 调用，或 import render_all(results, dir)")
