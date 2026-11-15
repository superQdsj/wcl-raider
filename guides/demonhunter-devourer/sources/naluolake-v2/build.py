"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-纳洛拉克的洞穴-噬灭恶魔猎手.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r2 (US +22, 26:35; most complete use of 疾影 / 黑暗 / 瓦解)
END = 26 * 60 + 35
BANDS = [('0:21', '4:08', '开场 · 饥荒雕像', 'trash'), ('4:08', '7:38', '囤宝狂人', 'boss'),
         ('7:51', '9:53', '地语看护者', 'trash'), ('10:08', '15:04', '冰川 · 决意化身', 'trash'),
         ('15:04', '18:12', '寒冬哨兵', 'boss'), ('18:46', '20:26', '图腾营地', 'trash'),
         ('21:18', '22:47', '纳尼亚', 'trash'), ('23:22', '26:35', '纳洛拉克', 'boss')]
MARKS = [('0:43.5', 'e', 183752, '断治疗之风'), ('2:06.0', '', 198589, '疾影接苦难盛宴'),
         ('4:16.9', '', 198589, '疾影接贪婪咆哮'), ('5:37.6', '', 198589, '疾影接饕餮怒吼'),
         ('6:54.2', '', 196718, '黑暗接饕餮怒吼'), ('8:07.0', 'e', 183752, '断大地之箭'),
         ('11:00.4', 'e', 183752, '断冰冷咆哮'), ('12:51.6', '', 198589, '疾影接冰川之墓'),
         ('16:08.4', 'e', 183752, '断寒冬帷幕'), ('19:16.1', '', 198589, '疾影接原始回响'),
         ('22:04.1', 'e', 183752, '断纳尼亚闪电箭'), ('23:29.7', '', 198589, '疾影接回响重击'),
         ('24:42.2', 'v', 1261776, '躲祖尔加拉身后')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(163,48,201,')
         + '.mk.start{transform:translateX(-22%)}\n:root{--shadow:#5fc6d6;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>噬灭恶魔猎手 · 纳洛拉克的洞穴</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-纳洛拉克的洞穴-噬灭恶魔猎手.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))

# Icons live in guides/icons/; the page links to them instead of embedding base64.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.abspath(__file__).split("/guides/")[0], "guides", "tools"))
from icons import externalize
print("icons:", externalize(out))
