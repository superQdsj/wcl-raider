"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-23-毒牙祭坛-兽王猎人.html
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

# r2 +23 限时实录，计时从报告战斗开始。
TOTAL_SEC = 1695.2
BANDS = [
    ('0:14', '6:06.5', '开场小怪', 'trash'),
    ('6:08', '10:44.1', '拉维', 'boss'),
    ('10:56.6', '13:36.6', '高阶进化者', 'trash'),
    ('13:43', '16:57.9', '扭缠盘蛇', 'boss'),
    ('17:10.4', '23:49.9', '祭坛利刃与神选者', 'trash'),
    ('23:55.2', '28:15.2', '祖尔加', 'boss'),
]
MARKS = [
    ('1:45.8', 'e', 264735, '减鲜血献祭'),
    ('4:14.6', 'v', 781, '逃脱解麻痹'),
    ('6:50.6', '', 186265, '龟壳挡喷吐'),
    ('7:16.2', 'e', 264735, '减喷吐跳伤'),
    ('11:24.6', 'e', 264735, '减振响'),
    ('13:12.0', 'muted', 147362, '反制断毒伤'),
    ('13:45.8', '', 186265, '龟壳挡同步'),
    ('16:03.8', 'v', 781, '逃脱拉断连线'),
    ('19:17.3', 'e', 264735, '减感染后段'),
    ('23:00.2', 'e', 264735, '减剧毒涌动'),
    ('25:39.6', 'e', 264735, '减伤接飞斧'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-23-毒牙祭坛-兽王猎人.html')

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
