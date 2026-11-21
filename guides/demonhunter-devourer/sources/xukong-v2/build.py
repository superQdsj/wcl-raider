"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-虚空之痕竞技场-噬灭恶魔猎手.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r1 (US +22, 26:24, hCfbYtnyc1aRvzrZ#45; same player as the talent string)
END = 26 * 60 + 20
BANDS = [('0:15', '2:38', '开场小怪', 'trash'), ('2:42', '6:13', '几丁高斯', 'trash'),
         ('6:20', '9:47', '塔兹拉尔', 'boss'), ('9:59', '11:54', '掠心者', 'trash'),
         ('12:04', '15:02', '阿特洛苏斯', 'boss'), ('15:14', '23:02', '虹虚魔 · 残虐者', 'trash'),
         ('23:02', '26:18', '煞戎努斯', 'boss')]
MARKS = [('0:29.2', 'e', 183752, '断挫志怒吼'), ('4:30.2', '', 198589, '疾影接险恶光环'),
         ('6:32.8', '', 198589, '疾影接空灵冲刺'), ('10:20.0', 'e', 1234195, '新星停熔岩箭'),
         ('10:23.9', 'v', 58984, '影遁甩虚空光束'), ('12:50.2', '', 198589, '疾影接剧毒光环'),
         ('16:05.3', '', 198589, '疾影接恐惧咆哮'), ('17:58.5', 'v', 58984, '影遁甩虚空光束'),
         ('19:01.3', 'e', 183752, '断熔岩箭'), ('21:26.8', 'e', 183752, '断愈体虚空'),
         ('25:11.0', '', 198589, '疾影接星辰坠击')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(163,48,201,')
         + ':root{--shadow:#5fc6d6;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>噬灭恶魔猎手 · 虚空之痕竞技场</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-虚空之痕竞技场-噬灭恶魔猎手.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))

# Icons live in guides/icons/; the page links to them instead of embedding base64.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.abspath(__file__).split("/guides/")[0], "guides", "tools"))
from icons import externalize
print("icons:", externalize(out))
