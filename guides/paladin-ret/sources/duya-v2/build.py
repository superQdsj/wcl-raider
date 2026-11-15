"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-毒牙祭坛-惩戒骑.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r1 (CN +23, 27:56, DbynTmWQLZakHxp2#22; same player as the talent string)
END = 28 * 60 + 5
BANDS = [('0:18', '5:54', '开场 · 仪式首领 · 毒蛇', 'trash'), ('6:13', '10:26', '拉维', 'boss'),
         ('10:41', '13:10', '扭缠蛇 · 进化者', 'trash'), ('13:19', '16:46', '扭缠盘蛇', 'boss'),
         ('16:59', '23:31', '晋升之蛇 · 神选者', 'trash'), ('23:36', '28:05', '祖尔加', 'boss')]
MARKS = [('0:34.1', 'e', 96231, '断刺耳嘶鸣'), ('3:49.7', '', 1022, '保护清鲜血献祭'),
         ('5:02.4', '', 1044, '自由解麻痹射击'), ('6:29.6', '', 403876, '圣佑顶毒球'),
         ('8:22.0', '', 642, '圣盾清毒球·接牺牲'), ('10:54.7', 'e', 96231, '断毒伤'),
         ('12:17.1', '', 6940, '牺牲清毒伤'), ('13:36.4', 'e', 96231, '断剧毒萎缩'),
         ('17:25.2', '', 642, '圣盾免疫感染'), ('19:38.3', 'e', 96231, '断群体毒伤'),
         ('22:54.8', '', 642, '圣盾＋保护清献祭'), ('24:15.5', '', 6940, '牺牲给飞斧目标')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(243,156,195,')
         + '.mk.start{transform:translateX(-22%)}\n:root{--shadow:#b48cf0;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>惩戒骑 · 毒牙祭坛</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-毒牙祭坛-惩戒骑.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))

# Icons live in guides/icons/; the page links to them instead of embedding base64.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.abspath(__file__).split("/guides/")[0], "guides", "tools"))
from icons import externalize
print("icons:", externalize(out))
