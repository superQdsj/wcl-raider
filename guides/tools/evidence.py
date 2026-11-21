#!/usr/bin/env python3
"""职业手册证据包：把多场录像（现行 5 场）的原始事件算成小表格，供写手册的模型直接读。

不做判断，只做确定性的计算：
  compare.md     每个敌方技能打到本玩家时，按「当时开着哪些防御技能」分组（直击与跳伤自动拆分）
                 含玩家最大生命值与占血量%，以及「敌方每次施放后本玩家有没有被打到」命中率
  uses.md        本玩家每次使用防御技能和低频技能的情境（排除同刻由本技能挂上的减益如自律）
  interrupts.md  本玩家打断与驱散汇总，以及主要敌方技能是否有读条（区分可断读条 vs 瞬发引导）
  team.md        全队承伤：按波次 × 敌方技能，含同刻多人吃（分摊/AOE 信号）
  debuffs.md     本玩家身上的减益：次数、平均持续、消失前后 0.5 秒内低频技能（含打断/控制）
  segments.md    波次时间表（首领名回退到波次名）+ 首领战内关键机制相对开打时间（+Xs）
  spells.md      Wowhead 技能说明：覆盖防御/always 技能（含基础冷却、充能与天赋改写冷却）与
                 敌方伤害/非伤害读条/减益机制
  talents.json   本玩家的天赋原始数据（playerDetails includeCombatantInfo）
  raw/           原始事件 JSON（需要时自己再算）

用法（仓库根目录）：
  python3 guides/tools/evidence.py --class guides/tools/classes/<专精>.json --out <目录> \
      "<WCL链接#fight=N>@玩家名" ... (共 5 场)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from wclr import data  # noqa: E402
from wclr.api import Client  # noqa: E402
from wclr.context import Run, esc, fetch, load_run  # noqa: E402
from wclr.wowhead import spells as wowhead_spells  # noqa: E402

HIT_LABEL = {
    0: "未命中", 4: "格挡", 5: "偏斜", 6: "抵抗", 7: "躲闪", 8: "招架", 9: "反射", 10: "免疫",
    16: "完全吸收", 17: "格挡", 127: "免疫/零伤",
}
CAST_HIT_WINDOW = 6000   # 敌方施放后多久内被打到算「这次打到了」
CTX_BEFORE, CTX_AFTER = 4000, 2000
LOWFREQ_MAX = 30
LONG_DEBUFFS = {"筋疲力尽", "心满意足", "时空错位", "疲惫", "Exhaustion", "Sated", "Temporal Displacement"}


def wan(x: float) -> str:
    return f"{x / 10000:.1f}万" if x >= 10000 else f"{x:.0f}"


def clock(ms: float) -> str:
    s = max(0, ms) / 1000
    return f"{int(s // 60)}:{s % 60:04.1f}"


def _fmt_cd(ms: float) -> str:
    s = ms / 1000.0
    if s >= 60 and abs(s % 60) < 0.05:
        return f"{int(round(s // 60))}分钟"
    if s >= 60 and abs((s / 60) * 10 - round((s / 60) * 10)) < 0.05:
        return f"{s / 60:.1f}分钟"
    return f"{s:g}秒"


class RunData:
    def __init__(self, idx: int, run: Run, name: str, cfg: dict, raw_dir: Path):
        self.idx, self.run = idx, run
        self.p = run.find_player(name)
        self.pid, self.name = self.p.id, self.p.name
        self.cfg = cfg
        n = esc(self.name)
        get = lambda **kw: data.events(run, limit=60000, **kw)[0]  # noqa: E731
        self.casts = get(data_type="Casts", hostility="Friendlies", expr=f'source.name = "{n}"')
        self.taken = get(data_type="DamageTaken", hostility="Friendlies", expr=f'target.name = "{n}"', include_resources=True)
        self.team_taken = get(data_type="DamageTaken", hostility="Friendlies")
        self.debuffs = get(data_type="Debuffs", hostility="Friendlies", expr=f'target.name = "{n}"')
        buff_ids = sorted({b for d in cfg["defensives"] for b in d.get("buff", [d["cast"]])})
        self.buffs = get(data_type="Buffs", hostility="Friendlies",
                         expr=f'target.name = "{n}" and ability.id in ({",".join(map(str, buff_ids))})')
        self.enemy = get(data_type="Casts", hostility="Enemies")
        self.interrupts = get(data_type="Interrupts", hostility="Friendlies", expr=f'source.name = "{n}"')
        self.dispels = get(data_type="Dispels", hostility="Friendlies", expr=f'source.name = "{n}"')
        names = {"actors": {a: v.get("name") for a, v in run.actors.items()},
                 "abilities": {g: v.get("name") for g, v in run.abilities.items()},
                 "fight_start": run.start}
        (raw_dir / f"run{idx}_names.json").write_text(json.dumps(names, ensure_ascii=False))
        for k in ("casts", "taken", "team_taken", "debuffs", "buffs", "enemy", "interrupts", "dispels"):
            (raw_dir / f"run{idx}_{k}.json").write_text(json.dumps(getattr(self, k), ensure_ascii=False))
        self.windows = self._windows()
        hps = [e.get("maxHitPoints") for e in self.taken if e.get("maxHitPoints")]
        self.max_hp = max(hps) if hps else 0

    # 防御技能生效窗口：优先用增益事件，没有增益事件就用施法时间 + 配置的持续时间
    def _windows(self):
        out = []
        for d in self.cfg["defensives"]:
            ids = set(d.get("buff", [d["cast"]]))
            opened = {}
            got = False
            for e in self.buffs:
                if e.get("abilityGameID") not in ids:
                    continue
                got = True
                if e["type"] == "applybuff":
                    opened[e["abilityGameID"]] = e["timestamp"]
                elif e["type"] == "removebuff" and e["abilityGameID"] in opened:
                    out.append((d["name"], opened.pop(e["abilityGameID"]), e["timestamp"]))
            for t0 in opened.values():
                out.append((d["name"], t0, t0 + d.get("dur", 5) * 1000))
            if not got:
                for e in self.casts:
                    if (e["type"] == "cast" and e.get("abilityGameID") == d["cast"]
                            and e.get("targetID") in (None, -1, self.pid)):  # 给别人的不算自己的窗口
                        out.append((d["name"], e["timestamp"], e["timestamp"] + d.get("dur", 5) * 1000))
        return out

    def active(self, ts: float) -> str:
        names = sorted({n for n, a, b in self.windows if a <= ts <= b})
        return "+".join(names) or "无"

    def t(self, ts):
        return clock(ts - self.run.start)

    def seg(self, ts):
        p = self.run.pull_of(ts)
        if not p:
            return "间隔"
        if not p.encounter_id:
            return f"#{p.idx}"
        boss_label = "/".join(p.boss_names) or p.name or "首领"
        return f"#{p.idx} {boss_label}"


def ab(rd: RunData, gid) -> str:
    return rd.run.ab(gid)


def dmg(e) -> float:
    return (e.get("amount") or 0) + (e.get("absorbed") or 0)


def compare_md(runs):
    hp_vals = [rd.max_hp for rd in runs if rd.max_hp]
    avg_hp = sum(hp_vals) / len(hp_vals) if hp_vals else 0
    hp_note = (
        "玩家最大生命值：" + " / ".join(f"r{rd.idx} {wan(rd.max_hp)}" for rd in runs if rd.max_hp)
        if hp_vals else "玩家最大生命值：事件未含资源字段"
    )
    lines = [
        "# 窗口内外对比（本玩家承伤，按当时开着的防御技能分组）",
        "",
        hp_note,
        "口径：伤害 = 实际掉血 + 吸收量；同时含直击和持续跳伤的技能自动拆分为 `[直击]` 与 `[跳伤]` 两张表。",
        "每格：命中次数 · 0伤害/未命中(类型) · 有伤害平均（占最大血量%）· 最大 · 涉及场次。\"无\"=对照组。",
        "只列总命中≥3 或在任一防御窗口内出现过的敌方技能，按总伤害排序。",
        "",
    ]

    # 检测每个技能 ID 是否同时存在直击与 tick 跳伤
    kinds_by_gid = defaultdict(set)
    for rd in runs:
        for e in rd.taken:
            if e.get("type") == "damage":
                kinds_by_gid[e.get("abilityGameID")].add("tick" if e.get("tick") else "direct")

    by = defaultdict(lambda: defaultdict(list))  # key -> combo -> [(rd, e)]
    total = Counter()
    for rd in runs:
        for e in rd.taken:
            if e.get("type") != "damage":
                continue
            gid = e.get("abilityGameID")
            suffix = ("[跳伤]" if e.get("tick") else "[直击]") if len(kinds_by_gid[gid]) > 1 else ""
            nm = f"{ab(rd, gid)}{suffix}({gid})"
            by[nm][rd.active(e["timestamp"])].append((rd, e))
            total[nm] += dmg(e)

    for nm, _ in total.most_common():
        combos = by[nm]
        n = sum(len(v) for v in combos.values())
        if n < 3 and set(combos) == {"无"}:
            continue
        lines.append(f"## {nm} — 共 {n} 次，总 {wan(total[nm])}")
        lines.append("| 当时开着 | 命中 | 0伤害/未命中 | 有伤害平均 | 占血量 | 最大 | 场次 |")
        lines.append("|---|---|---|---|---|---|---|")
        for combo, evs in sorted(combos.items(), key=lambda kv: (kv[0] != "无", -len(kv[1]))):
            zero = [e for _, e in evs if dmg(e) == 0]
            kinds = Counter(HIT_LABEL.get(e.get("hitType"), f"hit{e.get('hitType')}") for e in zero)
            pos = [dmg(e) for _, e in evs if dmg(e) > 0]
            avg_v = sum(pos) / len(pos) if pos else 0
            avg = wan(avg_v) if pos else "—"
            hp_pct = f"{avg_v / avg_hp * 100:.0f}%" if (pos and avg_hp) else "—"
            mx = wan(max(pos)) if pos else "—"
            rs = "/".join(f"r{r}" for r in sorted({rd.idx for rd, _ in evs}))
            zs = f"{len(zero)}（{'、'.join(f'{k}{v}' for k, v in kinds.items())}）" if zero else "0"
            lines.append(f"| {combo} | {len(evs)} | {zs} | {avg} | {hp_pct} | {mx} | {rs} |")
        lines.append("")

    # 每次敌方施放后有没有打到本玩家
    lines += [
        "# 敌方每次施放后本玩家是否被打到（同名技能，施放后6秒内）",
        "",
        "看点名跳过/反射/免疫：比较「施放时开着X」与「无」的被打到比例。只列施放≥4次且打到过本玩家的技能。",
        "",
    ]
    rows = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for rd in runs:
        hit_names = defaultdict(list)
        for e in rd.taken:
            if e.get("type") == "damage":
                hit_names[ab(rd, e.get("abilityGameID"))].append(e["timestamp"])
        for e in rd.enemy:
            if e.get("type") != "cast":
                continue
            nm = ab(rd, e.get("abilityGameID"))
            if nm not in hit_names:
                continue
            ts = e["timestamp"]
            hit = any(ts <= h <= ts + CAST_HIT_WINDOW for h in hit_names[nm])
            c = rows[nm][rd.active(ts)]
            c[0] += 1
            c[1] += hit
    for nm, combos in rows.items():
        if sum(v[0] for v in combos.values()) < 4:
            continue
        cells = "；".join(f"{k} {v[1]}/{v[0]}" for k, v in sorted(combos.items(), key=lambda kv: kv[0] != "无"))
        lines.append(f"- {nm}：{cells}")
    return "\n".join(lines) + "\n"


def uses_md(runs, defensive_names, always=()):
    lines = [
        "# 本玩家技能使用情境",
        "",
        "每行：时间 波次 技能 → 目标 | 前4秒/后2秒敌方读条或施放 | 前3秒吃到的伤害 | 使用前身上已有减益（已排除本技能同刻挂上的减益如自律） | 使用后0.5秒内消失的减益",
        "",
    ]
    for rd in runs:
        cnt = Counter(e.get("abilityGameID") for e in rd.casts if e.get("type") == "cast")
        lines.append(f"## r{rd.idx} {rd.name}（{rd.run.header()}）")
        for e in rd.casts:
            if e.get("type") != "cast":
                continue
            gid = e.get("abilityGameID")
            name = ab(rd, gid)
            if name not in defensive_names and gid not in always and cnt[gid] > LOWFREQ_MAX:
                continue
            ts = e["timestamp"]
            tgt = e.get("targetID")
            tgt_s = f" → {rd.run.actor_name(tgt, e.get('targetInstance'))}" if tgt and tgt != rd.pid and tgt != -1 else ""
            ctx = []
            for x in rd.enemy:
                if ts - CTX_BEFORE <= x["timestamp"] <= ts + CTX_AFTER:
                    tag = "读" if x["type"] == "begincast" else "放"
                    s = f"{ab(rd, x.get('abilityGameID'))}{tag}{(x['timestamp'] - ts) / 1000:+.1f}"
                    if s not in ctx:
                        ctx.append(s)
            hits = Counter()
            for x in rd.taken:
                if x.get("type") == "damage" and ts - 3000 <= x["timestamp"] <= ts:
                    hits[ab(rd, x.get("abilityGameID"))] += dmg(x)
            state_before = {}
            gone = []
            for x in rd.debuffs:
                xts = x["timestamp"]
                if xts > ts + 500:
                    break
                k = ab(rd, x.get("abilityGameID"))
                if xts < ts - 20:
                    if x["type"] in ("applydebuff", "refreshdebuff", "applydebuffstack"):
                        state_before[k] = True
                    elif x["type"] == "removedebuff":
                        state_before[k] = False
                elif x["type"] == "removedebuff" and ts - 100 <= xts <= ts + 500 and state_before.get(k):
                    gone.append(k)
            on = [k for k, v in state_before.items() if v and k not in LONG_DEBUFFS]
            lines.append(
                f"- {rd.t(ts)} {rd.seg(ts)} **{name}**{tgt_s} | {'、'.join(ctx[:8]) or '—'} | "
                f"{'、'.join(f'{k}{wan(v)}' for k, v in hits.most_common(3)) or '—'} | "
                f"{'、'.join(sorted(set(on))) or '—'} | {'、'.join(gone) or '—'}"
            )
        lines.append("")
    return "\n".join(lines)


def interrupts_md(runs):
    lines = [
        "# 打断、驱散与敌方施法形态（是否含读条）",
        "",
        "## 本玩家打断汇总（按被打断的敌方技能）",
        "",
    ]
    int_stat = defaultdict(lambda: [0, set(), Counter()])  # label -> [count, runs, target_mobs]
    for rd in runs:
        for e in rd.interrupts:
            egid = e.get("extraAbilityGameID")
            if not egid:
                continue
            k = f"{ab(rd, egid)}({egid})"
            int_stat[k][0] += 1
            int_stat[k][1].add(rd.idx)
            tgt = rd.run.actor_name(e.get("targetID"), e.get("targetInstance"))
            int_stat[k][2][tgt.split("#")[0]] += 1
    if int_stat:
        lines.append("| 被打断技能 | 总次数 | 涉及场次 | 主要施法怪 |")
        lines.append("|---|---|---|---|")
        for k, (cnt, rset, mobs) in sorted(int_stat.items(), key=lambda kv: (-len(kv[1][1]), -kv[1][0])):
            rs = "/".join(f"r{r}" for r in sorted(rset))
            ms = "、".join(f"{m}×{c}" for m, c in mobs.most_common(3))
            lines.append(f"| {k} | {cnt} | {rs} | {ms} |")
    else:
        lines.append("（五场均无打断记录）")
    lines.append("")

    lines += ["## 本玩家驱散汇总（按被驱散的减益）", ""]
    disp_stat = defaultdict(lambda: [0, set(), Counter()])
    for rd in runs:
        for e in rd.dispels:
            egid = e.get("extraAbilityGameID")
            if not egid:
                continue
            k = f"{ab(rd, egid)}({egid})"
            disp_stat[k][0] += 1
            disp_stat[k][1].add(rd.idx)
            via = ab(rd, e.get("abilityGameID"))
            disp_stat[k][2][via] += 1
    if disp_stat:
        lines.append("| 被驱散减益 | 总次数 | 涉及场次 | 驱散技能 |")
        lines.append("|---|---|---|---|")
        for k, (cnt, rset, vias) in sorted(disp_stat.items(), key=lambda kv: (-len(kv[1][1]), -kv[1][0])):
            rs = "/".join(f"r{r}" for r in sorted(rset))
            vs = "、".join(f"{v}×{c}" for v, c in vias.most_common(3))
            lines.append(f"| {k} | {cnt} | {rs} | {vs} |")
    else:
        lines.append("（五场均无驱散记录）")
    lines.append("")

    # 敌方施法形态：区分有 begincast（读条）和仅 cast 无 begincast（瞬发或瞬发引导，常规打断无法断读条）
    lines += [
        "## 敌方主要技能读条形态（区分可断读条 vs 瞬发/引导）",
        "",
        "仅 `cast` 无 `begincast` 的高频引导技（如箭雨）常规打断无法打断，需看 `debuffs.md` 是否可用群控/硬控停掉。",
        "",
    ]
    cast_forms = defaultdict(lambda: [0, 0])  # label -> [begincast, cast]
    for rd in runs:
        for e in rd.enemy:
            gid = e.get("abilityGameID")
            if not gid or gid <= 1:
                continue
            k = f"{ab(rd, gid)}({gid})"
            if e.get("type") == "begincast":
                cast_forms[k][0] += 1
            elif e.get("type") == "cast":
                cast_forms[k][1] += 1
    top_casts = sorted(cast_forms.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:45]
    lines.append("| 敌方技能 | begincast(读条) | cast(施放) | 形态提示 |")
    lines.append("|---|---|---|---|")
    for k, (bc, cs) in top_casts:
        hint = "有读条" if bc > 0 else "无读条（瞬发/引导）"
        lines.append(f"| {k} | {bc} | {cs} | {hint} |")
    return "\n".join(lines) + "\n"


def team_md(runs):
    lines = [
        "# 全队承伤（按波次 × 敌方技能）",
        "",
        "每行：技能 · 命中次数 · 被打到的不同玩家数 · 同一时刻(±0.3s)最多几名不同玩家一起吃 · 单次平均/最大 · 本玩家吃了几次。每波只列总伤害前8。",
        "",
    ]
    for rd in runs:
        lines.append(f"## r{rd.idx} {rd.name}（{rd.run.header()}）")
        players = set(rd.run.players)
        groups = defaultdict(list)
        for e in rd.team_taken:
            if e.get("type") != "damage" or e.get("targetID") not in players:
                continue
            groups[(rd.seg(e["timestamp"]), e.get("abilityGameID"))].append(e)
        segs = defaultdict(list)
        for (sg, gid), evs in groups.items():
            segs[sg].append((sum(dmg(x) for x in evs), gid, evs))
        for p in rd.run.pulls:
            sg = rd.seg(p.start + 1)
            if sg not in segs:
                continue
            lines.append(f"### {sg} {rd.t(p.start)}–{rd.t(p.end)}")
            for tot, gid, evs in sorted(segs[sg], key=lambda x: -x[0])[:8]:
                best = max(len({y["targetID"] for y in evs if abs(y["timestamp"] - x["timestamp"]) <= 300})
                           for x in evs)
                pos = [dmg(x) for x in evs if dmg(x) > 0] or [0]
                mine = sum(1 for x in evs if x.get("targetID") == rd.pid)
                lines.append(
                    f"- {ab(rd, gid)}({gid}) · {len(evs)}次 · {len({x['targetID'] for x in evs})}人 · "
                    f"同刻最多{best}人 · 均{wan(sum(pos) / len(pos))}/最大{wan(max(pos))} · 本玩家{mine}次"
                )
        lines.append("")
    return "\n".join(lines)


def debuffs_md(runs):
    lines = [
        "# 本玩家身上的减益",
        "",
        "每行：减益 · 上身次数 · 平均持续 · 消失前后0.5秒内本玩家用过的低频技能（含打断/群控/免疫，≥2场出现控制或打断时务必检查是否可靠控/断提前结束）。超过2分钟的长减益不列。",
        "",
    ]
    for rd in runs:
        lines.append(f"## r{rd.idx} {rd.name}")
        on = {}
        stat = defaultdict(lambda: [0, 0.0, Counter()])
        cnt = Counter(e.get("abilityGameID") for e in rd.casts if e.get("type") == "cast")
        my_casts = [(e["timestamp"], ab(rd, e.get("abilityGameID"))) for e in rd.casts
                    if e.get("type") == "cast" and cnt[e.get("abilityGameID")] <= LOWFREQ_MAX]
        for x in rd.debuffs:
            k = f"{ab(rd, x.get('abilityGameID'))}({x.get('abilityGameID')})"
            if x["type"] == "applydebuff":
                on[k] = x["timestamp"]
                stat[k][0] += 1
            elif x["type"] == "removedebuff" and k in on:
                t0 = on.pop(k)
                stat[k][1] += x["timestamp"] - t0
                near = [n for t, n in my_casts if x["timestamp"] - 500 <= t <= x["timestamp"] + 100]
                for n in near:
                    stat[k][2][n] += 1
        for k, (n, tot, near) in sorted(stat.items(), key=lambda kv: -kv[1][0]):
            if tot / max(n, 1) > 120000:
                continue
            ns = "、".join(f"{a}×{b}" for a, b in near.most_common(4)) or "—"
            lines.append(f"- {k} · {n}次 · 均{tot / max(n, 1) / 1000:.1f}秒 · {ns}")
        lines.append("")
    return "\n".join(lines)


def segments_md(runs):
    lines = [
        "# 波次时间表（含首领战关键机制相对开打时间）",
        "",
    ]
    for rd in runs:
        lines.append(f"## r{rd.idx} {rd.name}（{rd.run.header()}）")
        for p in rd.run.pulls:
            boss_label = "/".join(p.boss_names) or p.name or "首领"
            boss = f" **首领 {boss_label}**" if p.encounter_id else ""
            mobs = "、".join(f"{n}×{c}" for n, c in p.mobs[:5])
            dur = int(round((p.end - p.start) / 1000))
            lines.append(f"- #{p.idx} {rd.t(p.start)}–{rd.t(p.end)}（{dur}s）{boss} {mobs}")
            if p.encounter_id:
                # 统计该首领战内本玩家关键减益首次/二次相对开打时间，辅助冷却算术
                rel_deb = defaultdict(list)
                for x in rd.debuffs:
                    if x.get("type") == "applydebuff" and p.start <= x["timestamp"] <= p.end:
                        nm = ab(rd, x.get("abilityGameID"))
                        if nm not in LONG_DEBUFFS and nm != "自律":
                            rel_deb[nm].append(int(round((x["timestamp"] - p.start) / 1000)))
                if rel_deb:
                    parts = [
                        f"{nm}({'/'.join(f'+{s}s' for s in ts[:4])})"
                        for nm, ts in sorted(rel_deb.items(), key=lambda kv: kv[1][0])[:8]
                    ]
                    lines.append(f"  - 相对开打减益：{'；'.join(parts)}")
        lines.append("")
    return "\n".join(lines)


def spells_md(runs, cfg, client, tal_data=None):
    ids = Counter()
    # 1. 玩家防御与 always 功能技能最高优先级纳入
    for d in cfg["defensives"]:
        ids[d["cast"]] += 10 ** 10
        for b in d.get("buff", []):
            ids[b] += 5 * 10 ** 9
    for g in cfg.get("always", []):
        ids[g] += 8 * 10 ** 9
    # 2. 敌方伤害、全队伤害、本玩家减益、以及非伤害敌方读条/施放（覆盖禁疗/满能量/控制等机制）
    for rd in runs:
        for e in rd.taken:
            ids[e.get("abilityGameID")] += dmg(e) + 1
        for e in rd.team_taken:
            ids[e.get("abilityGameID")] += dmg(e) / 5
        for e in rd.debuffs:
            ids[e.get("abilityGameID")] += 5 * 10 ** 6
        for e in rd.enemy:
            if e.get("type") in ("begincast", "cast"):
                ids[e.get("abilityGameID")] += 2 * 10 ** 5
        for e in rd.interrupts:
            ids[e.get("extraAbilityGameID")] += 3 * 10 ** 6
        for e in rd.dispels:
            ids[e.get("extraAbilityGameID")] += 3 * 10 ** 6

    top = [g for g, _ in ids.most_common(100) if g and g > 1]
    info = wowhead_spells(top, client.lang)

    # 收集天赋改写冷却里涉及的天赋技能 ID 名称，方便直接标出中文天赋名
    mod_ids = sorted({mid for i in info.values() for mid in (i.get("cooldown_mods") or {})})
    mod_info = wowhead_spells(mod_ids, client.lang) if mod_ids else {}

    lines = ["# 技能说明（Wowhead，含玩家基础冷却与天赋改写冷却）", ""]
    for g in top:
        i = info.get(g)
        if not i:
            continue
        meta = []
        if i.get("dispel"):
            meta.append(f"驱散：{i['dispel']}")
        if i.get("cooldown_ms"):
            meta.append(f"基础冷却：{_fmt_cd(i['cooldown_ms'])}")
        if i.get("charges") and i["charges"] > 1:
            meta.append(f"{i['charges']}层充能")
        if i.get("cooldown_mods"):
            mods_s = "，".join(
                f"{(mod_info.get(mid) or {}).get('name', mid)}→{_fmt_cd(ms)}"
                for mid, ms in i["cooldown_mods"].items()
            )
            meta.append(f"天赋改写：{mods_s}")
        head = f"## {i['name']}（{g}）" + (f" · {' · '.join(meta)}" if meta else "")
        body = (i.get("description") or "").replace("\n", " ")
        aura = f" ‖ 效果：{i['aura']}".replace("\n", " / ") if i.get("aura") else ""
        lines.append(f"{head}\n{body}{aura}\n")
    return "\n".join(lines)


def talents(runs, out):
    res = {}
    en = Client(lang="en")
    for rd in runs:
        try:
            r2 = load_run(en, rd.run.url)
            if en.use_v1:
                det = r2.summary.get("playerDetails") or {}
            else:
                rep = fetch(r2, "d: playerDetails(fightIDs: $fid, includeCombatantInfo: true)")
                det = (rep.get("d") or {}).get("data", {}).get("playerDetails", {})
            for role in det.values():
                for p in role:
                    if p.get("name") == rd.name:
                        res[f"r{rd.idx}_{rd.name}"] = p
        except Exception as exc:  # 天赋拿不到不影响其他输出
            res[f"r{rd.idx}_{rd.name}"] = {"error": str(exc)}
    (out / "talents.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    ok = lambda v: isinstance(v.get("combatantInfo"), dict) and v["combatantInfo"].get("talentTree")  # noqa: E731
    return {k: ("ok" if ok(v) else "缺") for k, v in res.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", required=True, help="职业配置 JSON（防御技能及其增益 ID）")
    ap.add_argument("--out", required=True)
    ap.add_argument("runs", nargs="+", help="链接@玩家名")
    a = ap.parse_args()
    cfg = json.loads(Path(a.cls).read_text())
    out = Path(a.out)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    client = Client()
    runs = []
    for i, spec in enumerate(a.runs, 1):
        ref, _, name = spec.rpartition("@")
        runs.append(RunData(i, load_run(client, ref), name, cfg, out / "raw"))
        print(f"r{i} {runs[-1].name} 取数完成", file=sys.stderr)
    names = {d["name"] for d in cfg["defensives"]} | {runs[0].run.ab(d["cast"]) for d in cfg["defensives"]}
    (out / "compare.md").write_text(compare_md(runs))
    (out / "uses.md").write_text(uses_md(runs, names, set(cfg.get("always", []))))
    (out / "interrupts.md").write_text(interrupts_md(runs))
    (out / "team.md").write_text(team_md(runs))
    (out / "debuffs.md").write_text(debuffs_md(runs))
    (out / "segments.md").write_text(segments_md(runs))
    (out / "spells.md").write_text(spells_md(runs, cfg, client))
    tal = talents(runs, out)
    rows = [f"r{rd.idx} | {rd.name} | {rd.run.header()} | {rd.run.url} | 防御窗口 {len(rd.windows)} 个" for rd in runs]
    (out / "README.md").write_text(
        "# 证据包\n\n" + "\n".join(rows) + f"\n\n天赋：{tal}\n\n"
        "文件：compare.md（直击/跳伤拆分后的窗口内外对比，先看这个）、uses.md、interrupts.md（打断/驱散与读条形态）、"
        "team.md、debuffs.md、segments.md（含首领相对开打时间）、spells.md（含玩家冷却与天赋改写）、talents.json、raw/*.json\n"
    )
    for f in sorted(out.glob("*.md")):
        print(f"{f.name}: {len(f.read_text())} 字符", file=sys.stderr)
    print(f"天赋：{tal}；API 实时请求 {client.live} 次", file=sys.stderr)


if __name__ == "__main__":
    main()
