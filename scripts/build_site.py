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
ICONS = (ROOT / "guides" / "icons").resolve()  # shared spell icons, see guides/tools/icons.py
# Display order. Every spec is named the same way: spec + class (敏锐 + 潜行者).
# color is the in-game class color; icon is the in-game spec icon in site/img/icons/.
CLASSES = {
    "demonhunter-devourer": dict(en="Devourer Demon Hunter", spec="噬灭", cls="恶魔猎手", role="远程输出", color="#A330C9", icon="classicon_demonhunter_void"),
    "warrior-arms": dict(en="Arms Warrior", spec="武器", cls="战士", role="近战输出", color="#C69B6D", icon="ability_warrior_savageblow"),
    "rogue": dict(en="Subtlety Rogue", spec="敏锐", cls="潜行者", role="近战输出", color="#FFF468", icon="ability_stealth"),
    "holy-paladin": dict(en="Holy Paladin", spec="神圣", cls="圣骑士", role="治疗", color="#F48CBA", icon="spell_holy_holybolt"),
    "paladin-ret": dict(en="Retribution Paladin", spec="惩戒", cls="圣骑士", role="近战输出", color="#F48CBA", icon="spell_holy_auraoflight"),
}
# Chinese name, English name, card image site/img/dungeons/<img>.jpg.
DUNGEON_INFO = [
    ("夺目谷", "The Blinding Vale", "vale"),
    ("塞塔里斯神庙", "Temple of Sethraliss", "sethraliss"),
    ("密谋小径", "Murder Row", "murder"),
    ("毒牙祭坛", "Altar of Fangs", "altar"),
    ("红玉新生法池", "Ruby Life Pools", "ruby"),
    ("纳洛拉克的洞穴", "Den of Nalorakk", "nalorakk"),
    ("虚空之痕竞技场", "Voidscar Arena", "voidscar"),
    ("诸王之眠", "Kings' Rest", "kingsrest"),
]
DUNGEONS = [d[0] for d in DUNGEON_INFO]
LEDE = re.compile(r'<p class="lede">(.*?)</p>', re.S)
TAG = re.compile(r"<[^>]+>")
# Guides are standalone pages with no way back; the published copy gets this link.
HOME_LINK = ('<a href="/" style="position:fixed;z-index:50;top:12px;right:12px;padding:5px 12px;border-radius:999px;'
             'font:500 13px/1.4 system-ui,sans-serif;color:#d6d2c4;background:rgba(16,14,13,.86);border:1px solid #3a342f;'
             'text-decoration:none;backdrop-filter:blur(6px)">← 全部手册</a>')


def _text(fragment):
    return " ".join(unescape(TAG.sub("", fragment)).split())


def _dungeon(path):
    return next((p for p in path.stem.split("-")[3:] if p in DUNGEONS), None)


def _meta(path):
    """Date, dungeon and lede of a guide."""
    parts = path.stem.split("-")
    html_text = path.read_text(encoding="utf-8")
    m = LEDE.search(html_text)
    lede = _text(m.group(1)) if m else ""
    return {"date": "-".join(parts[:3]),
            "dungeon": _dungeon(path),
            "lede": lede,
            "href": "/" + quote(path.relative_to(ROOT).as_posix())}


def site_data(guides):
    classes = []
    for slug, pages in guides:
        by = {}
        for e in map(_meta, pages):  # newest first, so the first per dungeon is current
            by.setdefault(e["dungeon"], []).append(e)
        current = {d: {**v[0], "old": [{"href": o["href"], "date": o["date"]} for o in v[1:]]}
                   for d, v in by.items()}
        classes.append({"slug": slug, **CLASSES[slug], "guides": current})
    dungeons = [{"name": n, "en": en, "img": img} for n, en, img in DUNGEON_INFO]
    return {"dungeons": dungeons, "classes": classes}


def write_pages(data):
    plain = "".join(
        f'<h2>{escape(c["spec"] + c["cls"])}</h2><ul>' + "".join(
            f'<li><a href="{g["href"]}">{escape(d)}</a></li>' for d, g in c["guides"].items()) + "</ul>"
        for c in data["classes"])
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    index = (TEMPLATE / "index.html").read_text(encoding="utf-8")
    index = index.replace("__NOSCRIPT__", f'<div class="plain">{plain}</div>').replace("__DATA__", payload)
    (OUTPUT / "index.html").write_text(index, encoding="utf-8")
    for name in ("404.html", "site.css", "site.js"):
        shutil.copyfile(TEMPLATE / name, OUTPUT / name)
    shutil.copytree(TEMPLATE / "img", OUTPUT / "img")
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
    guides, hubs = [], {}
    for slug in CLASSES:
        pages = sorted((ROOT / "guides" / slug).glob("*.html"), reverse=True)
        guides.append((slug, [p for p in pages if _dungeon(p)]))
        # Per-class contents pages predate the home page and go stale; they are not
        # published, and links to them lead to that class on the home page instead.
        hubs.update({p.resolve(): slug for p in pages if not _dungeon(p)})
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
            if asset in files or asset in hubs:
                continue
            # Images must sit next to the page or in the shared guides/icons/.
            if (not (asset.is_relative_to(page.parent.resolve()) or asset.is_relative_to(ICONS))
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
        if source.suffix == ".html":
            text = source.read_text(encoding="utf-8").replace("<body>", "<body>" + HOME_LINK, 1)
            for hub, slug in hubs.items():
                if hub.parent == source.parent:
                    text = re.sub(r'href="%s"([^>]*)>[^<]*<' % re.escape(hub.name),
                                  r'href="/#%s"\1>返回全部手册<' % slug, text)
            target.write_text(text, encoding="utf-8")
        else:
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
