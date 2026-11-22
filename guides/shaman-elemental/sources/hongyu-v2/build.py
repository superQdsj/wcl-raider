"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-23-红玉新生法池-元素萨满.html
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

# 代表场次：r2 Keai（红玉新生法池 +24 限时 27:20，总实录 27:14）
# 必做动作覆盖最全、零低样本兜底点：完整展示一轮星界 + 二轮土元素的过载分工、熔火血脉后段延后开与尾王 P1 土元 / P2 星界。
TOTAL_SEC = 1640.0
BANDS = [
    ('0:10', '3:32', '开场', 'trash'),
    ('3:32', '7:05', '① 梅莉杜莎', 'boss'),
    ('7:42', '11:32', '火廊前段', 'trash'),
    ('11:39', '14:40', '火廊后段', 'trash'),
    ('14:40', '19:22', '② 柯姬雅', 'boss'),
    ('19:37', '23:05', '雷电台', 'trash'),
    ('23:05', '27:14', '③ 基拉卡', 'boss'),
]
# '' = 星界转移固定点 (--gold), 'e' = 土元素 (--tl-e), 'muted' = 顺手星界 (灰)
MARKS = [
    ('0:32', 'muted', 108271, '地缚印记'),
    ('1:49', 'e', 198103, '土元·弹幕'),
    ('2:29', '', 108271, '弹幕叠印记'),
    ('4:58', '', 108271, '冰霜过载'),
    ('6:18', 'e', 198103, '土元·二过载'),
    ('8:18', '', 108271, '地狱烈火'),
    ('11:02', '', 108271, '熔火血脉'),
    ('13:28', '', 108271, '地狱烈火'),
    ('16:34', '', 108271, '风暴烈火'),
    ('20:15', '', 108271, '闪电涌流'),
    ('22:32', '', 108271, '涌流叠践踏'),
    ('23:48', 'e', 198103, '土元·喷吐'),
    ('25:22', '', 108271, 'P2烈焰喷吐'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-23-红玉新生法池-元素萨满.html')

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
