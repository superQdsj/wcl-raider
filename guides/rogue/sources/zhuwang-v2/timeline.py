"""Three-lane timeline: where each of the three rogues spent Cloak of Shadows (and the Vanishes that cleared a mark).
Times are each run's own WCL times (data/run*/casts.md), mapped piecewise onto run 1's boss pull/kill times so the
three lanes line up by fight segment. Returns HTML for {{TIMELINE}}."""


def t(s):
    m, x = s.split(':')
    return int(m) * 60 + float(x)


# boss pull / kill anchors per run (data/run*/pulls.md: start, start + duration)
ANCH = {
    1: ['0:00', '3:13', '6:43', '14:05', '17:49', '19:47', '24:05', '26:00', '29:26', '29:27'],
    2: ['0:00', '3:14', '6:50', '14:01', '17:56', '19:53', '24:18', '26:12', '29:42', '29:43'],
    3: ['0:00', '3:11', '7:10', '14:23', '17:58', '19:51', '24:21', '26:28', '30:01', '30:02'],
}
END = t(ANCH[1][-1])


def norm(run, s):
    x = t(s)
    a, r = [t(v) for v in ANCH[run]], [t(v) for v in ANCH[1]]
    for i in range(len(a) - 1):
        if a[i] <= x <= a[i + 1]:
            return r[i] + (x - a[i]) / (a[i + 1] - a[i]) * (r[i + 1] - r[i])
    return x


def pct(sec):
    return f'{sec / END * 100:.2f}%'


BANDS = [  # run-1 times
    ('0:22', '3:13', '开场小怪', 'trash'),
    ('3:13', '6:43', '黄金风蛇', 'boss'),
    ('6:56', '14:05', '拉胡艾 · 血誓刺客 · 墓室', 'trash'),
    ('14:05', '17:49', '姆沁巴', 'boss'),
    ('18:02', '19:47', '狂战士', 'trash'),
    ('19:47', '24:05', '部族议会', 'boss'),
    ('24:25', '25:49', '祖尔', 'trash'),
    ('26:00', '29:26', '达萨', 'boss'),
]

CALLOUTS = [  # (start, end, text) run-1 times
    ('0:50', '1:02', '旋风斩'),
    ('3:24', '3:36', '蛇之风'),
    ('7:40', '7:50', '过载'),
    ('14:28', '17:04', '排干体液'),
    ('24:30', '25:30', '黑暗启示'),
    ('27:32', '27:44', '镀金毁灭'),
]

# (run time, kind, label); kind: c = cloak on a core mechanic, m = cloak elsewhere, v = vanish that cleared a mark
LANES = [
    ('Tacokekw', 1, [
        ('0:56.0', 'c', '暗影旋风斩'), ('3:29.6', 'c', '蛇之风'), ('7:44.6', 'c', '过载'),
        ('16:28.0', 'v', '排干体液'), ('17:00.7', 'c', '排干体液'),
        ('24:33.0', 'v', '黑暗启示'), ('25:26.6', 'c', '黑暗启示'), ('27:37.4', 'c', '镀金毁灭'),
    ]),
    ('Qingxinlucky', 2, [
        ('0:56.5', 'c', '暗影旋风斩'), ('3:30.6', 'c', '蛇之风'), ('6:08.6', 'c', '蛇之风'),
        ('9:18.0', 'm', '叉状闪电'), ('13:30.5', 'm', '墓室小怪'), ('14:46.4', 'v', '排干体液'),
        ('15:47.7', 'c', '排干体液'), ('20:13.6', 'm', '斩首之斧（无效）'),
        ('25:18.6', 'c', '黑暗启示'), ('27:50.5', 'c', '镀金毁灭'),
    ]),
    ('Messerknecht', 3, [
        ('0:51.0', 'c', '暗影旋风斩'), ('3:27.7', 'c', '蛇之风'), ('5:37.8', 'c', '蛇之风'), ('7:50.6', 'c', '过载'),
        ('14:31.9', 'v', '排干体液'), ('15:04.7', 'c', '排干体液'), ('16:44.1', 'v', '排干体液'),
        ('18:43.5', 'm', '冰霜震击'), ('24:58.3', 'v', '黑暗启示'), ('25:53.1', 'c', '黑暗启示'), ('28:04.5', 'c', '镀金毁灭'),
    ]),
]
ICON = {'c': 31224, 'm': 31224, 'v': 1856}


def build():
    out = ['<div class="tl">']
    for a, b, label, kind in BANDS:
        out.append(f'<div class="band {kind}" style="left:{pct(t(a))};width:{pct(t(b) - t(a))}">{label}</div>')
    for a, b, text in CALLOUTS:
        out.append(f'<div class="call" style="left:{pct(t(a))};width:{pct(t(b) - t(a))}"><span>{text}</span></div>')
    for i, (name, run, marks) in enumerate(LANES):
        top = f'var(--l{i + 1})'
        out.append(f'<div class="lane" style="top:{top}"></div>')
        out.append(f'<div class="lane-label" style="top:{top}">{name}</div>')
        for at, kind, label in marks:
            x = norm(run, at)
            out.append(f'<img class="mk {kind}" style="left:{pct(x)};top:{top}" src="{{{{I:{ICON[kind]}}}}}" '
                       f'alt="{label}" title="{name} {at} {label}">')
    for m in range(0, 30, 5):
        style = 'left:0;transform:none' if m == 0 else f'left:{pct(m * 60)}'
        out.append(f'<div class="axis" style="{style}">{m}:00</div>')
    out.append('</div>')
    return '\n'.join(out)


if __name__ == '__main__':
    print(build())
