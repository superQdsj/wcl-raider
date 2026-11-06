"""runs / overview / pulls 命令。"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from . import data, fmt
from .api import Client
from .context import Run, is_mplus, load_meta, parse_ref, result_label
from .population import MIN_RELIABLE, player_keys, spec_populations


# ---------------------------------------------------------------- runs

def cmd_runs(client: Client, ref: str) -> str:
    code, hint = parse_ref(ref)
    meta, _ = load_meta(client, code)
    fights = meta.get("fights") or []
    mplus = [f for f in fights if is_mplus(f)]
    region = (meta.get("region") or {}).get("slug") or "?"
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime((meta.get("startTime") or 0) / 1000))
    lines = [f"# 报告 {code} · {meta.get('title') or ''} · {region} · {when}"]
    if not mplus:
        others = sorted({f.get("name") for f in fights if f.get("name")})
        lines.append("该报告中没有大秘境记录。" + (f"包含的战斗：{fmt.join_limited(others, 12)}" if others else ""))
        return "\n".join(lines)
    done = [f for f in mplus if f.get("kill")]
    default = (done or mplus)[-1]["id"]
    lines.append(f"共 {len(mplus)} 条大秘境记录；" +
                 (f"**本次分析 fight {hint}**（链接里指定的）。" if hint else f"链接没有指定 fight，默认分析 fight {default}（最后一条完成的）。"))
    rows = []
    for f in mplus:
        dur = f["endTime"] - f["startTime"]
        kt = f.get("keystoneTime")
        req, got = f.get("countRequired"), f.get("countReached")
        prog = fmt.pct(got, req, 1) if req else "—"
        rows.append([
            f["id"], f.get("name"), f"+{f.get('keystoneLevel')}", result_label(f),
            fmt.clock(kt, True) if kt else f"{fmt.clock(dur)}（实际）", prog,
            f"{f.get('averageItemLevel') or 0:.1f}",
        ])
    lines.append(fmt.table(["fight", "副本", "层数", "结果", "用时", "进度", "平均装等"], rows))
    return "\n".join(lines)


SATED_MS = 600_000  # 嗜血类效果的力竭/心满意足：10 分钟内不能再吃


def lust_boss_lines(run: Run, lust_ts: List[float]) -> List[str]:
    """每个首领战的嗜血情况：交了没有；没交时，是没得用（被前面的小怪波用掉了）还是有但没交。"""
    out = []
    for p in run.pulls:
        if not p.is_boss or not p.kill:
            continue
        name = "、".join(p.boss_names) or p.name
        used = [t for t in lust_ts if p.start - 5000 <= t <= p.end]
        if used:
            out.append(f"- #{p.idx} {name}：交了（开怪后 {fmt.clock(used[0] - p.start) if used[0] > p.start else '0:00'}）")
            continue
        before = [t for t in lust_ts if t < p.start - 5000]
        if not before or p.start - before[-1] >= SATED_MS:
            out.append(f"- #{p.idx} {name}：**开怪时嗜血可用，但整场首领战没交**")
            continue
        ready = before[-1] + SATED_MS
        src = run.pull_tag(before[-1])
        if ready < p.end:
            out.append(f"- #{p.idx} {name}：没交。上一次在 {run.t(before[-1])}（{src}），开怪后 {fmt.clock(ready - p.start)} 转好，"
                       "转好后也没交")
        else:
            out.append(f"- #{p.idx} {name}：**没得用**。上一次在 {run.t(before[-1])}（{src}），要到 {run.t(ready)} 才转好，"
                       f"比首领战结束还晚。如果 {src} 那次留到这里，这个首领就有嗜血")
    if not out:
        return []
    return ["", "## 首领战的嗜血（力竭 10 分钟；按本场嗜血时间推算）"] + out + [
        "没得用的首领，看是不是值得把前面那次嗜血留下来：对照 `splits` 里这个首领比参考慢多少、参考在哪里开的嗜血。"]


# ---------------------------------------------------------------- overview

def _timing_lines(run: Run, deaths: int) -> List[str]:
    out = []
    timer = run.timer_ms()
    affixes = "、".join(run.affix_names()) or "—"
    out.append(f"- 词缀：{affixes}")
    penalty, how = run.death_penalty(deaths)
    if run.keystone_time:
        kt = run.keystone_time
        if timer:
            left = timer - kt
            s = (f"- 官方用时 {fmt.clock(kt, True)} / 限时 {fmt.clock(timer)} → "
                 + (f"剩余 {fmt.clock(left, True)}" if left >= 0 else f"超时 {fmt.clock(-left, True)}"))
            for lvl, ratio in ((2, 0.8), (3, 0.6)):
                th = timer * ratio
                s += f"；+{lvl} 线 {fmt.clock(th)}" + (f"（差 {fmt.clock(kt - th, True)}）" if kt > th else "（已达成）")
            out.append(s)
        else:
            out.append(f"- 官方用时 {fmt.clock(kt, True)}（未能从 Raider.IO 获取该副本限时）")
        out.append(f"- 扣除罚时后的用时 = 官方用时 − 死亡次数 × 每次罚时 = "
                   f"{fmt.clock(kt, True)} − {deaths} × {penalty / 1000:g} 秒 = {fmt.clock(kt - deaths * penalty, True)}")
    else:
        prog = fmt.pct(run.fight.get("countReached"), run.fight.get("countRequired"), 1)
        out.append(f"- 未完成：记录在 {fmt.clock(run.duration)} 处结束，怪物进度 {prog}"
                   + (f"，限时 {fmt.clock(timer)}" if timer else ""))
    out.append(f"- 死亡 {deaths} 次；每次罚时 {penalty // 1000} 秒（{how}）→ 罚时合计 {fmt.clock(deaths * penalty)}"
               "（不含跑尸与减员的时间损失）")
    combat = run.combat_ms()
    bosses = [p for p in run.pulls if p.is_boss]
    out.append(f"- 实际时长 {fmt.clock(run.duration, True)}（含约 10 秒开场倒计时）；战斗中 {fmt.clock(combat)}"
               f"（{fmt.pct(combat, run.duration)}），脱战 {fmt.clock(run.duration - combat)}；"
               f"共 {len(run.pulls)} 波（首领 {len(bosses)} / 小怪 {len(run.pulls) - len(bosses)}）")
    req, got = run.fight.get("countRequired"), run.fight.get("countReached")
    extra = []
    if req:
        extra.append(f"怪物进度 {got}/{req}（{fmt.pct(got, req, 1)}）")
    if run.fight.get("rating"):
        extra.append(f"评分 {run.fight['rating']:.1f}")
    if run.fight.get("averageItemLevel"):
        extra.append(f"平均装等 {run.fight['averageItemLevel']:.1f}")
    if extra:
        out.append("- " + "；".join(extra))
    return out


def cmd_overview(run: Run) -> str:
    keys = player_keys(run)
    got = data.parallel({
        "dd": lambda: data.damage_done(run),
        "intr": lambda: data.interrupts(run),
        "rkd": lambda: data.rankings(run, "dps"),
        "rkh": lambda: data.rankings(run, "hps"),
        "populations": lambda: spec_populations(run, keys.values()),
    })
    secs = run.duration / 1000.0
    dmg = {e.get("id"): e.get("total") or 0 for e in run.summary.get("damageDone") or []}
    heal = {e.get("id"): e.get("total") or 0 for e in run.summary.get("healingDone") or []}
    active = {e.get("id"): e.get("activeTime") for e in got["dd"].get("entries") or []}
    rk_dps, rk_hps = data.ranking_index(got["rkd"]), data.ranking_index(got["rkh"])
    kicks: Dict[int, int] = {}
    for ab in data.interrupt_entries(got["intr"]):
        for d in ab.get("details") or []:
            pid = run.owner(d.get("id"))
            if pid is None:
                continue
            kicks[pid] = kicks.get(pid, 0) + (d.get("total") or 0)
    deaths = run.player_deaths()
    death_count: Dict[int, int] = {}
    for d in deaths:
        death_count[d["id"]] = death_count.get(d["id"], 0) + 1

    lines = [f"# {run.header()}", f"链接：{run.url}"]
    note = run.other_runs_note()
    if note:
        lines.append(note)
    prior = run.prior_attempts_note()
    if prior:
        lines += ["", "## 这一把之前"] + prior
    lines += ["", "## 计时"] + _timing_lines(run, len(deaths))

    rows = []
    for p in run.players.values():
        rk = (rk_hps if p.role == "healer" else rk_dps).get(p.name) or {}
        bracket = rk.get("bracketPercent")
        overall = rk.get("rankPercent")
        population = (got.get("populations") or {}).get(keys.get(p.id))
        if population is None:
            sample_text = "样本未知，不可靠"
        else:
            count = int(population.get("count") or 0)
            reliable = population.get("more") or count >= MIN_RELIABLE
            sample_text = f"样本 {count} 人" + ("" if reliable else "，不可靠")
        parse = "—" if bracket is None else f"{bracket}（{sample_text}）" + (f"（总{overall}）" if overall is not None else "")
        rows.append([
            p.name, p.spec_zh, fmt.ROLE_ZH.get(p.role, p.role), f"{p.ilvl:.0f}" if p.ilvl else "—",
            fmt.num(dmg.get(p.id, 0) / secs), fmt.num(heal.get(p.id, 0) / secs), parse,
            fmt.pct(active.get(p.id), run.duration, 1) if active.get(p.id) else "—",
            death_count.get(p.id, 0), kicks.get(p.id, 0), p.potions, p.healthstones,
        ])
    lines += ["", "## 玩家记录与表现"]
    if len(run.players) > 5:
        lines.append(f"记录含 {len(run.players)} 名友方玩家，可能含中途加入或未实际作战者，不能视为同时在场的阵容。")
    lines += [
              fmt.table(["玩家", "职业-专精", "职责", "装等", "DPS", "HPS", "同层百分位", "活跃", "死亡", "打断", "药水",
                         "治疗石"], rows),
              "说明：DPS/HPS 按整场实际时长计算（与 WCL 一致）；同层百分位 = 同副本同层同专精的 WCL 排名百分位"
              "（治疗按 HPS，其余按 DPS；总百分位不分层级）；同层样本有下一页或至少 20 人时标为可靠，"
              "样本小时百分位的噪声很大；活跃 = WCL 伤害表 activeTime / 整场时长，非 GCD 利用率。"]

    bosses: Dict[int, List[Any]] = {}
    for p in run.pulls:
        if p.is_boss:
            bosses.setdefault(p.encounter_id, []).append(p)
    if bosses:
        brow = []
        for pulls in bosses.values():
            kill = next((p for p in pulls if p.kill), None)
            name = "、".join(pulls[0].boss_names) or pulls[0].name
            brow.append([name, len(pulls), fmt.clock(kill.dur) if kill else "未击杀",
                         len([p for p in pulls if not p.kill]), "、".join(f"#{p.idx}" for p in pulls)])
        lines += ["", "## 首领战", fmt.table(["首领", "尝试次数", "击杀用时", "未击杀尝试", "波次"], brow)]

    if deaths:
        items = []
        for d in deaths:
            ts = run.start + (d.get("deathTime") or 0)
            ab = run.ab((d.get("ability") or {}).get("guid"))
            items.append(f"{run.t(ts)} {run.pull_tag(ts)} {d.get('name')} ← {ab}")
        lines += ["", f"## 死亡一览（{len(deaths)} 次，详见 `deaths`）", fmt.join_limited(items, 30, "；")]
    return "\n".join(lines)


# ---------------------------------------------------------------- pulls

def cmd_pulls(run: Run) -> str:
    got = data.parallel({
        "dd": lambda: data.graph(run, "DamageDone"),
        "dt": lambda: data.graph(run, "DamageTaken"),
        "kills": lambda: data.events(run, data_type="Deaths", hostility="Enemies", limit=20000),
        "lust": lambda: data.lust_casts(run),
    })
    lust_by_pull: Dict[int, List[str]] = {}
    lust_items: List[str] = []
    for ts, gid, src in got.get("lust") or []:
        pull = run.pull_of(ts)
        who = run.actor_name(src) if src is not None else "?"
        lust_items.append(f"{run.t(ts)} {run.pull_tag(ts)} {run.ab(gid)}←{who}")
        if pull:
            lust_by_pull.setdefault(pull.idx, []).append(run.t(ts))
    forces: Dict[int, float] = {}
    seen_kills = set()
    for e in got["kills"][0]:
        if e.get("type") != "death":
            continue
        key = (e.get("targetID"), e.get("targetInstance"))
        if key in seen_kills:
            continue
        seen_kills.add(key)
        actor = run.actors.get(e.get("targetID")) or {}
        value = float(run.npc_count.get(str(int(actor.get("gameID") or 0)), 0) or 0)
        pull = run.pull_of(e["timestamp"])
        if value and pull:
            forces[pull.idx] = forces.get(pull.idx, 0.0) + value
    dps_pts, dps_start, dps_iv = data.player_series_total(got["dd"], run)
    dt_pts, dt_start, dt_iv = data.player_series_total(got["dt"], run)
    req = run.fight.get("countRequired") or 0
    deaths = run.player_deaths()
    deaths_by_pull: Dict[int, List[str]] = {}
    gap_deaths: List[str] = []
    for d in deaths:
        ts = run.start + (d.get("deathTime") or 0)
        p = run.pull_of(ts)
        label = f"{d.get('name')}({run.t(ts)})"
        if p:
            deaths_by_pull.setdefault(p.idx, []).append(label)
        else:
            gap_deaths.append(label)

    rows = []
    prev_end = run.start
    gaps = []
    for p in run.pulls:
        gap = p.start - prev_end
        gaps.append((gap, p))
        dps = data.window_rate(dps_pts, dps_start, dps_iv, p.start, p.end)
        dtps = data.window_rate(dt_pts, dt_start, dt_iv, p.start, p.end)
        rows.append([
            p.idx, run.t(p.start), fmt.clock(p.dur), fmt.clock(gap), run.pull_desc(p, 4),
            fmt.pct(forces.get(p.idx), req, 1) if (req and forces.get(p.idx)) else "—",
            fmt.num(dps), fmt.num(dtps), "、".join(deaths_by_pull.get(p.idx, [])) or "—",
            ("✓" + "、".join(lust_by_pull[p.idx])) if p.idx in lust_by_pull else "",
        ])
        prev_end = max(prev_end, p.end)
    lines = [f"# 波次时间线 — {run.header()}",
             "时间相对钥石开始（WCL 计时，比游戏内计时早约 10 秒）；进度 = 该波被击杀怪物的进度值合计；"
             "团队DPS/承伤为该波平均每秒数值。",
             fmt.table(["波", "开始", "时长", "距上波", "内容", "进度", "团队DPS", "承伤/秒", "死亡", "嗜血"], rows)]
    if gap_deaths:
        lines.append(f"波次之间的死亡：{'、'.join(gap_deaths)}")
    lust_ts = sorted(ts for ts, _, _ in (got.get("lust") or []))
    lines += lust_boss_lines(run, lust_ts)
    if got["kills"][1]:
        lines.append("（敌方死亡事件已截断，各波进度仅为已获取部分）")

    combat = run.combat_ms()
    boss_ms = sum(p.dur for p in run.pulls if p.is_boss)
    trash = [p for p in run.pulls if not p.is_boss]
    trash_ms = sum(p.dur for p in trash)
    tail = run.end - prev_end
    lines += ["", "## 汇总",
              f"- 战斗中 {fmt.clock(combat)}（{fmt.pct(combat, run.duration)}）；脱战 {fmt.clock(run.duration - combat)}"
              f"（含开场到第一波 {fmt.clock(run.pulls[0].start - run.start) if run.pulls else '—'}，"
              f"最后一波结束到记录结束 {fmt.clock(tail)}）",
              f"- 首领战合计 {fmt.clock(boss_ms)}；小怪 {len(trash)} 波合计 {fmt.clock(trash_ms)}"
              + (f"，平均每波 {fmt.clock(trash_ms / len(trash))}" if trash else "")]
    big = sorted(gaps[1:], key=lambda g: -g[0])[:4]  # 第一波之前是开场倒计时，不计入
    if big:
        lines.append("- 最长的间隔：" + "；".join(
            f"#{p.idx} 前 {fmt.clock(g)}（{run.t(p.start - g)}→{run.t(p.start)}）" for g, p in big if g > 0))
    lines.append("- 嗜血类技能：" + (f"{len(lust_items)} 次（{'；'.join(lust_items)}）" if lust_items else "本场未检测到"))
    wipes = [p for p in run.pulls if p.is_boss and p.kill is False]
    if wipes:
        lines.append("- 首领战未击杀尝试：" + "；".join(f"#{p.idx} {run.pull_desc(p)} 在 {fmt.clock(p.dur)} 处" for p in wipes))
    if req:
        total_forces = sum(forces.values())
        lines.append(f"- 各波进度合计 {fmt.pct(total_forces, req, 1)}（官方 {fmt.pct(run.fight.get('countReached'), req, 1)}；"
                     "按击杀事件统计，个别召唤物/特殊计数可能有偏差）")
    return "\n".join(lines)
