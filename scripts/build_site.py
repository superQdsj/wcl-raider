#!/usr/bin/env python3
"""Build a public site from finished guide HTML only (Python standard library)."""

from html import escape, unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import quote, unquote, urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "site"
TEMPLATE = ROOT / "site"
# Display order. color is the in-game class color; on is the text color on it;
# glyph is the single character on the spec's seal.
CLASSES = {
    "demonhunter-devourer": dict(name="噬灭恶魔猎手", short="噬灭", family="恶魔猎手", role="远程输出", color="#A330C9", on="#FFFFFF", glyph="噬"),
    "warrior-arms": dict(name="武器战", short="武器", family="战士", role="近战输出", color="#C69B6D", on="#14110D", glyph="武"),
    "rogue": dict(name="潜行者", family="潜行者", short="潜行", role="近战输出", color="#FFF468", on="#14130A", glyph="潜"),
    "holy-paladin": dict(name="神圣骑士", short="神圣", family="圣骑士", role="治疗", color="#F48CBA", on="#1A0F14", glyph="圣"),
    "paladin-ret": dict(name="惩戒骑士", short="惩戒", family="圣骑士", role="近战输出", color="#F48CBA", on="#1A0F14", glyph="惩"),
}
DUNGEONS = ["夺目谷", "塞塔里斯神庙", "密谋小径", "毒牙祭坛",
            "红玉新生法池", "纳洛拉克的洞穴", "虚空之痕竞技场", "诸王之眠"]
LEDE = re.compile(r'<p class="lede">(.*?)</p>', re.S)
BOLD = re.compile(r"<b>(.*?)</b>", re.S)
TAG = re.compile(r"<[^>]+>")


def _text(fragment):
    return " ".join(unescape(TAG.sub("", fragment)).split())


def _meta(path):
    """Date, dungeon, title, lede and up to three short key skills from a guide."""
    parts = path.stem.split("-")
    html_text = path.read_text(encoding="utf-8")
    m = LEDE.search(html_text)
    lede = _text(m.group(1)) if m else ""
    keys = []
    for b in BOLD.findall(m.group(1)) if m else []:
        k = _text(b)
        if 2 <= len(k) <= 7 and not re.search(r"[，、。,+→：]", k) and k not in keys:
            keys.append(k)
    title = re.search(r"<title>(.*?)</title>", html_text, re.S)
    return {"date": "-".join(parts[:3]),
            "dungeon": next((p for p in parts[3:] if p in DUNGEONS), None),
            "title": unescape(title.group(1)).strip() if title else path.stem,
            "lede": lede, "keys": keys[:3],
            "href": "/" + quote(path.relative_to(ROOT).as_posix())}


def site_data(guides):
    classes = []
    for slug, pages in guides:
        by, extras = {}, []
        for e in map(_meta, pages):  # newest first, so the first per dungeon is current
            if e["dungeon"]:
                by.setdefault(e["dungeon"], []).append(e)
            else:
                extras.append({k: e[k] for k in ("title", "href", "lede")})
        current = {d: {**v[0], "old": [{"href": o["href"], "date": o["date"]} for o in v[1:]]}
                   for d, v in by.items()}
        classes.append({"slug": slug, **CLASSES[slug], "guides": current, "extras": extras})
    return {"dungeons": DUNGEONS, "classes": classes}


def write_pages(data):
    plain = "".join(
        f'<h2>{escape(c["name"])}</h2><ul>' + "".join(
            f'<li><a href="{g["href"]}">{escape(d)}</a></li>' for d, g in c["guides"].items()) + "</ul>"
        for c in data["classes"])
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    index = (TEMPLATE / "index.html").read_text(encoding="utf-8")
    index = index.replace("__NOSCRIPT__", f'<div class="plain">{plain}</div>').replace("__DATA__", payload)
    (OUTPUT / "index.html").write_text(index, encoding="utf-8")
    for name in ("404.html", "site.css", "site.js"):
        shutil.copyfile(TEMPLATE / name, OUTPUT / name)
    (OUTPUT / "assets").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "assets" / "icon.svg", OUTPUT / "assets" / "icon.svg")


class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key not in ("src", "href") or not value:
                continue
            parsed = urlsplit(value)
            if not parsed.scheme and not parsed.netloc and parsed.path:
                self.paths.append(unquote(parsed.path))


def main():
    guides = [(slug, sorted((ROOT / "guides" / slug).glob("*.html"), reverse=True))
              for slug in CLASSES]
    files = {p for _, pages in guides for p in pages}
    if not files:
        raise SystemExit("No finished guides found")
    # Validate before touching the existing build. Only finished pages and their
    # explicitly linked images are permitted in the public output.
    for page in tuple(files):
        parser = LocalLinks()
        parser.feed(page.read_text(encoding="utf-8"))
        for link in parser.paths:
            asset = (page.parent / link).resolve()
            if asset in files:
                continue
            if (not asset.is_relative_to(page.parent.resolve())
                    or asset.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"}
                    or not asset.is_file()):
                raise SystemExit(f"Unsupported or missing local link: {page.relative_to(ROOT)} -> {link}")
            files.add(asset)
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    for source in sorted(files):
        target = OUTPUT / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    write_pages(site_data(guides))
    (OUTPUT / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n", encoding="utf-8")
    archive = ROOT / "dist" / "wcl-raider-site.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        for path in sorted(OUTPUT.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(OUTPUT))
    print(f"Built {sum(len(pages) for _, pages in guides)} guides: {OUTPUT}")
    print(f"Upload archive: {archive}")


if __name__ == "__main__":
    main()
