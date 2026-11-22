"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-23-虚空之痕竞技场-元素萨满.html
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

# 代表场 r3（+24 29:27，无复生，五处星界固定点全覆盖；几丁高斯土元素属兜底未画）
TOTAL_SEC = 1767.0
BANDS = [
    ('0:15', '7:23', '开场 · 几丁高斯', 'trash'),
    ('7:23', '11:36', '塔兹拉尔', 'boss'),
    ('11:45', '13:44', '熔岩区', 'trash'),
    ('13:53', '17:58', '阿特洛苏斯', 'boss'),
    ('18:11', '25:28', '虚空区', 'trash'),
    ('25:29', '29:27', '煞戎努斯', 'boss'),
]
# '' = 主大招 (--gold), 'e' = 副手牌1 (--tl-e), 'v' = 副手牌2 (--tl-v), 'muted' = 顺手交牌 (灰)
MARKS = [
    ('4:56', '', 108271, '险恶光环'),
    ('7:37', '', 108271, '冲刺一轮'),
    ('9:21', '', 108271, '冲刺四轮'),
    ('10:04', 'e', 198103, '冲刺五轮'),
    ('11:06', '', 108271, '冲刺七轮'),
    ('15:27', '', 108271, '光环二轮'),
    ('17:07', '', 108271, '光环四轮'),
    ('19:13', '', 108271, '恐惧咆哮'),
    ('22:36', '', 108271, '恐惧咆哮'),
    ('24:28', '', 108271, '恐惧咆哮'),
    ('26:42', '', 108271, '星坠二轮'),
    ('27:33', 'e', 198103, '星坠三轮'),
    ('28:27', '', 108271, '星坠四轮'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-23-虚空之痕竞技场-元素萨满.html')

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
