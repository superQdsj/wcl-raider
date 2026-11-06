"""splits 命令：按首领把一把钥石切成几段，逐段与参考记录比用时和路线（速通式分段对比）。

一段 = 从上一个首领击杀（或钥石开始）到下一个首领击杀。段内包括该段的小怪、首领战、失败尝试和脱战时间。
参考记录优先选"路线最像"的同层带日志记录，也可以用 --ref 指定（例如自己上一把限时的记录）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import fmt
from .api import DAY, HOUR, RATE, WCLError
from .context import Run, parse_ref, table_data
from .data import parallel

Q_RANKINGS = """query($id: Int!, $bracket: Int!, $page: Int!) {
  worldData { encounter(id: $id) { fightRankings(bracket: $bracket, page: $page) } }
  %s
}""" % RATE

Q_REF_FIGHTS = """query($code: String!) {
  reportData { report(code: $code) { fights { id name encounterID difficulty keystoneLevel kill } } }
  %s
}""" % RATE

Q_REF = """query($code: String!, $fid: [Int]!) {
  reportData { report(code: $code) {
    masterData { actors(type: "NPC") { gameID name subType } }
    fights(fightIDs: $fid) { id name encounterID startTime endTime keystoneTime keystoneLevel keystoneBonus kill
      averageItemLevel npcCountMap
      dungeonPulls { encounterID kill startTime endTime enemyNPCs { gameID minimumInstanceID maximumInstanceID } } }
    deaths: table(dataType: Deaths, fightIDs: $fid)
  } }
  %s
}""" % RATE

FRIENDLY_TYPES = set(fmt.CLASS_ZH)


# ---------------------------------------------------------------- 纯数据结构（便于离线测试）

@dataclass
class Wave:
    idx: int
    start: float              # 相对钥石开始
    dur: float
    encounter: int
    kill: Optional[bool]
    mobs: Dict[int, int]      # 去重后的 gameID -> 数量（之前的波次里出现过的怪不再计入）
    raw: Dict[int, int] = field(default_factory=dict)  # 不去重：这一波实际出现的怪


@dataclass
class Segment:
    encounter: int            # 0 = 最后一个首领之后的收尾 / 未完成
    start: float              # 相对钥石开始的毫秒
    end: float
    pulls: int = 0            # 小怪波数
    combat: float = 0.0
    boss: float = 0.0         # 击杀那一次的首领战用时
    wipes: float = 0.0        # 失败的首领尝试用时合计
    wipe_count: int = 0
    deaths: int = 0
    forces: float = 0.0
    mobs: Dict[int, int] = field(default_factory=dict)  # 小怪 gameID -> 数量
    pull_idx: List[int] = field(default_factory=list)   # 本场的波次编号（仅本场有意义）
    waves: List["Wave"] = field(default_factory=list)

    @property
    def dur(self) -> float:
        return self.end - self.start

    @property
    def idle(self) -> float:
        return max(0.0, self.dur - self.combat)

    @property
    def trash(self) -> float:
        return max(0.0, self.combat - self.boss - self.wipes)


def _valid(pulls: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted((p for p in pulls if p["endTime"] - p["startTime"] >= 1000), key=lambda p: p["startTime"])


def _union(spans: List[Tuple[float, float]]) -> float:
    total, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(spans):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def _npc_counts(pull: Dict[str, Any], seen: Optional[set] = None) -> Dict[int, int]:
    """该波出现的敌方 NPC 数量。传入 seen 时按 (gameID, 实例) 去重：同一只怪跨两波只算在第一次出现的那波。"""
    out: Dict[int, int] = {}
    for npc in pull.get("enemyNPCs") or []:
        gid = int(npc.get("gameID") or 0)
        if not gid:
            continue
        lo, hi = npc.get("minimumInstanceID") or 1, npc.get("maximumInstanceID") or 1
        n = 0
        for inst in range(lo, max(lo, hi) + 1):
            if seen is not None:
                if (gid, inst) in seen:
                    continue
                seen.add((gid, inst))
            n += 1
        if n:
            out[gid] = out.get(gid, 0) + n
    return out


def build_segments(pulls: Sequence[Dict[str, Any]], start: float, end: float,
                   npc_count: Dict[str, Any], death_ts: Sequence[float]) -> List[Segment]:
    """把 dungeonPulls（报告相对毫秒）切成首领分段；返回的时间相对钥石开始。"""
    rel_deaths = sorted(t - start for t in death_ts)
    segs: List[Segment] = []
    cur: List[Tuple[int, Dict[str, Any]]] = []
    seg_start = 0.0
    killed = set()
    seen: set = set()
    valid = _valid(pulls)

    def close(enc: int, seg_end: float) -> None:
        seg = Segment(encounter=enc, start=seg_start, end=seg_end)
        spans = []
        for idx, p in cur:
            s, e = p["startTime"] - start, p["endTime"] - start
            spans.append((s, e))
            counts = _npc_counts(p, seen)
            raw = _npc_counts(p)
            seg.forces += sum(float(npc_count.get(str(g), 0) or 0) * n for g, n in counts.items())
            seg.pull_idx.append(idx)
            p_enc = p.get("encounterID") or 0
            seg.waves.append(Wave(idx=idx, start=s, dur=e - s, encounter=p_enc, kill=p.get("kill"), mobs=counts, raw=raw))
            if p_enc > 0:
                if p.get("kill") and p_enc == enc:
                    seg.boss = e - s
                elif not p.get("kill"):
                    seg.wipes += e - s
                    seg.wipe_count += 1
                else:
                    seg.boss += e - s  # 罕见：同一段里击杀了另一个首领（顺序异常），计入首领用时
                # 一起拉进首领战的小怪（给进度的）也算这一段拉的怪；首领本体和机制刷出的小怪不给进度
                for g, n in counts.items():
                    if float(npc_count.get(str(g), 0) or 0) > 0:
                        seg.mobs[g] = seg.mobs.get(g, 0) + n
            else:
                seg.pulls += 1
                for g, n in counts.items():
                    seg.mobs[g] = seg.mobs.get(g, 0) + n
        seg.combat = _union(spans)
        seg.deaths = sum(1 for t in rel_deaths if seg.start <= t < seg.end or (enc == 0 and t >= seg.start))
        segs.append(seg)

    for i, p in enumerate(valid, start=1):
        cur.append((i, p))
        enc = p.get("encounterID") or 0
        if enc > 0 and p.get("kill") and enc not in killed:
            killed.add(enc)
            close(enc, p["endTime"] - start)
            cur = []
            seg_start = p["endTime"] - start
    if cur:
        close(0, max(end - start, max(p["endTime"] for _, p in cur) - start))
    elif segs and end - start - segs[-1].end > 5000:
        # 最后一个首领之后还有一段记录（例如尾声），算作收尾
        close(0, end - start)
    return segs


def route_similarity(a: Dict[int, int], b: Dict[int, int], weight: Dict[int, float]) -> float:
    """按怪物进度值加权的 Jaccard：两边都拉了的怪 / 任一边拉了的怪。

    不给进度的怪（召唤物、首领机制刷出的小怪）不是路线选择，不参与比较。"""
    keys = {k for k in set(a) | set(b) if weight.get(k)}
    if not keys:
        return 0.0
    num = den = 0.0
    for k in keys:
        w = weight[k]
        num += w * min(a.get(k, 0), b.get(k, 0))
        den += w * max(a.get(k, 0), b.get(k, 0))
    return num / den if den else 0.0


def total_mobs(segs: Sequence[Segment]) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for s in segs:
        for g, n in s.mobs.items():
            out[g] = out.get(g, 0) + n
    return out


def pace_excess(ours: Segment, ours_total: float, ref: Segment, ref_total: float) -> float:
    """按整体节奏折算后，本段比参考多用的时间：本段用时 − 参考本段用时 × (本场总用时 ÷ 参考总用时)。"""
    if ref_total <= 0:
        return 0.0
    return ours.dur - ref.dur * (ours_total / ref_total)


def mob_costs(seg: Segment, weight: Dict[int, float]) -> Dict[int, float]:
    """参考这一段里，每种（给进度的）小怪平均花了多少战斗时间：每波的用时按进度比例分给波里的怪。"""
    cost: Dict[int, float] = {}
    count: Dict[int, int] = {}
    for w in seg.waves:
        if w.encounter:
            continue
        mobs = {g: n for g, n in w.mobs.items() if weight.get(g)}
        total = sum(weight[g] * n for g, n in mobs.items())
        if total <= 0:
            continue
        for g, n in mobs.items():
            cost[g] = cost.get(g, 0.0) + w.dur * weight[g] * n / total
            count[g] = count.get(g, 0) + n
    return {g: cost[g] / count[g] for g in cost if count.get(g)}


def wave_ref_time(wave: Wave, costs: Dict[int, float], weight: Dict[int, float]) -> Tuple[Optional[float], float]:
    """参考拉同样这些怪大约要多久。返回 (估计用时, 覆盖率)。

    覆盖率 = 本波（去重后、给进度的）怪里，参考同一段也拉了的比例（按进度）。参考没拉的部分按比例放大。
    本波的怪全都在之前出现过（例如灭团后重拉）时返回 (0, 1)：参考不需要花这段时间。
    """
    mobs = {g: n for g, n in wave.mobs.items() if weight.get(g)}
    if not mobs:
        raw = {g: n for g, n in wave.raw.items() if weight.get(g)}
        return (0.0, 1.0) if raw else (None, 0.0)
    total = sum(weight[g] * n for g, n in mobs.items())
    covered = sum(weight[g] * n for g, n in mobs.items() if g in costs)
    if covered <= 0:
        return None, 0.0
    est = sum(costs[g] * n for g, n in mobs.items() if g in costs)
    cov = covered / total
    return est / cov, cov


# ---------------------------------------------------------------- 获取参考记录

@dataclass
class RefRun:
    code: str
    fid: int
    level: int
    bonus: int
    kill: bool
    keystone_time: Optional[float]
    duration: float
    ilvl: Optional[float]
    team: str
    segs: List[Segment]
    names: Dict[int, str]
    weight: Dict[int, float]
    deaths: int
    source: str               # "排名第N" / "指定"
    similarity: float = 0.0

    @property
    def label(self) -> str:
        return f"{self.code}#{self.fid}"

    @property
    def boss_order(self) -> List[int]:
        return [s.encounter for s in self.segs if s.encounter]


def _fetch_ref(run: Run, code: str, fid: int, team: str, source: str) -> Optional[RefRun]:
    payload = run.client.gql(Q_REF, {"code": code, "fid": [fid]}, ttl=7 * DAY, partial=True)
    if payload.get("_errors"):
        return None
    rep = (payload.get("reportData") or {}).get("report") or {}
    fights = rep.get("fights") or []
    if not fights:
        return None
    f = fights[0]
    if not f.get("keystoneLevel"):
        return None
    death_ts = []
    for e in table_data(rep.get("deaths")).get("entries") or []:
        if (e.get("type") or "") in FRIENDLY_TYPES and e.get("timestamp") is not None:
            death_ts.append(float(e["timestamp"]))
    npc_count = f.get("npcCountMap") or {}
    segs = build_segments(f.get("dungeonPulls") or [], f["startTime"], f["endTime"], npc_count, death_ts)
    names = {int(a["gameID"]): a.get("name") or "?" for a in ((rep.get("masterData") or {}).get("actors") or [])
             if a.get("gameID")}
    return RefRun(code=code, fid=fid, level=f.get("keystoneLevel") or 0, bonus=f.get("keystoneBonus") or 0,
                  kill=bool(f.get("kill")), keystone_time=f.get("keystoneTime"),
                  duration=f["endTime"] - f["startTime"], ilvl=f.get("averageItemLevel"), team=team,
                  segs=segs, names=names, weight={int(k): float(v or 0) for k, v in npc_count.items()},
                  deaths=len(death_ts), source=source)


def _candidates(run: Run, level: int, want: int) -> Tuple[List[Dict[str, Any]], str]:
    for bracket in (level - 1, 0):
        rows: List[Dict[str, Any]] = []
        for page in (1, 2, 3):
            data_ = run.client.gql(Q_RANKINGS, {"id": run.encounter_id, "bracket": bracket, "page": page}, ttl=6 * HOUR)
            fr = ((data_.get("worldData") or {}).get("encounter") or {}).get("fightRankings") or {}
            for r in fr.get("rankings") or []:
                rep = r.get("report") or {}
                if not rep.get("code") or rep.get("fightID") is None:
                    continue
                if rep["code"] == run.code and rep["fightID"] == run.fight_id:
                    continue
                if any(x["report"]["code"] == rep["code"] and x["report"]["fightID"] == rep["fightID"] for x in rows):
                    continue
                r["_rank"] = len(rows) + 1
                rows.append(r)
            if len(rows) >= want or not fr.get("hasMorePages"):
                break
        if len(rows) >= 2 or bracket == 0:
            return rows[:want], (f"同层 +{level}" if bracket else "全部层数（同层带日志的记录不足）")
    return [], "无"


def _resolve_ref(run: Run, ref: str) -> Tuple[str, int]:
    text = ref.strip()
    if "#" in text and "://" not in text and len(text.split("#")[0]) in (16, 18):
        code, fid = text.split("#", 1)
        return code, int(fid)
    code, fight = parse_ref(text)
    if fight is not None:
        return code, int(fight)
    data_ = run.client.gql(Q_REF_FIGHTS, {"code": code}, ttl=DAY)
    fights = ((data_.get("reportData") or {}).get("report") or {}).get("fights") or []
    same = [f for f in fights if f.get("difficulty") == 10 and (f.get("keystoneLevel") or 0) > 0
            and f.get("encounterID") == run.encounter_id]
    if not same:
        raise WCLError(f"参考报告 {code} 里没有 {run.dungeon} 的大秘境记录；请用 CODE#fight 指定。")
    return code, (next((f for f in reversed(same) if f.get("kill")), same[-1]))["id"]


# ---------------------------------------------------------------- 命令

def cmd_splits(run: Run, refs: int = 3, candidates: int = 8, level: Optional[int] = None,
               explicit: Optional[List[str]] = None) -> str:
    deaths_ts = [run.start + (d.get("deathTime") or 0) for d in run.player_deaths()]
    ours = build_segments(run.raw_pulls, run.start, run.end, run.npc_count, deaths_ts)
    if not ours:
        raise WCLError("本场没有可用的波次数据。")
    our_total = run.duration
    weight = {int(k): float(v or 0) for k, v in run.npc_count.items()}
    our_mobs = total_mobs(ours)
    names: Dict[int, str] = {}
    for a in run.actors.values():
        if a.get("type") == "NPC" and a.get("gameID"):
            names.setdefault(int(a["gameID"]), a.get("name") or "?")
    boss_names: Dict[int, str] = {}
    for p in run.pulls:
        if p.is_boss and p.encounter_id not in boss_names:
            boss_names[p.encounter_id] = "、".join(p.boss_names) or p.name

    level = level or run.level
    tasks = {}
    if explicit:
        for i, ref in enumerate(explicit):
            code, fid = _resolve_ref(run, ref)
            tasks[f"x{i}"] = (lambda c=code, f=fid: _fetch_ref(run, c, f, "", "指定"))
    note = "指定的参考记录"
    picked_from = 0
    if not explicit or len(explicit) < refs:
        rows, note = _candidates(run, level, candidates)
        picked_from = len(rows)
        for r in rows:
            team = " ".join(fmt.class_spec(t.get("class", ""), t.get("spec", "")).split("-")[-1]
                            for t in r.get("team") or [])
            tasks[f"r{r['_rank']}"] = (lambda r=r, team=team: _fetch_ref(
                run, r["report"]["code"], r["report"]["fightID"], team, f"排名第{r['_rank']}"))
    if not tasks:
        raise WCLError("没有找到可对比的参考记录（该副本在 WCL 上没有带日志的排名）。")
    got = parallel(tasks, workers=5)
    pool = [v for v in got.values() if v]
    if not pool:
        raise WCLError("参考记录的数据获取失败（报告可能已被设为私密或删除）。")
    our_order = [s.encounter for s in ours if s.encounter]
    for r in pool:
        r.similarity = route_similarity(our_mobs, total_mobs(r.segs), weight)
        names.update({k: v for k, v in r.names.items() if k not in names})
    chosen = [r for r in pool if r.source == "指定"]
    ranked = sorted((r for r in pool if r.source != "指定" and r.kill),
                    key=lambda r: (r.boss_order != our_order, -round(r.similarity, 2), r.duration))
    chosen += ranked[: max(0, refs - len(chosen))]
    if not chosen:
        raise WCLError("候选记录里没有完成的钥石可作参考。")

    lines = [f"# 分段计时对比 — {run.header()}",
             "一段 = 从上一个首领击杀（或钥石开始）到下一个首领击杀。所有时间是**实际经过的时间**（WCL 计时，"
             "不含死亡罚时）；罚时单独列出。"]

    # 参考记录
    crow = []
    for r in sorted(pool, key=lambda r: (r not in chosen, -r.similarity)):
        order_ok = "一致" if r.boss_order == our_order else "不同"
        crow.append(["✓" if r in chosen else "", r.source, r.label, f"+{r.level}",
                     (f"限时+{r.bonus}" if r.bonus else "超时") if r.kill else "未完成",
                     fmt.clock(r.keystone_time, True) if r.keystone_time else "—",
                     f"{r.ilvl:.1f}" if r.ilvl else "—", r.team or "—", r.deaths,
                     f"{r.similarity * 100:.0f}%", order_ok])
    our_ilvl = run.fight.get("averageItemLevel")
    lines += ["", f"## 参考记录（来源：{note}" + (f"，候选 {picked_from} 条" if picked_from else "") + "）",
              f"本场：+{run.level}，" + (fmt.clock(run.keystone_time, True) if run.keystone_time else "未完成") +
              (f"，装等 {our_ilvl:.1f}" if our_ilvl else "") + f"，死亡 {len(deaths_ts)}。",
              fmt.table(["选用", "来源", "报告", "层数", "结果", "官方用时", "装等", "阵容", "死亡", "路线相似度", "首领顺序"], crow),
              "路线相似度 = 全场小怪构成按进度值加权的重合度（100% = 拉的怪完全一样）。优先选首领顺序一致、路线最像的记录。"]

    # 分段计时
    def ref_seg(r: RefRun, seg: Segment) -> Optional[Segment]:
        return next((s for s in r.segs if s.encounter == seg.encounter), None)

    heads = ["段", "本场"] + [f"参考{i + 1}" for i in range(len(chosen))] + ["参考中位", "本段差", "按节奏折算超额", "累计差"]
    trow = []
    penalty, _ = run.death_penalty(len(deaths_ts))
    cum_diff_rows = []
    for k, seg in enumerate(ours):
        name = f"{k + 1}. 到 {boss_names.get(seg.encounter, seg.encounter)}" if seg.encounter else f"{k + 1}. 收尾/未完成"
        cells = [name, fmt.clock(seg.dur)]
        durs, excess, cums = [], [], []
        for r in chosen:
            rs = ref_seg(r, seg)
            cells.append(fmt.clock(rs.dur) if rs else "—")
            if rs:
                durs.append(rs.dur)
                excess.append(pace_excess(seg, our_total, rs, r.duration))
                cums.append(seg.end - rs.end)
        med = fmt.median(durs)
        cells.append(fmt.clock(med) if med is not None else "—")
        cells.append(_signed(seg.dur - med) if med is not None else "—")
        ex = fmt.median(excess)
        cells.append(_signed(ex) if ex is not None else "—")
        cum = fmt.median(cums)
        cells.append(_signed(cum) if cum is not None else "—")
        trow.append(cells)
        cum_diff_rows.append((seg, med, ex))
    ref_totals = [r.duration for r in chosen]
    trow.append(["合计（实际时长）", fmt.clock(our_total)] + [fmt.clock(t) for t in ref_totals] +
                [fmt.clock(fmt.median(ref_totals)), _signed(our_total - fmt.median(ref_totals)), "", ""])
    lines += ["", "## 分段用时", fmt.table(heads, trow),
              "- 本段差 = 本场 − 参考中位；累计差 = 到这个首领击杀时，本场比参考落后（+）或领先（−）多少。",
              "- 按节奏折算超额 = 本段用时 − 参考本段用时 × (本场总时长 ÷ 参考总时长)，取各参考的中位数。"
              "它扣掉了装等、层数带来的整体快慢，**正值大的段 = 比本场平均水平丢得更多的段**，是复盘的重点。",
              f"- 死亡罚时另计：本场 {len(deaths_ts)} 次 × {penalty / 1000:g} 秒 = {fmt.clock(len(deaths_ts) * penalty)}。"]

    # 分段构成
    brow = []
    for k, seg in enumerate(ours):
        rs_list = [x for x in (ref_seg(r, seg) for r in chosen) if x]

        def med_of(attr: str) -> Optional[float]:
            return fmt.median([getattr(x, attr) for x in rs_list])

        def pair(ours_v: float, attr: str, clock: bool = True) -> str:
            m = med_of(attr)
            if clock:
                return f"{fmt.clock(ours_v)} / {fmt.clock(m) if m is not None else '—'}"
            return f"{ours_v:g} / {m:g}" if m is not None else f"{ours_v:g} / —"

        req = run.fight.get("countRequired") or 0
        f_ours = fmt.pct(seg.forces, req, 1) if req else f"{seg.forces:g}"
        f_ref = med_of("forces")
        f_ref_txt = (fmt.pct(f_ref, req, 1) if req else f"{f_ref:g}") if f_ref is not None else "—"
        pulls_txt = (f"#{seg.pull_idx[0]}–#{seg.pull_idx[-1]}" if len(seg.pull_idx) > 1 else
                     (f"#{seg.pull_idx[0]}" if seg.pull_idx else "—"))
        brow.append([f"{k + 1}", pulls_txt, pair(seg.pulls, "pulls", False), pair(seg.trash, "trash"),
                     pair(seg.boss, "boss"), (f"{seg.wipe_count}次 {fmt.clock(seg.wipes)}" if seg.wipe_count else "—")
                     + " / " + (fmt.clock(med_of("wipes")) if med_of("wipes") else "—"),
                     pair(seg.idle, "idle"), pair(seg.deaths, "deaths", False), f"{f_ours} / {f_ref_txt}"])
    lines += ["", "## 每段的时间花在哪（本场 / 参考中位）",
              fmt.table(["段", "本场波次", "小怪波数", "小怪战斗", "首领击杀", "首领失败尝试", "脱战", "死亡", "进度"], brow),
              "- 小怪战斗 = 段内战斗时间 − 首领战；脱战 = 段用时 − 战斗时间（跑路、等冷却、喝水、跑尸都在这里）。",
              "- 几波连着拉、中间不脱战会被 WCL 合并成一波，所以\"波数\"少不一定是拉得少。"]

    # 波次对照
    pace = fmt.median([our_total / r.duration for r in chosen if r.duration]) or 1.0
    wrows = []
    for k, seg in enumerate(ours):
        per_ref = []
        for r in chosen:
            rs = ref_seg(r, seg)
            per_ref.append(mob_costs(rs, weight) if rs else None)
        for w in seg.waves:
            content = (f"首领 {boss_names.get(w.encounter, w.encounter)}" + ("" if w.kill else "（未击杀）")
                       if w.encounter else _mob_text(w.raw, names, weight))
            if not w.encounter and w.raw and not any(weight.get(g) for g in w.mobs):
                content += "（全是之前出现过的怪：重拉/跨波）"
            if w.encounter:
                refs_d = [x.boss for x in (ref_seg(r, seg) for r in chosen) if x and x.boss] if w.kill else []
                ref_med = fmt.median(refs_d) if refs_d else None
                matched = f"{len(refs_d)}/{len(chosen)}" if w.kill else "失败尝试"
            else:
                durs, covs = [], []
                for costs in per_ref:
                    if costs is None:
                        continue
                    est, cov = wave_ref_time(w, costs, weight)
                    if est is not None and cov >= 0.5:
                        durs.append(est)
                        covs.append(cov)
                ref_med = fmt.median(durs) if durs else None
                matched = (f"{len(durs)}/{len(chosen)}（覆盖 {fmt.median(covs) * 100:.0f}%）" if durs
                           else f"0/{len(chosen)}")
            if ref_med is None:
                ref_txt = diff = adj = "—"
            else:
                ref_txt, diff, adj = fmt.clock(ref_med), _signed(w.dur - ref_med), _signed(w.dur - ref_med * pace)
            wrows.append([f"{k + 1}", f"#{w.idx}", fmt.clock(w.start), content, fmt.clock(w.dur), ref_txt, diff, adj,
                          matched])
    lines += ["", "## 波次对照（本场每一波 vs 参考拉同样这些怪大约用多久，取中位）",
              fmt.table(["段", "波", "开始", "内容", "本场用时", "参考估计", "差", "扣掉整体快慢后", "可比参考"], wrows),
              f"- 扣掉整体快慢后 = 本场用时 − 参考估计 × {pace:.2f}（本场总时长 ÷ 参考总时长，取中位）。"
              "正值大的波 = 比本场平均节奏慢得更多的波。",
              "- 参考估计：在参考的同一段里，把每波的战斗时间按进度分给波里的怪，得到每种怪的平均耗时，"
              "再按本场这一波拉的怪加总。参考拆拉或合拉都能比；只算战斗时间，不含波与波之间的脱战。",
              "- 覆盖 = 本场这一波的怪，参考同一段也拉了的比例（按进度），低于 50% 不比较。"
              "之前出现过的怪（灭团后重拉）参考估计为 0，整波都算多花的时间。",
              "- 差值只用来指出\"可能慢在这一波\"，原因要回到 `pulls`/`deaths`/`events` 核实。"]

    # 路线差异
    rlines = []
    for k, seg in enumerate(ours):
        rs_list = [x for x in (ref_seg(r, seg) for r in chosen) if x]
        if not rs_list:
            continue
        gids = set(seg.mobs) | {g for x in rs_list for g in x.mobs}
        more, less = [], []
        for g in gids:
            if not weight.get(g):
                continue  # 不给进度的召唤物/机制小怪，不算路线差异
            o = seg.mobs.get(g, 0)
            m = fmt.median([x.mobs.get(g, 0) for x in rs_list]) or 0
            d = o - m
            if abs(d) < 1:
                continue
            w = weight[g]
            item = (abs(d) * w, f"{names.get(g, g)}×{abs(d):g}（进度 {w * abs(d):g}）")
            (more if d > 0 else less).append(item)
        if more or less:
            more.sort(key=lambda x: -x[0])
            less.sort(key=lambda x: -x[0])
            txt = f"- 第 {k + 1} 段："
            if more:
                txt += "本场多拉 " + "、".join(t for _, t in more[:6])
            if less:
                txt += ("；" if more else "") + "本场没拉/少拉 " + "、".join(t for _, t in less[:6])
            rlines.append(txt)
    lines += ["", "## 路线差异（本场 vs 参考中位，按段）"] + (rlines or ["- 各段拉的小怪与参考基本一致。"])
    lines.append("- 进度值是该怪的计数（与 countRequired 同单位）。多拉的怪如果进度最后溢出，就是可以省的时间；"
                 "少拉的怪要看是在别的段补上了，还是走了另一条路。")
    if req := run.fight.get("countRequired"):
        lines.append(f"- 全场进度：本场 {fmt.pct(run.fight.get('countReached'), req, 1)}。")
    return "\n".join(lines)


def _mob_text(mobs: Dict[int, int], names: Dict[int, str], weight: Dict[int, float], limit: int = 3) -> str:
    items = sorted(mobs.items(), key=lambda kv: -(kv[1] * (weight.get(kv[0]) or 0.1)))
    parts = [f"{names.get(g, g)}×{n}" for g, n in items[:limit]]
    if len(items) > limit:
        parts.append(f"+{len(items) - limit}种")
    return " ".join(parts) or "—"


def _signed(ms: Optional[float]) -> str:
    if ms is None:
        return "—"
    if abs(ms) < 500:
        return "±0:00"
    return ("+" if ms > 0 else "−") + fmt.clock(abs(ms))
