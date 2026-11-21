"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-塞塔里斯神庙-噬灭恶魔猎手.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r1 (EU +22, 28:08, rL6J8cZhbHQ2zxVD#10) — has every technique on the page
END = 28 * 60 + 8
BANDS = [('0:13', '1:30', '开场', 'trash'), ('1:30', '5:26', '阿德里斯与阿斯匹克斯', 'boss'),
         ('5:36', '11:05', '毒蛇与三叶虫', 'trash'), ('11:10', '14:44', '米利克萨', 'boss'),
         ('14:50', '17:19', '雷云', 'trash'), ('17:26', '20:57', '加瓦兹特', 'boss'),
         ('21:13', '24:51', '宝珠守望者', 'trash'), ('24:53', '28:02', '塞塔里斯的化身', 'boss')]
MARKS = [('0:40.7', '', 198589, '疾影接震地'), ('1:42.7', '', 198589, '疾影接阵风'),
         ('6:52.2', 'e', 217832, '禁锢停箭雨'), ('9:09.8', 'e', 183752, '断扰乱心智'),
         ('13:09.5', '', 198589, '疾影接雷霆喷吐'), ('15:27.0', 'e', 278326, '吞噬偷积攒电荷'),
         ('16:56.2', '', 198589, '疾影接释放电荷'), ('18:45.4', '', 198589, '疾影拦光束'),
         ('22:54.2', '', 196718, '黑暗接蚀骨践踏'), ('26:02.0', 'e', 1234195, '虚空新星晕折磨者'),
         ('27:00.3', '', 198589, '疾影顶腐化')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(163,48,201,')
         + ':root{--shadow:#5fc6d6;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>噬灭恶魔猎手 · 塞塔里斯神庙</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-塞塔里斯神庙-噬灭恶魔猎手.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))

# Icons live in guides/icons/; the page links to them instead of embedding base64.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.abspath(__file__).split("/guides/")[0], "guides", "tools"))
from icons import externalize
print("icons:", externalize(out))
