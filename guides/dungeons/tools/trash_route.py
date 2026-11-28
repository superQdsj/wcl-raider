#!/usr/bin/env python3
"""Which trash mobs (and which of their casts) show up in which route segment.

    python3 guides/dungeons/tools/trash_route.py <runs.json>  > evidence/trash-route.md

Segment = number of bosses already killed when the trash pull starts (0 = before boss 1).
Uses the same cached WCL queries as diag.py trash.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from wclr import data  # noqa: E402
from wclr.api import Client  # noqa: E402
from wclr.context import load_run  # noqa: E402

runs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["runs"]
client = Client()
mob_runs = defaultdict(Counter)        # seg -> mob -> runs seen
mob_cnt = defaultdict(Counter)         # seg -> mob -> total count
casts = defaultdict(Counter)           # (seg, mob) -> ability name -> casts
for r in runs:
    run = load_run(client, f"{r['code']}#fight={r['fid']}")
    bosses = sorted({(p.end, p.encounter_id) for p in run.pulls if p.is_boss and p.kill})
    kills = []
    for end, eid in bosses:
        if eid not in [e for _, e in kills]:
            kills.append((end, eid))
    def seg(ts):
        return sum(1 for end, _ in kills if end <= ts)
    trash = [p for p in run.pulls if not p.is_boss]
    seen = defaultdict(set)
    for p in trash:
        s = seg(p.start)
        for name, n in p.mobs:
            seen[s].add(name)
            mob_cnt[s][name] += n
    for s, names in seen.items():
        for n in names:
            mob_runs[s][n] += 1
    evs, _ = data.events(run, data_type="Casts", start=run.start, end=run.end,
                         hostility="Enemies", expr='type = "cast"', limit=15000)
    boss_win = [(p.start, p.end) for p in run.pulls if p.is_boss]
    for e in evs:
        ts = e.get("timestamp", 0)
        if any(a <= ts <= b for a, b in boss_win):
            continue
        src = run.actor_name(e.get("sourceID"))
        ab = e.get("ability", {}).get("name") or str(e.get("abilityGameID"))
        casts[(seg(ts), src)][ab] += 1

names = ["老 1 之前", "老 1 → 老 2", "老 2 → 老 3", "老 3 → 老 4", "老 4 之后"]
print(f"# 小怪分段（{len(runs)} 场，段 = 开打时已击杀的首领数）\n")
for s in sorted(mob_runs):
    print(f"## {names[s] if s < len(names) else s}\n")
    for mob, nr in mob_runs[s].most_common():
        top = ", ".join(f"{a}×{c}" for a, c in casts[(s, mob)].most_common(6))
        print(f"- **{mob}**：{nr}/{len(runs)} 场出现，共 {mob_cnt[s][mob]} 只 | 施法：{top or '—'}")
    print()
