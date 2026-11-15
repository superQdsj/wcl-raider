"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-15-诸王之眠-噬灭恶魔猎手.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run r2 (EU +22, 30:04; same player as the talent string)
END = 30 * 60 + 4
BANDS = [('0:17', '3:42', '开场小怪', 'trash'), ('3:56', '7:07', '黄金风蛇', 'boss'),
         ('7:22', '11:23', '女王 · 阿库尔 · 议事厅', 'trash'), ('11:45', '15:12', '墓室', 'trash'),
         ('15:12', '18:22', '姆沁巴', 'boss'), ('18:41', '20:28', '狂战士', 'trash'),
         ('20:28', '24:45', '部族议会', 'boss'), ('25:09', '26:27', '祖尔', 'trash'),
         ('26:41', '30:04', '达萨', 'boss')]
MARKS = [('0:55.8', '', 198589, '疾影接旋风斩'), ('4:12.5', '', 198589, '疾影接蛇之风'),
         ('8:56.8', '', 196718, '黑暗接鲜血吸取'), ('13:32.2', 'e', 183752, '断恶疾排放'),
         ('16:26.1', 'v', 58984, '影遁断排干体液'), ('16:47.8', '', 198589, '疾影接觉醒猛击'),
         ('21:30.4', '', 198589, '疾影接翻滚'), ('22:35.1', 'v', 58984, '影遁取消翻滚'),
         ('25:27.8', 'e', 278326, '吞噬束缚秒爪牙'), ('28:41.0', '', 198589, '疾影接震地之跃')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(163,48,201,')
         + '.mk.start{transform:translateX(-22%)}\n:root{--shadow:#5fc6d6;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>噬灭恶魔猎手 · 诸王之眠</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-15-诸王之眠-噬灭恶魔猎手.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))
