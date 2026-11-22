"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-毒牙祭坛-元素萨满.html
Uses shared guides/tools/timeline.py and guides/tools/icons.py (inject_icons)."""
import json
import os
import re
import sys

H = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = H  # 如复用兄弟目录证据/天赋，改为对应路径并在 NOTES.md 说明
TOOLS = os.path.join(H, '../../../tools')
sys.path.insert(0, TOOLS)
from icons import externalize, inject_icons
from timeline import GOLD_TL_CSS, timeline

# 代表录像 r2（+23 27:18.9），星界转移 / 土元素实际施放时间
TOTAL_SEC = 1638.9
BANDS = [
    ('0:13', '5:59', '开场', 'trash'),
    ('6:03', '10:06', '拉维', 'boss'),
    ('10:19', '12:59', '进化者', 'trash'),
    ('12:59', '16:11', '盘蛇', 'boss'),
    ('16:18', '22:56', '神选者', 'trash'),
    ('23:01', '27:18', '祖尔加', 'boss'),
]
# '' = 星界转移固定点, 'e' = 土元素
MARKS = [
    ('0:35', '', 108271, '鲜血献祭'),
    ('3:29', '', 108271, '鲜血献祭'),
    ('6:35', '', 108271, '嘶嘶食腐'),
    ('7:57', 'e', 198103, '三重喷吐'),
    ('9:30', '', 108271, '嘶嘶食腐'),
    ('12:35', '', 108271, '振响'),
    ('17:49', '', 108271, '感染'),
    ('19:37', '', 108271, '剧毒涌动'),
    ('21:55', '', 108271, '涌动+献祭'),
    ('24:47', '', 108271, '切骨者'),
    ('26:56', '', 108271, '切骨者'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-毒牙祭坛-元素萨满.html')

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
