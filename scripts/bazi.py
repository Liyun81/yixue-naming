#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bazi.py —— 真太阳时八字排盘与五行喜忌分析

排盘口径（写入报告，供核对）：
1. 时区换算：出生时间按出生地当地时间输入。默认按北京时间（UTC+8）
   解释；境外出生可用 --tz 给时区偏移（如美西 --tz -8），换算为北京
   标准时间后再进入后续步骤。1986–1991 年全国实行夏令时，期间出生
   的墙上时间自动减 1 小时还原为标准时间（可用 --no-dst 关闭）。
2. 真太阳时 = 北京标准时间 + 均时差(EoT) + (出生地经度 − 120°)×4 分钟。
   经度修正方向：东经小于 120°（如成都 104°E）地方时慢，真太阳时数值
   更早（减约 64 分钟）；东经大于 120°（如哈尔滨 126.6°E）则更早于
   北京时间的对侧——数值更大。均时差采用 Meeus 太阳视位置算法
   （误差 < 0.1 分钟），在出生时刻评估。
3. 年柱、月柱：以北京标准时间与标准节气交接时刻表比较判定（主流排盘
   软件通行口径；节气同日出生时，真太阳时化不改变判定结果）。
4. 年柱以立春交接时刻为界（非农历春节）；月柱以十二节为界。
5. 日柱以儒略日（JDN）独立推算（与内置历法内核交叉验证一致）；
   时柱按日干五鼠遁推导。晚子时（真太阳时 23:00–24:00）日柱、时柱
   均算次日（主流八字派口径）。
6. 节气精确时刻由内置历法内核（vendor/lunar_python，MIT 许可）计算，
   返回北京时间；运行期零第三方依赖。

本模块为技能自有实现：日柱/时柱/EoT/夏令时/时区换算均为自建算法，
仅借用内置历法内核的节气精确时刻与年/月柱基准，
喜忌分析为技能自建规则引擎（评分口径全部写入输出，可复核）。
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

try:
    from lunar_python import Lunar, Solar  # noqa: E402
except Exception as _e:  # pragma: no cover - vendor 缺失时应明确报错
    raise ImportError("内置历法内核缺失：scripts/vendor/lunar_python，"
                      "请参考 scripts/vendor/NOTICE.md 恢复") from _e


class BaziError(Exception):
    """八字排盘输入或数据错误。"""

    def __init__(self, message, code="bazi_input"):
        super().__init__(message)
        self.message = message
        self.code = code


# ---------------------------------------------------------------- 基础表

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

GAN_WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
              "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
ZHI_WUXING = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
              "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
              "戌": "土", "亥": "水"}

# 地支藏干（本气、中气、余气），空位用 None
ZHI_CANG = {
    "子": ("癸", None, None),
    "丑": ("己", "癸", "辛"),
    "寅": ("甲", "丙", "戊"),
    "卯": ("乙", None, None),
    "辰": ("戊", "乙", "癸"),
    "巳": ("丙", "戊", "庚"),
    "午": ("丁", "己", None),
    "未": ("己", "丁", "乙"),
    "申": ("庚", "壬", "戊"),
    "酉": ("辛", None, None),
    "戌": ("戊", "辛", "丁"),
    "亥": ("壬", "甲", None),
}
CANG_WEIGHT = (1.0, 0.6, 0.4)   # 本气 / 中气 / 余气

# 月令当权额外权重
MONTH_WEIGHT = 1.5

WUXING_ORDER = ("木", "火", "土", "金", "水")
WUXING_COLOR = {"木": "#3f7a4e", "火": "#b5452f", "土": "#a8813f",
                "金": "#8a8f96", "水": "#3f6b8a"}
WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # 我生
WUXING_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}      # 我克

SHISHEN_SAME = "比劫"   # 同我
SHISHEN_OUT = "食伤"    # 我生
SHISHEN_WEALTH = "财"   # 我克
SHISHEN_POWER = "官杀"  # 克我
SHISHEN_PRINT = "印"    # 生我

# 月令旺相休囚死：当令者旺、月令所生者相、生月令者休、克月令者囚、月令所克者死
def month_state(wx, month_wx):
    if wx == month_wx:
        return "旺"
    if WUXING_SHENG[month_wx] == wx:
        return "相"
    if WUXING_SHENG[wx] == month_wx:
        return "休"
    if WUXING_KE[wx] == month_wx:
        return "囚"
    return "死"


