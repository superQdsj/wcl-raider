"""find 命令：只知道副本名（和职业）时，找带日志的高分记录。

- 副本名 → 当前赛季的 encounter ID（worldData.expansions → zones → encounters，跳过 PTR/Beta 分区）。
- 带职业：characterRankings（该职业玩家的个人排名，每条对应一场带日志的钥石），去重；
  不带职业：fightRankings（整队排名）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import fmt
from .api import DAY, HOUR, RATE, Client, WCLError

Q_ZONES = """{ worldData { expansions { id name zones { id name encounters { id name } } } } %s }""" % RATE

Q_FIGHT_RANK = """query($id: Int!, $bracket: Int!, $page: Int!) {
  worldData { encounter(id: $id) { name fightRankings(bracket: $bracket, page: $page) } }
  %s
}""" % RATE


def _q_char(spec: bool) -> str:
    return ("""query($id: Int!, $cls: String!, %s$bracket: Int!, $page: Int!) {
  worldData { encounter(id: $id) { name characterRankings(className: $cls, %smetric: playerscore,
    bracket: $bracket, page: $page) } }
  %s
}""" % ("$spec: String!, " if spec else "", "specName: $spec, " if spec else "", RATE))


def resolve_dungeon(client: Client, query: str) -> Tuple[int, str]:
    """副本名（中/英文片段）或 encounter ID → (ID, 名称)，优先最新资料片的正式赛季分区。"""
    q = (query or "").strip()
    data = client.gql(Q_ZONES, {}, ttl=7 * DAY)
    exps = sorted((data.get("worldData") or {}).get("expansions") or [], key=lambda e: -int(e.get("id") or 0))
    hits: List[Tuple[int, str, str]] = []
    for exp in exps:
        for z in sorted(exp.get("zones") or [], key=lambda z: -int(z.get("id") or 0)):
            zname = z.get("name") or ""
            if any(w in zname for w in ("PTR", "Beta", "Complete")):
                continue
            for e in z.get("encounters") or []:
                if q.isdigit() and int(q) == e.get("id"):
                    return int(e["id"]), e.get("name") or q
                if q and q.lower() in (e.get("name") or "").lower():
                    hits.append((int(e["id"]), e.get("name") or "?", zname))
        if hits:
            break
    if not hits:
        raise WCLError(f"没有找到名称包含 '{query}' 的副本（只查最新资料片的正式分区）；也可以直接给 encounter ID。")
    exact = [h for h in hits if h[1] == q]
    eid, name, _z = (exact or hits)[0]
    return eid, name


def find_runs(client: Client, eid: int, cls: Optional[str] = None, spec: Optional[str] = None,
              level: Optional[int] = None, want: int = 8) -> Tuple[List[Dict[str, Any]], str]:
    """返回 [{code, fid, level, duration, region, who: [(名字, 专精中文)], team}]；第二项说明取自哪个层数段。"""
    brackets = [level, 0] if level else [0]
    for bracket in brackets:
        out: List[Dict[str, Any]] = []
        seen = set()
        for page in (1, 2, 3):
            if cls:
                v: Dict[str, Any] = {"id": eid, "cls": cls, "bracket": bracket, "page": page}
                if spec:
                    v["spec"] = spec
                d = client.gql(_q_char(bool(spec)), v, ttl=6 * HOUR)
                block = ((d.get("worldData") or {}).get("encounter") or {}).get("characterRankings") or {}
            else:
                d = client.gql(Q_FIGHT_RANK, {"id": eid, "bracket": bracket, "page": page}, ttl=6 * HOUR)
                block = ((d.get("worldData") or {}).get("encounter") or {}).get("fightRankings") or {}
            for r in block.get("rankings") or []:
                rep = r.get("report") or {}
                if not rep.get("code") or rep.get("fightID") is None:
                    continue
                key = (rep["code"], int(rep["fightID"]))
                who = [(r.get("name") or "?", fmt.class_spec(r.get("class", ""), r.get("spec", "")))] if cls else []
                if key in seen:
                    for row in out:
                        if (row["code"], row["fid"]) == key:
                            row["who"] += who
                    continue
                seen.add(key)
                out.append({"code": key[0], "fid": key[1], "level": r.get("bracketData") or r.get("hardModeLevel"),
                            "duration": r.get("duration"), "region": (r.get("server") or {}).get("region") or "",
                            "who": who, "team": [fmt.class_spec(t.get("class", ""), t.get("spec", ""))
                                                 for t in r.get("team") or []]})
            if len(out) >= want or not block.get("hasMorePages"):
                break
        if out or bracket == 0:
            return out[:want], (f"+{level}" if bracket else "全部层数")
    return [], "无"


def cmd_find(client: Client, dungeon: str, cls_text: Optional[str] = None, level: Optional[int] = None,
             limit: int = 8) -> str:
    eid, name = resolve_dungeon(client, dungeon)
    cls = spec = None
    if cls_text:
        try:
            cls, spec = fmt.parse_class(cls_text)
        except ValueError as exc:
            raise WCLError(str(exc)) from None
    rows, note = find_runs(client, eid, cls, spec, level, limit)
    label = fmt.class_spec(cls, spec or "") if cls else "整队"
    if not rows:
        raise WCLError(f"{name}（{eid}）在 {note} 没有找到带日志的{label}排名记录。")
    host = "https://www.warcraftlogs.com/reports"
    lines = [f"# {name}（encounter {eid}）· {label} 高分记录（{note}，按排名）"]
    table = []
    for i, r in enumerate(rows, 1):
        who = "、".join(f"{n}({s})" for n, s in r["who"]) if cls else "、".join(r["team"])
        table.append([i, f"+{r['level']}" if r["level"] else "?", fmt.clock(r["duration"]) if r["duration"] else "?",
                      r["region"], who, f"{host}/{r['code']}#fight={r['fid']}"])
    lines.append(fmt.table(["#", "层数", "用时", "地区", "该职业玩家（专精）" if cls else "阵容", "链接"], table))
    first = f"{host}/{rows[0]['code']}#fight={rows[0]['fid']}"
    if cls:
        lines.append(f"\n下一步：`tactics {first} --class {cls_text} --refs 2`（以第 1 条为主，再从同一份排名里取 2 场对照）。")
    else:
        lines.append(f"\n下一步：`tactics {first} --refs 2`。")
    return "\n".join(lines)
