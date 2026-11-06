"""damage 命令：按敌方技能的我方承伤、命中次数、每人分布与描述性标记。"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Tuple

from . import data, fmt
from .api import WCLError
from .context import Run


def _hits(e: Dict[str, Any]) -> Tuple[int, int]:
    return int(e.get("hitCount") or 0), int(e.get("tickCount") or 0)


def merge_damage_segments(events: List[Dict[str, Any]], gap_ms: float = 2500) -> Dict[int, List[Dict[str, Any]]]:
    """同一玩家相邻命中/跳间隔不超过 gap_ms 时合并；伤害含吸收、不含过量。"""
    per: Dict[int, List[Dict[str, Any]]] = {}
    for event in sorted(events, key=lambda item: item.get("timestamp", 0)):
        if event.get("fake") or event.get("type") != "damage" or event.get("targetID") is None:
            continue
        timestamp = event["timestamp"]
        segments = per.setdefault(event["targetID"], [])
        if not segments or timestamp - segments[-1]["end"] > gap_ms:
            segments.append({"start": timestamp, "end": timestamp, "hits": 0, "ticks": 0,
                             "damage": 0, "timestamps": []})
        segment = segments[-1]
        segment["end"] = timestamp
        segment["ticks" if event.get("tick") else "hits"] += 1
        segment["damage"] += (event.get("amount") or 0) + (event.get("absorbed") or 0)
        segment["timestamps"].append(timestamp)
    return per


def per_player_taken(run: Run) -> Dict[int, Dict[int, Dict[str, Any]]]:
    """{玩家ID: {技能ID: 条目}}（每人一张承伤表，可得到每人命中次数）。"""
    tasks = {str(pid): (lambda pid=pid: data.damage_taken(run, player=pid)) for pid in run.players}
    got = data.parallel(tasks, workers=5)
    out: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for pid_s, tbl in got.items():
        m: Dict[int, Dict[str, Any]] = {}
        for e in tbl.get("entries") or []:
            gid = int(e.get("guid") or 0)
            if gid in m:  # 同一技能多来源时合并
                for k in ("total", "hitCount", "tickCount", "uses"):
                    m[gid][k] = (m[gid].get(k) or 0) + (e.get(k) or 0)
            else:
                m[gid] = dict(e)
        out[int(pid_s)] = m
    return out


def _flags(run: Run, total: float, dist: List[Tuple[int, float, int]]) -> str:
    """dist: [(玩家ID, 伤害, 命中+跳)]。仅描述分布形态，不做"可躲/不可躲"的结论。"""
    if total <= 0:
        return ""
    tanks = {pid for pid, p in run.players.items() if p.role == "tank"}
    tank_share = sum(d for pid, d, _ in dist if pid in tanks) / total
    hit_players = [(pid, d) for pid, d, _ in dist if d > 0]
    flags = []
    if tank_share >= 0.9:
        flags.append("仅坦克" if all(pid in tanks for pid, _ in hit_players) else f"坦克占{tank_share * 100:.0f}%")
    else:
        non_tank = [(pid, d) for pid, d, _ in dist if pid not in tanks]
        shares = [d / total for _, d in non_tank]
        if len(hit_players) == len(run.players) and len(hit_players) >= 2:
            vals = [d for _, d in hit_players]
            if min(vals) > 0 and max(vals) / min(vals) <= 3:
                flags.append("全员承伤接近")
        if shares:
            med = statistics.median(shares)
            for pid, d in non_tank:
                share = d / total
                if share >= 0.35 and share >= 2 * max(med, 0.01) and len(hit_players) >= 2:
                    flags.append(f"集中:{run.players[pid].name}{share * 100:.0f}%")
        if len(hit_players) == 1 and hit_players[0][0] not in tanks:
            flags.append(f"只打中:{run.players[hit_players[0][0]].name}")
    return " ".join(flags)


def cmd_damage(run: Run, top: int = 25, melee: bool = False, ability: Optional[str] = None) -> str:
    if ability:
        return _ability_detail(run, ability)
    got = data.parallel({"group": lambda: data.damage_taken(run), "per": lambda: per_player_taken(run)})
    entries = [e for e in got["group"].get("entries") or [] if (e.get("total") or 0) > 0]
    per = got["per"]
    grand = sum(e.get("total") or 0 for e in entries)
    melee_e = [e for e in entries if int(e.get("guid") or 0) == 1]
    lines = [f"# 承伤（伤害来源 → 我方，含自伤与环境）— {run.header()}"]
    if not entries:
        lines.append("没有承伤数据。")
        return "\n".join(lines)
    tanks = [p for p in run.players.values() if p.role == "tank"]
    if melee_e:
        mt = sum(e.get("total") or 0 for e in melee_e)
        tank_melee = sum((per.get(p.id, {}).get(1) or {}).get("total") or 0 for p in tanks)
        lines.append(f"总承伤 {fmt.num(grand)}；其中近战 {fmt.num(mt)}（{fmt.pct(mt, grand)}，坦克承受其中 {fmt.pct(tank_melee, mt)}）"
                     + ("" if melee else "，下表默认不含近战（--melee 显示）") + "。")
    else:
        lines.append(f"总承伤 {fmt.num(grand)}。")
    per_totals = {pid: sum(e.get("total") or 0 for e in m.values()) for pid, m in per.items()}
    lines.append("每人总承伤：" + "；".join(
        f"{run.players[pid].name} {fmt.num(v)}" for pid, v in sorted(per_totals.items(), key=lambda kv: -kv[1])))

    shown = [e for e in sorted(entries, key=lambda e: -(e.get("total") or 0))
             if melee or int(e.get("guid") or 0) != 1][:top]
    rows = []
    for e in shown:
        gid = int(e.get("guid") or 0)
        total = float(e.get("total") or 0)
        hits, ticks = _hits(e)
        uses = e.get("uses")
        dist = []
        for pid in run.players:
            pe = per.get(pid, {}).get(gid)
            if pe:
                h, t = _hits(pe)
                dist.append((pid, float(pe.get("total") or 0), h + t))
            else:
                dist.append((pid, 0.0, 0))
        dist_sorted = sorted([d for d in dist if d[1] > 0], key=lambda d: -d[1])
        dist_txt = " ".join(f"{run.players[pid].name}{fmt.pct(d, total)}/{n}" for pid, d, n in dist_sorted[:5])
        per_cast = f"{hits / uses:.1f}" if uses and hits else "—"
        src = e.get("actorName") or "—"
        rows.append([fmt.ability_label(e.get("name") or run.ab(gid), gid), src, fmt.num(total), fmt.pct(total, grand, 1),
                     uses if uses else "—", f"{hits}/{ticks}", per_cast, dist_txt, _flags(run, total, dist)])
    lines += ["", f"## 按技能（前 {len(rows)} 个）",
              fmt.table(["技能", "来源", "伤害", "占比", "来源施放", "命中/跳", "每次施放命中", "承受分布(伤害%/命中+跳)", "分布标记"],
                        rows),
              "说明：命中=直接伤害次数，跳=周期伤害次数；每次施放命中=命中/敌方施放（为次数比，受目标数、重复命中与路线影响）；"
              "分布标记只描述谁在承受，是否可躲请结合技能机制与 `compare` 判断。"]
    return "\n".join(lines)


def _match_abilities(run: Run, query: str) -> List[int]:
    q = query.strip()
    if q.isdigit():
        return [int(q)]
    ql = q.lower()
    ids = [gid for gid, a in run.abilities.items() if ql in (a.get("name") or "").lower()]
    if not ids:
        raise WCLError(f"本场找不到名称包含 '{query}' 的技能。")
    if len(ids) > 20:
        raise WCLError(f"名称 '{query}' 匹配 {len(ids)} 个技能 ID，请缩小名称范围或指定技能 ID。")
    return ids


def _ability_detail(run: Run, query: str) -> str:
    ids = _match_abilities(run, query)
    expr = "ability.id in (%s)" % ", ".join(str(i) for i in ids)
    evs, truncated = data.events(run, data_type="DamageTaken", expr=expr, limit=5000)
    evs = [e for e in evs if e.get("type") == "damage" and e.get("targetID") in run.players]
    names = "、".join(sorted({run.ab(i) for i in ids}))
    lines = [f"# 技能承伤明细：{names}（{', '.join(str(i) for i in ids)}）— {run.header()}"]
    if not evs:
        lines.append("本场没有队员受到该技能伤害。")
        return "\n".join(lines)
    per: Dict[int, Dict[str, Any]] = {}
    by_pull: Dict[str, Dict[int, int]] = {}
    for e in evs:
        pid = e["targetID"]
        st = per.setdefault(pid, {"n": 0, "dmg": 0.0, "ticks": 0, "max": 0.0})
        amt = (e.get("amount") or 0) + (e.get("absorbed") or 0)
        st["n"] += 0 if e.get("tick") else 1
        st["ticks"] += 1 if e.get("tick") else 0
        st["dmg"] += amt
        st["max"] = max(st["max"], amt)
        tag = run.pull_tag(e["timestamp"])
        by_pull.setdefault(tag, {})
        by_pull[tag][pid] = by_pull[tag].get(pid, 0) + 1
    rows = [[run.players[pid].label, st["n"], st["ticks"], fmt.num(st["dmg"]), fmt.num(st["max"])]
            for pid, st in sorted(per.items(), key=lambda kv: -kv[1]["dmg"])]
    lines += [fmt.table(["玩家", "命中", "跳", "伤害+吸收(不含过量)", "单次最大"], rows), "", "## 按波次（每人被打中的次数，含跳）"]
    prow = []
    for tag, m in by_pull.items():
        prow.append([tag, " ".join(f"{run.players[pid].name}×{n}" for pid, n in sorted(m.items(), key=lambda kv: -kv[1]))])
    lines.append(fmt.table(["波次", "命中"], prow))
    segments = merge_damage_segments(evs)
    lines += ["", "## 受伤段（同一玩家相邻命中/跳间隔 ≤ 2.5 秒合并，每人最多 8 段，按时间排序）"]
    for player_id, player_segments in segments.items():
        segment_rows = []
        for segment in player_segments[:8]:
            tags = list(dict.fromkeys(run.pull_tag(timestamp) for timestamp in segment["timestamps"]))
            segment_rows.append([f"{run.t(segment['start'], True)}–{run.t(segment['end'], True)}",
                                 f"{segment['ticks']}/{segment['hits']}", fmt.num(segment["damage"]), "、".join(tags)])
        lines += [f"### {run.players[player_id].label}", fmt.table(["时间", "跳数/命中数", "伤害合计+吸收（不含过量）", "所在波次"], segment_rows)]
        if len(player_segments) > 8:
            lines.append(f"（其余 {len(player_segments) - 8} 段略）")
    direct = [e for e in evs if not e.get("tick")]
    if direct:
        lines += ["", "## 直接命中时间点（前 40 条）"]
        items = [f"{run.t(e['timestamp'], True)} {run.players[e['targetID']].name} {fmt.num((e.get('amount') or 0) + (e.get('absorbed') or 0))}"
                 for e in direct[:40]]
        lines.append("；".join(items))
    if truncated:
        lines.append("（事件过多已截断）")
    return "\n".join(lines)
