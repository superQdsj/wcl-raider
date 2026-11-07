from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import base64
from html import escape
import json
from pathlib import Path


from guidelib import ASSETS, DUNGEONS, SEASON, connect, ensure_spells, load_module, spec_dir, tree_for
from talents import encode, selections

# 由 configure() 按职业目录填好；测试和 build() 都先调用它
P = None          # profile 模块
DIRECTORY = None  # guides/<职业-专精>
DB = None         # sqlite 连接
ICONS = {}


def configure(directory):
    global P, DIRECTORY, DB
    if DB is not None:
        DB.close()
    DIRECTORY = spec_dir(directory)
    P = load_module(DIRECTORY, 'profile')
    DB = connect(DIRECTORY)
    ICONS.clear()
    return load_module(DIRECTORY, 'guides').GUIDES


EXTRA_CSS = '''
.guide-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:20px}
.guide-card{padding:22px;border:1px solid var(--line);background:var(--panel);border-radius:12px}
.guide-card h2{font-size:21px}.guide-card p{color:var(--mute);font-size:13px}
.guide-links{display:flex;gap:16px;color:var(--gold);font-size:13px}
.guide-card.pending{opacity:.45}
.copy-status{font-size:12px;color:var(--mute);min-height:18px;margin:0}
@media(max-width:760px){.guide-grid{grid-template-columns:1fr}}
.combo{margin-top:20px;display:grid;grid-template-columns:1.05fr 1fr;gap:22px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px}
.combo h3{font-size:20px;font-weight:900;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.combo h3 .x{color:var(--faint);font-family:var(--body);font-weight:500;margin:0 4px}
.combo p{margin:10px 0 0;color:#d2cec0;font-size:14.5px}
.combo p b{color:var(--gold)}
.steps{margin:14px 0 0;padding:0;list-style:none;display:grid;gap:8px;counter-reset:s}
.steps li{display:grid;grid-template-columns:26px 1fr;gap:10px;align-items:start;font-size:14px;color:#d2cec0}
.steps li::before{counter-increment:s;content:counter(s);width:26px;height:26px;border-radius:50%;background:var(--gold);color:#1a1608;font:700 13px var(--mono);display:grid;place-items:center}
.steps li b{color:var(--ink)}
.seq{display:grid;gap:12px;align-content:center}
.seq .cap{font-size:12px;color:var(--faint)}
.seq-row{display:grid;grid-template-columns:86px 1fr;gap:10px;align-items:center;font-size:13px;color:var(--mute)}
.track{position:relative;height:34px;background:var(--panel-2);border-radius:6px}
.track .ev{position:absolute;top:5px;transform:translateX(-50%);display:flex;align-items:center}
.track .ev img{width:24px;height:24px;border-radius:5px;border:1px solid #000;box-shadow:0 0 0 2px var(--gold)}
.track .gap{position:absolute;top:50%;height:2px;background:var(--gold-dim);transform:translateY(-50%)}
.track .lbl{position:absolute;right:8px;top:50%;transform:translateY(-50%);font:700 12px var(--mono);color:var(--gold)}
.seq .res{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.seq .res span{font-size:12.5px;border:1px solid var(--gold-dim);color:var(--ink);border-radius:999px;padding:2px 10px;background:rgba(242,210,75,.06)}
.skill{flex-wrap:wrap}
.skill .who{font-weight:500;font-size:12.5px;color:var(--mute)}
.plus{color:var(--faint);font-weight:500;margin:0 2px}
.tag.fire{color:#f29a6b;border-color:rgba(242,154,107,.35)}
.tag.frost{color:#8fd3f0;border-color:rgba(143,211,240,.35)}
.tag.nature{color:var(--venom);border-color:rgba(134,201,124,.35)}
@media(max-width:760px){.combo{grid-template-columns:1fr}}
@media print{body{print-color-adjust:exact}}
.who-line{margin-top:6px;font-size:12.5px;color:var(--gold)}
.mk .ics{display:flex;gap:2px}
.mk.dn .ics{order:1}
.legend{align-items:center}
.legend img{display:inline-block;vertical-align:-5px;margin-right:5px;width:18px;height:18px;border-radius:50%}
/* 手机覆盖放在最后，才能盖过上面的基础规则 */
@media (max-width:520px){
  .code-row{flex-direction:column;align-items:stretch}
  .code-row button{padding:10px 20px}
  .seq-row{grid-template-columns:64px 1fr}
  .track{height:auto;min-height:34px;padding-bottom:22px}
  .track .lbl{top:auto;bottom:4px;transform:none}
}
'''

