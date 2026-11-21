"""Offline rebuild: python3 build.py [out.html]  (default: ./sample.html)
Template sample for all class guides (毒林夜色 visual + single-spine route + top quick-ref).
Inputs: head.part + body.part; shares tstring.json & icons.json with ../duya-v2/ (正式副本设为 H).
Timeline: single track from r2 (pJqfFgYPNKaBmz1k#30, +24), via shared guides/tools/timeline.py."""
import json
import os
import re
import sys

H = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(H, '..', 'duya-v2')  # 样板复用兄弟目录数据；正式新副本直接设为 H
TOOLS = os.path.join(H, '../../../tools')
sys.path.insert(0, TOOLS)
from icons import externalize
from timeline import GOLD_TL_CSS, timeline

BANDS = [  # r2 segments (../duya-v2/evidence/segments.md)
    ('0:13', '6:13', '开场小怪', 'trash'),
    ('6:21', '11:17', '拉维', 'boss'),
    ('11:27', '14:24', '进化者', 'trash'),
    ('14:24', '17:54', '扭缠盘蛇', 'boss'),
    ('17:59', '24:48', '利刃 · 神选者', 'trash'),
    ('24:53', '29:40', '祖尔加', 'boss'),
]
# '' = 核心斗篷点 (--gold), 'e' = 闪避接切骨者 (--tl-e), 'muted' = 顺手斗篷 (灰)
# 注：r2 19:30 的感染斗篷属低样本兜底（仅 r2/r4），不列入实录主轴标记
MARKS = [  # r2 cloak / evasion times (../duya-v2/evidence/uses.md)
    ('0:53', 'muted', 31224, '麻痹射击'),
    ('7:13', '', 31224, '清三重喷吐'),
    ('10:01', '', 31224, '预开喷吐'),
    ('13:15', 'muted', 31224, '清毒伤'),
    ('16:02', '', 31224, '同步毒液'),
    ('21:42', '', 31224, '剧毒涌动'),
    ('23:44', '', 31224, '剧毒涌动'),
    ('25:31', 'e', 5277, '接切骨者'),
    ('27:17', '', 31224, '拦光束'),
    ('27:43', 'e', 5277, '接切骨者'),
    ('29:23', '', 31224, '拦光束'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, 'sample.html')

s = (open(os.path.join(H, 'head.part'), encoding='utf-8').read()
     + open(os.path.join(H, 'body.part'), encoding='utf-8').read())
s = s.replace('{{TLCSS}}', GOLD_TL_CSS)
s = s.replace('{{TIMELINE}}', timeline(29 * 60 + 40.6, BANDS, MARKS))
if '{{TALENT}}' in s:
    s = s.replace('{{TALENT}}', json.load(open(os.path.join(DATA_DIR, 'tstring.json'), encoding='utf-8'))['string'])
ic = json.load(open(os.path.join(DATA_DIR, 'icons.json'), encoding='utf-8'))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]

with open(out, 'w', encoding='utf-8') as f:
    f.write(s)
print(out, len(s))
print('icons:', externalize(out))
