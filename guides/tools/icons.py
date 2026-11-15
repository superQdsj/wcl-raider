"""Move base64 icons out of guide HTML into shared files under guides/icons/.

An icon is stored as guides/icons/<sha1 first 12 hex>.jpg, so the same icon
used by many guides is one file. The page links to it with a path relative to
the page. Running it again on a page that has no data URIs changes nothing.

usage: python3 guides/tools/icons.py [page.html ...]   (default: every guides/*/*.html)
From a build script: from icons import externalize; externalize(out)
"""
import base64
import hashlib
import os
import re
import sys

GUIDES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(GUIDES, "icons")
DATA_URI = re.compile(r"data:image/(jpeg|jpg|png|webp|gif);base64,([A-Za-z0-9+/=]+)")
EXT = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}


def externalize(page):
    """Rewrite one HTML file in place; return (icons replaced, bytes saved)."""
    page = os.path.abspath(page)
    with open(page, encoding="utf-8") as f:
        text = f.read()
    base = os.path.relpath(ICONS, os.path.dirname(page)).replace(os.sep, "/")
    os.makedirs(ICONS, exist_ok=True)
    count = [0]

    def swap(m):
        data = base64.b64decode(m.group(2))
        name = hashlib.sha1(data).hexdigest()[:12] + "." + EXT[m.group(1)]
        path = os.path.join(ICONS, name)
        if not os.path.exists(path):
            with open(path, "wb") as out:
                out.write(data)
        count[0] += 1
        return base + "/" + name

    new = DATA_URI.sub(swap, text)
    if new != text:
        with open(page, "w", encoding="utf-8") as f:
            f.write(new)
    return count[0], len(text.encode()) - len(new.encode())


if __name__ == "__main__":
    pages = sys.argv[1:] or sorted(
        os.path.join(GUIDES, d, f)
        for d in os.listdir(GUIDES) if os.path.isdir(os.path.join(GUIDES, d))
        for f in os.listdir(os.path.join(GUIDES, d)) if f.endswith(".html"))
    total = 0
    for p in pages:
        n, saved = externalize(p)
        total += saved
        if n:
            print(f"{os.path.relpath(p, GUIDES)}: {n} icons, -{saved // 1024} KB")
    print(f"total -{total // 1024} KB; icons in {ICONS}")
