"""Offline rebuild: python3 build.py [out.html]  (default: ./trial.html)
Inputs: page.html (template), timeline.py (variant with .pin/.gl markup);
icons.json + tstring.json are shared with ../duya-v2/ (same files).
v3: Raycast vocabulary (launcher windows, keycaps, glow), v2 content spine. Gold = cloak / must-do, red = evasion."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
from timeline import timeline

BANDS = [
    ('0:13', '6:13', '开场小怪', 'trash'),
    ('6:21', '11:17', '拉维', 'boss'),
    ('11:27', '14:24', '进化者', 'trash'),
    ('14:24', '17:54', '扭缠盘蛇', 'boss'),
    ('17:59', '24:48', '利刃 · 神选者', 'trash'),
    ('24:53', '29:40', '祖尔加', 'boss'),
]
# '' = must-do (gold), 'muted' = other cloak uses (gray)
MARKS = [
    ('0:53', 'muted', 31224, '麻痹射击'),
    ('7:13', '', 31224, '三重喷吐'),
    ('10:01', '', 31224, '三重喷吐'),
    ('13:15', 'muted', 31224, '毒伤'),
    ('16:02', '', 31224, '同步毒液'),
    ('19:30', 'muted', 31224, '感染'),
    ('21:42', '', 31224, '剧毒涌动'),
    ('23:44', '', 31224, '剧毒涌动'),
    ('27:17', 'muted', 31224, '光束'),
    ('27:43', 'e', 5277, '接切骨者'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, 'trial.html')
s = open(os.path.join(H, 'page.html'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(29 * 60 + 40.6, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, '..', 'duya-v2', 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, '..', 'duya-v2', 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))
