#!/usr/bin/env python3
"""职业手册证据包：把多场录像（现行 5 场）的原始事件算成小表格，供写手册的模型直接读。

不做判断，只做确定性的计算：
  compare.md   每个敌方技能打到本玩家时，按「当时开着哪些防御技能」分组的命中数 / 免疫或未命中数 / 平均伤害
               以及「敌方每次施放后本玩家有没有被打到」的命中率（看点名跳过、反射之类）
  uses.md      本玩家每次使用防御技能和低频技能的情境：所在波次、前后敌方读条、刚吃的伤害、身上减益、随后消失的减益
  team.md      全队承伤：按波次 × 敌方技能，命中人数、单次伤害、同一时刻多人吃（分摊/AOE 信号）
  debuffs.md   本玩家身上的减益：次数、平均持续、提前消失时附近用了什么
  segments.md  波次时间表（首领战标出）
  spells.md    相关技能的 Wowhead 说明（防御技能 + 打到本玩家/全队的主要敌方技能 + 减益）
  talents.json 本玩家的天赋原始数据（playerDetails includeCombatantInfo）
  raw/         原始事件 JSON（需要时自己再算）

用法（仓库根目录）：
  python3 guides/tools/evidence.py --class guides/tools/classes/rogue.json --out <目录> \
      "<WCL链接#fight=N>@玩家名" "<链接>@玩家名" "<链接>@玩家名" "<链接>@玩家名" "<链接>@玩家名"
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

HIT_LABEL = {7: "躲闪", 8: "招架", 9: "反射", 10: "免疫", 4: "格挡", 5: "偏斜", 0: "未命中", 6: "抵抗"}
CAST_HIT_WINDOW = 6000   # 敌方施放后多久内被打到算「这次打到了」
CTX_BEFORE, CTX_AFTER = 4000, 2000
LOWFREQ_MAX = 30
LONG_DEBUFFS = {"筋疲力尽", "心满意足", "时空错位", "疲惫", "Exhaustion", "Sated", "Temporal Displacement"}         # 每场施放次数不超过它的技能算「低频技能」，列进 uses.md


def wan(x: float) -> str:
    return f"{x / 10000:.1f}万" if x >= 10000 else f"{x:.0f}"


def clock(ms: float) -> str:
    s = max(0, ms) / 1000
    return f"{int(s // 60)}:{s % 60:04.1f}"


class RunData:
    def __init__(self, idx: int, run: Run, name: str, cfg: dict, raw_dir: Path):
        self.idx, self.run = idx, run
        self.p = run.find_player(name)
        self.pid, self.name = self.p.id, self.p.name
        self.cfg = cfg
        n = esc(self.name)
        get = lambda **kw: data.events(run, limit=60000, **kw)[0]  # noqa: E731
        self.casts = get(data_type="Casts", hostility="Friendlies", expr=f'source.name = "{n}"')
        self.taken = get(data_type="DamageTaken", hostility="Friendlies", expr=f'target.name = "{n}"')
        self.team_taken = get(data_type="DamageTaken", hostility="Friendlies")
        self.debuffs = get(data_type="Debuffs", hostility="Friendlies", expr=f'target.name = "{n}"')
        buff_ids = sorted({b for d in cfg["defensives"] for b in d.get("buff", [d["cast"]])})
        self.buffs = get(data_type="Buffs", hostility="Friendlies",
                         expr=f'target.name = "{n}" and ability.id in ({",".join(map(str, buff_ids))})')
        self.enemy = get(data_type="Casts", hostility="Enemies")
        names = {"actors": {a: v.get("name") for a, v in run.actors.items()},
                 "abilities": {g: v.get("name") for g, v in run.abilities.items()},
                 "fight_start": run.start}
        (raw_dir / f"run{idx}_names.json").write_text(json.dumps(names, ensure_ascii=False))
        for k in ("casts", "taken", "team_taken", "debuffs", "buffs", "enemy"):
            (raw_dir / f"run{idx}_{k}.json").write_text(json.dumps(getattr(self, k), ensure_ascii=False))
        self.windows = self._windows()

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
        return f"#{p.idx}" + (f" {'/'.join(p.boss_names)}" if p.encounter_id else "")


def ab(rd: RunData, gid) -> str:
    return rd.run.ab(gid)


def dmg(e) -> float:
    return (e.get("amount") or 0) + (e.get("absorbed") or 0)


def compare_md(runs):
    lines = ["# 窗口内外对比（本玩家承伤，按当时开着的防御技能分组）",
             "",
             "每格：命中次数 · 其中0伤害/未命中次数(类型) · 有伤害时平均单次 · 涉及场次。\"无\"=没开任何防御技能，是对照组。",
             "只列总命中≥3 或在任一防御窗口内出现过的敌方技能，按总伤害排序。", ""]
    by = defaultdict(lambda: defaultdict(list))  # name -> combo -> [(run, e)]
    total = Counter()
    for rd in runs:
        for e in rd.taken:
            if e.get("type") != "damage":
                continue
            nm = f"{ab(rd, e.get('abilityGameID'))}({e.get('abilityGameID')})"
            by[nm][rd.active(e["timestamp"])].append((rd.idx, e))
            total[nm] += dmg(e)
    for nm, _ in total.most_common():
        combos = by[nm]
        n = sum(len(v) for v in combos.values())
        if n < 3 and set(combos) == {"无"}:
            continue
        lines.append(f"## {nm} — 共 {n} 次，总 {wan(total[nm])}")
        lines.append("| 当时开着 | 命中 | 0伤害/未命中 | 有伤害平均 | 最大 | 场次 |")
        lines.append("|---|---|---|---|---|---|")
        for combo, evs in sorted(combos.items(), key=lambda kv: (kv[0] != "无", -len(kv[1]))):
            zero = [e for _, e in evs if dmg(e) == 0]
            kinds = Counter(HIT_LABEL.get(e.get("hitType"), f"hit{e.get('hitType')}") for e in zero)
            pos = [dmg(e) for _, e in evs if dmg(e) > 0]
            avg = wan(sum(pos) / len(pos)) if pos else "—"
            mx = wan(max(pos)) if pos else "—"
            rs = "/".join(f"r{r}" for r in sorted({r for r, _ in evs}))
            zs = f"{len(zero)}（{'、'.join(f'{k}{v}' for k, v in kinds.items())}）" if zero else "0"
            lines.append(f"| {combo} | {len(evs)} | {zs} | {avg} | {mx} | {rs} |")
        lines.append("")
    # 每次敌方施放后有没有打到本玩家
    lines += ["# 敌方每次施放后本玩家是否被打到（同名技能，施放后6秒内）", "",
              "看点名跳过/反射/免疫：比较「施放时开着X」与「无」的被打到比例。只列施放≥4次且打到过本玩家的技能。", ""]
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
    lines = ["# 本玩家技能使用情境", "",
             "每行：时间 波次 技能 → 目标 | 前4秒/后2秒敌方读条或施放 | 前3秒吃到的伤害 | 使用时身上减益 | 使用后0.5秒内消失的减益", ""]
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
            on, gone = set(), []
            state = {}
            for x in rd.debuffs:
                if x["timestamp"] > ts + 500:
                    break
                k = ab(rd, x.get("abilityGameID"))
                if x["type"] in ("applydebuff", "refreshdebuff", "applydebuffstack"):
                    state[k] = True
                elif x["type"] == "removedebuff":
                    if ts - 100 <= x["timestamp"] <= ts + 500 and state.get(k):
                        gone.append(k)
                    state[k] = False
            on = [k for k, v in state.items() if v and k not in LONG_DEBUFFS] + gone
            lines.append(f"- {rd.t(ts)} {rd.seg(ts)} **{name}**{tgt_s} | {'、'.join(ctx[:8]) or '—'} | "
                         f"{'、'.join(f'{k}{wan(v)}' for k, v in hits.most_common(3)) or '—'} | "
                         f"{'、'.join(sorted(set(on))) or '—'} | {'、'.join(gone) or '—'}")
        lines.append("")
    return "\n".join(lines)


def team_md(runs):
    lines = ["# 全队承伤（按波次 × 敌方技能）", "",
             "每行：技能 · 命中次数 · 被打到的不同玩家数 · 同一时刻(±0.3s)最多几名不同玩家一起吃 · 单次平均/最大 · 本玩家吃了几次。每波只列总伤害前8。", ""]
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
                lines.append(f"- {ab(rd, gid)}({gid}) · {len(evs)}次 · {len({x['targetID'] for x in evs})}人 · "
                             f"同刻最多{best}人 · 均{wan(sum(pos) / len(pos))}/最大{wan(max(pos))} · 本玩家{mine}次")
        lines.append("")
    return "\n".join(lines)


def debuffs_md(runs):
    lines = ["# 本玩家身上的减益", "", "每行：减益 · 上身次数 · 平均持续 · 消失前后0.5秒内本玩家用过的低频技能（可能是它清掉的）。超过2分钟的长减益不列。", ""]
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
                continue  # 筋疲力尽之类的长减益
            ns = "、".join(f"{a}×{b}" for a, b in near.most_common(4)) or "—"
            lines.append(f"- {k} · {n}次 · 均{tot / max(n, 1) / 1000:.1f}秒 · {ns}")
        lines.append("")
    return "\n".join(lines)


def segments_md(runs):
    lines = ["# 波次时间表", ""]
    for rd in runs:
        lines.append(f"## r{rd.idx} {rd.name}（{rd.run.header()}）")
        for p in rd.run.pulls:
            boss = f" **首领 {'/'.join(p.boss_names)}**" if p.encounter_id else ""
            mobs = "、".join(f"{n}×{c}" for n, c in p.mobs[:5])
            lines.append(f"- #{p.idx} {rd.t(p.start)}–{rd.t(p.end)}{boss} {mobs}")
        lines.append("")
    return "\n".join(lines)


def spells_md(runs, cfg, client):
    ids = Counter()
    for d in cfg["defensives"]:
        ids[d["cast"]] += 10 ** 9
    for rd in runs:
        for e in rd.taken:
            ids[e.get("abilityGameID")] += dmg(e) + 1
        for e in rd.team_taken:
            ids[e.get("abilityGameID")] += dmg(e) / 5
        for e in rd.debuffs:
            ids[e.get("abilityGameID")] += 10 ** 6
    top = [g for g, _ in ids.most_common(70) if g and g > 1]
    info = wowhead_spells(top, client.lang)
    lines = ["# 技能说明（Wowhead）", ""]
    for g in top:
        i = info.get(g)
        if not i:
            continue
        head = f"## {i['name']}（{g}）" + (f" · 驱散：{i['dispel']}" if i.get("dispel") else "")
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
    (out / "team.md").write_text(team_md(runs))
    (out / "debuffs.md").write_text(debuffs_md(runs))
    (out / "segments.md").write_text(segments_md(runs))
    (out / "spells.md").write_text(spells_md(runs, cfg, client))
    tal = talents(runs, out)
    rows = [f"r{rd.idx} | {rd.name} | {rd.run.header()} | {rd.run.url} | 防御窗口 {len(rd.windows)} 个" for rd in runs]
    (out / "README.md").write_text("# 证据包\n\n" + "\n".join(rows) + f"\n\n天赋：{tal}\n\n"
                                   "文件：compare.md（窗口内外对比，先看这个）、uses.md、team.md、debuffs.md、"
                                   "segments.md、spells.md、talents.json、raw/*.json\n")
    for f in sorted(out.glob("*.md")):
        print(f"{f.name}: {len(f.read_text())} 字符", file=sys.stderr)
    print(f"天赋：{tal}；API 实时请求 {client.live} 次", file=sys.stderr)


if __name__ == "__main__":
    main()
