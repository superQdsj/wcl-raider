"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-密谋小径-噬灭恶魔猎手.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r1 (US +22, 28:05, PMGFzxcybAv8pL24#4); talent string is r3 (majority picks)
END = 28 * 60 + 5
BANDS = [('0:11', '4:49', '开场小怪', 'trash'), ('4:49', '6:47', '凯斯媞亚', 'boss'),
         ('7:27', '8:26', '酒馆', 'trash'), ('8:26', '11:50', '赞恩', 'boss'),
         ('12:14', '16:20', '魔蝇 · 掠夺者', 'trash'), ('16:37', '20:24', '萨祖克斯', 'boss'),
         ('20:40', '23:49', '小鬼群', 'trash'), ('24:29', '28:00', '利希尔', 'boss')]
MARKS = [('0:15.7', 'e', 183752, '断邪能飞弹'), ('1:39.0', 'e', 183752, '断诱惑'),
         ('3:58.2', '', 198589, '疾影顶浮龙'), ('5:09.7', 'e', 183752, '断邪能风暴'),
         ('7:32.1', 'e', 183752, '断恶意评价'), ('9:58.1', '', 198589, '疾影接影舞步'),
         ('12:33.1', 'e', 183752, '断邪能之怒'), ('14:07.0', 'v', 58984, '影遁断吸取生命'),
         ('18:13.5', '', 198589, '疾影接碾压'), ('21:37.7', 'e', 1234195, '新星停邪火爆裂'),
         ('23:30.6', 'v', 58984, '影遁断吸取生命'), ('24:32.9', 'e', 183752, '断混乱之箭'),
         ('27:42.7', 'e', 1234195, '新星晕野生小鬼')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(163,48,201,')
         + '.mk.start{transform:translateX(-22%)}\n:root{--shadow:#5fc6d6;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>噬灭恶魔猎手 · 密谋小径</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-密谋小径-噬灭恶魔猎手.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))

# Icons live in guides/icons/; the page links to them instead of embedding base64.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.abspath(__file__).split("/guides/")[0], "guides", "tools"))
from icons import externalize
print("icons:", externalize(out))
