#!/usr/bin/env python3
"""Fetch a spec's talents from the sample runs and encode the most common build.

    python3 guides/v3/tools/talents.py <runs.json> <dungeon slug> <spec id>
    e.g. python3 guides/v3/tools/talents.py guides/v3/sethraliss/drafts/paladin-retribution/runs.json sethraliss ret

Writes guides/v3/<slug>/evidence/talents-<spec>.json (raw WCL playerDetails with combatantInfo)
and tstring-<spec>.json (import string, round-trip checked by guides/tools/enc.py, plus per-run diffs).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "guides" / "tools"))
from wclr.api import Client, RATE  # noqa: E402

runs_path, slug, spec = sys.argv[1:4]
ev = ROOT / "guides" / "v3" / slug / "evidence"
runs = json.loads(Path(runs_path).read_text(encoding="utf-8"))["runs"]
q = ("query($c:String!,$f:[Int]){ %s reportData{ report(code:$c){ "
     "playerDetails(fightIDs:$f, includeCombatantInfo:true) } } }" % RATE)
client = Client()
out = {}
for r in runs:
    d = client.gql(q, {"c": r["code"], "f": [r["fid"]]})
    pd = d["reportData"]["report"]["playerDetails"]
    pd = pd.get("data", pd).get("playerDetails", pd)
    for role in ("dps", "tanks", "healers"):
        for p in pd.get(role) or []:
            if p.get("name") == r["player"]:
                out[f"{r['tag']}_{p['name']}"] = p
raw = ev / f"talents-{spec}.json"
raw.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"{len(out)}/{len(runs)} runs -> {raw.relative_to(ROOT)}")
subprocess.run([sys.executable, str(ROOT / "guides/tools/enc.py"), "--in", str(raw),
                "--out", str(ev / f"tstring-{spec}.json")], check=True)
