"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-22-红玉新生法池-惩戒骑.html
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

# 代表场：r3（Âra +23，录像计时 25:36，末战斗事件 25:16，报告 m6jBctXD2TyvZH1a fight 18）：
# 必做的自由给坦克、圣佑地狱烈火、圣盾闪电涌流、牺牲给喷吐全覆盖；省略单场兜底点与事后晚开的 7:42.1。
TOTAL_SEC = 1516.0
BANDS = [
    ('0:12', '3:10', '开场', 'trash'),
    ('3:10', '6:46', '①梅莉杜莎', 'boss'),
    ('7:23', '14:09', '火焰区', 'trash'),
    ('14:09', '17:54', '②柯姬雅', 'boss'),
    ('18:13', '21:37', '雷暴区', 'trash'),
    ('21:37', '25:16', '③基拉卡', 'boss'),
]
# '' = 圣盾术 (--gold), 'e' = 圣佑术, 'v' = 自由/牺牲祝福
MARKS = [
    ('2:02.6', 'e', 403876, '圣佑弹幕'),
    ('4:31.0', 'v', 1044, '自由给坦克'),
    ('9:53.3', 'e', 403876, '圣佑烈火'),
    ('13:33.5', 'v', 6940, '牺牲给炸弹'),
    ('15:08.9', 'e', 403876, '圣佑烈火'),
    ('16:29.6', 'e', 403876, '圣佑烈火'),
    ('18:22.3', '', 642, '圣盾涌流'),
    ('19:40.0', 'e', 403876, '圣佑涌流'),
    ('21:55.7', 'e', 403876, '圣佑喷吐'),
    ('23:27.9', 'v', 6940, '牺牲给喷吐'),
    ('24:28.9', 'v', 6940, '牺牲给喷吐'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-22-红玉新生法池-惩戒骑.html')

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
