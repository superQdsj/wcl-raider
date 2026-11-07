"""从 sources/guide.db 打印一个副本的「本职业技能证据表」：以本职业的非伤害技能为主线，
列出每个技能三场里用了几次、给了谁、伴随哪些敌方机制、有什么直接效果、常接什么，再附机制事实。

用法：
  python3 evidence.py <职业目录> <副本>                    # 总表（写手册的主要输入）
  python3 evidence.py <职业目录> <副本> --ability 法术反射   # 逐次施放：时间、位置、目标、前 4 秒敌方读条、身上减益
  python3 evidence.py <职业目录> <副本> --mechanic 火热冲击  # 该机制每次读条前后 6 秒内本职业按了什么（量 03 专题的时机）
  python3 evidence.py <职业目录> <副本> --sql "SELECT ..."   # 直接查库（表结构见 guidelib.SCHEMA）
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import statistics

from guidelib import DUNGEONS, connect, ensure_spells, load_module, spec_dir, spell_info, tree_for, tree_spells

HIT = {'9': '反射', '10': '免疫'}


def seconds(ms):
    if not ms:
        return '—'
    value = round(ms / 1000, 1) if ms < 10000 else round(ms / 1000)
    return f'{value / 60:g} 分钟' if value >= 60 and value % 6 == 0 else f'{value:g} 秒'


def spread(values):
    values = sorted(values)
    if not values:
        return ''
    if len(values) == 1:
        return f'{values[0]:+.1f}s'
    return f'{values[0]:+.1f}～{values[-1]:+.1f}s（中位 {statistics.median(values):+.1f}s）'


def short(text, width=70):
    text = ' '.join((text or '').split())
    return text if len(text) <= width else text[:width] + '…'


class Data:
    def __init__(self, conn, dungeon):
        self.conn = conn
        self.runs = [dict(row) for row in conn.execute('SELECT * FROM run WHERE dungeon=? ORDER BY rank', (dungeon,))]
        if len(self.runs) != 3:
            raise SystemExit(f'{dungeon}：库里有 {len(self.runs)} 场，先跑 collect.py')
        self.keys = [run['key'] for run in self.runs]
        marks = ','.join('?' * len(self.keys))
        self.names = {}
        for row in conn.execute(f'SELECT id, name FROM ability WHERE run IN ({marks})', self.keys):
            self.names[row['id']] = row['name']
        self.uses = [dict(row) for row in conn.execute(f'SELECT * FROM class_use WHERE run IN ({marks}) ORDER BY run, ts', self.keys)]
        for use in self.uses:
            for field in ('active', 'applied_after', 'hits', 'before', 'after', 'removed', 'blocked', 'after_hits'):
                use[field] = json.loads(use[field])
        self.assoc = [dict(row) for row in conn.execute(f'SELECT * FROM assoc WHERE run IN ({marks})', self.keys)]
        self.enemy = [dict(row) for row in conn.execute(f'SELECT * FROM enemy_cast WHERE run IN ({marks})', self.keys)]
        self.debuffs = [dict(row) for row in conn.execute(f'SELECT * FROM debuff WHERE run IN ({marks})', self.keys)]
        self.index = {key: index + 1 for index, key in enumerate(self.keys)}

    def name(self, spell_id):
        return self.names.get(spell_id, str(spell_id))


def overview(data, info, keep):
    out = [f"# 证据表 · 三场：" + ' / '.join(f"#{i + 1} {run['player_name']} +{run['level']}" for i, run in enumerate(data.runs)), '']
    out.append('读法：每个技能先看「伴随」和「直接效果」，再按技能说明讲通为什么；伴随只说明时间上接近。')
    out.append('时间差 = 本技能减去敌方读条开始或施放的秒数（正数 = 敌方先动、本技能在后）。读条开始和落地分开量，用 --mechanic。\n')
    by_spell = defaultdict(list)
    dropped = Counter()
    for use in data.uses:
        tip = info.get(use['spell'], {})
        # 留下：profile/天赋树里的技能，以及有冷却的基础技能（清洁、圣盾这类）；去掉：饰品药水、无冷却的循环技能
        wanted = use['spell'] in keep or data.name(use['spell']) in keep or tip.get('cooldown_ms')
        if wanted and not (tip.get('description') or '').startswith('[Item Effect]'):
            by_spell[use['spell']].append(use)
        else:
            dropped[data.name(use['spell'])] += 1
    data.uses = [use for uses in by_spell.values() for use in uses]
    data.uses.sort(key=lambda use: (use['run'], use['ts']))
    assoc = defaultdict(lambda: defaultdict(lambda: {'runs': set(), 'n': 0, 'of': 0, 'expected': 0.0, 'chans': Counter()}))
    for row in data.assoc:
        item = assoc[row['spell']][row['mechanic']]
        item['runs'].add(row['run'])
        item['n'] += row['n']
        item['of'] += row['of']
        item['expected'] += row['n'] / row['lift'] if row['lift'] else 0
        item['chans'].update(json.loads(row['chans']))
    out.append('## 一、本职业技能 → 用在哪\n')
    for spell_id, uses in sorted(by_spell.items(), key=lambda item: -len(item[1])):
        per_run = Counter(data.index[use['run']] for use in uses)
        gaps = [b['ts'] - a['ts'] for a, b in zip(uses, uses[1:]) if a['run'] == b['run']]
        tip = info.get(spell_id, {})
        cooldown = seconds(tip.get('cooldown_ms'))
        if (tip.get('charges') or 1) > 1:
            cooldown += f" ×{tip['charges']} 充能"
        mods = tip.get('cooldown_mods') or {}
        if mods:
            cooldown += '（天赋改：' + '、'.join(f'{seconds(ms)}[{mod}]' for mod, ms in mods.items()) + '）'
        out.append(f"### {data.name(spell_id)} {spell_id} · 冷却 {cooldown} · 最短间隔 {seconds(min(gaps)) if gaps else '—'} · "
                   f"共 {len(uses)} 次（" + ' / '.join(f'#{i} {per_run.get(i, 0)}' for i in (1, 2, 3)) + '）')
        out.append(f"- 说明：{short(tip.get('description'), 90)}")
        targets = Counter(use['target'] for use in uses)
        out.append('- 给谁：' + '、'.join(f'{target}×{n}' for target, n in targets.most_common(5)))
        lines = []
        for mechanic, item in sorted(assoc[spell_id].items(), key=lambda kv: (-len(kv[1]['runs']), -kv[1]['n'])):
            lift = item['n'] / item['expected'] if item['expected'] else 999
            dts = [dt for use in uses for dt, gid, _ in use['before'] + use['after'] if data.name(gid) == mechanic]
            chans = '、'.join(name for name, _ in item['chans'].most_common(2))
            lines.append(f"{mechanic} {len(item['runs'])}/3 场·{item['n']}/{item['of']} 次·{lift:.1f} 倍[{chans}]"
                         + (f" 时间差 {spread([-dt for dt in dts])}" if dts else ''))
        if lines:
            out.append('- 伴随：' + '；'.join(lines[:8]))
        effects = Counter()
        for use in uses:
            for debuff, _target, inferred in use['removed']:
                effects[f"{'推断消除' if inferred else '驱散'} {data.name(debuff)}"] += 1
            for (hit, gid), n in use['blocked']:
                effects[f"{HIT.get(str(hit), hit)} {data.name(gid)}"] += n
        if effects:
            out.append('- 直接效果：' + '、'.join(f'{text}×{n}' for text, n in effects.most_common()))
        places = Counter(use['location'] for use in uses)
        out.append('- 位置：' + '、'.join(f'{place}×{n}' for place, n in places.most_common(4)))
        out.append('')
    if dropped:
        out.append('不展开（饰品、药水、种族、循环技能）：' + '、'.join(f'{name}×{n}' for name, n in dropped.most_common()) + '\n')
    out.append('## 二、5 秒内连用（三场合计 ≥3 次）\n')
    chains = defaultdict(list)
    for a, b in zip(data.uses, data.uses[1:]):
        if a['run'] == b['run'] and a['spell'] != b['spell'] and b['ts'] - a['ts'] <= 5000:
            chains[(a['spell'], b['spell'])].append((b['ts'] - a['ts']) / 1000)
    for (a, b), gaps in sorted(chains.items(), key=lambda kv: -len(kv[1])):
        if len(gaps) >= 3:
            out.append(f'- {data.name(a)} → {data.name(b)} ×{len(gaps)}，间隔 {min(gaps):.1f}～{max(gaps):.1f}s（中位 {statistics.median(gaps):.1f}s）')
    out.append('\n## 三、相关敌方机制的事实\n')
    linked = {mechanic for spell in assoc.values() for mechanic in spell}
    linked |= {data.name(debuff) for use in data.uses for debuff, _, _ in use['removed']}
    linked |= {data.name(gid) for use in data.uses for (_, gid), _ in use['blocked']}
    linked |= {data.name(row['spell']) for row in data.debuffs}
    casts = defaultdict(lambda: {'ids': Counter(), 'runs': set(), 'source': Counter(), 'target': Counter()})
    for row in data.enemy:
        name = data.name(row['spell'])
        if name in linked:
            item = casts[name]
            item['ids'][row['spell']] += 1
            item['runs'].add(row['run'])
            item['source'][row['source']] += 1
            if row['type'] == 'cast' and row['target']:
                item['target'][row['target'].split('·')[0] if not row['target'].startswith('敌方') else '敌方'] += 1
    out.append('| 机制 | ID | 场次·次数 | 施法者 | 施放目标 | 驱散/持续 | 说明 |\n|---|---|---|---|---|---|---|')
    for name in sorted(linked, key=lambda name: -sum(casts[name]['ids'].values()) if name in casts else 0):
        item = casts.get(name)
        ids = [spell_id for spell_id, _ in item['ids'].most_common()] if item else sorted(
            {row['spell'] for row in data.debuffs if data.name(row['spell']) == name}
            or {spell_id for spell_id, other in data.names.items() if other == name and spell_id in info}
            or {spell_id for spell_id, other in data.names.items() if other == name})
        tip = next((info[spell_id] for spell_id in ids if info.get(spell_id, {}).get('description')), {})
        source = '、'.join(f'{s}×{n}' for s, n in item['source'].most_common(2)) if item else '（只有减益）'
        target = '、'.join(f'{t}×{n}' for t, n in item['target'].most_common(3)) if item else ''
        count = f"{len(item['runs'])}/3·{sum(item['ids'].values())}" if item else ''
        out.append(f"| {name} | {ids[0] if ids else ''} | {count} | {source} | {target} | {tip.get('dispel') or '—'}/{seconds(tip.get('duration_ms'))} | {short(tip.get('description'))} |")
    out.append('\n施放目标「自己」= 本职业玩家。只打坦克的读条（多为「坦克×n」）才能用嘲讽改目标。')
    out.append('\n## 四、本职业身上的减益怎么结束\n')
    endings = defaultdict(lambda: {'n': 0, 'runs': set(), 'how': Counter(), 'dur': []})
    for row in data.debuffs:
        item = endings[data.name(row['spell'])]
        item['n'] += 1
        item['runs'].add(row['run'])
        item['dur'].append((row['end'] - row['start']) / 1000)
        how = row['reason'] + (f"（{data.name(row['by_spell'])}{'，推断' if row['inferred'] else ''}）" if row['by_spell'] else '')
        item['how'][how] += 1
    for name, item in sorted(endings.items(), key=lambda kv: -kv[1]['n'])[:20]:
        out.append(f"- {name}：{len(item['runs'])}/3 场 {item['n']} 次，中位 {statistics.median(item['dur']):.0f}s；"
                   + '、'.join(f'{how}×{n}' for how, n in item['how'].most_common(3)))
    return '\n'.join(out)


def ability_detail(data, query):
    uses = [use for use in data.uses if query in (str(use['spell']), data.name(use['spell']))]
    if not uses:
        raise SystemExit(f'没有找到技能 {query}')
    out = [f'# {query} · 逐次施放（{len(uses)} 次）', '', '| 场 | 时间 | 位置 | 目标 | 血量 | 前 4 秒敌方 | 身上减益 | 效果 |', '|---|---|---|---|---|---|---|---|']
    for use in uses:
        before = '、'.join(f"{data.name(gid)}{dt:+.1f}s" for dt, gid, _ in use['before'][-3:])
        active = '、'.join(data.name(gid) for gid in use['active'][:3])
        effect = '、'.join([f'消除{data.name(d)}' for d, _, _ in use['removed']] + [f"{HIT.get(str(h), h)}{data.name(g)}×{n}" for (h, g), n in use['blocked']])
        hp = f"{use['hp']:.0f}%" if use['hp'] is not None else ''
        out.append(f"| #{data.index[use['run']]} | {use['clock']} | {use['location']} | {use['target']} | {hp} | {before} | {active} | {effect} |")
    return '\n'.join(out)


def mechanic_detail(data, query):
    """该机制每次出现前后 6 秒内本职业按了什么，时间差分别相对读条开始和落地（读条结束、生效）。"""
    ids = {spell_id for spell_id, name in data.names.items() if name == query or str(spell_id) == query}
    casts = sorted((row for row in data.enemy if row['spell'] in ids and row['type'] in ('begincast', 'cast')),
                   key=lambda r: (r['run'], r['ts']))
    if not casts:
        raise SystemExit(f'没有找到敌方机制 {query}')
    events, used = [], set()
    for index, row in enumerate(casts):  # 读条开始配上随后同一施法者的落地
        if index in used:
            continue
        land = None
        if row['type'] == 'begincast':
            land = next((j for j in range(index + 1, len(casts)) if j not in used and casts[j]['type'] == 'cast'
                         and casts[j]['run'] == row['run'] and casts[j]['source'] == row['source']
                         and 0 <= casts[j]['ts'] - row['ts'] < 8000), None)
            if land is not None:
                used.add(land)
            events.append((row, casts[land] if land is not None else None))
        else:
            events.append((None, row))
    by_run = defaultdict(list)
    for use in data.uses:
        by_run[use['run']].append(use)
    from_start, from_land, per_run = defaultdict(list), defaultdict(list), defaultdict(list)
    out = [f'# {query} · 每次出现前后 6 秒内本职业按了什么', '', '时间差：读条开始 → 本技能 / 落地 → 本技能（正数 = 本技能在后）', '']
    for begin, land in events:
        anchor = begin or land
        near = [use for use in by_run[anchor['run']] if -6000 <= use['ts'] - anchor['ts'] <= 6000 + (land['ts'] - anchor['ts'] if land else 0)]
        parts = []
        for use in near:
            name = data.name(use['spell'])
            text = name
            if begin:
                dt = (use['ts'] - begin['ts']) / 1000
                from_start[name].append(dt)
                text += f' 读条{dt:+.1f}s'
            if land:
                dt = (use['ts'] - land['ts']) / 1000
                from_land[name].append(dt)
                per_run[(name, data.index[anchor['run']])].append(dt)
                text += f' 落地{dt:+.1f}s'
            parts.append(text)
        start = next(run['start'] for run in data.runs if run['key'] == anchor['run'])
        clock = int((anchor['ts'] - start) / 1000)
        target = (land or anchor)['target'] or '—'
        out.append(f"- #{data.index[anchor['run']]} {clock // 60}:{clock % 60:02d} {anchor['source']} → {target}：" + ('、'.join(parts) or '—'))
    out.append(f'\n共 {len(events)} 次。')
    names = Counter({name: len(values) for name, values in (from_land or from_start).items()})
    for name, n in names.most_common(6):
        line = f'- {name}×{n}'
        if from_start.get(name):
            line += f'：相对读条开始 {spread(from_start[name])}'
        if from_land.get(name):
            line += f'；相对落地 {spread(from_land[name])}；每场中位 ' + ' / '.join(
                f'#{i} {statistics.median(per_run[(name, i)]):+.1f}s' for i in (1, 2, 3) if per_run.get((name, i)))
        out.append(line)
    out.append('专题写时机时，用每场中位附近的窄范围，并写清相对读条开始还是落地。')
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('spec')
    parser.add_argument('dungeon', choices=DUNGEONS)
    parser.add_argument('--ability')
    parser.add_argument('--mechanic')
    parser.add_argument('--sql')
    args = parser.parse_args()
    directory = spec_dir(args.spec)
    conn = connect(directory)
    if args.sql:
        for row in conn.execute(args.sql):
            print(' | '.join(str(value) for value in tuple(row)))
        return
    data = Data(conn, args.dungeon)
    if args.ability:
        print(ability_detail(data, args.ability))
    elif args.mechanic:
        print(mechanic_detail(data, args.mechanic))
    else:
        profile = load_module(directory, 'profile')
        counts = Counter(row['spell'] for row in data.enemy) + Counter(row['spell'] for row in data.debuffs)
        ensure_spells(conn, {use['spell'] for use in data.uses} | {spell for spell, n in counts.items() if n >= 2})
        ensure_spells(conn, profile.SKILLS)
        keep = set(profile.SKILLS) | tree_spells(tree_for(profile.SPEC_ID), groups=('classNodes', 'specNodes', 'heroNodes'))
        info = spell_info(conn)
        keep |= {info[spell]['name'] for spell in profile.SKILLS}  # 同名不同 ID（如英勇飞跃 6544 / 52174）
        print(overview(data, info, keep))


if __name__ == '__main__':
    main()