COPY_SCRIPT = '''
(() => {
  const button = document.getElementById('copy-btn');
  const code = document.getElementById('talent-code');
  const status = document.getElementById('copy-status');
  function done() {
    button.textContent = '已复制';
    status.textContent = '回到游戏天赋界面，选择「导入」并粘贴。';
    setTimeout(() => { button.textContent = '复制'; }, 1600);
  }
  function fallback() {
    const range = document.createRange();
    range.selectNodeContents(code);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    try {
      if (document.execCommand('copy')) { done(); return; }
    } catch (error) {}
    status.textContent = '字符串已选中，请按 ⌘C / Ctrl+C 复制。';
  }
  button.addEventListener('click', () => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code.textContent.trim()).then(done, fallback);
    } else { fallback(); }
  });
})();
'''


def filename(name, extension='html'):
    return f'{P.DATE}-{name}-{P.NAME}.{extension}'


def icon(spell_id, tooltips, size=''):
    name = tooltips[str(spell_id)]['icon']
    if name not in ICONS:
        row = DB.execute('SELECT jpg FROM icon WHERE name=?', (name,)).fetchone()
        if not row or not bytes(row[0]).startswith(b'\xff\xd8'):
            raise ValueError(f'Invalid icon {spell_id}')
        ICONS[name] = base64.b64encode(bytes(row[0])).decode('ascii')
    encoded = ICONS[name]
    return f'<img class="ic {size}" width="28" height="28" src="data:image/jpeg;base64,{encoded}" alt="">'


def spell_link(spell_id, tooltips, label=None):
    name = label or tooltips[str(spell_id)]['name']
    return f'<a href="https://www.wowhead.com/spell={spell_id}" target="_blank" rel="noopener noreferrer">{escape(name)}</a>'


def mechanic_id(name, mapping, tooltips, debuff=False, explicit=None):
    """按名字找机制的技能 ID。同名机制有多个版本（小怪版/首领版）时，行里给 explicit 指定。"""
    if explicit:
        if str(explicit) not in tooltips:
            raise ValueError(f'{name}: explicit spell {explicit} missing from guide.db')
        return explicit
    candidates = [spell_id for spell_id in mapping[name] if tooltips[str(spell_id)].get('description')]
    if debuff:
        with_aura = [spell_id for spell_id in candidates if tooltips[str(spell_id)].get('aura')]
        if with_aura:
            return with_aura[0]
    return candidates[0]


def action_names(row, tooltips):
    return escape(row['action']) if row['action'] else spell_link(row['skills'][0], tooltips)


def skill_chain(skills, tooltips, size='sm'):
    return '<span class="plus">+</span>'.join(f'{icon(spell_id, tooltips, size)}{spell_link(spell_id, tooltips)}' for spell_id in skills)


def row_skills(row, tooltips):
    if row['action'] or len(row['skills']) == 1:
        html = f'{icon(row["skills"][0],tooltips,"sm")}{action_names(row,tooltips)}{action_pill(row["skills"][0])}'
    else:
        html = skill_chain(row['skills'], tooltips)
    if row.get('who'):
        html += f'<span class="who">{escape(row["who"])}</span>'
    return html


def moment_action(row, tooltips):
    if row['action'] or len(row['skills']) == 1:
        return f'<div class="act"><span class="arrow">→</span>{icon(row["skills"][0], tooltips, "lg")}{action_names(row, tooltips)}</div>'
    return ''.join(f'<div class="act"><span class="{"arrow" if index == 0 else "arrow plus"}">{"→" if index == 0 else "+"}</span>{icon(spell_id, tooltips, "lg")}{spell_link(spell_id, tooltips)}</div>' for index, spell_id in enumerate(row['skills']))


