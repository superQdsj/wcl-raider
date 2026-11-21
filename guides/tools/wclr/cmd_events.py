"""events 命令：原始事件钻取。"""
from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from . import data, fmt
from .api import WCLError
from .context import Run, esc

TYPES = {
    # 名称: (dataType, hostilityType, 玩家过滤看 target 还是 source)
    "damage-taken": ("DamageTaken", "Friendlies", "target"),
    "damage-done": ("DamageDone", "Friendlies", "source"),
    "healing": ("Healing", "Friendlies", "target"),
    "casts": ("Casts", "Friendlies", "source"),
    "enemy-casts": ("Casts", "Enemies", "source"),
    "buffs": ("Buffs", "Friendlies", "target"),
    "debuffs": ("Debuffs", "Friendlies", "target"),
    "deaths": ("Deaths", "Friendlies", "target"),
    "interrupts": ("Interrupts", "Friendlies", "source"),
    "dispels": ("Dispels", "Friendlies", "source"),
    "all": ("All", "Friendlies", "either"),
}

LABEL = {
    "damage": "伤害", "heal": "治疗", "absorbed": "吸收", "cast": "施法", "begincast": "读条",
    "applybuff": "获得增益", "removebuff": "增益消失", "refreshbuff": "刷新增益", "applybuffstack": "增益叠层",
    "removebuffstack": "增益减层", "applydebuff": "获得减益", "removedebuff": "减益消失", "refreshdebuff": "刷新减益",
    "applydebuffstack": "减益叠层", "removedebuffstack": "减益减层", "interrupt": "打断", "dispel": "驱散",
    "death": "死亡", "resurrect": "复活", "summon": "召唤", "energize": "回能", "resourcechange": "资源变化",
    "removebuffstack ": "增益减层", "healabsorbed": "治疗被吸收", "extraattacks": "额外攻击",
}


def _ensure_v1_abilities(run: Run) -> None:
    if not (getattr(run.client, "use_v1", False) is True):
        return
    for view, params in (
        ("damage-taken", {"by": "ability"}),
        ("casts", {"by": "ability"}),
        ("casts", {"by": "ability", "hostility": 1}),
    ):
        tbl = run.client.v1_get(
            f"report/tables/{view}/{run.code}",
            {"start": int(run.start), "end": int(run.end), "translate": "true", **params},
            ttl=run.ttl,
        ) or {}
        for e in tbl.get("entries") or []:
            gid = e.get("guid")
            if gid is not None:
                run.abilities.setdefault(int(gid), {"gameID": int(gid), "name": e.get("name")})


def _ability_ids(run: Run, query: str) -> List[int]:
    q = query.strip()
    if q.isdigit():
        return [int(q)]
    ids = [gid for gid, a in run.abilities.items() if q.lower() in (a.get("name") or "").lower()]
    if not ids and getattr(run.client, "use_v1", False) is True:
        _ensure_v1_abilities(run)
        ids = [gid for gid, a in run.abilities.items() if q.lower() in (a.get("name") or "").lower()]
    if not ids:
        raise WCLError(f"本场找不到名称包含 '{query}' 的技能。")
    if len(ids) > 30:
        raise WCLError(f"名称 '{query}' 匹配 {len(ids)} 个技能 ID，请缩小名称范围或指定技能 ID。")
    return ids


