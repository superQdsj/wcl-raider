"""标准数据获取：每张表单独查询（便于跨命令复用缓存），支持并行与事件分页。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from .api import WCLError
from .context import Run, esc, fetch, table_data

def parallel(tasks: Dict[str, Callable[[], Any]], workers: int = 4) -> Dict[str, Any]:
    """并行执行若干独立获取函数，返回 {名称: 结果}。任一失败则抛出其异常。"""
    if len(tasks) <= 1:
        return {k: fn() for k, fn in tasks.items()}
    out: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(workers, len(tasks))) as pool:
        futs = {k: pool.submit(fn) for k, fn in tasks.items()}
        for k, fut in futs.items():
            out[k] = fut.result()
    return out


def _table(run: Run, data_type: str, args: str = "") -> Dict[str, Any]:
    fields = f"t: table(dataType: {data_type}, fightIDs: $fid{', ' + args if args else ''})"
    return table_data(fetch(run, fields).get("t"))


# ---------------------------------------------------------------- tables

def damage_done(run: Run, source: Optional[int] = None) -> Dict[str, Any]:
    return _table(run, "DamageDone", f"sourceID: {source}" if source else "")


def healing(run: Run, source: Optional[int] = None) -> Dict[str, Any]:
    return _table(run, "Healing", f"sourceID: {source}" if source else "")


def casts(run: Run, source: int) -> Dict[str, Any]:
    return _table(run, "Casts", f"sourceID: {source}")


def buffs(run: Run, holder: int) -> Dict[str, Any]:
    # Buffs 表里 sourceID = 身上带着这些增益的玩家（与 WCL 网页的视角一致）
    return _table(run, "Buffs", f"sourceID: {holder}")


def damage_taken(run: Run, player: Optional[int] = None) -> Dict[str, Any]:
    # DamageTaken 表里 sourceID = 承受伤害的我方玩家
    return _table(run, "DamageTaken", "viewBy: Ability" + (f", sourceID: {player}" if player else ""))


def interrupts(run: Run) -> Dict[str, Any]:
    return _table(run, "Interrupts")


def deaths_table(run: Run) -> Dict[str, Any]:
    return _table(run, "Deaths")


def dispels(run: Run) -> Dict[str, Any]:
    return _table(run, "Dispels")


def window_table(run: Run, data_type: str, start: float, end: float) -> Dict[str, Any]:
    """按报告相对时间限定表格范围，不改变既有整场查询的缓存键。"""
    return _table(run, data_type, f"startTime: {max(run.start, start):.0f}, endTime: {min(run.end, end):.0f}")


def rankings(run: Run, metric: str) -> List[Dict[str, Any]]:
    obj = fetch(run, f"r: rankings(fightIDs: $fid, playerMetric: {metric})").get("r") or {}
    return (obj.get("data") if isinstance(obj, dict) else None) or []


def graph(run: Run, data_type: str) -> Dict[str, Any]:
    fields = (f"g: graph(dataType: {data_type}, fightIDs: $fid, startTime: {run.start:.0f}, "
              f"endTime: {run.end:.0f})")
    obj = fetch(run, fields).get("g") or {}
    return obj.get("data") if isinstance(obj, dict) and isinstance(obj.get("data"), dict) else obj


def events(run: Run, *, data_type: str = "All", start: Optional[float] = None, end: Optional[float] = None,
           hostility: str = "Friendlies", source: Optional[int] = None, target: Optional[int] = None,
           ability: Optional[int] = None, expr: str = "", limit: int = 5000,
           include_resources: bool = False) -> Tuple[List[Dict[str, Any]], bool]:
    """分页获取事件。返回 (事件列表, 是否被 limit 截断)。时间为报告相对毫秒。"""
    start = run.start if start is None else max(run.start, start)
    end = run.end if end is None else min(run.end, end)
    if limit <= 0 or end <= start:
        return [], False
    args = [f"dataType: {data_type}", "fightIDs: $fid", f"hostilityType: {hostility}"]
    if source:
        args.append(f"sourceID: {source}")
    if target:
        args.append(f"targetID: {target}")
    if ability:
        args.append(f"abilityID: {ability}")
    if expr:
        args.append(f'filterExpression: "{esc(expr)}"')
    if include_resources:
        args.append("includeResources: true")
    out: List[Dict[str, Any]] = []
    cursor = start
    truncated = False
    for _ in range(50):
        page_limit = min(10000, max(100, limit - len(out)))
        fields = (f"e: events({', '.join(args)}, startTime: {cursor:.0f}, endTime: {end:.0f}, "
                  f"limit: {page_limit}) {{ data nextPageTimestamp }}")
        page = fetch(run, fields).get("e") or {}
        batch = [e for e in (page.get("data") or []) if not e.get("fake")]
        out.extend(batch)
        nxt = page.get("nextPageTimestamp")
        if len(out) > limit:
            return out[:limit], True
        if not nxt or nxt >= end:
            break
        if nxt <= cursor:
            raise WCLError("WCL 事件分页游标未前进，请缩小时间窗口后重试。")
        if len(out) >= limit:
            truncated = True
            break
        cursor = nxt
    else:
        truncated = True  # 保护上限也必须显式告知调用方
    return out, truncated


# ---------------------------------------------------------------- helpers

def interrupt_entries(tbl: Dict[str, Any]) -> List[Dict[str, Any]]:
    """打断表里的技能条目（结构为 entries[].entries[]，做扁平化兼容）。"""
    out: List[Dict[str, Any]] = []

    def walk(items: Any) -> None:
        for it in items or []:
            if not isinstance(it, dict):
                continue
            if "spellsBegun" in it or "spellsInterrupted" in it:
                out.append(it)
            elif it.get("entries"):
                walk(it["entries"])

    walk(tbl.get("entries"))
    return out


def ranking_index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """rankings(...) -> {角色名: 排名信息}。"""
    idx: Dict[str, Dict[str, Any]] = {}
    for fight in rows:
        for role in (fight.get("roles") or {}).values():
            for c in (role or {}).get("characters") or []:
                if c.get("name"):
                    idx[c["name"]] = c
    return idx


def player_series_total(graph_data: Dict[str, Any], run: Run) -> Tuple[List[float], float, float]:
    """把 graph 中所有我方玩家（含宠物归属）的序列逐点相加。返回 (每点数值/秒, 起点, 间隔毫秒)。"""
    series = graph_data.get("series") or []
    names = {p.name for p in run.players.values()}
    total: List[float] = []
    start, interval = run.start, 0.0
    for s in series:
        if s.get("id") not in run.players and s.get("name") not in names:
            continue
        data = s.get("data") or []
        start = s.get("pointStart", start)
        interval = s.get("pointInterval", interval)
        if len(total) < len(data):
            total.extend([0.0] * (len(data) - len(total)))
        for i, v in enumerate(data):
            if isinstance(v, (int, float)):
                total[i] += v
            elif isinstance(v, (list, tuple)) and len(v) >= 2:
                total[i] += v[1] or 0
    return total, float(start), float(interval)


def window_rate(points: List[float], start: float, interval: float, a: float, b: float) -> Optional[float]:
    """graph 序列在 [a, b] 窗口内的平均每秒数值。"""
    if not points or interval <= 0 or b <= a:
        return None
    if a < start - 1e-6 or b > start + len(points) * interval + 1e-6:
        # 缺失的图表区间不能当作伤害/治疗为零。
        return None
    acc = 0.0
    for i, v in enumerate(points):
        s = start + i * interval
        e = s + interval
        ov = min(b, e) - max(a, s)
        if ov > 0:
            acc += v * ov
    return acc / (b - a)


def require_events_ok(evs: List[Dict[str, Any]], what: str) -> None:
    if evs is None:
        raise WCLError(f"未能获取{what}事件。")


# 嗜血类技能（团队急速）：已知 ID + 精确名称匹配（中/英）
LUST_IDS = {2825, 32182, 80353, 264667, 390386, 381301, 444257, 466904}
LUST_NAMES = {"嗜血", "英勇", "时间扭曲", "原始狂怒", "Bloodlust", "Heroism", "Time Warp", "Primal Rage", "Fury of the Aspects"}


def lust_casts(run: Run) -> List[Tuple[float, int, Optional[int]]]:
    """返回本场每次嗜血类效果 (时间戳, 技能ID, 施放者ID)。同一次施放给全队上的增益按 5 秒合并。"""
    ids = {gid for gid in LUST_IDS if gid in run.abilities}
    for gid, a in run.abilities.items():
        name = a.get("name") or ""
        if name in LUST_NAMES or name.endswith("战鼓") or name.endswith("Drums"):
            ids.add(gid)
    if not ids:
        return []
    expr = 'type = "applybuff" and ability.id in (%s)' % ", ".join(str(i) for i in sorted(ids))
    evs, _ = events(run, data_type="Buffs", expr=expr, limit=2000)
    out: List[Tuple[float, int, Optional[int]]] = []
    for e in sorted(evs, key=lambda x: x.get("timestamp") or 0):
        if e.get("type") != "applybuff":
            continue
        if out and e["timestamp"] - out[-1][0] <= 5000:
            continue
        src = e.get("sourceID")
        out.append((e["timestamp"], int(e.get("abilityGameID") or 0), run.owner(src) if src is not None else None))
    return out
