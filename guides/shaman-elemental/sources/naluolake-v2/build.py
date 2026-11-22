"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-23-纳洛拉克的洞穴-元素萨满.html
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

# 代表场次：r4 小电飒（纳洛拉克的洞穴 +24 限时，29:35 战斗结束，覆盖全部固定点；尾王首发回响重击用土元素）
TOTAL_SEC = 1775.0
BANDS = [
    ('0:22', '3:59', '开场', 'trash'),
    ('3:59', '7:54', '①囤宝狂人', 'boss'),
    ('8:08', '15:58', '林道·冰川', 'trash'),
    ('15:59', '19:52', '②寒冬哨兵', 'boss'),
    ('20:26', '25:38', '图腾·纳尼亚', 'trash'),
    ('25:38', '29:35', '③纳洛拉克', 'boss'),
]
# '' = 星界转移 (--gold), 'e' = 土元素 (--tl-e), 'v' = 清毒图腾 (--tl-v)
# 时间均取自 r4 uses.md 实录施放时刻；上下排由 timeline() 自动交替
MARKS = [
    ('2:30.4', '', 108271, '苦难盛宴'),
    ('4:09.3', '', 108271, '咆哮·补开'),
    ('4:37.3', 'v', 383013, '清孢子'),
    ('6:38.8', 'v', 383013, '清孢子'),
    ('6:49.1', '', 108271, '饕餮·补开'),
    ('8:32.7', '', 108271, '剃刀俯冲'),
    ('14:12.7', '', 108271, '凛冽严冬'),
    ('16:55.2', '', 108271, '寒冰暴雨'),
    ('19:19.2', '', 108271, '折磨·兜底'),
    ('22:01.8', '', 108271, '原始回响'),
    ('23:51.0', '', 108271, '纳尼亚·可选'),
    ('25:46.0', 'e', 198103, '首发重击'),
    ('27:15.7', '', 108271, '回响重击'),
    ('29:26.5', '', 108271, '回响重击'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-23-纳洛拉克的洞穴-元素萨满.html')

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
