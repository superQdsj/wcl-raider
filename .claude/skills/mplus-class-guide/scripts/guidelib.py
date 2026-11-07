"""职业手册共用的小工具：仓库路径、职业配置、SQLite 证据库、技能资料与图标缓存。

每个职业目录 guides/<职业-专精>/ 只放三样自己的东西：profile.py（职业常量）、guides.py（逐本内容）、
sources/guide.db（三场录像的证据、技能说明、图标）。其余全部在本 skill 里。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from urllib.request import Request, urlopen

SKILL = Path(__file__).resolve().parents[1]
ASSETS = SKILL / 'assets'


def _root():
    for parent in [*Path(__file__).resolve().parents, *Path.cwd().resolve().parents, Path.cwd().resolve()]:
        if (parent / '.claude/skills/mplus-review/scripts/wclr').is_dir():
            return parent
    raise RuntimeError('找不到仓库根目录（需要 .claude/skills/mplus-review/scripts/wclr）')


ROOT = _root()
# wclr 只当数据库用：WCL 接口、缓存、点数限额、Wowhead 说明。不要读 mplus-review / mplus-tactics 的说明文档。
sys.path.insert(0, str(ROOT / '.claude/skills/mplus-review/scripts'))

SEASON = json.loads((ASSETS / 'season.json').read_text(encoding='utf-8'))
DUNGEONS = SEASON['dungeons']
TREE_GROUPS = ('classNodes', 'specNodes', 'heroNodes', 'subTreeNodes')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS run(          -- 每个副本三场：本专精玩家的一场限时录像
  key TEXT PRIMARY KEY, dungeon TEXT, rank INTEGER, url TEXT, code TEXT, fight INTEGER, level INTEGER,
  duration_ms REAL, keystone_ms REAL, start REAL, player_id INTEGER, player_name TEXT, hero TEXT,
  combatant TEXT, pulls TEXT);
CREATE TABLE IF NOT EXISTS survey(dungeon TEXT, url TEXT, player TEXT, level INTEGER, hero TEXT);
CREATE TABLE IF NOT EXISTS ability(run TEXT, id INTEGER, name TEXT, PRIMARY KEY(run, id));
CREATE TABLE IF NOT EXISTS class_use(    -- 本职业玩家常规循环之外的每次施放
  run TEXT, ts REAL, clock TEXT, spell INTEGER, target TEXT, hp REAL, dmg_pct REAL, location TEXT,
  active TEXT, applied_after TEXT, hits TEXT, before TEXT, after TEXT, removed TEXT, blocked TEXT, after_hits TEXT);
CREATE TABLE IF NOT EXISTS assoc(        -- 某技能反复伴随的敌方机制；lift = 实际 ÷ 随机时刻的期望
  run TEXT, spell INTEGER, mechanic TEXT, n INTEGER, of INTEGER, lift REAL, p REAL, chans TEXT);
CREATE TABLE IF NOT EXISTS enemy_cast(run TEXT, ts REAL, spell INTEGER, type TEXT, source TEXT, target TEXT);
CREATE TABLE IF NOT EXISTS debuff(       -- 本职业玩家身上的敌方减益，以及怎么结束的
  run TEXT, spell INTEGER, start REAL, "end" REAL, reason TEXT, by_spell INTEGER, inferred INTEGER);
CREATE TABLE IF NOT EXISTS spell(
  id INTEGER PRIMARY KEY, name TEXT, dispel TEXT, description TEXT, aura TEXT, duration_ms REAL,
  cooldown_ms REAL, charges INTEGER, cooldown_mods TEXT, icon TEXT);
CREATE TABLE IF NOT EXISTS icon(name TEXT PRIMARY KEY, jpg BLOB);
'''


def spec_dir(path):
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = ROOT / 'guides' / path
    path = path.resolve()
    if not (path / 'profile.py').exists():
        raise SystemExit(f'{path} 里没有 profile.py：先按 SKILL.md「新职业」建好职业目录')
    return path


def load_module(directory, name):
    spec = importlib.util.spec_from_file_location(f'{directory.name}_{name}', directory / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # guides.py 里 from guidelib import row, stop
    spec.loader.exec_module(module)
    return module


def connect(directory):
    path = directory / 'sources' / 'guide.db'
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def tree_for(spec_id):
    trees = json.loads((ASSETS / 'talent-trees.json').read_text(encoding='utf-8'))
    return next(tree for tree in trees if tree['specId'] == spec_id)


def hero_of(combatant, tree):
    """这名玩家选的英雄天赋 entry（含 id/name）；combatantInfo 读不到时返回 None。"""
    info = combatant.get('combatantInfo') if isinstance(combatant, dict) else None
    if not isinstance(info, dict) or not info.get('talentTree'):
        return None
    chosen = {talent.get('id') for talent in info['talentTree']}
    for node in tree['subTreeNodes']:
        for entry in node['entries']:
            if entry.get('type') == 'subtree' and entry['id'] in chosen:
                return entry
    return None


def tree_spells(tree, entries=None, groups=TREE_GROUPS):
    return {entry.get('spellId') for group in groups for node in tree[group] for entry in node['entries']
            if entries is None or entry['id'] in entries}


# ---------------------------------------------------------------- 技能说明与图标

def ensure_spells(conn, identifiers):
    """把缺的技能说明（Wowhead 中文）和图标补进库里。都在库里时不联网。"""
    identifiers = {int(spell_id) for spell_id in identifiers if spell_id}
    have = {row[0] for row in conn.execute('SELECT id FROM spell')}
    missing = sorted(identifiers - have)
    if missing:
        from wclr.wowhead import spells
        found = spells(missing, lang='zh')
        lost = [spell_id for spell_id in missing if not (found.get(spell_id) or {}).get('name')]
        if lost:
            raise ValueError(f'Wowhead 查不到这些技能：{lost}')
        conn.executemany('INSERT OR REPLACE INTO spell VALUES (?,?,?,?,?,?,?,?,?,?)', [
            (spell_id, info['name'], info.get('dispel'), info.get('description'), info.get('aura'), info.get('duration_ms'),
             info.get('cooldown_ms'), info.get('charges'), json.dumps(info.get('cooldown_mods') or {}), info.get('icon'))
            for spell_id, info in found.items()])
    names = {row[0] for row in conn.execute('SELECT icon FROM spell WHERE icon IS NOT NULL')}
    names -= {row[0] for row in conn.execute('SELECT name FROM icon')}
    if names:
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(_download_icon, sorted(names)))
        conn.executemany('INSERT OR REPLACE INTO icon VALUES (?,?)', rows)
    conn.commit()


def _download_icon(name):
    from wclr.api import CACHE_DIR
    path = CACHE_DIR / 'icons' / f'{name}.jpg'
    if not path.exists():
        request = Request(f'https://wow.zamimg.com/images/wow/icons/large/{name}.jpg', headers={'User-Agent': 'wcl-raider-guides/1.0'})
        with urlopen(request, timeout=30) as response:
            content = response.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    content = path.read_bytes()
    if not content.startswith(b'\xff\xd8'):
        raise ValueError(f'图标不是 JPEG：{name}')
    return name, content


def spell_info(conn):
    out = {}
    for row in conn.execute('SELECT * FROM spell'):
        info = dict(row)
        info['cooldown_mods'] = {int(key): value for key, value in json.loads(info['cooldown_mods'] or '{}').items()}
        out[row['id']] = info
    return out


# ---------------------------------------------------------------- guides.py 的写法

def row(mechanic, signal, skills, why, action=None, tags=(), who=None, mechanic_id=None, card=None):
    """路线里的一行。mechanic_id：同名机制有小怪版/首领版时，显式指定链接与图标用哪个技能 ID。
    card：这一行进 02 先学这四招时，卡片上的说明（两句完整的话）；不给就用 why。"""
    return {'mechanic': mechanic, 'signal': signal, 'skills': skills, 'why': why, 'action': action, 'tags': list(tags),
            'who': who, 'mechanic_id': mechanic_id, 'card': card}


def stop(name, kind, rows, note=''):
    return {'name': name, 'kind': kind, 'rows': rows, 'note': note}
