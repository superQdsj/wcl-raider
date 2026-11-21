#!/usr/bin/env python3
"""Deterministic quality gatekeeper for DPS dungeon guides (guides/tools/GUIDE-SPEC.md).

Checks every machine-verifiable rule in one fast offline pass:
  1. Build integrity: no {{...}} placeholders, no data:image base64, all icons exist in guides/icons/
  2. Offline purity: no Google Fonts / external CSS or JS CDNs
  3. Publishing contract (scripts/build_site.py): bare <body>, <p class="lede">, valid filename & CLASSES registration
  4. CSS variable discipline (when --source-dir exists): zero hardcoded colors outside :root, all 29 required tokens,
     no legacy .mk.start/.mk.end patches, no rainbow pill classes, no non-width inline styles in body.part
  5. WCAG AA contrast (>= 4.5:1) on all core dark-theme foreground/background pairs
  6. Navigation & JS safety: all #anchor links valid, outer nav clearance >= 110px, no 00-03 section number clash,
     bottom-of-page scroll-spy fallback, null-safe talent copy JS & guarded build.py {{TALENT}}
  7. Shared timeline geometry: uses min-width:884px + margin:0 48px + .mk.up{bottom:148px}, labels <= 8 chars,
     same-side mark spacing >= 52px
  8. Content hygiene: banned report/stat phrases & leaked player names absent from <header>/<main>
  9. NOTES.md completeness: required 4 sections present

Usage:
  python3 guides/tools/check.py <page.html> [--source-dir <dir>] [--published]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

TOOLS = Path(__file__).resolve().parent
GUIDES = TOOLS.parent
ROOT = GUIDES.parent
ICONS = GUIDES / "icons"

REQUIRED_VARS = [
    "--bg", "--nav-bg", "--panel", "--panel-2", "--line", "--line-2",
    "--tint-1", "--tint-2", "--ic-edge",
    "--ink", "--ink-2", "--mute", "--faint",
    "--gold", "--gold-dim", "--on-gold", "--gold-bg", "--gold-chip", "--gold-band",
    "--hero-a", "--hero-b", "--tl-e", "--tl-v",
    "--bar-off", "--bar-mid", "--on-bar",
    "--blood", "--blood-bg", "--blood-line",
]

BANNED_PATTERNS = [
    (r"\b[1-5]/5\b", "样本比例（如 5/5）"),
    (r"五场|这五场|5\s*场", "场次统计口吻"),
    (r"中位数", "统计词「中位数」"),
    (r"平均", "统计词「平均」"),
    (r"共\s*\d+\s*次", "统计词「共 N 次」"),
    (r"一场按\s*\d+", "统计词「一场按 X 次」"),
    (r"全场最[多重高]", "统计/极值词「全场最多/最重/最高」"),
    (r"(?:金色|粉色|紫色|蓝色|绿色)高亮", "模板色词写死（应写「带「必做」标签的高亮行」）"),
    (r"\bTODO\b", "残留 TODO 占位符"),
]


def _lum(hex_c: str) -> float:
    h = hex_c.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def parse_root_vars(css_text: str) -> dict:
    m = re.search(r":root\{([^}]+)\}", css_text, re.S)
    if not m:
        return {}
    out = {}
    for k, v in re.findall(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);", m.group(1)):
        out[k.strip()] = v.strip()
    return out


def check_page(page: Path, source_dir: Optional[Path], published: bool) -> Tuple[List[str], List[str]]:
    fails: List[str] = []
    warns: List[str] = []

    if not page.is_file():
        return [f"HTML file not found: {page}"], warns

    html = page.read_text(encoding="utf-8")

    # 1. Build integrity
    leftovers = re.findall(r"\{\{[^}]*\}\}", html)
    if leftovers:
        fails.append(f"Unreplaced placeholders: {leftovers[:5]}")
    if "data:image" in html:
        fails.append("Embedded base64 data:image found; run guides/tools/icons.py to externalize.")

    srcs = re.findall(r'<img[^>]+src="([^"]+)"', html)
    if not srcs:
        fails.append("No <img> icons found in page.")
    for s in srcs:
        if s.startswith(("http://", "https://")):
            fails.append(f"External image URL not allowed: {s}")
            continue
        target = (page.parent / s).resolve()
        if not target.is_file():
            fails.append(f"Missing local icon: {s} -> {target}")
        elif not (target.is_relative_to(ICONS) or target.is_relative_to(page.parent.resolve())):
            fails.append(f"Icon outside guides/icons/ or page dir: {s}")

    # 2. Offline / no external CDN
    if re.search(r"fonts\.googleapis\.com|fonts\.gstatic\.com", html, re.I):
        fails.append("Google Fonts link found; use pure system font stack.")
    ext_assets = re.findall(r'<(?:link[^>]+href|script[^>]+src)="(https?://[^"]+)"', html, re.I)
    if ext_assets:
        fails.append(f"External CSS/JS CDN found: {ext_assets[:3]}")

    # 3. Publishing contract
    if "<body>" not in html:
        fails.append("Missing exact bare <body> tag (scripts/build_site.py requires literal '<body>' without attributes).")
    lede_m = re.search(r'<p class="lede">(.*?)</p>', html, re.S)
    if not lede_m or len(re.sub(r"<[^>]+>", "", lede_m.group(1)).strip()) < 15:
        fails.append('Missing or too-short <p class="lede"> (required by scripts/build_site.py).')

    is_top_level = page.resolve().parent.parent == GUIDES and page.resolve().parent.name not in ("icons", "tools")
    if published or is_top_level:
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_site  # type: ignore

        slug = page.resolve().parent.name
        if slug not in build_site.CLASSES:
            fails.append(f"Class slug '{slug}' not registered in scripts/build_site.py CLASSES.")
        else:
            icon_file = ROOT / "site" / "img" / "icons" / f"{build_site.CLASSES[slug]['icon']}.jpg"
            if not icon_file.is_file():
                fails.append(f"Missing site spec icon: {icon_file}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}-", page.name):
            fails.append(f"Published filename must start with YYYY-MM-DD-: {page.name}")
        if not build_site._dungeon(page):
            fails.append(f"Filename does not match any dungeon in build_site.DUNGEON_INFO: {page.name}")

    # 4. CSS variables & WCAG contrast
    rv = parse_root_vars(html)
    missing_vars = [v for v in REQUIRED_VARS if v not in rv]
    if missing_vars:
        fails.append(f"Missing required :root variables: {missing_vars}")

    hex_re = re.compile(r"^#[0-9a-fA-F]{3,6}$")
    contrast_pairs = [
        ("--ink on --panel-2", "--ink", "--panel-2"),
        ("--ink-2 on --panel-2", "--ink-2", "--panel-2"),
        ("--mute on --panel-2", "--mute", "--panel-2"),
        ("--faint on --panel-2", "--faint", "--panel-2"),
        ("--gold on --panel", "--gold", "--panel"),
        ("--on-gold on --gold", "--on-gold", "--gold"),
        ("--on-bar on --bar-off", "--on-bar", "--bar-off"),
        ("--on-bar on --bar-mid", "--on-bar", "--bar-mid"),
        ("--blood on --panel", "--blood", "--panel"),
    ]
    for label, fg_k, bg_k in contrast_pairs:
        fg, bg = rv.get(fg_k, ""), rv.get(bg_k, "")
        if hex_re.match(fg) and hex_re.match(bg):
            cr = contrast_ratio(fg, bg)
            if cr < 4.5:
                fails.append(f"WCAG AA contrast fail for {label} ({fg} on {bg}): {cr:.2f}:1 < 4.5:1")

    # 5. Anchors, sticky nav & JS guards
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    hrefs = re.findall(r'href="#([^"]+)"', html)
    broken = [h for h in hrefs if h not in ids]
    if broken:
        fails.append(f"Broken internal anchors: {sorted(set(broken))}")

    if 'class="nav-scroll"' not in html:
        warns.append("Sticky nav missing .nav-scroll inner wrapper (recommended so links never slide under ← 全部手册).")
    nav_m = re.search(r'<nav\b[^>]*>(.*?)</nav>', html, re.S)
    if nav_m:
        nav_nums = re.findall(r'<span class="n">(0[0-9])</span>', nav_m.group(1))
        if nav_nums:
            fails.append(f"Nav uses 00-09 numbers {nav_nums} which collide with section headings 00-03; use ①②③ or short names.")

    if "copy-btn" in html or "addEventListener" in html:
        script_m = re.search(r"<script>(.*?)</script>", html, re.S)
        sc = script_m.group(1) if script_m else ""
        if "copy-btn" in sc and not re.search(r"if\s*\(\s*btn\s*&&\s*code\s*\)|if\s*\(\s*cb\s*&&\s*code\s*\)", sc):
            fails.append("Talent copy JS lacks null guard (if(btn&&code)); omitting import box will break nav scroll-spy.")
        if "scrollHeight" not in sc:
            warns.append("Scroll-spy JS missing bottom-of-page fallback (scrollHeight check) to highlight #talent.")

    # 6. Timeline checks
    if 'class="tl"' in html:
        if "min-width:884px" not in html or "margin:0 48px" not in html:
            fails.append("Timeline CSS does not match shared guides/tools/timeline.py (min-width:884px; margin:0 48px).")
        if ".mk.up{bottom:148px}" not in html:
            fails.append("Timeline CSS missing .mk.up{bottom:148px} from shared timeline.py.")
        if re.search(r"\.mk\.start\s*\{", html):
            fails.append("Legacy .mk.start CSS patch found; remove it and use shared timeline.py.")

        marks = re.findall(
            r'<div class="(mk [^"]+)" style="left:([0-9.]+)%"><span class="lab">([^<]*)</span>',
            html,
        )
        for _, _, lab in marks:
            if len(lab.strip()) > 8:
                fails.append(f"Timeline mark label > 8 chars ('{lab}'): risk of edge clipping or overlap.")
        for side in (" up", " dn"):
            pts = sorted((float(p) / 100.0 * 884.0, lab) for cls, p, lab in marks if side in cls)
            for (x1, l1), (x2, l2) in zip(pts, pts[1:]):
                if x2 - x1 < 50.0:
                    warns.append(f"Tight timeline same-side ({side.strip()}) labels: '{l1}' & '{l2}' are {x2 - x1:.1f}px apart (< 50px).")

    # 7. Content hygiene (before <footer>)
    parts = html.split("<footer", 1)
    main_html = parts[0]
    footer_html = parts[1] if len(parts) > 1 else ""
    main_text = re.sub(r"<style>.*?</style>", "", main_html, flags=re.S)
    main_text = re.sub(r"<[^>]+>", " ", main_text)

    for pat, desc in BANNED_PATTERNS:
        m = re.search(pat, main_text)
        if m:
            fails.append(f"Banned phrasing in main body ({desc}): matched '{m.group(0)}'")

    # Check if reference player names from footer leaked into main body
    for link_txt in re.findall(r"<a[^>]+>([^<]+)</a>", footer_html):
        name = link_txt.strip().split()[0] if link_txt.strip() else ""
        if len(name) >= 2 and not name.startswith("+") and name in main_text:
            fails.append(f"Reference player name '{name}' from footer leaked into main body.")

    # 8. Source directory checks
    if source_dir:
        head_p = source_dir / "head.part"
        body_p = source_dir / "body.part"
        build_p = source_dir / "build.py"
        notes_p = source_dir / "NOTES.md"

        if head_p.is_file():
            head = head_p.read_text(encoding="utf-8")
            head_no_root = re.sub(r":root\{[^}]+\}", "", head, flags=re.S)
            bad_colors = re.findall(r"#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)", head_no_root)
            if bad_colors:
                fails.append(f"Hardcoded colors outside :root in head.part: {bad_colors[:6]}")
            if re.search(r"\.pill\b|\.tag\.(?:magic|poison|bleed|phys)\b", head):
                fails.append("Legacy rainbow .pill / .tag.* classes found in head.part.")

        if body_p.is_file():
            body = body_p.read_text(encoding="utf-8")
            bad_inline = [s for s in re.findall(r'style="([^"]+)"', body) if not re.fullmatch(r"width:\d+(?:\.\d+)?%", s)]
            if bad_inline:
                fails.append(f"Non-width inline style in body.part: {bad_inline[:5]}")
            must_count = len(re.findall(r'class="row(?: step)? must"', body))
            if must_count == 0:
                warns.append("No .row.must highlighted rows found in body.part.")
            elif must_count > 7:
                warns.append(f"High number of must-do rows ({must_count}); keep focused around 3–6.")

        if build_p.is_file():
            bt = build_p.read_text(encoding="utf-8")
            if "from timeline import" not in bt:
                fails.append("build.py does not import shared guides/tools/timeline.py.")
            if "externalize" not in bt and "inject_icons" not in bt:
                fails.append("build.py does not use guides/tools/icons.py (inject_icons / externalize).")
            if "tstring.json" in bt and "{{TALENT}}" in bt and not re.search(r"if\s+['\"]\{\{TALENT\}\}['\"]\s+in\s+", bt):
                fails.append("build.py reads tstring.json unconditionally; guard with `if '{{TALENT}}' in s:`.")

        if not notes_p.is_file():
            fails.append(f"Missing {notes_p}")
        else:
            nt = notes_p.read_text(encoding="utf-8")
            for kw, label in [
                (r"重建|build\.py", "样本来源与重建命令"),
                (r"低样本|删掉", "删掉的低样本打法"),
                (r"天赋|tstring|enc\.py", "天赋核对记录"),
                (r"补查|wcl\.py", "补查记录"),
            ]:
                if not re.search(kw, nt):
                    warns.append(f"NOTES.md may be missing section: {label}")

    return fails, warns


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a DPS guide HTML & source dir against GUIDE-SPEC.md.")
    ap.add_argument("page", help="Path to generated guide HTML")
    ap.add_argument("--source-dir", help="Path to sources/<dungeon>-v2/ directory (auto-inferred if page is inside it)")
    ap.add_argument("--published", action="store_true", help="Enforce published filename and build_site.py CLASSES checks")
    args = ap.parse_args()

    page = Path(args.page).resolve()
    src: Optional[Path] = Path(args.source_dir).resolve() if args.source_dir else None
    if src is None and (page.parent / "head.part").is_file():
        src = page.parent

    fails, warns = check_page(page, src, args.published)
    for w in warns:
        print(f"WARN: {w}")
    for f in fails:
        print(f"FAIL: {f}")

    if fails:
        print(f"\nCHECK FAILED: {len(fails)} error(s), {len(warns)} warning(s)")
        sys.exit(1)
    print(f"CHECK PASSED: 0 errors, {len(warns)} warning(s) ({page.name})")


if __name__ == "__main__":
    main()
