"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-虚空之痕竞技场-惩戒骑.html
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

# 代表场：r3（+23 · 28:20.8，报告 1XnY9HZkM4BmN8LF fight 8）：两个必留圣盾点都接了牺牲，无低样本兜底点
TOTAL_SEC = 1701.0
BANDS = [
    ('0:16', '3:01', '开场', 'trash'),
    ('3:09', '7:05', '竞技场', 'trash'),
    ('7:05', '10:42', '①塔兹拉尔', 'boss'),
    ('10:52', '12:59', '掠心者', 'trash'),
    ('13:18', '17:02', '②阿特洛苏斯', 'boss'),
    ('17:26', '24:41', '残虐者', 'trash'),
    ('24:41', '28:20', '③煞戎努斯', 'boss'),
]
# '' = 圣盾术 + 牺牲 (--gold), 'e' = 牺牲祝福保队友, 'v' = 圣佑术, 'muted' = 圣疗自救
MARKS = [
    ('0:51.1', 'v', 403876, '圣佑钉锤'),
    ('7:17.6', 'v', 403876, '圣佑冲刺'),
    ('7:54.0', '', 642, '圣盾+牺牲'),
    ('9:04.2', 'muted', 633, '圣疗自救'),
    ('14:01.9', 'v', 403876, '圣佑光环'),
    ('15:44.6', 'v', 403876, '圣佑光环'),
    ('17:46.0', 'v', 403876, '圣佑咆哮'),
    ('19:51.8', 'e', 6940, '牺牲给光束'),
    ('25:02.6', 'v', 403876, '圣佑坠击'),
    ('26:47.6', 'v', 403876, '圣佑坠击'),
    ('27:39.8', '', 642, '圣盾+牺牲'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-虚空之痕竞技场-惩戒骑.html')

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
