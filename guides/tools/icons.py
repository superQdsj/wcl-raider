"""Shared spell icon helper for guide HTML.

Icons live in guides/icons/<sha1 first 12 hex>.jpg so every guide shares one file
per image, linked via a relative path (no embedded base64 data URIs).

Two ways to use from build.py:
  1. New guides (recommended — no per-dungeon icons.json needed):
       from icons import inject_icons
       html = inject_icons(html, out_path)
     Resolves every {{I:<spell_id>}} via guides/icons/by-spell.json, automatically
     fetching missing icons from Wowhead (via wclr.wowhead + wow.zamimg.com) when
     online, and writes relative links directly.
  2. Legacy guides (with embedded base64 from icons.json):
       from icons import externalize
       externalize(out_path)

CLI usage:
  python3 guides/tools/icons.py [page.html ...]         # externalize base64 in pages
  python3 guides/tools/icons.py --seed                  # seed guides/icons/by-spell.json from existing icons.json
  python3 guides/tools/icons.py --fetch 31224 1966 ...  # prefetch spell IDs into guides/icons/
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

TOOLS = Path(__file__).resolve().parent
GUIDES = TOOLS.parent
ICONS = GUIDES / "icons"
INDEX = ICONS / "by-spell.json"
DATA_URI = re.compile(r"data:image/(jpeg|jpg|png|webp|gif);base64,([A-Za-z0-9+/=]+)")
PLACEHOLDER = re.compile(r"\{\{I:(\d+)\}\}")
EXT = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}
WOWHEAD_ICON_URL = "https://wow.zamimg.com/images/wow/icons/large/{name}.jpg"


def _save_bytes(data: bytes, ext: str = "jpg") -> str:
    ICONS.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha1(data).hexdigest()[:12] + "." + ext
    path = ICONS / name
    if not path.exists():
        path.write_bytes(data)
    return name


def load_index() -> Dict[str, str]:
    if INDEX.is_file():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return {}


def save_index(idx: Dict[str, str]) -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    ordered = {k: idx[k] for k in sorted(idx, key=lambda x: int(x) if x.isdigit() else 0)}
    INDEX.write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _decode_data_uri(uri: str) -> Optional[Tuple[bytes, str]]:
    m = DATA_URI.fullmatch(uri.strip())
    if not m:
        return None
    return base64.b64decode(m.group(2)), EXT[m.group(1)]


def seed_index() -> Tuple[int, int]:
    """Scan existing guides/*/sources/*/icons.json and record spell_id -> filename in by-spell.json."""
    idx = load_index()
    added = 0
    for p in sorted(GUIDES.glob("*/sources/**/icons.json")):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        for sid, uri in raw.items():
            if not str(sid).isdigit() or not isinstance(uri, str):
                continue
            key = str(sid)
            if key in idx and (ICONS / idx[key]).is_file():
                continue
            decoded = _decode_data_uri(uri)
            if not decoded:
                continue
            fname = _save_bytes(*decoded)
            idx[key] = fname
            added += 1
    save_index(idx)
    return added, len(idx)


def fetch_icon(spell_id: int, idx: Optional[Dict[str, str]] = None) -> str:
    """Resolve one spell ID to a filename in guides/icons/, fetching from Wowhead if missing."""
    key = str(int(spell_id))
    owned = idx is None
    if idx is None:
        idx = load_index()
    if key in idx and (ICONS / idx[key]).is_file():
        return idx[key]

    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    from wclr import wowhead  # local import to keep offline usage zero-overhead

    info = wowhead.spell(int(spell_id), lang="zh") or wowhead.spell(int(spell_id), lang="en")
    icon_name = (info or {}).get("icon")
    if not icon_name:
        raise RuntimeError(f"Wowhead returned no icon name for spell ID {spell_id}")
    url = WOWHEAD_ICON_URL.format(name=icon_name.lower())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (wcl-raider)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    if not data:
        raise RuntimeError(f"Empty icon download for spell ID {spell_id} ({url})")
    fname = _save_bytes(data, "jpg")
    idx[key] = fname
    if owned:
        save_index(idx)
    return fname


def inject_icons(
    html_text: str,
    page_path: str | os.PathLike,
    fallback_json: Optional[str | os.PathLike] = None,
    fetch: bool = True,
) -> Tuple[str, int, int]:
    """Replace every {{I:<spell_id>}} in html_text with relative paths into guides/icons/.

    Returns (updated_html, total_replaced, newly_fetched_count).
    """
    page_dir = Path(page_path).resolve().parent
    rel_base = os.path.relpath(ICONS, page_dir).replace(os.sep, "/")
    idx = load_index()
    local_map: Dict[str, str] = {}
    if fallback_json and Path(fallback_json).is_file():
        local_map = json.loads(Path(fallback_json).read_text(encoding="utf-8"))

    ids = sorted({m.group(1) for m in PLACEHOLDER.finditer(html_text)}, key=int)
    fetched = 0
    dirty = False
    for sid in ids:
        if sid in idx and (ICONS / idx[sid]).is_file():
            continue
        if sid in local_map:
            decoded = _decode_data_uri(local_map[sid])
            if decoded:
                idx[sid] = _save_bytes(*decoded)
                dirty = True
                continue
        if not fetch:
            raise KeyError(f"Spell icon {sid} not in {INDEX} and fetch=False")
        fetch_icon(int(sid), idx)
        fetched += 1
        dirty = True

    if dirty:
        save_index(idx)

    count = [0]

    def swap(m: re.Match) -> str:
        count[0] += 1
        return f"{rel_base}/{idx[m.group(1)]}"

    return PLACEHOLDER.sub(swap, html_text), count[0], fetched


def externalize(page: str | os.PathLike) -> Tuple[int, int]:
    """Rewrite one HTML file in place; return (icons replaced, bytes saved)."""
    page_path = Path(page).resolve()
    text = page_path.read_text(encoding="utf-8")
    base = os.path.relpath(ICONS, page_path.parent).replace(os.sep, "/")
    ICONS.mkdir(parents=True, exist_ok=True)
    count = [0]

    def swap(m: re.Match) -> str:
        data = base64.b64decode(m.group(2))
        name = _save_bytes(data, EXT[m.group(1)])
        count[0] += 1
        return base + "/" + name

    new = DATA_URI.sub(swap, text)
    if new != text:
        page_path.write_text(new, encoding="utf-8")
    return count[0], len(text.encode()) - len(new.encode())


def _prefetch(ids: Iterable[int]) -> None:
    idx = load_index()
    dirty = False
    for sid in ids:
        key = str(sid)
        existed = key in idx and (ICONS / idx[key]).is_file()
        fname = fetch_icon(sid, idx)
        if not existed:
            dirty = True
        print(f"  {sid} -> guides/icons/{fname}" + ("" if existed else " (fetched)"))
    if dirty:
        save_index(idx)


def main() -> None:
    ap = argparse.ArgumentParser(description="Shared guide icon manager (guides/icons/).")
    ap.add_argument("--seed", action="store_true", help="Seed guides/icons/by-spell.json from existing icons.json")
    ap.add_argument("--fetch", nargs="+", type=int, metavar="SPELL_ID", help="Fetch missing spell icons via Wowhead")
    ap.add_argument("pages", nargs="*", help="HTML files to externalize base64 icons in place")
    args = ap.parse_args()

    if args.seed:
        added, total = seed_index()
        print(f"seeded {INDEX}: +{added} new, {total} total spells")
        return
    if args.fetch:
        _prefetch(args.fetch)
        return

    pages = args.pages or sorted(
        str(p)
        for d in GUIDES.iterdir() if d.is_dir() and d.name not in ("icons", "tools")
        for p in d.glob("*.html")
    )
    total = 0
    for p in pages:
        n, saved = externalize(p)
        total += saved
        if n:
            print(f"{os.path.relpath(p, GUIDES)}: {n} icons, -{saved // 1024} KB")
    print(f"total -{total // 1024} KB; icons in {ICONS}")


if __name__ == "__main__":
    main()
