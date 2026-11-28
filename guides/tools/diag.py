#!/usr/bin/env python3
"""极简大秘境 DPS 诊断脚本（v3 底座）：以敌方关键技能施放为主键，一屏输出 5 维实战数据。

用法：
  1. 抽样固化 12-15 场高分限时样本（不同报告 + 不同玩家）：
     python3 guides/tools/diag.py sample --dungeon 塞塔里斯 --class 惩戒骑 --levels 24,23 --want 15 --out runs.json

  2. 单 Boss 一屏 5 维诊断：
     python3 guides/tools/diag.py boss --runs runs.json --class guides/tools/classes/paladin-ret.json --boss 1

  3. 全本小怪（非 Boss 战斗）按「怪物名 + 威胁技能」聚合五维诊断：
     python3 guides/tools/diag.py trash --runs runs.json --class guides/tools/classes/paladin-ret.json

  4. 双向反查（按技能列出所有受击/躲避/免疫原始明细，用于证伪口诀）：
     python3 guides/tools/diag.py inspect --runs runs.json --class guides/tools/classes/paladin-ret.json --boss 1 --ability <技能ID或名称>
     python3 guides/tools/diag.py inspect --runs runs.json --class guides/tools/classes/paladin-ret.json --trash --ability <怪物名或技能名或ID>
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from wclr import cmd_find, data, fmt, wowhead  # noqa: E402
from wclr.api import Client, WCLError, stderr  # noqa: E402
from wclr.context import Pull, Run, esc, load_run  # noqa: E402

# 明确的外减 / 团减 Buff 技能 ID（精确匹配，不使用模糊关键词，避免把普通小盾混入外减）
EXTERNAL_DEF_BUFF_IDS: Dict[int, str] = {
    33206: "痛苦压制",
    47788: "守护之魂",
    102342: "铁木树皮",
    116849: "作茧缚命",
    6940: "牺牲祝福",
    357170: "时光膨胀",
    357171: "时光膨胀",
    98007: "灵魂链接",
    325174: "灵魂链接",
    62618: "真言术：障",
    81782: "真言术：障",
    145629: "反魔法领域",
    51052: "反魔法领域",
    97462: "集结呐喊",
    97463: "集结呐喊",
    31821: "光环掌握",
    374227: "微风",
    374229: "微风",
    196718: "黑暗",
    209426: "黑暗",
    1022: "外部保护",
    204018: "破咒祝福",
}
# 仅当施放者不是本人时才算“外部”的技能 ID（避免与本人自施放重复计）
EXTERNAL_ONLY_IF_OTHER_SOURCE = {6940, 1022, 204018}

# WCL hitType 中表示完全免疫 / 抵抗 / 躲闪 / 招架 / 未命中的值
IMMUNE_HIT_TYPES = {7, 8, 9, 10, 11, 14, 15, 16, 17}


# ============================================================================
# 基础数据结构
# ============================================================================

@dataclass
class SkillDef:
    name: str
    cast: int
    buff: List[int] = field(default_factory=list)
    dur_ms: float = 8000.0
    cd_ms: float = 60000.0
    tier: str = "normal"  # normal / major / utility
    cleanse_immune: bool = False
    blocked_by_debuff: List[int] = field(default_factory=list)


@dataclass
class RunSample:
    idx: int
    tag: str  # r01..r15
    code: str
    fid: int
    level: int
    player: str
    region: str
    duration: Optional[float] = None


@dataclass
class BossPack:
    sample: RunSample
    run: Run
    player_id: int
    player_name: str
    pulls: List[Pull]
    player_all_casts: List[Dict[str, Any]]
    player_buffs: List[Dict[str, Any]]
    friendly_dt: List[Dict[str, Any]]
    friendly_debuffs: List[Dict[str, Any]]
    enemy_casts: List[Dict[str, Any]]
    player_heals: List[Dict[str, Any]]
    dispels: List[Dict[str, Any]]
    deaths: List[Dict[str, Any]]
    interrupts: List[Dict[str, Any]] = field(default_factory=list)
    buff_intervals: Dict[int, List[Tuple[float, float, Optional[int], bool]]] = field(default_factory=dict)
    debuff_intervals: Dict[int, List[Tuple[float, float, Optional[int], bool]]] = field(default_factory=dict)
    cast_times: Dict[int, List[float]] = field(default_factory=dict)
    max_hp: float = 0.0


@dataclass
class SkillMeta:
    key: str
    name: str
    is_boss: bool
    source_npc: str
    is_dot: bool = False   # True = 带 tick 伤害的 DoT/多跳技，按单目标实例归并
    cast_ids: Set[int] = field(default_factory=set)
    dmg_ids: Set[int] = field(default_factory=set)
    debuff_ids: Set[int] = field(default_factory=set)
    runs: Set[str] = field(default_factory=set)
    intervals: List[float] = field(default_factory=list)
    party_raw_dmgs: List[float] = field(default_factory=list)


@dataclass
class WaveRecord:
    """一次敌方技能施放波次（或 DoT 单目标完整实例）在目标玩家身上的完整记录。"""
    skill_key: str
    skill_name: str
    is_boss: bool
    cast_ids: Set[int]
    dmg_ids: Set[int]
    sample_tag: str
    player_name: str
    run: Run
    pull: Pull
    wave_ts: float
    # 全队层面
    party_hit_count: int
    party_debuff_count: int
    # 目标玩家层面
    outcome: str  # "hit" | "immune" | "dodged"
    hits: List[Dict[str, Any]] = field(default_factory=list)
    total_dmg: float = 0.0
    total_abs: float = 0.0
    start_hp_pct: Optional[float] = None
    min_hp_pct: Optional[float] = None
    active_defs: List[str] = field(default_factory=list)
    active_normal: List[str] = field(default_factory=list)
    active_major: List[str] = field(default_factory=list)
    passive_defs: List[str] = field(default_factory=list)  # 0主动施放但被动触发的盾，如复仇之盾(184662)
    ready_normal: List[str] = field(default_factory=list)
    ready_major: List[str] = field(default_factory=list)
    locked_major: List[str] = field(default_factory=list)
    overlap_other_dmg: float = 0.0
    overlap_skills: List[str] = field(default_factory=list)
    ext_buffs: List[str] = field(default_factory=list)     # 明确 ID 命中的外减/团减
    window_heal: float = 0.0
    window_heal_top: List[str] = field(default_factory=list)
    died: bool = False


# ============================================================================
# 工具函数
# ============================================================================

def load_class_cfg(path: Path) -> Tuple[str, List[SkillDef], List[SkillDef]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    defs: List[SkillDef] = []
    for d in raw.get("defensives") or []:
        defs.append(SkillDef(
            name=d["name"],
            cast=int(d["cast"]),
            buff=[int(x) for x in (d.get("buff") or [d["cast"]])],
            dur_ms=float(d.get("dur", 8)) * 1000.0,
            cd_ms=float(d.get("cd", 60)) * 1000.0,
            tier=str(d.get("tier", "normal")),
            cleanse_immune=bool(d.get("cleanse_immune", False)),
            blocked_by_debuff=[int(x) for x in (d.get("blocked_by_debuff") or [])],
        ))
    utils: List[SkillDef] = []
    for u in raw.get("utilities") or []:
        utils.append(SkillDef(
            name=u["name"],
            cast=int(u["cast"]),
            buff=[int(x) for x in (u.get("buff") or [])],
            dur_ms=float(u.get("dur", 0)) * 1000.0,
            cd_ms=float(u.get("cd", 60)) * 1000.0,
            tier="utility",
            cleanse_immune=bool(u.get("cleanse_immune", False)),
            blocked_by_debuff=[int(x) for x in (u.get("blocked_by_debuff") or [])],
        ))
    return raw.get("class") or path.stem, defs, utils


def med(vals: Sequence[float]) -> Optional[float]:
    clean = [v for v in vals if v is not None and not math.isnan(v)]
    return statistics.median(clean) if clean else None


def pct_str(val: Optional[float], digits: int = 0) -> str:
    return "—" if val is None else f"{val:.{digits}f}%"


def rel_pull(pull: Pull, ts: float) -> str:
    return fmt.clock(ts - pull.start, True)


def wcl_event_url(run: Run, ts: float, pre_ms: int = 5000, post_ms: int = 1000) -> str:
    """生成可直接点击跳转到 WCL 事件流窗口的锚点链接。"""
    s = max(int(run.start), int(round(ts - pre_ms)))
    e = min(int(run.end), int(round(ts + post_ms)))
    return f"{run.url}&view=events&start={s}&end={e}"


def wcl_ref(sample_tag: str, pull: Pull, run: Run, ts: float, use_run_clock: bool = False) -> str:
    label = run.t(ts, True) if use_run_clock else rel_pull(pull, ts)
    return f"[{sample_tag}@{label}]({wcl_event_url(run, ts)})"


def build_aura_intervals(
    evs: List[Dict[str, Any]],
    target_id: int,
    apply_types: Set[str],
    remove_types: Set[str],
    fallback_dur_ms: Dict[int, float],
    end_ts: float,
) -> Dict[int, List[Tuple[float, float, Optional[int], bool]]]:
    """构建 {ability_id: [(start, end, source_id, has_explicit_remove)]}。"""
    active: Dict[int, Tuple[float, Optional[int]]] = {}
    out: Dict[int, List[Tuple[float, float, Optional[int], bool]]] = defaultdict(list)
    for e in sorted(evs, key=lambda x: x.get("timestamp") or 0):
        if e.get("targetID") != target_id:
            continue
        gid = e.get("abilityGameID")
        if not gid:
            continue
        gid = int(gid)
        typ = e.get("type") or ""
        ts = float(e.get("timestamp") or 0)
        if typ in apply_types:
            if gid in active:
                if "refresh" in typ:
                    continue
                s0, src0 = active.pop(gid)
                out[gid].append((s0, ts, src0, False))
            active[gid] = (ts, e.get("sourceID"))
        elif typ in remove_types:
            if gid in active:
                s0, src0 = active.pop(gid)
                out[gid].append((s0, ts, src0, True))
            else:
                out[gid].append((ts - fallback_dur_ms.get(gid, 10000.0), ts, e.get("sourceID"), True))
    for gid, (s0, src0) in active.items():
        dur = fallback_dur_ms.get(gid, 10000.0)
        out[gid].append((s0, min(end_ts, s0 + dur), src0, False))
    return out


def is_aura_active(
    intervals: List[Tuple[float, float, Optional[int], bool]],
    ts: float,
    slack_ms: float = 150.0,
) -> bool:
    for s, e, _src, _rem in intervals:
        if s - slack_ms <= ts <= e + slack_ms:
            return True
    return False


def active_defensives_at(
    pack: BossPack,
    skills: List[SkillDef],
    ts: float,
    slack_ms: float = 150.0,
    buff_only: bool = False,
) -> List[SkillDef]:
    hit: List[SkillDef] = []
    for sk in skills:
        found = False
        for bid in sk.buff:
            ivs = pack.buff_intervals.get(bid) or []
            if is_aura_active(ivs, ts, slack_ms=slack_ms):
                found = True
                break
        if not found and not buff_only and slack_ms >= 0:
            for ct in pack.cast_times.get(sk.cast) or []:
                if ct - slack_ms <= ts <= ct + sk.dur_ms + slack_ms:
                    found = True
                    break
        if found:
            hit.append(sk)
    return hit


def is_skill_ready(
    pack: BossPack,
    sk: SkillDef,
    ts: float,
    eff_cd_ms: Dict[int, float],
) -> Tuple[bool, str]:
    """返回 (是否可用, 不可用原因: 'ok' | 'cd' | 'debuff_lock')。"""
    for lock_id in sk.blocked_by_debuff:
        ivs = pack.debuff_intervals.get(lock_id) or []
        if is_aura_active(ivs, ts, slack_ms=50.0):
            return False, "debuff_lock"
    cd = eff_cd_ms.get(sk.cast, sk.cd_ms)
    last_cast: Optional[float] = None
    for ct in pack.cast_times.get(sk.cast) or []:
        if ct < ts - 200.0:
            last_cast = ct
        else:
            break
    if last_cast is not None and (ts - last_cast) < cd - 1500.0:
        return False, "cd"
    return True, "ok"


def external_buffs_at(pack: BossPack, ts: float) -> List[str]:
    """按明确技能 ID 集合检查 ts 时刻作用于玩家的外减 / 团减 Buff。"""
    names: List[str] = []
    seen: Set[str] = set()
    for gid, label in EXTERNAL_DEF_BUFF_IDS.items():
        ivs = pack.buff_intervals.get(gid)
        if not ivs:
            continue
        for s, e, src, _rem in ivs:
            if s - 150.0 <= ts <= e + 150.0:
                if gid in EXTERNAL_ONLY_IF_OTHER_SOURCE:
                    if src is not None and (src == pack.player_id or pack.run.owner(src) == pack.player_id):
                        continue
                if label not in seen:
                    seen.add(label)
                    names.append(label)
                break
    return names


def heals_in_window(pack: BossPack, start_ts: float, end_ts: float) -> Tuple[float, List[str]]:
    """统计窗口内玩家受到的有效治疗（排除过量）与主要来源。"""
    total = 0.0
    by_ab: Counter[str] = Counter()
    for e in pack.player_heals:
        ts = float(e.get("timestamp") or 0)
        if start_ts <= ts <= end_ts:
            amt = float(e.get("amount") or 0)
            if amt > 0:
                total += amt
                src = pack.run.actor_name(e.get("sourceID"))
                ab = pack.run.ab(e.get("abilityGameID"))
                by_ab[f"{src}:{ab}"] += amt
    top = [f"{k}({fmt.num(v)})" for k, v in by_ab.most_common(2)]
    return total, top


def find_boss_pulls(run: Run, boss_spec: str) -> List[Pull]:
    """支持按 Boss 序号（1..4）、encounterID 或名称片段匹配。"""
    boss_pulls = [p for p in run.pulls if p.is_boss]
    if not boss_pulls:
        return []
    order_eids: List[int] = []
    for p in boss_pulls:
        if p.encounter_id not in order_eids:
            order_eids.append(p.encounter_id)
    q = boss_spec.strip()
    if q.isdigit():
        val = int(q)
        if 1 <= val <= len(order_eids):
            target_eid = order_eids[val - 1]
            return [p for p in boss_pulls if p.encounter_id == target_eid]
        return [p for p in boss_pulls if p.encounter_id == val]
    ql = q.lower()
    return [
        p for p in boss_pulls
        if ql in (p.name or "").lower() or any(ql in bn.lower() for bn in p.boss_names)
    ]


def hp_before_after(ev: Dict[str, Any], hp_is_post: bool) -> Tuple[Optional[float], Optional[float]]:
    """根据 WCL 伤害事件计算 (起手血量%, 吃完剩血%)。"""
    mhp = ev.get("maxHitPoints")
    hp = ev.get("hitPoints")
    if not mhp or hp is None or mhp <= 0:
        return None, None
    amt = float(ev.get("amount") or 0)
    ok = float(ev.get("overkill") or 0)
    if hp_is_post:
        post = max(0.0, float(hp))
        eff_amt = max(0.0, amt - ok) if (ok > 0 and amt >= ok) else amt
        pre = max(0.0, min(float(mhp), post + eff_amt))
    else:
        pre = max(0.0, float(hp))
        post = max(0.0, pre - amt)
    return 100.0 * pre / float(mhp), 100.0 * post / float(mhp)


def detect_hp_is_post(packs: List[BossPack]) -> bool:
    """自动检测 WCL 事件里的 hitPoints 是扣血后（post）还是扣血前（pre）。"""
    post_votes = 0
    pre_votes = 0
    for pack in packs:
        for e in pack.friendly_dt:
            ok = float(e.get("overkill") or 0)
            hp = e.get("hitPoints")
            if ok > 0 and hp is not None:
                if float(hp) == 0:
                    post_votes += 1
                else:
                    pre_votes += 1
    if post_votes or pre_votes:
        return post_votes >= pre_votes
    return True


def is_boss_actor(run: Run, actor_id: Optional[int], boss_names: Set[str]) -> bool:
    if actor_id is None or actor_id == -1:
        return False
    a = run.actors.get(actor_id)
    if not a:
        return False
    if a.get("subType") == "Boss":
        return True
    return (a.get("name") or "") in boss_names


# ============================================================================
# 子命令 1：sample（抽样固化 12-15 场）
# ============================================================================

def cmd_sample(client: Client, args: argparse.Namespace) -> str:
    eid, dname = cmd_find.resolve_dungeon(client, args.dungeon)
    cls, spec = fmt.parse_class(args.cls)
    levels = [int(x.strip()) for x in args.levels.split(",") if x.strip()]
    want = args.want

    candidates: List[Dict[str, Any]] = []
    seen_codes: Set[str] = set()
    seen_players: Set[str] = set()

    for lv in levels:
        rows, _ = cmd_find.find_runs(client, eid, cls, spec, level=lv, want=max(want * 4, 60))
        for r in rows:
            code = r["code"]
            if code in seen_codes:
                continue
            who = r.get("who") or []
            if not who:
                continue
            pname = who[0][0]
            pkey = pname.lower()
            if pkey in seen_players:
                continue
            seen_codes.add(code)
            seen_players.add(pkey)
            candidates.append({
                "code": code,
                "fid": int(r["fid"]),
                "level": int(r.get("level") or lv),
                "player": pname,
                "region": r.get("region") or "",
                "duration": r.get("duration"),
            })
            if len(candidates) >= want + 6:
                break
        if len(candidates) >= want + 6:
            break

    verified: List[Dict[str, Any]] = []

    def check_one(c: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            run = load_run(client, f"{c['code']}#fight={c['fid']}")
            if not run.kill or run.bonus < 1:
                return None
            p = run.find_player(c["player"])
            return {
                "code": run.code,
                "fid": run.fight_id,
                "level": run.level,
                "bonus": run.bonus,
                "player": p.name,
                "spec": p.spec_zh,
                "region": (run.report.get("region") or {}).get("slug") or c["region"],
                "duration_ms": int(run.duration),
                "url": run.url,
            }
        except Exception as exc:
            stderr(f"[sample] 跳过 {c['code']}#fight={c['fid']} ({c['player']}): {exc}")
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check_one, candidates))

    for r in results:
        if r:
            verified.append(r)
            if len(verified) >= want:
                break

    for i, r in enumerate(verified, 1):
        r["tag"] = f"r{i:02d}"

    payload = {
        "dungeon": dname,
        "encounter_id": eid,
        "class": fmt.class_spec(cls, spec or ""),
        "levels": levels,
        "count": len(verified),
        "runs": verified,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [f"# 样本固化完成：{dname} · {payload['class']} · 共 {len(verified)} 场限时"]
    rows_tbl = [
        [r["tag"], f"+{r['level']}(+{r['bonus']})", fmt.clock(r["duration_ms"]), r["region"], r["player"], r["url"]]
        for r in verified
    ]
    lines.append(fmt.table(["#", "层数", "用时", "区", "玩家", "链接"], rows_tbl))
    lines.append(f"\n已写入：{out_path}")
    return "\n".join(lines)


# ============================================================================
# 数据加载（15 场并发拉取 Boss 窗口 + 全本防御施法）
# ============================================================================

def load_samples(runs_path: Path) -> Tuple[Dict[str, Any], List[RunSample]]:
    raw = json.loads(runs_path.read_text(encoding="utf-8"))
    samples: List[RunSample] = []
    for i, r in enumerate(raw.get("runs") or [], 1):
        samples.append(RunSample(
            idx=i,
            tag=r.get("tag") or f"r{i:02d}",
            code=r["code"],
            fid=int(r["fid"]),
            level=int(r.get("level") or 0),
            player=r["player"],
            region=r.get("region") or "",
            duration=r.get("duration_ms"),
        ))
    return raw, samples


def load_boss_pack(
    client: Client,
    sample: RunSample,
    boss_spec: str,
    all_track_cast_ids: List[int],
    skill_fallback_dur: Dict[int, float],
) -> Optional[BossPack]:
    run = load_run(client, f"{sample.code}#fight={sample.fid}")
    player = run.find_player(sample.player)
    pulls = find_boss_pulls(run, boss_spec)
    if not pulls:
        stderr(f"[diag] {sample.tag} ({sample.player}) 未找到 Boss '{boss_spec}'，跳过。")
        return None

    win_start = min(p.start for p in pulls)
    win_end = max(p.end for p in pulls)
    buff_start = max(run.start, win_start - 30_000)

    cast_expr = ""
    if all_track_cast_ids:
        cast_expr = "ability.id in (%s)" % ", ".join(str(x) for x in sorted(set(all_track_cast_ids)))

    p_casts, _ = data.events(
        run, data_type="Casts", start=run.start, end=run.end,
        hostility="Friendlies", source=player.id, expr=cast_expr, limit=2000,
    )
    p_buffs, _ = data.events(
        run, data_type="Buffs", start=buff_start, end=win_end,
        hostility="Friendlies", target=player.id, limit=5000,
    )
    # WCL v1 的 buffs 接口带 targetid 时可能只返回自施放增益，单独按外减 ID 补拉全队外减/团减事件
    ext_expr = "ability.id in (%s)" % ", ".join(str(x) for x in sorted(EXTERNAL_DEF_BUFF_IDS))
    ext_buff_evs, _ = data.events(
        run, data_type="Buffs", start=buff_start, end=win_end,
        hostility="Friendlies", expr=ext_expr, limit=2000,
    )
    p_buffs = p_buffs + [e for e in ext_buff_evs if e.get("targetID") == player.id]
    f_dt, trunc_dt = data.events(
        run, data_type="DamageTaken", start=win_start, end=win_end,
        hostility="Friendlies", limit=8000, include_resources=True,
    )
    f_deb, _ = data.events(
        run, data_type="Debuffs", start=max(run.start, win_start - 15_000), end=win_end,
        hostility="Friendlies", limit=5000,
    )
    e_casts, _ = data.events(
        run, data_type="Casts", start=win_start, end=win_end,
        hostility="Enemies", limit=5000,
    )
    p_heals, _ = data.events(
        run, data_type="Healing", start=win_start, end=win_end,
        hostility="Friendlies", target=player.id, limit=5000,
    )
    dispels_evs, _ = data.events(
        run, data_type="Dispels", start=win_start, end=win_end,
        hostility="Friendlies", limit=1000,
    )
    death_evs, _ = data.events(
        run, data_type="Deaths", start=win_start, end=win_end,
        hostility="Friendlies", target=player.id, limit=200,
    )
    # v1 的 Deaths 不认 target 参数，会返回全队死亡，必须本地再按本人过滤
    death_evs = [e for e in death_evs if e.get("targetID") == player.id]
    if trunc_dt:
        stderr(f"[warn] {sample.tag} DamageTaken 事件达到上限被截断")

    def in_pulls(ts: float, pad_pre: float = 0.0, pad_post: float = 0.0) -> bool:
        return any(p.start - pad_pre <= ts <= p.end + pad_post for p in pulls)

    f_dt = [e for e in f_dt if in_pulls(float(e.get("timestamp") or 0), 500, 500)]
    e_casts = [e for e in e_casts if in_pulls(float(e.get("timestamp") or 0), 500, 500)]

    buff_ivs = build_aura_intervals(
        p_buffs, player.id,
        {"applybuff", "refreshbuff", "applybuffstack"},
        {"removebuff"},
        skill_fallback_dur, win_end,
    )
    debuff_ivs = build_aura_intervals(
        f_deb, player.id,
        {"applydebuff", "refreshdebuff", "applydebuffstack"},
        {"removedebuff"},
        {25771: 30000.0}, win_end,
    )
    cast_times: Dict[int, List[float]] = defaultdict(list)
    for e in sorted(p_casts, key=lambda x: x.get("timestamp") or 0):
        if e.get("type") == "cast" and e.get("abilityGameID"):
            cast_times[int(e["abilityGameID"])].append(float(e["timestamp"]))

    max_hp = 0.0
    for e in f_dt:
        if e.get("targetID") == player.id and e.get("maxHitPoints"):
            max_hp = max(max_hp, float(e["maxHitPoints"]))

    return BossPack(
        sample=sample,
        run=run,
        player_id=player.id,
        player_name=player.name,
        pulls=pulls,
        player_all_casts=p_casts,
        player_buffs=p_buffs,
        friendly_dt=f_dt,
        friendly_debuffs=f_deb,
        enemy_casts=e_casts,
        player_heals=p_heals,
        dispels=dispels_evs,
        deaths=death_evs,
        buff_intervals=buff_ivs,
        debuff_intervals=debuff_ivs,
        cast_times=cast_times,
        max_hp=max_hp,
    )


# ============================================================================
# 核心分析引擎（5 维数据）
# ============================================================================

def calibrate_cooldowns(
    packs: List[BossPack],
    skills: List[SkillDef],
) -> Tuple[Dict[int, float], Dict[int, Dict[str, Any]]]:
    """统计每个技能的实测最小 CD、全本/Boss 内施放次数、开怪前在 CD 比例。"""
    eff_cd: Dict[int, float] = {}
    stats: Dict[int, Dict[str, Any]] = {}

    for sk in skills:
        all_gaps: List[float] = []
        total_dungeon_casts = 0
        boss_casts_per_run: List[int] = []
        used_in_boss_runs = 0
        for pack in packs:
            cts = sorted(pack.cast_times.get(sk.cast) or [])
            total_dungeon_casts += len(cts)
            for a, b in zip(cts, cts[1:]):
                gap = b - a
                if gap >= 5000.0:
                    all_gaps.append(gap)
            in_boss = [
                t for t in cts
                if any(p.start <= t <= p.end for p in pack.pulls)
            ]
            boss_casts_per_run.append(len(in_boss))
            if in_boss:
                used_in_boss_runs += 1

        if all_gaps:
            all_gaps.sort()
            obs_min = all_gaps[0]
            if len(all_gaps) >= 15 or obs_min <= sk.cd_ms * 1.15:
                eff = math.floor(obs_min / 1000.0) * 1000.0
                cd_note = f"{eff / 1000:.0f}s(实测最小{obs_min / 1000:.1f}s)"
            else:
                eff = sk.cd_ms
                cd_note = f"{sk.cd_ms / 1000:.0f}s(标称;实测最小{obs_min / 1000:.0f}s)"
            eff_cd[sk.cast] = eff
        else:
            eff_cd[sk.cast] = sk.cd_ms
            cd_note = f"{sk.cd_ms / 1000:.0f}s(标称)"

        on_cd_at_pull = 0
        for pack in packs:
            p0 = pack.pulls[0]
            prev = [t for t in (pack.cast_times.get(sk.cast) or []) if t < p0.start]
            if prev and (p0.start - prev[-1]) < eff_cd[sk.cast] - 1000.0:
                on_cd_at_pull += 1

        stats[sk.cast] = {
            "skill": sk,
            "eff_cd_ms": eff_cd[sk.cast],
            "cd_note": cd_note,
            "total_dungeon_casts": total_dungeon_casts,
            "total_boss_casts": sum(boss_casts_per_run),
            "avg_boss_casts": sum(boss_casts_per_run) / max(1, len(packs)),
            "used_boss_runs": used_in_boss_runs,
            "on_cd_at_pull": on_cd_at_pull,
            "n_runs": len(packs),
        }
    return eff_cd, stats


def pair_enemy_cast_anchors(raw_casts: List[Dict[str, Any]]) -> List[float]:
    """把同一来源同一技能的 begincast + cast 精准配对（支持 4.5s+ 长读条），再按 1.5s 合并多怪齐发。"""
    raw_casts = sorted(raw_casts, key=lambda x: float(x.get("timestamp") or 0))
    pending_begin: Dict[Tuple[Any, int], float] = {}
    anchors: List[float] = []

    for e in raw_casts:
        ts = float(e.get("timestamp") or 0)
        typ = e.get("type")
        key = ((e.get("sourceID"), e.get("sourceInstance")), int(e.get("abilityGameID") or 0))
        if typ == "begincast":
            if key in pending_begin and ts - pending_begin[key] > 10000.0:
                anchors.append(pending_begin.pop(key))
            pending_begin[key] = ts
        elif typ == "cast":
            if key in pending_begin and ts - pending_begin[key] <= 10000.0:
                pending_begin.pop(key)
            anchors.append(ts)

    for ts in pending_begin.values():
        anchors.append(ts)

    anchors.sort()
    merged: List[float] = []
    for t in anchors:
        if not merged or t - merged[-1] > 1500.0:
            merged.append(t)
    return merged


def _make_wave_record(
    pack: BossPack,
    pull: Pull,
    meta: SkillMeta,
    eval_ts: float,
    party_hit_count: int,
    party_debuff_count: int,
    player_hits: List[Dict[str, Any]],
    player_got_debuff: bool,
    active_normal_defs: List[SkillDef],
    active_major_defs: List[SkillDef],
    passive_defs: List[SkillDef],
    eff_cd: Dict[int, float],
    hp_is_post: bool,
    player_enemy_hits: List[Dict[str, Any]],
    death_times: List[float],
) -> WaveRecord:
    """将单次波次/DoT实例的命中列表评估为完整的 WaveRecord（含起手血量、手牌、被动盾与外减隔离）。"""
    all_defs = active_normal_defs + active_major_defs
    all_own_ids = meta.cast_ids | meta.dmg_ids | meta.debuff_ids
    run = pack.run

    act_defs = active_defensives_at(pack, all_defs, eval_ts)
    act_norm = [s.name for s in act_defs if s.tier == "normal"]
    act_maj = [s.name for s in act_defs if s.tier == "major"]
    pas_defs = [s.name for s in active_defensives_at(pack, passive_defs, eval_ts, buff_only=True)]

    if len(player_hits) > 1:
        for h in player_hits[1:]:
            hts = float(h["timestamp"])
            for s in active_defensives_at(pack, all_defs, hts):
                if s.tier == "normal" and s.name not in act_norm:
                    act_norm.append(s.name)
                elif s.tier == "major" and s.name not in act_maj:
                    act_maj.append(s.name)
            for s in active_defensives_at(pack, passive_defs, hts, buff_only=True):
                if s.name not in pas_defs:
                    pas_defs.append(s.name)

    tot_dmg = sum(float(h.get("amount") or 0) for h in player_hits)
    tot_abs = sum(float(h.get("absorbed") or 0) for h in player_hits)
    any_immune_ht = any(int(h.get("hitType") or 0) in IMMUNE_HIT_TYPES for h in player_hits)

    if player_hits:
        if tot_dmg == 0 and tot_abs == 0 and (any_immune_ht or act_maj):
            outcome = "immune"
        else:
            outcome = "hit"
    elif player_got_debuff:
        outcome = "hit"
    else:
        outcome = "dodged"

    start_hp: Optional[float] = None
    min_hp: Optional[float] = None
    if player_hits:
        p0_pre, p0_post = hp_before_after(player_hits[0], hp_is_post)
        start_hp = p0_pre
        posts = [hp_before_after(h, hp_is_post)[1] for h in player_hits]
        posts = [x for x in posts if x is not None]
        min_hp = min(posts) if posts else p0_post

    r_norm: List[str] = []
    r_maj: List[str] = []
    l_maj: List[str] = []
    for sk in active_normal_defs:
        if sk.name in act_norm:
            continue
        ok, _why = is_skill_ready(pack, sk, eval_ts, eff_cd)
        if ok:
            r_norm.append(sk.name)
    for sk in active_major_defs:
        if sk.name in act_maj:
            continue
        ok, why = is_skill_ready(pack, sk, eval_ts, eff_cd)
        if ok:
            r_maj.append(sk.name)
        elif why == "debuff_lock":
            l_maj.append(sk.name)

    ov_dmg = 0.0
    ov_names: List[str] = []
    if player_hits:
        t_lo = float(player_hits[0]["timestamp"]) - 2000.0
        t_hi = float(player_hits[-1]["timestamp"]) + 2000.0
        for oh in player_enemy_hits:
            ogid = int(oh.get("abilityGameID") or 0)
            if ogid in all_own_ids or ogid <= 1:
                continue
            ots = float(oh.get("timestamp") or 0)
            if t_lo <= ots <= t_hi:
                oa = float(oh.get("amount") or 0)
                if oa > 0:
                    ov_dmg += oa
                    onm = run.ab(ogid)
                    if onm not in ov_names:
                        ov_names.append(onm)

    # 精确外减/团减（若为多跳 DoT，检查整个受击期间是否覆盖了外减）
    ext_b: List[str] = []
    if outcome == "hit":
        check_ts = [float(h["timestamp"]) for h in player_hits] if player_hits else [eval_ts]
        for cts in check_ts:
            for nm in external_buffs_at(pack, cts):
                if nm not in ext_b:
                    ext_b.append(nm)

    w_heal, w_heal_top = (0.0, [])
    if player_hits:
        h_lo = float(player_hits[0]["timestamp"]) - 500.0
        h_hi = float(player_hits[-1]["timestamp"]) + 1500.0
        w_heal, w_heal_top = heals_in_window(pack, h_lo, h_hi)

    if player_hits and outcome == "hit":
        last_h = float(player_hits[-1]["timestamp"])
        died = any(last_h - 100.0 <= dt <= last_h + 2000.0 for dt in death_times)
    else:
        died = False

    return WaveRecord(
        skill_key=meta.key,
        skill_name=meta.name,
        is_boss=meta.is_boss,
        cast_ids=set(meta.cast_ids),
        dmg_ids=set(meta.dmg_ids),
        sample_tag=pack.sample.tag,
        player_name=pack.player_name,
        run=run,
        pull=pull,
        wave_ts=eval_ts,
        party_hit_count=party_hit_count,
        party_debuff_count=party_debuff_count,
        outcome=outcome,
        hits=player_hits,
        total_dmg=tot_dmg,
        total_abs=tot_abs,
        start_hp_pct=start_hp,
        min_hp_pct=min_hp,
        active_defs=act_norm + act_maj,
        active_normal=act_norm,
        active_major=act_maj,
        passive_defs=pas_defs,
        ready_normal=r_norm,
        ready_major=r_maj,
        locked_major=l_maj,
        overlap_other_dmg=ov_dmg,
        overlap_skills=ov_names,
        ext_buffs=ext_b,
        window_heal=w_heal,
        window_heal_top=w_heal_top,
        died=died,
    )


def build_enemy_waves(
    packs: List[BossPack],
    active_normal_defs: List[SkillDef],
    active_major_defs: List[SkillDef],
    passive_defs: List[SkillDef],
    eff_cd: Dict[int, float],
    hp_is_post: bool,
) -> Tuple[Dict[str, SkillMeta], List[WaveRecord]]:
    """
    从「敌方关键技能施放」出发（补充孤立伤害/减益）：
    - 区分 Boss 原生技能 vs 带入小怪技能；
    - 同名多伤害 ID（如 电闪雷鸣 1288092 vs 1314051）按伤害 ID 拆键并共享父级 cast_ids；
    - 带 tick=True 多跳 DoT（如 阵风 / 锯齿冲锋 / 箭雨），按「单名目标的一次 applydebuff/非tick首击 → 后续同目标 tick」
      完整归并一轮，彻底避免短 CD DoT 跨目标串波。
    """
    boss_names: Set[str] = {bn for pk in packs for p in pk.pulls for bn in p.boss_names}
    grouped: Dict[Tuple[bool, str], Dict[str, Any]] = {}

    def touch(is_b: bool, nm: str, src_name: str, tag: str) -> Dict[str, Any]:
        g = grouped.setdefault((is_b, nm), {
            "name": nm, "is_boss": is_b, "src_cnt": Counter(),
            "cast_ids": set(), "dmg_ids": set(), "debuff_ids": set(), "runs": set(),
            "dmg_id_counts": Counter(), "tick_dmg_ids": set(),
        })
        if src_name and src_name != "环境":
            g["src_cnt"][src_name] += 1
        g["runs"].add(tag)
        return g

    for pack in packs:
        run = pack.run
        fids = set(run.players.keys()) | set(run.pet_owner.keys())
        for e in pack.enemy_casts:
            gid = int(e.get("abilityGameID") or 0)
            if gid <= 1:
                continue
            src = e.get("sourceID")
            if src in fids:
                continue
            nm = (run.ab(gid) or f"技能{gid}").strip()
            g = touch(is_boss_actor(run, src, boss_names), nm, run.actor_name(src), pack.sample.tag)
            g["cast_ids"].add(gid)
        for e in pack.friendly_dt:
            if e.get("type") != "damage":
                continue
            src = e.get("sourceID")
            if src in fids:
                continue
            gid = int(e.get("abilityGameID") or 0)
            if gid <= 1:
                continue
            nm = (run.ab(gid) or f"技能{gid}").strip()
            g = touch(is_boss_actor(run, src, boss_names), nm, run.actor_name(src), pack.sample.tag)
            g["dmg_ids"].add(gid)
            g["dmg_id_counts"][gid] += 1
            if e.get("tick"):
                g["tick_dmg_ids"].add(gid)
        for e in pack.friendly_debuffs:
            if e.get("type") not in ("applydebuff", "applydebuffstack"):
                continue
            src = e.get("sourceID")
            if src in fids:
                continue
            gid = int(e.get("abilityGameID") or 0)
            if gid <= 1:
                continue
            nm = (run.ab(gid) or f"技能{gid}").strip()
            g = touch(is_boss_actor(run, src, boss_names), nm, run.actor_name(src), pack.sample.tag)
            g["debuff_ids"].add(gid)

    metas: Dict[str, SkillMeta] = {}
    for (is_b, nm), g in grouped.items():
        top_src = g["src_cnt"].most_common(1)[0][0] if g["src_cnt"] else "环境"
        dids_sorted = [gid for gid, _ in g["dmg_id_counts"].most_common()]
        major_dids: List[int] = []
        if dids_sorted:
            top_cnt = g["dmg_id_counts"][dids_sorted[0]]
            for gid in dids_sorted:
                cnt = g["dmg_id_counts"][gid]
                if cnt >= 10 or cnt >= top_cnt * 0.10:
                    major_dids.append(gid)
            if not major_dids:
                major_dids = [dids_sorted[0]]

        prefix = "" if is_b else f"[小怪:{top_src}] "
        if len(major_dids) >= 2:
            for did in major_dids:
                key = f"{prefix}{nm}({did})"
                is_dot = did in g["tick_dmg_ids"]
                metas[key] = SkillMeta(
                    key=key, name=nm, is_boss=is_b, source_npc=top_src, is_dot=is_dot,
                    cast_ids=set(g["cast_ids"]),
                    dmg_ids={did},
                    debuff_ids=set(g["debuff_ids"]) if did == major_dids[0] else set(),
                    runs=set(g["runs"]),
                )
        else:
            key = f"{prefix}{nm}"
            is_dot = bool(g["tick_dmg_ids"] & set(g["dmg_ids"]))
            metas[key] = SkillMeta(
                key=key, name=nm, is_boss=is_b, source_npc=top_src, is_dot=is_dot,
                cast_ids=set(g["cast_ids"]),
                dmg_ids=set(g["dmg_ids"]),
                debuff_ids=set(g["debuff_ids"]),
                runs=set(g["runs"]),
            )

    all_waves: List[WaveRecord] = []

    for pack in packs:
        run = pack.run
        fids = set(run.players.keys()) | set(run.pet_owner.keys())
        player_id = pack.player_id
        player_enemy_hits = [
            e for e in pack.friendly_dt
            if e.get("type") == "damage"
            and e.get("targetID") == player_id
            and e.get("sourceID") not in fids
        ]
        death_times = [float(e.get("timestamp") or 0) for e in pack.deaths]

        for key, meta in metas.items():
            cids = meta.cast_ids
            dids = meta.dmg_ids
            dbids = meta.debuff_ids
            match_dmg_ids = dids if dids else cids
            all_own_ids = cids | dids | dbids

            for pull in pack.pulls:
                raw_casts = [
                    e for e in pack.enemy_casts
                    if int(e.get("abilityGameID") or 0) in cids
                    and (is_boss_actor(run, e.get("sourceID"), boss_names) == meta.is_boss)
                    and pull.start - 500 <= float(e.get("timestamp") or 0) <= pull.end + 500
                    and e.get("type") in ("begincast", "cast")
                ]
                wave_anchors = pair_enemy_cast_anchors(raw_casts) if raw_casts else []

                # ---- 分支 A：带 tick 多跳 DoT，按单目标实例归并，绝不按全局下次施法硬切 ----
                if meta.is_dot:
                    pull_dt = sorted(
                        [
                            e for e in pack.friendly_dt
                            if e.get("type") == "damage"
                            and e.get("sourceID") not in fids
                            and (is_boss_actor(run, e.get("sourceID"), boss_names) == meta.is_boss)
                            and int(e.get("abilityGameID") or 0) in match_dmg_ids
                            and pull.start - 300 <= float(e.get("timestamp") or 0) <= pull.end + 500
                        ],
                        key=lambda x: float(x.get("timestamp") or 0),
                    )
                    pull_deb = sorted(
                        [
                            e for e in pack.friendly_debuffs
                            if e.get("sourceID") not in fids
                            and (is_boss_actor(run, e.get("sourceID"), boss_names) == meta.is_boss)
                            and int(e.get("abilityGameID") or 0) in (dbids | match_dmg_ids)
                            and pull.start - 300 <= float(e.get("timestamp") or 0) <= pull.end + 500
                        ],
                        key=lambda x: float(x.get("timestamp") or 0),
                    )

                    # 补齐无施法事件的孤立首击/上 debuff 锚点
                    orphan_starts: List[float] = []
                    for e in pull_dt:
                        if not e.get("tick"):
                            ts = float(e["timestamp"])
                            if not any(a - 300.0 <= ts <= a + 2000.0 for a in wave_anchors):
                                orphan_starts.append(ts)
                    for e in pull_deb:
                        if e.get("type") in ("applydebuff", "refreshdebuff"):
                            ts = float(e["timestamp"])
                            if not any(a - 300.0 <= ts <= a + 2000.0 for a in wave_anchors):
                                orphan_starts.append(ts)
                    if orphan_starts:
                        orphan_starts.sort()
                        extra: List[float] = []
                        for t in orphan_starts:
                            if not extra or t - extra[-1] > 1800.0:
                                extra.append(t)
                        wave_anchors = sorted(wave_anchors + extra)

                    if not wave_anchors:
                        continue

                    for a, b in zip(wave_anchors, wave_anchors[1:]):
                        if b - a >= 2000.0:
                            meta.intervals.append((b - a) / 1000.0)

                    # 预索引目标玩家的所有 DoT 实例起点与 removedebuff 终点
                    ret_dt = [e for e in pull_dt if e.get("targetID") == player_id]
                    ret_rems = [
                        float(e["timestamp"]) for e in pull_deb
                        if e.get("targetID") == player_id and e.get("type") == "removedebuff"
                    ]
                    ret_starts: List[float] = []
                    for e in pull_deb:
                        if e.get("targetID") == player_id and e.get("type") in ("applydebuff", "refreshdebuff"):
                            ret_starts.append(float(e["timestamp"]))
                    for e in ret_dt:
                        if not e.get("tick"):
                            ts = float(e["timestamp"])
                            if not any(abs(ts - s) <= 500.0 for s in ret_starts):
                                ret_starts.append(ts)
                    ret_starts.sort()
                    # 合并 500ms 内的同一实例起点
                    ret_inst_starts: List[float] = []
                    for s in ret_starts:
                        if not ret_inst_starts or s - ret_inst_starts[-1] > 500.0:
                            ret_inst_starts.append(s)

                    consumed_ret_dt: Set[int] = set()
                    consumed_inst: Set[int] = set()

                    for idx, anchor in enumerate(wave_anchors):
                        nxt = wave_anchors[idx + 1] - 100.0 if idx + 1 < len(wave_anchors) else pull.end + 500.0
                        app_lo = anchor - 300.0
                        app_hi = min(nxt, anchor + 2000.0)

                        # 只统计本波新上 debuff / 非 tick 首击的友方人数（排除上一轮残留跳！）
                        p_hit_tgts: Set[int] = set()
                        p_deb_tgts: Set[int] = set()
                        for e in pull_dt:
                            ts = float(e["timestamp"])
                            if app_lo <= ts <= app_hi and not e.get("tick"):
                                tid = e.get("targetID")
                                if tid in run.players:
                                    p_hit_tgts.add(tid)
                        for e in pull_deb:
                            ts = float(e["timestamp"])
                            if app_lo <= ts <= app_hi and e.get("type") in ("applydebuff", "refreshdebuff"):
                                tid = e.get("targetID")
                                if tid in run.players:
                                    p_deb_tgts.add(tid)
                                    p_hit_tgts.add(tid)

                        # 检查目标玩家是否在本波被点名开启新实例
                        matched_i: Optional[int] = None
                        for ii, ist in enumerate(ret_inst_starts):
                            if ii not in consumed_inst and app_lo <= ist <= app_hi:
                                matched_i = ii
                                break

                        if matched_i is None:
                            all_waves.append(_make_wave_record(
                                pack, pull, meta, anchor,
                                len(p_hit_tgts), len(p_deb_tgts),
                                [], False,
                                active_normal_defs, active_major_defs, passive_defs,
                                eff_cd, hp_is_post, player_enemy_hits, death_times,
                            ))
                            continue

                        consumed_inst.add(matched_i)
                        ist = ret_inst_starts[matched_i]
                        # 找到该实例的自然结束（removedebuff+250ms 或同目标下次实例-100ms 或 +10s 上限）
                        end_cands = [ist + 10000.0, pull.end + 500.0]
                        if matched_i + 1 < len(ret_inst_starts):
                            end_cands.append(ret_inst_starts[matched_i + 1] - 100.0)
                        next_rem = next((r for r in ret_rems if r >= ist + 100.0), None)
                        if next_rem is not None:
                            end_cands.append(next_rem + 250.0)
                        inst_end = min(end_cands)

                        inst_hits: List[Dict[str, Any]] = []
                        for di, e in enumerate(ret_dt):
                            if di in consumed_ret_dt:
                                continue
                            ts = float(e["timestamp"])
                            if ist - 150.0 <= ts <= inst_end:
                                inst_hits.append(e)
                                consumed_ret_dt.add(di)

                        got_deb = any(
                            e.get("targetID") == player_id
                            and e.get("type") in ("applydebuff", "refreshdebuff")
                            and abs(float(e["timestamp"]) - ist) <= 400.0
                            for e in pull_deb
                        )
                        eval_ts = float(inst_hits[0]["timestamp"]) if inst_hits else ist
                        tot_raw = sum(float(h.get("amount") or 0) + float(h.get("absorbed") or 0) for h in inst_hits)
                        if tot_raw > 0:
                            meta.party_raw_dmgs.append(tot_raw)

                        all_waves.append(_make_wave_record(
                            pack, pull, meta, eval_ts,
                            max(len(p_hit_tgts), 1), max(len(p_deb_tgts), 1 if got_deb else 0),
                            inst_hits, got_deb,
                            active_normal_defs, active_major_defs, passive_defs,
                            eff_cd, hp_is_post, player_enemy_hits, death_times,
                        ))
                    continue

                # ---- 分支 B：非 DoT 爆发 / 延迟引爆 / AOE / 可躲秒杀技 ----
                orphan_pts: List[float] = []
                for e in pack.friendly_dt:
                    if (e.get("type") == "damage"
                            and e.get("sourceID") not in fids
                            and (is_boss_actor(run, e.get("sourceID"), boss_names) == meta.is_boss)
                            and int(e.get("abilityGameID") or 0) in match_dmg_ids
                            and pull.start <= float(e.get("timestamp") or 0) <= pull.end):
                        ts = float(e["timestamp"])
                        if not any(a - 300.0 <= ts <= a + 9000.0 for a in wave_anchors):
                            orphan_pts.append(ts)
                if not wave_anchors:
                    for e in pack.friendly_debuffs:
                        if (e.get("type") == "applydebuff"
                                and e.get("sourceID") not in fids
                                and (is_boss_actor(run, e.get("sourceID"), boss_names) == meta.is_boss)
                                and int(e.get("abilityGameID") or 0) in dbids
                                and pull.start <= float(e.get("timestamp") or 0) <= pull.end):
                            orphan_pts.append(float(e["timestamp"]))
                if orphan_pts:
                    orphan_pts.sort()
                    extra = []
                    for t in orphan_pts:
                        if not extra or t - extra[-1] > 3500.0:
                            extra.append(t)
                    wave_anchors = sorted(wave_anchors + extra)

                if not wave_anchors:
                    continue

                for a, b in zip(wave_anchors, wave_anchors[1:]):
                    if b - a >= 3000.0:
                        meta.intervals.append((b - a) / 1000.0)

                for idx, anchor in enumerate(wave_anchors):
                    nxt = wave_anchors[idx + 1] - 300.0 if idx + 1 < len(wave_anchors) else pull.end + 500.0
                    w_start = anchor - 300.0
                    w_end = min(nxt, anchor + 9000.0)

                    party_hit_targets: Set[int] = set()
                    party_deb_targets: Set[int] = set()
                    player_hits: List[Dict[str, Any]] = []

                    for e in pack.friendly_dt:
                        if e.get("type") != "damage" or e.get("sourceID") in fids:
                            continue
                        if int(e.get("abilityGameID") or 0) not in match_dmg_ids:
                            continue
                        ts = float(e.get("timestamp") or 0)
                        if w_start <= ts <= w_end:
                            tid = e.get("targetID")
                            raw_d = float(e.get("amount") or 0) + float(e.get("absorbed") or 0)
                            if tid in run.players:
                                party_hit_targets.add(tid)
                                if raw_d > 0:
                                    meta.party_raw_dmgs.append(raw_d)
                            if tid == player_id:
                                player_hits.append(e)

                    player_got_debuff = False
                    for e in pack.friendly_debuffs:
                        if e.get("type") not in ("applydebuff", "applydebuffstack") or e.get("sourceID") in fids:
                            continue
                        if int(e.get("abilityGameID") or 0) not in dbids:
                            continue
                        ts = float(e.get("timestamp") or 0)
                        if w_start <= ts <= w_end:
                            tid = e.get("targetID")
                            if tid in run.players:
                                party_deb_targets.add(tid)
                            if tid == player_id:
                                player_got_debuff = True

                    eval_ts = float(player_hits[0]["timestamp"]) if player_hits else anchor
                    all_waves.append(_make_wave_record(
                        pack, pull, meta, eval_ts,
                        len(party_hit_targets), len(party_deb_targets),
                        player_hits, player_got_debuff,
                        active_normal_defs, active_major_defs, passive_defs,
                        eff_cd, hp_is_post, player_enemy_hits, death_times,
                    ))

    return metas, all_waves


def detect_dangers(
    packs: List[BossPack],
    active_normal_defs: List[SkillDef],
    active_major_defs: List[SkillDef],
    passive_defs: List[SkillDef],
    eff_cd: Dict[int, float],
    hp_is_post: bool,
    use_run_clock: bool = False,
) -> List[Dict[str, Any]]:
    """维度 ④：扫描全部死亡 & 残血(<20% HP)事件，回溯前 5 秒连招，附可点击 WCL 事件链接。"""
    all_defs = active_normal_defs + active_major_defs
    dangers: List[Dict[str, Any]] = []

    for pack in packs:
        run = pack.run
        pid = pack.player_id
        p_hits = [
            e for e in pack.friendly_dt
            if e.get("type") == "damage" and e.get("targetID") == pid
        ]
        p_hits.sort(key=lambda x: float(x.get("timestamp") or 0))

        raw_pts: List[Tuple[float, str, float, Pull]] = []
        for d in pack.deaths:
            ts = float(d.get("timestamp") or 0)
            pl = next((p for p in pack.pulls if p.start - 500 <= ts <= p.end + 1500), pack.pulls[0])
            raw_pts.append((ts, "死亡", 0.0, pl))

        for h in p_hits:
            _pre, post = hp_before_after(h, hp_is_post)
            if post is not None and post < 20.0:
                ts = float(h.get("timestamp") or 0)
                pl = next((p for p in pack.pulls if p.start - 500 <= ts <= p.end + 500), pack.pulls[0])
                raw_pts.append((ts, "残血", post, pl))

        raw_pts.sort(key=lambda x: x[0])
        clusters: List[List[Tuple[float, str, float, Pull]]] = []
        for pt in raw_pts:
            if clusters and pt[0] - clusters[-1][0][0] <= 5000.0:
                clusters[-1].append(pt)
            else:
                clusters.append([pt])

        for cl in clusters:
            deaths_in = [x for x in cl if x[1] == "死亡"]
            chosen = deaths_in[0] if deaths_in else min(cl, key=lambda x: x[2])
            ts, kind, hp_pct, pl = chosen
            chain_hits = [
                h for h in p_hits
                if ts - 5000.0 <= float(h.get("timestamp") or 0) <= ts + 100.0
                and (float(h.get("amount") or 0) > 0 or float(h.get("absorbed") or 0) > 0)
            ]
            combo_parts: List[str] = []
            skill_seq: List[str] = []
            for h in chain_hits[-6:]:
                hts = float(h["timestamp"])
                dt_s = (hts - ts) / 1000.0
                anm = run.ab(h.get("abilityGameID"))
                amt = float(h.get("amount") or 0)
                abso = float(h.get("absorbed") or 0)
                _, post_h = hp_before_after(h, hp_is_post)
                hp_tag = f"→{post_h:.0f}%" if post_h is not None else ""
                abs_tag = f"(吸{fmt.num(abso)})" if abso > 0 else ""
                combo_parts.append(f"{dt_s:+.1f}s {anm} {fmt.num(amt)}{abs_tag}{hp_tag}")
                if anm != "近战" and (not skill_seq or skill_seq[-1] != anm):
                    skill_seq.append(anm)

            act = [s.name for s in active_defensives_at(pack, all_defs, ts)]
            pas = [s.name for s in active_defensives_at(pack, passive_defs, ts, buff_only=True)]
            r_norm = [s.name for s in active_normal_defs if s.name not in act and is_skill_ready(pack, s, ts, eff_cd)[0]]
            r_maj = [s.name for s in active_major_defs if s.name not in act and is_skill_ready(pack, s, ts, eff_cd)[0]]
            ext = external_buffs_at(pack, ts)
            dangers.append({
                "tag": pack.sample.tag,
                "ref_md": wcl_ref(pack.sample.tag, pl, run, ts, use_run_clock=use_run_clock),
                "player": pack.player_name,
                "kind": kind,
                "hp_pct": hp_pct,
                "rel_t": run.t(ts, True) if use_run_clock else rel_pull(pl, ts),
                "combo": " → ".join(combo_parts) if combo_parts else "（无伤害记录）",
                "pattern": " + ".join(skill_seq[-3:]) if skill_seq else "未知",
                "active": act,
                "passive": pas,
                "ready_norm": r_norm,
                "ready_maj": r_maj,
                "ext": ext,
                "wipe": pl.kill is False,
            })
    return dangers


def detect_interactions(
    packs: List[BossPack],
    cleanse_skills: List[SkillDef],
    major_skills: List[SkillDef],
    wh_info: Dict[int, Dict[str, Any]],
    use_run_clock: bool = False,
) -> Tuple[List[str], List[str]]:
    """维度 ⑤：清除实锤（排除自然到期与驱散） + 严格窗内免疫/穿透实锤，全部附 WCL 锚点链接。"""
    emp_dur_samples: Dict[int, List[float]] = defaultdict(list)
    cleanse_cast_ids = {s.cast for s in cleanse_skills}

    for pack in packs:
        pid = pack.player_id
        fids = set(pack.run.players.keys()) | set(pack.run.pet_owner.keys())
        c_times = [t for cid in cleanse_cast_ids for t in (pack.cast_times.get(cid) or [])]
        disp_times = [
            float(e.get("timestamp") or 0) for e in pack.dispels
            if e.get("targetID") == pid
        ]
        death_times = [float(e.get("timestamp") or 0) for e in pack.deaths]

        for gid, ivs in pack.debuff_intervals.items():
            if gid == 25771:
                continue
            for s, e, src, has_rem in ivs:
                if not has_rem or src in fids:
                    continue
                if any(abs(e - ct) <= 400.0 for ct in c_times):
                    continue
                if any(abs(e - dt) <= 400.0 for dt in disp_times):
                    continue
                if any(abs(e - dt) <= 600.0 for dt in death_times):
                    continue
                dur = e - s
                if 1000.0 <= dur <= 60000.0:
                    emp_dur_samples[gid].append(dur)

    nat_dur_ms: Dict[int, float] = {}
    for gid, vals in emp_dur_samples.items():
        if vals:
            nat_dur_ms[gid] = statistics.median(vals)
    for gid, info in wh_info.items():
        if info.get("duration_ms") and gid not in nat_dur_ms:
            nat_dur_ms[gid] = float(info["duration_ms"])

    cleanse_hits: Dict[Tuple[str, str, int], List[Tuple[float, float, Optional[float], str]]] = defaultdict(list)
    cleanse_skips: Counter[Tuple[str, str, str]] = Counter()

    for pack in packs:
        pid = pack.player_id
        fids = set(pack.run.players.keys()) | set(pack.run.pet_owner.keys())
        for sk in cleanse_skills:
            for ct in pack.cast_times.get(sk.cast) or []:
                pl = next((p for p in pack.pulls if p.start - 500 <= ct <= p.end + 500), None)
                if not pl:
                    continue
                for gid, ivs in pack.debuff_intervals.items():
                    if gid == 25771:
                        continue
                    for s, e, src, has_rem in ivs:
                        if not has_rem or src in fids:
                            continue
                        delta = e - ct
                        if not (-50.0 <= delta <= 250.0):
                            continue
                        dname = pack.run.ab(gid)
                        is_dispelled = any(
                            d.get("targetID") == pid
                            and int(d.get("extraAbilityGameID") or 0) == gid
                            and abs(float(d.get("timestamp") or 0) - e) <= 300.0
                            and int(d.get("abilityGameID") or 0) != sk.cast
                            for d in pack.dispels
                        )
                        if is_dispelled:
                            cleanse_skips[(sk.name, dname, "队友驱散")] += 1
                            continue
                        lived = e - s
                        nat = nat_dur_ms.get(gid) or (wh_info.get(gid) or {}).get("duration_ms")
                        if nat and lived >= nat - 500.0:
                            cleanse_skips[(sk.name, dname, "自然到期")] += 1
                            continue
                        cleanse_hits[(sk.name, dname, gid)].append((
                            delta, lived / 1000.0, (nat / 1000.0 if nat else None),
                            wcl_ref(pack.sample.tag, pl, pack.run, ct, use_run_clock=use_run_clock),
                        ))

    cleanse_lines: List[str] = []
    for (cname, dname, gid), items in sorted(cleanse_hits.items(), key=lambda kv: -len(kv[1])):
        d_med = statistics.median([x[0] for x in items])
        l_med = statistics.median([x[1] for x in items])
        nat_s = items[0][2]
        nat_tag = f"自然{nat_s:.1f}s" if nat_s else "自然未知"
        refs = "、".join(x[3] for x in items[:3])
        cleanse_lines.append(
            f"- 清除实锤：`{cname}` → 提前清掉 `{dname}({gid})` ×{len(items)}次"
            f"（Δt中位 {d_med:+.0f}ms，已持续 {l_med:.1f}s / {nat_tag}，样本 {refs}）"
        )
    for (cname, dname, reason), cnt in cleanse_skips.most_common(4):
        cleanse_lines.append(f"- （已排除伪清除：`{cname}` 旁 `{dname}` 消失 ×{cnt}次，实为{reason}）")

    imm_map: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    for pack in packs:
        pid = pack.player_id
        fids = set(pack.run.players.keys()) | set(pack.run.pet_owner.keys())
        for e in pack.friendly_dt:
            if e.get("type") != "damage" or e.get("targetID") != pid or e.get("sourceID") in fids:
                continue
            gid = int(e.get("abilityGameID") or 0)
            if gid <= 1:
                continue
            ts = float(e.get("timestamp") or 0)
            act_maj = active_defensives_at(pack, major_skills, ts, slack_ms=-50.0)
            if not act_maj:
                continue
            amt = float(e.get("amount") or 0)
            abso = float(e.get("absorbed") or 0)
            pl = next((p for p in pack.pulls if p.start - 500 <= ts <= p.end + 500), pack.pulls[0])
            enm = pack.run.ab(gid)
            for sk in act_maj:
                rec = imm_map.setdefault((sk.name, enm, gid), {"zero": 0, "dmg": 0, "dmgs": [], "refs": []})
                if amt == 0 and abso == 0:
                    rec["zero"] += 1
                    if len(rec["refs"]) < 3:
                        rec["refs"].append(wcl_ref(pack.sample.tag, pl, pack.run, ts, use_run_clock=use_run_clock))
                else:
                    rec["dmg"] += 1
                    rec["dmgs"].append(amt + abso)
                    if len(rec["refs"]) < 3:
                        rec["refs"].append(wcl_ref(pack.sample.tag, pl, pack.run, ts, use_run_clock=use_run_clock))

    imm_lines: List[str] = []
    for (mname, enm, gid), rec in sorted(imm_map.items(), key=lambda kv: -(kv[1]["zero"] + kv[1]["dmg"])):
        refs = "、".join(rec["refs"])
        if rec["zero"] > 0 and rec["dmg"] == 0:
            imm_lines.append(f"- 免疫实锤：`{mname}` 完全免疫 `{enm}({gid})`（0伤 ×{rec['zero']}次，样本 {refs}）")
        elif rec["dmg"] > 0 and rec["zero"] == 0:
            dm = statistics.median(rec["dmgs"])
            imm_lines.append(f"- 穿透实锤：`{mname}` **不免疫** `{enm}({gid})`（仍吃中位 {fmt.num(dm)} ×{rec['dmg']}次，样本 {refs}）")
        else:
            dm = statistics.median(rec["dmgs"]) if rec["dmgs"] else 0
            imm_lines.append(
                f"- 混合交互：`{mname}` vs `{enm}({gid})`（0伤 ×{rec['zero']}次 / 仍掉血 ×{rec['dmg']}次 中位{fmt.num(dm)}，样本 {refs}）"
            )

    return cleanse_lines, imm_lines


# ============================================================================
# 子命令 2：boss（一屏 5 维输出）
# ============================================================================

def select_key_skills(
    metas: Dict[str, SkillMeta],
    waves: List[WaveRecord],
    n_runs: int,
) -> Tuple[List[str], List[str]]:
    """分开返回 (Boss原生关键技能列表, 带入小怪关键技能列表)。"""
    by_skill: Dict[str, List[WaveRecord]] = defaultdict(list)
    for w in waves:
        by_skill[w.skill_key].append(w)

    boss_scored: List[Tuple[float, str]] = []
    trash_scored: List[Tuple[float, str]] = []

    for key, ws in by_skill.items():
        m = metas[key]
        hits = [w for w in ws if w.outcome == "hit"]
        immunes = [w for w in ws if w.outcome == "immune"]
        party_hits = sum(w.party_hit_count for w in ws)
        party_debs = sum(w.party_debuff_count for w in ws)
        max_dmg = max((w.total_dmg + w.total_abs for w in hits), default=0.0)
        party_med = med(m.party_raw_dmgs) or 0.0
        if not hits and not immunes and party_hits == 0 and party_debs == 0:
            if len(ws) < max(3, int(n_runs * 0.4)):
                continue
        score = max(max_dmg, party_med * 0.6) + len(hits) * 200_000 + len(immunes) * 500_000 + party_hits * 40_000 + len(ws) * 5_000
        if m.is_boss:
            boss_scored.append((score, key))
        else:
            if hits or immunes or party_hits >= 10:
                trash_scored.append((score, key))

    boss_scored.sort(reverse=True)
    trash_scored.sort(reverse=True)
    return [k for _, k in boss_scored[:10]], [k for _, k in trash_scored[:6]]


def format_one_screen(
    meta_runs: Dict[str, Any],
    cls_name: str,
    packs: List[BossPack],
    defs: List[SkillDef],
    utils: List[SkillDef],
    eff_cd: Dict[int, float],
    cd_stats: Dict[int, Dict[str, Any]],
    active_norm: List[SkillDef],
    active_maj: List[SkillDef],
    zero_cast_defs: List[SkillDef],
    metas: Dict[str, SkillMeta],
    waves: List[WaveRecord],
    dangers: List[Dict[str, Any]],
    cleanse_lines: List[str],
    imm_lines: List[str],
    wh_info: Dict[int, Dict[str, Any]],
) -> str:
    n_runs = len(packs)
    boss_name = "、".join(packs[0].pulls[0].boss_names) or packs[0].pulls[0].name
    boss_eid = packs[0].pulls[0].encounter_id
    durs = [sum(p.dur for p in pk.pulls) / 1000.0 for pk in packs]
    med_dur = statistics.median(durs)
    med_hp = statistics.median([pk.max_hp for pk in packs if pk.max_hp > 0]) if any(pk.max_hp > 0 for pk in packs) else 0.0
    levels = Counter(pk.sample.level for pk in packs)
    lv_str = " / ".join(f"+{lv}×{c}" for lv, c in sorted(levels.items(), reverse=True))
    trash_runs = sum(1 for pk in packs if any(
        any(n not in p.boss_names for n, _ in p.mobs) for p in pk.pulls
    ))

    out: List[str] = []
    out.append(f"# {meta_runs.get('dungeon')} · {boss_name}（encounter {boss_eid}）· {cls_name} 极简五维诊断")
    out.append(
        f"> 样本：{n_runs} 场高分限时（{lv_str}，不同报告/玩家）| 中位战斗时长 {fmt.clock(med_dur * 1000)} "
        f"| {cls_name}中位血量 {fmt.num(med_hp)} | 拉入小怪合波 {trash_runs}/{n_runs} 场"
    )

    boss_keys, trash_keys = select_key_skills(metas, waves, n_runs)
    by_skill: Dict[str, List[WaveRecord]] = defaultdict(list)
    for w in waves:
        by_skill[w.skill_key].append(w)

    def fmt_skill_overview(key: str) -> str:
        ws = by_skill[key]
        m = metas[key]
        ids_all = sorted(m.cast_ids | m.dmg_ids | m.debuff_ids)
        id_str = "/".join(str(x) for x in ids_all[:3])
        p_cnts = [max(w.party_hit_count, w.party_debuff_count) for w in ws if max(w.party_hit_count, w.party_debuff_count) > 0]
        p_all = [max(w.party_hit_count, w.party_debuff_count) for w in ws]
        p_med = med(p_cnts) if (m.is_dot and p_cnts) else med(p_all)
        p_max = max(p_all) if p_all else 0
        cyc = f"~{statistics.median(m.intervals):.1f}s" if m.intervals and statistics.median(m.intervals) < 10 else (
            f"~{statistics.median(m.intervals):.0f}s" if m.intervals else "一次性/不固定"
        )

        hits = [w for w in ws if w.outcome == "hit"]
        pure_bare = [w for w in hits if not w.active_defs and not w.passive_defs and not w.ext_buffs]
        sample_hits = pure_bare or hits
        imm_cnt = sum(1 for w in ws if w.outcome == "immune")
        dodge_cnt = sum(1 for w in ws if w.outcome == "dodged")

        if sample_hits:
            dmg_med = statistics.median([w.total_dmg + w.total_abs for w in sample_hits])
            dmg_pct = (100.0 * dmg_med / med_hp) if med_hp else 0.0
            tick_med = statistics.median([len(w.hits) for w in sample_hits])
            tick_tag = f"({tick_med:.0f}跳合)" if tick_med >= 1.8 else ""
            dmg_str = (
                f"纯裸吃中位 {fmt.num(dmg_med)} ({dmg_pct:.0f}%HP){tick_tag}"
                if pure_bare else f"有覆盖中位 {fmt.num(dmg_med)} ({dmg_pct:.0f}%HP){tick_tag}"
            )
        elif m.party_raw_dmgs:
            p_dmg = statistics.median(m.party_raw_dmgs)
            p_pct = (100.0 * p_dmg / med_hp) if med_hp else 0.0
            dmg_str = f"本专精0掉血（全队命中中位 {fmt.num(p_dmg)} ≈{p_pct:.0f}%本专精HP）"
        else:
            dmg_str = "本专精0直接承伤"

        if p_med is not None and p_med >= 4:
            shape = "全队AOE"
        elif p_med is not None and p_med >= 1.5:
            shape = f"点/扫{p_med:.0f}人(最高{p_max})"
        elif p_max >= 1:
            shape = f"单点{p_med:.0f}人(最高{p_max})" if m.is_dot else f"单点/可躲(中位{p_med:.0f}人,最高{p_max})"
        else:
            shape = "非伤害/状态技"
        if m.debuff_ids or m.is_dot:
            shape += "+DoT" if m.is_dot else "+Debuff"

        wh_desc = ""
        for gid in sorted(m.dmg_ids) + sorted(m.cast_ids):
            if gid in wh_info and wh_info[gid].get("description"):
                dtxt = wh_info[gid]["description"].replace("\n", " ")
                wh_desc = dtxt[:52] + ("…" if len(dtxt) > 52 else "")
                break

        return (
            f"- **{key}**（{m.source_npc}, ID:{id_str}）：{shape} | 周期 {cyc} | {dmg_str} | "
            f"共{len(ws)}波（中{len(hits)} / 免疫{imm_cnt} / 躲避未中{dodge_cnt}）"
            + (f" — *{wh_desc}*" if wh_desc else "")
        )

    # ---- ① 机制速览 ----
    out.append("\n## ① 机制速览（按敌方关键技能施放主键，DoT 按单目标完整归并）")
    for k in boss_keys:
        out.append(fmt_skill_overview(k))
    if trash_keys:
        out.append("- *（合波带入小怪威胁技）*：")
        for k in trash_keys:
            out.append("  " + fmt_skill_overview(k))

    # ---- ② 手牌预算账 ----
    out.append("\n## ② 手牌预算账")
    for sk in defs:
        st = cd_stats[sk.cast]
        tier_tag = "常规" if sk.tier == "normal" else "大牌"
        zero_tag = " 【全本0次主动施放，已从分母排除（被动盾归入其他覆盖）】" if st["total_dungeon_casts"] == 0 else ""
        out.append(
            f"- **{sk.name}**（{tier_tag}）：实际CD {st['cd_note']} | "
            f"开怪前在CD {st['on_cd_at_pull']}/{n_runs} | "
            f"Boss场均 {st['avg_boss_casts']:.2f}次（{st['used_boss_runs']}/{n_runs}场用过，全本共{st['total_dungeon_casts']}次）{zero_tag}"
        )
    util_parts: List[str] = []
    for sk in utils:
        st = cd_stats[sk.cast]
        if st["total_boss_casts"] > 0:
            util_parts.append(f"{sk.name} {st['avg_boss_casts']:.2f}次/场({st['used_boss_runs']}/{n_runs}场)")
    if util_parts:
        out.append("- 功能/应急牌（Boss内用过）：" + " | ".join(util_parts))
    out.append(
        f"- 分母口径：常规减伤 = `{'、'.join(s.name for s in active_norm) or '无'}`；"
        f"大牌免疫 = `{'、'.join(s.name for s in active_maj) or '无'}`"
        + (f"（全本 0 次主动施放已排除：{'、'.join(s.name for s in zero_cast_defs)}）" if zero_cast_defs else "")
    )

    # ---- ③ 正例 vs 反例对照 ----
    out.append("\n## ③ 正例 vs 反例对照（被动盾与明确外减单独隔离为「其他覆盖」，最危样本附 WCL 锚点）")

    def summarize_group(label: str, grp: List[WaveRecord], show_rescue: bool = False) -> str:
        if not grp:
            return f"  - {label}：0次"
        s_hps = [w.start_hp_pct for w in grp if w.start_hp_pct is not None]
        e_hps = [w.min_hp_pct for w in grp if w.min_hp_pct is not None]
        ov = sum(1 for w in grp if w.overlap_other_dmg > 0)
        died = sum(1 for w in grp if w.died)
        imm = sum(1 for w in grp if w.outcome == "immune")
        sh_s = f"起手{med(s_hps):.0f}%(低{min(s_hps):.0f}%)" if s_hps else "起手—"
        eh_s = f"剩血{med(e_hps):.0f}%(低{min(e_hps):.0f}%)" if e_hps else "剩血—"
        extra = []
        if imm:
            extra.append(f"免疫{imm}次")
        if died:
            extra.append(f"**2s内死{died}次**")
        if ov:
            extra.append(f"叠伤{ov}/{len(grp)}")
        if show_rescue:
            low_grp = sorted([w for w in grp if w.min_hp_pct is not None], key=lambda x: x.min_hp_pct or 100.0)
            if low_grp:
                w0 = low_grp[0]
                rescue_notes = []
                if w0.ext_buffs:
                    rescue_notes.append("外减:" + "/".join(w0.ext_buffs))
                if w0.passive_defs:
                    rescue_notes.append("被动:" + "/".join(w0.passive_defs))
                if w0.total_abs > 0 and med_hp and w0.total_abs >= med_hp * 0.12:
                    rescue_notes.append(f"盾吸{fmt.num(w0.total_abs)}")
                if w0.window_heal > 0 and med_hp and w0.window_heal >= med_hp * 0.25:
                    rescue_notes.append(f"窗内抬血{fmt.num(w0.window_heal)}")
                r_str = ("[" + ",".join(rescue_notes) + "]") if rescue_notes else "[无外减]"
                ref_link = wcl_ref(w0.sample_tag, w0.pull, w0.run, w0.wave_ts)
                extra.append(
                    f"最危:{ref_link} ({pct_str(w0.start_hp_pct)}→{pct_str(w0.min_hp_pct)}{r_str})"
                )
        return f"  - {label}：{len(grp)}次 | {sh_s} → {eh_s}" + (f" | {'，'.join(extra)}" if extra else "")

    for section_label, key_list in (("Boss 原生技能", boss_keys), ("合波带入小怪威胁技", trash_keys)):
        emitted_hdr = False
        for key in key_list:
            ws = by_skill[key]
            hits_and_imm = [w for w in ws if w.outcome in ("hit", "immune")]
            if not hits_and_imm:
                continue
            if not emitted_hdr:
                out.append(f"### {section_label}")
                emitted_hdr = True
            dodged = [w for w in ws if w.outcome == "dodged"]
            pos_norm = [w for w in hits_and_imm if w.active_normal and not w.active_major]
            pos_maj = [w for w in hits_and_imm if w.active_major]
            no_act = [w for w in hits_and_imm if not w.active_defs]
            other_cov = [w for w in no_act if w.passive_defs or w.ext_buffs]
            pure_bare = [w for w in no_act if not w.passive_defs and not w.ext_buffs]
            neg_ready = [w for w in pure_bare if w.ready_normal]
            neg_cd = [w for w in pure_bare if not w.ready_normal]

            out.append(f"- **{key}**（共{len(ws)}波：中/免疫{len(hits_and_imm)}，躲避/未中{len(dodged)}）")
            if pos_norm:
                sub = Counter("+".join(w.active_normal) for w in pos_norm)
                tag = "正例·常规(" + "/".join(f"{k}×{v}" for k, v in sub.most_common()) + ")"
                out.append(summarize_group(tag, pos_norm))
            if pos_maj:
                sub = Counter("+".join(w.active_defs) for w in pos_maj)
                tag = "正例·大牌(" + "/".join(f"{k}×{v}" for k, v in sub.most_common()) + ")"
                out.append(summarize_group(tag, pos_maj))
            if other_cov:
                sub = Counter("+".join(w.passive_defs + w.ext_buffs) for w in other_cov)
                tag = "其他覆盖(" + "/".join(f"{k}×{v}" for k, v in sub.most_common(4)) + ")"
                out.append(summarize_group(tag, other_cov))
            out.append(summarize_group("反例A·纯裸吃就绪未交", neg_ready, show_rescue=True))
            if neg_cd:
                out.append(summarize_group("反例B·纯裸吃CD未交", neg_cd, show_rescue=True))

    # ---- ④ 死点 & 残血(<20%) 前 5 秒连招 ----
    out.append("\n## ④ 死点 & 残血（<20% HP）前 5 秒连招")
    n_dead = sum(1 for d in dangers if d["kind"] == "死亡")
    n_low = sum(1 for d in dangers if d["kind"] == "残血")
    out.append(f"- 总计：**死亡 {n_dead} 次 / 残血(<20%) {n_low} 次**（覆盖 {n_runs} 场）")
    if dangers:
        pat_cnt = Counter(d["pattern"] for d in dangers)
        out.append("- 高频连招模式：" + " | ".join(f"`{k}` ×{v}" for k, v in pat_cnt.most_common(4)))
        ordered = sorted(dangers, key=lambda x: (0 if x["kind"] == "死亡" else 1, x["hp_pct"]))
        for d in ordered[:10]:
            cov = d["active"] + [f"被动:{x}" for x in d["passive"]] + [f"外减:{x}" for x in d["ext"]]
            st_def = f"身上:{'+'.join(cov)}" if cov else "纯裸吃"
            rd_parts = []
            if d["ready_norm"]:
                rd_parts.append("常规就绪:" + "/".join(d["ready_norm"]))
            if d["ready_maj"]:
                rd_parts.append("大牌就绪:" + "/".join(d["ready_maj"]))
            rd_str = "，".join(rd_parts) if rd_parts else "无牌就绪"
            wipe_tag = "[灭团波]" if d["wipe"] else ""
            out.append(
                f"  - {d['ref_md']} {d['player']} **{d['kind']}({d['hp_pct']:.0f}%)**{wipe_tag} "
                f"[{st_def} | {rd_str}]：{d['combo']}"
            )

    # ---- ⑤ 免疫 / 清除交互实锤 ----
    out.append("\n## ⑤ 免疫 / 清除交互实锤")
    if cleanse_lines:
        out.extend(cleanse_lines)
    else:
        out.append(f"- 清除实锤：{n_runs} 场内未检测到提前清除敌方 Debuff 的实锤。")
    if imm_lines:
        out.extend(imm_lines)
    else:
        out.append(f"- 免疫实锤：{n_runs} 场内未检测到免疫大牌期间的直接伤害交互事件。")

    return "\n".join(out)


def run_boss_load(
    client: Client,
    runs_path: Path,
    cls_path: Path,
    boss_spec: str,
):
    meta_runs, samples = load_samples(runs_path)
    cls_name, defs, utils = load_class_cfg(cls_path)
    all_skills = defs + utils
    all_cast_ids = [s.cast for s in all_skills]
    fallback_dur = {bid: s.dur_ms for s in all_skills for bid in s.buff}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [
            pool.submit(load_boss_pack, client, smp, boss_spec, all_cast_ids, fallback_dur)
            for smp in samples
        ]
        packs = [f.result() for f in futs if f.result() is not None]

    if not packs:
        raise WCLError(f"在 {runs_path} 的样本中未找到 Boss '{boss_spec}'。")

    hp_is_post = detect_hp_is_post(packs)
    eff_cd, cd_stats = calibrate_cooldowns(packs, all_skills)

    # 按全本 0 次主动施放过滤（避免简单 Boss 没人交牌被误踢出分母）；被过滤项转入 passive_defs 隔离被动盾
    active_norm = [s for s in defs if s.tier == "normal" and cd_stats[s.cast]["total_dungeon_casts"] > 0]
    active_maj = [s for s in defs if s.tier == "major" and cd_stats[s.cast]["total_dungeon_casts"] > 0]
    zero_cast_defs = [s for s in defs if cd_stats[s.cast]["total_dungeon_casts"] == 0]

    metas, waves = build_enemy_waves(packs, active_norm, active_maj, zero_cast_defs, eff_cd, hp_is_post)
    return (
        meta_runs, cls_name, packs, defs, utils, eff_cd, cd_stats,
        active_norm, active_maj, zero_cast_defs, metas, waves, hp_is_post,
    )


def cmd_boss(client: Client, args: argparse.Namespace) -> str:
    (
        meta_runs, cls_name, packs, defs, utils, eff_cd, cd_stats,
        active_norm, active_maj, zero_cast_defs, metas, waves, hp_is_post,
    ) = run_boss_load(client, Path(args.runs), Path(args.cls), args.boss)

    wh_ids: Set[int] = set()
    for m in metas.values():
        wh_ids |= m.cast_ids | m.dmg_ids | m.debuff_ids
    wh_info = wowhead.spells(wh_ids, lang="zh") if not args.no_wowhead else {}

    dangers = detect_dangers(packs, active_norm, active_maj, zero_cast_defs, eff_cd, hp_is_post)
    cleanse_skills = [s for s in defs + utils if s.cleanse_immune]
    major_skills = [s for s in defs if s.tier == "major"]
    cleanse_lines, imm_lines = detect_interactions(packs, cleanse_skills, major_skills, wh_info)

    return format_one_screen(
        meta_runs, cls_name, packs, defs, utils, eff_cd, cd_stats,
        active_norm, active_maj, zero_cast_defs, metas, waves,
        dangers, cleanse_lines, imm_lines, wh_info,
    )


# ============================================================================
# 子命令 2b：trash（全本非 Boss 小怪按「怪物名 + 威胁技能」聚合五维诊断）
# ============================================================================

def load_trash_pack(
    client: Client,
    sample: RunSample,
    all_track_cast_ids: List[int],
    own_buff_ids: List[int],
    skill_fallback_dur: Dict[int, float],
) -> Optional[BossPack]:
    run = load_run(client, f"{sample.code}#fight={sample.fid}")
    player = run.find_player(sample.player)
    trash_pulls = [p for p in run.pulls if not p.is_boss]
    boss_pulls = [p for p in run.pulls if p.is_boss]
    if not trash_pulls:
        stderr(f"[diag] {sample.tag} ({sample.player}) 未找到非 Boss 小怪波次，跳过。")
        return None

    cast_expr = ""
    if all_track_cast_ids:
        cast_expr = "ability.id in (%s)" % ", ".join(str(x) for x in sorted(set(all_track_cast_ids)))
    own_buff_expr = ""
    if own_buff_ids:
        own_buff_expr = "ability.id in (%s)" % ", ".join(str(x) for x in sorted(set(own_buff_ids)))
    ext_expr = "ability.id in (%s)" % ", ".join(str(x) for x in sorted(EXTERNAL_DEF_BUFF_IDS))

    # 全本瘦身拉取：复用 boss 阶段已缓存的 player_casts，buffs 按 ID 过滤仅 ~100 条/场
    p_casts, _ = data.events(
        run, data_type="Casts", start=run.start, end=run.end,
        hostility="Friendlies", source=player.id, expr=cast_expr, limit=2000,
    )
    p_buffs, _ = data.events(
        run, data_type="Buffs", start=run.start, end=run.end,
        hostility="Friendlies", target=player.id, expr=own_buff_expr, limit=3000,
    )
    ext_buff_evs, _ = data.events(
        run, data_type="Buffs", start=run.start, end=run.end,
        hostility="Friendlies", expr=ext_expr, limit=3000,
    )
    p_buffs = p_buffs + [e for e in ext_buff_evs if e.get("targetID") == player.id]

    tgt_expr = f'target.name = "{esc(player.name)}"'
    p_dt, trunc_dt = data.events(
        run, data_type="DamageTaken", start=run.start, end=run.end,
        hostility="Friendlies", expr=tgt_expr, limit=12000, include_resources=True,
    )
    p_deb, _ = data.events(
        run, data_type="Debuffs", start=run.start, end=run.end,
        hostility="Friendlies", expr=tgt_expr, limit=6000,
    )
    e_casts, trunc_ec = data.events(
        run, data_type="Casts", start=run.start, end=run.end,
        hostility="Enemies", expr='type = "cast"', limit=15000,
    )
    dispels_evs, _ = data.events(
        run, data_type="Dispels", start=run.start, end=run.end,
        hostility="Friendlies", limit=2000,
    )
    int_evs, _ = data.events(
        run, data_type="Interrupts", start=run.start, end=run.end,
        hostility="Friendlies", source=player.id, limit=1000,
    )
    death_evs, _ = data.events(
        run, data_type="Deaths", start=run.start, end=run.end,
        hostility="Friendlies", target=player.id, limit=200,
    )
    # v1 的 Deaths 不认 target 参数，会返回全队死亡，必须本地再按本人过滤
    death_evs = [e for e in death_evs if e.get("targetID") == player.id]
    if trunc_dt:
        stderr(f"[warn] {sample.tag} trash DamageTaken 达到上限被截断")
    if trunc_ec:
        stderr(f"[warn] {sample.tag} trash Enemy Casts 达到上限被截断")

    def in_trash(ts: float) -> bool:
        if any(bp.start <= ts <= bp.end for bp in boss_pulls):
            return False
        return any(p.start - 500 <= ts <= p.end + 500 for p in trash_pulls)

    f_dt = [e for e in p_dt if in_trash(float(e.get("timestamp") or 0))]
    e_casts = [e for e in e_casts if in_trash(float(e.get("timestamp") or 0))]
    dispels_evs = [e for e in dispels_evs if in_trash(float(e.get("timestamp") or 0))]
    int_evs = [e for e in int_evs if in_trash(float(e.get("timestamp") or 0))]
    death_evs = [e for e in death_evs if in_trash(float(e.get("timestamp") or 0))]

    buff_ivs = build_aura_intervals(
        p_buffs, player.id,
        {"applybuff", "refreshbuff", "applybuffstack"},
        {"removebuff"},
        skill_fallback_dur, run.end,
    )
    debuff_ivs = build_aura_intervals(
        p_deb, player.id,
        {"applydebuff", "refreshdebuff", "applydebuffstack"},
        {"removedebuff"},
        {25771: 30000.0}, run.end,
    )
    cast_times: Dict[int, List[float]] = defaultdict(list)
    for e in sorted(p_casts, key=lambda x: x.get("timestamp") or 0):
        if e.get("type") == "cast" and e.get("abilityGameID"):
            cast_times[int(e["abilityGameID"])].append(float(e["timestamp"]))

    max_hp = 0.0
    for e in f_dt:
        if e.get("targetID") == player.id and e.get("maxHitPoints"):
            max_hp = max(max_hp, float(e["maxHitPoints"]))

    return BossPack(
        sample=sample,
        run=run,
        player_id=player.id,
        player_name=player.name,
        pulls=trash_pulls,
        player_all_casts=p_casts,
        player_buffs=p_buffs,
        friendly_dt=f_dt,
        friendly_debuffs=[e for e in p_deb if in_trash(float(e.get("timestamp") or 0))],
        enemy_casts=e_casts,
        player_heals=[],
        dispels=dispels_evs,
        deaths=death_evs,
        interrupts=int_evs,
        buff_intervals=buff_ivs,
        debuff_intervals=debuff_ivs,
        cast_times=cast_times,
        max_hp=max_hp,
    )


def build_trash_waves(
    packs: List[BossPack],
    active_normal_defs: List[SkillDef],
    active_major_defs: List[SkillDef],
    passive_defs: List[SkillDef],
    eff_cd: Dict[int, float],
    hp_is_post: bool,
) -> Tuple[Dict[str, SkillMeta], List[WaveRecord]]:
    """按「怪物名 · 技能名」聚合全本非 Boss 小怪技能（DoT 按单目标实例归并，非 DoT 按施法/受击归并）。"""
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def src_npc(run: Run, aid: Optional[int]) -> str:
        return run.actor_name(aid) if aid not in (None, -1) else "环境"

    def touch(npc: str, nm: str, tag: str) -> Dict[str, Any]:
        g = grouped.setdefault((npc, nm), {
            "npc": npc, "name": nm,
            "cast_ids": set(), "dmg_ids": set(), "debuff_ids": set(), "runs": set(),
            "dmg_id_counts": Counter(), "tick_dmg_ids": set(),
        })
        g["runs"].add(tag)
        return g

    for pack in packs:
        run = pack.run
        fids = set(run.players.keys()) | set(run.pet_owner.keys())
        for e in pack.enemy_casts:
            gid = int(e.get("abilityGameID") or 0)
            if gid <= 1:
                continue
            src = e.get("sourceID")
            if src in fids:
                continue
            npc = src_npc(run, src)
            nm = (run.ab(gid) or f"技能{gid}").strip()
            g = touch(npc, nm, pack.sample.tag)
            g["cast_ids"].add(gid)
        for e in pack.friendly_dt:
            if e.get("type") != "damage":
                continue
            src = e.get("sourceID")
            if src in fids:
                continue
            gid = int(e.get("abilityGameID") or 0)
            if gid <= 1:
                continue
            npc = src_npc(run, src)
            nm = (run.ab(gid) or f"技能{gid}").strip()
            g = touch(npc, nm, pack.sample.tag)
            g["dmg_ids"].add(gid)
            g["dmg_id_counts"][gid] += 1
            if e.get("tick"):
                g["tick_dmg_ids"].add(gid)
        for e in pack.friendly_debuffs:
            if e.get("type") not in ("applydebuff", "applydebuffstack"):
                continue
            src = e.get("sourceID")
            if src in fids:
                continue
            gid = int(e.get("abilityGameID") or 0)
            if gid <= 1:
                continue
            npc = src_npc(run, src)
            nm = (run.ab(gid) or f"技能{gid}").strip()
            g = touch(npc, nm, pack.sample.tag)
            g["debuff_ids"].add(gid)

    metas: Dict[str, SkillMeta] = {}
    for (npc, nm), g in grouped.items():
        dids_sorted = [gid for gid, _ in g["dmg_id_counts"].most_common()]
        major_dids: List[int] = []
        if dids_sorted:
            top_cnt = g["dmg_id_counts"][dids_sorted[0]]
            for gid in dids_sorted:
                cnt = g["dmg_id_counts"][gid]
                if cnt >= 10 or cnt >= top_cnt * 0.10:
                    major_dids.append(gid)
            if not major_dids:
                major_dids = [dids_sorted[0]]

        if len(major_dids) >= 2:
            for did in major_dids:
                key = f"{npc} · {nm}({did})"
                metas[key] = SkillMeta(
                    key=key, name=nm, is_boss=False, source_npc=npc,
                    is_dot=(did in g["tick_dmg_ids"]),
                    cast_ids=set(g["cast_ids"]), dmg_ids={did},
                    debuff_ids=set(g["debuff_ids"]) if did == major_dids[0] else set(),
                    runs=set(g["runs"]),
                )
        else:
            key = f"{npc} · {nm}"
            metas[key] = SkillMeta(
                key=key, name=nm, is_boss=False, source_npc=npc,
                is_dot=bool(g["tick_dmg_ids"] & set(g["dmg_ids"])),
                cast_ids=set(g["cast_ids"]), dmg_ids=set(g["dmg_ids"]),
                debuff_ids=set(g["debuff_ids"]), runs=set(g["runs"]),
            )

    all_waves: List[WaveRecord] = []

    for pack in packs:
        run = pack.run
        fids = set(run.players.keys()) | set(run.pet_owner.keys())
        player_id = pack.player_id
        player_enemy_hits = [
            e for e in pack.friendly_dt
            if e.get("type") == "damage"
            and e.get("targetID") == player_id
            and e.get("sourceID") not in fids
        ]
        death_times = [float(e.get("timestamp") or 0) for e in pack.deaths]

        # 按 (npc, gid) 预分组，加速 15 场 × 几十种小怪技的聚合
        dt_by_npc_gid: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
        for e in player_enemy_hits:
            dt_by_npc_gid[(src_npc(run, e.get("sourceID")), int(e.get("abilityGameID") or 0))].append(e)
        deb_by_npc_gid: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
        for e in pack.friendly_debuffs:
            if e.get("sourceID") in fids or e.get("targetID") != player_id:
                continue
            deb_by_npc_gid[(src_npc(run, e.get("sourceID")), int(e.get("abilityGameID") or 0))].append(e)
        ec_by_npc_gid: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
        for e in pack.enemy_casts:
            if e.get("sourceID") in fids:
                continue
            ec_by_npc_gid[(src_npc(run, e.get("sourceID")), int(e.get("abilityGameID") or 0))].append(e)

        def pull_for(ts: float) -> Pull:
            return next((p for p in pack.pulls if p.start - 500 <= ts <= p.end + 500), pack.pulls[0])

        for key, meta in metas.items():
            npc = meta.source_npc
            cids = meta.cast_ids
            dids = meta.dmg_ids
            dbids = meta.debuff_ids
            match_dmg_ids = dids if dids else cids

            ret_dt = sorted(
                [e for g in match_dmg_ids for e in dt_by_npc_gid.get((npc, g), [])],
                key=lambda x: float(x.get("timestamp") or 0),
            )
            ret_deb = sorted(
                [e for g in (dbids | match_dmg_ids) for e in deb_by_npc_gid.get((npc, g), [])],
                key=lambda x: float(x.get("timestamp") or 0),
            )
            raw_casts = sorted(
                [e for g in cids for e in ec_by_npc_gid.get((npc, g), [])],
                key=lambda x: float(x.get("timestamp") or 0),
            )
            if not ret_dt and not ret_deb and not raw_casts:
                continue

            cast_anchors = pair_enemy_cast_anchors(raw_casts) if raw_casts else []

            if meta.is_dot:
                ret_rems = [float(e["timestamp"]) for e in ret_deb if e.get("type") == "removedebuff"]
                raw_starts: List[float] = []
                for e in ret_deb:
                    if e.get("type") in ("applydebuff", "refreshdebuff"):
                        raw_starts.append(float(e["timestamp"]))
                for e in ret_dt:
                    if not e.get("tick"):
                        ts = float(e["timestamp"])
                        if not any(abs(ts - s) <= 500.0 for s in raw_starts):
                            raw_starts.append(ts)
                # 纯 tick 通道技（无 applydebuff 也无非 tick 首击）按 3s 断档切实例
                if not raw_starts and ret_dt:
                    for e in ret_dt:
                        ts = float(e["timestamp"])
                        if not raw_starts or ts - raw_starts[-1] > 3000.0:
                            raw_starts.append(ts)
                raw_starts.sort()
                inst_starts: List[float] = []
                for s in raw_starts:
                    if not inst_starts or s - inst_starts[-1] > 500.0:
                        inst_starts.append(s)

                consumed_dt: Set[int] = set()
                matched_cast_idx: Set[int] = set()
                for ii, ist in enumerate(inst_starts):
                    pl = pull_for(ist)
                    end_cands = [ist + 10000.0, pl.end + 500.0]
                    if ii + 1 < len(inst_starts):
                        end_cands.append(inst_starts[ii + 1] - 100.0)
                    next_rem = next((r for r in ret_rems if r >= ist + 100.0), None)
                    if next_rem is not None:
                        end_cands.append(next_rem + 250.0)
                    inst_end = min(end_cands)

                    inst_hits: List[Dict[str, Any]] = []
                    for di, e in enumerate(ret_dt):
                        if di in consumed_dt:
                            continue
                        ts = float(e["timestamp"])
                        if ist - 150.0 <= ts <= inst_end:
                            inst_hits.append(e)
                            consumed_dt.add(di)
                    got_deb = any(
                        e.get("type") in ("applydebuff", "refreshdebuff") and abs(float(e["timestamp"]) - ist) <= 400.0
                        for e in ret_deb
                    )
                    for ci, ca in enumerate(cast_anchors):
                        if ci not in matched_cast_idx and ca - 300.0 <= ist <= ca + 2500.0:
                            matched_cast_idx.add(ci)
                            break
                    eval_ts = float(inst_hits[0]["timestamp"]) if inst_hits else ist
                    all_waves.append(_make_wave_record(
                        pack, pl, meta, eval_ts, 1, 1 if got_deb else 0,
                        inst_hits, got_deb,
                        active_normal_defs, active_major_defs, passive_defs,
                        eff_cd, hp_is_post, player_enemy_hits, death_times,
                    ))
                # 未命中目标玩家的施法记为 dodged
                for ci, ca in enumerate(cast_anchors):
                    if ci not in matched_cast_idx:
                        all_waves.append(_make_wave_record(
                            pack, pull_for(ca), meta, ca, 0, 0,
                            [], False,
                            active_normal_defs, active_major_defs, passive_defs,
                            eff_cd, hp_is_post, player_enemy_hits, death_times,
                        ))
            else:
                # 非 DoT：按 1.5s 聚类目标玩家受击，再与敌方 cast 锚点对齐统计躲避/未中
                hit_clusters: List[List[Dict[str, Any]]] = []
                for e in ret_dt:
                    ts = float(e["timestamp"])
                    if hit_clusters and ts - float(hit_clusters[-1][-1]["timestamp"]) <= 1500.0:
                        hit_clusters[-1].append(e)
                    else:
                        hit_clusters.append([e])

                matched_cast_idx = set()
                for cl in hit_clusters:
                    t0 = float(cl[0]["timestamp"])
                    pl = pull_for(t0)
                    got_deb = any(
                        e.get("type") in ("applydebuff", "applydebuffstack") and abs(float(e["timestamp"]) - t0) <= 1000.0
                        for e in ret_deb
                    )
                    for ci, ca in enumerate(cast_anchors):
                        if ci not in matched_cast_idx and ca - 300.0 <= t0 <= ca + 6000.0:
                            matched_cast_idx.add(ci)
                            break
                    all_waves.append(_make_wave_record(
                        pack, pl, meta, t0, 1, 1 if got_deb else 0,
                        cl, got_deb,
                        active_normal_defs, active_major_defs, passive_defs,
                        eff_cd, hp_is_post, player_enemy_hits, death_times,
                    ))
                # 有纯 debuff 无伤害的命中（例如定身/减速类小怪技能）
                for e in ret_deb:
                    if e.get("type") not in ("applydebuff", "applydebuffstack"):
                        continue
                    ts = float(e["timestamp"])
                    if any(abs(ts - float(cl[0]["timestamp"])) <= 1500.0 for cl in hit_clusters):
                        continue
                    for ci, ca in enumerate(cast_anchors):
                        if ci not in matched_cast_idx and ca - 300.0 <= ts <= ca + 4000.0:
                            matched_cast_idx.add(ci)
                            break
                    all_waves.append(_make_wave_record(
                        pack, pull_for(ts), meta, ts, 0, 1,
                        [], True,
                        active_normal_defs, active_major_defs, passive_defs,
                        eff_cd, hp_is_post, player_enemy_hits, death_times,
                    ))
                for ci, ca in enumerate(cast_anchors):
                    if ci not in matched_cast_idx:
                        all_waves.append(_make_wave_record(
                            pack, pull_for(ca), meta, ca, 0, 0,
                            [], False,
                            active_normal_defs, active_major_defs, passive_defs,
                            eff_cd, hp_is_post, player_enemy_hits, death_times,
                        ))

    return metas, all_waves


def detect_player_dispels(packs: List[BossPack], use_run_clock: bool = True) -> List[str]:
    """维度 ⑤ 补充：玩家主动驱散实锤（如清毒术驱散中毒/疾病，含自驱与驱队友统计 + WCL 链接）。"""
    # key: (dispel_name, extra_name, extra_gid) -> {"self": int, "ally": int, "refs": []}
    rec_map: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    for pack in packs:
        run = pack.run
        pid = pack.player_id
        for e in pack.dispels:
            if e.get("type") != "dispel" or e.get("sourceID") != pid:
                continue
            ab_gid = int(e.get("abilityGameID") or 0)
            ex_gid = int(e.get("extraAbilityGameID") or 0)
            if not ex_gid:
                continue
            ab_nm = run.ab(ab_gid)
            ex_nm = run.ab(ex_gid)
            ts = float(e.get("timestamp") or 0)
            pl = next((p for p in pack.pulls if p.start - 500 <= ts <= p.end + 500), pack.pulls[0])
            rec = rec_map.setdefault((ab_nm, ex_nm, ex_gid), {"self": 0, "ally": 0, "refs": []})
            if e.get("targetID") == pid:
                rec["self"] += 1
            else:
                rec["ally"] += 1
            if len(rec["refs"]) < 3:
                rec["refs"].append(wcl_ref(pack.sample.tag, pl, run, ts, use_run_clock=use_run_clock))

    lines: List[str] = []
    for (ab_nm, ex_nm, ex_gid), rec in sorted(rec_map.items(), key=lambda kv: -(kv[1]["self"] + kv[1]["ally"])):
        tot = rec["self"] + rec["ally"]
        refs = "、".join(rec["refs"])
        lines.append(
            f"- 驱散实锤：`{ab_nm}` → 驱散 `{ex_nm}({ex_gid})` ×{tot}次"
            f"（自驱 {rec['self']} / 驱队友 {rec['ally']}，样本 {refs}）"
        )
    return lines


def run_trash_load(
    client: Client,
    runs_path: Path,
    cls_path: Path,
):
    meta_runs, samples = load_samples(runs_path)
    cls_name, defs, utils = load_class_cfg(cls_path)
    all_skills = defs + utils
    all_cast_ids = [s.cast for s in all_skills]
    own_buff_ids = [bid for s in all_skills for bid in s.buff]
    fallback_dur = {bid: s.dur_ms for s in all_skills for bid in s.buff}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [
            pool.submit(load_trash_pack, client, smp, all_cast_ids, own_buff_ids, fallback_dur)
            for smp in samples
        ]
        packs = [f.result() for f in futs if f.result() is not None]

    if not packs:
        raise WCLError(f"在 {runs_path} 的样本中未找到非 Boss 小怪战斗。")

    hp_is_post = detect_hp_is_post(packs)
    eff_cd, cd_stats = calibrate_cooldowns(packs, all_skills)

    active_norm = [s for s in defs if s.tier == "normal" and cd_stats[s.cast]["total_dungeon_casts"] > 0]
    active_maj = [s for s in defs if s.tier == "major" and cd_stats[s.cast]["total_dungeon_casts"] > 0]
    zero_cast_defs = [s for s in defs if cd_stats[s.cast]["total_dungeon_casts"] == 0]

    metas, waves = build_trash_waves(packs, active_norm, active_maj, zero_cast_defs, eff_cd, hp_is_post)
    return (
        meta_runs, cls_name, packs, defs, utils, eff_cd, cd_stats,
        active_norm, active_maj, zero_cast_defs, metas, waves, hp_is_post,
    )


def format_trash_screen(
    meta_runs: Dict[str, Any],
    cls_name: str,
    packs: List[BossPack],
    defs: List[SkillDef],
    utils: List[SkillDef],
    eff_cd: Dict[int, float],
    cd_stats: Dict[int, Dict[str, Any]],
    active_norm: List[SkillDef],
    active_maj: List[SkillDef],
    zero_cast_defs: List[SkillDef],
    metas: Dict[str, SkillMeta],
    waves: List[WaveRecord],
    dangers: List[Dict[str, Any]],
    cleanse_lines: List[str],
    imm_lines: List[str],
    dispel_lines: List[str],
    wh_info: Dict[int, Dict[str, Any]],
) -> str:
    n_runs = len(packs)
    trash_durs = [sum(p.dur for p in pk.pulls) / 1000.0 for pk in packs]
    med_dur = statistics.median(trash_durs)
    med_pulls = statistics.median([len(pk.pulls) for pk in packs])
    med_hp = statistics.median([pk.max_hp for pk in packs if pk.max_hp > 0]) if any(pk.max_hp > 0 for pk in packs) else 0.0
    levels = Counter(pk.sample.level for pk in packs)
    lv_str = " / ".join(f"+{lv}×{c}" for lv, c in sorted(levels.items(), reverse=True))

    out: List[str] = []
    out.append(f"# {meta_runs.get('dungeon')} · 全本小怪（非 Boss）· {cls_name} 极简五维诊断")
    out.append(
        f"> 样本：{n_runs} 场高分限时（{lv_str}）| 小怪中位总时长 {fmt.clock(med_dur * 1000)}（中位 {med_pulls:.0f} 波）"
        f"| {cls_name}中位血量 {fmt.num(med_hp)}"
    )

    by_skill: Dict[str, List[WaveRecord]] = defaultdict(list)
    for w in waves:
        by_skill[w.skill_key].append(w)

    # 按威胁度选出 Top 15 小怪关键技（高伤 / 致死 / 高频命中 / 免疫交互）
    scored: List[Tuple[float, str]] = []
    for key, ws in by_skill.items():
        hits = [w for w in ws if w.outcome == "hit"]
        imm = [w for w in ws if w.outcome == "immune"]
        if not hits and not imm:
            continue
        bare = [w for w in hits if not w.active_defs and not w.passive_defs and not w.ext_buffs]
        sample_h = bare or hits
        med_d = statistics.median([w.total_dmg + w.total_abs for w in sample_h]) if sample_h else 0.0
        n_dead = sum(1 for w in hits if w.died)
        n_low = sum(1 for w in hits if w.min_hp_pct is not None and w.min_hp_pct < 25.0)
        # 过滤极低伤害且无危险/无 debuff 的纯蚊子腿
        if med_d < (med_hp * 0.10 if med_hp else 100_000) and n_dead == 0 and n_low == 0 and not imm and len(hits) < 8:
            continue
        score = med_d + n_dead * 3_000_000 + n_low * 600_000 + len(hits) * 40_000 + len(imm) * 300_000
        scored.append((score, key))
    scored.sort(reverse=True)
    top_keys = [k for _, k in scored[:15]]

    # ---- ① 高频致死/高伤小怪技速览 ----
    out.append("\n## ① 高频致死 / 高伤小怪技速览（按「怪物名 · 威胁技能」聚合）")
    for key in top_keys:
        ws = by_skill[key]
        m = metas[key]
        ids_all = sorted(m.cast_ids | m.dmg_ids | m.debuff_ids)
        id_str = "/".join(str(x) for x in ids_all[:3])
        hits = [w for w in ws if w.outcome == "hit"]
        pure_bare = [w for w in hits if not w.active_defs and not w.passive_defs and not w.ext_buffs]
        sample_h = pure_bare or hits
        imm_cnt = sum(1 for w in ws if w.outcome == "immune")
        dodge_cnt = sum(1 for w in ws if w.outcome == "dodged")
        n_dead = sum(1 for w in hits if w.died)
        if sample_h:
            dmg_med = statistics.median([w.total_dmg + w.total_abs for w in sample_h])
            dmg_pct = (100.0 * dmg_med / med_hp) if med_hp else 0.0
            tick_med = statistics.median([len(w.hits) for w in sample_h])
            tick_tag = f"({tick_med:.0f}跳合)" if tick_med >= 1.8 else ""
            dmg_str = (
                f"纯裸吃中位 {fmt.num(dmg_med)} ({dmg_pct:.0f}%HP){tick_tag}"
                if pure_bare else f"有覆盖中位 {fmt.num(dmg_med)} ({dmg_pct:.0f}%HP){tick_tag}"
            )
        else:
            dmg_str = "0直接掉血(Debuff/免疫)"
        tag_dot = "DoT" if m.is_dot else ("Debuff" if m.debuff_ids else "直伤")
        dead_tag = f" | **2s内死{n_dead}次**" if n_dead else ""
        wh_desc = ""
        for gid in sorted(m.dmg_ids) + sorted(m.cast_ids):
            if gid in wh_info and wh_info[gid].get("description"):
                dtxt = wh_info[gid]["description"].replace("\n", " ")
                wh_desc = dtxt[:46] + ("…" if len(dtxt) > 46 else "")
                break
        out.append(
            f"- **{key}**（ID:{id_str}，{tag_dot}）：{dmg_str} | "
            f"中{len(hits)} / 免疫{imm_cnt} / 未中{dodge_cnt}（覆盖{len({w.sample_tag for w in hits + [x for x in ws if x.outcome == 'immune']})}/{n_runs}场）"
            f"{dead_tag}" + (f" — *{wh_desc}*" if wh_desc else "")
        )

    # ---- ② 小怪手牌与控断预算账 ----
    out.append("\n## ② 小怪手牌与控断预算账")
    for sk in defs:
        st = cd_stats[sk.cast]
        tier_tag = "常规" if sk.tier == "normal" else "大牌"
        zero_tag = " 【全本0次主动施放，已排除分母（被动盾归入其他覆盖）】" if st["total_dungeon_casts"] == 0 else ""
        out.append(
            f"- **{sk.name}**（{tier_tag}）：实际CD {st['cd_note']} | "
            f"小怪场均 {st['avg_boss_casts']:.2f}次（共{st['total_boss_casts']}次，{st['used_boss_runs']}/{n_runs}场；全本共{st['total_dungeon_casts']}次）{zero_tag}"
        )
    util_parts: List[str] = []
    for sk in utils:
        st = cd_stats[sk.cast]
        if st["total_boss_casts"] > 0:
            util_parts.append(f"{sk.name} {st['avg_boss_casts']:.2f}次/场(共{st['total_boss_casts']}次,{st['used_boss_runs']}/{n_runs}场)")
    if util_parts:
        out.append("- 功能/应急/控断牌（小怪战）：" + " | ".join(util_parts))

    # 统计小怪战打断目标明细
    int_cnt: Counter[str] = Counter()
    tot_ints = 0
    for pack in packs:
        for e in pack.interrupts:
            if e.get("type") == "interrupt":
                ex = int(e.get("extraAbilityGameID") or 0)
                if ex:
                    tot_ints += 1
                    tgt_nm = pack.run.actor_name(e.get("targetID"))
                    int_cnt[f"{tgt_nm}:{pack.run.ab(ex)}({ex})"] += 1
    if tot_ints:
        top_int = " | ".join(f"`{k}` ×{v}" for k, v in int_cnt.most_common(6))
        out.append(f"- 打断实锤（共 {tot_ints} 次，场均 {tot_ints / n_runs:.1f} 次）：{top_int}")

    # ---- ③ 正例 vs 反例对照（Top 12 高危小怪技）----
    out.append("\n## ③ 正例 vs 反例对照（Top 12 高威胁小怪技，含被动盾与外减隔离 + WCL 锚点）")

    def summarize_group(label: str, grp: List[WaveRecord], show_rescue: bool = False) -> str:
        if not grp:
            return f"  - {label}：0次"
        s_hps = [w.start_hp_pct for w in grp if w.start_hp_pct is not None]
        e_hps = [w.min_hp_pct for w in grp if w.min_hp_pct is not None]
        ov = sum(1 for w in grp if w.overlap_other_dmg > 0)
        died = sum(1 for w in grp if w.died)
        imm = sum(1 for w in grp if w.outcome == "immune")
        sh_s = f"起手{med(s_hps):.0f}%(低{min(s_hps):.0f}%)" if s_hps else "起手—"
        eh_s = f"剩血{med(e_hps):.0f}%(低{min(e_hps):.0f}%)" if e_hps else "剩血—"
        extra = []
        if imm:
            extra.append(f"免疫{imm}次")
        if died:
            extra.append(f"**2s内死{died}次**")
        if ov:
            extra.append(f"叠伤{ov}/{len(grp)}")
        if show_rescue:
            low_grp = sorted([w for w in grp if w.min_hp_pct is not None], key=lambda x: x.min_hp_pct or 100.0)
            if low_grp:
                w0 = low_grp[0]
                notes = []
                if w0.total_abs > 0 and med_hp and w0.total_abs >= med_hp * 0.12:
                    notes.append(f"盾吸{fmt.num(w0.total_abs)}")
                r_str = ("[" + ",".join(notes) + "]") if notes else "[无外减]"
                ref_link = wcl_ref(w0.sample_tag, w0.pull, w0.run, w0.wave_ts, use_run_clock=True)
                extra.append(f"最危:{ref_link} ({pct_str(w0.start_hp_pct)}→{pct_str(w0.min_hp_pct)}{r_str})")
        return f"  - {label}：{len(grp)}次 | {sh_s} → {eh_s}" + (f" | {'，'.join(extra)}" if extra else "")

    for key in top_keys[:12]:
        ws = by_skill[key]
        hits_and_imm = [w for w in ws if w.outcome in ("hit", "immune")]
        if not hits_and_imm:
            continue
        dodged = [w for w in ws if w.outcome == "dodged"]
        pos_norm = [w for w in hits_and_imm if w.active_normal and not w.active_major]
        pos_maj = [w for w in hits_and_imm if w.active_major]
        no_act = [w for w in hits_and_imm if not w.active_defs]
        other_cov = [w for w in no_act if w.passive_defs or w.ext_buffs]
        pure_bare = [w for w in no_act if not w.passive_defs and not w.ext_buffs]
        neg_ready = [w for w in pure_bare if w.ready_normal]
        neg_cd = [w for w in pure_bare if not w.ready_normal]

        out.append(f"- **{key}**（中/免疫{len(hits_and_imm)}，未中{len(dodged)}）")
        if pos_norm:
            sub = Counter("+".join(w.active_normal) for w in pos_norm)
            out.append(summarize_group("正例·常规(" + "/".join(f"{k}×{v}" for k, v in sub.most_common()) + ")", pos_norm))
        if pos_maj:
            sub = Counter("+".join(w.active_defs) for w in pos_maj)
            out.append(summarize_group("正例·大牌(" + "/".join(f"{k}×{v}" for k, v in sub.most_common()) + ")", pos_maj))
        if other_cov:
            sub = Counter("+".join(w.passive_defs + w.ext_buffs) for w in other_cov)
            out.append(summarize_group("其他覆盖(" + "/".join(f"{k}×{v}" for k, v in sub.most_common(4)) + ")", other_cov))
        out.append(summarize_group("反例A·纯裸吃就绪未交", neg_ready, show_rescue=True))
        if neg_cd:
            out.append(summarize_group("反例B·纯裸吃CD未交", neg_cd, show_rescue=True))

    # ---- ④ 小怪死点 & 残血(<20%) 前 5 秒连招 ----
    out.append("\n## ④ 小怪死点 & 残血（<20% HP）前 5 秒连招")
    n_dead = sum(1 for d in dangers if d["kind"] == "死亡")
    n_low = sum(1 for d in dangers if d["kind"] == "残血")
    out.append(f"- 总计：**死亡 {n_dead} 次 / 残血(<20%) {n_low} 次**（覆盖 {n_runs} 场）")
    if dangers:
        pat_cnt = Counter(d["pattern"] for d in dangers)
        out.append("- 高频连招模式：" + " | ".join(f"`{k}` ×{v}" for k, v in pat_cnt.most_common(6)))
        ordered = sorted(dangers, key=lambda x: (0 if x["kind"] == "死亡" else 1, x["hp_pct"]))
        for d in ordered[:12]:
            cov = d["active"] + [f"被动:{x}" for x in d["passive"]] + [f"外减:{x}" for x in d["ext"]]
            st_def = f"身上:{'+'.join(cov)}" if cov else "纯裸吃"
            rd_parts = []
            if d["ready_norm"]:
                rd_parts.append("常规就绪:" + "/".join(d["ready_norm"]))
            if d["ready_maj"]:
                rd_parts.append("大牌就绪:" + "/".join(d["ready_maj"]))
            rd_str = "，".join(rd_parts) if rd_parts else "无牌就绪"
            out.append(
                f"  - {d['ref_md']} {d['player']} **{d['kind']}({d['hp_pct']:.0f}%)** "
                f"[{st_def} | {rd_str}]：{d['combo']}"
            )

    # ---- ⑤ 免疫 / 清除 / 自由解控 / 清毒驱散实锤 ----
    out.append("\n## ⑤ 免疫 / 清除 / 解控 / 驱散交互实锤")
    if dispel_lines:
        out.extend(dispel_lines)
    else:
        out.append(f"- 驱散实锤：{n_runs} 场小怪战未检测到玩家主动驱散。")
    if cleanse_lines:
        out.extend(cleanse_lines)
    else:
        out.append(f"- 清除/解控实锤：{n_runs} 场小怪战未检测到提前清除敌方 Debuff 的实锤。")
    if imm_lines:
        out.extend(imm_lines[:15])
    else:
        out.append(f"- 免疫实锤：{n_runs} 场小怪战未检测到免疫大牌期间的直接伤害交互事件。")

    return "\n".join(out)


def cmd_trash(client: Client, args: argparse.Namespace) -> str:
    (
        meta_runs, cls_name, packs, defs, utils, eff_cd, cd_stats,
        active_norm, active_maj, zero_cast_defs, metas, waves, hp_is_post,
    ) = run_trash_load(client, Path(args.runs), Path(args.cls))

    wh_ids: Set[int] = set()
    for m in metas.values():
        wh_ids |= m.dmg_ids | m.debuff_ids
    wh_info = wowhead.spells(wh_ids, lang="zh") if not args.no_wowhead else {}

    dangers = detect_dangers(packs, active_norm, active_maj, zero_cast_defs, eff_cd, hp_is_post, use_run_clock=True)
    cleanse_skills = [s for s in defs + utils if s.cleanse_immune]
    major_skills = [s for s in defs if s.tier == "major"]
    cleanse_lines, imm_lines = detect_interactions(packs, cleanse_skills, major_skills, wh_info, use_run_clock=True)
    dispel_lines = detect_player_dispels(packs, use_run_clock=True)

    return format_trash_screen(
        meta_runs, cls_name, packs, defs, utils, eff_cd, cd_stats,
        active_norm, active_maj, zero_cast_defs, metas, waves,
        dangers, cleanse_lines, imm_lines, dispel_lines, wh_info,
    )


# ============================================================================
# 子命令 3：inspect（双向反查，逐条输出指定技能的 15 场原始受击明细，支持 --boss / --trash）
# ============================================================================

def cmd_inspect(client: Client, args: argparse.Namespace) -> str:
    if not args.trash and not args.boss:
        raise WCLError("inspect 需要指定 --boss <序号/名称> 或 --trash。")
    if args.trash:
        (
            _meta_runs, _cls_name, _packs, _defs, _utils, _eff_cd, _cd_stats,
            _active_norm, _active_maj, _zero_cast_defs, metas, waves, _hp_is_post,
        ) = run_trash_load(client, Path(args.runs), Path(args.cls))
    else:
        (
            _meta_runs, _cls_name, _packs, _defs, _utils, _eff_cd, _cd_stats,
            _active_norm, _active_maj, _zero_cast_defs, metas, waves, _hp_is_post,
        ) = run_boss_load(client, Path(args.runs), Path(args.cls), args.boss)

    q = args.ability.strip().lower()
    matched_waves: List[WaveRecord] = []
    for w in waves:
        ids = w.cast_ids | w.dmg_ids
        if (q.isdigit() and int(q) in ids) or (q in w.skill_key.lower()) or (q in w.skill_name.lower()):
            if args.only_hit and w.outcome == "dodged":
                continue
            if args.only_bare and (w.outcome != "hit" or w.active_defs or w.passive_defs or w.ext_buffs):
                continue
            matched_waves.append(w)

    if not matched_waves:
        return f"未找到匹配 '{args.ability}' 的波次（可选技能示例：{'、'.join(sorted(metas)[:25])}）。"

    matched_waves.sort(key=lambda w: (w.min_hp_pct if w.min_hp_pct is not None else 999.0, -w.total_dmg))
    scope = "全本小怪" if args.trash else f"Boss {args.boss}"
    lines = [f"# 双向反查明细（{scope}）：{args.ability}（共 {len(matched_waves)} 条，按最低剩血升序）"]
    rows = []
    for w in matched_waves[: args.limit]:
        hp_s = f"{pct_str(w.start_hp_pct)}→{pct_str(w.min_hp_pct)}"
        dmg_s = fmt.num(w.total_dmg) + (f"(吸{fmt.num(w.total_abs)})" if w.total_abs > 0 else "")
        cov = w.active_defs + [f"被动:{x}" for x in w.passive_defs] + [f"外减:{x}" for x in w.ext_buffs]
        def_s = "+".join(cov) if cov else "纯裸吃"
        rd_s = "/".join(w.ready_normal + [f"*{x}" for x in w.ready_major]) or "全CD"
        ov_s = f"{fmt.num(w.overlap_other_dmg)}({'+'.join(w.overlap_skills[:2])})" if w.overlap_other_dmg > 0 else "无"
        heal_s = fmt.num(w.window_heal) if w.window_heal > 0 else "—"
        rows.append([
            wcl_ref(w.sample_tag, w.pull, w.run, w.wave_ts, use_run_clock=bool(args.trash)),
            w.player_name,
            w.skill_key,
            w.outcome + ("(死)" if w.died else ""),
            f"{w.party_hit_count}/{w.party_debuff_count}",
            dmg_s,
            hp_s,
            def_s,
            rd_s,
            ov_s,
            heal_s,
        ])
    lines.append(fmt.table(
        ["样本@时间", "玩家", "技能键", "状态", "队中/deb", "伤害", "起手→剩血", "减伤/其他覆盖", "就绪牌(*大牌)", "±2s叠伤", "窗内抬血"],
        rows,
    ))
    return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="大秘境 DPS 极简五维诊断脚本（v3）")
    p.add_argument("--api", choices=["auto", "v1", "v2"], default=None)
    p.add_argument("--refresh", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sample", help="抽样固化 12-15 场高分限时样本")
    sp.add_argument("--dungeon", required=True, help="副本名，如 塞塔里斯")
    sp.add_argument("--class", dest="cls", required=True, help="职业专精，如 惩戒骑")
    sp.add_argument("--levels", default="24,23", help="逗号分隔的层数优先级，默认 24,23")
    sp.add_argument("--want", type=int, default=15, help="目标样本数，默认 15")
    sp.add_argument("--out", required=True, help="输出 runs.json 路径")

    bp = sub.add_parser("boss", help="单 Boss 一屏 5 维诊断")
    bp.add_argument("--runs", required=True, help="runs.json 路径")
    bp.add_argument("--class", dest="cls", required=True, help="职业配置 JSON 路径")
    bp.add_argument("--boss", required=True, help="Boss 序号(1-4) / encounterID / 名称片段")
    bp.add_argument("--no-wowhead", action="store_true", help="跳过 Wowhead 说明查询")

    tp = sub.add_parser("trash", help="全本非 Boss 小怪按「怪物名 + 威胁技能」聚合五维诊断")
    tp.add_argument("--runs", required=True, help="runs.json 路径")
    tp.add_argument("--class", dest="cls", required=True, help="职业配置 JSON 路径")
    tp.add_argument("--no-wowhead", action="store_true", help="跳过 Wowhead 说明查询")

    ip = sub.add_parser("inspect", help="按敌方技能输出逐条受击明细（双向反查证伪用）")
    ip.add_argument("--runs", required=True)
    ip.add_argument("--class", dest="cls", required=True)
    ip.add_argument("--boss", help="Boss 序号(1-4) / encounterID / 名称片段（与 --trash 二选一）")
    ip.add_argument("--trash", action="store_true", help="反查全本非 Boss 小怪战斗")
    ip.add_argument("--ability", required=True, help="技能 ID、技能名或小怪名称片段")
    ip.add_argument("--only-hit", action="store_true", help="只看命中/免疫，隐藏未命中")
    ip.add_argument("--only-bare", action="store_true", help="只看纯裸吃命中")
    ip.add_argument("--limit", type=int, default=60)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    client = Client(api_version=args.api, refresh=args.refresh)
    try:
        if args.cmd == "sample":
            out = cmd_sample(client, args)
        elif args.cmd == "boss":
            out = cmd_boss(client, args)
        elif args.cmd == "trash":
            out = cmd_trash(client, args)
        elif args.cmd == "inspect":
            out = cmd_inspect(client, args)
        else:
            raise WCLError(f"未知命令：{args.cmd}")
    except WCLError as exc:
        stderr(f"错误：{exc}")
        return 2
    sys.stdout.write(out.rstrip() + "\n")
    sys.stdout.flush()
    if client.live or client.cached:
        stderr(f"— {client.footer()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
