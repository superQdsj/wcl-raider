from __future__ import annotations

import argparse
import base64
from html import escape
import json
from pathlib import Path
import sys

from guides import GUIDES
from talents import encode, selections

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[1]
SOURCE = DIRECTORY / 'sources'
DATE = '2026-11-07'
DUNGEONS = ['毒牙祭坛', '夺目谷', '红玉新生法池', '密谋小径', '纳洛拉克的洞穴', '塞塔里斯神庙', '虚空之痕竞技场', '诸王之眠']

TOOLS = [
    (23920, '20%魔法减伤，最多5秒；反射首个可反射法术。', '命中前开；反射消耗即结束，不清已有负面。'),
    (386208, '15%全伤减免，代价是造成伤害降低10%。', '危险前切入，结束后切回战斗姿态。'),
    (118038, '30%全伤减免＋100%招架，持续8秒。', '提前覆盖叠伤；招架不免疫流血和范围伤害。'),
    (18499, '解恐惧、闷棍与部分瘫痪；无所畏惧额外解减速。', '控制上身后用；不解普通昏迷。'),
    (97462, '大秘境提高全队15%当前与最大生命，持续10秒。', '团队爆发前开，按约定轮次使用。'),
    (202168, '攻击敌人，自疗基础值为最大生命的30%。', '掉血后用，需要可攻击目标。'),
    (6552, '打断读条，并封锁该系5秒。', '按轮次断危险读条。'),
    (46968, '前方10码昏迷2秒；单体可补风暴之锤。', '漏断时补停，注意昏迷免疫与递减。'),
    (100, '冲向敌人；冷酷追杀可解除移动限制。', '须有距离与通路；解根独立间隔30秒。'),
    (6544, '跳向安全落点，腾跃步伐提供后续加速。', '躲地面、避正面；定身时另找解法。'),
    (355, '强制目标攻击你 6 秒。', '只在反射就绪时嘲讽读条怪；先跟坦克打招呼。'),
    (384110, '无视护甲的远程投掷，对吸收护盾额外 500% 伤害。', '护盾一出现就丢，不用贴近。'),
    (386164, '输出姿态：暴击 +3%，移动限制持续时间 −10%。', '危险一过就切回来，别整场挂防御姿态。'),
    (107570, '单体昏迷 4 秒，能晕断引导。', '停引导和读条；注意昏迷免疫。'),
]

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


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def filename(name, extension='html'):
    return f'{DATE}-{name}-武器战.{extension}'


def icon(spell_id, tooltips, size=''):
    tooltip = tooltips[str(spell_id)]
    content = (SOURCE / 'icons' / f"{tooltip['icon']}.jpg").read_bytes()
    if not content.startswith(b'\xff\xd8'):
        raise ValueError(f'Invalid icon {spell_id}')
    encoded = base64.b64encode(content).decode('ascii')
    return f'<img class="ic {size}" width="28" height="28" src="data:image/jpeg;base64,{encoded}" alt="">'


def spell_link(spell_id, tooltips, label=None):
    name = label or tooltips[str(spell_id)]['name']
    return f'<a href="https://www.wowhead.com/spell={spell_id}" target="_blank" rel="noopener noreferrer">{escape(name)}</a>'


def mechanic_id(name, mapping, tooltips, debuff=False):
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
    kind, label = {
        23920: ('dr', '反射／减伤'), 386208: ('dr', '减伤'),
        118038: ('dr', '减伤'), 18499: ('clr', '自解'),
        97462: ('heal', '团队'), 202168: ('heal', '自疗'),
        6552: ('mv', '打断'), 46968: ('mv', '群控'),
        107570: ('mv', '单控'), 100: ('mv', '位移'), 6544: ('mv', '位移'),
        355: ('imm', '嘲讽'), 384110: ('imm', '破盾'), 386164: ('mv', '姿态'),
    }[spell_id]
    return f'<span class="pill p-{kind}">{label}</span>'


def clock(milliseconds):
    seconds = max(0, int(milliseconds / 1000))
    return f'{seconds // 60}:{seconds % 60:02d}'


