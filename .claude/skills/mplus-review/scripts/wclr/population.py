"""同层同专精的排名样本（characterRankings）：样本量与各角色最佳成绩，用于判断百分位是否可靠。"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from .api import HOUR, RATE
from .context import Run

MIN_RELIABLE = 20  # 同层样本少于这个数时，WCL 的同层百分位噪声很大

Key = Tuple[str, str, str]  # (className, specName, metric)


def spec_populations(run: Run, keys: Iterable[Key]) -> Dict[Key, Dict[str, object]]:
    """批量获取 {(职业, 专精, 指标): {"count": 样本数, "amounts": [各角色最佳成绩, 降序], "more": 是否还有更多页}}。

    样本数 = 该副本、本场层数、该专精在 WCL 上的排名角色数（每个角色只算最佳一场）。
    只取第 1 页（最多 100 人）；count 是 WCL 给出的总数。
    """
    keys = sorted({k for k in keys if k[0] and k[1]})
    if not keys or not run.encounter_id or not run.level:
        return {}
    parts = []
    for i, (cls, spec, metric) in enumerate(keys):
        parts.append(f'p{i}: characterRankings(className: "{cls}", specName: "{spec}", metric: {metric}, '
                     f'bracket: {run.level - 1}, page: 1)')
    q = "query { worldData { encounter(id: %d) { %s } } %s }" % (run.encounter_id, " ".join(parts), RATE)
    data = run.client.gql(q, ttl=6 * HOUR, partial=True)
    enc = (data.get("worldData") or {}).get("encounter") or {}
    out: Dict[Key, Dict[str, object]] = {}
    for i, key in enumerate(keys):
        cr = enc.get(f"p{i}") or {}
        rows = cr.get("rankings") or []
        amounts: List[float] = sorted((float(r.get("amount") or 0) for r in rows), reverse=True)
        out[key] = {"count": int(cr.get("count") or len(rows)), "amounts": amounts, "more": bool(cr.get("hasMorePages"))}
    return out


def player_keys(run: Run) -> Dict[int, Key]:
    """每名玩家对应的样本键：治疗用 hps，其余用 dps。"""
    out: Dict[int, Key] = {}
    for pid, p in run.players.items():
        if p.cls and p.spec:
            out[pid] = (p.cls, p.spec, "hps" if p.role == "healer" else "dps")
    return out


def median_best(info: Optional[Dict[str, object]]) -> Optional[float]:
    amounts = list((info or {}).get("amounts") or [])
    if not amounts:
        return None
    amounts.sort()
    n = len(amounts)
    return amounts[n // 2] if n % 2 else (amounts[n // 2 - 1] + amounts[n // 2]) / 2.0