def _line(run: Run, e: Dict[str, Any]) -> str:
    typ = e.get("type") or "?"
    ts = e.get("timestamp") or 0
    src = run.actor_name(e.get("sourceID"), e.get("sourceInstance"))
    tgt = run.actor_name(e.get("targetID"), e.get("targetInstance")) if e.get("targetID") not in (None, -1) else ""
    ab = fmt.ability_label(run.ab(e["abilityGameID"]), e["abilityGameID"]) if e.get("abilityGameID") else ""
    head = f"{run.t(ts, True)} {run.pull_tag(ts)} {LABEL.get(typ, typ)}"
    if typ == "damage":
        extra = []
        if e.get("absorbed"):
            extra.append(f"吸收{fmt.num(e['absorbed'])}")
        if e.get("overkill"):
            extra.append(f"过量{fmt.num(e['overkill'])}")
        if e.get("hitType") == 2:
            extra.append("暴击")
        if e.get("tick"):
            extra.append("跳")
        hp = ""
        if e.get("maxHitPoints"):
            hp = f" 剩{100.0 * (e.get('hitPoints') or 0) / e['maxHitPoints']:.0f}%"
        return f"{head} {src} → {tgt} {ab} {fmt.num(e.get('amount') or 0)}" + (f"（{'，'.join(extra)}）" if extra else "") + hp
    if typ == "heal":
        oh = f"（过量{fmt.num(e['overheal'])}）" if e.get("overheal") else ""
        return f"{head} {src} → {tgt} {ab} {fmt.num(e.get('amount') or 0)}{oh}"
    if typ == "absorbed":
        attacker = run.actor_name(e.get("attackerID"), e.get("attackerInstance"))
        return (f"{head} {ab}（{src}）为 {tgt} 吸收了 {attacker} 的 {run.ab(e.get('extraAbilityGameID'))} "
                f"{fmt.num(e.get('amount') or 0)}")
    if typ in ("interrupt", "dispel"):
        return f"{head} {src} → {tgt} 用 {ab} {'打断' if typ == 'interrupt' else '驱散'}了 {run.ab(e.get('extraAbilityGameID'))}"
    if typ == "death":
        killer = run.actor_name(e.get("killerID"), e.get("killerInstance")) if e.get("killerID") else "?"
        return f"{head} {tgt or src}（致死：{run.ab(e.get('killingAbilityGameID'))} ← {killer}）"
    if "stack" in typ:
        return f"{head} {ab} {src} → {tgt} 层数{e.get('stack')}"
    return f"{head} {src}" + (f" → {tgt}" if tgt else "") + (f" {ab}" if ab else "")


def cmd_events(run: Run, args: argparse.Namespace) -> str:
    kind = (args.type or "all").lower()
    if kind not in TYPES:
        raise WCLError(f"未知事件类型 {kind}；可选：{' | '.join(TYPES)}")
    data_type, hostility, side = TYPES[kind]
    start, end = run.start, run.end
    if args.pull:
        pull = next((p for p in run.pulls if p.idx == args.pull), None)
        if not pull:
            raise WCLError(f"没有第 {args.pull} 波（共 {len(run.pulls)} 波）。")
        start, end = pull.start - 3000, pull.end + 1000
    try:
        if args.t_from:
            start = run.start + fmt.parse_clock(args.t_from)
        if args.t_to:
            end = run.start + fmt.parse_clock(args.t_to)
    except ValueError as exc:
        raise WCLError(str(exc)) from None
    start, end = max(start, run.start), min(end, run.end)
    if end <= start:
        raise WCLError("结束时间必须晚于开始时间。")
    conds = []
    if args.player:
        p = run.find_player(args.player)
        n = esc(p.name)
        if side == "target":
            conds.append(f'target.name = "{n}"')
        elif side == "source":
            conds.append(f'source.name = "{n}"')
        else:
            conds.append(f'(source.name = "{n}" or target.name = "{n}")')
    if args.target:
        conds.append(f'target.name = "{esc(args.target)}"')
    if args.ability:
        ids = _ability_ids(run, args.ability)
        conds.append("ability.id in (%s)" % ", ".join(str(i) for i in ids))
    if args.filter:
        conds.append(f"({args.filter})")
    expr = " and ".join(conds)
    want_hp = kind in ("damage-taken", "all")
    evs, truncated = data.events(run, data_type=data_type, start=start, end=end, hostility=hostility, expr=expr,
                                 limit=max(1, args.limit), include_resources=want_hp)
    direction = "（玩家双向过滤：施放或承受）" if args.player and kind == "all" else ""
    lines = [f"# 事件 {kind}{direction} {run.t(start, True)}–{run.t(end, True)}" + (f" 过滤：{expr}" if expr else "") +
             f" — {run.header()}"]
    if not evs:
        lines.append("（没有匹配的事件）")
        return "\n".join(lines)
    shown = evs[: args.limit]
    lines += [_line(run, e) for e in shown]
    if truncated or len(evs) > len(shown):
        lines.append(f"…（**输出被截断**：只显示了前 {args.limit} 条，到 {run.t(shown[-1]['timestamp'], True)} 为止。"
                     f"加 `--limit {max(1000, args.limit * 4)}`，或者缩小时间窗口、加 `--type`/`--player` 过滤后再查。"
                     "被截断的窗口不能用来判断\"某个技能没交\"。）")
    return "\n".join(lines)
