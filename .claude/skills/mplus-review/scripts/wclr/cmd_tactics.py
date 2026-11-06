"""tactics 命令：玩家在常规输出循环之外用了哪些技能、什么时候用、在应对什么。

思路：
  1. 选出每名玩家的"额外技能"——已知功能技能（catalog），或低频且几乎不贡献伤害/治疗的施法。
  2. 还原每一次使用的情境：作用对象身上的敌方减益、前后几秒的敌方读条/施放、刚刚被什么打中、血线。
  3. 记录使用后的直接效果：减益被驱散/提前消失、随后免疫或反射了哪些敌方技能。
  4. 汇总：同一技能多次使用时反复伴随的敌方机制（与随机时刻相比的倍数），以及每个敌方机制被哪些技能应对。
所有时间戳为报告相对毫秒。
"""
from __future__ import annotations

import bisect
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import catalog, data, fmt
from .api import WCLError
from .context import Run

# ---------------------------------------------------------------- 参数
CAST_BEFORE = 4000     # 使用前多久内的敌方读条/施放算"情境"
CAST_AFTER = 2000      # 使用后多久内的敌方施放算"预判"
HIT_BEFORE = 3000      # 使用前多久内被打中算"刚被击中"
APPLY_AFTER = 2000     # 使用后多久内上身的减益算"预判"
REMOVE_LO, REMOVE_HI = -100, 400   # 减益在使用后这个窗口内消失，算"随后消失"
DISPEL_MATCH = 300     # 驱散事件与施法的匹配容差
IMMUNE_WINDOW = 12000  # 免疫/反射命中归因到此前多久内的使用
EARLY_RATIO = 0.85     # 持续时间短于"完整持续"的这个比例，算提前消失
DEATH_SLACK = 500
SYNC_END = 300         # 多名玩家在这个间隔内同时失去同一减益，视为机制自己结束，不归因给玩家
GROUP_WINDOW = 2000    # 多名玩家在这个间隔内都用了保命/免疫类技能，算"团队同时应对"
GROUP_MIN_PLAYERS = 3
AFTER_HITS = 6000      # 使用后多久内受到的敌方技能命中（用来看"是否真的被打到"）
GROUP_EFFECT_CATS = {"免疫", "反射", "减伤", "外部减伤", "团队减伤", "自解", "解控"}
MAX_CPM = 1.5          # 未分类技能：CPM 不高于此值
MAX_DMG_SHARE = 0.02   # 未分类技能：伤害占比低于此值
MAX_HEAL_SHARE = 0.04  # 未分类技能：治疗占比低于此值
MIN_LIFT = 2.5          # 伴随倍数下限
MAX_P = 0.02            # 伴随的泊松检验 p 值上限（每个技能×机制组合单独检验，未做多重比较校正）
STRONG_P = 0.002        # 只有伴随、没有直接效果时，进入"敌方机制"表的门槛
OPENER_WINDOW = 6000    # 开怪后多久内使用算"开怪"
OPENER_SHARE = 0.6      # 未分类技能超过这个比例在开怪时使用，推测为开怪爆发
NOISE_CATS = {"爆发", "伤害", "治疗", "开怪爆发", "消耗品", "战复", "副本效果", "增益", "饰品"}   # 没有直接效果时不展开
DUNGEON_CLASSES = 3     # 不在分类表里、却被至少这么多个不同职业施放的技能，视为副本道具/特殊按钮
COMBO_WINDOW = 5000     # 同一玩家先后使用两个额外技能的间隔不超过此值，算"连用"
REMOVER_CATS = {"自解", "免疫", "驱散", "解控", "外部减伤"}  # 已知可能移除减益的技能：单次推断也保留
MIN_INFER_REPEAT, MIN_INFER_PRECISION = 2, 0.5        # 其他技能：至少 2 次、且身上有该减益时一半以上都随后消失
BLOCK_TIERS = {"免疫": 2, "反射": 2, "解控": 2, "自解": 2, "减伤": 1, "外部减伤": 1, "团队减伤": 1}
HIT_TYPES = {10: "免疫", 9: "反射"}
GROUP_CATS = {"团队减伤", "驱散", "解控"}


# ---------------------------------------------------------------- 数据结构
@dataclass
class Aura:
    gid: int
    target: int
    start: float
    end: float
    reason: str = "自然结束"          # 自然结束 / 驱散 / 提前消失 / 死亡 / 战斗结束
    by: Optional[Tuple[int, int]] = None  # (玩家, 技能)：驱散者或推断的消除者
    inferred: bool = False

    @property
    def dur(self) -> float:
        return self.end - self.start


@dataclass
class Use:
    player: int
    gid: int
    ts: float
    target: Optional[int]          # 施法目标（我方玩家）；None = 自身/无目标
    subject: int                   # 情境看谁：队友目标，否则施法者自己
    group: bool
    hp: Optional[float] = None     # 作用对象使用前的血量 %
    dmg_pct: float = 0.0           # 使用前 3 秒承伤 / 最大生命
    active: List[int] = field(default_factory=list)       # 作用对象身上的敌方减益
    applied_after: List[int] = field(default_factory=list)
    hits: Counter = field(default_factory=Counter)        # 使用前 3 秒被打中的敌方技能 -> 次数
    before: List[Tuple[float, int, str]] = field(default_factory=list)  # (相对秒, 技能, 读条/施放) 使用前
    after: List[Tuple[float, int, str]] = field(default_factory=list)   # 使用后
    removed: List[Tuple[int, int, bool]] = field(default_factory=list)  # (减益, 对象, 是否为推断)
    blocked: Counter = field(default_factory=Counter)     # (命中类型, 敌方技能) -> 次数
    after_hits: Counter = field(default_factory=Counter)  # 使用后 6 秒内作用对象受到的敌方技能命中（不含近战）


@dataclass
class Result:
    uses: List[Use]
    auras: List[Aura]
    extra: Dict[Tuple[int, int], Dict[str, Any]]           # (玩家, 技能) -> {cat, n, cpm, dmg, heal}
    skipped: Dict[int, List[Tuple[int, int]]]              # 玩家 -> [(技能, 次数)] 打断等不展开的
    unmatched_dispels: Counter                              # (玩家, 驱散技能, 减益) -> 次数
    blocks_unattributed: Counter                            # (对象, 命中类型, 敌方技能) -> 次数
    assoc: Dict[Tuple[int, int], List[Dict[str, Any]]]     # (玩家, 技能) -> 关联机制
    full_dur: Dict[int, float]
    combat_ms: float
    combos: Dict[int, List[Tuple[int, int, int, float, int]]] = field(default_factory=dict)  # 玩家 -> [(A, B, 次数, 中位间隔, 其中先B后A)]
    groups: List[Dict[str, Any]] = field(default_factory=list)   # 团队同时应对
    enemy_ids: Dict[str, Set[int]] = field(default_factory=dict) # 敌方技能名 -> 出现过的 ID（读条/减益/伤害）


