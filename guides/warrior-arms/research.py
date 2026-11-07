from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.claude/skills/mplus-review/scripts'))

from wclr.api import Client, RATE
from wclr.cmd_find import find_runs, resolve_dungeon
from wclr.cmd_tactics import analyze, class_digest, fetch_events, render
from wclr.context import load_run
from wclr.wowhead import classify, spells

SOURCE = Path(__file__).resolve().parent / 'sources'
DUNGEONS = ['毒牙祭坛', '夺目谷', '红玉新生法池', '密谋小径', '纳洛拉克的洞穴', '塞塔里斯神庙', '虚空之痕竞技场', '诸王之眠']


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def research(name):
    client = Client()
    directory = SOURCE / name
    encounter, _ = resolve_dungeon(client, '红玉新生' if name == '红玉新生法池' else name)
    rankings, _ = find_runs(client, encounter, 'Warrior', 'Arms', want=8)
    save(directory / 'rankings.json', rankings)
    results = []
    for row in rankings:
        run = load_run(client, row['code'], str(row['fid']))
        warriors = [player for player in run.players.values() if player.cls == 'Warrior' and player.spec == 'Arms']
        if not run.kill or run.bonus < 1 or not warriors:
            continue
        player = next((player for player in warriors if player.name == row['who'][0][0]), warriors[0])
        query = 'query($c:String,$f:[Int]){%s reportData{report(code:$c){playerDetails(fightIDs:$f,includeCombatantInfo:true)}}}' % RATE
        details = client.gql(query, {'c': run.code, 'f': [run.fight_id]}, ttl=30 * 86400)
        groups = details['reportData']['report']['playerDetails']['data']['playerDetails']
        combatant = next(item for group in groups.values() if isinstance(group, list) for item in group if item.get('id') == player.id)
        if not isinstance(combatant.get('combatantInfo'), dict) or not combatant['combatantInfo'].get('talentTree'):
            continue
        events = fetch_events(run)
        debuffs = Counter(event.get('abilityGameID') for event in events['debuffs'] if event.get('type') == 'applydebuff')
        info = spells([spell for spell, _ in debuffs.most_common(40)], lang='zh')

        def categorize(identifiers):
            return {spell: category for spell, tooltip in spells(identifiers[:80], lang='zh').items() if (category := classify(tooltip))}

        result = analyze(run, events, classify=categorize, known_dur={spell: tooltip['duration_ms'] for spell, tooltip in info.items() if tooltip.get('duration_ms')})
        markdown = render(run, result, cls=('Warrior', 'Arms'), detail=100) + '\n' + class_digest([(run, result)], 'Warrior', 'Arms')
        stem = f'{run.code}-{run.fight_id}'
        (directory / f'{stem}.md').write_text(markdown, encoding='utf-8')
        uses = []
        for use in result.uses:
            if use.player == player.id:
                value = asdict(use)
                value['hits'] = dict(use.hits)
                value['after_hits'] = dict(use.after_hits)
                value['blocked'] = [[list(key), count] for key, count in use.blocked.items()]
                value['time'] = run.t(use.ts)
                uses.append(value)
        record = {
            'url': f'https://www.warcraftlogs.com/reports/{run.code}#fight={run.fight_id}',
            'code': run.code, 'fight': run.fight_id, 'level': run.level,
            'duration_ms': run.duration, 'keystone_ms': run.keystone_time,
            'start': run.start, 'report_start': run.report.get('startTime'),
            'player': asdict(player), 'combatant': combatant,
            'pulls': [asdict(pull) for pull in run.pulls], 'uses': uses,
            'abilities': run.abilities, 'tooltips': info,
            'auras': [asdict(aura) for aura in result.auras if aura.target == player.id],
            'reflection_hits': [event for event in events['taken'] if event.get('targetID') == player.id and event.get('hitType') == 9],
            'enemy_casts': events['ecasts'],
        }
        save(directory / f'{stem}.json', record)
        results.append({'file': f'{stem}.json', 'player': player.name, 'level': run.level, 'url': record['url']})
        print(name, len(results), player.name, f'+{run.level}', client.rate, flush=True)
        if len(results) == 3:
            break
    if len(results) != 3:
        raise RuntimeError(f'{name}: only {len(results)} timed Arms runs')
    save(directory / 'selected.json', results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dungeons', nargs='*', choices=DUNGEONS)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(research, args.dungeons or DUNGEONS))