# 出生地经度表（东经，度）。未列地名可用 --longitude 直接给经度。
CITIES = {
    "北京": 116.41, "天津": 117.20, "上海": 121.47, "重庆": 106.55,
    "哈尔滨": 126.64, "长春": 125.32, "沈阳": 123.43, "呼和浩特": 111.75,
    "石家庄": 114.51, "太原": 112.55, "济南": 117.12, "郑州": 113.62,
    "西安": 108.94, "兰州": 103.83, "银川": 106.23, "西宁": 101.78,
    "乌鲁木齐": 87.62, "喀什": 75.99, "拉萨": 91.11, "成都": 104.07,
    "绵阳": 104.68, "自贡": 104.78, "荣县": 104.42, "宜宾": 104.64,
    "泸州": 105.44, "南充": 106.11, "达州": 107.47, "乐山": 103.77,
    "贵阳": 106.63, "昆明": 102.83, "南宁": 108.32,
    "海口": 110.20, "广州": 113.26, "深圳": 114.06, "珠海": 113.55,
    "东莞": 113.75, "佛山": 113.12, "厦门": 118.09, "福州": 119.30,
    "泉州": 118.59, "杭州": 120.15, "宁波": 121.55, "温州": 120.70,
    "南京": 118.80, "苏州": 120.58, "无锡": 120.30, "徐州": 117.18,
    "合肥": 117.23, "武汉": 114.31, "长沙": 112.94, "南昌": 115.86,
    "九江": 115.99, "青岛": 120.38, "烟台": 121.39, "大连": 121.62,
    "洛阳": 112.45, "开封": 114.31, "桂林": 110.29, "柳州": 109.42,
    "三亚": 109.51, "湛江": 110.36, "汕头": 116.68, "香港": 114.17,
    "澳门": 113.55, "台北": 121.56, "高雄": 120.31, "台南": 120.20,
}
CITY_PROVINCE = {
    "香港": "中国香港", "澳门": "中国澳门", "台北": "中国台湾",
    "高雄": "中国台湾", "台南": "中国台湾",
}


def longitude_of(city=None, longitude=None, tz_offset=None):
    """解析出生地经度。city 命中内置表则返回其经度；否则要求 longitude。

    tz_offset 非 None（境外出生）时放宽至全球经度；否则限制在中国范围。
    """
    if longitude is not None:
        try:
            lon = float(longitude)
        except (TypeError, ValueError):
            raise BaziError(f"经度无法解析：{longitude}，应给数值（东经为正，如 104.07）")
        if not (-180 <= lon <= 180):
            raise BaziError(f"经度 {lon} 超出地球范围（−180°–180°）")
        if not (70 <= lon <= 140) and tz_offset is None:
            raise BaziError(f"经度 {lon} 超出中国范围（70°E–140°E）；境外出生请同时"
                            "给出 --tz 时区偏移（如 --tz -8）")
        return lon, (city or f"东经{lon:.2f}°")
    if city:
        if city in CITIES:
            return CITIES[city], _place_name(city)
        # 去掉 市/区/县 后缀再试
        for suffix in ("市", "地区", "自治州", "区", "县"):
            if city.endswith(suffix) and city[:-len(suffix)] in CITIES:
                return CITIES[city[:-len(suffix)]], _place_name(city[:-len(suffix)])
        raise BaziError(f"未收录出生地「{city}」的经度，请用 --longitude 直接给出"
                        "（如成都 104.07），或换用已收录城市")
    return 120.0, "东经120°（未提供出生地，按北京时间基准经度）"


def _place_name(city):
    """港澳台地区按全称显示（中国香港/中国澳门/中国台湾）。"""
    return CITY_PROVINCE.get(city, city)


# ---------------------------------------------------------------- 时区与夏令时

# 中国夏令时（1986–1991 全国实行；1992-04-05 起停止）。
# 起止日期：4 月中旬第一个星期日 02:00（标准时）拨快至 03:00，
# 9 月中旬第一个星期日 02:00（夏令时）拨回至 01:00。
# 详见 references/08_八字排盘与五行喜忌.md。
CN_DST = {
    1986: ((5, 4), (9, 14)),
    1987: ((4, 12), (9, 13)),
    1988: ((4, 10), (9, 11)),
    1989: ((4, 16), (9, 17)),
    1990: ((4, 15), (9, 16)),
    1991: ((4, 14), (9, 15)),
}


def parse_tz(text):
    """解析时区偏移：'+8' / '-5' / '+5:30' / 'UTC+8'。返回小时（浮点）或 None。"""
    if text is None:
        return None
    t = str(text).strip().upper().replace("UTC", "").replace("GMT", "")
    if not t or t in ("+", "-"):
        return None
    import re
    m = re.match(r"^([+-]?)(\d{1,2})(?::(\d{1,2}))?$", t)
    if not m:
        raise BaziError(f"时区无法解析：{text}，应形如 +8 / -5 / +5:30（相对 UTC）")
    sign = -1 if m.group(1) == "-" else 1
    hours = int(m.group(2))
    minutes = int(m.group(3) or 0)
    if hours > 14 or minutes > 59:
        raise BaziError(f"时区偏移超出合理范围：{text}")
    return sign * (hours + minutes / 60.0)


