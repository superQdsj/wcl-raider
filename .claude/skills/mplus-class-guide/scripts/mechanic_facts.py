"""列出一个副本三场录像里的机制事实：敌方技能由谁施放、该职业技能的连用、
每个技能的实际最短施放间隔（技能说明里没有冷却，别凭记忆写），以及技能给了谁（职责）。

用法：python3 mechanic_facts.py <guides/<职业-专精>/sources/<副本>> [--top 40]

读取该目录的 selected.json 与对应记录 JSON（research.py 的产物），
用 WCL 报告的 actors 把 enemy_casts 的 sourceID 换成怪物名（走本地缓存，首次需要 API 点数）。
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / '.claude/skills/mplus-review/scripts'))

from wclr.api import Client  # noqa: E402
from wclr.context import load_run  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--top', type=int, default=40, help='施法者表最多列多少个敌方技能')
    args = parser.parse_args()
    directory = args.directory.resolve()
    selected = json.loads((directory / 'selected.json').read_text())
    client = Client()
    casters: dict[str, Counter] = {}
    totals = Counter()
    runs_seen: dict[str, set] = {}
    chains = Counter()
    gaps: dict[str, list] = {}
    given: dict[str, Counter] = {}
    for row in selected:
        record = json.loads((directory / row['file']).read_text())
        run = load_run(client, record['code'], str(record['fight']))
        abilities = record['abilities']
        for event in record['enemy_casts']:
            name = abilities.get(str(event['abilityGameID']), {}).get('name')
            actor = run.actors.get(event.get('sourceID'), {})
            source = actor.get('name')
            if not name or not source or source == 'Environment' or actor.get('type') != 'NPC':
                continue
            casters.setdefault(name, Counter())[source] += 1
            totals[name] += 1
            runs_seen.setdefault(name, set()).add(row['file'])
        uses = sorted(record['uses'], key=lambda use: use['ts'])
        last = {}
        for use in uses:
            name = abilities.get(str(use['gid']), {}).get('name', use['gid'])
            if use['gid'] in last:
                gaps.setdefault(name, []).append(use['ts'] - last[use['gid']])
            last[use['gid']] = use['ts']
            target = run.players.get(use.get('target')) if use.get('target') is not None else None
            if target is None:
                label = '自己/无目标' if use.get('target') in (None, record['player']['id']) else '非玩家目标'
            elif target.id == record['player']['id']:
                label = '自己'
            else:
                label = f'{target.role}·{target.spec_zh}'
            given.setdefault(name, Counter())[label] += 1
        for first, second in zip(uses, uses[1:]):
            if first['gid'] != second['gid'] and second['ts'] - first['ts'] <= 5000:
                pair = (abilities.get(str(first['gid']), {}).get('name', first['gid']), abilities.get(str(second['gid']), {}).get('name', second['gid']))
                chains[pair] += 1
    print(f'# {directory.name}：敌方技能施法者（{len(selected)} 场合计）\n')
    print('| 敌方技能 | 场次 | 次数 | 施法者 |\n|---|---|---|---|')
    for name, count in totals.most_common(args.top):
        who = '、'.join(f'{source}×{n}' for source, n in casters[name].most_common(3))
        print(f'| {name} | {len(runs_seen[name])}/{len(selected)} | {count} | {who} |')
    print(f'\n# 本职业 5 秒内连用（{len(selected)} 场合计，≥3 次）\n')
    print('| 先 | 后 | 次数 |\n|---|---|---|')
    for (first, second), count in chains.most_common():
        if count >= 3:
            print(f'| {first} | {second} | {count} |')
    print(f'\n# 本职业技能：最短施放间隔与给了谁（{len(selected)} 场合计）\n')
    print('最短间隔是同一玩家两次施放的最小间隔，≈ 含天赋减冷却后的实际冷却上限；只施放过一次的不列间隔。')
    print('目标列只区分职责和专精；近战/远程请按专精自己判断。\n')
    print('| 技能 | 次数 | 最短间隔 | 给了谁 |\n|---|---|---|---|')
    for name, counter in sorted(given.items(), key=lambda item: -sum(item[1].values())):
        gap = f"{min(gaps[name]) / 1000:.0f} 秒" if gaps.get(name) else '—'
        who = '、'.join(f'{label}×{n}' for label, n in counter.most_common(4))
        print(f'| {name} | {sum(counter.values())} | {gap} | {who} |')
    print('\n下一步：对要写的技能跑 `wcl spell <ID>` 查打谁、持续、类型、能否驱散。')


if __name__ == '__main__':
    main()
