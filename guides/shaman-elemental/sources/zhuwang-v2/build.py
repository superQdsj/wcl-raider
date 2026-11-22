"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-诸王之眠-元素萨满.html
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

# 代表场：r3 一期一会 (+24 限时 32:05，战斗实录至 32:13 = 1934s)
# 覆盖全部 6 个核心星界转移固定点 + 2 次土元素 + 2 次净化术关键点 + 1 次条件星界，共 14 点，0 低样本兜底点
TOTAL_SEC = 1934.0
BANDS = [
    ('0:25', '3:23', '开场', 'trash'),
    ('3:23', '7:28', '①风蛇', 'boss'),
    ('7:46', '12:46', '大厅', 'trash'),
    ('13:10', '15:20', '木乃伊', 'trash'),
    ('15:21', '19:15', '②姆沁巴', 'boss'),
    ('19:34', '21:16', '议会前', 'trash'),
    ('21:17', '26:02', '③议会', 'boss'),
    ('26:16', '28:02', '祖尔影', 'trash'),
    ('28:10', '32:13', '④达萨', 'boss'),
]
# '' = 星界转移固定点 (--gold), 'e' = 土元素 (--tl-e), 'v' = 净化术 (--tl-v), 'muted' = 条件/顺手星界 (灰)
MARKS = [
    ('1:01', '', 108271, '暗影旋风斩'),
    ('2:56', '', 108271, '暗影旋风斩'),
    ('5:50', '', 108271, '蛇风补星界'),
    ('6:54', 'e', 198103, '蛇之风土元'),
    ('8:22', '', 108271, '骤裂+吸取'),
    ('9:32', 'v', 370, '驱队长壁垒'),
    ('15:32', '', 108271, '排干体液'),
    ('19:54', 'muted', 108271, '嗜血飞斧'),
    ('22:49', '', 108271, '翻滚分摊'),
    ('23:29', 'e', 198103, '翻滚土元'),
    ('25:27', '', 108271, '后续翻滚'),
    ('26:44', 'v', 370, '秒杀爪牙'),
    ('29:37', '', 108271, '震地之跃'),
    ('31:12', '', 108271, '隔轮震地'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-诸王之眠-元素萨满.html')

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
