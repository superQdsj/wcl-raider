#!/usr/bin/env python3
"""Shared talent string encoder + round-trip verifier for all WoW specs.

Reads a WCL evidence/talents.json (or legacy talents_raw.json), encodes a chosen
player's talentTree against the Raidbots spec tree, decodes it back to assert
0 mismatches / 0 extra nodes, resolves official Chinese talent names via cached
Wowhead tooltips (so authors NEVER hand-translate talent names), prints cross-run
diffs in Chinese + English + spellId, and writes tstring.json.

Usage:
  python3 guides/tools/enc.py --in <evidence/talents.json> --out <tstring.json> [--spec 70] [--player r1_名字]
  python3 guides/tools/enc.py --list-specs
  python3 guides/tools/enc.py --refresh-tree
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOLS = Path(__file__).resolve().parent
GUIDES = TOOLS.parent
DEFAULT_TREE = GUIDES / "rogue" / "sources" / "dl" / "talents.json"
RAIDBOTS_URL = "https://www.raidbots.com/static/data/live/talents.json"
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

_WCL_CLASS = {
    "DeathKnight": "Death Knight",
    "DemonHunter": "Demon Hunter",
}


def load_specs(tree_path: Path) -> List[Dict[str, Any]]:
    if not tree_path.is_file():
        raise SystemExit(
            f"Missing Raidbots talent tree: {tree_path}\n"
            f"Run: python3 guides/tools/enc.py --refresh-tree"
        )
    return json.loads(tree_path.read_text(encoding="utf-8"))


def refresh_tree(tree_path: Path) -> None:
    tree_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(RAIDBOTS_URL, headers={"User-Agent": "Mozilla/5.0 (wcl-raider)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    specs = json.loads(raw.decode("utf-8"))
    assert isinstance(specs, list) and len(specs) >= 35, "Unexpected Raidbots talents.json format"
    tree_path.write_bytes(raw)
    print(f"Updated {tree_path}: {len(specs)} specs ({len(raw) // 1024} KB)")


def extract_tree(entry: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(entry, dict):
        return None
    ci = entry.get("combatantInfo")
    if isinstance(ci, dict) and ci.get("talentTree"):
        return ci["talentTree"]
    if entry.get("talentTree"):
        return entry["talentTree"]
    return None


def infer_spec_id(entry: Dict[str, Any], specs: List[Dict[str, Any]]) -> Optional[int]:
    icon = entry.get("icon") or ""
    if "-" in icon:
        cls_raw, spec_raw = icon.split("-", 1)
        cls_name = _WCL_CLASS.get(cls_raw, cls_raw)
        for s in specs:
            if (s.get("className", "").replace(" ", "").lower() == cls_name.replace(" ", "").lower()
                    and s.get("specName", "").replace(" ", "").lower() == spec_raw.replace(" ", "").lower()):
                return int(s["specId"])
    tree = extract_tree(entry) or []
    ids = {t["nodeID"] for t in tree}
    if not ids:
        return None
    best = max(
        specs,
        key=lambda s: len(ids & {n["id"] for n in s.get("specNodes", [])}),
    )
    if len(ids & {n["id"] for n in best.get("specNodes", [])}) >= 10:
        return int(best["specId"])
    return None


def build_nodes(spec: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    nodes: Dict[int, Dict[str, Any]] = {}
    for k in ("classNodes", "specNodes", "heroNodes", "subTreeNodes"):
        for n in spec.get(k, []):
            nodes[n["id"]] = n
    return nodes


def encode(tree: List[Dict[str, Any]], spec: Dict[str, Any], nodes: Dict[int, Dict[str, Any]]) -> Tuple[str, Dict[int, Dict[str, Any]]]:
    w: Dict[int, Dict[str, Any]] = {}
    for t in tree:
        nid = t["nodeID"]
        if nid in w:
            w[nid]["rank"] += t["rank"]
        else:
            w[nid] = dict(t)

    bits: List[int] = []

    def add(n: int, v: int) -> None:
        bits.extend((v >> i) & 1 for i in range(n))

    add(8, 2)
    add(16, int(spec["specId"]))
    for _ in range(16):
        add(8, 0)

    for nid in spec["fullNodeOrder"]:
        if nid not in w:
            add(1, 0)
            continue
        n, t = nodes[nid], w[nid]
        add(1, 1)
        if n.get("freeNode"):
            add(1, 0)
            continue
        add(1, 1)
        mx = n.get("maxRanks", 1)
        add(1, int(t["rank"] != mx))
        if t["rank"] != mx:
            add(6, t["rank"])
        choice = n["type"] in ("choice", "subtree")
        add(1, int(choice))
        if choice:
            add(2, [e.get("id") for e in n["entries"]].index(t["id"]))

    while len(bits) % 6:
        bits.append(0)
    out = "".join(B64[sum(bits[i + j] << j for j in range(6))] for i in range(0, len(bits), 6))
    return out, w


def decode(st: str, spec: Dict[str, Any], nodes: Dict[int, Dict[str, Any]]) -> Dict[int, Tuple[Any, Any]]:
    bits: List[int] = []
    for ch in st:
        v = B64.index(ch)
        bits += [(v >> i) & 1 for i in range(6)]
    pos = [0]

    def rd(n: int) -> int:
        v = sum(bits[pos[0] + i] << i for i in range(n))
        pos[0] += n
        return v

    ver, sid = rd(8), rd(16)
    assert ver == 2 and sid == int(spec["specId"]), f"Header mismatch: ver={ver}, specId={sid}"
    for _ in range(16):
        rd(8)
    out: Dict[int, Tuple[Any, Any]] = {}
    for nid in spec["fullNodeOrder"]:
        if not rd(1):
            continue
        n = nodes[nid]
        if not rd(1):
            out[nid] = ("granted", None)
            continue
        r = rd(6) if rd(1) else n.get("maxRanks", 1)
        idx = rd(2) if rd(1) else 0
        out[nid] = (r, n["entries"][idx]["id"])
    return out


def verify_roundtrip(st: str, w: Dict[int, Dict[str, Any]], spec: Dict[str, Any], nodes: Dict[int, Dict[str, Any]]) -> None:
    back = decode(st, spec, nodes)
    bad = []
    for nid, t in w.items():
        b = back.get(nid)
        if b is None:
            bad.append((nid, "missing"))
        elif b[0] != "granted" and (b[0] != t["rank"] or (nodes[nid]["type"] != "tiered" and b[1] != t["id"])):
            bad.append((nid, t, b))
    extra = set(back) - set(w)
    if bad or extra:
        raise AssertionError(f"Round-trip verification failed: mismatch={bad}, extra={extra}")


def talent_entries(w: Dict[int, Dict[str, Any]], nodes: Dict[int, Dict[str, Any]]) -> Dict[str, Optional[int]]:
    """Return {en_name: spellId} for all selected nodes."""
    out: Dict[str, Optional[int]] = {}
    for nid, t in w.items():
        n = nodes[nid]
        e = next((x for x in n.get("entries", []) if x.get("id") == t["id"]), None)
        en_name = (e.get("name") if e and e.get("name") else n["name"])
        sid = e.get("spellId") if e else n.get("spellId")
        out[en_name] = int(sid) if sid else None
    return out


def resolve_zh_names(spell_ids: List[int]) -> Dict[int, str]:
    """Fetch official Chinese client names via cached wclr.wowhead.spells."""
    clean = sorted({int(s) for s in spell_ids if s and int(s) > 1})
    if not clean:
        return {}
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    from wclr.wowhead import spells as wowhead_spells
    info = wowhead_spells(clean, lang="zh")
    return {gid: v["name"] for gid, v in info.items() if v.get("name")}


def fmt_talent(en_name: str, sid: Optional[int], zh_map: Dict[int, str]) -> str:
    zh = zh_map.get(sid) if sid else None
    if zh:
        return f"{zh}({en_name}/{sid})"
    return f"{en_name}({sid})" if sid else en_name


def main() -> None:
    ap = argparse.ArgumentParser(description="Shared WoW talent string encoder & round-trip verifier.")
    ap.add_argument("--in", dest="inp", help="Path to evidence/talents.json (or talents_raw.json)")
    ap.add_argument("--out", help="Output path for tstring.json (optional; omit for dry-run)")
    ap.add_argument("--spec", type=int, help="Raidbots specId (auto-inferred from WCL icon if omitted)")
    ap.add_argument("--player", help="Player key in talents.json (defaults to first player with talentTree)")
    ap.add_argument("--tree", default=str(DEFAULT_TREE), help=f"Raidbots talents.json path (default: {DEFAULT_TREE})")
    ap.add_argument("--no-zh", action="store_true", help="Skip Wowhead Chinese name resolution (pure offline)")
    ap.add_argument("--list-specs", action="store_true", help="List all specIds in Raidbots talents.json")
    ap.add_argument("--refresh-tree", action="store_true", help="Download latest Raidbots talents.json")
    args = ap.parse_args()

    tree_path = Path(args.tree)
    if args.refresh_tree:
        refresh_tree(tree_path)
        return

    specs = load_specs(tree_path)
    if args.list_specs:
        for s in sorted(specs, key=lambda x: (x.get("className", ""), x.get("specName", ""))):
            print(f"{s['specId']:>4}  {s.get('className',''):<14} {s.get('specName','')}")
        return

    if not args.inp:
        ap.error("--in is required (unless using --list-specs or --refresh-tree)")

    raw = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    available = [(k, extract_tree(v)) for k, v in raw.items() if extract_tree(v)]
    if not available:
        print("NO_TALENTS: None of the runs in this file contain a WCL talentTree.")
        print("Per GUIDE-SPEC.md: omit the import string box from #talent and document in NOTES.md.")
        sys.exit(2)

    if args.player:
        if args.player not in raw or not extract_tree(raw[args.player]):
            raise SystemExit(f"Player '{args.player}' missing or has no talentTree. Available: {[k for k, _ in available]}")
        who, tree = args.player, extract_tree(raw[args.player])
    else:
        who, tree = available[0]

    spec_id = args.spec or infer_spec_id(raw[who], specs)
    if not spec_id:
        raise SystemExit("Could not infer specId; pass --spec <id> (see --list-specs).")
    spec = next((s for s in specs if int(s.get("specId", -1)) == spec_id), None)
    if not spec:
        raise SystemExit(f"specId {spec_id} not found in {tree_path}")
    nodes = build_nodes(spec)

    results: Dict[str, Tuple[str, Dict[str, Optional[int]]]] = {}
    for k, tr in available:
        st_k, w_k = encode(tr, spec, nodes)
        verify_roundtrip(st_k, w_k, spec, nodes)
        results[k] = (st_k, talent_entries(w_k, nodes))

    st, base_entries = results[who]
    # Resolve Chinese names for all diff talents (+ selected talents when writing tstring.json)
    diff_sids = set()
    for k, (st_k, ent_k) in results.items():
        if k == who or st_k == st:
            continue
        for en_n in set(base_entries) ^ set(ent_k):
            sid = base_entries.get(en_n) or ent_k.get(en_n)
            if sid:
                diff_sids.add(sid)
    zh_map: Dict[int, str] = {}
    if not args.no_zh:
        want_ids = list(diff_sids | ({s for s in base_entries.values() if s} if args.out else set()))
        zh_map = resolve_zh_names(want_ids)

    print(f"spec: {spec_id} ({spec.get('className')} - {spec.get('specName')})")
    print(f"selected: {who} ({len(base_entries)} nodes, round-trip 0 mismatch / 0 extra)")
    print(f"string: {st}")

    base_set = set(base_entries)
    diffs_out: Dict[str, Any] = {}
    for k, (st_k, ent_k) in results.items():
        if k == who:
            continue
        if st_k == st:
            print(f"  vs {k}: IDENTICAL")
            diffs_out[k] = "IDENTICAL"
        else:
            only_base = sorted(base_set - set(ent_k))
            only_other = sorted(set(ent_k) - base_set)
            b_fmt = [fmt_talent(n, base_entries.get(n), zh_map) for n in only_base]
            o_fmt = [fmt_talent(n, ent_k.get(n), zh_map) for n in only_other]
            print(f"  vs {k}: -{b_fmt}  +{o_fmt}")
            diffs_out[k] = {"removed": b_fmt, "added": o_fmt}

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tal_zh = {
            en_n: {"zh": zh_map.get(sid), "spellId": sid}
            for en_n, sid in sorted(base_entries.items())
        }
        payload = {
            "player": who,
            "specId": spec_id,
            "string": st,
            "talents": sorted(base_entries),
            "talents_zh": tal_zh,
            "diffs": diffs_out,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote: {out_path}")


if __name__ == "__main__":
    main()
