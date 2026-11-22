"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-23-密谋小径-元素萨满.html
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

# 代表场次：r2 孤独咩（密谋小径 +24 限时，31:05 战斗结束 / 31:41 结算，无复生，覆盖全部固定点）
TOTAL_SEC = 1865.0
BANDS = [
    ('0:12', '4:50', '开场', 'trash'),
    ('4:50', '6:40', '①凯斯媞亚', 'boss'),
    ('8:14', '11:53', '②赞恩', 'boss'),
    ('12:15', '17:56', '邪能街', 'trash'),
    ('17:56', '22:08', '③萨祖克斯', 'boss'),
    ('22:23', '26:55', '小鬼傀儡', 'trash'),
    ('26:56', '31:05', '④利希尔', 'boss'),
]
# '' = 星界转移 (--gold), 'e' = 土元素 (--tl-e), 'v' = 清毒图腾 (--tl-v), 'muted' = 顺手星界 (灰，本页未用)
# 时间均取自 r2 uses.md 实录施放时刻；上下排由 timeline() 自动交替
MARKS = [
    ('3:19.6', '', 108271, '大浮龙波'),
    ('3:50.7', 'v', 383013, '清毒·扒手'),
    ('6:22.1', '', 108271, '混沌爆裂'),
    ('8:21.8', '', 108271, '①影舞步'),
    ('9:05.6', 'e', 198103, '土元素·赞恩'),
    ('11:13.3', '', 108271, '⑤影舞步'),
    ('13:00.4', '', 108271, '魔化狂乱'),
    ('14:45.1', '', 108271, '吸取生命'),
    ('18:34.8', '', 108271, '①碾压·狂怒'),
    ('19:25.5', 'e', 198103, '土元素·老三'),
    ('20:24.2', '', 108271, '③碾压·狂怒'),
    ('25:24.2', '', 108271, '亵渎猛击'),
    ('27:16.5', '', 108271, '①古尔丹之指'),
    ('29:05.9', '', 108271, '③古尔丹之指'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-23-密谋小径-元素萨满.html')

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
