"""输出格式化工具：数字、时间、Markdown 表格、职业专精中文名。"""
from __future__ import annotations

import math
import statistics
from typing import Any, Iterable, List, Optional, Sequence

CLASS_ZH = {
    "DeathKnight": "死亡骑士", "DemonHunter": "恶魔猎手", "Druid": "德鲁伊", "Evoker": "唤魔师",
    "Hunter": "猎人", "Mage": "法师", "Monk": "武僧", "Paladin": "圣骑士", "Priest": "牧师",
    "Rogue": "潜行者", "Shaman": "萨满祭司", "Warlock": "术士", "Warrior": "战士",
}

SPEC_ZH = {
    ("DeathKnight", "Blood"): "鲜血", ("DeathKnight", "Frost"): "冰霜", ("DeathKnight", "Unholy"): "邪恶",
    ("DemonHunter", "Havoc"): "浩劫", ("DemonHunter", "Vengeance"): "复仇",
    ("Druid", "Balance"): "平衡", ("Druid", "Feral"): "野性", ("Druid", "Guardian"): "守护", ("Druid", "Restoration"): "恢复",
    ("Evoker", "Devastation"): "湮灭", ("Evoker", "Preservation"): "恩护", ("Evoker", "Augmentation"): "增辉",
    ("Hunter", "BeastMastery"): "野兽控制", ("Hunter", "Marksmanship"): "射击", ("Hunter", "Survival"): "生存",
    ("Mage", "Arcane"): "奥术", ("Mage", "Fire"): "火焰", ("Mage", "Frost"): "冰霜",
    ("Monk", "Brewmaster"): "酒仙", ("Monk", "Mistweaver"): "织雾", ("Monk", "Windwalker"): "踏风",
    ("Paladin", "Holy"): "神圣", ("Paladin", "Protection"): "防护", ("Paladin", "Retribution"): "惩戒",
    ("Priest", "Discipline"): "戒律", ("Priest", "Holy"): "神圣", ("Priest", "Shadow"): "暗影",
    ("Rogue", "Assassination"): "奇袭", ("Rogue", "Outlaw"): "狂徒", ("Rogue", "Subtlety"): "敏锐",
    ("Shaman", "Elemental"): "元素", ("Shaman", "Enhancement"): "增强", ("Shaman", "Restoration"): "恢复",
    ("Warlock", "Affliction"): "痛苦", ("Warlock", "Demonology"): "恶魔学识", ("Warlock", "Destruction"): "毁灭",
    ("Warrior", "Arms"): "武器", ("Warrior", "Fury"): "狂怒", ("Warrior", "Protection"): "防护",
}

ROLE_ZH = {"tank": "坦克", "healer": "治疗", "dps": "输出", "unknown": "未知"}


def class_spec(cls: str, spec: str) -> str:
    """职业-专精中文名；未知的新专精（如午夜的 DH Devourer）保留英文。"""
    c = CLASS_ZH.get(cls, cls or "?")
    s = SPEC_ZH.get((cls, spec), spec or "")
    return f"{c}-{s}" if s else c


def num(value: Optional[float]) -> str:
    """1234 -> 1.23K, 12345678 -> 12.3M（3 位有效数字）。"""
    if value is None:
        return "—"
    v = float(value)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v < 1000:
        return f"{sign}{v:.0f}"
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= size:
            x = v / size
            if x >= 100:
                return f"{sign}{x:.0f}{unit}"
            if x >= 10:
                return f"{sign}{x:.1f}{unit}"
            return f"{sign}{x:.2f}{unit}"
    return f"{sign}{v:.0f}"


def pct(part: Optional[float], whole: Optional[float] = None, digits: int = 0) -> str:
    if part is None:
        return "—"
    if whole is not None:
        if not whole:
            return "—"
        part = 100.0 * part / whole
    return f"{part:.{digits}f}%"


def clock(ms: Optional[float], precise: bool = False) -> str:
    """毫秒 -> m:ss（或 m:ss.s）。分钟数可超过 60。"""
    if ms is None:
        return "—"
    neg = ms < 0
    ms = abs(ms)
    if precise:
        tenths = int(round(ms / 100.0))
        s, t = divmod(tenths, 10)
        m, s = divmod(s, 60)
        out = f"{m}:{s:02d}.{t}"
    else:
        total = int(ms // 1000)
        m, s = divmod(total, 60)
        out = f"{m}:{s:02d}"
    return ("-" if neg else "") + out


def secs(ms: Optional[float], digits: int = 1) -> str:
    if ms is None:
        return "—"
    return f"{ms / 1000.0:.{digits}f}s"


def parse_clock(text: str) -> float:
    """'12:34' / '12:34.5' / '754' / '754.5s' -> 毫秒。"""
    t = text.strip().lower()
    if t.endswith("s"):
        t = t[:-1]
    sign = -1 if t.startswith("-") else 1
    if t.startswith(("+", "-")):
        t = t[1:]
    try:
        if t.startswith(("+", "-")):
            raise ValueError
        parts = [float(p) for p in t.split(":")]
        if (not parts or len(parts) > 3 or any(not math.isfinite(p) or p < 0 for p in parts)
                or any(p >= 60 for p in parts[1:])
                or any(not p.is_integer() for p in parts[:-1])):
            raise ValueError
        total = 0.0
        for p in parts:
            total = total * 60 + p
        result = sign * total * 1000.0
        if not math.isfinite(result):
            raise ValueError
        return result
    except ValueError:
        raise ValueError(f"无效时间：{text}；请使用 12:34.5 或秒数。") from None


def limit_output(text: str, limit: int = 6000) -> str:
    """限制终端数据输出，尽量在完整行处截断并保留明确提示。"""
    if len(text) <= limit:
        return text
    note = f"\n…（输出已截断，原共 {len(text)} 字符；请缩小 --top/--detail，或用 events --from/--to 分段查看）"
    head = text[:limit - len(note)]
    if "\n" in head:
        head = head.rsplit("\n", 1)[0]
    return head + note


def cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    rows = list(rows)
    if not rows:
        return "（无）"
    out = ["| " + " | ".join(cell(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(cell(v) for v in row) + " |")
    return "\n".join(out)


def median(values: Sequence[float]) -> Optional[float]:
    vals = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return statistics.median(vals) if vals else None


def join_limited(items: List[str], limit: int, sep: str = "、") -> str:
    if len(items) <= limit:
        return sep.join(items)
    return sep.join(items[:limit]) + f"{sep}…(+{len(items) - limit})"


def ability_label(name: Optional[str], gid: Any) -> str:
    return f"{name or '未知技能'}({gid})"