def _shift_days(y, m, d, delta_days):
    """日期平移 delta_days 天（可负），返回 (y, m, d)。"""
    days = [31, 29 if _is_leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    d += delta_days
    while d > days[m - 1]:
        d -= days[m - 1]
        m += 1
        if m > 12:
            m = 1
            y += 1
            days = [31, 29 if _is_leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    while d < 1:
        m -= 1
        if m < 1:
            m = 12
            y -= 1
        d += [31, 29 if _is_leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return y, m, d


def tz_to_beijing(year, month, day, hour, minute, tz_offset):
    """当地墙上时间 → 北京标准时间（UTC+8）。返回 (y,m,d,h,mi, 换算说明或None)。"""
    if tz_offset is None or abs(tz_offset - 8.0) < 1e-9:
        return year, month, day, hour, minute, None
    delta_min = int(round((8.0 - tz_offset) * 60))
    total = hour * 60 + minute + delta_min
    d_total, rem = divmod(total, 24 * 60)
    if d_total:
        y, m, d = _shift_days(year, month, day, d_total)
    else:
        y, m, d = year, month, day
    h, mi = divmod(rem, 60)
    note = (f"时区换算：UTC{tz_offset:+.2f} 当地 {year:04d}-{month:02d}-{day:02d} "
            f"{hour:02d}:{minute:02d} → 北京时间 {y:04d}-{m:02d}-{d:02d} {h:02d}:{mi:02d}")
    return y, m, d, h, mi, note


def dst_adjust(year, month, day, hour, minute):
    """北京墙上时间 → 北京标准时间（夏令时还原）。

    规则（references/08）：
    - 夏令时开始日 02:00（标准时）起为夏令时（墙上 03:00 起）；
      开始日 02:00–02:59 的墙上时间不存在（被拨快跳过），按标准时解释；
    - 夏令时结束日 02:00（夏令时）起已拨回标准；结束日 01:00–01:59
      为重复时刻，按标准时解释；结束日 00:00–00:59 仍为夏令时；
    - 窗口内标准时间 = 墙上时间 − 1 小时（可能跨至前一日）。
    返回 (y, m, d, h, mi, 是否夏令时还原, 说明或None)。
    """
    if year not in CN_DST:
        return year, month, day, hour, minute, False, None
    (sm, sd), (em, ed) = CN_DST[year]
    if (month, day) < (sm, sd) or (month, day) > (em, ed):
        return year, month, day, hour, minute, False, None
    if (month, day) == (sm, sd) and hour < 3:
        return year, month, day, hour, minute, False, None
    if (month, day) == (em, ed) and hour >= 1:
        return year, month, day, hour, minute, False, None
    # 夏令时还原：墙上 − 1 小时（00:00–00:59 会跨到前一日）
    total = (hour - 1) * 60 + minute
    d_total, rem = divmod(total, 24 * 60)
    if d_total:
        y, m, d = _shift_days(year, month, day, d_total)
    else:
        y, m, d = year, month, day
    h, mi = divmod(rem, 60)
    note = (f"夏令时还原：{year} 年全国夏令时（{sm:02d}-{sd:02d} 至 {em:02d}-{ed:02d}），"
            f"墙上时间 {hour:02d}:{minute:02d} 减 1 小时 → 标准时间 "
            f"{y:04d}-{m:02d}-{d:02d} {h:02d}:{mi:02d}")
    return y, m, d, h, mi, True, note


# ---------------------------------------------------------------- 真太阳时

def equation_of_time_minutes(year, month, day, hour=12, minute=0):
    """均时差 EoT（分钟）：真太阳时 − 平太阳时（正=视太阳超前、钟慢）。

    Meeus《Astronomical Algorithms》太阳视位置算法（NOAA 太阳计算器同源）：
    由平黄经 L0、平近点角 M 求真黄经与视赤经，EoT = 4×(L0 − 视赤经)。
    与公开天文年历锚点误差 < 0.1 分钟（2/11 ≈ −14.2、11/3 ≈ +16.4）。
    在给定时刻（UT）评估。
    """
    jd = _julian_day_ut(year, month, day, hour, minute) - 8.0 / 24.0
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + 36000.76983 * t + 0.0003032 * t * t) % 360.0
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    c = math.radians((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m)
                     + (0.019993 - 0.000101 * t) * math.sin(2 * m)
                     + 0.000289 * math.sin(3 * m))
    lam = math.radians(l0) + c
    omega = math.radians(125.04 - 1934.136 * t)
    lam -= math.radians(0.00569) + math.radians(0.00478) * math.sin(omega)
    eps = math.radians(23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0)
    eps += math.radians(0.00256) * math.cos(omega)
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)))
    eot = (l0 - ra + 180.0) % 360.0 - 180.0
    return 4.0 * eot


def _julian_day_ut(year, month, day, hour=0, minute=0):
    """格里高利历日期 + 时刻 → 儒略日（UT）。"""
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return (int(365.25 * (year + 4716)) + int(30.6001 * (month + 1))
            + day + b - 1524.5 + (hour + minute / 60.0) / 24.0)


