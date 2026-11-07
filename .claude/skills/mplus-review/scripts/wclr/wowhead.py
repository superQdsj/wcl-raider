"""Wowhead 技能资料：名称、驱散类型、说明文字、冷却与充能（tooltip 接口，磁盘缓存 30 天）。"""
from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Iterable, Optional

from .api import DAY, http_json

TOOLTIP_URL = "https://nether.wowhead.com/tooltip/spell/{gid}?dataEnv=1&locale={locale}"
LOCALES = {"zh": 4, "en": 0}

# 减益右上角的驱散类型（中/英）→ 统一中文标签
DISPEL_LABELS = {
    "magic": "魔法", "魔法": "魔法",
    "poison": "中毒", "中毒": "中毒",
    "curse": "诅咒", "诅咒": "诅咒",
    "disease": "疾病", "疾病": "疾病",
    "enrage": "激怒", "激怒": "激怒",
    "bleed": "流血", "流血": "流血",
}

_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.I)
_TH = re.compile(r"<th[^>]*>(.*?)</th>", re.I | re.S)


def _text(fragment: str) -> str:
    text = _BR.sub("\n", fragment or "")
    text = _TAG.sub("", text)
    text = html.unescape(text).replace("​", "")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def parse_tooltip(payload: Dict[str, Any]) -> Dict[str, Any]:
    """把 tooltip JSON 拆成 {name, dispel, description, aura}。"""
    tip = payload.get("tooltip") or ""
    buff = payload.get("buff") or ""
    dispel = None
    for raw in _TH.findall(buff) + _TH.findall(tip):
        label = DISPEL_LABELS.get(_text(raw).strip().lower())
        if label:
            dispel = label
            break
    # 说明在 class="q" 的 div 里；没有时退回整段 tooltip 文本
    desc_parts = re.findall(r'<div class="q[^"]*">(.*?)</div>', tip, re.S)
    desc = _text(" ".join(desc_parts)) if desc_parts else _text(tip)
    aura = _text(buff)
    if payload.get("name") and aura.startswith(payload["name"]):
        aura = aura[len(payload["name"]):].strip()
    for raw in _TH.findall(buff):
        label = _text(raw).strip()
        if label and aura.startswith(label):
            aura = aura[len(label):].strip()
    cooldown, charges, mods = parse_cooldown(tip)
    return {"name": payload.get("name"), "dispel": dispel, "description": desc, "aura": aura,
            "duration_ms": parse_duration(aura), "icon": payload.get("icon"),
            "cooldown_ms": cooldown, "charges": charges, "cooldown_mods": mods}


_DUR = [
    (re.compile(r"持续\s*(\d+(?:\.\d+)?)\s*秒"), 1000), (re.compile(r"持续\s*(\d+(?:\.\d+)?)\s*分钟"), 60000),
    (re.compile(r"(\d+(?:\.\d+)?)\s*seconds? remaining", re.I), 1000),
    (re.compile(r"(\d+(?:\.\d+)?)\s*min(?:ute)?s? remaining", re.I), 60000),
]


_TIME = re.compile(r"(\d+(?:\.\d+)?)\s*(秒|分钟|小时|sec|min|hr|hour)", re.I)
_TIME_UNIT = {"秒": 1000, "sec": 1000, "分钟": 60000, "min": 60000, "小时": 3600000, "hr": 3600000, "hour": 3600000}


def _time_ms(text: str) -> Optional[float]:
    m = _TIME.search((text or "").replace("\u200b", ""))
    return float(m.group(1)) * _TIME_UNIT[m.group(2).lower()] if m else None


