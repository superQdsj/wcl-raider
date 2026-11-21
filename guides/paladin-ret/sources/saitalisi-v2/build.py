"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-21-塞塔里斯神庙-惩戒骑.html
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

# 代表场次 r2 哦毕爷（CN +23 30:36）：路线每个必做圣盾/保护/圣疗点都在这一场出现。波次见 evidence/segments.md，技能时间见 evidence/uses.md
TOTAL_SEC = 30 * 60 + 13.8
BANDS = [
    ('0:14', '1:24', '开场', 'trash'),
    ('1:24', '5:31', '双子', 'boss'),
    ('5:43', '11:44', '毒蛇道', 'trash'),
    ('11:49', '15:44', '米利克萨', 'boss'),
    ('15:50', '19:04', '风暴云', 'trash'),
    ('19:12', '22:31', '加瓦兹特', 'boss'),
    ('22:39', '26:33', '前厅', 'trash'),
    ('26:35', '30:13', '化身', 'boss'),
]
# '' = 必留圣盾点 (--gold), 'e' = 保护祝福清流血 (--tl-e), 'v' = 圣疗术给化身 (--tl-v), 'muted' = 顺手圣盾 (灰)
# 不画：r2 0:38 保护祝福交震地（兜底，仅 r2/r3）、23:46 前厅圣盾交蚀骨践踏（备选，仅 r2/r4）
MARKS = [
    ('7:01', 'e', 1022, '保护清血'),
    ('7:19', 'muted', 642, '顺手圣盾'),
    ('19:45', '', 642, '圣盾挡光束'),
    ('27:16', '', 642, '圣盾·腐化'),
    ('27:44', 'v', 633, '圣疗给化身'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-21-塞塔里斯神庙-惩戒骑.html')

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
