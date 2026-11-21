"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-塞塔里斯神庙-惩戒骑.html
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

# 代表场：r1（+24 · 31:51.5，报告 2JCbhkXHdf6MzDB4 fight 11），必做动作全覆盖、无低样本兜底点
TOTAL_SEC = 1915.0
BANDS = [
    ('0:13', '1:45', '开场', 'trash'),
    ('1:45', '5:56', '①双首领', 'boss'),
    ('6:08', '12:15', '蝰蛇区', 'trash'),
    ('12:19', '16:28', '②米利克萨', 'boss'),
    ('16:36', '19:46', '云气区', 'trash'),
    ('19:54', '23:39', '③加瓦兹特', 'boss'),
    ('23:46', '27:49', '宝珠区', 'trash'),
    ('27:50', '31:51', '④化身', 'boss'),
]
# '' = 圣盾术 (--gold), 'e' = 圣佑术, 'v' = 保护/牺牲祝福, 'muted' = 圣疗术给化身
MARKS = [
    ('0:35.8', 'v', 1022, '保护清流血'),
    ('2:41.7', 'e', 403876, '圣佑电闪'),
    ('3:36.1', '', 642, '圣盾电闪'),
    ('7:11.0', 'v', 1022, '保护清流血'),
    ('11:26.3', '', 642, '圣盾清流血'),
    ('14:35.3', 'e', 403876, '圣佑喷吐'),
    ('17:09.8', 'e', 403876, '圣佑电荷'),
    ('18:28.3', 'e', 403876, '圣佑电荷'),
    ('20:47.6', 'v', 6940, '牺牲给光束'),
    ('23:04.1', 'v', 6940, '牺牲给光束'),
    ('24:54.3', 'e', 403876, '圣佑践踏'),
    ('27:51.1', 'muted', 633, '圣疗给化身'),
    ('28:40.1', 'e', 403876, '圣佑腐化'),
    ('30:32.8', '', 642, '圣盾腐化'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-塞塔里斯神庙-惩戒骑.html')

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