def row_tags(row):
    return ''.join(f' <span class="tag{" " + kind if kind else ""}">{escape(text)}</span>' for text, kind in row.get('tags', []))


def combo(guide, tooltips):
    data = guide['combo']
    output = [f'<section id="chapter-3"><h2><span class="k">03</span>{escape(data["title"])}</h2><div class="combo"><div>']
    output.append('<h3>' + '<span class="x">→</span>'.join(f'{icon(spell_id, tooltips, "lg")}{spell_link(spell_id, tooltips)}' for spell_id in data['skills']) + '</h3>')
    output.append(f'<p>{data["intro"]}</p><ol class="steps">')
    output.extend(f'<li><span>{step}</span></li>' for step in data['steps'])
    output.append(f'</ol><p>{data["outro"]}</p></div>')
    label = '；'.join(f'{name} {note}' for name, _, _, _, _, note in data['tracks'])
    output.append(f'<div class="seq" role="img" aria-label="{escape(label)}"><div class="cap">{escape(data["cap"])}</div>')
    for name, spell_id, position, gap_start, gap_width, note in data['tracks']:
        marker = icon(spell_id, tooltips).replace('class="ic " ', '')
        output.append(f'<div class="seq-row"><span>{escape(name)}</span><div class="track"><span class="gap" style="left:{gap_start}%;width:{gap_width}%"></span><span class="ev" style="left:{position}%">{marker}</span><span class="lbl">{escape(note)}</span></div></div>')
    output.append('<div class="res">' + ''.join(f'<span>{escape(item)}</span>' for item in data['result']) + '</div></div></div></section>')
    return ''.join(output)


def action_pill(spell_id):
    kind, label = P.SKILLS[spell_id][:2]
    return f'<span class="pill p-{kind}">{label}</span>'


def clock(milliseconds):
    seconds = max(0, int(milliseconds / 1000))
    return f'{seconds // 60}:{seconds % 60:02d}'


def timeline_skills(guide):
    """01 时间线追踪的大冷却：guide['timeline_skills'] 优先，否则 profile.BIG_COOLDOWNS。"""
    return list(guide.get('timeline_skills') or P.BIG_COOLDOWNS)


def timeline_markers(guide, record, tooltips):
    """推荐玩家那一整场里，大冷却的每一次使用 → 时间线上的点。

    12 秒内接连按下的合成一个点（多个图标）；标签是当时在应对的机制：施放前 4 秒的敌方读条、
    身上的减益、刚被打中的技能、被消除/免疫/反射的技能里，优先取正文路线写过的机制，最多两个，用「+」连。
    guide['timeline_labels'] = {'10:31': '开怪青翠践踏'} 按点的起始时间改标签，值为 None 时去掉这个点。
    """
    big = timeline_skills(guide)
    names = {int(spell_id): ability['name'] for spell_id, ability in record['abilities'].items()}
    by_name = {tooltips[str(spell_id)]['name']: spell_id for spell_id in big}
    route = {row['mechanic'] for stage in guide['route'] for row in stage['rows']}
    answers = defaultdict(set)  # 路线里写明「这个技能应对这个机制」的
    for stage in guide['route']:
        for row in stage['rows']:
            for skill in row['skills']:
                answers[skill].add(row['mechanic'])
    uses = [(use, by_name.get(names.get(use['gid']), use['gid'] if use['gid'] in big else None)) for use in record['uses']]
    uses = sorted(((use, spell_id) for use, spell_id in uses if spell_id), key=lambda item: item[0]['ts'])
    groups = []
    for use, spell_id in uses:
        if groups and use['ts'] - groups[-1][-1][0]['ts'] <= 12000 and use['ts'] - groups[-1][0][0]['ts'] <= 45000:
            groups[-1].append((use, spell_id))
        else:
            groups.append([(use, spell_id)])
    overrides = guide.get('timeline_labels', {})
    markers = []
    for group in groups:
        votes = Counter()
        for use, spell_id in group:
            nearby = [gid for _, gid, _ in use['before']] + use['active'] + use['applied_after']
            nearby += [int(gid) for gid in use['hits']] + [item[0] for item in use.get('removed', [])]
            nearby += [key[1] for key, _ in use.get('blocked', [])]
            for name in dict.fromkeys(names.get(gid) for gid in nearby):
                if name in answers[spell_id]:
                    votes[name] += 3
                elif name in route:
                    votes[name] += 1
        first, last = group[0][0], group[-1][0]
        time = first['time'] if last['ts'] - first['ts'] <= 10000 else f"{first['time']}–{last['time']}"
        ranked = votes.most_common(2)
        # 第二个机制只在它也是正文写明的应对对象时才并列（两件危险事叠在一起）
        label = ' + '.join(name for index, (name, score) in enumerate(ranked) if index == 0 or score >= 3) or None
        label = overrides.get(first['time'], label)
        if label:
            markers.append((first['ts'], label, list(dict.fromkeys(spell_id for _, spell_id in group)), time))
    limit = guide.get('timeline_max', 12)
    if len(markers) > limit:  # 太密时均匀抽样，保留首尾
        markers = [markers[round(index * (len(markers) - 1) / (limit - 1))] for index in range(limit)]
    return markers


