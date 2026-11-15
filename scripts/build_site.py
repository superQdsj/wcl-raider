#!/usr/bin/env python3
"""Build a public site from finished guide HTML only (Python standard library)."""

from html import escape
from html.parser import HTMLParser
from pathlib import Path
import shutil
from urllib.parse import quote, unquote, urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "site"
CLASSES = {
    "demonhunter-devourer": "噬灭恶魔猎手",
    "warrior-arms": "武器战",
    "rogue": "潜行者",
    "holy-paladin": "神圣骑士",
    "paladin-ret": "惩戒骑士",
}


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

    sections = []
    for slug, pages in guides:
        links = "\n".join(
            f'<li><a href="{quote(p.relative_to(ROOT).as_posix())}">{escape(p.stem)}</a></li>'
            for p in pages
        )
        sections.append(f'<section><h2>{CLASSES[slug]}</h2><ul>{links}</ul></section>')
    (OUTPUT / "index.html").write_text('''<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>大秘境攻略 · wcl-raider</title>
<style>
body{max-width:860px;margin:48px auto;padding:0 20px;font:16px/1.7 system-ui,sans-serif;color:#222;background:#fafafa}
h1{font-size:28px}h2{font-size:20px;margin-top:32px}a{color:#2458a6;overflow-wrap:anywhere}li{margin:8px 0}p{color:#666}
</style>
<h1>大秘境攻略</h1>
<p>首页整理中，攻略可以通过以下链接阅读。</p>
''' + "\n".join(sections) + "\n</html>\n", encoding="utf-8")
    (OUTPUT / "404.html").write_text('''<!doctype html><html lang="zh-CN">
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>页面未找到</title><h1>页面未找到</h1><p><a href="/">返回攻略首页</a></p></html>
''', encoding="utf-8")
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
