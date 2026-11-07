from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

from guides import GUIDES
from talents import encode, selections

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[1]
sys.path.insert(0, str(ROOT / '.claude/skills/mplus-review/scripts'))

from wclr.wowhead import spells

CORE = [100, 355, 6544, 6552, 23920, 386164, 386208, 118038, 18499, 97462, 202168, 107570, 46968, 227847, 107574, 384110]
TALENTS = [23920, 118038, 386208, 1271925, 444776, 103827, 202163, 1280961, 382549, 444770, 1271926]


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepare():
    source = DIRECTORY / 'sources'
    trees = json.loads((ROOT / 'archives/rogue-dungeon-guides/sources/dl/talents.json').read_text())
    tree = next(tree for tree in trees if tree['specId'] == 71)
    save(source / 'arms-tree.json', tree)
    base = (ROOT / 'archives/rogue-dungeon-guides/sources/rogue.src.html').read_text()
    style = re.search(r'<style>(.*?)</style>', base, re.S).group(1)
    (source / 'design.css').write_text(re.sub(r'/\*.*?\*/', '', style, flags=re.S).strip() + '\n', encoding='utf-8')
    identifiers = set(CORE + TALENTS)
    for name, guide in GUIDES.items():
        directory = source / name
        rows = json.loads((directory / 'selected.json').read_text())
        records = [json.loads((directory / row['file']).read_text()) for row in rows]
        names = {}
        occurrences = Counter()
        for record in records:
            occurrences.update(event.get('abilityGameID') for event in record['enemy_casts'])
            occurrences.update(aura['gid'] for aura in record['auras'])
            for spell_id, ability in record['abilities'].items():
                names.setdefault(ability['name'], set()).add(int(spell_id))
        wanted = {row['mechanic'] for stop in guide['route'] for row in stop['rows']} | {debuff[0] for debuff in guide['debuffs']}
        missing = wanted - names.keys()
        if missing:
            raise ValueError(f'{name}: Unknown mechanics {sorted(missing)}')
        mapping = {name: sorted(names[name], key=lambda spell_id: (-occurrences[spell_id], spell_id)) for name in sorted(wanted)}
        save(directory / 'mechanics.json', mapping)
        identifiers.update(spell_id for values in mapping.values() for spell_id in values)
        talent_strings = []
        for record in records:
            selected = selections(record['combatant'])
            talent_strings.append({'player': record['player']['name'], 'url': record['url'], 'string': encode(tree, selected), 'selected': selected})
        save(directory / 'talents.json', talent_strings)
    tooltips = spells(sorted(identifiers), lang='zh')
    missing = identifiers - tooltips.keys()
    if missing or any(not value.get('name') for value in tooltips.values()):
        raise ValueError(f'Missing spell tooltips: {missing}')
    for directory in (source / name for name in GUIDES):
        for name, values in json.loads((directory / 'mechanics.json').read_text()).items():
            if not any(tooltips[spell_id].get('description') for spell_id in values):
                raise ValueError(f'Missing mechanic description: {directory.name}: {name}')
    save(source / 'spells.json', tooltips)

    def download(icon):
        path = source / 'icons' / f'{icon}.jpg'
        if path.exists():
            return
        request = Request(f'https://wow.zamimg.com/images/wow/icons/large/{icon}.jpg', headers={'User-Agent': 'wcl-raider-guides/1.0'})
        with urlopen(request, timeout=30) as response:
            content = response.read()
        if not content.startswith(b'\xff\xd8'):
            raise ValueError(f'Invalid JPEG: {icon}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    icons = {tooltip['icon'] for tooltip in tooltips.values() if tooltip.get('icon')}
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(download, sorted(icons)))
    print(f'{len(tooltips)} verified spell tooltips; {len(icons)} embedded icons; 24 talent strings round-tripped.')


if __name__ == '__main__':
    prepare()
