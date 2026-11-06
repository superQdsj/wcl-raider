"""player 命令：单人深挖。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import data, fmt
from .context import Run
from .cmd_events import _ability_ids


def _entries(tbl: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [e for e in tbl.get("entries") or [] if isinstance(e, dict)]


def cmd_player(run: Run, name: str, top: int = 15, ability: Optional[str] = None) -> str:
    p = run.find_player(name)
    pid = p.id
    if ability:
        return _ability_timeline(run, pid, ability)
    tasks = {
        "casts": lambda: data.casts(run, pid),
        "dmg": lambda: data.damage_done(run, pid),
        "taken": lambda: data.damage_taken(run, player=pid),
        "buffs": lambda: data.buffs(run, pid),
        "dd_all": lambda: data.damage_done(run),
        "rk": lambda: data.rankings(run, "hps" if p.role == "healer" else "dps"),
    }
    if p.role == "healer":
        tasks["heal"] = lambda: data.healing(run, pid)
    got = data.parallel(tasks, workers=6)
    secs = run.duration / 1000.0
    combat_min = max(run.combat_ms() / 60000.0, 0.01)
    dmg_total = next((e.get("total") or 0 for e in run.summary.get("damageDone") or [] if e.get("id") == pid), 0)
    heal_total = next((e.get("total") or 0 for e in run.summary.get("healingDone") or [] if e.get("id") == pid), 0)
    active = next((e.get("activeTime") for e in _entries(got["dd_all"]) if e.get("id") == pid), None)
    rk = data.ranking_index(got["rk"]).get(p.name) or {}
    deaths = [d for d in run.player_deaths() if d.get("id") == pid]

    lines = [f"# 玩家：{p.name}-{p.server}（{p.spec_zh} · {fmt.ROLE_ZH.get(p.role, p.role)} · 装等 {p.ilvl or '—'}）",
             f"{run.header()}"]
    parse = f"同层百分位 {rk.get('bracketPercent')}，总百分位 {rk.get('rankPercent')}" if rk else "无排名数据"
    lines.append(f"- DPS {fmt.num(dmg_total / secs)}，HPS {fmt.num(heal_total / secs)}（{parse}）；"
                 f"活跃时间 {fmt.pct(active, run.duration, 1) if active else '—'}；死亡 {len(deaths)} 次"
                 + (f"（{'、'.join(run.t(run.start + (d.get('deathTime') or 0)) for d in deaths)}）" if deaths else "")
                 + f"；药水 {p.potions} 次，治疗石 {p.healthstones} 次")
    lines.append(f"- 战斗中时长 {fmt.clock(run.combat_ms())}（CPM 按战斗中时长计算）")

    casts = sorted((e for e in _entries(got["casts"]) if int(e.get("guid") or 0) != 1), key=lambda e: -(e.get("total") or 0))
    rows = [[fmt.ability_label(e.get("name") or run.ab(e.get("guid")), e.get("guid")), e.get("total") or 0,
             f"{(e.get('total') or 0) / combat_min:.2f}"] for e in casts]
    lines += ["", f"## 技能施放（共 {len(casts)} 种，{sum(e.get('total') or 0 for e in casts)} 次）",
              fmt.table(["技能", "次数", "CPM"], rows[:top])]
    if len(rows) > top:
        lines.append(f"（其余 {len(rows) - top} 种略）")

    # 低频技能时间轴（多为爆发/减伤/功能/消耗品）
    limit = combat_min * 1.2
    rare = [e for e in casts if 0 < (e.get("total") or 0) <= limit][:min(top, 25)]
    if rare:
        ids = [int(e.get("guid")) for e in rare]
        evs, truncated = data.events(run, data_type="Casts", source=pid,
                             expr="type = \"cast\" and ability.id in (%s)" % ", ".join(str(i) for i in ids), limit=3000)
        by: Dict[int, List[float]] = {}
        for e in evs:
            if e.get("sourceID") == pid and e.get("type") == "cast":
                by.setdefault(int(e.get("abilityGameID") or 0), []).append(e["timestamp"])
        trow = []
        boss_pulls = [q for q in run.pulls if q.is_boss]
        for gid in ids:
            ts = sorted(by.get(gid, []))
            if not ts:
                continue
            marks = [f"{run.t(t)}{run.pull_tag(t)}" for t in ts]
            used_pulls = {run.pull_of(t).idx for t in ts if run.pull_of(t)}
            boss_txt = "、".join(("✓" if q.idx in used_pulls else "✗") + f"#{q.idx}" for q in boss_pulls)
            gaps = [b - a for a, b in zip(ts, ts[1:])]
            gap_txt = f"{fmt.clock(min(gaps))}/{fmt.clock(max(gaps))}" if gaps else "—"
            trow.append([fmt.ability_label(run.ab(gid), gid), len(ts), gap_txt, boss_txt or "—",
                         fmt.join_limited(marks, 14, " ")])
        lines += ["", "## 低频技能时间轴（CPM ≤ 1.2，按战斗中时长计算，最多 25 行）",
                  fmt.table(["技能", "次数", "最短/最长间隔", "首领战是否使用", "施放时间（波次）"], trow),
                  "说明：时间轴仅表示日志中的施法时点；未出现可能与天赋、冷却、死亡或日志缺失有关。"]
        if truncated:
            lines.append("（低频技能事件已截断，时间轴仅为已获取部分）")

    dmg_entries = sorted(_entries(got["dmg"]), key=lambda e: -(e.get("total") or 0))
    if dmg_entries and dmg_total:
        d_all = sum(e.get("total") or 0 for e in dmg_entries)
        lines += ["", "## 伤害构成（含归属宠物；WCL 可能合并技能/召唤物）", fmt.table(
            ["技能/合并项", "伤害", "占比"],
            [[fmt.ability_label(e.get("name") or run.ab(e.get("guid")), e.get("guid")), fmt.num(e.get("total")),
              fmt.pct(e.get("total"), d_all, 1)] for e in dmg_entries[:top]])]
    if "heal" in got:
        heal_entries = sorted(_entries(got["heal"]), key=lambda e: -(e.get("total") or 0))
        h_all = sum(e.get("total") or 0 for e in heal_entries)
        lines += ["", "## 治疗构成（过量 = 过量治疗占该技能总治疗量的比例）", fmt.table(
            ["技能", "有效治疗", "占比", "过量"],
            [[fmt.ability_label(e.get("name") or run.ab(e.get("guid")), e.get("guid")), fmt.num(e.get("total")),
              fmt.pct(e.get("total"), h_all, 1),
              fmt.pct(e.get("overheal") or 0, (e.get("total") or 0) + (e.get("overheal") or 0))]
             for e in heal_entries[:top]])]

    taken = sorted(_entries(got["taken"]), key=lambda e: -(e.get("total") or 0))
    if taken:
        t_all = sum(e.get("total") or 0 for e in taken)
        lines += ["", f"## 承伤构成（共 {fmt.num(t_all)}）", fmt.table(
            ["技能", "来源", "伤害", "占比", "命中/跳"],
            [[fmt.ability_label(e.get("name") or run.ab(e.get("guid")), e.get("guid")), e.get("actorName") or "—", fmt.num(e.get("total")),
              fmt.pct(e.get("total"), t_all, 1), f"{e.get('hitCount') or 0}/{e.get('tickCount') or 0}"]
             for e in taken[:top]])]

    auras = sorted(got["buffs"].get("auras") or [], key=lambda a: -(a.get("totalUptime") or 0))
    if auras:
        # Buffs 的 start/endTime 可覆盖整个报告，totalTime 才是所选 fight 的统计时长。
        span = got["buffs"].get("totalTime") or run.duration
        rows = [[fmt.ability_label(a.get("name"), a.get("guid")), fmt.pct(a.get("totalUptime"), span), a.get("totalUses")]
                for a in auras[:top] if (a.get("totalUptime") or 0) > 0]
        lines += ["", f"## 身上增益覆盖率（前 {top}；含食物/合剂与外部技能）",
                  fmt.table(["增益", "覆盖率", "次数"], rows)]
    return "\n".join(lines)


def _ability_timeline(run: Run, player_id: int, query: str) -> str:
    ability_ids = _ability_ids(run, query)
    expression = 'type = "cast" and ability.id in (%s)' % ", ".join(str(ability_id) for ability_id in ability_ids)
    events, truncated = data.events(run, data_type="Casts", source=player_id, expr=expression, limit=20000)
    events = [event for event in events if event.get("type") == "cast" and event.get("sourceID") == player_id
              and event.get("abilityGameID") in ability_ids]
    events.sort(key=lambda event: event["timestamp"])
    lines = [f"# 玩家技能时间轴：{run.players[player_id].name} — {run.header()}",
             fmt.table(["技能", "施放时间", "所在波次"],
                       [[fmt.ability_label(run.ab(event["abilityGameID"]), event["abilityGameID"]),
                         run.t(event["timestamp"], True), run.pull_tag(event["timestamp"])] for event in events])]
    for ability_id in ability_ids:
        timestamps = [event["timestamp"] for event in events if event["abilityGameID"] == ability_id]
        gaps = [later - earlier for earlier, later in zip(timestamps, timestamps[1:])]
        interval = f"{min(gaps) / 1000:.1f}/{max(gaps) / 1000:.1f} 秒" if gaps else "无法判定（不足两次）"
        lines.append(f"- {fmt.ability_label(run.ab(ability_id), ability_id)}：{len(timestamps)} 次；最短/最长间隔 {interval}")
    if truncated:
        lines.append("（事件已截断，次数及间隔仅基于已获取部分。）")
    return "\n".join(lines)
