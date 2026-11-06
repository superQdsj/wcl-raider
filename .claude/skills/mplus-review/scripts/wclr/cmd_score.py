"""score 命令（评分 v2）：数据分 = 统一公式 ×（客观数据 + agent 已核实的结构化判断）。

公式、权重与 judgments.json 的格式见 references/scoring.md。原则：
- 输入相同，分数一定相同；每个维度都打印计算依据。
- 输入不成立（数据缺失、口径冲突、样本过小、缺少必要判断）时为 N/A，不硬给分。
- 有效维度的权重 < 70% 时不发布总分。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from . import data, fmt
from .api import WCLError
from .context import Run, esc, fetch, table_data

SCORING_VERSION = "v2"
CLUSTER_GAP_MS = 20000
PUBLISH_MIN_WEIGHT = 0.70

WEIGHTS = {
    "dps": {"survival": 0.30, "mechanics": 0.25, "interrupts": 0.15, "output": 0.20, "usage": 0.10},
    "tank": {"survival": 0.35, "mechanics": 0.20, "interrupts": 0.20, "output": 0.10, "usage": 0.15},
    "healer": {"survival": 0.35, "mechanics": 0.30, "interrupts": 0.10, "usage": 0.25},
}
TEAM_WEIGHTS = {"timer": 0.40, "survival": 0.35, "kicks": 0.25}
DIMS = ("survival", "mechanics", "interrupts", "output", "usage")
DIM_ZH = {"survival": "生存", "mechanics": "机制", "interrupts": "打断", "output": "输出", "usage": "技能运用"}
DEATH_PENALTY = {"personal": 3.0, "shared": 1.5, "unknown": 1.5, "chain": 0.0}
CAUSE_ZH = {"personal": "个人可避免", "shared": "部分责任", "unknown": "未能核实", "chain": "连锁/他人/不可躲"}


def clamp(x: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, x))


def show(x: Optional[float]) -> str:
    return "N/A" if x is None else f"{round(x + 1e-9, 1):.1f}"


def weighted(scores: Dict[str, Optional[float]], weights: Dict[str, float]) -> Tuple[Optional[float], float]:
    num = den = 0.0
    for k, w in weights.items():
        v = scores.get(k)
        if v is not None:
            num += v * w
            den += w
    return (num / den if den else None), den / (sum(weights.values()) or 1.0)


# ---------------------------------------------------------------- judgments

def load_judgments(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except OSError as exc:
        raise WCLError(f"无法读取判断文件 {path}：{exc}") from None
    except ValueError as exc:
        raise WCLError(f"判断文件不是合法 JSON：{exc}") from None
    if not isinstance(raw, dict):
        raise WCLError("判断文件的顶层必须是对象（{...}）。")
    return raw


def _avoidable(j: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """{技能ID: {"evidence": 证据, "roles": 适用职责集合或 None（全部职责）}}。"""
    out: Dict[int, Dict[str, Any]] = {}
    for item in j.get("avoidable") or []:
        if isinstance(item, dict) and str(item.get("id", "")).isdigit():
            roles = item.get("roles")
            roles = {r for r in roles if r in ("tank", "healer", "dps")} if isinstance(roles, list) else None
            out[int(item["id"])] = {"evidence": str(item.get("evidence") or ""), "roles": roles or None}
        elif str(item).isdigit():
            out[int(item)] = {"evidence": "", "roles": None}
    return out


def _death_causes(j: Dict[str, Any]) -> Dict[int, Tuple[str, str]]:
    out: Dict[int, Tuple[str, str]] = {}
    for k, v in (j.get("deaths") or {}).items():
        if not str(k).isdigit():
            continue
        cause, ev = (v.get("cause"), v.get("evidence") or "") if isinstance(v, dict) else (v, "")
        if cause in DEATH_PENALTY:
            out[int(k)] = (cause, str(ev))
    return out


# ---------------------------------------------------------------- inputs

def _deaths(run: Run) -> List[Dict[str, Any]]:
    """玩家死亡（报告相对时间），与 deaths 命令同序编号。"""
    evs, _ = data.events(run, data_type="Deaths")
    out = [e for e in evs if e.get("type") == "death" and e.get("targetID") in run.players]
    return sorted(out, key=lambda e: e["timestamp"])


def _clusters(deaths: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
    """每次死亡的 (串编号, 串内序号)。"""
    info, c, pos, last = [], 0, 0, None
    for d in deaths:
        if last is None or d["timestamp"] - last > CLUSTER_GAP_MS:
            c, pos = c + 1, 0
        pos += 1
        info.append((c, pos))
        last = d["timestamp"]
    return info


def _max_hp(run: Run) -> Dict[int, float]:
    """每名玩家的最大生命（取一次承伤事件的 maxHitPoints）。"""
    parts = []
    ids = list(run.players)
    for i, pid in enumerate(ids):
        expr = f'target.name = "{esc(run.players[pid].name)}" and type = "damage"'
        parts.append(f'h{i}: events(dataType: DamageTaken, fightIDs: $fid, includeResources: true, limit: 3, '
                     f'filterExpression: "{esc(expr)}") {{ data }}')
    got = fetch(run, "\n".join(parts), partial=True)
    out: Dict[int, float] = {}
    for i, pid in enumerate(ids):
        for e in (got.get(f"h{i}") or {}).get("data") or []:
            if e.get("targetID") == pid and e.get("maxHitPoints"):
                out[pid] = float(e["maxHitPoints"])
                break
    return out


def _split_kicks(run: Run, intr_tbl: Dict[str, Any], kick_events: List[Dict[str, Any]]) -> Dict[int, Dict[str, float]]:
    from .cmd_interrupts import INTERRUPT_CAPABLE_ATTACKS, KICK_SPELLS
    pure_names = {run.ab(g) for g in set(KICK_SPELLS) | set(INTERRUPT_CAPABLE_ATTACKS) if g in run.abilities}
    out = {pid: {"pure": 0.0, "control": 0.0, "casts": 0.0} for pid in run.players}
    for e in data.interrupt_entries(intr_tbl):
        for d in e.get("details") or []:
            pid = run.owner(d.get("id")) or d.get("id")
            if pid not in out:
                continue
            for a in d.get("abilities") or []:
                key = "pure" if a.get("name") in pure_names else "control"
                out[pid][key] += a.get("total") or 0
    for ev in kick_events:
        pid = run.owner(ev.get("sourceID"))
        if pid in out and ev.get("type") == "cast":
            out[pid]["casts"] += 1
    return out


def _benchmark(run: Run) -> Optional[Dict[str, Any]]:
    """与 compare 相同的同层高分记录（3 场）。只接受同层；不足 2 场时不提供基准。"""
    from .cmd_compare import _bench_run, _dt_map, _fight_rankings, _intr_map
    rows, note = _fight_rankings(run, run.level)
    if not rows or not note.startswith("同层"):
        return None
    picks = rows[:3]
    got = data.parallel({str(i): (lambda r=r: _bench_run(run, r["report"]["code"], r["report"]["fightID"]))
                         for i, r in enumerate(picks)}, workers=3)
    runs = []
    for i, r in enumerate(picks):
        rep = got.get(str(i)) or {}
        fights = rep.get("fights") or []
        if not fights or rep.get("_errors") or not isinstance(rep.get("dt"), dict) or not isinstance(rep.get("intr"), dict):
            continue
        f = fights[0]
        boss_ms: Dict[int, float] = {}
        for p in f.get("dungeonPulls") or []:
            if (p.get("encounterID") or 0) > 0:
                boss_ms[p["encounterID"]] = boss_ms.get(p["encounterID"], 0.0) + (p["endTime"] - p["startTime"])
        runs.append({"fight": f, "deaths": r.get("deaths") or 0, "dt": _dt_map(table_data(rep.get("dt"))),
                     "intr": _intr_map(table_data(rep.get("intr"))), "boss_ms": boss_ms})
    if len(runs) < 2:
        return None
    return {"runs": runs, "note": note}


# ---------------------------------------------------------------- team

def _team(run: Run, deaths: List[Dict[str, Any]], bench: Optional[Dict[str, Any]], our_intr: Dict[int, Dict[str, Any]]):
    team: Dict[str, Optional[float]] = {}
    why: Dict[str, str] = {}
    timer = run.timer_ms()
    if run.keystone_time and timer:
        r = (timer - run.keystone_time) / timer
        team["timer"] = clamp(7.0 + 7.5 * r)
        why["timer"] = f"官方用时 {fmt.clock(run.keystone_time, True)} / 限时 {fmt.clock(timer)}，余量 {r * 100:+.1f}%（{run.result}）"
    else:
        team["timer"] = None
        why["timer"] = "N/A：未完成或缺少限时数据"
    team["survival"] = clamp(10.0 - 1.0 * len(deaths))
    why["survival"] = f"死亡 {len(deaths)} 次（每次 −1.0；团灭不再额外扣分）"
    team["kicks"], why["kicks"] = None, "N/A：未获取同层高分基准"
    if bench:
        expected = actual = 0.0
        used, skipped = [], []
        for gid, o in our_intr.items():
            bs = [b["intr"].get(gid) for b in bench["runs"]]
            valid = [v for v in bs if v and v["begun"] > 0]
            consistent = all(v["kicked"] <= v["begun"] and v["kicked"] + v["done"] <= v["begun"] * 1.05
                             for v in valid + [o] if v)
            b_begun = sum(v["begun"] for v in valid)
            b_kicked = sum(v["kicked"] for v in valid)
            if not consistent:
                skipped.append(run.ab(gid))
                continue
            if b_begun >= 3 and o["begun"] >= 3 and b_kicked / b_begun >= 0.6:
                expected += (b_kicked / b_begun) * o["begun"]
                actual += o["kicked"]
                used.append(run.ab(gid))
        if expected > 0:
            team["kicks"] = clamp(10.0 * actual / expected)
            why["kicks"] = (f"高分稳定打断（≥60%）的 {len(used)} 个技能：本场打断 {actual:.0f}，按高分打断率期望 {expected:.1f}"
                            f"（{fmt.join_limited(used, 4)}）" + (f"；计数不一致已排除：{fmt.join_limited(skipped, 3)}" if skipped else ""))
        else:
            why["kicks"] = "N/A：没有可对照且计数一致的稳定打断技能" + (f"（排除：{fmt.join_limited(skipped, 3)}）" if skipped else "")
    return team, why


# ---------------------------------------------------------------- mechanics

def _per_use_ok(e: Optional[Dict[str, Any]]) -> bool:
    """按施放次数归一化只适用于"一次施放打中少数人"的技能：每次施放 ≤ 10 次命中（平均每人 ≤ 2 次）。
    光环/持续型技能一次施放会反复命中，按施放次数归一化没有意义。"""
    if not e or not e.get("uses"):
        return False
    return ((e.get("hits") or 0) + (e.get("ticks") or 0)) / e["uses"] <= 10.0


def _boss_encounter_of(run: Run, src_name: Optional[str]) -> Optional[int]:
    if not src_name:
        return None
    for p in run.pulls:
        if p.is_boss and src_name in p.boss_names:
            return p.encounter_id
    return None


def _boss_ms(run: Run) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for p in run.pulls:
        if p.is_boss:
            out[p.encounter_id] = out.get(p.encounter_id, 0.0) + p.dur
    return out


def _mechanics(run: Run, avoid: Dict[int, Dict[str, Any]], bench: Optional[Dict[str, Any]], our_dt: Dict[int, Dict[str, Any]],
               per: Dict[int, Dict[int, Dict[str, Any]]], max_hp: Dict[int, float]):
    """返回 ({玩家: 分数或 None}, {玩家: 依据}, 技能级说明列表)。"""
    scores: Dict[int, Optional[float]] = {}
    notes: Dict[int, str] = {}
    ability_notes: List[str] = []
    if not avoid:
        for pid in run.players:
            scores[pid], notes[pid] = None, "N/A：尚未提供已核实的可躲技能（judgments.avoidable）"
        return scores, notes, ability_notes
    n_players = min(5, len(run.players)) or 5
    group_hp = fmt.median(list(max_hp.values()))
    our_boss = _boss_ms(run)
    expected_pp: Dict[int, float] = {}
    for gid in avoid:
        o = our_dt.get(gid) or {}
        enc = _boss_encounter_of(run, o.get("src"))
        rates, how = [], "无基准，期望 0"
        if bench:
            for b in bench["runs"]:
                v = b["dt"].get(gid)
                hits = (v["hits"] + v["ticks"]) if v else 0.0
                if _per_use_ok(o) and v and _per_use_ok(v):
                    rates.append(hits / v["uses"])
                    how = "按敌方施放次数归一化"
                elif enc and b["boss_ms"].get(enc):
                    rates.append(hits / b["boss_ms"][enc])
                    how = "按该首领战时长归一化"
                elif v:
                    rates.append(hits)
                    how = "未归一化（小怪地面效果等）"
        rate = fmt.median(rates) if rates else 0.0
        if how == "按敌方施放次数归一化":
            exp_group = rate * (o.get("uses") or 0)
        elif how == "按该首领战时长归一化":
            exp_group = rate * our_boss.get(enc, 0.0)
        else:
            exp_group = rate
        expected_pp[gid] = exp_group / n_players
        ours_n = (o.get("hits") or 0) + (o.get("ticks") or 0)
        ability_notes.append(f"{run.ab(gid)}({gid})：本场命中+跳 {ours_n:.0f}，期望每人 {expected_pp[gid]:.1f}（{how}"
                             + (f"，{len(rates)} 场高分" if rates else "") + "）")
    for pid in run.players:
        hp = max_hp.get(pid) or group_hp
        if not hp:
            scores[pid], notes[pid] = None, "N/A：取不到最大生命值"
            continue
        bars, parts = 0.0, []
        for gid, meta in avoid.items():
            if meta.get("roles") and run.players[pid].role not in meta["roles"]:
                continue  # 该技能只对部分职责可躲（如正面技能对坦克不可躲）
            pe = (per.get(pid) or {}).get(gid)
            if not pe:
                continue
            n = (pe.get("hitCount") or 0) + (pe.get("tickCount") or 0)
            if n <= 0:
                continue
            excess = max(0.0, n - expected_pp.get(gid, 0.0))
            if excess <= 0:
                continue
            avg = (pe.get("total") or 0) / n
            b = excess * avg / hp
            if b >= 0.05:
                bars += b
                parts.append(f"{run.ab(gid)} 超额 {excess:.1f} 次≈{b:.2f} 管血")
        scores[pid] = clamp(10.0 - 1.0 * bars)
        notes[pid] = (f"超额可躲伤害 {bars:.2f} 管血（{fmt.join_limited(parts, 4)}）" if parts else "已核实的可躲技能上没有超额")
    return scores, notes, ability_notes


def _candidates(run: Run, bench: Optional[Dict[str, Any]], our_dt: Dict[int, Dict[str, Any]],
                per: Dict[int, Dict[int, Dict[str, Any]]]) -> List[str]:
    """暴露偏离候选：归一化后仍高于每一场高分记录 1.5 倍以上的技能。只是候选，需要 agent 核实。"""
    if not bench:
        return []
    out = []
    our_boss = _boss_ms(run)
    tanks = [pid for pid, p in run.players.items() if p.role == "tank"]
    for gid, o in our_dt.items():
        ours = (o.get("hits") or 0) + (o.get("ticks") or 0)
        if ours < 5:
            continue
        tank_dmg = sum((((per.get(pid) or {}).get(gid) or {}).get("total") or 0) for pid in tanks)
        if o.get("total") and tank_dmg / o["total"] >= 0.9:
            continue  # 坦克承受 ≥90%：职责伤害，不列候选
        enc = _boss_encounter_of(run, o.get("src"))
        if _per_use_ok(o):
            our_rate, unit = ours / o["uses"], "每次施放"
            rates = [((v["hits"] + v["ticks"]) / v["uses"]) for v in (b["dt"].get(gid) for b in bench["runs"])
                     if v and _per_use_ok(v)]
        elif enc and our_boss.get(enc):
            our_rate, unit = ours / (our_boss[enc] / 1000.0), "每秒（该首领战）"
            rates = [(((b["dt"].get(gid) or {}).get("hits", 0) + (b["dt"].get(gid) or {}).get("ticks", 0))
                      / (b["boss_ms"][enc] / 1000.0)) for b in bench["runs"] if b["boss_ms"].get(enc)]
        else:
            # 小怪技能、无法按施放次数归一化：只在明显高于每一场高分时列为"未归一化候选"
            raw = [((b["dt"].get(gid) or {}).get("hits", 0) + (b["dt"].get(gid) or {}).get("ticks", 0)) for b in bench["runs"]]
            if raw and any(raw) and ours >= 1.5 * max(raw) and ours - max(raw) >= 5:
                top = sorted(((run.players[pid].name, ((per.get(pid) or {}).get(gid) or {}).get("hitCount", 0)
                               + ((per.get(pid) or {}).get(gid) or {}).get("tickCount", 0)) for pid in run.players),
                             key=lambda x: -x[1])
                out.append(f"{run.ab(gid)}({gid})：【未归一化，可能受路线影响】本场命中+跳 {ours:.0f} vs 高分 "
                           f"{' / '.join(f'{r:.0f}' for r in raw)}；本场 {' '.join(f'{n}×{c}' for n, c in top[:4] if c)}")
            continue
        if not rates:
            continue
        if our_rate >= 1.5 * max(max(rates), 1e-9) and our_rate > (fmt.median(rates) or 0):
            top = sorted(((run.players[pid].name, ((per.get(pid) or {}).get(gid) or {}).get("hitCount", 0)
                           + ((per.get(pid) or {}).get(gid) or {}).get("tickCount", 0)) for pid in run.players),
                         key=lambda x: -x[1])
            out.append(f"{run.ab(gid)}({gid})：{unit}命中 {our_rate:.2f} vs 高分 {' / '.join(f'{r:.2f}' for r in rates)}；"
                       f"本场 {' '.join(f'{n}×{c}' for n, c in top[:4] if c)}")
    return out


# ---------------------------------------------------------------- main

def cmd_score(run: Run, use_compare: bool = True, judgments: Optional[str] = None) -> str:
    from .cmd_compare import _dt_map, _intr_map
    from .cmd_damage import per_player_taken
    from .cmd_interrupts import KICK_SPELLS
    from .population import MIN_RELIABLE, median_best, player_keys, spec_populations

    j = load_judgments(judgments)
    avoid = _avoidable(j)
    causes = _death_causes(j)
    usage_j = j.get("usage") or {}
    adjusts = [a for a in (j.get("adjust") or []) if isinstance(a, dict)]

    kick_ids = [k for k in KICK_SPELLS if k in run.abilities]
    keys = player_keys(run)
    tasks = {
        "intr": lambda: data.interrupts(run),
        "rk_d": lambda: data.rankings(run, "dps"),
        "dt": lambda: data.damage_taken(run),
        "per": lambda: per_player_taken(run),
        "deaths": lambda: _deaths(run),
        "pop": lambda: spec_populations(run, keys.values()),
    }
    if kick_ids:
        expr = 'type = "cast" and ability.id in (%s)' % ", ".join(str(k) for k in kick_ids)
        tasks["kicks"] = lambda: data.events(run, data_type="Casts", expr=expr, limit=20000)[0]
    if avoid:
        tasks["hp"] = lambda: _max_hp(run)
    if use_compare and run.encounter_id:
        tasks["bench"] = lambda: _benchmark(run)
    got = data.parallel(tasks, workers=6)
    bench = got.get("bench")
    deaths = got["deaths"]
    cinfo = _clusters(deaths)
    our_intr = _intr_map(got["intr"])
    our_dt = _dt_map(got["dt"])
    per = got["per"]

    team, why = _team(run, deaths, bench, our_intr)
    team_total, team_cov = weighted(team, TEAM_WEIGHTS)

    # ---- 个人
    kicks = _split_kicks(run, got["intr"], got.get("kicks") or [])
    non_healers = [pid for pid, p in run.players.items() if p.role != "healer"]
    ref = fmt.median([kicks[p]["pure"] for p in non_healers]) or 0.0
    rk = data.ranking_index(got["rk_d"])
    secs = run.duration / 1000.0
    dmg = {e.get("id"): e.get("total") or 0 for e in run.summary.get("damageDone") or []}
    mech_scores, mech_notes, mech_abilities = _mechanics(run, avoid, bench, our_dt, per, got.get("hp") or {})

    rows, detail = [], []
    for pid, p in run.players.items():
        s: Dict[str, Optional[float]] = {}
        n: Dict[str, str] = {}
        # 生存
        pen, parts = 0.0, []
        for idx, d in enumerate(deaths, 1):
            if d["targetID"] != pid:
                continue
            _c, pos = cinfo[idx - 1]
            when = run.t(d["timestamp"])
            if idx in causes:
                cause, _ev = causes[idx]
                pen += DEATH_PENALTY[cause]
                parts.append(f"#{idx} {when} {CAUSE_ZH[cause]} −{DEATH_PENALTY[cause]:.1f}")
            else:
                v = 2.0 if pos == 1 else 1.0
                pen += v
                parts.append(f"#{idx} {when} 未归因（{'串首/单独' if pos == 1 else '串内'}）−{v:.1f}")
        s["survival"] = clamp(10.0 - pen)
        n["survival"] = "；".join(parts) if parts else "无死亡"
        # 机制
        s["mechanics"], n["mechanics"] = mech_scores.get(pid), mech_notes.get(pid, "")
        # 打断
        k = kicks[pid]
        if p.role == "healer" and k["casts"] == 0 and k["pure"] == 0:
            s["interrupts"], n["interrupts"] = None, f"N/A：治疗没有纯打断施放（控制打断 {k['control']:.0f} 次，只展示）"
        elif ref <= 0:
            s["interrupts"], n["interrupts"] = None, "N/A：本场非治疗队员的纯打断中位数为 0"
        else:
            fair = ref * (0.5 if p.role == "healer" else 1.0)
            share = k["pure"] / fair
            v = 5.0 + 5.0 * min(share, 1.0)
            eff_txt = "命中率未知（无施放记录）"
            if k["casts"]:
                eff = min(1.0, k["pure"] / k["casts"])
                eff_txt = f"纯打断命中 {k['pure']:.0f}/{k['casts']:.0f}"
                if k["casts"] >= 5 and eff < 0.5:
                    v -= 1.0
                    eff_txt += "（<50% −1.0）"
                elif k["casts"] >= 5 and eff < 0.75:
                    v -= 0.5
                    eff_txt += "（<75% −0.5）"
            if p.role == "healer":
                v = max(v, 7.0)
            s["interrupts"] = clamp(v)
            n["interrupts"] = (f"纯打断 {k['pure']:.0f} 次 = 参考值（非治疗中位数{'×0.5' if p.role == 'healer' else ''} {fair:.1f}）的 "
                               f"{share * 100:.0f}%；{eff_txt}；控制打断 {k['control']:.0f} 次（只展示）")
        # 输出
        if p.role == "healer":
            s["output"], n["output"] = None, "N/A：治疗 HPS 只展示，不计分"
        else:
            info = (got.get("pop") or {}).get(keys.get(pid)) or {}
            count, more = int(info.get("count") or 0), bool(info.get("more"))
            pct = (rk.get(p.name) or {}).get("bracketPercent")
            dps = dmg.get(pid, 0) / secs if secs else 0
            label = "伤害贡献" if p.role == "tank" else "输出"
            mb = median_best(info)
            if (more or count >= MIN_RELIABLE) and pct is not None:
                s["output"] = clamp(5.0 + 5.0 * float(pct) / 100.0)
                n["output"] = f"{label}：同层同专精百分位 {pct}（样本 {'100+' if more else count} 人）"
            elif count >= 3 and mb:
                ratio = dps / float(mb)
                s["output"] = clamp(5.0 + 5.0 * clamp((ratio - 0.70) / 0.30, 0.0, 1.0))
                n["output"] = (f"{label}：同层样本仅 {count} 人，改用 DPS {fmt.num(dps)} ÷ 同层同专精最佳成绩中位数 "
                               f"{fmt.num(mb)} = {ratio:.2f}（百分位 {pct} 不采用）")
            else:
                s["output"], n["output"] = None, f"N/A：同层样本 {count} 人，无法比较"
        # 技能运用
        u = usage_j.get(p.name)
        if isinstance(u, dict):
            misses = [m for m in u.get("misses") or [] if isinstance(m, dict)]
            contrib = [c for c in u.get("contributions") or [] if isinstance(c, dict)]
            major = sum(1 for m in misses if m.get("level") != "minor")
            minor = sum(1 for m in misses if m.get("level") == "minor")
            bonus = min(1.0, 0.5 * len(contrib))
            s["usage"] = clamp(9.0 - 1.0 * major - 0.5 * minor + bonus)
            n["usage"] = (f"基准 9.0；关键错失 {major} 条 −{major:.1f}，次要 {minor} 条 −{0.5 * minor:.1f}，"
                          f"功能贡献 {len(contrib)} 条 +{bonus:.1f}")
        else:
            s["usage"], n["usage"] = None, "N/A：未提供技能运用判断（judgments.usage）"
        # 已核实情境的修正（每人每维最多一条，单条 ±0.5）
        seen_dims = set()
        for a in adjusts:
            dim = a.get("dim")
            if a.get("player") != p.name or dim not in DIMS or dim in seen_dims or s.get(dim) is None:
                continue
            try:
                delta = max(-0.5, min(0.5, float(a.get("delta") or 0)))
            except (TypeError, ValueError):
                continue
            seen_dims.add(dim)
            s[dim] = clamp(s[dim] + delta)
            n[dim] += f"；修正 {delta:+.1f}（{a.get('evidence') or '未写证据'}）"
        total, cov = weighted(s, WEIGHTS[p.role])
        tot_txt = show(total) if cov >= PUBLISH_MIN_WEIGHT else f"不发布（有效权重 {cov * 100:.0f}%）"
        rows.append([p.label, fmt.ROLE_ZH[p.role]] + [show(s.get(d)) for d in DIMS] + [tot_txt])
        detail.append(f"- **{p.name}**（有效权重 {cov * 100:.0f}%）：" + "；".join(f"{DIM_ZH[d]}：{n.get(d) or '—'}" for d in DIMS))

    lines = [f"# 评分卡（数据分 {SCORING_VERSION}）— {run.header()}",
             "0.0–10.0：9.5+ 顶尖 · 8.5 优秀 · 7.5 良好 · 6.5 及格 · <6.5 不及格。数据分 = 统一公式 ×（客观数据 + "
             "已核实的结构化判断），输入相同则分数相同；N/A = 输入不成立，不硬给分。公式见 references/scoring.md。",
             f"判断文件：{judgments or '未提供（生存按默认规则，机制与技能运用为 N/A）'}"]
    team_rows = [["计时", show(team["timer"]), why["timer"]],
                 ["存活", show(team["survival"]), why["survival"]],
                 ["关键打断", show(team["kicks"]), why["kicks"]],
                 ["**团队总分**", f"**{show(team_total) if team_cov >= PUBLISH_MIN_WEIGHT else '不发布'}**",
                  f"计时 40% · 存活 35% · 关键打断 25%；有效权重 {team_cov * 100:.0f}%。与高分记录的用时对比见 `compare`，不计分"]]
    lines += ["", "## 团队", fmt.table(["维度", "数据分", "依据"], team_rows)]
    lines += ["", "## 个人", fmt.table(["玩家", "职责"] + [DIM_ZH[d] for d in DIMS] + ["总分"], rows),
              "权重：输出职责 生存30 机制25 打断15 输出20 技能运用10；坦克 生存35 机制20 打断20 伤害贡献10 技能运用15；"
              "治疗 生存35 机制30 打断10 技能运用25（HPS 不计分）。有效权重 <70% 时不发布总分。",
              "", "## 计算依据"] + detail
    if avoid:
        lines += ["", "## 机制：已核实可躲技能的期望命中"] + [f"- {x}" for x in mech_abilities]
    cands = _candidates(run, bench, our_dt, per)
    lines += ["", "## 暴露偏离候选（需核实，未计入评分）",
              "一次施放只打中少数人的技能按每次施放归一化，首领技能按首领战每秒归一化；归一化后本场仍 ≥ 每一场同层高分 1.5 倍的列在这里。"
              "无法归一化的小怪技能只在明显高于每一场高分时列出，并标注【未归一化】。是否可躲由 agent 核实后写入 judgments.avoidable。"]
    lines += [f"- {c}" for c in cands] if cands else ["（无）" if bench else "（没有同层高分基准，无法计算）"]
    if causes or avoid or usage_j or adjusts:
        lines += ["", "## 使用的判断"]
        for idx, (cause, ev) in sorted(causes.items()):
            lines.append(f"- 死亡 #{idx}：{CAUSE_ZH[cause]}" + (f" —— {ev}" if ev else ""))
        for gid, meta in avoid.items():
            scope = ("（仅适用：" + "、".join(fmt.ROLE_ZH[r] for r in sorted(meta["roles"])) + "）") if meta.get("roles") else ""
            lines.append(f"- 可躲：{run.ab(gid)}({gid}){scope}" + (f" —— {meta['evidence']}" if meta.get("evidence") else ""))
        for name, u in usage_j.items():
            if isinstance(u, dict):
                for m in u.get("misses") or []:
                    if isinstance(m, dict):
                        lines.append(f"- {name} 错失（{m.get('level', 'major')}）：{m.get('evidence', '')}")
                for c in u.get("contributions") or []:
                    if isinstance(c, dict):
                        lines.append(f"- {name} 贡献：{c.get('evidence', '')}")
    if bench:
        lines.append(f"\n基准：{bench['note']} {len(bench['runs'])} 场高分记录（与 `compare` 相同）。")
    return "\n".join(lines)
