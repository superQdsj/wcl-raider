"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-08-密谋小径-惩戒骑.html)
src = head.part (CSS) + body.part (content); {{TLCSS}} {{TIMELINE}} {{TALENT}} {{I:id}} are filled here."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, '../../../tools'))
from timeline import timeline, GOLD_TL_CSS

# single track: reference run 1 (+22, 27:41)
END = 27 * 60 + 41
BANDS = [('0:10', '4:56', '小怪 · 开场', 'trash'), ('5:14', '6:55', '凯斯媞亚', 'boss'),
         ('7:44', '8:31', '怪', 'trash'), ('8:31', '11:40', '赞恩', 'boss'),
         ('12:08', '15:51', '小怪 · 术士和魔蝇', 'trash'), ('15:58', '19:46', '萨祖克斯', 'boss'),
         ('20:02', '23:54', '小怪 · 小鬼和傀儡', 'trash'), ('23:54', '27:41', '利希尔', 'boss')]
MARKS = [('0:36', '', 6940, '坦克免毒'), ('0:55', 'muted', 213644, '清断心药膏'),
         ('4:02', '', 642, '扛燃烧邪能'), ('6:42', '', 403876, '扛混沌爆裂'),
         ('10:19', '', 6940, '免疫毒伤'), ('11:15', '', 1022, '免疫绝命凶径'),
         ('13:46', 'muted', 633, '圣盾没好·圣疗顶'), ('16:38', '', 403876, '碾压接狂怒'),
         ('21:27', '', 642, '解吸取生命'), ('23:07', '', 403876, '扛亵渎猛击'),
         ('26:03', '', 403876, '扛古尔丹之指'), ('26:57', '', 642, '牺牲＋圣盾')]

css = open(os.path.join(H, 'head.part'), encoding='utf-8').read()
tlcss = (GOLD_TL_CSS.replace('rgba(242,210,75,', 'rgba(243,156,195,')
         + ':root{--shadow:#b48cf0;--nature:#9bd65f}\n')
css = css.replace('{{TLCSS}}', tlcss)
head = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>惩戒骑 · 密谋小径</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">\n'
        f'<style>{css}</style>\n</head>\n<body>\n\n')
s = head + open(os.path.join(H, 'body.part'), encoding='utf-8').read()
s = s.replace('{{TIMELINE}}', timeline(END, BANDS, MARKS))
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-08-密谋小径-惩戒骑.html')
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))

# Icons live in guides/icons/; the page links to them instead of embedding base64.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.abspath(__file__).split("/guides/")[0], "guides", "tools"))
from icons import externalize
print("icons:", externalize(out))
