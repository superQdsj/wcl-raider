"""compare / spec 命令：与同副本同层的高分记录、同专精顶尖玩家对比。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import data, fmt
from .api import DAY, HOUR, RATE, WCLError
from .context import Run, table_data

Q_FIGHT_RANKINGS = """query($id: Int!, $bracket: Int!) {
  worldData { encounter(id: $id) { name fightRankings(bracket: $bracket, page: 1) } }
  %s
}""" % RATE

Q_CHAR_RANKINGS = """query($id: Int!, $cls: String!, $spec: String!, $metric: CharacterRankingMetricType!, $bracket: Int!) {
  worldData { encounter(id: $id) { name characterRankings(className: $cls, specName: $spec, metric: $metric,
    bracket: $bracket, page: 1) } }
  %s
}""" % RATE

Q_BENCH_RUN = """query($code: String!, $fid: [Int]!) {
  reportData { report(code: $code) {
    fights(fightIDs: $fid) { id name startTime endTime keystoneTime keystoneLevel keystoneBonus kill
      dungeonPulls { encounterID kill startTime endTime } }
    dt: table(dataType: DamageTaken, fightIDs: $fid, viewBy: Ability)
    intr: table(dataType: Interrupts, fightIDs: $fid)
  } }
  %s
}""" % RATE

Q_BENCH_PLAYER = """query($code: String!, $fid: [Int]!) {
  reportData { report(code: $code) {
    fights(fightIDs: $fid) { id startTime endTime keystoneLevel dungeonPulls { startTime endTime } }
    pd: playerDetails(fightIDs: $fid)
    dd: table(dataType: DamageDone, fightIDs: $fid)
  } }
  %s
}""" % RATE

Q_BENCH_CASTS = """query($code: String!, $fid: [Int]!, $sid: Int!) {
  reportData { report(code: $code) { c: table(dataType: Casts, fightIDs: $fid, sourceID: $sid) } }
  %s
}""" % RATE


def _union_ms(pulls: List[Dict[str, Any]]) -> float:
    total, cur_s, cur_e = 0.0, None, None
    for p in sorted(pulls, key=lambda x: x["startTime"]):
        if p["endTime"] - p["startTime"] < 1000:
            continue
        if cur_e is None or p["startTime"] > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = p["startTime"], p["endTime"]
        else:
            cur_e = max(cur_e, p["endTime"])
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def _logged(rows: List[Dict[str, Any]], run: Run) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        rep = r.get("report") or {}
        if not rep.get("code") or rep.get("fightID") is None:
            continue
        if rep["code"] == run.code and rep["fightID"] == run.fight_id:
            continue
        out.append(r)
    return out


def _fight_rankings(run: Run, level: int) -> Tuple[List[Dict[str, Any]], str]:
    tried = []
    for bracket in (level - 1, 0):
        data_ = run.client.gql(Q_FIGHT_RANKINGS, {"id": run.encounter_id, "bracket": bracket}, ttl=6 * HOUR)
        enc = (data_.get("worldData") or {}).get("encounter") or {}
        rows = _logged(((enc.get("fightRankings") or {}).get("rankings")) or [], run)
        tried.append(bracket)
        if len(rows) >= 2 or bracket == 0:
            note = f"同层 +{level}" if bracket else "全部层数（同层可用记录不足）"
            return rows, note
    return [], "无"


def _bench_run(run: Run, code: str, fid: int) -> Dict[str, Any]:
    data_ = run.client.gql(Q_BENCH_RUN, {"code": code, "fid": [fid]}, ttl=7 * DAY, partial=True)
    rep = (data_.get("reportData") or {}).get("report") or {}
    return {} if data_.get("_errors") else rep


FRIENDLY_SOURCE_TYPES = set(fmt.CLASS_ZH) | {"Player", "Pet"}


def _dt_map(tbl: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """敌方技能造成的承伤（排除近战，以及来源是我方玩家/宠物的伤害，如饰品自伤）。"""
    out: Dict[int, Dict[str, Any]] = {}
    for e in tbl.get("entries") or []:
        gid = int(e.get("guid") or 0)
        if gid == 1 or not (e.get("total") or e.get("hitCount") or e.get("tickCount")):
            continue
        sources = e.get("sources") or [{}]
        src_type = e.get("actorType") or sources[0].get("type") or ""
        if src_type in FRIENDLY_SOURCE_TYPES or (sources[0].get("type") or "") in FRIENDLY_SOURCE_TYPES:
            continue
        cur = out.setdefault(gid, {"total": 0, "hits": 0, "ticks": 0, "uses": 0, "name": e.get("name"),
                                   "src": e.get("actorName")})
        cur["total"] += e.get("total") or 0
        cur["hits"] += e.get("hitCount") or 0
        cur["ticks"] += e.get("tickCount") or 0
        cur["uses"] += e.get("uses") or 0
    return out


def _intr_map(tbl: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for e in data.interrupt_entries(tbl):
        gid = int(e.get("guid") or 0)
        cur = out.setdefault(gid, {"begun": 0, "kicked": 0, "done": 0, "name": e.get("name")})
        cur["begun"] += e.get("spellsBegun") or 0
        cur["kicked"] += (e.get("spellsInterrupted") or 0) + (e.get("spellChannelsInterrupted") or 0)
        cur["done"] += e.get("spellsCompleted") or 0
    return out


def _boss_times(pulls: List[Dict[str, Any]]) -> Dict[int, Tuple[float, int, int]]:
    """{encounterID: (击杀那次的用时, 尝试次数, 全部尝试总用时)}"""
    out: Dict[int, List[Dict[str, Any]]] = {}
    for p in pulls:
        if (p.get("encounterID") or 0) > 0 and p["endTime"] - p["startTime"] >= 1000:
            out.setdefault(p["encounterID"], []).append(p)
    res = {}
    for enc, ps in out.items():
        kill = next((p for p in ps if p.get("kill")), None)
        res[enc] = ((kill["endTime"] - kill["startTime"]) if kill else 0.0, len(ps),
                    sum(p["endTime"] - p["startTime"] for p in ps))
    return res


def cmd_compare(run: Run, runs: int = 3, level: Optional[int] = None, top: int = 15) -> str:
    level = level or run.level
    rows, note = _fight_rankings(run, level)
    if not rows:
        raise WCLError("没有找到可对比的高分记录（该副本在 WCL 上没有带日志的排名）。")
    picks = rows[: max(1, runs)]
    tasks = {str(i): (lambda r=r: _bench_run(run, r["report"]["code"], r["report"]["fightID"]))
             for i, r in enumerate(picks)}
    tasks["our_dt"] = lambda: data.damage_taken(run)
    tasks["our_intr"] = lambda: data.interrupts(run)
    got = data.parallel(tasks, workers=5)
    bench = []
    for i, r in enumerate(picks):
        rep = got[str(i)]
        fights = rep.get("fights") or []
        if not fights:
            continue
        bench.append({"rank": r, "fight": fights[0], "dt": _dt_map(table_data(rep.get("dt"))),
                      "intr": _intr_map(table_data(rep.get("intr")))})
    if not bench:
        raise WCLError("高分记录的数据获取失败（报告可能已被设为私密或删除）。")

    our_dt = _dt_map(got["our_dt"])
    our_intr = _intr_map(got["our_intr"])
    our_pulls = [{"encounterID": p.encounter_id, "kill": p.kill, "startTime": p.start, "endTime": p.end} for p in run.pulls]
    n = len(bench)
    lines = [f"# 与高分记录对比 — {run.header()}",
             f"对比对象：WCL 该副本{note}排名前 {n} 的带日志记录（已排除本场）。不同队伍的路线、阵容可能不同，"
             "命中次数和每次施放命中均受路线、存活时间与机制影响。"]
    if n < len(picks):
        lines.append(f"（{len(picks) - n} 条对比记录获取失败，已排除，未按 0 计入）")
    heads = ["指标", "本场"] + [f"高分{i + 1}" for i in range(n)]
    trows = [["报告", f"{run.code}#{run.fight_id}"] + [f"{b['rank']['report']['code']}#{b['rank']['report']['fightID']}" for b in bench]]
    trows.append(["层数/结果", f"+{run.level} {run.result}"] +
                 [f"+{b['fight'].get('keystoneLevel')} 限时+{b['fight'].get('keystoneBonus') or 0}" for b in bench])
    trows.append(["阵容", " ".join(p.spec for p in run.players.values())] +
                 [" ".join(t.get("spec", "?") for t in b["rank"].get("team") or []) for b in bench])
    trows.append(["官方用时", fmt.clock(run.keystone_time, True) if run.keystone_time else "未完成"] +
                 [fmt.clock(b["fight"].get("keystoneTime"), True) for b in bench])
    trows.append(["死亡", len(run.player_deaths())] + [b["rank"].get("deaths") for b in bench])
    b_pulls = [b["fight"].get("dungeonPulls") or [] for b in bench]
    trows.append(["波数", len(run.pulls)] + [len([p for p in ps if p["endTime"] - p["startTime"] >= 1000]) for ps in b_pulls])
    combat = run.combat_ms()
    trows.append(["战斗中", fmt.clock(combat)] + [fmt.clock(_union_ms(ps)) for ps in b_pulls])
    trows.append(["脱战", fmt.clock(run.duration - combat)] +
                 [fmt.clock((b["fight"]["endTime"] - b["fight"]["startTime"]) - _union_ms(ps)) for b, ps in zip(bench, b_pulls)])
    ours_boss = _boss_times(our_pulls)
    b_boss = [_boss_times(ps) for ps in b_pulls]
    names = {}
    for p in run.pulls:
        if p.is_boss and p.encounter_id not in names:
            names[p.encounter_id] = "、".join(p.boss_names) or p.name
    for enc in sorted(set(ours_boss) | {e for bb in b_boss for e in bb}):
        def txt(m: Dict[int, Tuple[float, int, int]]) -> str:
            if enc not in m:
                return "—"
            kill, tries, total = m[enc]
            return (fmt.clock(kill) if kill else "未击杀") + (f"（{tries}次共{fmt.clock(total)}）" if tries > 1 else "")
        trows.append([f"首领 {names.get(enc, enc)}", txt(ours_boss)] + [txt(m) for m in b_boss])
    trash = sum(p.dur for p in run.pulls if not p.is_boss)
    trows.append(["小怪战斗合计", fmt.clock(trash)] +
                 [fmt.clock(sum(p["endTime"] - p["startTime"] for p in ps if not p.get("encounterID"))) for ps in b_pulls])
    lines += ["", "## 用时结构", fmt.table(heads, trows)]

    # 承伤对比
    rows_dt = []
    only_ours = []
    for gid, o in our_dt.items():
        o_n = o["hits"] + o["ticks"]
        if o_n < 3:
            continue
        b_vals = [b["dt"].get(gid) for b in bench]
        present = [v for v in b_vals if v]
        b_counts = [(v["hits"] + v["ticks"]) if v else 0 for v in b_vals]
        med = fmt.median(b_counts) or 0.0
        o_pc = o["hits"] / o["uses"] if o["uses"] and o["hits"] else None
        b_pcs = [v["hits"] / v["uses"] for v in present if v["uses"] and v["hits"]]
        b_pc = fmt.median(b_pcs)
        label = fmt.ability_label(run.ab(gid) if gid in run.abilities else (o.get("name") or run.ab(gid)), gid)
        if not present:
            only_ours.append((o_n, label, o.get("src") or "—", fmt.num(o["total"])))
            continue
        ratio = o_n / max(med, 1.0)
        excess = o_n - med
        if ratio >= 1.5 and excess >= 3:
            rows_dt.append((excess, [label, o.get("src") or "—", f"{o_n}", f"{med:g}",
                                     " / ".join(str(c) for c in b_counts), f"{ratio:.1f}×",
                                     f"{o_pc:.1f}" if o_pc else "—", f"{b_pc:.1f}" if b_pc else "—"]))
    rows_dt.sort(key=lambda x: -x[0])
    lines += ["", "## 承伤：本场被打中明显更多的技能（命中+跳 ≥1.5 倍且多 3 次以上）",
              fmt.table(["技能", "来源", "本场命中+跳", "高分中位数", "高分各场", "倍数", "本场每次施放命中", "高分每次施放命中"],
                        [r for _, r in rows_dt[:top]]),
              "说明：命中/敌方施放为次数比，可能重复命中同一玩家；差异需结合路线、层数、存活时间与机制解释。"]
    if only_ours:
        only_ours.sort(key=lambda x: -x[0])
        lines += ["", "### 只在本场出现的承伤技能（高分记录完全没有：可能是对方路线没拉这只怪，也可能对方完全躲开了）",
                  fmt.table(["技能", "来源", "本场命中+跳", "伤害"], [[b, c, a, d] for a, b, c, d in only_ours[:top]])]

    # 打断对比
    irows = []
    gids = set(our_intr) | {g for b in bench for g in b["intr"]}
    for gid in gids:
        o = our_intr.get(gid)
        bs = [b["intr"].get(gid) for b in bench]
        present = [v for v in bs if v]
        b_begun = sum(v["begun"] for v in present)
        b_kicked = sum(v["kicked"] for v in present)
        b_rate = b_kicked / b_begun if b_begun else None
        if o:
            o_rate = o["kicked"] / o["begun"] if o["begun"] else None
            o_txt = f"{o['kicked']}/{o['begun']}（{fmt.pct(o_rate * 100 if o_rate is not None else None)}）"
            done = o["done"]
        else:
            our_uses = (our_dt.get(gid) or {}).get("uses") or 0
            o_rate, done = 0.0, None
            o_txt = "打断表未记录" + (f"（该技能本场至少施放 {our_uses} 次）" if our_uses else "（本场可能未出现）")
        b_txt = (f"{b_kicked}/{b_begun}（{fmt.pct(b_rate * 100)}，{len(present)}/{n} 场出现）" if b_begun else "未出现")
        gap = (b_rate - (o_rate or 0)) if b_rate is not None else -1
        name = run.ab(gid) if gid in run.abilities else ((o or (present[0] if present else {})).get("name") or f"技能{gid}")
        irows.append((gap, [fmt.ability_label(name, gid), o_txt, done if done is not None else "—", b_txt]))
    irows.sort(key=lambda x: -x[0])
    lines += ["", "## 打断率对比（打断/读条；按“高分打断率 − 本场打断率”排序）",
              fmt.table(["技能", "本场", "本场读完", "高分记录合计"], [r for _, r in irows[:top]]),
              "说明：表中缺失不等于本场从未打断；未出现的技能、控制与击杀中止均会影响可比性。"]
    return "\n".join(lines)


# ---------------------------------------------------------------- spec

def _char_rankings(run: Run, cls: str, spec: str, metric: str, level: int) -> Tuple[List[Dict[str, Any]], str]:
    for bracket in (level - 1, 0):
        data_ = run.client.gql(Q_CHAR_RANKINGS, {"id": run.encounter_id, "cls": cls, "spec": spec, "metric": metric,
                                                 "bracket": bracket}, ttl=6 * HOUR)
        enc = (data_.get("worldData") or {}).get("encounter") or {}
        rows = [r for r in ((enc.get("characterRankings") or {}).get("rankings")) or []
                if (r.get("report") or {}).get("code") and (r.get("report") or {}).get("fightID") is not None]
        if len(rows) >= 2 or bracket == 0:
            return rows, (f"同层 +{level}" if bracket else "全部层数（同层可用记录不足）")
    return [], "无"


def _bench_player(run: Run, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    code, fid = row["report"]["code"], row["report"]["fightID"]
    payload = run.client.gql(Q_BENCH_PLAYER, {"code": code, "fid": [fid]}, ttl=7 * DAY, partial=True)
    if payload.get("_errors"):
        return None
    rep = (payload.get("reportData") or {}).get("report") or {}
    if not rep.get("fights"):
        return None
    pd = table_data(rep.get("pd")).get("playerDetails") or {}
    actor = None
    for role in pd.values():
        for p in role or []:
            if p.get("name") == row.get("name") and (not row.get("server") or
                                                      (row["server"].get("name") in (None, p.get("server")))):
                actor = p
    if not actor:
        for role in pd.values():
            for p in role or []:
                if p.get("name") == row.get("name"):
                    actor = p
    if not actor:
        return None
    fights = rep.get("fights") or [{}]
    f = fights[0]
    dur = (f.get("endTime") or 0) - (f.get("startTime") or 0)
    combat = _union_ms(f.get("dungeonPulls") or []) or dur
    active = next((e.get("activeTime") for e in table_data(rep.get("dd")).get("entries") or [] if e.get("id") == actor["id"]), None)
    c = (run.client.gql(Q_BENCH_CASTS, {"code": code, "fid": [fid], "sid": actor["id"]}, ttl=7 * DAY)
         .get("reportData") or {}).get("report") or {}
    casts = {}
    for e in table_data(c.get("c")).get("entries") or []:
        gid = int(e.get("guid") or 0)
        if gid != 1:
            casts[gid] = casts.get(gid, 0) + (e.get("total") or 0)
            casts.setdefault(("name", gid), e.get("name"))
    return {"row": row, "dur": dur, "combat": combat, "active": active, "casts": casts, "level": f.get("keystoneLevel")}


def cmd_spec(run: Run, name: str, players: int = 3, level: Optional[int] = None, top: int = 25) -> str:
    p = run.find_player(name)
    if not p.spec:
        raise WCLError(f"无法确定 {p.name} 的专精。")
    level = level or run.level
    metric = "hps" if p.role == "healer" else "dps"
    rows, note = _char_rankings(run, p.cls, p.spec, metric, level)
    rows = [r for r in rows if not (r.get("name") == p.name and
            (not (r.get("server") or {}).get("name") or r["server"]["name"] == p.server))]
    if not rows:
        raise WCLError(f"没有找到 {p.spec_zh} 在该副本的带日志排名。")
    picks = rows[: max(1, players)]
    got = data.parallel({str(i): (lambda r=r: _bench_player(run, r)) for i, r in enumerate(picks)}
                        | {"ours": lambda: data.casts(run, p.id), "dd": lambda: data.damage_done(run)}, workers=5)
    bench = [got[str(i)] for i in range(len(picks)) if got.get(str(i))]
    if not bench:
        raise WCLError("顶尖玩家的数据获取失败（报告可能已私密或删除）。")
    our_combat = max(run.combat_ms(), 1.0)
    ours: Dict[int, int] = {}
    for e in got["ours"].get("entries") or []:
        gid = int(e.get("guid") or 0)
        if gid != 1:
            ours[gid] = ours.get(gid, 0) + (e.get("total") or 0)
    our_active = next((e.get("activeTime") for e in got["dd"].get("entries") or [] if e.get("id") == p.id), None)
    dmg_total = next((e.get("total") or 0 for e in run.summary.get("damageDone") or [] if e.get("id") == p.id), 0)
    heal_total = next((e.get("total") or 0 for e in run.summary.get("healingDone") or [] if e.get("id") == p.id), 0)
    our_amount = (heal_total if metric == "hps" else dmg_total) / (run.duration / 1000.0)

    lines = [f"# 同专精对比：{p.label} vs WCL {note} 前 {len(bench)} 名 {p.spec_zh}（按 {metric.upper()}）",
             run.header(),
             "CPM = 每分钟团队战斗时间的施放次数；路线、天赋、个人死亡与节奏差异仍会影响该指标。"]
    if len(bench) < len(picks):
        lines.append(f"（{len(picks) - len(bench)} 条玩家记录获取失败，已排除）")
    hrow = [["本场", p.name, f"+{run.level}", fmt.num(our_amount), fmt.pct(our_active, run.duration, 1) if our_active else "—",
             fmt.clock(our_combat), run.code]]
    for b in bench:
        r = b["row"]
        hrow.append([f"第{rows.index(r) + 1}名", r.get("name"), f"+{b['level'] or r.get('bracketData')}", fmt.num(r.get("amount")),
                     fmt.pct(b["active"], b["dur"], 1) if b["active"] else "—", fmt.clock(b["combat"]),
                     f"{r['report']['code']}#{r['report']['fightID']}"])
    lines.append(fmt.table(["", "玩家", "层数", metric.upper(), "活跃时间", "战斗中时长", "报告"], hrow))

    all_ids = set(ours) | {g for b in bench for g in b["casts"] if isinstance(g, int)}
    table_rows = []
    for gid in all_ids:
        o_cpm = ours.get(gid, 0) / (our_combat / 60000.0)
        b_cpms = [b["casts"].get(gid, 0) / (max(b["combat"], 1.0) / 60000.0) for b in bench]
        b_med = fmt.median(b_cpms) or 0.0
        used_by = sum(1 for b in bench if b["casts"].get(gid))
        if max(o_cpm, b_med) < 0.05:
            continue
        diff = o_cpm - b_med
        mark = ""
        if b_med >= 0.2 and o_cpm == 0:
            mark = "本场未使用"
        elif o_cpm >= 0.2 and used_by == 0:
            mark = "对比样本未记录"
        elif b_med > 0 and abs(diff) / b_med >= 0.3 and abs(diff) >= 0.3:
            mark = "低于样本≥30%" if diff < 0 else "高于样本≥30%"
        name = run.ab(gid) if gid in run.abilities else next(
            (b["casts"].get(("name", gid)) for b in bench if b["casts"].get(("name", gid))), f"技能{gid}")
        table_rows.append((max(o_cpm, b_med), [fmt.ability_label(name, gid), f"{o_cpm:.2f}", f"{b_med:.2f}",
                                                " / ".join(f"{c:.2f}" for c in b_cpms), f"{diff:+.2f}", mark]))
    table_rows.sort(key=lambda x: -x[0])
    lines += ["", "## 技能施放频率（按较高一方的 CPM 排序）",
              fmt.table(["技能", "本场CPM", "顶尖中位数", "顶尖各人", "差值", "标记"], [r for _, r in table_rows[:top]]),
              "说明：施放记录缺失不代表应当使用；请结合天赋、死亡、职责和路线解释 CPM 差异，跨层数据需谨慎比较。"]
    return "\n".join(lines)
