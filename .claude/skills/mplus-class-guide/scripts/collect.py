"""一次采集一个副本：英雄天赋投票 → 三场同专精、同英雄天赋、不同玩家的最高层限时录像 → 写进 sources/guide.db。

用法：
  python3 collect.py <职业目录> <副本>                 # 自动选三场
  python3 collect.py <职业目录> <副本> --hero Slayer   # 指定英雄天赋
  python3 collect.py <职业目录> <副本> --runs URL URL URL  # 指定三场（跳过排名查询）

<职业目录> 可写 warrior-arms（指 guides/warrior-arms）。需要 WCL 凭据；先 `python3 <wcl.py> points` 看剩余点数。
同一副本重跑会整体替换该副本的旧数据。
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
import re

from guidelib import DUNGEONS, SEASON, connect, ensure_spells, hero_of, load_module, spec_dir, tree_for

from wclr.api import Client, RATE
from wclr.cmd_find import find_runs, resolve_dungeon
from wclr.cmd_tactics import analyze, fetch_events, location_of
from wclr.context import load_run
from wclr.wowhead import classify, spells

DETAILS = 'query($c:String,$f:[Int]){%s reportData{report(code:$c){playerDetails(fightIDs:$f,includeCombatantInfo:true)}}}' % RATE


def candidate(client, code, fight, profile, tree, who=None):
    """读一场：限时、有本专精玩家。返回 run/玩家/天赋/英雄天赋，不符合或读不到（私密报告）返回 None。"""
    try:
        run = load_run(client, code, str(fight))
    except Exception as error:  # 私密/已删除的报告：跳过，不要让整次采集失败
        print(f'跳过 {code}#{fight}：{error}', flush=True)
        return None
    players = [player for player in run.players.values() if player.cls == profile.CLASS and player.spec == profile.SPEC]
    if not run.kill or run.bonus < 1 or not players:
        return None
    player = next((player for player in players if player.name == who), players[0])
    details = client.gql(DETAILS, {'c': run.code, 'f': [run.fight_id]}, ttl=30 * 86400)
    groups = details['reportData']['report']['playerDetails']['data']['playerDetails']
    combatant = next((item for group in groups.values() if isinstance(group, list) for item in group if item.get('id') == player.id), None)
    hero = hero_of(combatant, tree) if combatant else None
    return {'run': run, 'player': player, 'combatant': combatant, 'hero': hero['name'] if hero else None,
            'hero_entry': hero['id'] if hero else None}


def label(run, actor_id, me):
    if actor_id is None or actor_id == -1:
        return None
    if actor_id == me:
        return '自己'
    player = run.players.get(actor_id)
    if player:
        return f'{ {"tank": "坦克", "healer": "治疗"}.get(player.role, "输出")}·{player.spec_zh}'
    actor = run.actors.get(actor_id) or {}
    return f"敌方·{actor.get('name', actor_id)}" if actor.get('type') == 'NPC' else None


def store(conn, dungeon, rank, item):
    """分析一场并写进库：本职业玩家的额外技能施放、伴随机制、敌方读条、身上的减益。"""
    run, player, combatant = item['run'], item['player'], item['combatant']
    events = fetch_events(run)
    debuffs = Counter(event.get('abilityGameID') for event in events['debuffs'] if event.get('type') == 'applydebuff')
    info = spells([spell for spell, _ in debuffs.most_common(40)], lang='zh')

    def categorize(identifiers):
        return {spell: category for spell, tooltip in spells(identifiers[:80], lang='zh').items() if (category := classify(tooltip))}

    result = analyze(run, events, classify=categorize,
                     known_dur={spell: tooltip['duration_ms'] for spell, tooltip in info.items() if tooltip.get('duration_ms')})
    key = f'{run.code}-{run.fight_id}'
    conn.execute('INSERT INTO run VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
        key, dungeon, rank, f'https://www.warcraftlogs.com/reports/{run.code}#fight={run.fight_id}', run.code, run.fight_id,
        run.level, run.duration, run.keystone_time, run.start, player.id, player.name, item['hero'],
        json.dumps(combatant, ensure_ascii=False), json.dumps([asdict(pull) for pull in run.pulls], ensure_ascii=False)))
    conn.executemany('INSERT INTO ability VALUES (?,?,?)',
                     [(key, int(spell_id), ability['name']) for spell_id, ability in run.abilities.items()])
    # 施放目标：分析只保留友方目标，敌方目标（晕了谁、断了谁）从原始施法事件补
    targets = {(event['timestamp'], int(event.get('abilityGameID') or 0)): event.get('targetID')
               for event in events['casts'] if event.get('sourceID') == player.id and event.get('type') == 'cast'}
    rows, spell_ids = [], set()
    for use in result.uses:
        if use.player != player.id:
            continue
        target = label(run, use.target if use.target is not None else targets.get((use.ts, use.gid)), player.id) or '自己'
        location = re.sub(r'^\W+\s*', '', location_of(run, use.ts)[0])
        rows.append((key, use.ts, run.t(use.ts), use.gid, target, use.hp, use.dmg_pct, location,
                     json.dumps(use.active), json.dumps(use.applied_after), json.dumps(dict(use.hits)),
                     json.dumps(use.before, ensure_ascii=False), json.dumps(use.after, ensure_ascii=False),
                     json.dumps(use.removed), json.dumps([[list(k), n] for k, n in use.blocked.items()]),
                     json.dumps(dict(use.after_hits))))
        spell_ids.add(use.gid)
    conn.executemany('INSERT INTO class_use VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    conn.executemany('INSERT INTO assoc VALUES (?,?,?,?,?,?,?,?)', [
        (key, gid, row['name'], row['n'], row['of'], row['lift'] if row['lift'] != float('inf') else 999, row['p'],
         json.dumps(row['chans'], ensure_ascii=False))
        for (pid, gid), lst in result.assoc.items() if pid == player.id for row in lst])
    enemy = []
    for event in events['ecasts']:
        actor = run.actors.get(event.get('sourceID'), {})
        if actor.get('type') != 'NPC' or actor.get('name') in (None, 'Environment'):
            continue
        enemy.append((key, event['timestamp'], int(event.get('abilityGameID') or 0), event.get('type'), actor['name'],
                      label(run, event.get('targetID'), player.id)))
    conn.executemany('INSERT INTO enemy_cast VALUES (?,?,?,?,?,?)', enemy)
    conn.executemany('INSERT INTO debuff VALUES (?,?,?,?,?,?,?)', [
        (key, aura.gid, aura.start, aura.end, aura.reason, aura.by[1] if aura.by else None, int(aura.inferred))
        for aura in result.auras if aura.target == player.id])
    # 敌方技能只补出现过 ≥2 次的，避免为零星技能消耗请求；构建时缺的会再补
    enemy_counts = Counter(row[2] for row in enemy) + Counter(aura.gid for aura in result.auras if aura.target == player.id)
    ensure_spells(conn, spell_ids | {spell for spell, count in enemy_counts.items() if count >= 2})
    return key


def collect(directory, dungeon, survey=20, hero_name=None, urls=None):
    profile = load_module(directory, 'profile')
    tree = tree_for(profile.SPEC_ID)
    client = Client()
    conn = connect(directory)
    if urls:
        refs = [re.search(r'reports/(\w+)#fight=(\d+)', url).groups() for url in urls]
        candidates = [item for code, fight in refs if (item := candidate(client, code, int(fight), profile, tree))]
        if len(candidates) != len(urls):
            raise SystemExit('指定的录像里有不符合的（未限时或没有本专精玩家）')
        hero_name = hero_name or Counter(item['hero'] for item in candidates).most_common(1)[0][0]
        pool, survey_rows = candidates, []
    else:
        encounter, _ = resolve_dungeon(client, SEASON['search_alias'].get(dungeon, dungeon))
        rankings, _ = find_runs(client, encounter, profile.CLASS, profile.SPEC, want=survey)
        candidates = [item for row in rankings
                      if (item := candidate(client, row['code'], row['fid'], profile, tree, row['who'][0][0] if row['who'] else None))]
        votes = Counter(item['hero'] for item in candidates if item['hero'])
        if not votes:
            raise SystemExit(f'{dungeon}：前 {len(rankings)} 场都读不到英雄天赋')
        hero_name = hero_name or votes.most_common(1)[0][0]
        print(dungeon, '英雄天赋', dict(votes), '→', hero_name, flush=True)
        # 同层按用时排序；三场来自不同场次、不同玩家
        pool = sorted((item for item in candidates if item['hero'] == hero_name),
                      key=lambda item: (-(item['run'].level or 0), item['run'].keystone_time or item['run'].duration))
        survey_rows = [(dungeon, f"https://www.warcraftlogs.com/reports/{item['run'].code}#fight={item['run'].fight_id}",
                        item['player'].name, item['run'].level, item['hero']) for item in candidates]
    entry = next((item['hero_entry'] for item in pool if item['hero'] == hero_name), None)
    if entry != getattr(profile, 'HERO_ENTRY', entry):
        print(f'⚠ 多数英雄天赋 {hero_name}（entry {entry}）与 profile.HERO_ENTRY 不一致：改 profile.py，否则构建会拒绝推荐配置。')
    chosen, players = [], set()
    for item in pool:
        if item['hero'] == hero_name and item['player'].name not in players:
            chosen.append(item)
            players.add(item['player'].name)
        if len(chosen) == 3:
            break
    if len(chosen) != 3:
        raise SystemExit(f'{dungeon}：只找到 {len(chosen)} 场 {hero_name} 的限时录像（不同玩家）')
    keys = [row[0] for row in conn.execute('SELECT key FROM run WHERE dungeon=?', (dungeon,))]
    for table in ('ability', 'class_use', 'assoc', 'enemy_cast', 'debuff'):
        conn.executemany(f'DELETE FROM {table} WHERE run=?', [(key,) for key in keys])
    conn.execute('DELETE FROM run WHERE dungeon=?', (dungeon,))
    conn.execute('DELETE FROM survey WHERE dungeon=?', (dungeon,))
    conn.executemany('INSERT INTO survey VALUES (?,?,?,?,?)', survey_rows)
    for rank, item in enumerate(chosen, 1):
        store(conn, dungeon, rank, item)
        print(dungeon, rank, item['player'].name, f"+{item['run'].level}", client.rate, flush=True)
    conn.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('spec')
    parser.add_argument('dungeon', choices=DUNGEONS)
    parser.add_argument('--survey', type=int, default=20, help='参与英雄天赋投票的前 N 个不同场次')
    parser.add_argument('--hero', help='指定英雄天赋英文名（如 Slayer）')
    parser.add_argument('--runs', nargs=3, metavar='URL', help='直接指定三场录像')
    args = parser.parse_args()
    collect(spec_dir(args.spec), args.dungeon, survey=args.survey, hero_name=args.hero, urls=args.runs)