def timeline(guide, record, tooltips):
    names = {int(spell_id): ability['name'] for spell_id, ability in record['abilities'].items()}
    candidates = []
    for stage in guide['route']:
        for row in stage['rows']:
            for use in record['uses']:
                nearby = set(use['active'] + use['applied_after'])
                nearby.update(int(spell_id) for spell_id in use['hits'])
                nearby.update(item[1] for item in use['before'])
                if use['gid'] in row['skills'] and row['mechanic'] in {names.get(spell_id) for spell_id in nearby}:
                    candidates.append((use['ts'], row['mechanic'], use['gid'], use['time']))
                    break
    unique = []
    for item in sorted(set(candidates)):
        if any(item[1] == existing[1] for existing in unique):
            continue
        if unique and item[0] - unique[-1][0] < 45000:
            continue
        unique.append(item)
    if len(unique) < 4:
        raise ValueError('Insufficient distinct, mechanism-linked timeline entries')
    if len(unique) > 7:
        unique = [unique[round(index * (len(unique) - 1) / 6)] for index in range(7)]
    duration = record['duration_ms']
    start = record['start']
    bosses = [stage['name'] for stage in guide['route'] if stage['kind'] == 'boss']
    bands = []
    for pull in record['pulls']:
        pull_name = pull['name'].replace('和', '与')
        label = next((boss for boss in bosses if boss == pull_name or boss in pull_name or pull_name in boss), None)
        if label is None and pull['name'] == '光明众花':
            label = '莱克希议会'
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
    for index, (timestamp, mechanic, spell_id, time) in enumerate(unique):
        position = (timestamp - start) / duration * 100
        side = 'up' if index % 2 == 0 else 'dn'
        edge = ' end' if position > 94 else ''
        label_style = ' style="transform:translateX(24px)"' if position < 4 else ''
        marker_icon = icon(spell_id, tooltips, 'sm').replace('class="ic sm" ', '')
        output.append(f'<div class="mk {side}{edge}" style="left:{position:.2f}%"><span class="lab"{label_style}>{escape(mechanic)}</span><span class="t"{label_style}>{escape(time)}</span><span class="stem"></span>{marker_icon}</div>')
    output.append('</div></div><div class="legend"><span><i style="background:var(--gold-dim)"></i>首领</span><span><i style="background:var(--panel-2)"></i>小怪／转场</span><span>图标为应对技能；时刻随拉法变化。</span></div></div>')
    return ''.join(output)


