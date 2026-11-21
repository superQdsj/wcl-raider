"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-纳洛拉克的洞穴-惩戒骑.html
Uses shared guides/tools/timeline.py and guides/tools/icons.py (inject_icons)."""
import json
import os
import re
import sys

H = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = H
TOOLS = os.path.join(H, '../../../tools')
sys.path.insert(0, TOOLS)
from icons import externalize, inject_icons
from timeline import GOLD_TL_CSS, timeline

# 代表性实录：r5 +24 限时（31:27，RXKdxtTG471Vz9wQ#fight=14）
TOTAL_SEC = 1887.3
BANDS = [
    ('0:22', '4:30', '开场', 'trash'),
    ('4:30', '8:45', '①囤宝狂人', 'boss'),
    ('9:11', '11:09', '林道', 'trash'),
    ('11:26', '17:24', '冰川区', 'trash'),
    ('17:24', '21:53', '②寒冬哨兵', 'boss'),
    ('22:55', '26:35', '图腾/纳尼亚', 'trash'),
    ('27:19', '31:27', '③纳洛拉克', 'boss'),
]
# '' = 圣盾术主点 (--gold), 'e' = 圣佑术 (--tl-e), 'v' = 保护/自由/清毒 (--tl-v), 'muted' = 备选/顺手交牌 (灰)
MARKS = [
    ('2:55.7', 'e', 403876, '圣佑盛宴'),
    ('4:38.3', 'e', 403876, '圣佑咆哮'),
    ('5:59.9', 'e', 403876, '圣佑怒吼'),
    ('6:38.6', 'v', 1022, '保护怒吼'),
    ('8:43.0', 'v', 213644, '清毒孢子'),
    ('12:08.3', 'v', 1044, '自由免墓'),
    ('14:50.6', 'e', 403876, '圣佑严冬'),
    ('18:19.1', 'e', 403876, '圣佑暴雨'),
    ('20:25.6', 'e', 403876, '圣佑暴雨'),
    ('23:37.1', 'muted', 642, '圣盾+牺牲'),
    ('25:31.6', 'e', 403876, '圣佑烈焰'),
    ('27:26.8', 'e', 403876, '圣佑重击'),
    ('27:52.4', '', 642, '圣盾重击'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-纳洛拉克的洞穴-惩戒骑.html')

s = (open(os.path.join(H, 'head.part'), encoding='utf-8').read()
     + open(os.path.join(H, 'body.part'), encoding='utf-8').read())
s = s.replace('{{TLCSS}}', GOLD_TL_CSS)
s = s.replace('{{TIMELINE}}', timeline(TOTAL_SEC, BANDS, MARKS))
if '{{TALENT}}' in s:
    s = s.replace('{{TALENT}}', json.load(open(os.path.join(DATA_DIR, 'tstring.json'), encoding='utf-8'))['string'])

fallback_ic = os.path.join(DATA_DIR, 'icons.json')
s, n_icons, n_fetched = inject_icons(s, out, fallback_json=fallback_ic if os.path.isfile(fallback_ic) else None)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]

with open(out, 'w', encoding='utf-8') as f:
    f.write(s)
print(f'{out} ({len(s)} bytes) | icons={n_icons} (newly fetched={n_fetched})')
ext_n, ext_saved = externalize(out)
if ext_n:
    print(f'externalized extra base64: {ext_n} (-{ext_saved} bytes)')
