"""deaths 命令：每次死亡的致死原因、死前承伤时间线、死者施法与获得的增益、团灭判定。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import data, fmt
from .spells import res_kind
from .context import Run, esc, fetch
from .cmd_interrupts import KICK_SPELLS

CLUSTER_GAP_MS = 20000  # 相邻死亡间隔 ≤20 秒视为同一串连续死亡


RETURN_MIN_MS = 1000


def first_return(death: Dict[str, Any], events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """死亡后 1–300 秒内的首次主动施法（不含普攻）；时间均为报告毫秒。

    不用"给自己上的增益"：被动光环、复活时自动恢复的增益会在死后瞬间出现，造成假回归。
    死后 1 秒内的施法也忽略（死亡状态下不可能施法，多为同一时刻的残留事件）。"""
    player_id = death["targetID"]
    actions = [event for event in events
               if not event.get("fake") and event.get("sourceID") == player_id
               and RETURN_MIN_MS <= event.get("timestamp", 0) - death["timestamp"] <= 300000
               and event.get("type") == "cast" and event.get("abilityGameID") != 1]
    return min(actions, key=lambda event: event["timestamp"]) if actions else None


def _return_fields(run: Run, deaths: List[Dict[str, Any]]) -> str:
    fields = []
    for index, death in enumerate(deaths):
        name = esc(run.players[death["targetID"]].name)
        expression = f'source.name = "{name}" and type = "cast" and ability.id != 1'
        fields.append(
            f'r{index}: events(dataType: All, fightIDs: $fid, '
            f'startTime: {min(run.end, death["timestamp"] + RETURN_MIN_MS):.0f}, '
            f'endTime: {min(run.end, death["timestamp"] + 300000):.0f}, limit: 3, '
            f'filterExpression: "{esc(expression)}") {{ data nextPageTimestamp }}')
    return "\n".join(fields)


def spell_availability(timestamps: List[float], death_time: float) -> Tuple[Optional[float], Optional[float], str]:
    """返回距上次使用、整场最短间隔（毫秒）和仅基于实测间隔的判定。"""
    timestamps = sorted(timestamps)
    previous = [timestamp for timestamp in timestamps if timestamp <= death_time]
    gaps = [later - earlier for earlier, later in zip(timestamps, timestamps[1:])]
    shortest = min(gaps) if gaps else None
    if not previous:
        return None, shortest, "死前未用过（可用性未知）"
    elapsed = death_time - previous[-1]
    if shortest is None:
        return elapsed, None, "无法判定"
    return elapsed, shortest, "可用" if elapsed >= shortest else "可能在冷却"


def _availability_data(run: Run, player_id: int) -> Dict[str, Any]:
    combat_minutes = max(run.combat_ms() / 60000.0, 0.01)
    entries = [entry for entry in data.casts(run, player_id).get("entries") or []
               if int(entry.get("guid") or 0) not in ({0, 1} | set(KICK_SPELLS))
               and 0 < (entry.get("total") or 0) / combat_minutes <= 1.5]
    entries.sort(key=lambda entry: (-(entry.get("total") or 0), int(entry["guid"])))
    entries = entries[:12]
    if not entries:
        return {"entries": [], "events": [], "truncated": False}
    expression = 'type = "cast" and ability.id in (%s)' % ", ".join(str(int(entry["guid"])) for entry in entries)
    page = fetch(run, f'e: events(dataType: Casts, fightIDs: $fid, sourceID: {player_id}, '
                 f'startTime: {run.start:.0f}, endTime: {run.end:.0f}, limit: 10000, '
                 f'filterExpression: "{esc(expression)}") {{ data nextPageTimestamp }}').get("e") or {}
    events = [event for event in page.get("data") or [] if not event.get("fake")
              and event.get("sourceID") == player_id and event.get("type") == "cast"]
    return {"entries": entries, "events": events, "truncated": bool(page.get("nextPageTimestamp"))}


def _render_availability(run: Run, death: Dict[str, Any], info: Dict[str, Any]) -> List[str]:
    rows = []
    for entry in info.get("entries") or []:
        ability_id = int(entry["guid"])
        timestamps = [event["timestamp"] for event in info["events"] if event.get("abilityGameID") == ability_id]
        elapsed, shortest, verdict = spell_availability(timestamps, death["timestamp"])
        if info["truncated"] or len(timestamps) != entry.get("total"):
            verdict = "数据不全（无法判定）"
        rows.append([fmt.ability_label(entry.get("name") or run.ab(ability_id), ability_id),
                     f"{elapsed / 1000:.1f} 秒" if elapsed is not None else "—",
                     f"{shortest / 1000:.1f} 秒" if shortest is not None else "—", verdict])
    return ["", "#### 技能可用性（本场 CPM ≤ 1.5；最多 12 项）",
            fmt.table(["技能", "死前最近使用距死亡", "本场最短使用间隔", "判定"], rows) if rows else "没有符合条件的施法记录。",
            "说明：CPM 按战斗中时长计算，排除普攻和纯打断；实测最短间隔是冷却的上界，充能类技能不适用这条规则。"]


def _recap_fields(run: Run, deaths: List[Dict[str, Any]], window_ms: float) -> str:
    parts = []
    for i, d in enumerate(deaths):
        name = esc(run.players[d["targetID"]].name)
        t = d["timestamp"]
        expr = (f'(target.name = "{name}" and type in ("damage", "heal", "absorbed", "applybuff", "applydebuff")) '
                f'or (source.name = "{name}" and type in ("cast", "begincast"))')
        parts.append(
            f'd{i}: events(dataType: All, fightIDs: $fid, startTime: {max(run.start, t - max(window_ms, 15000)):.0f}, '
            f'endTime: {min(run.end, t + 300):.0f}, includeResources: true, limit: 2000, '
            f'filterExpression: "{esc(expr)}") {{ data nextPageTimestamp }}')
    return "\n".join(parts)


def _clusters(deaths: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    for d in sorted(deaths, key=lambda d: d["timestamp"]):
        if groups and d["timestamp"] - groups[-1][-1]["timestamp"] <= CLUSTER_GAP_MS:
            groups[-1].append(d)
        else:
            groups.append([d])
    return groups


def _hp(e: Dict[str, Any]) -> str:
    hp, mx = e.get("hitPoints"), e.get("maxHitPoints")
    if hp is None or not mx:
        return ""
    return f" 剩{100.0 * hp / mx:.0f}%"


def _render_recap(run: Run, d: Dict[str, Any], evs: List[Dict[str, Any]], window_ms: float) -> List[str]:
    pid = d["targetID"]
    t = d["timestamp"]
    lines: List[str] = []
    dmg = [e for e in evs if e.get("type") == "damage" and e.get("targetID") == pid and t - window_ms <= e["timestamp"] <= t + 300]
    max_hp = next((e.get("maxHitPoints") for e in reversed(dmg) if e.get("maxHitPoints")), None)
    if dmg:
        total = sum((e.get("amount") or 0) + (e.get("absorbed") or 0) for e in dmg)
        first_hp = next((e for e in dmg if e.get("maxHitPoints")), None)
        start_txt = ""
        if first_hp and first_hp.get("maxHitPoints"):
            before = (first_hp.get("hitPoints") or 0) + (first_hp.get("amount") or 0)
            start_txt = f"，窗口开始时约 {100.0 * min(before, first_hp['maxHitPoints']) / first_hp['maxHitPoints']:.0f}% 血量"
        hp_txt = f"（最大生命 {fmt.num(max_hp)}，相当于 {fmt.pct(total, max_hp)}）" if max_hp else ""
        lines.append(f"- 死前 {window_ms / 1000:.0f} 秒伤害+吸收（不含过量）{fmt.num(total)}{hp_txt}{start_txt}")
        floor = 0.015 * max_hp if max_hp else 3000.0
        meaningful = [e for e in dmg if (e.get("amount") or 0) + (e.get("absorbed") or 0) >= floor or e.get("overkill")]
        shown = meaningful[-14:]
        hidden = len(dmg) - len(shown)
        if hidden > 0:
            lines.append(f"  （另有 {hidden} 条较早或很小（<1.5% 血量）的伤害略）")
        for e in shown:
            rel = (e["timestamp"] - t) / 1000.0
            extra = []
            if e.get("absorbed"):
                extra.append(f"吸收{fmt.num(e['absorbed'])}")
            if e.get("mitigated") and e.get("unmitigatedAmount"):
                extra.append(f"减免{100.0 * e['mitigated'] / e['unmitigatedAmount']:.0f}%")
            if e.get("overkill"):
                extra.append(f"过量{fmt.num(e['overkill'])}")
            if e.get("hitType") == 2:
                extra.append("暴击")
            if e.get("tick"):
                extra.append("跳")
            src = run.actor_name(e.get("sourceID"), e.get("sourceInstance"))
            lines.append(f"  {rel:+.1f}s {run.ab(e.get('abilityGameID'))} ← {src} {fmt.num(e.get('amount') or 0)}"
                         + (f"（{'，'.join(extra)}）" if extra else "") + _hp(e))
    else:
        lines.append("- 死前窗口内未查到伤害事件（可能是秒杀、跌落或特殊机制）")

    heals = [e for e in evs if e.get("type") == "heal" and e.get("targetID") == pid and t - window_ms <= e["timestamp"] <= t]
    absorbs = [e for e in evs if e.get("type") == "absorbed" and e.get("targetID") == pid and t - window_ms <= e["timestamp"] <= t]
    if heals or absorbs:
        by_src: Dict[str, float] = {}
        for e in heals:
            key = run.actor_name(e.get("sourceID"))
            by_src[key] = by_src.get(key, 0) + (e.get("amount") or 0)
        top = sorted(by_src.items(), key=lambda kv: -kv[1])[:4]
        lines.append(f"- 同窗口受到治疗 {fmt.num(sum(e.get('amount') or 0 for e in heals))}"
                     + (f"（{'、'.join(f'{k} {fmt.num(v)}' for k, v in top)}）" if top else "")
                     + f"，护盾吸收 {fmt.num(sum(e.get('amount') or 0 for e in absorbs))}")

    casts = [e for e in evs if e.get("type") == "cast" and e.get("sourceID") == pid and e.get("abilityGameID") != 1
             and t - 15000 <= e["timestamp"] <= t]
    if casts:
        if len(casts) <= 12:
            items = [f"{run.ab(e.get('abilityGameID'))}({(e['timestamp'] - t) / 1000.0:+.1f}s)" for e in casts]
        else:
            grouped: Dict[str, List[float]] = {}
            for e in casts:
                grouped.setdefault(run.ab(e.get("abilityGameID")), []).append((e["timestamp"] - t) / 1000.0)
            items = []
            for name, times in grouped.items():
                if len(times) == 1:
                    items.append(f"{name}({times[0]:+.1f}s)")
                else:
                    items.append(f"{name}×{len(times)}({times[0]:+.1f}s…{times[-1]:+.1f}s)")
        lines.append(f"- 死者死前 15 秒的施法（{len(casts)} 次，不含普攻）：" + fmt.join_limited(items, 18))
    else:
        lines.append("- 死者死前 15 秒没有施法记录（不含普攻）")

    gained = [e for e in evs if e.get("type") in ("applybuff",) and e.get("targetID") == pid
              and t - 15000 <= e["timestamp"] <= t]
    if gained:
        seen = set()
        items = []
        for e in gained:
            name = run.ab(e.get("abilityGameID"))
            src = run.actor_name(e.get("sourceID"))
            key = (name, src)
            if key in seen:
                continue
            seen.add(key)
            who = "" if e.get("sourceID") == pid else f"←{src}"
            items.append(f"{name}{who}({(e['timestamp'] - t) / 1000.0:+.1f}s)")
        lines.append("- 死前 15 秒获得的增益（含触发效果，需自行辨别减伤/外部技能）：" + fmt.join_limited(items, 14))
    debuffs = [e for e in evs if e.get("type") == "applydebuff" and e.get("targetID") == pid
               and t - window_ms <= e["timestamp"] <= t]
    if debuffs:
        names = []
        for e in debuffs:
            n = run.ab(e.get("abilityGameID"))
            if n not in names:
                names.append(n)
        lines.append("- 死前被施加的减益：" + fmt.join_limited(names, 10))
    return lines


def cmd_deaths(run: Run, detail: int = 12, window: float = 10.0) -> str:
    got = data.parallel({
        "table": lambda: data.deaths_table(run),
        "events": lambda: data.events(run, data_type="Deaths")[0],
        "rez": lambda: data.events(run, data_type="All", expr='type = "resurrect"', limit=500)[0],
    })
    raw = [e for e in got["events"] if e.get("type") == "death" and e.get("targetID") in run.players]
    raw.sort(key=lambda e: e["timestamp"])
    rezzes = sorted((e for e in (got.get("rez") or []) if e.get("type") == "resurrect" and e.get("targetID") in run.players),
                    key=lambda e: e["timestamp"])

    def rez_after(d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """死亡之后、该玩家下一次死亡之前的第一次复活（战斗中复活/灵魂石等）。"""
        nxt = next((x["timestamp"] for x in raw if x["targetID"] == d["targetID"] and x["timestamp"] > d["timestamp"]), None)
        for r in rezzes:
            if r["targetID"] == d["targetID"] and r["timestamp"] > d["timestamp"] and (nxt is None or r["timestamp"] < nxt):
                return r
        return None
    table_by_key = {}
    for entry in got["table"].get("entries") or []:
        table_by_key[(entry.get("id"), int(entry.get("timestamp") or 0))] = entry

    def table_entry(d: Dict[str, Any]) -> Dict[str, Any]:
        best, gap = None, 1e18
        for (pid, ts), entry in table_by_key.items():
            if pid == d["targetID"] and abs(ts - d["timestamp"]) < gap:
                best, gap = entry, abs(ts - d["timestamp"])
        return best if best is not None and gap <= 2000 else {}

    lines = [f"# 死亡复盘 — {run.header()}"]
    if not raw:
        lines.append("本场没有玩家死亡。")
        return "\n".join(lines)

    returns = fetch(run, _return_fields(run, raw), partial=True)
    if returns.get("_errors"):
        lines.append("（部分回归记录获取失败：" + "；".join(returns["_errors"]) + "）")

    penalty, how = run.death_penalty(len(raw))
    lines.append(f"共 {len(raw)} 次死亡；罚时每次 {penalty // 1000} 秒（{how}），合计 {fmt.clock(len(raw) * penalty)}。"
                 "时间相对钥石开始。")

    # 串联/团灭
    groups = _clusters(raw)
    group_of: Dict[int, int] = {}
    n_players = min(5, len(run.players))  # 全场曾参与 12 人不代表同时有 12 人在场
    summary_rows = []
    for gi, g in enumerate(groups, 1):
        names = {e["targetID"] for e in g}
        kind = "疑似团灭" if len(names) >= max(3, n_players - 1) else ("多人连续死亡" if len(names) >= 2 else "单人")
        for e in g:
            group_of[id(e)] = gi
        if len(g) >= 2:
            pull = run.pull_of(g[0]["timestamp"])
            summary_rows.append([gi, kind, f"{run.t(g[0]['timestamp'])}–{run.t(g[-1]['timestamp'])}",
                                 run.pull_tag(g[0]["timestamp"]) + (f" {run.pull_desc(pull)}" if pull else ""),
                                 " → ".join(run.players[e["targetID"]].name for e in g)])
    if summary_rows:
        lines += ["", "## 连续死亡（相邻间隔 ≤20 秒归为一串；至少 4 名不同玩家为疑似团灭，不能据此判定原因）",
                  fmt.table(["串", "类型", "时间", "波次", "倒下顺序"], summary_rows)]

    rows = []
    for i, d in enumerate(raw, 1):
        p = run.players[d["targetID"]]
        te = table_entry(d)
        kb = te.get("killingBlow") or {}
        ab_id = d.get("killingAbilityGameID") or kb.get("guid")
        killer = run.actor_name(d.get("killerID"), d.get("killerInstance")) if d.get("killerID") else "—"
        rz = rez_after(d)
        if rz:
            kind = res_kind(rz.get("abilityGameID"), rz.get("sourceID"), rz.get("targetID"))
            rez_txt = (f"{kind}：+{(rz['timestamp'] - d['timestamp']) / 1000:.0f}s {run.ab(rz.get('abilityGameID'))}"
                       + ("" if kind == "自我复活" else f"←{run.actor_name(rz.get('sourceID'))}"))
        else:
            rez_txt = "没人复活 → 释放灵魂跑尸（推断）"
        page = returns.get(f"r{i - 1}")
        action = first_return(d, (page or {}).get("data") or [])
        return_text = (f"+{(action['timestamp'] - d['timestamp']) / 1000:.1f}秒（{run.ab(action.get('abilityGameID'))}）"
                       if action else "300 秒内无动作")
        if action and not rz:
            return_text += "，在墓地复活后的第一个动作，回到队伍还要跑路"
        if page is None or (not action and page.get("nextPageTimestamp")):
            return_text = "回归记录不全（未知）"
        rows.append([i, run.t(d["timestamp"], True), run.pull_tag(d["timestamp"]), p.label,
                     fmt.ability_label(run.ab(ab_id), ab_id), killer,
                     fmt.num(te.get("overkill")) if te.get("overkill") else "—",
                     group_of.get(id(d), "—"), rez_txt, return_text])
    lines += ["", "## 死亡列表", fmt.table(["#", "时间", "波次", "玩家", "致死技能", "来源", "过量", "串", "复活", "回归"], rows),
              "说明：复活列按复活事件的技能分类（战复 / 脱战复活 / 自我复活）；没有复活事件 = 没人复活他，"
              "他是释放灵魂、在墓地复活后跑回来的（WCL 不记录释放灵魂，所以是推断；没有复活事件的特殊复活方式可能漏掉非常规复活）。"
              "回归 = 死后 1–300 秒内首次主动施法（不含普攻、不含被动增益），是缺席时长的上界。被复活时，回归≈回到战斗；"
              "跑尸时，回归只是在墓地复活的时间，真正回到队伍还要加上跑路时间。搜索止于本场记录结束。"]
    if rezzes:
        kinds: Dict[str, int] = {}
        for r in rezzes:
            k = res_kind(r.get("abilityGameID"), r.get("sourceID"), r.get("targetID"))
            kinds[k] = kinds.get(k, 0) + 1
        lines.append(f"复活共 {len(rezzes)} 次（" + "、".join(f"{k} {v}" for k, v in kinds.items()) + "）：" + "；".join(
            f"{run.t(r['timestamp'])} {run.actor_name(r.get('sourceID'))} → {run.actor_name(r.get('targetID'))}"
            f"（{run.ab(r.get('abilityGameID'))}，{res_kind(r.get('abilityGameID'), r.get('sourceID'), r.get('targetID'))}）"
            for r in rezzes))

    # 每人统计
    per: Dict[int, List[int]] = {}
    for i, d in enumerate(raw, 1):
        per.setdefault(d["targetID"], []).append(i)
    lines.append("每人死亡：" + "；".join(f"{run.players[pid].name} {len(v)} 次" for pid, v in per.items()))

    # 逐次详情
    detail = max(0, detail)
    targets = raw[:detail]
    if targets:
        availability = {player_id: _availability_data(run, player_id) for player_id in {death["targetID"] for death in targets}}
        window_ms = window * 1000.0
        recap = fetch(run, _recap_fields(run, targets, window_ms), partial=True)
        if recap.get("_errors"):
            lines.append("（部分死亡窗口获取失败：" + "；".join(recap["_errors"]) + "）")
        lines += ["", f"## 逐次详情（前 {len(targets)} 次；时间为相对死亡时刻；剩x% = 该次伤害后的血量）"]
        for i, d in enumerate(targets):
            p = run.players[d["targetID"]]
            te = table_entry(d)
            pull = run.pull_of(d["timestamp"])
            title = f"### #{i + 1} {run.t(d['timestamp'], True)} {p.label}"
            if pull:
                title += f" · 第 {pull.idx} 波 {run.pull_desc(pull)}"
            lines.append(title)
            page = recap.get(f"d{i}")
            if page is None:
                lines.append("- 该次死亡窗口未能获取，无法判断伤害或施法记录。")
                lines += _render_availability(run, d, availability[d["targetID"]])
                continue
            if page.get("nextPageTimestamp"):
                lines.append("- 该死亡窗口事件已截断，下述数值仅为已获取部分；请用 events 缩小窗口核对。")
            dmg = te.get("damage") or {}
            if dmg.get("abilities"):
                top = sorted(dmg["abilities"], key=lambda a: -(a.get("total") or 0))[:5]
                win = te.get("deathWindow")
                lines.append(f"- WCL 死亡窗口{f'（{win / 1000:.1f}s）' if win else ''}承伤构成："
                             + "、".join(f"{run.ab(a.get('guid'))} {fmt.num(a.get('total'))}" for a in top))
            evs = ((recap.get(f"d{i}") or {}).get("data")) or []
            lines += _render_recap(run, d, evs, window_ms)
            lines += _render_availability(run, d, availability[d["targetID"]])
        if len(raw) > len(targets):
            lines.append(f"\n（其余 {len(raw) - len(targets)} 次死亡未展开；用 --detail {len(raw)} 查看全部）")
    return "\n".join(lines)
