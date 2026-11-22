"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: ../../2026-11-23-诸王之眠-兽王猎人.html
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

# r3 的报告内时间，含开场倒计时，不含钥石死亡罚时。
TOTAL_SEC = 1883.4
BANDS = [
    ('0:18.9', '3:26.0', '开场', 'trash'),
    ('3:39.9', '7:12.7', '黄金风蛇', 'boss'),
    ('7:32.4', '12:28.0', '陵墓大厅', 'trash'),
    ('13:08.4', '14:57.8', '木乃伊走廊', 'trash'),
    ('14:59.0', '18:33.6', '殓尸者姆沁巴', 'boss'),
    ('18:53.2', '20:57.5', '议会前小怪', 'trash'),
    ('20:57.7', '25:29.3', '部落议会', 'boss'),
    ('25:57.2', '27:18.2', '祖尔之影', 'trash'),
    ('27:31.5', '31:23.4', '达萨大王', 'boss'),
]
# '' = 灵龟守护，'e' = 优胜劣汰，'v' = 宁神或反制射击。
MARKS = [
    ('0:21.4', 'v', 19801, '驱爪牙护盾'),
    ('1:50.3', '', 186265, '龟壳挡旋风斩'),
    ('3:13.0', 'v', 147362, '断暗影箭'),
    ('6:06.2', 'e', 264735, '优胜扛蛇风'),
    ('7:42.7', 'v', 19801, '驱队长壁垒'),
    ('10:31.3', 'e', 264735, '优胜扛骤裂'),
    ('13:44.6', 'v', 147362, '断恶疾排放'),
    ('16:13.7', 'e', 264735, '优胜扛排干'),
    ('24:58.6', 'v', 147362, '断毒性新星'),
    ('26:46.6', 'e', 264735, '优胜扛弹幕'),
    ('28:07.0', '', 186265, '龟壳挡首发镀金'),
    ('30:14.1', 'e', 264735, '优胜扛镀金'),
    ('30:59.9', '', 186265, '龟壳挡镀金'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-23-诸王之眠-兽王猎人.html')

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
