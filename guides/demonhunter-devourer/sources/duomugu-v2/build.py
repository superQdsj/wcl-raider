"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-夺目谷-噬灭恶魔猎手.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r1 (EU +22, 26:16, gmFq6n4aVG3KHTZj#18; same player as the talent string)
END = 26 * 60 + 25
BANDS = [('0:15', '4:22', '开场小怪', 'trash'), ('4:22', '8:15', '莱克希三人组', 'boss'),
         ('8:23', '9:32', '怪', 'trash'), ('9:32', '13:14', '伊库兹', 'boss'),
         ('13:44', '14:13', '', 'trash'), ('14:13', '18:27', '鲁伊亚', 'boss'),
         ('18:47', '22:37', '薯身蟾 · 播法者', 'trash'), ('22:37', '26:25', '兹欧凯特', 'boss')]
MARKS = [('0:32.5', '', 198589, '疾影接拔根而起'), ('1:54.9', 'e', 1234195, '新星停光箭雨'),
         ('6:01.9', '', 198589, '疾影接荆棘之刃'), ('7:07.0', 'e', 183752, '断光芒箭'),
         ('9:19.7', 'e', 183752, '断迷乱尖叫'), ('12:59.3', 'v', 58984, '影遁脱根'),
         ('13:07.1', '', 196718, '黑暗接咆哮'), ('15:12.2', 'e', 183752, '断种子射击'),
         ('17:47.0', '', 198589, '疾影接光明之火'), ('23:06.3', '', 198589, '疾影接光绽之力'),
         ('23:45.3', 'e', 1234195, '新星晕鞭笞者')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(163,48,201,')
         + '.mk.start{transform:translateX(-22%)}\n:root{--shadow:#5fc6d6;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>噬灭恶魔猎手 · 夺目谷</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-夺目谷-噬灭恶魔猎手.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))