def timeline(guide, record, tooltips):
    markers = timeline_markers(guide, record, tooltips)
    if len(markers) < 4:
        raise ValueError('01 时间线不到 4 个点：检查 profile.BIG_COOLDOWNS / guide["timeline_skills"]，或用 timeline_labels 补标签')
    duration = record['duration_ms']
    start = record['start']
    bosses = [stage['name'] for stage in guide['route'] if stage['kind'] == 'boss']
    bands = []
    for pull in record['pulls']:
        pull_name = pull['name'].replace('和', '与')
        label = next((boss for boss in bosses if boss == pull_name or boss in pull_name or pull_name in boss), None)
        label = label or SEASON['pull_alias'].get(pull['name'])
        if not label:
            continue
        bands.append((max(0, pull['start'] - start), min(duration, pull['end'] - start), label))
    output = ['<div class="tl-card"><div class="tl-scroll"><div class="tl">']
    previous = 0
    for beginning, end, label in sorted(bands):
        if beginning > previous:
            output.append(f'<div class="band trash" style="left:{previous / duration * 100:.2f}%;width:{(beginning - previous) / duration * 100:.2f}%">小怪</div>')
        output.append(f'<div class="band boss" style="left:{beginning / duration * 100:.2f}%;width:{(end - beginning) / duration * 100:.2f}%">{escape(label)}</div>')
        previous = end
    if previous < duration:
        output.append(f'<div class="band trash" style="left:{previous / duration * 100:.2f}%;width:{(duration - previous) / duration * 100:.2f}%">小怪</div>')
    for tick in range(0, duration, 300000):
        alignment = ';transform:none' if tick == 0 else ''
        output.append(f'<div class="axis" style="left:{tick / duration * 100:.2f}%{alignment}">{clock(tick)}</div>')
    for index, (timestamp, mechanic, spell_ids, time) in enumerate(markers):
        position = (timestamp - start) / duration * 100
        side = 'up' if index % 2 == 0 else 'dn'
        edge = ' end' if position > 94 else ''
        label_style = ' style="transform:translateX(24px)"' if position < 4 else ''
        icons = ''.join(icon(spell_id, tooltips, 'sm').replace('class="ic sm" ', '') for spell_id in spell_ids)
        output.append(f'<div class="mk {side}{edge}" style="left:{position:.2f}%"><span class="lab"{label_style}>{escape(mechanic)}</span><span class="t"{label_style}>{escape(time)}</span><span class="stem"></span><span class="ics">{icons}</span></div>')
    legend = ''.join(f'<span>{icon(spell_id, tooltips, "sm").replace("class=\"ic sm\" ", "")}{escape(tooltips[str(spell_id)]["name"])}</span>' for spell_id in timeline_skills(guide))
    output.append(f'</div></div><div class="legend"><span><i style="background:var(--gold-dim)"></i>首领战</span><span><i style="background:var(--panel-2)"></i>小怪段</span>{legend}</div></div>')
    return ''.join(output)


