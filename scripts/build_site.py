#!/usr/bin/env python3
"""Build a public site from finished guide HTML only (Python standard library)."""

from html.parser import HTMLParser
from pathlib import Path
import shutil
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

from site_index import write_pages

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

    write_pages(guides, ROOT, OUTPUT)
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