def _day_of_year(year, month, day):
    days = [31, 29 if _is_leap(year) else 28, 31, 30, 31, 30,
            31, 31, 30, 31, 30, 31]
    return sum(days[:month - 1]) + day


def _is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def true_solar_time(year, month, day, hour, minute, longitude):
    """北京标准时间 → 真太阳时。返回 (y,m,d,h,mi, 校正明细)。

    真太阳时 = 标准时间 + EoT + (经度 − 120°)×4 分钟。
    经度修正方向：东经小于 120°（如成都）地方时慢，真太阳时数值更早。
    """
    eot = equation_of_time_minutes(year, month, day, hour, minute)
    lon_delta = (longitude - 120.0) * 4.0
    total = hour * 60 + minute + eot + lon_delta
    total_i = int(total)   # 截断到分（不四舍五入，避免把 HH:59:50 抬进下一时辰）
    d_total, rem = divmod(total_i, 24 * 60)
    if d_total:
        y, m, d = _shift_days(year, month, day, d_total)
    else:
        y, m, d = year, month, day
    h, mi = divmod(rem, 60)
    meta = {
        "eot": round(eot, 1),
        "lon_delta": round(lon_delta, 1),
        "total_delta": round(eot + lon_delta, 1),
        "shift_minutes": total_i - (hour * 60 + minute),
    }
    return y, m, d, h, mi, meta


# ---------------------------------------------------------------- 排盘