# ---------------------------------------------------------------- 工具
def _merge(spans: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    out: List[List[float]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _overlap(spans: List[Tuple[float, float]], combat: List[Tuple[float, float]]) -> float:
    total = 0.0
    for a, b in spans:
        for c, d in combat:
            if d <= a:
                continue
            if c >= b:
                break
            total += min(b, d) - max(a, c)
    return total


def _quantile(values: Sequence[float], q: float) -> float:
    vals = sorted(values)
    if not vals:
        return 0.0
    idx = min(len(vals) - 1, max(0, int(math.ceil(q * len(vals))) - 1))
    return vals[idx]


def poisson_tail(k: int, lam: float) -> float:
    """P(X >= k)，X ~ Poisson(lam)。"""
    if k <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    term = math.exp(-lam)
    cdf = term
    for i in range(1, k):
        term *= lam / i
        cdf += term
    return max(0.0, 1.0 - cdf)


def _ability_shares(tbl: Dict[str, Any], run: Run) -> Dict[Tuple[int, int], float]:
    """伤害/治疗表 -> {(玩家, 技能): 占该玩家总量的比例}。"""
    out: Dict[Tuple[int, int], float] = {}
    for entry in tbl.get("entries") or []:
        pid = entry.get("id")
        if pid not in run.players:
            continue
        total = float(entry.get("total") or 0)
        if total <= 0:
            continue
        for ab in entry.get("abilities") or []:
            gid = int(ab.get("guid") or 0)
            if gid:
                out[(pid, gid)] = out.get((pid, gid), 0.0) + float(ab.get("total") or 0) / total
    return out


# ---------------------------------------------------------------- 分析
def build_auras(run: Run, debuffs: Iterable[Dict[str, Any]], dispels: Iterable[Dict[str, Any]],
                deaths: Dict[int, List[float]], known_dur: Optional[Dict[int, float]] = None
                ) -> Tuple[List[Aura], Dict[int, float]]:
    """把敌方施加给玩家的减益配对成区间，并标出结束方式。

    驱散 / 死亡 / 同时结束（多名玩家同一时刻失去同一减益：机制自己的循环）/ 提前消失 / 自然结束。
    完整持续 = 未被驱散、未随死亡消失的那些的 90 分位；Wowhead 给出的持续时间更长时以它为准。
    """
    opened: Dict[Tuple[Any, ...], float] = {}
    auras: List[Aura] = []
    for e in sorted(debuffs, key=lambda x: x.get("timestamp") or 0):
        tgt = e.get("targetID")
        if tgt not in run.players or run.owner(e.get("sourceID")) is not None:
            continue  # 只看敌方（或环境）施加给玩家的减益
        key = (e.get("abilityGameID"), tgt, e.get("sourceID"), e.get("sourceInstance"))
        typ = e.get("type")
        if typ == "applydebuff":
            opened.setdefault(key, e["timestamp"])
        elif typ in ("refreshdebuff", "applydebuffstack") and key not in opened:
            opened[key] = e["timestamp"]
        elif typ == "removedebuff":
            st = opened.pop(key, None)
            if st is not None:
                auras.append(Aura(int(e["abilityGameID"]), tgt, st, e["timestamp"]))
    for (gid, tgt, _s, _i), st in opened.items():
        auras.append(Aura(int(gid), tgt, st, run.end, reason="战斗结束"))
    disp = [e for e in dispels if e.get("type") == "dispel" and not e.get("isBuff")]
    for a in auras:
        if a.reason == "战斗结束":
            continue
        for e in disp:
            if (e.get("targetID") == a.target and int(e.get("extraAbilityGameID") or 0) == a.gid
                    and abs(e["timestamp"] - a.end) <= 200):
                owner = run.owner(e.get("sourceID"))
                a.reason, a.by = "驱散", (owner if owner is not None else -1, int(e.get("abilityGameID") or 0))
                break
        else:
            if any(abs(t - a.end) <= DEATH_SLACK for t in deaths.get(a.target, [])):
                a.reason = "死亡"
    durs: Dict[int, List[float]] = defaultdict(list)
    for a in auras:
        if a.reason == "自然结束":
            durs[a.gid].append(a.dur)
    full = {gid: _quantile(ds, 0.9) for gid, ds in durs.items()}
    for gid, ms in (known_dur or {}).items():
        if ms and ms > full.get(gid, 0):
            full[gid] = ms
    ends: Dict[int, List[Tuple[float, int]]] = defaultdict(list)
    for a in auras:
        if a.reason == "自然结束":
            ends[a.gid].append((a.end, a.target))
    for a in auras:
        if a.reason != "自然结束" or not full.get(a.gid) or a.dur >= EARLY_RATIO * full[a.gid]:
            continue
        if any(t != a.target and abs(e - a.end) <= SYNC_END for e, t in ends[a.gid]):
            a.reason = "同时结束"
        else:
            a.reason = "提前消失"
    return auras, full


def _synchronized(stamps: List[Tuple[float, int]], players: int) -> bool:
    """几乎每次都是全队（≥ 4 人或全员）在 0.5 秒内同时"施放"：由副本施加，不是玩家按的。"""
    need = max(2, min(4, players))
    stamps = sorted(stamps)
    ts = [t for t, _p in stamps]
    synced = 0
    for t, _p in stamps:
        lo, hi = bisect.bisect_left(ts, t - 500), bisect.bisect_right(ts, t + 500)
        if len({p for _t, p in stamps[lo:hi]}) >= need:
            synced += 1
    return bool(stamps) and synced >= 0.8 * len(stamps)


def select_extra(run: Run, casts: Iterable[Dict[str, Any]], dd: Dict[str, Any], heal: Dict[str, Any],
                 combat_ms: float, classify: Optional[Callable[[List[int]], Dict[int, str]]] = None
                 ) -> Tuple[Dict[Tuple[int, int], Dict[str, Any]], Dict[int, List[Tuple[int, int]]]]:
    counts: Counter = Counter()
    openers: Counter = Counter()
    classes: Dict[int, Set[str]] = defaultdict(set)
    stamps: Dict[int, List[Tuple[float, int]]] = defaultdict(list)
    starts = sorted(p.start for p in run.pulls)
    for e in casts:
        if e.get("type") != "cast":
            continue
        owner = run.owner(e.get("sourceID"))
        gid = int(e.get("abilityGameID") or 0)
        if owner is None or gid <= 1:
            continue
        counts[(owner, gid)] += 1
        classes[gid].add(run.players[owner].cls)
        stamps[gid].append((e["timestamp"], owner))
        i = bisect.bisect_right(starts, e["timestamp"]) - 1
        if i >= 0 and e["timestamp"] - starts[i] <= OPENER_WINDOW:
            openers[(owner, gid)] += 1
    dmg = _ability_shares(dd, run)
    hl = _ability_shares(heal, run)
    minutes = max(combat_ms / 60000.0, 1e-6)
    extra: Dict[Tuple[int, int], Dict[str, Any]] = {}
    skipped: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
    for (pid, gid), n in counts.items():
        cat = catalog.category(gid, run.ab(gid))
        cpm = n / minutes
        info = {"cat": cat, "n": n, "cpm": cpm, "dmg": dmg.get((pid, gid), 0.0), "heal": hl.get((pid, gid), 0.0)}
        if cat == "打断":
            skipped[pid].append((gid, n))
            continue
        if cat is None and not (cpm <= MAX_CPM and info["dmg"] < MAX_DMG_SHARE and info["heal"] < MAX_HEAL_SHARE):
            continue
        info["opener"] = openers[(pid, gid)] / n
        extra[(pid, gid)] = info
    for (pid, gid), x in extra.items():
        if x["cat"] is None and len(classes[gid]) >= DUNGEON_CLASSES:
            x["cat"], x["auto"] = ("副本效果" if _synchronized(stamps[gid], len(run.players)) else "副本按钮"), True
    unknown = sorted({gid for (_p, gid), x in extra.items() if x["cat"] in (None, "副本按钮")})
    auto = classify(unknown) if (classify and unknown) else {}
    for (pid, gid), x in extra.items():
        if x["cat"] == "副本按钮" and auto.get(gid) in ("消耗品", "饰品"):
            x["cat"] = auto[gid]  # 多个职业都用的药水/饰品，不是副本按钮
        elif x["cat"] is None and auto.get(gid):
            x["cat"], x["auto"] = auto[gid], True
        elif x["cat"] is None and x["n"] >= 3 and x["opener"] >= OPENER_SHARE:
            x["cat"], x["auto"] = "开怪爆发", True
    return extra, dict(skipped)


def analyze(run: Run, ev: Dict[str, Any], classify: Optional[Callable[[List[int]], Dict[int, str]]] = None,
            known_dur: Optional[Dict[int, float]] = None) -> Result:
    """ev: casts / ecasts / debuffs / dispels / taken（事件列表），dd / heal（表格），deaths（玩家 -> 死亡时间列表）。"""
    combat = _merge([(p.start, p.end) for p in run.pulls]) or [(run.start, run.end)]
    combat_ms = sum(b - a for a, b in combat)
    deaths: Dict[int, List[float]] = ev.get("deaths") or {}
    auras, full = build_auras(run, ev.get("debuffs") or [], ev.get("dispels") or [], deaths, known_dur)
    extra, skipped = select_extra(run, ev.get("casts") or [], ev.get("dd") or {}, ev.get("heal") or {}, combat_ms,
                                  classify)
    friendly_gids = {int(e.get("abilityGameID") or 0) for e in ev.get("casts") or []}
    friendly_names = {run.ab(g) for g in friendly_gids}

    # ---- 敌方读条/施放
    enemy: List[Tuple[float, int, str, Optional[int]]] = []
    for e in ev.get("ecasts") or []:
        if run.owner(e.get("sourceID")) is not None or e.get("sourceID") in run.players:
            continue
        gid = int(e.get("abilityGameID") or 0)
        if gid <= 1 or gid in friendly_gids or run.ab(gid) in friendly_names:
            continue  # 我方召唤物（图腾、领域等）有时被记成敌对来源
        enemy.append((e["timestamp"], gid, "读条" if e.get("type") == "begincast" else "施放", e.get("targetID")))
    enemy.sort()
    enemy_ts = [x[0] for x in enemy]

    # ---- 承伤（含血量）
    taken: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for e in ev.get("taken") or []:
        if e.get("type") == "damage" and e.get("targetID") in run.players:
            taken[e["targetID"]].append(e)
    for lst in taken.values():
        lst.sort(key=lambda x: x["timestamp"])
    taken_ts = {pid: [x["timestamp"] for x in lst] for pid, lst in taken.items()}

    by_target: Dict[int, List[Aura]] = defaultdict(list)
    for a in auras:
        by_target[a.target].append(a)

    def window(lo: float, hi: float) -> List[Tuple[float, int, str, Optional[int]]]:
        i = bisect.bisect_left(enemy_ts, lo)
        j = bisect.bisect_right(enemy_ts, hi)
        return enemy[i:j]

    # ---- 每一次使用
    uses: List[Use] = []
    for e in sorted(ev.get("casts") or [], key=lambda x: x.get("timestamp") or 0):
        if e.get("type") != "cast":
            continue
        pid = run.owner(e.get("sourceID"))
        gid = int(e.get("abilityGameID") or 0)
        if pid is None or (pid, gid) not in extra:
            continue
        ts = e["timestamp"]
        tgt = e.get("targetID")
        tgt = tgt if tgt in run.players and tgt != pid else None
        cat = extra[(pid, gid)]["cat"]
        u = Use(pid, gid, ts, tgt, tgt or pid, group=bool(catalog.is_group(gid) and cat in GROUP_CATS))
        subjects = list(run.players) if u.group else [u.subject]
        # 血量与承伤
        lst = taken.get(u.subject, [])
        lo = bisect.bisect_left(taken_ts.get(u.subject, []), ts - 8000)
        last = None
        for x in lst[lo:]:
            if x["timestamp"] > ts:
                break
            if x.get("maxHitPoints") and x.get("resourceActor", 2) == 2:
                last = x
            if x["timestamp"] >= ts - HIT_BEFORE and x.get("hitType") not in HIT_TYPES:
                amount = (x.get("amount") or 0) + (x.get("absorbed") or 0)
                if last and last.get("maxHitPoints"):
                    u.dmg_pct += amount / last["maxHitPoints"]
                if int(x.get("abilityGameID") or 0) > 0 and run.owner(x.get("sourceID")) is None:
                    u.hits[int(x["abilityGameID"])] += 1
        if last:
            u.hp = 100.0 * (last.get("hitPoints") or 0) / last["maxHitPoints"]
        hi = bisect.bisect_right(taken_ts.get(u.subject, []), ts)
        for x in lst[hi:]:
            if x["timestamp"] > ts + AFTER_HITS:
                break
            g = int(x.get("abilityGameID") or 0)
            if g > 1 and run.owner(x.get("sourceID")) is None:
                u.after_hits[g] += 1
        for s in subjects:
            for a in by_target.get(s, []):
                if a.start <= ts <= a.end and a.gid not in u.active:
                    u.active.append(a.gid)
                elif ts < a.start <= ts + APPLY_AFTER and a.gid not in u.applied_after:
                    u.applied_after.append(a.gid)
        for t, g, kind, _tg in window(ts - CAST_BEFORE, ts + CAST_AFTER):
            rec = (round((t - ts) / 1000.0, 1), g, kind)
            (u.before if t <= ts else u.after).append(rec)
        uses.append(u)

    # ---- 效果一：驱散事件直接匹配
    dispel_events = [e for e in ev.get("dispels") or [] if e.get("type") == "dispel" and not e.get("isBuff")
                     and e.get("targetID") in run.players]
    unmatched: Counter = Counter()
    by_player_uses: Dict[int, List[Use]] = defaultdict(list)
    for u in uses:
        by_player_uses[u.player].append(u)
    for e in dispel_events:
        owner = run.owner(e.get("sourceID"))
        dg = int(e.get("abilityGameID") or 0)
        rm = int(e.get("extraAbilityGameID") or 0)
        cand = [u for u in by_player_uses.get(owner, []) if u.gid == dg and abs(u.ts - e["timestamp"]) <= DISPEL_MATCH]
        if cand:
            u = min(cand, key=lambda x: abs(x.ts - e["timestamp"]))
            u.removed.append((rm, e["targetID"], False))
        elif owner is not None:
            unmatched[(owner, dg, rm)] += 1

    # ---- 效果二：减益提前消失，推断为附近的使用造成
    for a in auras:
        if a.reason != "提前消失":
            continue
        cand = [u for u in uses if (u.subject == a.target or u.group)
                and a.end - REMOVE_HI <= u.ts <= a.end - REMOVE_LO]
        if not cand:
            continue
        u = min(cand, key=lambda x: abs(a.end - x.ts - 50))
        u.removed.append((a.gid, a.target, True))
        a.by, a.inferred = (u.player, u.gid), True
    # 过滤偶然巧合：不是已知的移除类技能时，要求同一技能反复消除同一减益
    total: Counter = Counter()      # 推断消除的次数（一次使用同时消除多人算多次）
    hit_uses: Counter = Counter()   # 有推断消除的使用次数
    chances: Counter = Counter()    # 使用时该减益在身上（或被它消除）的使用次数
    for u in uses:
        removed = {g for g, _t, inf in u.removed if inf}
        for g in set(u.active) | removed:
            chances[(u.player, u.gid, g)] += 1
        for g, _t, inf in u.removed:
            if inf:
                total[(u.player, u.gid, g)] += 1
        for g in removed:
            hit_uses[(u.player, u.gid, g)] += 1
    weak = {k for k, n in total.items()
            if (extra[(k[0], k[1])]["cat"] or "") not in REMOVER_CATS
            and (n < MIN_INFER_REPEAT or hit_uses[k] < MIN_INFER_PRECISION * max(1, chances[k]))}
    if weak:
        for u in uses:
            u.removed = [r for r in u.removed if not (r[2] and (u.player, u.gid, r[0]) in weak)]
        for a in auras:
            if a.inferred and a.by and (a.by[0], a.by[1], a.gid) in weak:
                a.by, a.inferred = None, False

    # ---- 效果三：免疫/反射命中，归因到此前 12 秒内的使用（优先选"多次使用后都出现免疫"的技能）
    blocks = []
    for pid, lst in taken.items():
        for x in lst:
            ht = x.get("hitType")
            if ht in HIT_TYPES and run.owner(x.get("sourceID")) is None and int(x.get("abilityGameID") or 0) > 1:
                blocks.append((x["timestamp"], pid, ht, int(x["abilityGameID"])))
    followed: Counter = Counter()
    for u in uses:
        if any((p == u.subject or u.group) and u.ts <= t <= u.ts + IMMUNE_WINDOW for t, p, _h, _g in blocks):
            followed[(u.player, u.gid)] += 1
    unattributed: Counter = Counter()
    for t, p, ht, g in blocks:
        cand = [u for u in uses if (u.subject == p or u.group) and u.ts <= t <= u.ts + IMMUNE_WINDOW]
        if not cand:
            unattributed[(p, ht, g)] += 1
            continue

        def rank(u: Use) -> Tuple[int, float, float]:
            info = extra[(u.player, u.gid)]
            return (BLOCK_TIERS.get(info["cat"] or "", 0), followed[(u.player, u.gid)] / max(1, info["n"]), u.ts)

        best = max(cand, key=rank)
        best.blocked[(ht, g)] += 1

    assoc = associate(run, uses, enemy, auras, taken, combat)
    enemy_ids: Dict[str, Set[int]] = defaultdict(set)
    for _t, g, _k, _tg in enemy:
        enemy_ids[run.ab(g)].add(g)
    for a in auras:
        enemy_ids[run.ab(a.gid)].add(a.gid)
    for lst in taken.values():
        for x in lst:
            g = int(x.get("abilityGameID") or 0)
            if g > 1 and run.owner(x.get("sourceID")) is None:
                enemy_ids[run.ab(g)].add(g)
    return Result(uses, auras, extra, skipped, unmatched, unattributed, assoc, full, combat_ms,
                  combos=find_combos(uses, extra), groups=group_responses(run, uses, extra, enemy),
                  enemy_ids=dict(enemy_ids))


def group_responses(run: Run, uses: List[Use], extra: Dict[Tuple[int, int], Dict[str, Any]],
                    enemy: List[Tuple[float, int, str, Optional[int]]]) -> List[Dict[str, Any]]:
    """至少 3 名玩家在 2 秒内都用了保命/免疫/解控类技能的时刻，以及之前 4 秒内的敌方读条/施放。"""
    lst = sorted((u for u in uses if (extra[(u.player, u.gid)]["cat"] or "") in GROUP_EFFECT_CATS),
                 key=lambda u: u.ts)
    enemy_ts = [x[0] for x in enemy]
    out: List[Dict[str, Any]] = []
    i = 0
    while i < len(lst):
        j = i
        while j + 1 < len(lst) and lst[j + 1].ts - lst[i].ts <= GROUP_WINDOW:
            j += 1
        members = lst[i:j + 1]
        if len({u.player for u in members}) >= GROUP_MIN_PLAYERS:
            t0 = members[0].ts
            lo = bisect.bisect_left(enemy_ts, t0 - CAST_BEFORE)
            hi = bisect.bisect_right(enemy_ts, members[-1].ts)
            casts: List[int] = []
            for _t, g, _k, _tg in enemy[lo:hi]:
                if g not in casts:
                    casts.append(g)
            out.append({"ts": t0, "uses": members, "casts": casts})
            i = j + 1
        else:
            i += 1
    return out


def find_combos(uses: List[Use], extra: Dict[Tuple[int, int], Dict[str, Any]]) -> Dict[int, List[Tuple[int, int, int, float]]]:
    """同一玩家反复在 5 秒内接连使用的两个额外技能（不论先后），例如牺牲祝福与圣盾术。"""
    by_player: Dict[int, List[Use]] = defaultdict(list)
    for u in uses:
        if (extra[(u.player, u.gid)]["cat"] or "") not in NOISE_CATS:
            by_player[u.player].append(u)
    out: Dict[int, List[Tuple[int, int, int, float]]] = {}
    for pid, lst in by_player.items():
        lst.sort(key=lambda u: u.ts)
        pairs: Dict[Tuple[int, int], List[float]] = defaultdict(list)
        for i, a in enumerate(lst):
            seen: Set[int] = set()
            for b in lst[i + 1:]:
                if b.ts - a.ts > COMBO_WINDOW:
                    break
                if b.gid != a.gid and b.gid not in seen:
                    seen.add(b.gid)
                    pairs[(a.gid, b.gid)].append(b.ts - a.ts)
        rows = []
        done: Set[Tuple[int, int]] = set()
        for (ga, gb), gaps in pairs.items():
            if (ga, gb) in done:
                continue
            back = pairs.get((gb, ga), [])
            done |= {(ga, gb), (gb, ga)}
            if len(back) > len(gaps):
                ga, gb, gaps, back = gb, ga, back, gaps
            both = gaps + back
            na, nb = extra[(pid, ga)]["n"], extra[(pid, gb)]["n"]
            if len(both) >= 2 and len(both) >= 0.3 * min(na, nb):
                rows.append((ga, gb, len(both), sorted(both)[len(both) // 2], len(back)))
        rows.sort(key=lambda r: -r[2])
        if rows:
            out[pid] = rows[:5]
    return out


def _name(run: Run, gid: int) -> str:
    return run.ab(gid)


def associate(run: Run, uses: List[Use], enemy, auras: List[Aura], taken, combat) -> Dict[Tuple[int, int], List[Dict[str, Any]]]:
    """同一技能多次使用时反复出现的敌方机制（按技能名合并读条、减益、伤害的不同 ID）。

    倍数（lift）= 实际伴随次数 ÷ 随机时刻也会伴随的期望次数。期望按该机制的"情境窗口"覆盖了多少比例的战斗时间计算。
    """
    combat_ms = sum(b - a for a, b in combat) or 1.0
    own_names = {_name(run, g) for (_p, g) in {(u.player, u.gid) for u in uses}}
    cast_spans: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    for t, g, _k, _tg in enemy:
        cast_spans[_name(run, g)].append((t - CAST_AFTER, t + CAST_BEFORE))
    aura_spans: Dict[Tuple[int, str], List[Tuple[float, float]]] = defaultdict(list)
    for a in auras:
        aura_spans[(a.target, _name(run, a.gid))].append((a.start - APPLY_AFTER, a.end))
    hit_spans: Dict[Tuple[int, str], List[Tuple[float, float]]] = defaultdict(list)
    for pid, lst in taken.items():
        for x in lst:
            g = int(x.get("abilityGameID") or 0)
            if g > 1 and run.owner(x.get("sourceID")) is None:
                hit_spans[(pid, _name(run, g))].append((x["timestamp"], x["timestamp"] + HIT_BEFORE))
    cache: Dict[Tuple[Any, ...], float] = {}

    def coverage(subjects: Tuple[int, ...], key: str) -> float:
        ck = (subjects, key)
        if ck not in cache:
            spans = list(cast_spans.get(key, []))
            for s in subjects:
                spans += aura_spans.get((s, key), []) + hit_spans.get((s, key), [])
            cache[ck] = min(1.0, _overlap(_merge(spans), combat) / combat_ms)
        return cache[ck]

    groups: Dict[Tuple[int, int], List[Use]] = defaultdict(list)
    for u in uses:
        groups[(u.player, u.gid)].append(u)
    out: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    all_players = tuple(run.players)
    for key, lst in groups.items():
        hits: Dict[str, Counter] = defaultdict(Counter)
        subjects_of = [all_players if u.group else (u.subject,) for u in lst]
        for u in lst:
            chans: Dict[str, Set[str]] = defaultdict(set)
            for _dt, g, kind in u.before:
                chans[_name(run, g)].add("前" + kind)
            for _dt, g, kind in u.after:
                chans[_name(run, g)].add("后" + kind)
            for g in u.active:
                chans[_name(run, g)].add("身上有")
            for g in u.applied_after:
                chans[_name(run, g)].add("随后上身")
            for g in u.hits:
                chans[_name(run, g)].add("刚被击中")
            for name, cs in chans.items():
                hits[name]["n"] += 1
                for c in cs:
                    hits[name][c] += 1
        rows = []
        for name, cnt in hits.items():
            if name in ("近战", "技能0") or name in own_names:
                continue
            exp = sum(coverage(subjects, name) for subjects in subjects_of)
            n = cnt["n"]
            lift = n / exp if exp > 0 else float("inf")
            pval = poisson_tail(n, exp)
            if n >= 2 and lift >= MIN_LIFT and pval <= MAX_P:
                rows.append({"name": name, "n": n, "of": len(lst), "lift": lift, "expected": exp, "p": pval,
                             "chans": {k: v for k, v in cnt.items() if k != "n"}})
        rows.sort(key=lambda r: (r["p"], -r["n"], r["name"]))
        out[key] = rows
    return out


# ---------------------------------------------------------------- 获取
def fetch_events(run: Run) -> Dict[str, Any]:
    tasks = {
        "casts": lambda: data.events(run, data_type="Casts", hostility="Friendlies", limit=100000)[0],
        "ecasts": lambda: data.events(run, data_type="Casts", hostility="Enemies", limit=100000)[0],
        "debuffs": lambda: data.events(run, data_type="Debuffs", hostility="Friendlies", limit=100000)[0],
        "dispels": lambda: data.events(run, data_type="Dispels", hostility="Friendlies", limit=20000)[0],
        "taken": lambda: data.events(run, data_type="DamageTaken", hostility="Friendlies", limit=200000,
                                     include_resources=True)[0],
        "dd": lambda: data.damage_done(run),
        "heal": lambda: data.healing(run),
    }
    ev = data.parallel(tasks, workers=4)
    deaths: Dict[int, List[float]] = defaultdict(list)
    for d in run.player_deaths():
        deaths[d["id"]].append(run.start + (d.get("deathTime") or 0))
    ev["deaths"] = dict(deaths)
    return ev


# ---------------------------------------------------------------- 输出
def _plabel(run: Run, pid: Optional[int]) -> str:
    if pid is None or pid == -1:
        return "?"
    p = run.players.get(pid)
    return p.label if p else run.actor_name(pid)


def _pshort(run: Run, pid: Optional[int]) -> str:
    p = run.players.get(pid) if pid is not None else None
    return f"{p.name}({fmt.CLASS_ZH.get(p.cls, p.cls)})" if p else "?"


def _lift(x: float) -> str:
    return "∞" if x == float("inf") else (f"{x:.0f}" if x >= 10 else f"{x:.1f}")


CHAN_ZH = ["身上有", "随后上身", "刚被击中", "前读条", "前施放", "后读条", "后施放"]


def _chan_text(chans: Dict[str, int]) -> str:
    return "，".join(f"{c}{chans[c]}" for c in CHAN_ZH if chans.get(c))


def _effects(run: Run, lst: List[Use]) -> Tuple[str, Counter, Counter]:
    rm_c: Counter = Counter()
    rm_inf: Counter = Counter()
    bl: Counter = Counter()
    for u in lst:
        for g, _t, inferred in u.removed:
            (rm_inf if inferred else rm_c)[_name(run, g)] += 1
        for (ht, g), k in u.blocked.items():
            bl[(HIT_TYPES[ht], _name(run, g))] += k
    parts = []
    for name, k in rm_c.most_common(4):
        parts.append(f"驱散 {name}×{k}")
    for name, k in rm_inf.most_common(4):
        parts.append(f"随后消失 {name}×{k}")
    for (kind, name), k in bl.most_common(4):
        parts.append(f"{kind} {name}×{k}")
    return "；".join(parts), rm_c + rm_inf, bl


def mechanic_map(run: Run, res: Result, focus: Optional[Set[int]] = None) -> Dict[str, Dict[str, Any]]:
    """敌方机制（按技能名） -> {"resp": Counter[(玩家, 技能)], "ev": {(玩家, 技能): 证据集合}, "ids": 技能 ID}。

    只收直接效果（驱散/推断消除/免疫/反射）和强伴随（n ≥ 3、p ≤ STRONG_P、非爆发类）。
    """
    mech: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"resp": Counter(), "ev": defaultdict(set), "ids": set()})
    for (pid, gid), rows in res.assoc.items():
        if focus is not None and pid not in focus:
            continue
        if (res.extra[(pid, gid)]["cat"] or "") in NOISE_CATS:
            continue
        for r in rows:
            if r["n"] < 3 or r["p"] > STRONG_P:
                continue
            m = mech[r["name"]]
            m["resp"][(pid, gid)] += r["n"]
            m["ev"][(pid, gid)].add(f"伴随{r['n']}/{r['of']}·{_lift(r['lift'])}倍")
    for u in res.uses:
        if focus is not None and u.player not in focus:
            continue
        for g, _t, inferred in u.removed:
            m = mech[_name(run, g)]
            m["resp"][(u.player, u.gid)] += 1
            m["ids"].add(g)
            m["ev"][(u.player, u.gid)].add("推断消除" if inferred else "驱散")
        for (ht, g), k in u.blocked.items():
            m = mech[_name(run, g)]
            m["resp"][(u.player, u.gid)] += k
            m["ids"].add(g)
            m["ev"][(u.player, u.gid)].add(HIT_TYPES[ht])
    for (pid, dg, rm), k in res.unmatched_dispels.items():
        if focus is not None and pid not in focus:
            continue
        m = mech[_name(run, rm)]
        m["resp"][(pid, dg)] += k
        m["ids"].add(rm)
        m["ev"][(pid, dg)].add("驱散")
    return mech


def class_players(run: Run, cls: str, spec: Optional[str] = None) -> Set[int]:
    return {pid for pid, p in run.players.items() if p.cls == cls and (not spec or p.spec == spec)}


def render(run: Run, res: Result, player: Optional[str] = None, ability: Optional[str] = None,
           top: int = 12, info: Optional[Dict[int, Dict[str, Any]]] = None, detail: int = 40,
           cls: Optional[Tuple[str, Optional[str]]] = None) -> str:
    info = info or {}
    lines = [f"# 应对技巧：常规循环之外的技能 — {run.header()}",
             f"链接：{run.url}",
             f"战斗中 {fmt.clock(res.combat_ms)}；额外技能 {len(res.extra)} 种、使用 {len(res.uses)} 次；"
             f"敌方施加给玩家的减益 {len(res.auras)} 次。口径见 references/data-notes.md「应对技巧」。"]
    focus: Optional[Set[int]] = {run.find_player(player).id} if player else None
    if cls:
        focus = class_players(run, *cls) & (focus if focus is not None else set(run.players))
        label = fmt.class_spec(cls[0], cls[1] or "")
        if not focus:
            lines.append(f"\n本场没有{label}，主场次的分表跳过；看下面的多场职业汇总。")
            return "\n".join(lines)
        lines.append("主场次只看" + label + "：" + "、".join(run.players[p].label for p in sorted(focus))
                     + "（一至五节只是这一场；多场合并见文末「职业汇总」）")
    if ability:
        return render_detail(run, res, ability, focus, detail)

    # ---- 一、敌方机制 → 应对
    mech = mechanic_map(run, res, focus)
    aura_by_name: Dict[str, List[Aura]] = defaultdict(list)
    for a in res.auras:
        aura_by_name[_name(run, a.gid)].append(a)
        mech_ids = mech[_name(run, a.gid)]["ids"] if _name(run, a.gid) in mech else None
        if mech_ids is not None:
            mech_ids.add(a.gid)
    rows = []
    for name, m in sorted(mech.items(), key=lambda kv: -sum(kv[1]["resp"].values())):
        if not m["resp"]:
            continue
        auras = aura_by_name.get(name, [])
        dispel = next((info[g]["dispel"] for g in m["ids"] | {a.gid for a in auras} if info.get(g, {}).get("dispel")), None)
        resp = []
        for (pid, gid), k in m["resp"].most_common(5):
            resp.append(f"{_pshort(run, pid)} {_name(run, gid)}[{'、'.join(sorted(m['ev'][(pid, gid)]))}]")
        ids = sorted(res.enemy_ids.get(name, set()) | m["ids"])
        rows.append([name, fmt.join_limited([str(g) for g in ids], 3, ","), dispel or "—",
                     f"{len(auras)}次/{len({a.target for a in auras})}人" if auras else "—", "；".join(resp)])
    lines += ["", "## 一、敌方机制 → 被哪些额外技能应对",
              "证据：驱散 = WCL 驱散事件；推断消除 = 使用后 0.4 秒内该减益提前消失；免疫/反射 = 使用后 12 秒内该技能对作用对象免疫/被反射；"
              "伴随 n/N·k倍 = 该技能 N 次使用里有 n 次处在这个机制的情境里，是随机时刻的 k 倍（只说明时间上相关；"
              "本表只收 n ≥ 3 且 p ≤ 0.002 的伴随）。",
              fmt.table(["敌方机制", "技能ID（读条/减益/伤害）", "驱散类型", "减益上身", "应对（玩家 技能[证据]）"],
                        rows[:max(top * 2, 20)])]

    # ---- 二、敌方减益怎么结束的
    rows = []
    for name, auras in sorted(aura_by_name.items(), key=lambda kv: -len(kv[1])):
        ends = Counter(a.reason for a in auras)
        how: Counter = Counter()
        for a in auras:
            if a.by and a.reason in ("驱散", "提前消失"):
                how[(a.by[0], a.by[1], a.reason)] += 1
        early = ends["驱散"] + ends["提前消失"]
        sync = ends["同时结束"]
        unexplained = sum(1 for a in auras if a.reason == "提前消失" and not a.by)
        by_text = "、".join(f"{_pshort(run, p)}{_name(run, g)}×{k}" + ("(推断)" if r == "提前消失" else "")
                            for (p, g, r), k in how.most_common(4))
        if unexplained:
            by_text += ("；" if by_text else "") + f"原因未识别×{unexplained}"
        full = res.full_dur.get(auras[0].gid)
        dispel = next((info[a.gid]["dispel"] for a in auras if info.get(a.gid, {}).get("dispel")), None)
        rows.append([name, fmt.join_limited([str(g) for g in sorted({a.gid for a in auras})], 2, ","), dispel or "—",
                     len(auras), len({a.target for a in auras}), fmt.secs(full) if full else "—",
                     f"{ends['驱散']}", f"{ends['提前消失']}（{fmt.pct(ends['提前消失'], len(auras))}）", sync,
                     ends["死亡"], by_text or "—"])
    lines += ["", "## 二、敌方减益是怎么结束的",
              "完整持续 = 未被驱散、未随死亡消失的那些的 90 分位（Wowhead 写的持续时间更长时用它）；"
              "提前消失 = 短于完整持续的 85%、不是驱散或死亡，且不是多人同时失去（同时结束 = 机制自己的循环，不归因给玩家）。",
              fmt.table(["减益", "ID", "驱散类型", "上身", "中招人", "完整持续", "驱散", "提前消失", "同时结束",
                         "随死亡消失", "谁处理的"], rows[:top * 2])]

    # ---- 三、每名玩家
    lines += ["", "## 三、每名玩家的额外技能",
              "典型情境 = 显著性最高的伴随机制（读条/施放/减益/伤害按技能名合并；泊松检验 p ≤ 0.02 且 ≥ 2.5 倍）；"
              "低血 = 作用对象使用前血量 < 50% 或前 3 秒承伤 ≥ 50% 最大生命；分类带 * 的是据 Wowhead 说明或使用时机推断的；"
              "爆发/伤害/治疗类且没有直接效果的技能只列在末行。"]
    per: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
    for (pid, gid) in res.extra:
        per[pid].append((pid, gid))
    uses_by: Dict[Tuple[int, int], List[Use]] = defaultdict(list)
    for u in res.uses:
        uses_by[(u.player, u.gid)].append(u)
    for pid, keys in per.items():
        if focus is not None and pid not in focus:
            continue
        p = run.players[pid]
        rows, quiet = [], []
        quiet_n: Dict[str, int] = {}
        quiet_cat: Dict[str, Optional[str]] = {}
        keys.sort(key=lambda k: (0 if _effects(run, uses_by[k])[0] else 1,
                                 min([r["p"] for r in res.assoc.get(k, [])] or [1.0]), -res.extra[k]["n"]))
        for key in keys:
            lst = uses_by.get(key, [])
            x = res.extra[key]
            eff, _rm, _bl = _effects(run, lst)
            assoc = res.assoc.get(key, [])
            if not eff and (not assoc or (x["cat"] or "") in NOISE_CATS):
                label = _name(run, key[1])
                quiet_n[label] = quiet_n.get(label, 0) + x["n"]
                quiet_cat.setdefault(label, x["cat"])
                continue
            boss = sum(1 for u in lst if (run.pull_of(u.ts) or None) and run.pull_of(u.ts).is_boss)
            low = sum(1 for u in lst if (u.hp is not None and u.hp < 50) or u.dmg_pct >= 0.5)
            ally = Counter(_pshort(run, u.target) for u in lst if u.target)
            ctx = "；".join(f"{r['name']} {r['n']}/{r['of']}（{_lift(r['lift'])}倍：{_chan_text(r['chans'])}）" for r in assoc[:3])
            whom = "、".join(f"{n}×{k}" for n, k in ally.most_common(2)) or ("群体" if lst and lst[0].group else "自身")
            rows.append([_name(run, key[1]) + f"({key[1]})", (x["cat"] or "未分类") + ("*" if x.get("auto") else ""),
                         x["n"], boss, f"{low}/{len(lst)}", whom,
                         ctx or "—", eff or "—"])
        lines += ["", f"### {p.label}·{fmt.ROLE_ZH.get(p.role, p.role)}", fmt.table(
            ["技能", "分类", "次数", "首领战", "低血", "给谁", "典型情境", "直接效果"], rows[:top])]
        quiet = [f"{n}×{k}" + (f"[{quiet_cat[n]}]" if quiet_cat.get(n) else "") for n, k in quiet_n.items()]
        if [c for c in res.combos.get(pid, []) if _name(run, c[0]) != _name(run, c[1])]:
            lines.append("常连用（5 秒内接连使用）：" + "；".join(
                f"{_name(run, a)} → {_name(run, b)} ×{k}" + (f"（其中反过来先 {_name(run, b)} {back} 次）" if back else "")
                + f"，中位间隔 {fmt.secs(gap)}" for a, b, k, gap, back in res.combos[pid] if _name(run, a) != _name(run, b)))
        if quiet:
            lines.append("其他额外技能（未见明显应对关系）：" + fmt.join_limited(quiet, 15))
        if res.skipped.get(pid):
            lines.append("打断（见 interrupts 命令）：" + "、".join(f"{_name(run, g)}×{n}" for g, n in res.skipped[pid]))

    # ---- 四、团队同时应对
    groups = [g for g in res.groups if focus is None or any(u.player in focus for u in g["uses"])]
    # 只留"全队级"的时刻：≥ 4 人，或有人确实免疫/反射了东西；按这个强度挑前若干个，再按时间排
    def strength(g: Dict[str, Any]) -> Tuple[int, int]:
        return (int(any(u.blocked for u in g["uses"])), len({u.player for u in g["uses"]}))
    groups = [g for g in groups if strength(g)[0] or strength(g)[1] >= 4]
    groups = sorted(sorted(groups, key=strength, reverse=True)[:top], key=lambda g: g["ts"])
    if groups:
        rows = []
        for g in groups:
            seen: Dict[int, List[str]] = defaultdict(list)
            for u in g["uses"]:
                seen[u.player].append(_name(run, u.gid))
            who = "；".join(f"{_pshort(run, p)} {'、'.join(dict.fromkeys(ns))}" for p, ns in seen.items())
            eff = Counter()
            for u in g["uses"]:
                for (ht, eg), k in u.blocked.items():
                    eff[f"{HIT_TYPES[ht]}{_name(run, eg)}"] += k
            rows.append([run.t(g["ts"]), run.pull_tag(g["ts"]), who,
                         fmt.join_limited([_name(run, c) for c in g["casts"]], 4) or "—",
                         "、".join(f"{k}×{v}" for k, v in eff.most_common(3)) or "—"])
        lines += ["", "## 四、团队同时应对",
                  "2 秒内 ≥ 4 人都用了保命/免疫/解控类技能，或 ≥ 3 人且有人免疫/反射成功的时刻（按强度取前若干个，按时间排列）。"
                  "看出全队对同一个技能的集体处理，例如大招读条时各自开免疫/减伤。",
                  fmt.table(["时间", "波次", "谁用了什么", "之前 4 秒的敌方读条/施放", "免疫/反射"], rows)]

    # ---- 五、未归因
    if res.blocks_unattributed:
        items = [f"{_pshort(run, p)} {HIT_TYPES[ht]} {_name(run, g)}×{k}" for (p, ht, g), k in res.blocks_unattributed.most_common(10)]
        lines += ["", "## 五、来源未识别的免疫/反射",
                  "此前 12 秒内没有该玩家相关的额外技能使用——可能来自被动天赋、种族、宠物，或持续时间更长的增益：",
                  "；".join(items)]
    lines += ["", "下一步：`tactics <链接> --ability <技能> [--player <玩家>]` 看逐次情境；`spell <技能ID>` 查 Wowhead 说明。"]
    return "\n".join(lines)


def render_detail(run: Run, res: Result, ability: str, focus: Optional[Set[int]], limit: int) -> str:
    q = ability.strip()
    if q.isdigit():
        match = lambda g: g == int(q)  # noqa: E731
    else:
        match = lambda g: q.lower() in _name(run, g).lower()  # noqa: E731
    lst = [u for u in res.uses if match(u.gid) and (focus is None or u.player in focus)]
    if not lst:
        names = sorted({_name(run, g) for (_p, g) in res.extra if focus is None or _p in focus})
        raise WCLError(f"没有匹配 '{ability}' 的额外技能使用。本场额外技能：" + fmt.join_limited(names, 40))
    who = "、".join(run.players[p].name for p in sorted(focus)) if focus is not None else ""
    lines = [f"# 逐次情境：{ability}" + (f"（{who}）" if who else "") + f" — {run.header()}",
             "列：时间 波次 | 施放者 → 作用对象 | 血量/前3秒承伤（使用前的剩余血量 % / 前 3 秒受到的伤害占最大生命 %；? = 前 8 秒没有承伤事件，读不到血量）| 身上的敌方减益 | 前4秒敌方读条/施放（相对秒，读/施）| 后2秒 | "
             "效果 | 之后6秒作用对象被哪些敌方技能命中（含被免疫/反射的；没有 = 这次可能没被针对）"]
    for u in lst[:limit]:
        tgt = f" → {run.players[u.target].name}" if u.target else ("（群体）" if u.group else "")
        hp = f"{u.hp:.0f}%" if u.hp is not None else "?"

        def fmt_cast(items: List[Tuple[float, int, str]]) -> str:
            seen, out = set(), []
            for dt, g, kind in items:
                k = (g, kind)
                if k in seen:
                    continue
                seen.add(k)
                out.append(f"{_name(run, g)}{kind[0]}{dt:+.1f}")
            return fmt.join_limited(out, 5, " ")

        eff = []
        for g, t, inferred in u.removed:
            eff.append(f"{'消失' if inferred else '驱散'}:{_name(run, g)}@{run.players[t].name}")
        merged: Counter = Counter()
        for (ht, g), k in u.blocked.items():
            merged[(HIT_TYPES[ht], _name(run, g))] += k
        eff += [f"{kind}:{name}×{k}" for (kind, name), k in merged.items()]
        hits = "、".join(f"{_name(run, g)}" for g, _k in u.hits.most_common(3))
        lines.append(
            f"- {run.t(u.ts, True)} {run.pull_tag(u.ts)} | {run.players[u.player].name}{tgt} | {hp}/{u.dmg_pct * 100:.0f}%"
            + (f"（被 {hits} 打中）" if hits else "")
            + f" | {fmt.join_limited([_name(run, g) for g in u.active], 4) or '—'}"
            + (f"（随后上身 {fmt.join_limited([_name(run, g) for g in u.applied_after], 3)}）" if u.applied_after else "")
            + f" | {fmt_cast(u.before) or '—'} | {fmt_cast(u.after) or '—'} | {'；'.join(eff) or '—'}"
            + f" | {fmt.join_limited([f'{_name(run, g)}×{k}' for g, k in u.after_hits.most_common()], 4) or '无'}")
    if len(lst) > limit:
        lines.append(f"…（共 {len(lst)} 次，只列前 {limit} 次；用 --detail N 调整）")
    return "\n".join(lines)


def _evidence_kinds(evs: Iterable[str]) -> Set[str]:
    return {"伴随" if e.startswith("伴随") else e for e in evs}


def team_ids(rosters: List[Set[str]], shared: int = 3) -> List[int]:
    """有 ≥ shared 名相同玩家的记录归为同一支队伍（传递合并），返回每场的队伍编号（按首次出现编号）。"""
    parent = list(range(len(rosters)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rosters)):
        for j in range(i + 1, len(rosters)):
            if len(rosters[i] & rosters[j]) >= shared:
                parent[find(j)] = find(i)
    labels: Dict[int, int] = {}
    return [labels.setdefault(find(i), len(labels)) for i in range(len(rosters))]


def aggregate(runs: List[Tuple[Run, Result]]) -> str:
    """多场对照：每个敌方机制在几场里被哪种职业的哪个技能应对。"""
    agg: Dict[str, Dict[Tuple[str, str], Dict[str, Any]]] = defaultdict(dict)
    seen_in: Dict[str, Set[int]] = defaultdict(set)
    for idx, (run, res) in enumerate(runs):
        for a in res.auras:
            seen_in[_name(run, a.gid)].add(idx)
        for name, m in mechanic_map(run, res).items():
            for (pid, gid), k in m["resp"].items():
                p = run.players.get(pid)
                cls = fmt.CLASS_ZH.get(p.cls, p.cls) if p else "?"
                slot = agg[name].setdefault((cls, _name(run, gid)), {"runs": set(), "n": 0, "ev": set()})
                slot["runs"].add(idx)
                slot["n"] += k
                slot["ev"] |= _evidence_kinds(m["ev"][(pid, gid)])
    teams = team_ids([{p.name for p in r.players.values()} for r, _res in runs])
    main_names = {p.name for p in runs[0][0].players.values()}
    lines = ["", f"## 六、多场对照（本场 + {len(runs) - 1} 场同副本记录，{len(set(teams))} 支队伍）"]
    rows = []
    for i, (run, _res) in enumerate(runs):
        comp = "、".join(p.spec_zh for p in run.players.values())
        same = len(main_names & {p.name for p in run.players.values()})
        rows.append([("本场" if i == 0 else f"参考{i}"), f"{run.code}#{run.fight_id}", f"+{run.level}", run.result,
                     fmt.clock(run.duration), chr(ord("A") + teams[i]), "—" if i == 0 else f"{same}/{len(run.players)}",
                     comp])
    lines.append(fmt.table(["", "记录", "层数", "结果", "时长", "队伍", "与本场同一批玩家", "阵容"], rows))
    lines.append("队伍 = 与另一场有 ≥ 3 名相同玩家的记录归为同一支队伍；同一支队伍的多场只能算一种习惯，不是多队共识。"
                 "场次 k/N（t 队）= N 场里有 k 场、来自 t 支队伍出现这种应对。证据含义同第一节。")
    rows = []
    n = len(runs)
    for name, slots in sorted(agg.items(), key=lambda kv: (-len(set().union(*[v["runs"] for v in kv[1].values()])),
                                                          -sum(v["n"] for v in kv[1].values()))):
        parts = []
        for (cls, ab), v in sorted(slots.items(), key=lambda kv: (-len(kv[1]["runs"]), -kv[1]["n"]))[:6]:
            nteams = len({teams[i] for i in v["runs"]})
            parts.append(f"{cls} {ab} {len(v['runs'])}/{n}场（{nteams}队）×{v['n']}[{'、'.join(sorted(v['ev']))}]")
        covered = len(set().union(*[v["runs"] for v in slots.values()]))
        rows.append([name, f"{len(seen_in.get(name, ()))}/{n}" if seen_in.get(name) else "—", f"{covered}/{n}",
                     "；".join(parts)])
    lines.append(fmt.table(["敌方机制", "减益出现场次", "有应对的场次", "应对（职业 技能 场次×次数[证据]）"], rows[:40]))
    return "\n".join(lines)


def timing_of(u: Use) -> str:
    """一次使用的时机（粗分类）：上身后解 / 预开免疫 / 低血保命 / 其他。"""
    if u.removed:
        return "上身后解"
    if u.blocked:
        return "预开免疫"
    if (u.hp is not None and u.hp < 50) or u.dmg_pct >= 0.5:
        return "低血保命"
    return "其他"


TIMING_ORDER = ["上身后解", "预开免疫", "低血保命", "其他"]


def location_of(run: Run, ts: float) -> Tuple[str, float]:
    """(位置名, 路线顺序)：首领战用首领名；其余按"上一个首领 → 下一个首领"分段（大秘境常常连拉，按波次分不稳定）。"""
    bosses = sorted((p for p in run.pulls if p.is_boss), key=lambda p: p.start)
    names = ["、".join(p.boss_names[:1]) or p.name for p in bosses]
    pl = run.pull_of(ts)
    if pl and pl.is_boss and pl in bosses:
        j = bosses.index(pl)
        return f"👹 首领 {j + 1} · {names[j]}", j + 1.0
    k = sum(1 for p in bosses if p.start < ts)
    prev = names[k - 1] if k else "开场"
    nxt = names[k] if k < len(names) else "结束"
    return f"👾 小怪 · {prev} → {nxt}", k + 0.5


def _dedupe_presses(run: Run, uses: List[Use], gap: float = 1500) -> List[Use]:
    """同一玩家 1.5 秒内的同名技能只算一次按键（例如操控时间的施放 342245 和回溯 342247 被记成两条）。"""
    last: Dict[Tuple[int, str], float] = {}
    out = []
    for u in sorted(uses, key=lambda u: u.ts):
        key = (u.player, _name(run, u.gid))
        if key in last and u.ts - last[key] <= gap:
            continue
        last[key] = u.ts
        out.append(u)
    return out


def class_digest(runs: List[Tuple[Run, Result]], cls: str, spec: Optional[str] = None) -> str:
    """职业汇总：跨多场，把某职业的额外技能按"技能 → 用在哪、什么时机"和"机制 → 怎么应对"两个方向合并。"""
    label = fmt.class_spec(cls, spec or "")
    n = len(runs)
    abil: Dict[str, Dict[str, Any]] = {}
    mech: Dict[str, Dict[Tuple[str], Dict[str, Any]]] = defaultdict(dict)
    debuff: Dict[str, Dict[str, Any]] = {}
    combos: Counter = Counter()
    combo_runs: Dict[Tuple[str, str], Set[int]] = defaultdict(set)
    roster: List[str] = []
    loc: Dict[Tuple[str, str], Dict[str, Any]] = {}
    loc_order: Dict[str, List[float]] = defaultdict(list)
    base: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"n": 0, "before": Counter(), "taking": Counter()})
    for idx, (run, res) in enumerate(runs):
        pids = class_players(run, cls, spec)
        tag = "本场" if idx == 0 else f"参考{idx}"
        presses = _dedupe_presses(run, res.uses)
        roster.append(f"{tag} {run.code}#{run.fight_id} +{run.level} {run.result}："
                      + ("、".join(run.players[p].label for p in sorted(pids)) or f"（没有{label}）"))
        if not pids:
            continue
        # 基线：同一位置所有玩家的额外技能使用（近似"这个位置随便一个时刻"），用来去掉一直在读的技能
        for u in presses:
            if (res.extra[(u.player, u.gid)]["cat"] or "") in NOISE_CATS:
                continue
            b = base[location_of(run, u.ts)[0]]
            b["n"] += 1
            for nm in {_name(run, g) for _dt, g, _k in u.before}:
                b["before"][nm] += 1
            for nm in {_name(run, g) for g in set(u.hits) | set(u.after_hits)}:
                b["taking"][nm] += 1
        for (pid, gid), x in res.extra.items():
            if pid not in pids:
                continue
            name = _name(run, gid)
            if name in abil and abil[name]["cat"] is None and x["cat"] is not None:
                abil[name]["cat"], abil[name]["auto"] = x["cat"], x.get("auto")
            a = abil.setdefault(name, {"cat": x["cat"], "auto": x.get("auto"), "runs": set(), "n": 0,
                                       "timing": Counter(), "eff": Counter(), "mech": Counter(), "mech_runs": defaultdict(set),
                                       "ids": set(), "where": Counter(), "taking": Counter(), "uses": 0})
            a["runs"].add(idx)
            a["ids"].add(gid)
            a.setdefault("specs", Counter())[run.players[pid].spec_zh.split("-")[-1]] += 1
            for r in res.assoc.get((pid, gid), []):
                a["mech"][r["name"]] += r["n"]
                a["mech_runs"][r["name"]].add(idx)
        for u in presses:
            if u.player not in pids:
                continue
            a = abil.get(_name(run, u.gid))
            if a is None:
                continue
            a["timing"][timing_of(u)] += 1
            a["uses"] += 1
            a["n"] += 1
            if (a["cat"] or "") not in NOISE_CATS and a["cat"] is not None:
                where, order = location_of(run, u.ts)
                loc_order[where].append(order)
                L = loc.setdefault((where, _name(run, u.gid)), {"runs": set(), "n": 0, "before": Counter(),
                                                                 "taking": Counter(), "eff": Counter()})
                L["runs"].add(idx)
                L["n"] += 1
                for nm in {_name(run, g) for _dt, g, _k in u.before}:
                    L["before"][nm] += 1
                for nm in {_name(run, g) for g in set(u.hits) | set(u.after_hits)}:
                    L["taking"][nm] += 1
                for g, _t, inferred in u.removed:
                    L["eff"][("推断消除" if inferred else "驱散", _name(run, g))] += 1
                for (ht, g), k in u.blocked.items():
                    L["eff"][(HIT_TYPES[ht], _name(run, g))] += k
            w = location_of(run, u.ts)[0]
            a["where"][w.split(" · ")[-1] if w.startswith("👹") else "小怪"] += 1
            for g in set(u.hits) | set(u.after_hits):
                a["taking"][_name(run, g)] += 1
            for g, _t, inferred in u.removed:
                a["eff"][("推断消除" if inferred else "驱散", _name(run, g))] += 1
            for (ht, g), k in u.blocked.items():
                a["eff"][(HIT_TYPES[ht], _name(run, g))] += k
        for name, m in mechanic_map(run, res, pids).items():
            for (pid, gid), k in m["resp"].items():
                slot = mech[name].setdefault((_name(run, gid),), {"runs": set(), "n": 0, "ev": set()})
                slot["runs"].add(idx)
                slot["n"] += k
                slot["ev"] |= _evidence_kinds(m["ev"][(pid, gid)])
        for au in res.auras:
            if au.target not in pids:
                continue
            d = debuff.setdefault(_name(run, au.gid), {"runs": set(), "n": 0, "ends": Counter(), "by": Counter(),
                                                        "ids": set()})
            d["runs"].add(idx)
            d["n"] += 1
            d["ids"].add(au.gid)
            if au.by and au.reason in ("驱散", "提前消失"):
                who = "自己" if au.by[0] == au.target else fmt.CLASS_ZH.get(
                    run.players[au.by[0]].cls, "?") if au.by[0] in run.players else "?"
                d["by"][f"{who}·{_name(run, au.by[1])}" + ("(推断)" if au.inferred else "")] += 1
                d["ends"]["自己解" if who == "自己" else "队友解"] += 1
            else:
                d["ends"][{"提前消失": "提前消失(原因不明)"}.get(au.reason, au.reason)] += 1
        for pid in pids:
            for a_gid, b_gid, k, _gap, _back in res.combos.get(pid, []):
                key = (_name(run, a_gid), _name(run, b_gid))
                if key[0] == key[1]:
                    continue  # 同名两个 ID（例如操控时间的施放与回溯）
                combos[key] += k
                combo_runs[key].add(idx)
    lines = ["", f"## 七、职业汇总：{label}（{n} 场）", *[f"- {r}" for r in roster],
             "时机 = 每次使用的粗分类：上身后解（用完减益被驱散/消失）、预开免疫（用完后免疫/反射了敌方技能）、"
             "低血保命（用前血量 < 50% 或前 3 秒承伤 ≥ 50%）、其他（多半是对读条预开但没被打到，或纯习惯性使用）。"
             "直接效果合并多场；伴随机制只列 ≥ 2 场都出现的（单场时列全部）。"]
    rows = []
    hidden = []
    for name, a in sorted(abil.items(), key=lambda kv: (-(len(kv[1]["eff"]) > 0), -len(kv[1]["runs"]), -kv[1]["n"])):
        if ((a["cat"] or "") in NOISE_CATS or a["cat"] is None) and not a["eff"]:
            hidden.append(f"{name}×{a['n']}[{a['cat'] or '未分类'}]")
            continue
        need = 2 if n > 1 else 1
        mechs = [f"{m}({len(a['mech_runs'][m])}场)" for m, _k in a["mech"].most_common(8)
                 if len(a["mech_runs"][m]) >= need][:4]
        if not a["eff"] and not mechs and len(a["runs"]) < max(2, n // 2 + 1):
            continue
        tim = " ".join(f"{t}{a['timing'][t]}" for t in TIMING_ORDER if a["timing"][t])
        where = " ".join(f"{w}{k}" for w, k in a["where"].most_common(4))
        taking = "、".join(f"{nm} {fmt.pct(k, a['uses'])}" for nm, k in a["taking"].most_common(3)
                          if a["uses"] and k / a["uses"] >= 0.15)
        eff = "；".join(f"{k}{nm}×{v}" for (k, nm), v in a["eff"].most_common(5))
        specs = "、".join(sp for sp, _k in (a.get("specs") or Counter()).most_common())
        rows.append([f"{name}({','.join(str(g) for g in sorted(a['ids']))})",
                     (a["cat"] or "未分类") + ("*" if a.get("auto") else ""), f"{len(a['runs'])}/{n}", specs or "—", a["n"],
                     where or "—", tim or "—", taking or "—", eff or "—", "、".join(mechs) or "—"])
    lines += ["", f"### 技能 → 用在哪、什么时机",
              "在哪用 = 首领战（按首领名）/小怪的使用次数；当时在吃的伤害 = 用前 3 秒或用后 6 秒作用对象被这个敌方技能打中的使用占比（≥ 15% 才列）。",
              fmt.table(["技能(ID)", "分类", "场次", "专精", "次数", "在哪用", "时机", "当时在吃的伤害", "直接效果", "常伴随的机制"], rows[:30])]
    if hidden:
        lines.append("未列入（增益/输出/消耗品，或未分类且没有直接效果——多半是饰品、道具；需要时 `spell <ID>` 查）："
                     + fmt.join_limited(hidden, 15))
    rows = []
    single = 0
    for (where, ab), L in sorted(loc.items(), key=lambda kv: (fmt.median(loc_order[kv[0][0]]) or 0, -kv[1]["n"])):
        if L["n"] < 2 and not L["eff"]:
            continue
        if n > 1 and len(L["runs"]) < 2 and not L["eff"]:
            single += 1
            continue
        B = base[where]

        def top(c: Counter, key: str) -> str:
            out = []
            for nm, k in c.most_common():
                share = k / L["n"]
                lift = share / max(1e-9, B[key][nm] / max(1, B["n"]))
                if share >= 0.3 and lift >= 1.3:
                    out.append(f"{nm} {fmt.pct(k, L['n'])}" + (f"（{_lift(lift)}倍）" if L["n"] >= 4 else ""))
                if len(out) == 2:
                    break
            return "、".join(out)
        rows.append([where, ab, f"{len(L['runs'])}/{n}", L["n"], top(L["before"], "before") or "—",
                     top(L["taking"], "taking") or "—",
                     "；".join(f"{k}{nm}×{v}" for (k, nm), v in L["eff"].most_common(3)) or "—"])
    lines += ["", "### 按位置：在哪一段用了什么、当时敌人在干什么",
              "位置 = 首领战，或两个首领之间的小怪段（连拉时按波次分不稳定）。用前敌方读条 = 使用前 4 秒内敌方读条/施放；"
              "当时在吃的伤害同上表。占比 = 这个位置这个技能的使用里出现该敌方技能的比例；倍数 = 占比 ÷ 同一位置全队所有额外技能使用里的占比"
              "（去掉一直在读的技能）。只列占比 ≥ 30% 且 ≥ 1.3 倍的；次数 < 4 时不显示倍数（样本太少，只当线索）。"
              "位置名可以直接当报告里的段标题。",
              fmt.table(["位置", "技能", "场次", "次数", "用前敌方读条/施放", "当时在吃的伤害", "直接效果"], rows[:45])
              if rows else "（没有）"]
    if single:
        lines.append(f"（另有 {single} 个只在 1 场出现、没有直接效果的组合未列出：只是一个人的习惯，不写进正文。）")
    rows = []
    for name, slots in sorted(mech.items(), key=lambda kv: (-len(set().union(*[v["runs"] for v in kv[1].values()])),
                                                          -sum(v["n"] for v in kv[1].values()))):
        parts = [f"{ab} {len(v['runs'])}/{n}场×{v['n']}[{'、'.join(sorted(v['ev']))}]"
                 for (ab,), v in sorted(slots.items(), key=lambda kv: (-len(kv[1]["runs"]), -kv[1]["n"]))[:5]]
        rows.append([name, "；".join(parts)])
    lines += ["", f"### 敌方机制 → {label}怎么应对（只收直接效果和强伴随）",
              fmt.table(["敌方机制", "应对（技能 场次×次数[证据]）"], rows[:30]) if rows else "（没有）"]
    rows = []
    for name, d in sorted(debuff.items(), key=lambda kv: -kv[1]["n"]):
        rows.append([f"{name}({','.join(str(g) for g in sorted(d['ids'])[:2])})", f"{len(d['runs'])}/{n}", d["n"],
                     "、".join(f"{k}{v}" for k, v in d["ends"].most_common()),
                     "、".join(f"{k}×{v}" for k, v in d["by"].most_common(4)) or "—"])
    lines += ["", f"### {label}身上的敌方减益：怎么结束的",
              fmt.table(["减益(ID)", "场次", "上身", "结束方式", "谁解的"], rows[:25]) if rows else "（没有）"]
    if combos:
        lines += ["", "常连用（5 秒内接连使用，合并多场）：" + "；".join(
            f"{a} → {b} ×{k}（{len(combo_runs[(a, b)])}场）" for (a, b), k in combos.most_common(8))]
    return "\n".join(lines)


def cmd_tactics(run: Run, player: Optional[str] = None, ability: Optional[str] = None, top: int = 12,
                detail: int = 40, wowhead: bool = True, refs: int = 0, explicit: Optional[List[str]] = None,
                cls_text: Optional[str] = None) -> str:
    from .wowhead import classify as wh_classify, spells
    lang = run.client.lang if getattr(run.client, "lang", None) in ("zh", "en") else "zh"

    def classify(gids: List[int]) -> Dict[int, str]:
        found = spells(gids[:80], lang=lang)
        return {g: c for g, c in ((g, wh_classify(i)) for g, i in found.items()) if c}

    cls_fn = classify if wowhead else None

    def run_one(r: Run) -> Tuple[Result, Dict[int, Dict[str, Any]]]:
        ev = fetch_events(r)
        found: Dict[int, Dict[str, Any]] = {}
        if wowhead:
            counts = Counter(int(e.get("abilityGameID") or 0) for e in ev.get("debuffs") or []
                             if e.get("type") == "applydebuff" and r.owner(e.get("sourceID")) is None)
            found = spells([g for g, _n in counts.most_common(40)], lang=lang)
        known = {g: i["duration_ms"] for g, i in found.items() if i.get("duration_ms")}
        return analyze(r, ev, classify=cls_fn, known_dur=known), found

    cls: Optional[Tuple[str, Optional[str]]] = None
    if cls_text:
        try:
            cls = fmt.parse_class(cls_text)
        except ValueError as exc:
            raise WCLError(str(exc)) from None
    res, info = run_one(run)
    out = render(run, res, player=player, ability=ability, top=top, info=info, detail=detail, cls=cls)
    if ability or not (refs or explicit):
        if cls and not ability:
            out += "\n" + class_digest([(run, res)], *cls)
        return out
    from .cmd_splits import _candidates, _resolve_ref
    from .context import load_run
    targets: List[Tuple[str, int]] = [_resolve_ref(run, r) for r in (explicit or [])]
    if refs:
        want = refs + len(explicit or [])
        if cls:
            # 按职业找：该职业玩家的个人排名（同层优先），每条对应一场带日志的钥石
            from .cmd_find import find_runs
            found, _note = find_runs(run.client, run.encounter_id, cls[0], cls[1], run.level, want + 3)
            keys = [(r["code"], r["fid"]) for r in found]
        else:
            rows, _note = _candidates(run, run.level, want + 2)
            keys = [(r["report"]["code"], int(r["report"]["fightID"])) for r in rows]
        for key in keys:
            if key != (run.code, run.fight_id) and key not in targets and len(targets) < want:
                targets.append(key)
    runs: List[Tuple[Run, Result]] = [(run, res)]
    failed = []
    for code, fid in targets:
        try:
            other = load_run(run.client, code, str(fid))
            runs.append((other, run_one(other)[0]))
        except WCLError as exc:
            failed.append(f"{code}#{fid}：{str(exc).splitlines()[0]}")
    out += "\n" + aggregate(runs)
    if cls:
        out += "\n" + class_digest(runs, *cls)
    if failed:
        out += "\n未能分析：" + "；".join(failed)
    return out
