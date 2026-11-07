"""Swimlane timeline for Ptz's +22 run (vxWqaMdprBXmcHPG#14). Returns HTML for {{TIMELINE}}."""

END = 28 * 60 + 48


def t(s):
    m, x = s.split(':')
    return int(m) * 60 + float(x)


def pct(sec):
    return f'{sec / END * 100:.2f}%'


BANDS = [  # (start, end, label, kind)
    ('0:22', '3:00', '开场小怪', 'trash'),
    ('3:00', '6:33', '黄金风蛇', 'boss'),
    ('6:44', '13:49', '小怪', 'trash'),
    ('13:49', '17:06', '姆沁巴', 'boss'),
    ('17:24', '18:45', '小怪', 'trash'),
    ('18:45', '23:05', '部族议会', 'boss'),
    ('23:11', '25:01', '小怪', 'trash'),
    ('25:19', '28:47', '达萨大王', 'boss'),
]

# b = 反弹单体法术（电弧/叉状闪电/暗影弹幕），a = 魔法范围伤害减 20%
REFLECTS = [
    ('0:58.0', 'a'), ('1:23.9', 'a'), ('1:57.2', 'a'), ('2:20.9', 'a'),
    ('3:16.3', 'a'), ('3:43.5', 'a'), ('4:21.3', 'a'), ('4:49.4', 'a'), ('5:27.1', 'a'), ('5:54.1', 'a'), ('6:30.8', 'a'),
    ('10:26.6', 'b'), ('10:56.0', 'b'), ('11:21.2', 'b'),
    ('13:58.4', 'a'), ('14:21.4', 'a'), ('15:27.6', 'a'), ('16:34.4', 'a'),
    ('21:11.6', 'b'), ('21:41.4', 'b'), ('22:10.3', 'b'), ('22:40.9', 'b'),
    ('23:44.9', 'b'), ('24:35.4', 'b'),
    ('25:54.6', 'a'), ('26:57.0', 'a'), ('27:44.1', 'a'), ('28:31.8', 'a'),
]

STANCE = [
    ('3:06.6', '3:14.8'), ('3:31.3', '3:38.6'), ('4:36.8', '4:45.1'), ('5:16.4', '5:22.9'), ('6:43.3', '6:53.3'),
    ('9:27.7', '9:30.7'), ('9:52.7', '9:55.7'), ('10:08.0', '10:11.8'), ('10:16.8', '10:24.5'),
    ('11:42.9', '12:07.7'), ('12:10.6', '12:21.7'), ('14:44.0', '14:47.0'), ('16:25.4', '16:33.2'),
    ('17:19.3', '17:30.3'), ('18:32.6', '18:49.0'), ('19:20.2', '19:25.7'),
    ('19:59.0', '20:02.0'), ('20:19.5', '20:22.5'), ('20:40.1', '20:43.1'), ('21:01.0', '21:04.4'),
    ('23:07.1', '23:39.5'), ('24:46.0', '24:50.4'), ('25:05.1', '25:21.4'), ('25:39.1', '25:42.7'),
    ('26:40.7', '26:45.7'), ('27:28.4', '27:32.1'), ('28:15.1', '28:18.9'),
]

BIG = [  # (time, icon id, label)
    ('1:21.8', 97462, '集结'), ('3:16.4', 118038, '剑在人在'), ('4:46.8', 97462, '集结'),
    ('9:27.3', 118038, '剑在人在'), ('9:53.3', 97462, '集结'), ('12:31.2', 118038, '剑在人在'),
    ('26:22.5', 97462, '集结'), ('26:41.1', 118038, '剑在人在'), ('28:31.8', 118038, '剑在人在'),
]

CALLOUTS = [  # 上方标注：(start, end, text)
    ('3:16', '6:31', '蛇之风 ×7 全反射'),
    ('10:26', '11:22', '叉状闪电'),
    ('14:21', '16:35', '觉醒猛击 ×3'),
    ('19:59', '22:41', '翻滚切姿态 · 电弧反射'),
    ('23:44', '24:36', '暗影弹幕'),
    ('25:54', '28:32', '镀金毁灭 ×4'),
]


def build():
    out = ['<div class="tl">']
    for a, b, label, kind in BANDS:
        out.append(f'<div class="band {kind}" style="left:{pct(t(a))};width:{pct(t(b) - t(a))}">{label}</div>')
    for a, b, text in CALLOUTS:
        out.append(f'<div class="call" style="left:{pct(t(a))};width:{pct(t(b) - t(a))}"><span>{text}</span></div>')
    out.append('<div class="lane-label" style="top:var(--l1)">法术反射</div>')
    out.append('<div class="lane-label" style="top:var(--l2)">防御姿态</div>')
    out.append('<div class="lane-label" style="top:var(--l3)">大减伤</div>')
    out.append('<div class="lane" style="top:var(--l1)"></div><div class="lane" style="top:var(--l2)"></div><div class="lane" style="top:var(--l3)"></div>')
    for at, kind in REFLECTS:
        out.append(f'<i class="rf {kind}" style="left:{pct(t(at))}"></i>')
    for a, b in STANCE:
        w = max(t(b) - t(a), 3)
        out.append(f'<i class="st" style="left:{pct(t(a))};width:{pct(w)}"></i>')
    for at, icon, label in BIG:
        out.append(f'<img class="bg" style="left:{pct(t(at))}" src="{{{{I:{icon}}}}}" alt="{label}" title="{at} {label}">')
    for m in range(0, 29, 5):
        style = 'left:0;transform:none' if m == 0 else f'left:{pct(m * 60)}'
        out.append(f'<div class="axis" style="{style}">{m}:00</div>')
    out.append('</div>')
    return '\n'.join(out)


if __name__ == '__main__':
    print(build())
