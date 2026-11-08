"""Three-lane timeline: where each of the three rogues spent Cloak of Shadows, plus the Evasions on Lexi's Thorn Blade
and the Vanishes that broke a Bloodthorn root. Times are each run's own WCL times (evidence/uses.md), mapped piecewise
onto run 1's boss pull/kill times (evidence/segments.md) so the three lanes line up by fight segment."""


def t(s):
    m, x = s.split(':')
    return int(m) * 60 + float(x)


# boss segment start / end per run (evidence/segments.md)
ANCH = {
    1: ['0:00', '3:57.3', '7:42.1', '8:54.1', '12:50.7', '13:48.2', '18:14.2', '22:01.2', '25:17.6'],
    2: ['0:00', '4:47.1', '8:35.5', '8:55.7', '12:38.3', '14:46.9', '18:41.9', '22:30.3', '25:52.3'],
    3: ['0:00', '3:45.8', '7:34.2', '8:52.4', '12:50.2', '14:48.4', '18:34.9', '23:11.7', '26:29.9'],
}
END = t('25:40')


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
    ('0:14', '3:57', '开场小怪', 'trash'),
    ('3:57', '7:42', '莱克希 · 科兹齐特 · 梅提克', 'boss'),
    ('7:51', '8:54', '', 'trash'),
    ('8:54', '12:50', '伊库兹', 'boss'),
    ('13:48', '18:14', '鲁伊亚', 'boss'),
    ('18:30', '22:01', '薯身蟾 · 播法者', 'trash'),
    ('22:01', '25:17', '兹欧凯特', 'boss'),
]

CALLOUTS = [  # (start, end, text) run-1 times
    ('0:30', '0:40', '喷涌之花'),
    ('4:06', '7:14', '基岩涌动'),
    ('9:18', '12:30', '唤棘者咆哮'),
    ('19:18', '20:20', '喷毒'),
]

# (run time, kind, label); kind: c = cloak on a core mechanic, m = cloak elsewhere,
# e = evasion on Lexi's Thorn Blade, v = vanish that broke a root
LANES = [
    ('Qingxinlucky', 1, [
        ('0:33.2', 'c', '喷涌之花'), ('3:34.0', 'm', '拔根而起'), ('5:37.0', 'c', '基岩涌动'), ('8:12.0', 'm', '拔根而起'),
        ('12:23.7', 'c', '唤棘者咆哮'), ('15:26.8', 'm', '尖刺盾牌（无用）'), ('19:45.5', 'c', '喷毒'),
    ]),
    ('Tacokekw', 2, [
        ('0:30.7', 'c', '喷涌之花'), ('2:32.6', 'c', '喷涌之花'), ('5:41.6', 'e', '荆棘之刃'), ('10:24.7', 'c', '唤棘者咆哮'),
        ('10:34.4', 'v', '血棘之根'), ('15:06.7', 'm', '光明坠落'), ('17:39.7', 'm', '光明坠落'), ('19:49.6', 'c', '喷毒'),
        ('21:56.2', 'm', '小怪（空交）'), ('24:40.5', 'm', '光绽之力'),
    ]),
    ('Charrend', 3, [
        ('0:33.5', 'c', '喷涌之花'), ('3:52.3', 'c', '基岩涌动'), ('4:40.7', 'e', '荆棘之刃'), ('6:07.7', 'c', '基岩涌动'),
        ('8:18.7', 'c', '喷涌之花'), ('9:35.3', 'v', '血棘之根'), ('10:35.7', 'm', '血棘之根'), ('11:40.2', 'v', '血棘之根'),
        ('12:36.0', 'm', '青翠践踏（物理）'), ('18:02.2', 'm', '凶残痛击（无效）'), ('20:12.0', 'c', '喷毒'),
    ]),
]
ICON = {'c': 31224, 'm': 31224, 'v': 1856, 'e': 5277}


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
    for m in range(0, 26, 5):
        style = 'left:0;transform:none' if m == 0 else f'left:{pct(m * 60)}'
        out.append(f'<div class="axis" style="{style}">{m}:00</div>')
    out.append('</div>')
    return '\n'.join(out)


if __name__ == '__main__':
    print(build())