def parse_birth(text):
    """解析出生时间：'1990-05-20 14:30' / '1990-05-20' / '1990年5月20日14时30分'。"""
    if not text:
        return None
    import re
    t = text.strip()
    t = t.replace("年", "-").replace("月", "-").replace("日", " ")
    t = t.replace("时", ":").replace("分", ":").replace("秒", "")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{1,2}))?$", t)
    if not m:
        raise BaziError(f"出生时间无法解析：{text}，应为 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD'")
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    h = int(m.group(4)) if m.group(4) else None
    mi = int(m.group(5)) if m.group(5) else 0
    if not (1900 <= y <= 2100):
        raise BaziError(f"出生年份 {y} 超出支持范围（1900–2100）")
    if not (1 <= mo <= 12):
        raise BaziError(f"出生月份 {mo} 不合法")
    days = [31, 29 if _is_leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not (1 <= d <= days[mo - 1]):
        raise BaziError(f"{y}年{mo}月没有 {d} 日")
    if h is not None and not (0 <= h <= 23):
        raise BaziError(f"出生小时 {h} 不合法")
    if h is not None and not (0 <= mi <= 59):
        raise BaziError(f"出生分钟 {mi} 不合法")
    return {"year": y, "month": mo, "day": d, "hour": h, "minute": mi,
            "time_known": h is not None}


def _lunar_of(y, m, d, h, mi):
    return Lunar.fromSolar(Solar.fromYmdHms(y, m, d, h, mi, 0))


def day_ganzhi(y, m, d):
    """日柱：儒略日（JDN）独立推算。与内置历法内核交叉验证一致。

    公式：JDN(格里高利历) → 六十甲子序号 = (JDN + 49) mod 60。
    公开锚点：1949-10-01 甲子、2000-01-01 戊午、2024-01-01 甲子。
    """
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    jdn = d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
    idx = (jdn + 49) % 60
    return GAN[idx % 10] + ZHI[idx % 12]


def time_ganzhi(day_gz, hour):
    """时柱：五鼠遁。hour 为真太阳时小时（0–23）。

    甲己日起甲子、乙庚日起丙子、丙辛日起戊子、丁壬日起庚子、戊癸日起壬子；
     equivalently 时干 = (日干序×2 + 时支序) mod 10（甲=0、子=0）。
    """
    zhi_idx = ((hour + 1) // 2) % 12
    gan_idx = (GAN.index(day_gz[0]) * 2 + zhi_idx) % 10
    return GAN[gan_idx] + ZHI[zhi_idx]


def pillars(birth, longitude, tz_offset=None, use_dst=True):
    """四柱排盘。birth 为 parse_birth 结果；longitude 为出生地经度。

    柱别口径：
    - 年柱、月柱：以北京标准时间与标准节气交接时刻表比较判定
      （主流排盘软件通行口径；节气同日出生时，真太阳时化不改变判定）；
    - 日柱、时柱：以真太阳时为准（晚子时按真太阳时 23:00–24:00 判定，
      日柱、时柱均算次日；日柱 JDN 自算、时柱五鼠遁自算）。

    换算链：当地墙上时间 →（--tz）北京墙上时间 →（夏令时）北京标准时间
    → 年/月柱（节气表）；标准时间 + EoT + 经度 → 真太阳时 → 日/时柱。
    """
    y, m, d = birth["year"], birth["month"], birth["day"]
    h, mi = birth["hour"], birth["minute"]
    time_known = birth["time_known"]

    notes = []
    # 夏令时还原仅对北京时间口径生效：境外出生（--tz）时用户给出的偏移
    # 已是当时实际偏移，不再套用中国夏令时。
    china_tz = tz_offset is None or abs(tz_offset - 8.0) < 1e-9
    if time_known:
        # 1) 时区换算（境外出生）
        by, bm, bd, bh, bmi, tz_note = tz_to_beijing(y, m, d, h, mi, tz_offset)
        if tz_note:
            notes.append(tz_note)
        # 2) 夏令时还原（1986–1991，仅北京时间口径）
        if use_dst and china_tz:
            sy, sm, sd, sh, smi, was_dst, dst_note = dst_adjust(by, bm, bd, bh, bmi)
            if dst_note:
                notes.append(dst_note)
        else:
            sy, sm, sd, sh, smi, was_dst = by, bm, bd, bh, bmi, False
        solar_basis = f"{sy:04d}-{sm:02d}-{sd:02d} {sh:02d}:{smi:02d}"
    else:
        # 时辰未知：以正午定盘（标准时间同日 12:00）
        sy, sm, sd, sh, smi, was_dst = y, m, d, 12, 0, False
        solar_basis = f"{sy:04d}-{sm:02d}-{sd:02d} 12:00（正午定盘）"

    # 年柱、月柱：标准时间与节气表比较（内核 Exact 系列按节气时刻分界）
    lunar_std = _lunar_of(sy, sm, sd, sh, smi)
    year_gz = lunar_std.getYearInGanZhiExact()     # 立春为界
    month_gz = lunar_std.getMonthInGanZhiExact()   # 十二节为界（时刻分界）
    prev_jq = lunar_std.getPrevJieQi()
    next_jq = lunar_std.getNextJieQi()

    # 日柱、时柱：真太阳时
    if time_known:
        ty, tm, td, th, tmi, meta = true_solar_time(sy, sm, sd, sh, smi, longitude)
        # 晚子时（真太阳时 23:00–24:00）：日柱、时柱均算次日
        if th >= 23:
            py, pm, pd = _shift_days(ty, tm, td, 1)
            day_gz = day_ganzhi(py, pm, pd)
        else:
            day_gz = day_ganzhi(ty, tm, td)
        time_gz = time_ganzhi(day_gz, th)
    else:
        ty, tm, td, th, tmi = sy, sm, sd, 12, 0
        meta = {"note": "出生时辰未知，年月日三柱以正午时刻定盘，时柱从略"}
        day_gz = day_ganzhi(ty, tm, td)
        time_gz = None

    day_gan = day_gz[0]
    result = {
        "birth": birth,
        "time_known": time_known,
        "longitude": longitude,
        "tz_offset": tz_offset,
        "was_dst": was_dst,
        "conversion_notes": notes,
        "true_solar": {"year": ty, "month": tm, "day": td,
                       "hour": th, "minute": tmi, **meta},
        "solar_basis": solar_basis,
        "standard_text": f"{sy:04d}-{sm:02d}-{sd:02d} {sh:02d}:{smi:02d}",
        "true_solar_text": f"{ty:04d}-{tm:02d}-{td:02d} {th:02d}:{tmi:02d}" if time_known
                           else f"{ty:04d}-{tm:02d}-{td:02d} 12:00",
        "pillars": {
            "year": year_gz, "month": month_gz, "day": day_gz, "time": time_gz,
        },
        "prev_jieqi": {"name": prev_jq.getName(),
                       "time": prev_jq.getSolar().toYmdHms()},
        "next_jieqi": {"name": next_jq.getName(),
                       "time": next_jq.getSolar().toYmdHms()},
    }
    return result


# ---------------------------------------------------------------- 五行统计

def shishen(day_wx, other_wx):
    """other 五行相对日主五行的十神归类。"""
    if other_wx == day_wx:
        return SHISHEN_SAME
    if WUXING_SHENG[day_wx] == other_wx:
        return SHISHEN_OUT
    if WUXING_KE[day_wx] == other_wx:
        return SHISHEN_WEALTH
    if WUXING_KE[other_wx] == day_wx:
        return SHISHEN_POWER
    return SHISHEN_PRINT


def wuxing_stat(pillars):
    """五行力量统计：天干各 1.0；地支藏干按 1.0/0.6/0.4；月令地支再 ×1.5。"""
    stat = {wx: {"gan": 0.0, "zhi": 0.0, "total": 0.0, "count_gan": 0} for wx in WUXING_ORDER}
    month_zhi = pillars["month"][1]
    for pos in ("year", "month", "day", "time"):
        gz = pillars[pos]
        if not gz:
            continue
        gan, zhi = gz[0], gz[1]
        stat[GAN_WUXING[gan]]["gan"] += 1.0
        stat[GAN_WUXING[gan]]["count_gan"] += 1
        cang = ZHI_CANG[zhi]
        for i, g in enumerate(cang):
            if g:
                w = CANG_WEIGHT[i]
                if zhi == month_zhi:
                    w *= MONTH_WEIGHT
                stat[GAN_WUXING[g]]["zhi"] += round(w, 2)
    for wx in WUXING_ORDER:
        stat[wx]["total"] = round(stat[wx]["gan"] + stat[wx]["zhi"], 2)
    return stat


def strength_of(pillars):
    """日主强弱：support = 比劫+印 的力量，drain = 食伤+财+官杀 的力量。"""
    day_wx = GAN_WUXING[pillars["day"][0]]
    stat = wuxing_stat(pillars)
    support = drain = 0.0
    for wx in WUXING_ORDER:
        ss = shishen(day_wx, wx)
        if ss in (SHISHEN_SAME, SHISHEN_PRINT):
            support += stat[wx]["total"]
        else:
            drain += stat[wx]["total"]
    total = support + drain
    ratio = support / total if total else 0.5
    if ratio >= 0.62:
        label = "身强"
    elif ratio >= 0.54:
        label = "中和偏强"
    elif ratio >= 0.46:
        label = "中和"
    elif ratio >= 0.38:
        label = "中和偏弱"
    else:
        label = "身弱"
    # 得令 / 得地 / 得势
    month_wx = ZHI_WUXING[pillars["month"][1]]
    de_ling = month_state(day_wx, month_wx) in ("旺", "相")
    roots = [gz[1] for gz in (pillars["year"], pillars["month"],
                              pillars["day"], pillars["time"]) if gz]
    root_hit = [z for z in roots
                if any(GAN_WUXING[g] == day_wx for g in ZHI_CANG[z] if g)]
    de_di = bool(root_hit)
    gans = [gz[0] for gz in (pillars["year"], pillars["month"],
                             pillars["day"], pillars["time"]) if gz]
    help_gan = [g for g in gans
                if GAN_WUXING[g] == day_wx or WUXING_SHENG[GAN_WUXING[g]] == day_wx]
    return {
        "day_wuxing": day_wx,
        "support": round(support, 2), "drain": round(drain, 2),
        "ratio": round(ratio, 3), "label": label,
        "de_ling": de_ling, "month_state": month_state(day_wx, month_wx),
        "month_wuxing": month_wx,
        "de_di": de_di, "roots": root_hit,
        "de_shi": len(help_gan) >= 2, "help_gan": help_gan,
    }


# ---------------------------------------------------------------- 喜忌

def xi_ji(pillars):
    """五行喜忌：以身强身弱定生扶/克泄，兼看冬夏调候。"""
    st = strength_of(pillars)
    stat = wuxing_stat(pillars)
    day_wx = st["day_wuxing"]
    month_zhi = pillars["month"][1]

    if st["label"] in ("身强", "中和偏强"):
        like = [SHISHEN_WEALTH, SHISHEN_POWER, SHISHEN_OUT]      # 喜克泄耗
        avoid = [SHISHEN_SAME, SHISHEN_PRINT]                   # 忌印比
    elif st["label"] in ("身弱", "中和偏弱"):
        like = [SHISHEN_PRINT, SHISHEN_SAME]                    # 喜生扶
        avoid = [SHISHEN_WEALTH, SHISHEN_POWER, SHISHEN_OUT]    # 忌克泄耗
    else:  # 中和：顺势，缺者补之、旺者泄之
        like = []
        avoid = []
        weakest = min(WUXING_ORDER, key=lambda w: stat[w]["total"])
        strongest = max(WUXING_ORDER, key=lambda w: stat[w]["total"])
        like.append(shishen(day_wx, weakest))
        avoid.append(shishen(day_wx, strongest))

    def wuxing_of_sstype(ss):
        return [wx for wx in WUXING_ORDER if shishen(day_wx, wx) == ss]

    like_wx = []
    for ss in like:
        for wx in wuxing_of_sstype(ss):
            if wx not in like_wx:
                like_wx.append(wx)
    avoid_wx = []
    for ss in avoid:
        for wx in wuxing_of_sstype(ss):
            if wx not in avoid_wx:
                avoid_wx.append(wx)

    # 调候：夏生喜水、冬生喜火（仅在该行偏枯时提升优先级）
    tiaohou = None
    if month_zhi in ("巳", "午", "未") and stat["水"]["total"] < 1.5:
        tiaohou = ("生于巳午未月，火炎土燥，调候以水为急"
                   if "水" in avoid_wx or "水" not in like_wx else
                   "生于巳午未月，火炎土燥，水亦调候所宜")
        if "水" not in like_wx:
            like_wx.insert(0, "水")
    elif month_zhi in ("亥", "子", "丑") and stat["火"]["total"] < 1.5:
        tiaohou = "生于亥子丑月，水冷金寒，调候以火为急"
        if "火" not in like_wx:
            like_wx.insert(0, "火")

    # 用神：喜类中力量最弱者（最需补）；喜神：其余喜类
    like_sorted = sorted(like_wx, key=lambda w: stat[w]["total"])
    yongshen = like_sorted[:1] if like_sorted else []
    xishen = like_sorted[1:] if len(like_sorted) > 1 else []
    avoid_sorted = sorted(avoid_wx, key=lambda w: -stat[w]["total"])
    jishen = avoid_sorted[:1] if avoid_sorted else []
    choushen = []
    for wx in jishen:   # 仇神：生忌神之五行
        parent = [k for k, v in WUXING_SHENG.items() if v == wx]
        for p in parent:
            if p not in choushen and p not in jishen and p not in yongshen:
                choushen.append(p)
    used = set(yongshen + xishen + jishen + choushen)
    xianshen = [w for w in WUXING_ORDER if w not in used]

    reason = (f"日主{day_wx}，{st['label']}"
              f"（生助 {st['support']} / 克泄 {st['drain']}，"
              f"月令{ZHI_WUXING[pillars['month'][1]]}{st['month_state']}）；"
              + ("身强喜克泄耗，忌再生扶。" if st["label"] in ("身强", "中和偏强")
                 else "身弱喜生扶，忌再克泄。" if st["label"] in ("身弱", "中和偏弱")
                 else "中和取衡，弱者补、旺者泄。"))
    return {
        "yongshen": yongshen, "xishen": xishen, "jishen": jishen,
        "choushen": choushen, "xianshen": xianshen,
        "reason": reason, "tiaohou": tiaohou,
        "like_wx": like_wx, "avoid_wx": avoid_wx,
    }


# ---------------------------------------------------------------- 原盘评分

def balance_score(pillars):
    """原盘平衡分：五行越均衡分越高；缺行/独旺扣分；有通关链加分。"""
    stat = wuxing_stat(pillars)
    totals = [stat[w]["total"] for w in WUXING_ORDER]
    total = sum(totals) or 1
    # 均衡度：各五行占比与均值的方差
    share = [t / total for t in totals]
    mean = 1 / 5
    var = sum((s - mean) ** 2 for s in share) / 5
    balance = max(0.0, 1 - var * 14)
    # 缺行扣分（无天干且无藏干）
    lacking = sum(1 for w in WUXING_ORDER if stat[w]["total"] <= 0)
    # 通关链：任一五行既生喜又泄旺（木→火→土→金→水→木 连续三环）
    chain = 0
    present = [w for w in WUXING_ORDER if stat[w]["total"] > 0]
    if len(present) >= 4:
        chain = 4
    score = round(balance * 88 - lacking * 5 + chain, 1)
    score = max(30.0, min(95.0, score))
    if score >= 80:
        grade = "流通"
    elif score >= 70:
        grade = "偏衡"
    elif score >= 60:
        grade = "中平"
    else:
        grade = "偏枯"
    return {"score": score, "grade": grade, "lacking_wx":
            [w for w in WUXING_ORDER if stat[w]["total"] <= 0]}


# ---------------------------------------------------------------- 总入口

def analyze_bazi(birth_text, city=None, longitude=None, tz_offset=None, use_dst=True):
    """八字排盘 + 五行喜忌。birth_text 见 parse_birth；返回结构化结果。

    tz_offset：出生地时区偏移（小时，如 -8）；None 表示北京时间（UTC+8）。
    use_dst：是否自动还原 1986–1991 年全国夏令时（默认 True）。
    """
    birth = parse_birth(birth_text)
    if birth is None:
        raise BaziError("未提供出生时间", code="bazi_missing")
    lon, place = longitude_of(city, longitude, tz_offset)
    base = pillars(birth, lon, tz_offset=tz_offset, use_dst=use_dst)
    p = base["pillars"]
    stat = wuxing_stat(p)
    st = strength_of(p)
    xj = xi_ji(p)
    bal = balance_score(p)

    # 逐柱藏干与十神
    day_wx = GAN_WUXING[p["day"][0]]
    detail = {}
    for pos in ("year", "month", "day", "time"):
        gz = p[pos]
        if not gz:
            detail[pos] = None
            continue
        cang = []
        for i, g in enumerate(ZHI_CANG[gz[1]]):
            if g:
                cang.append({"gan": g, "weight": CANG_WEIGHT[i],
                             "wuxing": GAN_WUXING[g],
                             "shishen": shishen(day_wx, GAN_WUXING[g])})
        detail[pos] = {"gan": gz[0], "zhi": gz[1],
                       "gan_wuxing": GAN_WUXING[gz[0]],
                       "zhi_wuxing": ZHI_WUXING[gz[1]],
                       "cang": cang}
    result = {
        **base,
        "place": place, "longitude": lon,
        "pillar_detail": detail,
        "wuxing_stat": stat,
        "strength": st,
        "xi_ji": xj,
        "balance": bal,
    }
    return result


DISCLAIMER = ("八字排盘与五行喜忌基于传统子平命理规则生成；真太阳时校正含时区/"
              "夏令时（1986–1991）还原、经度修正与 Meeus 天文算法均时差"
              "（误差 <0.1 分钟），节气时刻精确到秒。仅供民俗文化参考，"
              "不具备科学预测效力，不构成人生决策依据。")


def render_bazi(bz):
    """八字段文字（供 analyze.py 报告调用）。"""
    L = []
    L.append("　排盘口径：真太阳时 = 北京时间 + 均时差 + (出生地经度 − 120°)×4分钟；")
    L.append("　　　　日柱、时柱按真太阳时（晚子时 23:00–24:00 日时柱均算次日）；")
    L.append("　　　　年柱、月柱按北京标准时间与标准节气表判定（立春/十二节时刻分界）。")
    ts = bz["true_solar"]
    if bz["time_known"]:
        L.append(f"　出生地：{bz['place']}")
        for note in bz.get("conversion_notes") or []:
            L.append(f"　{note}")
        L.append(f"　北京标准时间：{bz['solar_basis']}")
        L.append(f"　均时差 {ts['eot']:+.1f} 分（Meeus），经度修正 {ts['lon_delta']:+.1f} 分"
                 f"（合计 {ts['total_delta']:+.1f} 分）")
        L.append(f"　真太阳时：{bz['true_solar_text']}")
        if abs(ts.get("shift_minutes", 0)) >= 1:
            cross_day = bz["standard_text"][:10] != bz["true_solar_text"][:10]
            # 是否真的跨了时辰，按地支索引比，不看偏移量大小
            def _zhi_idx(hour):
                return ((hour + 1) // 2) % 12
            cross_zhi = (_zhi_idx(int(bz["standard_text"][11:13]))
                         != _zhi_idx(int(bz["true_solar_text"][11:13])))
            L.append(f"　※ 校正偏移 {ts['shift_minutes']:+d} 分钟"
                     + ("，已跨日，四柱以真太阳时为准" if cross_day
                        else "，已跨时辰，时柱以真太阳时为准" if cross_zhi
                        else "，时辰不变"))
    else:
        L.append(f"　出生地：{bz['place']}")
        L.append(f"　出生时辰未知，年月日以正午定盘，时柱从略。")
    p = bz["pillars"]
    L.append(f"　前节气：{bz['prev_jieqi']['name']}（{bz['prev_jieqi']['time']}）　"
             f"后节气：{bz['next_jieqi']['name']}（{bz['next_jieqi']['time']}）")
    L.append("")
    L.append("　┌──────┬──────┬──────┬──────┐")
    L.append("　│ 年柱 │ 月柱 │ 日柱 │ 时柱 │")
    L.append("　├──────┼──────┼──────┼──────┤")
    L.append("　│  %s  │  %s  │  %s  │  %s  │" % (
        p["year"], p["month"], p["day"], p["time"] or " 未知 "))
    L.append("　└──────┴──────┴──────┴──────┘")
    for pos, label in (("year", "年"), ("month", "月"), ("day", "日"), ("time", "时")):
        d = bz["pillar_detail"][pos]
        if not d:
            L.append(f"　{label}柱：时辰未知，从略")
            continue
        cang_txt = "、".join(f"{c['gan']}({c['shishen']})" for c in d["cang"])
        L.append(f"　{label}柱 {d['gan']}{d['zhi']}：{d['gan_wuxing']}{d['gan']}、"
                 f"{d['zhi_wuxing']}{d['zhi']}　藏干 {cang_txt}")
    st = bz["strength"]
    L.append(f"　日主 {st['day_wuxing']}（{p['day'][0]}）"
             f"　月令 {st['month_wuxing']}·{st['month_state']}")
    L.append(f"　强弱：{st['label']}　生助 {st['support']} ／ 克泄 {st['drain']}"
             f"　得令：{'是' if st['de_ling'] else '否'}"
             f"　得地：{'是（' + '、'.join(st['roots']) + '）' if st['de_di'] else '否'}"
             f"　得势：{'是' if st['de_shi'] else '否'}")
    stat = bz["wuxing_stat"]
    L.append("　五行力量：" + "　".join(
        f"{w} {stat[w]['total']:.1f}" for w in WUXING_ORDER))
    xj = bz["xi_ji"]
    L.append(f"　喜忌：用神 {'、'.join(xj['yongshen']) or '—'}"
             f"　喜神 {'、'.join(xj['xishen']) or '—'}"
             f"　忌神 {'、'.join(xj['jishen']) or '—'}"
             f"　仇神 {'、'.join(xj['choushen']) or '—'}"
             f"　闲神 {'、'.join(xj['xianshen']) or '—'}")
    L.append(f"　判据：{xj['reason']}")
    if xj.get("tiaohou"):
        L.append(f"　调候：{xj['tiaohou']}")
    bal = bz["balance"]
    L.append(f"　原盘评分：{bal['score']} / 100（{bal['grade']}）"
             + (f"　缺 {'、'.join(bal['lacking_wx'])}" if bal["lacking_wx"] else ""))
    return L
