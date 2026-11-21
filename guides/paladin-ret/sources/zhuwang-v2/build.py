"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-21-诸王之眠-惩戒骑.html)
src = head.part (<head> + CSS) + body.part (content + script); {{TLCSS}} {{TIMELINE}} {{TALENT}} are filled here.
Evidence lives in ../zhuwang/evidence/. System fonts only (no Google Fonts); icons are ../icons/<hash>.jpg.
Talent string: python3 enc.py r1_哦毕爷 -> tstring.json."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: r1 哦毕爷 (CN +24, 32:04, fAvBRtjbKxGqdMWL#289; same player as the talent string)
END = 32 * 60 + 4.2
BANDS = [('0:18', '3:14', '开门大厅', 'trash'), ('3:15', '7:12', '风蛇', 'boss'),
         ('7:27', '12:43', '陵墓四王', 'trash'), ('13:01', '15:04', '停尸间', 'trash'),
         ('15:04', '19:10', '姆沁巴', 'boss'), ('19:24', '21:08', '长廊', 'trash'),
         ('21:08', '25:55', '部族议会', 'boss'), ('26:10', '27:52', '祖尔之影', 'trash'),
         ('28:07', '32:04', '达萨', 'boss')]
MARKS = [  # evidence/uses.md, r1
    ('0:58.0', '', 642, '圣盾免疫旋风斩'), ('3:31.0', '', 403876, '圣佑顶蛇之风'),
    ('5:41.1', '', 403876, '圣佑顶蛇之风'), ('7:51.7', '', 6940, '牺牲接鲜血吸取'),
    ('8:13.7', '', 1022, '保护清骤裂'), ('11:05.0', 'e', 213644, '清毒蛇打击'),
    ('16:21.1', '', 6940, '牺牲接排干体液'), ('19:51.9', '', 1022, '保护挡飞斧'),
    ('20:58.1', 'e', 115750, '盲目之光'), ('26:56.0', 'muted', 642, '圣盾'),
    ('29:44.0', '', 1022, '保护免疫震地之跃'), ('30:55.7', '', 642, '牺牲＋圣盾保坦'),
]
ICON = {642: 'b3bb765fb8bc', 1022: 'bdbd6a5f6061', 6940: '011c0b335bf9', 403876: '39f85b6d2657',
        213644: '81bc87699eff', 115750: 'f8cb22a1bcc9'}

tlcss = GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(217,171,82,')
s = open(os.path.join(H, 'head.part'), encoding='utf-8').read() + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TLCSS}}', tlcss)
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json'), encoding='utf-8'))['string'])
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: f'../icons/{ICON[int(m.group(1))]}.jpg', s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-21-诸王之眠-惩戒骑.html')
# body.part links icons as ../icons/<hash>.jpg, so the page must sit in guides/<class>/ (next to the published one).
assert os.path.dirname(os.path.abspath(os.path.join(os.path.abspath(out), '..'))) == os.path.abspath(os.path.join(H, '../../..')), \
    'output must be in guides/<class>/ so ../icons/ resolves: ' + out
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))

from icons import externalize
print("icons:", externalize(out))
