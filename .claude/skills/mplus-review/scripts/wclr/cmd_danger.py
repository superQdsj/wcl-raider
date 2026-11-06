"""danger 命令：找"差点炸"的时刻——没死人但血线很低的瞬间，以及多人同时掉到低血线的团队险情。

死亡只是结果。复盘要看下一把还会不会出事，险情和死亡一样重要：同一个技能这把把人打到 10% 没死，下一把就可能死。
数据：带 includeResources 的承伤事件里有承受者受击后的血量（hitPoints/maxHitPoints）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import data, fmt
from .context import Run
from .spells import CHEAT_DEATH, CHEAT_DEATH_COOLDOWN


@dataclass
class Dip:
    pid: int
    start: float      # 报告相对毫秒：血量第一次跌破阈值
    low_ts: float
    low_pct: float
    end: float = 0.0  # 第一次回到 50% 以上的受击时刻（上界：只有受击事件带血量）
    died: bool = False
    damage: Dict[int, float] = field(default_factory=dict)  # 跌到最低前 6 秒的承伤，按技能
    sources: Dict[int, str] = field(default_factory=dict)
    cheat: str = ""   # 最低点前后 3 秒内触发的免死效果（名称）


def hp_points(events: Sequence[Dict[str, Any]], players: Sequence[int]) -> Dict[int, List[Tuple[float, float]]]:
    """每名玩家的 (时间, 血量百分比) 序列。只取 resourceActor == 2（资源属于承受者）的事件。"""
    out: Dict[int, List[Tuple[float, float]]] = {p: [] for p in players}
    for e in events:
        tid = e.get("targetID")
        if tid not in out or e.get("resourceActor") != 2:
            continue
        hp, mx = e.get("hitPoints"), e.get("maxHitPoints")
        if hp is None or not mx:
            continue
        out[tid].append((float(e["timestamp"]), 100.0 * float(hp) / float(mx)))
    for v in out.values():
        v.sort()
    return out


def find_dips(points: List[Tuple[float, float]], threshold: float,
              recover: float = 50.0, merge_gap: float = 3000.0) -> List[Tuple[float, float, float, float]]:
    """连续低血段：从跌破 threshold 开始，到血量回到 recover 以上结束。

    返回 [(开始, 最低点时间, 最低百分比, 结束)]；一直没回到 recover 时，结束 = 最后一个点。"""
    out = []
    cur: Optional[List[float]] = None
    for ts, pct in points:
        if cur is None:
            if pct < threshold:
                cur = [ts, ts, pct]
        else:
            if pct < cur[2]:
                cur[1], cur[2] = ts, pct
            if pct >= recover:
                out.append((cur[0], cur[1], cur[2], ts))
                cur = None
    if cur is not None:
        out.append((cur[0], cur[1], cur[2], points[-1][0]))
    # 回到 50% 后 3 秒内又跌破（或同一毫秒里治疗与伤害的先后不确定）算同一次险情
    merged: List[Tuple[float, float, float, float]] = []
    for d in out:
        if merged and d[0] - merged[-1][3] <= merge_gap:
            a = merged[-1]
            low = d if d[2] < a[2] else a
            merged[-1] = (a[0], low[1], low[2], d[3])
        else:
            merged.append(d)
    return merged


def team_moments(points: Dict[int, List[Tuple[float, float]]], below: float, need: int,
                 window: float = 4000.0) -> List[Tuple[float, List[Tuple[int, float]]]]:
    """多人在 window 毫秒内同时低于 below%：返回 [(时间, [(玩家, 窗口内最低%)])]，相邻 15 秒内的合并为一次。"""
    lows: List[Tuple[float, int, float]] = []
    for pid, pts in points.items():
        for ts, pct in pts:
            if pct < below:
                lows.append((ts, pid, pct))
    lows.sort()
    moments: List[Tuple[float, Dict[int, float]]] = []
    j = 0
    for i, (ts, _, _) in enumerate(lows):
        while lows[j][0] < ts - window:
            j += 1
        who: Dict[int, float] = {}
        for t2, pid, pct in lows[j:i + 1]:
            who[pid] = min(pct, who.get(pid, 101.0))
        if len(who) >= need:
            if moments and ts - moments[-1][0] <= 15000:
                prev = moments[-1][1]
                for pid, pct in who.items():
                    prev[pid] = min(pct, prev.get(pid, 101.0))
            else:
                moments.append((ts, dict(who)))
    return [(ts, sorted(who.items(), key=lambda kv: kv[1])) for ts, who in moments]


def cmd_danger(run: Run, threshold: float = 35.0, team_below: float = 50.0, top: int = 25) -> str:
    pids = list(run.players)
    got = data.parallel({
        "dt": lambda: data.events(run, data_type="DamageTaken", hostility="Friendlies", include_resources=True,
                                  limit=200000),
        "heal": lambda: data.events(run, data_type="Healing", hostility="Friendlies", include_resources=True,
                                    limit=200000),
        "cheat": lambda: data.events(run, data_type="All", hostility="Friendlies", limit=2000,
                                     expr="type in (\"applybuff\", \"applydebuff\", \"heal\") and ability.id in ("
                                          + ", ".join(str(x) for x in sorted(CHEAT_DEATH)) + ")"),
    })
    cheat_evs = sorted((e for e in (got.get("cheat") or ([], False))[0] if e.get("targetID") in run.players),
                       key=lambda e: (e.get("abilityGameID") in CHEAT_DEATH_COOLDOWN, e["timestamp"]))
    evs, truncated = got["dt"]
    heals, heal_trunc = got["heal"]
    truncated = truncated or heal_trunc
    points = hp_points(list(evs) + list(heals), pids)
    death_ts: Dict[int, List[float]] = {}
    for d in run.player_deaths():
        death_ts.setdefault(d["id"], []).append(run.start + (d.get("deathTime") or 0))

    dips: List[Dip] = []
    for pid, pts in points.items():
        for start, low_ts, low, end in find_dips(pts, threshold):
            died = any(start - 1000 <= t <= max(end, low_ts + 8000) for t in death_ts.get(pid, []))
            dips.append(Dip(pid=pid, start=start, low_ts=low_ts, low_pct=max(0.0, low), end=end, died=died))
    # 跌到最低前 6 秒的承伤构成
    by_target: Dict[int, List[Dict[str, Any]]] = {}
    for e in evs:
        if e.get("type") == "damage" and e.get("targetID") in run.players:
            by_target.setdefault(e["targetID"], []).append(e)
    for dip in dips:
        for e in by_target.get(dip.pid, []):
            if dip.low_ts - 6000 <= e["timestamp"] <= dip.low_ts:
                amt = (e.get("amount") or 0) + (e.get("absorbed") or 0)
                gid = int(e.get("abilityGameID") or 0)
                dip.damage[gid] = dip.damage.get(gid, 0.0) + amt
                dip.sources.setdefault(gid, run.actor_name(e.get("sourceID"), e.get("sourceInstance")))

    for dip in dips:
        for e in cheat_evs:
            if e.get("targetID") == dip.pid and dip.low_ts - 3000 <= e["timestamp"] <= dip.low_ts + 3000:
                dip.cheat = run.ab(e.get("abilityGameID"))
                break
    alive = [d for d in dips if not d.died]
    alive.sort(key=lambda d: d.low_pct)
    lines = [f"# 险情 — {run.header()}",
             f"个人险情 = 血量跌破 {threshold:g}% 且随后没有死亡（回到 50% 以上算结束）；"
             f"团队险情 = 4 秒内至少 3 人同时低于 {team_below:g}%。血量取自每次受击和受到治疗后的记录（不含护盾）。"]
    if truncated:
        lines.append("（承伤事件已截断，后段可能漏掉险情）")
    if not any(points.values()):
        lines.append("本场承伤事件里没有血量数据，无法判断险情。")
        return "\n".join(lines)

    # 按波次汇总
    per_pull: Dict[str, List[int]] = {}
    for d in dips:
        tag = run.pull_tag(d.low_ts)
        row = per_pull.setdefault(tag, [0, 0])
        row[0 if not d.died else 1] += 1
    team = team_moments(points, team_below, need=min(3, max(2, len(pids) - 2)))
    team_by_pull: Dict[str, int] = {}
    for ts, _ in team:
        tag = run.pull_tag(ts)
        team_by_pull[tag] = team_by_pull.get(tag, 0) + 1
    tags = sorted(set(per_pull) | set(team_by_pull), key=lambda t: _tag_order(t))
    prow = []
    for tag in tags:
        p = run.pulls[_tag_order(tag) - 1] if tag.startswith("#") and "后" not in tag and _tag_order(tag) <= len(run.pulls) else None
        prow.append([tag, run.pull_desc(p) if p else "—", per_pull.get(tag, [0, 0])[0], per_pull.get(tag, [0, 0])[1],
                     team_by_pull.get(tag, 0)])
    lines += ["", "## 按波次", fmt.table(["波", "内容", "个人险情", "低血后死亡", "团队险情"], prow),
              "险情和死亡集中的波次，就是这条路线上最危险的地方；没死人也要拿出来讲。"]

    # 团队险情
    if team:
        trow = []
        for ts, who in team[:top]:
            abil: Dict[int, float] = {}
            for pid, _ in who:
                for e in by_target.get(pid, []):
                    if ts - 6000 <= e["timestamp"] <= ts + 1000:
                        gid = int(e.get("abilityGameID") or 0)
                        abil[gid] = abil.get(gid, 0.0) + (e.get("amount") or 0) + (e.get("absorbed") or 0)
            top_ab = sorted(abil.items(), key=lambda kv: -kv[1])[:3]
            dead_after = [run.players[pid].name for pid, _ in who
                          if any(ts - 2000 <= t <= ts + 10000 for t in death_ts.get(pid, []))]
            def _cheat(pid: int) -> str:
                hit = next((e for e in cheat_evs if e.get("targetID") == pid and ts - 6000 <= e["timestamp"] <= ts + 3000), None)
                return f"（免死：{run.ab(hit.get('abilityGameID'))}）" if hit else ""
            trow.append([run.t(ts), run.pull_tag(ts), "、".join(f"{run.players[pid].name} {pct:.0f}%{_cheat(pid)}" for pid, pct in who),
                         "、".join(f"{run.ab(g)}({g})" for g, _ in top_ab) or "—", "、".join(dead_after) or "—"])
        lines += ["", f"## 团队险情（{len(team)} 次）",
                  fmt.table(["时间", "波", "同时低血的人（最低血量）", "前 6 秒主要伤害", "随后死亡"], trow),
                  "团队险情通常是团减、群疗大招、打断或躲技能里有一环没跟上。把它和该波的打断、减伤时间轴对照着看。"]
    else:
        lines += ["", "## 团队险情", "无。"]

    # 个人险情
    irow = []
    for d in alive[:top]:
        p = run.players[d.pid]
        top_ab = sorted(d.damage.items(), key=lambda kv: -kv[1])[:3]
        total = sum(d.damage.values()) or 1.0
        irow.append([run.t(d.low_ts, True), run.pull_tag(d.low_ts), p.name, fmt.ROLE_ZH.get(p.role, p.role),
                     f"{d.low_pct:.0f}%" + (f"（免死：{d.cheat}）" if d.cheat else ""), f"{max(0.1, (d.end - d.start) / 1000):.1f}s",
                     "、".join(f"{run.ab(g)}({g}) {100 * v / total:.0f}%" for g, v in top_ab) or "—"])
    lines += ["", f"## 个人险情（没死，最危险的 {min(top, len(alive))} 次 / 共 {len(alive)} 次）",
              fmt.table(["最低点", "波", "玩家", "职责", "最低血量", f"低于 {threshold:g}% 到回 50%", "前 6 秒伤害构成"], irow),
              "标\"免死\"的 = 致死伤害被免死效果（炼狱、灸灼、欺诈死亡等）挡住了：这一下本该死人，免死下一次不一定转好，按\"差点死\"处理。"
              "持续时间按受击/受治疗事件计算，误差约为两次事件的间隔。"
              "持续很短 = 一下被打到低血（爆发伤害，要提前减伤或躲开）；持续长 = 治疗或自保有一段跟不上。"]

    # 每人汇总
    srow = []
    for pid, p in run.players.items():
        mine = [d for d in dips if d.pid == pid]
        if not points.get(pid):
            continue
        srow.append([p.name, fmt.ROLE_ZH.get(p.role, p.role), len([d for d in mine if not d.died]),
                     len([d for d in mine if d.died]), (f"{min(d.low_pct for d in mine if not d.died):.0f}%" if any(not d.died for d in mine)
                      else f"≥{threshold:g}%")])
    lines += ["", "## 每人", fmt.table(["玩家", "职责", "险情", "低血后死亡", "没死时的最低血量"], srow),
              "同一个人反复出现在险情里，比一次死亡更说明问题（站位、减伤习惯或治疗分配）。"
              "坦克的险情要结合主动减伤看（`player <坦克>` 的低频技能时间轴）。"]
    return "\n".join(lines)


def _tag_order(tag: str) -> int:
    digits = "".join(ch for ch in tag.split("后")[0] if ch.isdigit())
    return int(digits) if digits else 0