def header(title, lede, style, index=False, core='反射 / 姿态 / 剑在人在'):
    heading = '武器战'
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark"><title>武器战 · {escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>{style}</style></head><body>
<header><div class="wrap"><div class="eyebrow">MYTHIC+ · ARMS WARRIOR · FIELD MANUAL</div>
<h1><span class="cls">{heading}</span><span class="dot">·</span>{escape(title)}</h1>
<p class="lede">{lede}</p><div class="chips"><span class="chip">专精 <b>武器战士</b></span><span class="chip">英雄天赋 <b>屠戮者</b></span><span class="chip">核心 <b>{escape(core)}</b></span></div>'''


def render_guide(name, guide, style, tooltips, tree):
    directory = SOURCE / name
    selected = read(directory / 'selected.json')
    if len(selected) != 3 or len({row['url'] for row in selected}) != 3:
        raise ValueError(f'{name}: expected three distinct runs')
    records = [read(directory / row['file']) for row in selected]
    nodes = {node['id']: node for group in ['classNodes','specNodes','heroNodes','subTreeNodes'] for node in tree[group]}
    talent_cards = guide['talent_cards']
    talent_keys = guide['talent_keys']
    required = {spell_id for spell_id, _ in talent_cards}

    def supports_guide(record):
        entries = {talent['id'] for talent in selections(record['combatant']).values()}
        spells = {entry.get('spellId') for node in nodes.values() for entry in node['entries'] if entry['id'] in entries}
        return required <= spells

    record = next((record for record in records if supports_guide(record)), None)
    if record is None:
        raise ValueError(f'{name}: No sampled talent loadout supports the documented toolkit')
    mapping = read(directory / 'mechanics.json')
    chosen = selections(record['combatant'])
    selected_entries = {talent['id'] for talent in chosen.values()}
    if 123390 not in selected_entries:
        raise ValueError('The recommended build must be Slayer')
    import_string = encode(tree, chosen)
    output = [header(f'{name} 应对手册', guide['lede'], style, core=guide.get('core', '反射 / 姿态 / 剑在人在'))]
    output.append('</div></header><main class="wrap">')
    output.append('<section id="chapter-1"><h2><span class="k">01</span>全程关键技能时间线</h2><p class="sub">记住技能交给谁；实战看点名和读条。</p>')
    output.append(timeline(guide, record, tooltips) + '</section>')
    output.append('<section id="chapter-2"><h2><span class="k">02</span>先学这四招</h2><div class="moments">')
    for stage_index, row_index in guide['moments']:
        stage = guide['route'][stage_index]
        row = stage['rows'][row_index]
        output.append(f'<article class="mo"><div class="where">{escape(stage["name"])}</div><div class="sig">{escape(row["signal"])}<b>{escape(row["mechanic"])}</b></div>{moment_action(row, tooltips)}<p>{escape(row["why"])}</p></article>')
    output.append('</div></section>')
    output.append(combo(guide, tooltips))
    output.extend(route_and_rest(name, guide, tooltips, mapping, record, selected, directory, import_string, tree, selected_entries, talent_cards, talent_keys))
    return '\n'.join(output)


def route_and_rest(name, guide, tooltips, mapping, record, selected, directory, import_string, tree, selected_entries, talent_cards, talent_keys):
    output = []
    output.append('<section id="chapter-4"><h2><span class="k">04</span>按路线逐段</h2><p class="sub">每一行：看到什么 → 按什么 → 为什么。</p><div class="route">')
    boss = 0
    for stage in guide['route']:
        if stage['kind'] == 'boss':
            boss += 1
        node = str(boss) if stage['kind'] == 'boss' else '怪'
        output.append(f'<article class="stop {stage["kind"]}"><div class="node">{node}</div><div class="stop-body"><div class="stop-head"><h3>{escape(stage["name"])}</h3><span class="kind">{stage["kind"].upper()}</span></div>')
        for row in stage['rows']:
            spell_id = mechanic_id(row['mechanic'], mapping, tooltips)
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
    tools = {spell_id: (effect, timing) for spell_id, effect, timing in TOOLS}
    for spell_id in guide.get('tools', [spell_id for spell_id, _, _ in TOOLS]):
        effect, timing = guide.get('tool_notes', {}).get(spell_id, tools[spell_id])
        locations = '、'.join(list(dict.fromkeys(used.get(spell_id, [])))[:3])
        if not locations:
            continue
        output.append(f'<article class="tool{" star" if spell_id in guide.get('tool_stars', [23920,118038]) else ""}"><div class="top">{icon(spell_id,tooltips)}<div class="nm">{spell_link(spell_id,tooltips)}</div></div><dl class="dl"><dt>作用</dt><dd>{escape(effect)}</dd><dt>本里</dt><dd>{escape(locations)}</dd><dt>时机</dt><dd>{escape(timing)}</dd></dl></article>')
    output.append('</div></section>')
    output.append('<section id="chapter-6"><h2><span class="k">06</span>身上常中的减益</h2><div class="tbl-wrap"><table><thead><tr><th>负面效果</th><th>类型</th><th>能自解吗</th><th>怎么处理</th></tr></thead><tbody>')
    for mechanic, kind, self_help, treatment in guide['debuffs']:
        spell_id = mechanic_id(mechanic, mapping, tooltips, debuff=True)
        tag = 'poison' if '中毒' in kind else 'bleed' if '流血' in kind else 'magic' if '魔法' in kind else ''
        output.append(f'<tr><td><div class="dname">{icon(spell_id,tooltips,"sm")}{spell_link(spell_id,tooltips,mechanic)}</div></td><td><span class="tag {tag}">{escape(kind)}</span></td><td class="{"no" if self_help == "否" else "yes"}">{escape(self_help)}</td><td>{escape(treatment)}</td></tr>')
    output.append('</tbody></table></div></section>')
    output.append('<section id="chapter-7"><h2><span class="k">07</span>天赋</h2><p class="sub">武器 · 屠戮者。复制后，在游戏天赋界面选择「导入」。</p>')
    output.append(f'<div class="talent"><div class="code-row"><code id="talent-code">{import_string}</code><button type="button" id="copy-btn">复制</button></div><p id="copy-status" class="copy-status" role="status" aria-live="polite">推荐 +{record["level"]} {escape(record["player"]["name"])}同款配置。</p><div class="tal-grid">')
    chosen_spells = {entry.get('spellId') for group in ['classNodes','specNodes','heroNodes'] for node in tree[group] for entry in node['entries'] if entry['id'] in selected_entries}
    for spell_id, effect in talent_cards:
        if spell_id not in chosen_spells:
            raise ValueError(f'Recommended talent card is not selected: {spell_id}')
        output.append(f'<div class="tal{" key" if spell_id in talent_keys else ""}">{icon(spell_id,tooltips)}<div><b>{spell_link(spell_id,tooltips)}</b><span>{escape(effect)}</span></div></div>')
    output.append('</div><div class="refs">参考录像：')
    for selected_row in selected:
        reference = read(directory / selected_row['file'])
        milliseconds = reference['keystone_ms'] or reference['duration_ms']
        seconds = int(milliseconds / 1000)
        output.append(f'<a href="{escape(reference["url"])}" target="_blank" rel="noopener noreferrer">{escape(reference["player"]["name"])} · +{reference["level"]} · {seconds // 60}:{seconds % 60:02d}</a>')
    output.append(f'</div></div></section></main><footer><div class="wrap">武器战 · {escape(name)} 应对手册 · {DATE} · <a href="{DATE}-武器战-八本手册.html">返回八本目录</a></div></footer><script>{COPY_SCRIPT}</script></body></html>')
    return output


def build(output_dir, png=False):
    tooltips = read(SOURCE / 'spells.json')
    tree = read(SOURCE / 'arms-tree.json')
    style = (SOURCE / 'design.css').read_text() + EXTRA_CSS
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, guide in GUIDES.items():
        path = output_dir / filename(name)
        path.write_text(render_guide(name, guide, style, tooltips, tree), encoding='utf-8')
        paths.append(path)
        print(path)
    index = [header('八本手册', '选副本，查<b>信号 → 技能 → 为什么</b>。', style, index=True), f'</div></header><main class="wrap"><section><h2><span class="k">{len(GUIDES):02d} / {len(DUNGEONS):02d}</span>选择副本</h2><div class="guide-grid">']
    for name in DUNGEONS:
        guide = GUIDES.get(name)
        if guide:
            index.append(f'<article class="guide-card"><h2>{escape(name)}</h2><p>{escape(guide["theme"])}</p><div class="guide-links"><a href="{filename(name)}">打开完整手册 →</a><a href="{filename(name,"png")}">查看长图 ↗</a></div></article>')
        else:
            index.append(f'<article class="guide-card pending"><h2>{escape(name)}</h2><p>重写中</p></article>')
    index.append(f'</div></section></main><footer><div class="wrap">武器战 · 屠戮者 · 八本应对手册 · {DATE}</div></footer></body></html>')
    index_path = output_dir / f'{DATE}-武器战-八本手册.html'
    index_path.write_text('\n'.join(index), encoding='utf-8')
    print(index_path)
    if png:
        sys.path.insert(0, str(ROOT / '.claude/skills/mplus-review/scripts'))
        from wclr.export import export
        for path in paths:
            export(path, png=str(path.with_suffix('.png')))
            print(path.with_suffix('.png'))
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='离线重建武器战八本攻略；--png 额外需要 Playwright 与 Chrome。')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reviews')
    parser.add_argument('--png', action='store_true')
    args = parser.parse_args()
    build(args.output_dir.resolve(), png=args.png)
