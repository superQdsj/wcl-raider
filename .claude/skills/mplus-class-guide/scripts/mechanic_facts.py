"""列出一个副本三场录像里的机制事实：敌方技能由谁施放、该职业技能的连用。

用法：python3 mechanic_facts.py <archives/<职业>-dungeon-guides/sources/<副本>> [--top 40]

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
    print('\n下一步：对要写的技能跑 `wcl spell <ID>` 查打谁、持续、类型、能否驱散。')


if __name__ == '__main__':
    main()