def header(title, lede, style, index=False, core=None):
    core = core or P.DEFAULT_CORE
    heading = P.NAME
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark"><title>{P.NAME} · {escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>{style}</style></head><body>
<header><div class="wrap"><div class="eyebrow">MYTHIC+ · {P.EYEBROW} · FIELD MANUAL</div>
<h1><span class="cls">{heading}</span><span class="dot">·</span>{escape(title)}</h1>
<p class="lede">{lede}</p><div class="chips"><span class="chip">专精 <b>{P.SPEC_LABEL}</b></span><span class="chip">英雄天赋 <b>{P.HERO}</b></span><span class="chip">核心 <b>{escape(core)}</b></span></div>'''


def load_records(name):
    """库里这个副本的三场，整理成构建器用的记录：玩家、天赋、首领分段、本职业施放与情境。"""
    records = []
    for run in DB.execute('SELECT * FROM run WHERE dungeon=? ORDER BY rank', (name,)):
        uses = []
        for use in DB.execute('SELECT * FROM class_use WHERE run=? ORDER BY ts', (run['key'],)):
            uses.append({'gid': use['spell'], 'ts': use['ts'], 'time': use['clock'], 'active': json.loads(use['active']),
                         'applied_after': json.loads(use['applied_after']), 'hits': json.loads(use['hits']),
                         'before': json.loads(use['before']), 'removed': json.loads(use['removed']),
                         'blocked': json.loads(use['blocked'])})
        records.append({'key': run['key'], 'url': run['url'], 'level': run['level'], 'duration_ms': int(run['duration_ms']),
                        'keystone_ms': run['keystone_ms'], 'start': run['start'], 'player': {'name': run['player_name']},
                        'combatant': json.loads(run['combatant']), 'pulls': json.loads(run['pulls']), 'uses': uses,
                        'abilities': {str(row['id']): {'name': row['name']} for row in
                                      DB.execute('SELECT id, name FROM ability WHERE run=?', (run['key'],))}})
    if len(records) != 3 or len({record['url'] for record in records}) != 3:
        raise ValueError(f'{name}: 库里应有三场不同的录像，先跑 collect.py')
    return records


def mechanic_map(name, guide, records):
    """机制名 → 本副本里同名的技能 ID，按出现次数排序（同名的小怪版/首领版都在里面）。"""
    keys = [record['key'] for record in records]
    marks = ','.join('?' * len(keys))
    occurrences = {row[0]: row[1] for row in DB.execute(
        f'SELECT spell, COUNT(*) FROM (SELECT spell FROM enemy_cast WHERE run IN ({marks}) UNION ALL '
        f'SELECT spell FROM debuff WHERE run IN ({marks})) GROUP BY spell', keys + keys)}
    names = {}
    for record in records:
        for spell_id, ability in record['abilities'].items():
            names.setdefault(ability['name'], set()).add(int(spell_id))
    wanted = {row['mechanic'] for stop in guide['route'] for row in stop['rows']} | {debuff[0] for debuff in guide['debuffs']}
    missing = wanted - names.keys()
    if missing:
        raise ValueError(f'{name}: 录像里没有这些机制名 {sorted(missing)}')
    return {mechanic: sorted(names[mechanic], key=lambda spell_id: (-occurrences.get(spell_id, 0), spell_id)) for mechanic in sorted(wanted)}


def guide_spells(guide):
    ids = {skill for stop in guide['route'] for row in stop['rows'] for skill in row['skills']}
    ids |= {row['mechanic_id'] for stop in guide['route'] for row in stop['rows'] if row.get('mechanic_id')}
    ids |= set(guide['combo']['skills']) | {track[1] for track in guide['combo']['tracks']}
    ids |= set(timeline_skills(guide)) | set(guide.get('tools', [])) | {spell_id for spell_id, _ in guide['talent_cards']}
    ids |= {debuff[4] for debuff in guide['debuffs'] if len(debuff) > 4}
    return ids


def tooltips_for(ids):
    ensure_spells(DB, ids)
    marks = ','.join('?' * len(ids))
    return {str(row['id']): dict(row) for row in DB.execute(f'SELECT * FROM spell WHERE id IN ({marks})', sorted(ids))}


def render_guide(name, guide, style, tree):
    records = load_records(name)
    selected = records
    mapping = mechanic_map(name, guide, records)
    tooltips = tooltips_for(guide_spells(guide) | {spell_id for ids in mapping.values() for spell_id in ids})
    for mechanic, ids in mapping.items():
        if not any(tooltips[str(spell_id)].get('description') for spell_id in ids):
            raise ValueError(f'{name}: 机制 {mechanic} 没有说明文字')
    nodes = {node['id']: node for group in ['classNodes','specNodes','heroNodes','subTreeNodes'] for node in tree[group]}
    talent_cards = guide['talent_cards']
    talent_keys = guide['talent_keys']
    # 推荐配置必须包含正文用到的全部天赋技能，不只是六张卡：路线行、专题、工具箱里出现的技能，
    # 只要是天赋树里的技能，都算进来。
    tree_spells = {entry.get('spellId') for node in nodes.values() for entry in node['entries']}
    body = {skill for stop in guide['route'] for row in stop['rows'] for skill in row['skills']}
    body |= set(guide.get('combo', {}).get('skills', [])) | set(guide.get('tools', []))
    required = {spell_id for spell_id, _ in talent_cards} | (body & tree_spells)

    def supports_guide(record):
        entries = {talent['id'] for talent in selections(record['combatant']).values()}
        spells = {entry.get('spellId') for node in nodes.values() for entry in node['entries'] if entry['id'] in entries}
        return required <= spells

    record = next((record for record in records if supports_guide(record)), None)
    if record is None:
        raise ValueError(f'{name}: No sampled talent loadout supports the documented toolkit')
    chosen = selections(record['combatant'])
    selected_entries = {talent['id'] for talent in chosen.values()}
    if P.HERO_ENTRY not in selected_entries:
        raise ValueError(f'The recommended build must be {P.HERO}')
    import_string = encode(tree, chosen)
    output = [header(f'{name} 应对手册', guide['lede'], style, core=guide.get('core'))]
    output.append('</div></header><main class="wrap">')
    big_names = '、'.join(tooltips[str(spell_id)]['name'] for spell_id in timeline_skills(guide))
    output.append(f'<section id="chapter-1"><h2><span class="k">01</span>一场里大技能交在哪</h2><p class="sub">一整场 +{record["level"]} 里，{big_names}分别交给了哪个机制。</p>')
    output.append(timeline(guide, record, tooltips) + '</section>')
    output.append('<section id="chapter-2"><h2><span class="k">02</span>先学这四招</h2><div class="moments">')
    for stage_index, row_index in guide['moments']:
        stage = guide['route'][stage_index]
        row = stage['rows'][row_index]
        output.append(f'<article class="mo"><div class="where">{escape(stage["name"])}</div><div class="sig">{escape(row["signal"])}<b>{escape(row["mechanic"])}</b></div>{moment_action(row, tooltips)}{f'<div class="who-line">交给：{escape(row["who"])}</div>' if row.get('who') else ''}<p>{escape(row.get("card") or row["why"])}</p></article>')
    output.append('</div></section>')
    output.append(combo(guide, tooltips))
    output.extend(route_and_rest(name, guide, tooltips, mapping, record, selected, import_string, tree, selected_entries, talent_cards, talent_keys))
    return '\n'.join(output)


def route_and_rest(name, guide, tooltips, mapping, record, selected, import_string, tree, selected_entries, talent_cards, talent_keys):
    output = []
    output.append('<section id="chapter-4"><h2><span class="k">04</span>按路线逐段</h2><p class="sub">每一行：看到什么 → 按什么 → 为什么。</p><div class="route">')
    boss = 0
    for stage in guide['route']:
        if stage['kind'] == 'boss':
            boss += 1
        node = str(boss) if stage['kind'] == 'boss' else '怪'
        output.append(f'<article class="stop {stage["kind"]}"><div class="node">{node}</div><div class="stop-body"><div class="stop-head"><h3>{escape(stage["name"])}</h3><span class="kind">{stage["kind"].upper()}</span></div>')
        for row in stage['rows']:
            spell_id = mechanic_id(row['mechanic'], mapping, tooltips, explicit=row.get('mechanic_id'))
            output.append(f'<div class="row"><div class="mech">{icon(spell_id,tooltips)}<div><div class="n">{spell_link(spell_id,tooltips,row["mechanic"])}</div><div class="s">{escape(row["signal"])}{row_tags(row)}</div></div></div><div class="to" aria-hidden="true">→</div><div class="skill">{row_skills(row,tooltips)}</div><div class="why">{escape(row["why"])}</div></div>')
        if stage['note']:
            output.append(f'<div class="note">{escape(stage["note"])}</div>')
        output.append('</div></article>')
    output.append('</div></section>')
    output.append('<section id="chapter-5"><h2><span class="k">05</span>工具箱</h2><div class="tools">')
    used = {}
    for stage in guide['route']:
        for row in stage['rows']:
            for spell_id in row['skills']:
                used.setdefault(spell_id, []).append(row['mechanic'])
    for spell_id in guide['tools']:
        effect, timing = guide.get('tool_notes', {}).get(spell_id) or P.SKILLS[spell_id][2:]
        locations = '、'.join(list(dict.fromkeys(used.get(spell_id, [])))[:3])
        if not locations:
            continue
        output.append(f'<article class="tool{" star" if spell_id in guide.get('tool_stars', []) else ""}"><div class="top">{icon(spell_id,tooltips)}<div class="nm">{spell_link(spell_id,tooltips)}</div></div><dl class="dl"><dt>作用</dt><dd>{escape(effect)}</dd><dt>本里</dt><dd>{escape(locations)}</dd><dt>时机</dt><dd>{escape(timing)}</dd></dl></article>')
    output.append('</div></section>')
    output.append('<section id="chapter-6"><h2><span class="k">06</span>身上常中的减益</h2><div class="tbl-wrap"><table><thead><tr><th>负面效果</th><th>类型</th><th>能自解吗</th><th>怎么处理</th></tr></thead><tbody>')
    for mechanic, kind, self_help, treatment, *explicit in guide['debuffs']:
        spell_id = mechanic_id(mechanic, mapping, tooltips, debuff=True, explicit=explicit[0] if explicit else None)
        tag = 'poison' if '中毒' in kind else 'bleed' if '流血' in kind else 'magic' if '魔法' in kind else ''
        output.append(f'<tr><td><div class="dname">{icon(spell_id,tooltips,"sm")}{spell_link(spell_id,tooltips,mechanic)}</div></td><td><span class="tag {tag}">{escape(kind)}</span></td><td class="{"no" if self_help == "否" or self_help.startswith("✗") else "yes"}">{escape(self_help)}</td><td>{escape(treatment)}</td></tr>')
    output.append('</tbody></table></div></section>')
    output.append(f'<section id="chapter-7"><h2><span class="k">07</span>天赋</h2><p class="sub">{P.TREE_LABEL} · {P.HERO}。复制后，在游戏天赋界面选择「导入」。</p>')
    output.append(f'<div class="talent"><div class="code-row"><code id="talent-code">{import_string}</code><button type="button" id="copy-btn">复制</button></div><p id="copy-status" class="copy-status" role="status" aria-live="polite">推荐 +{record["level"]} {escape(record["player"]["name"])}同款配置。</p><div class="tal-grid">')
    chosen_spells = {entry.get('spellId') for group in ['classNodes','specNodes','heroNodes'] for node in tree[group] for entry in node['entries'] if entry['id'] in selected_entries}
    for spell_id, effect in talent_cards:
        if spell_id not in chosen_spells:
            in_tree = any(entry.get('spellId') == spell_id for group in ['classNodes','specNodes','heroNodes'] for node in tree[group] for entry in node['entries'])
            if not in_tree:
                raise ValueError(f'Talent card {spell_id} is a baseline ability, not a talent node; drop it from talent_cards')
            raise ValueError(f'Recommended talent card is not selected: {spell_id}')
        output.append(f'<div class="tal{" key" if spell_id in talent_keys else ""}">{icon(spell_id,tooltips)}<div><b>{spell_link(spell_id,tooltips)}</b><span>{escape(effect)}</span></div></div>')
    output.append('</div><div class="refs">参考录像：')
    for reference in selected:
        milliseconds = reference['keystone_ms'] or reference['duration_ms']
        seconds = int(milliseconds / 1000)
        output.append(f'<a href="{escape(reference["url"])}" target="_blank" rel="noopener noreferrer">{escape(reference["player"]["name"])} · +{reference["level"]} · {seconds // 60}:{seconds % 60:02d}</a>')
    output.append(f'</div></div></section></main><footer><div class="wrap">{P.NAME} · {escape(name)} 应对手册 · {P.DATE} · <a href="{P.DATE}-{P.NAME}-八本手册.html">返回八本目录</a></div></footer><script>{COPY_SCRIPT}</script></body></html>')
    return output


def page_style():
    """设计样式（潜行者原稿）+ 第二版组件，强调色换成本职业色。"""
    style = (ASSETS / 'design.css').read_text() + EXTRA_CSS
    for rogue, accent in P.CLASS_ACCENT.items():
        style = style.replace(rogue, accent)
    return style


def build(directory, output_dir=None, png=False, dungeons=None):
    """构建 dungeons 里的几本（默认全部已写完的），并刷新八本目录页。"""
    guides = configure(directory)
    output_dir = Path(output_dir or DIRECTORY)
    tree = tree_for(P.SPEC_ID)
    style = page_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    wanted = dungeons or list(guides)
    unknown = [name for name in wanted if name not in guides]
    if unknown:
        raise ValueError(f'guides.py 里还没有这些副本：{unknown}')
    for name in wanted:
        path = output_dir / filename(name)
        path.write_text(render_guide(name, guides[name], style, tree), encoding='utf-8')
        paths.append(path)
        print(path)
    index = [header('八本手册', '选副本，查<b>信号 → 技能 → 为什么</b>。', style, index=True), f'</div></header><main class="wrap"><section><h2><span class="k">{len(guides):02d} / {len(DUNGEONS):02d}</span>选择副本</h2><div class="guide-grid">']
    for name in DUNGEONS:
        guide = guides.get(name)
        if guide:
            index.append(f'<article class="guide-card"><h2>{escape(name)}</h2><p>{escape(guide["theme"])}</p><div class="guide-links"><a href="{filename(name)}">打开完整手册 →</a><a href="{filename(name,"png")}">查看长图 ↗</a></div></article>')
        else:
            index.append(f'<article class="guide-card pending"><h2>{escape(name)}</h2><p>制作中</p></article>')
    index.append(f'</div></section></main><footer><div class="wrap">{P.NAME} · {P.HERO} · 八本应对手册 · {P.DATE}</div></footer></body></html>')
    index_path = output_dir / f'{P.DATE}-{P.NAME}-八本手册.html'
    index_path.write_text('\n'.join(index), encoding='utf-8')
    print(index_path)
    if png:
        from wclr.export import export
        for path in paths:
            export(path, png=str(path.with_suffix('.png')))
            print(path.with_suffix('.png'))
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='构建职业副本手册（HTML 内嵌全部图标）；--png 需要 Playwright 与 Chrome。')
    parser.add_argument('spec', help='职业目录，如 warrior-arms')
    parser.add_argument('--output-dir', type=Path, help='默认写进职业目录')
    parser.add_argument('--png', action='store_true')
    parser.add_argument('--dungeon', action='append', choices=DUNGEONS, help='只构建这一本（可重复）；目录页照常刷新')
    args = parser.parse_args()
    build(args.spec, args.output_dir, png=args.png, dungeons=args.dungeon)
