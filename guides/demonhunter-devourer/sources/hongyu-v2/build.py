"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-红玉新生法池-噬灭恶魔猎手.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r1 (US +22, 25:02; same player as the talent string)
END = 25 * 60 + 13
BANDS = [('0:10', '3:17', '开场小怪', 'trash'), ('3:17', '6:42', '梅莉杜莎', 'boss'),
         ('7:17', '13:40', '火焰区小怪', 'trash'), ('13:40', '17:42', '柯姬雅', 'boss'),
         ('17:52', '21:35', '风暴区小怪', 'trash'), ('21:35', '25:13', '基拉卡 · 厄克哈特', 'boss')]
MARKS = [('0:23.1', '', 198589, '疾影接采掘冲击'), ('1:41.2', '', 198589, '疾影接钢铁弹幕'),
         ('3:26.3', 'e', 183752, '断冷冽飞弹'), ('4:40.5', '', 198589, '疾影接冰霜过载'),
         ('7:20.8', 'e', 183752, '断火热冲击'), ('7:59.4', '', 1234195, '晕断燃焰弹幕'),
         ('10:19.6', '', 198589, '疾影接熔火血脉'), ('11:21.4', 'e', 183752, '断焰烬之箭'),
         ('14:01.8', 'e', 183752, '断烈焰狂轰'), ('15:12.0', '', 198589, '疾影接缚焰仪式'),
         ('18:21.8', 'e', 183752, '断雷霆冲击'), ('18:31.0', 'v', 58984, '影遁断闪电涌流'),
         ('22:46.4', '', 198589, '疾影接烈焰喷吐'), ('24:58.0', '', 198589, '疾影接阻断暴雨')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(163,48,201,')
         + '.mk.start{transform:translateX(-22%)}\n:root{--shadow:#5fc6d6;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>噬灭恶魔猎手 · 红玉新生法池</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-红玉新生法池-噬灭恶魔猎手.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))
