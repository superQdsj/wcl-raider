"""interrupts 命令：敌方读条的打断率、漏断时间点；每人打断、打断技能浪费。"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import data, fmt
from .api import WCLError
from .context import Run

# 纯打断技能（用于计算"施放了但没打断到"）。ID 不存在于本场日志时自动忽略。
KICK_SPELLS = {
    1766: "Kick", 6552: "Pummel", 2139: "Counterspell", 47528: "Mind Freeze", 96231: "Rebuke",
    57994: "Wind Shear", 106839: "Skull Bash", 78675: "Solar Beam", 147362: "Counter Shot",
    187707: "Muzzle", 116705: "Spear Hand Strike", 183752: "Disrupt", 351338: "Quell", 15487: "Silence",
    19647: "Spell Lock", 119910: "Spell Lock", 132409: "Spell Lock", 89766: "Axe Toss", 119914: "Axe Toss",
    386071: "Disrupting Shout",
}

_TRAILING_NUM = re.compile(r"\s+\d+$")


# 打断事件计为纯打断、但平时主要用于伤害的技能（不计入"打断技能施放"）：复仇之盾
INTERRUPT_CAPABLE_ATTACKS = {31935: "Avenger's Shield"}


def split_interrupts(abilities: List[Dict[str, Any]], total: int,
                     kick_names: Iterable[str] = ()) -> Tuple[int, int]:
    """按技能 ID 拆分成功打断；无 ID 的 WCL 汇总项用已知同名纯打断识别。"""
    names = set(KICK_SPELLS.values()) | set(INTERRUPT_CAPABLE_ATTACKS.values()) | set(kick_names)
    pure = sum(ability.get("total") or 0 for ability in abilities
               if (int(ability.get("guid") or ability.get("id") or 0) in KICK_SPELLS
                   or int(ability.get("guid") or ability.get("id") or 0) in INTERRUPT_CAPABLE_ATTACKS
                   or (not (ability.get("guid") or ability.get("id")) and ability.get("name") in names)))
    pure = min(total, pure)
    return pure, total - pure


def inconsistent_counts(begun: int, interrupted: int, completed: int) -> bool:
    """汇总口径冲突时，该行打断率不可靠；允许合计 5% 的误差。"""
    return interrupted > begun or (interrupted + completed) * 100 > begun * 105


def estimate_capacity(duration_ms: float, shortest_intervals: Iterable[Optional[float]]) -> float:
    """按波次时长 / 各玩家实测最短纯打断间隔求和；缺失或零间隔不参与。"""
    return sum(max(0, duration_ms) / interval for interval in shortest_intervals if interval is not None and interval > 0)


def enemy_cast_counts(events: List[Dict[str, Any]], ability_ids: Iterable[int]) -> Dict[int, Tuple[int, int]]:
    """每技能返回读条次数、不同施法单位数；有 begincast 时不重复算完成的 cast。"""
    counts = {}
    for ability_id in ability_ids:
        relevant = [event for event in events if not event.get("fake") and event.get("abilityGameID") == ability_id]
        beginnings = [event for event in relevant if event.get("type") == "begincast"]
        casts = beginnings or [event for event in relevant if event.get("type") == "cast"]
        actors = {(event.get("sourceID"), event.get("sourceInstance") or 1) for event in casts}
        counts[ability_id] = (len(casts), len(actors))
    return counts


def _caster_names(entry: Dict[str, Any]) -> List[str]:
    names: Dict[str, int] = {}
    for m in entry.get("missedCasts") or []:
        n = _TRAILING_NUM.sub("", m.get("name") or "")
        if n:
            names[n] = names.get(n, 0) + 1
    for d in entry.get("details") or []:
        for a in d.get("actors") or []:
            n = _TRAILING_NUM.sub("", a.get("name") or "")
            if n:
                names[n] = names.get(n, 0) + (a.get("total") or 0)
    return [n for n, _ in sorted(names.items(), key=lambda kv: -kv[1])]


def cmd_interrupts(run: Run, times: int = 8, pull: Optional[int] = None) -> str:
    selected_pull = next((item for item in run.pulls if item.idx == pull), None) if pull is not None else None
    if pull is not None and selected_pull is None:
        raise WCLError(f"没有第 {pull} 波（共 {len(run.pulls)} 波）。")
    kick_ids = [k for k in KICK_SPELLS if k in run.abilities]
    tasks = {"table": lambda: data.interrupts(run), "disp": lambda: data.dispels(run)}
    if selected_pull:
        tasks["table"] = lambda: data.window_table(run, "Interrupts", selected_pull.start, selected_pull.end)
        tasks["disp"] = lambda: data.window_table(run, "Dispels", selected_pull.start, selected_pull.end)
        tasks["enemy"] = lambda: data.events(run, data_type="Casts", hostility="Enemies",
                                            start=selected_pull.start, end=selected_pull.end, limit=20000)
    if kick_ids:
        expr = "type = \"cast\" and ability.id in (%s)" % ", ".join(str(k) for k in kick_ids)
        tasks["kicks"] = lambda: data.events(run, data_type="Casts", expr=expr, limit=20000)
    got = data.parallel(tasks)
    entries = data.interrupt_entries(got["table"])
    lines = [f"# 打断 — {run.header()}"]
    if selected_pull:
        lines.append(f"范围：第 {selected_pull.idx} 波 {run.t(selected_pull.start, True)}–{run.t(selected_pull.end, True)}"
                     f"（{fmt.clock(selected_pull.dur, True)}）；打断与驱散表均限定为该波。")
    if not entries:
        lines.append(("本波" if selected_pull else "本场") + "没有任何敌方技能被打断过（或 WCL 未记录打断）。")
    total_begun = sum(e.get("spellsBegun") or 0 for e in entries)
    total_kicked = sum((e.get("spellsInterrupted") or 0) + (e.get("spellChannelsInterrupted") or 0) for e in entries)
    total_done = sum(e.get("spellsCompleted") or 0 for e in entries)
    if entries:
        lines.append(
            f"被打断过至少 1 次的敌方技能 {len(entries)} 个（从未被打断过的可打断技能不会出现在此表，"
            f"需用 `compare` 对照高分记录）。合计读条 {total_begun} 次 → 打断 {total_kicked}"
            f"（{fmt.pct(total_kicked, total_begun)}），读完 {total_done}（{fmt.pct(total_done, total_begun)}），"
            f"其他中止 {max(0, total_begun - total_kicked - total_done)}（控制/击杀/读条中目标死亡等）。")
    rows = []
    entries.sort(key=lambda e: -(e.get("spellsCompleted") or 0))
    for e in entries:
        begun = e.get("spellsBegun") or 0
        kicked = (e.get("spellsInterrupted") or 0) + (e.get("spellChannelsInterrupted") or 0)
        done = e.get("spellsCompleted") or 0
        other = max(0, begun - kicked - done)
        # missedCasts 的 timestamp 是相对战斗开始的毫秒，换算成报告时间
        missed = sorted(run.start + (m.get("timestamp") or 0) for m in e.get("missedCasts") or [])
        when = [f"{run.t(ts)}({run.pull_tag(ts)})" for ts in missed[:times]]
        dist: Dict[str, int] = {}
        for ts in missed:
            tag = run.pull_tag(ts)
            dist[tag] = dist.get(tag, 0) + 1
        when_txt = " ".join(when)
        if len(missed) > times:
            when_txt += f" …共{len(missed)}次"
        if len(dist) > 1:
            when_txt += "；按波次 " + " ".join(f"{k}×{v}" for k, v in dist.items())
        rows.append([fmt.ability_label(run.ab(e.get("guid")), e.get("guid")),
                     fmt.join_limited(_caster_names(e), 2), begun, kicked, done, other,
                     fmt.pct(kicked, begun), "不一致" if inconsistent_counts(begun, kicked, done) else "", when_txt or "—"])
    if rows:
        lines += ["", "## 敌方读条（按读完次数排序）",
                  fmt.table(["技能", "施法者", "读条", "打断", "读完", "其他中止", "打断率", "计数", "读完的时间点（波次）"], rows),
                  "说明：打断 > 读条，或打断 + 读完 > 读条 × 1.05 时标为不一致；该行打断率不可靠。"]

    kick_names = {run.ab(ability_id) for ability_id in kick_ids}
    kick_names |= {run.ab(a) for a in INTERRUPT_CAPABLE_ATTACKS if a in run.abilities}
    per: Dict[int, Dict[str, Any]] = {}
    for e in entries:
        target_name = run.ab(e.get("guid"))
        for d in e.get("details") or []:
            pid = d.get("id")
            if pid not in run.players:
                pid = run.owner(pid) or pid
            st = per.setdefault(pid, {"total": 0, "pure": 0, "control": 0, "targets": {}, "methods": {}})
            st["total"] += d.get("total") or 0
            pure, control = split_interrupts(d.get("abilities") or [], d.get("total") or 0, kick_names)
            st["pure"] += pure
            st["control"] += control
            st["targets"][target_name] = st["targets"].get(target_name, 0) + (d.get("total") or 0)
            for a in d.get("abilities") or []:
                st["methods"][a.get("name")] = st["methods"].get(a.get("name"), 0) + (a.get("total") or 0)
    casts_by: Dict[int, Dict[int, int]] = {}
    kick_events, kick_truncated = got.get("kicks", ([], False))
    if kick_truncated:
        lines.append("（打断技能施放事件已截断，下表施放次数仅为已获取部分）")
    for ev in kick_events:
        if ev.get("type") != "cast" or ev.get("abilityGameID") not in KICK_SPELLS:
            continue
        if selected_pull and not selected_pull.start <= ev["timestamp"] <= selected_pull.end:
            continue
        pid = run.owner(ev.get("sourceID"))
        if pid is None:
            continue
        gid = ev.get("abilityGameID")
        casts_by.setdefault(pid, {})
        casts_by[pid][gid] = casts_by[pid].get(gid, 0) + 1

    prow = []
    for pid, p in run.players.items():
        st = per.get(pid, {"total": 0, "pure": 0, "control": 0, "targets": {}, "methods": {}})
        kc = casts_by.get(pid, {})
        kick_txt, wasted = [], 0
        by_name: Dict[str, int] = {}
        for gid, n in sorted(kc.items(), key=lambda kv: -kv[1]):
            name = run.ab(gid)
            kick_txt.append(f"{name}({gid}) {n}")
            by_name[name] = by_name.get(name, 0) + n
        for name, n in by_name.items():
            landed = st["methods"].get(name, 0)
            wasted += max(0, n - landed)
        targets = sorted(st["targets"].items(), key=lambda kv: -kv[1])
        methods = sorted(st["methods"].items(), key=lambda kv: -kv[1])
        prow.append([p.label, st["pure"], st["control"], "、".join(kick_txt) or "—", wasted if kc else "—",
                     fmt.join_limited([f"{k} {v}" for k, v in targets], 3),
                     fmt.join_limited([f"{k} {v}" for k, v in methods], 3)])
    lines += ["", "## 每人打断",
              fmt.table(["玩家", "纯打断", "控制打断", "打断技能施放", "施放−打断计数", "打断最多的技能", "打断手段"], prow),
              "说明：施放−打断计数按同名技能合并、每组下限为 0；这是汇总差值，范围控制可一次打断多人，不能等同于空断次数；"
              "打断手段里可能包含被 WCL 计为打断的控制技能（如击倒、致盲、恐惧）。"]
    if selected_pull:
        lines += _capacity_section(run, selected_pull, entries, kick_events, kick_truncated, got.get("enemy", ([], False)))
    dispel_lines = _dispel_section(run, got.get("disp") or {}, times)
    if selected_pull:
        dispel_lines = [line.replace("本场没有驱散记录", "本波没有驱散记录") for line in dispel_lines]
    lines += dispel_lines
    return "\n".join(lines)


def _capacity_section(run: Run, pull: Any, entries: List[Dict[str, Any]], kicks: List[Dict[str, Any]],
                      kicks_truncated: bool, enemy: Tuple[List[Dict[str, Any]], bool]) -> List[str]:
    ability_ids = [int(entry["guid"]) for entry in entries
                   if (entry.get("spellsInterrupted") or 0) + (entry.get("spellChannelsInterrupted") or 0) > 0]
    counts = enemy_cast_counts(enemy[0], ability_ids)
    rows = [[fmt.ability_label(run.ab(ability_id), ability_id), *counts[ability_id]] for ability_id in ability_ids]
    lines = ["", "## 打断容量（估算）", fmt.table(["本波被打断过的技能", "读条次数", "施法者数量（不同 instance）"], rows)]
    player_rows, intervals = [], []
    missing = []
    for player_id, player in run.players.items():
        timestamps = sorted(event["timestamp"] for event in kicks if not event.get("fake")
                            and event.get("type") == "cast" and event.get("abilityGameID") in KICK_SPELLS
                            and run.owner(event.get("sourceID")) == player_id)
        gaps = [later - earlier for earlier, later in zip(timestamps, timestamps[1:])]
        shortest = min(gaps) if gaps else None
        if shortest is None or shortest <= 0 or kicks_truncated:
            missing.append(player.name)
            intervals.append(None)
        else:
            intervals.append(shortest)
        count = sum(pull.start <= timestamp <= pull.end for timestamp in timestamps)
        player_rows.append([player.label, count, f"{shortest / 1000:.1f} 秒" if shortest is not None else "无法判定"])
    needed = sum(count for count, _ in counts.values())
    capacity = estimate_capacity(pull.dur, intervals)
    lines += [fmt.table(["玩家", "本波纯打断施放", "整场最短施放间隔（冷却上界）"], player_rows),
              f"容量估算 = Σ（本波时长 ÷ 各玩家最短间隔）= {capacity:.1f} 次；"
              f"本波需要打断的读条总数（仅本波被打断过的技能）= {needed} 次。",
              "说明：这只是估算，不是可保证的打断次数；最短间隔来自整场实测，是冷却的上界，"
              "未计起手是否可用、控制打断、充能、目标距离及多人技能重叠；同一玩家的纯打断合并计间隔。"
              "读条按 enemy-casts 的 begincast 统计，无起读事件时按 cast 统计，避免起读/完成重复计数。"]
    if missing:
        lines.append("以下玩家缺少可用间隔，未纳入估算：" + "、".join(missing) + "；不可将部分容量视为全队完整容量。")
    if kicks_truncated or enemy[1]:
        lines.append("（施法事件已截断，容量或读条数仅基于已获取部分，不能视为完整统计。）")
    return lines


def _dispel_section(run: Run, tbl: Dict[str, Any], times: int) -> List[str]:
    """驱散：WCL 驱散表与打断表同构——施加次数 / 被驱散 / 未驱散，以及谁用什么驱散。"""
    entries = data.interrupt_entries(tbl)
    if not entries:
        return ["", "## 驱散", "本场没有驱散记录（没有任何效果被驱散过；从未被驱散的可驱散减益不会出现在这里）。"]
    rows = []
    for e in sorted(entries, key=lambda x: -((x.get("spellsInterrupted") or 0) + (x.get("spellsCompleted") or 0))):
        applied = e.get("spellsBegun") or 0
        removed = (e.get("spellsInterrupted") or 0) + (e.get("spellChannelsInterrupted") or 0)
        kept = e.get("spellsCompleted") or 0
        who: Dict[str, int] = {}
        how: Dict[str, int] = {}
        hit: Dict[str, int] = {}
        for d in e.get("details") or []:
            pid = run.owner(d.get("id")) or d.get("id")
            name = run.players[pid].name if pid in run.players else (d.get("name") or "?")
            who[name] = who.get(name, 0) + (d.get("total") or 0)
            for a in d.get("abilities") or []:
                how[a.get("name")] = how.get(a.get("name"), 0) + (a.get("total") or 0)
            for a in d.get("actors") or []:
                hit[a.get("name")] = hit.get(a.get("name"), 0) + (a.get("total") or 0)
        missed = sorted(run.start + (m.get("timestamp") or 0) for m in e.get("missedCasts") or [])
        when = " ".join(f"{run.t(ts)}({run.pull_tag(ts)})" for ts in missed[:times])
        if len(missed) > times:
            when += f" …共{len(missed)}次"
        rows.append([fmt.ability_label(run.ab(e.get("guid")), e.get("guid")), applied, removed, kept,
                     fmt.join_limited([f"{k} {v}" for k, v in sorted(who.items(), key=lambda kv: -kv[1])], 3),
                     fmt.join_limited([f"{k} {v}" for k, v in sorted(how.items(), key=lambda kv: -kv[1])], 2),
                     fmt.join_limited([f"{k} {v}" for k, v in sorted(hit.items(), key=lambda kv: -kv[1])], 4),
                     when or "—"])
    return ["", "## 驱散（被驱散过至少 1 次的效果）",
            fmt.table(["效果", "出现", "被驱散", "未驱散", "驱散者", "驱散技能", "被驱散对象", "未驱散的时间点（波次）"], rows),
            "说明：出现/被驱散/未驱散来自 WCL 驱散表（与打断表同构）；未驱散可能是自然结束、无人可驱或驱散冷却中。"]
