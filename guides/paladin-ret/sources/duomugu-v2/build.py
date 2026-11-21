"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-夺目谷-惩戒骑.html
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

# 代表性实录：r2 +24 限时（29:53，2JCbhkXHdf6MzDB4#fight=14）
TOTAL_SEC = 1793.1
BANDS = [
    ('0:14', '4:53', '开场', 'trash'),
    ('4:54', '9:11', '①莱克希三人组', 'boss'),
    ('9:19', '10:37', '过桥', 'trash'),
    ('10:37', '14:56', '②伊库兹', 'boss'),
    ('15:31', '17:16', '棘喉兽', 'trash'),
    ('17:17', '21:29', '③鲁伊亚', 'boss'),
    ('21:57', '25:47', '蛤蟆区', 'trash'),
    ('25:47', '29:53', '④兹欧凯特', 'boss'),
]
# '' = 圣盾术主点 (--gold), 'e' = 圣佑术 (--tl-e), 'v' = 保护/自由/清毒 (--tl-v), 'muted' = 备选/顺手交牌 (灰)
MARKS = [
    ('0:33.6', 'e', 403876, '圣佑喷涌'),
    ('2:10.4', 'e', 403876, '圣佑喷涌'),
    ('5:02.7', 'e', 403876, '圣佑涌动'),
    ('7:18.0', 'e', 403876, '圣佑涌动'),
    ('8:49.1', 'v', 1022, '保护荆棘'),
    ('11:01.2', 'muted', 642, '圣盾+牺牲'),
    ('12:22.7', 'v', 1044, '自由防根'),
    ('14:14.3', 'e', 403876, '圣佑咆哮'),
    ('17:27.1', 'e', 403876, '圣佑光火'),
    ('20:06.5', 'v', 1022, '保护痛击'),
    ('21:05.3', '', 642, '圣盾双免'),
    ('22:17.7', 'v', 213644, '清毒喷毒'),
    ('26:06.5', 'e', 403876, '圣佑木质'),
    ('28:42.6', '', 642, '圣盾木质'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-夺目谷-惩戒骑.html')

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