def parse_cooldown(tip: str):
    """tooltip 里的基础冷却、充能次数和天赋改写后的冷却。

    Wowhead 把它们写在注释里：<!--baseCooldown:25 秒 冷却-->、<!--baseCharges:1 次充能-->，
    天赋改写写成 <!--cooldown:<天赋技能ID>:3.5分钟冷却时间-->（点了该天赋后的冷却）。
    返回 (cooldown_ms, charges, {天赋技能ID: cooldown_ms})；没有冷却的技能返回 (None, None, {})。
    """
    tip = (tip or "").replace("\u200b", "")
    base = re.search(r"<!--baseCooldown:(.*?)-->", tip) or re.search(r"<!--cooldownText-->(.*?)<!--cooldownText-->", tip)
    charges = re.search(r"<!--baseCharges:(\d+)", tip)
    mods = {}
    for spell_id, text in re.findall(r"<!--cooldown:(\d+):(.*?)-->", tip):
        value = _time_ms(text)
        if value:
            mods[int(spell_id)] = value
    return (_time_ms(base.group(1)) if base else None), (int(charges.group(1)) if charges else None), mods


def parse_duration(aura: str) -> Optional[float]:
    """减益效果文字里的剩余时间（"持续14秒" / "14 seconds remaining"）-> 毫秒。"""
    for rx, unit in _DUR:
        m = rx.search(aura or "")
        if m:
            return float(m.group(1)) * unit
    return None


def spell(gid: int, lang: str = "zh") -> Optional[Dict[str, Any]]:
    """单个技能资料；网络失败或 Wowhead 没有该技能时返回 None。"""
    try:
        gid = int(gid)
    except (TypeError, ValueError):
        return None
    if gid <= 1:
        return None
    payload = http_json(TOOLTIP_URL.format(gid=gid, locale=LOCALES.get(lang, 4)), ttl=30 * DAY)
    if not isinstance(payload, dict) or not payload.get("name"):
        return None
    info = parse_tooltip(payload)
    info["id"] = gid
    return info


def spells(gids: Iterable[int], lang: str = "zh", workers: int = 6) -> Dict[int, Dict[str, Any]]:
    """并行获取多个技能资料，失败的不出现在结果里。"""
    ids = sorted({int(g) for g in gids if g and int(g) > 1})
    if not ids:
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(workers, len(ids))) as pool:
        for gid, info in zip(ids, pool.map(lambda g: spell(g, lang), ids)):
            if info:
                out[gid] = info
    return out


# 按说明文字给未知的玩家技能归类（顺序即优先级）。只用于标注和筛选，输出里标"据 Wowhead 说明推断"。
_RULES = [
    ("免疫", ("免疫", "immune", "immunity")),
    ("反射", ("反射", "reflect")),
    ("自解", ("移除", "驱散", "解除", "清除", "remove", "dispel", "cleanse")),
    ("解控", ("定身", "减速效果", "移动限制", "昏迷效果", "恐惧效果", "snare", "root", "movement impairing",
              "loss of control")),
    ("减伤", ("受到的伤害降低", "伤害降低", "伤害减少", "吸收", "damage taken reduced", "reduces damage taken",
              "absorb", "avoid")),
    ("控制", ("昏迷", "击退", "恐惧", "瘫痪", "迷惑", "沉默", "打断", "stun", "knock", "fear", "incapacitat",
              "disorient", "silence", "interrupt")),
    ("位移", ("移动速度提高", "移动速度提升", "跃", "冲向", "传送", "movement speed increased",
              "increases your movement speed", "leap", "teleport", "charge")),
    ("爆发", ("伤害提高", "急速提高", "暴击几率提高", "全能提高", "精通提高", "主属性", "damage increased",
              "increases your damage", "haste", "critical strike", "versatility", "mastery")),
    ("治疗", ("治疗", "恢复", "heal", "restore")),
    ("伤害", ("伤害", "damage")),
]


def classify(info: Optional[Dict[str, Any]]) -> Optional[str]:
    if not info:
        return None
    text = ((info.get("description") or "") + " " + (info.get("aura") or "")).lower()
    if "[item effect]" in text or "[物品效果]" in text:  # 装备/消耗品触发的技能，不是职业技巧
        return "消耗品" if any(w in text for w in ("饮用", "药水", "potion", "drink", "flask", "合剂")) else "饰品"
    for cat, words in _RULES:
        if any(w in text for w in words):
            return cat
    return None
