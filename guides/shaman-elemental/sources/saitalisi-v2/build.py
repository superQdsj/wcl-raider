"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-塞塔里斯神庙-元素萨满.html
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

# Representative run: r2 Fauni (+24 30:46 = 1846s, EU) — clean core coverage, zero low-sample fallback points on Boss 2.
# Timestamps retain 0.1s precision from segments.md / run2_casts.json (timeline.py displays integer seconds, positions by float).
# Trash segments #3–#5 (6:01.3–12:06.7) are merged into one continuous '蝰蛇区' band.
TOTAL_SEC = 1846.0
BANDS = [
    ('0:14.3', '1:42.5', '开场', 'trash'),
    ('1:43.1', '5:49.1', '①双首领', 'boss'),
    ('6:01.3', '12:06.7', '蝰蛇区', 'trash'),
    ('12:11.1', '16:08.6', '②米利克萨', 'boss'),
    ('16:11.5', '19:04.8', '暴怒云气', 'trash'),
    ('19:11.7', '23:02.9', '③加瓦兹特', 'boss'),
    ('23:22.3', '27:06.4', '宝珠区', 'trash'),
    ('27:08.8', '30:40.4', '④化身', 'boss'),
]
# '' = 星界转移 (--gold), 'e' = 土元素 (--tl-e), 'v' = 清毒图腾 (--tl-v)
MARKS = [
    ('0:36.7', '', 108271, '震地'),
    ('2:40.3', '', 108271, '电闪雷鸣'),
    ('6:40.9', '', 108271, '锯齿冲锋'),
    ('7:04.8', 'v', 383013, '清毒·毒素'),
    ('10:49.9', 'v', 383013, '清毒·毒素'),
    ('17:12.5', '', 108271, '释放电荷'),
    ('18:33.9', 'e', 198103, '土元·电荷'),
    ('19:21.1', '', 108271, '镀流1'),
    ('20:53.6', '', 108271, '镀流2'),
    ('22:24.8', '', 108271, '镀流3'),
    ('25:02.6', '', 108271, '蚀骨践踏'),
    ('26:29.2', 'e', 198103, '土元·践踏'),
    ('27:49.1', '', 108271, '腐化1'),
    ('29:39.5', '', 108271, '腐化2'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-塞塔里斯神庙-元素萨满.html')

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
