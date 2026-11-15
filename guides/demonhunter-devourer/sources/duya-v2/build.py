"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-毒牙祭坛-噬灭恶魔猎手.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r1 (US +22, 27:03, myKVjGMJZ68DRp1w#68; same player as the talent string)
END = 27 * 60 + 3
BANDS = [('0:14', '6:05', '开场 · 仪式首领 · 毒蛇', 'trash'), ('6:05', '10:17', '拉维', 'boss'),
         ('10:26', '13:17', '扭缠蛇 · 进化者', 'trash'), ('13:24', '16:33', '扭缠盘蛇', 'boss'),
         ('16:41', '22:51', '晋升之蛇 · 神选者', 'trash'), ('23:04', '26:57', '祖尔加', 'boss')]
MARKS = [('0:41.0', 'e', 183752, '断刺耳嘶鸣'), ('2:12.0', '', 198589, '疾影接鲜血献祭'),
         ('3:11.8', '', 196718, '黑暗接鲜血献祭'), ('6:50.7', '', 198589, '疾影顶三重喷吐'),
         ('10:53.0', '', 198589, '疾影接振响'), ('11:20.6', 'e', 183752, '断毒伤'),
         ('15:44.5', 'muted', 1287798, '藤蔓之握撕盘蛇'), ('18:07.3', '', 198589, '疾影顶感染'),
         ('20:04.1', '', 198589, '疾影接剧毒涌动'), ('23:13.1', 'muted', 1300876, '拦毒牙光束'),
         ('23:57.3', '', 198589, '疾影进飞斧清毒液'), ('26:07.2', '', 198589, '疾影进飞斧清毒液')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(163,48,201,')
         + '.mk.start{transform:translateX(-22%)}\n:root{--shadow:#5fc6d6;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>噬灭恶魔猎手 · 毒牙祭坛</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-毒牙祭坛-噬灭恶魔猎手.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))
