import argparse
import base64
import json
import re
from html.parser import HTMLParser
from pathlib import Path


GUIDES = [
    ("duomugu", "src.html", "夺目谷"),
    ("hongyu", "rogue.src.html", "红玉新生法池"),
    ("mimouxiaojing", "src.html", "密谋小径"),
    ("naluolake", "src.html", "纳洛拉克的洞穴"),
    ("saitalisi", "rogue.src.html", "塞塔里斯神庙"),
    ("xukong", "src.html", "虚空之痕竞技场"),
    ("zhuwang", "rogue.src.html", "诸王之眠"),
]


class ImageValidator(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        source = dict(attrs).get("src", "")
        if not source.startswith("data:image/") or ";base64," not in source:
            raise ValueError("Image is not embedded: " + source[:80])
        payload = source.split(",", 1)[1]
        if not base64.b64decode(payload, validate=True):
            raise ValueError("Image payload is empty")


def render(directory, filename):
    text = (directory / filename).read_text(encoding="utf-8")
    icons = json.loads((directory / "icons.json").read_text(encoding="utf-8"))
    talent = json.loads((directory / "tstring.json").read_text(encoding="utf-8"))
    text = re.sub(r"\{\{I:(\d+)\}\}", lambda match: icons[match[1]], text)
    text = re.sub(
        r"\{\{T:(\d+)\}\}",
        lambda match: "data:image/jpeg;base64,"
        + base64.b64encode(
            (directory / "ticons" / (match[1] + ".jpg")).read_bytes()
        ).decode("ascii"),
        text,
    )
    if not talent.get("string"):
        raise ValueError("Talent import string is empty")
    text = text.replace("{{TALENT}}", talent["string"])
    if "{{" in text:
        raise ValueError("Unresolved template placeholder")
    validator = ImageValidator()
    validator.feed(text)
    validator.close()
    return text


def main():
    parser = argparse.ArgumentParser(description="Rebuild archived rogue HTML guides offline")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--include-original", action="store_true")
    args = parser.parse_args()
    sources = Path(__file__).resolve().parent / "sources"
    guides = list(GUIDES)
    if args.include_original:
        guides.insert(0, ("", "rogue.src.html", "毒牙祭坛"))
    rendered = [
        (name, render(sources / folder, filename))
        for folder, filename, name in guides
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, text in rendered:
        output = args.output_dir / ("2026-10-28-" + name + "-潜行者.html")
        output.write_text(text, encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
