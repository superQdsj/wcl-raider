"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-夺目谷-元素萨满.html
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

# 代表场：r1 孤独咩 (+24 限时 28:22，战斗实录至 28:01 = 1681s)
# 覆盖 11 次核心星界转移 + 2 次高样本土元素（鲁伊亚 5/5、兹欧凯特 3/5）+ 1 次清毒图腾，共 14 点，0 低样本点
TOTAL_SEC = 1681.0
BANDS = [
    ('0:14', '4:28', '开场', 'trash'),
    ('4:28', '8:55', '①密林三杰', 'boss'),
    ('9:01', '10:22', '林地', 'trash'),
    ('10:22', '14:39', '②伊库兹', 'boss'),
    ('15:09', '15:22', '荒芜', 'trash'),
    ('15:22', '20:04', '③鲁伊亚', 'boss'),
    ('20:21', '22:34', '蟾蜍区', 'trash'),
    ('22:43', '24:18', '尾王前', 'trash'),
    ('24:18', '28:01', '④兹欧凯特', 'boss'),
]
# '' = 星界转移固定点 (--gold), 'e' = 土元素 (--tl-e), 'v' = 清毒图腾 (--tl-v), 'muted' = 条件星界 (灰)
MARKS = [
    ('0:32', '', 108271, '喷涌+拔根'),
    ('2:29', '', 108271, '喷涌之花'),
    ('6:08', 'muted', 108271, '基岩+荆棘'),
    ('8:22', 'muted', 108271, '基岩+荆棘'),
    ('12:56', '', 108271, '疯乱+咆哮'),
    ('15:34', '', 108271, '光明之火'),
    ('18:59', '', 108271, '峡谷之灵'),
    ('19:30', 'e', 198103, '土·痛击'),
    ('20:47', 'v', 383013, '清毒·喷毒'),
    ('21:14', '', 108271, '二轮喷毒'),
    ('23:08', '', 108271, '喷涌之花'),
    ('25:32', '', 108271, '二轮叠层'),
    ('26:31', 'e', 198103, '土·补球'),
    ('27:15', '', 108271, '四轮叠层'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-夺目谷-元素萨满.html')

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
