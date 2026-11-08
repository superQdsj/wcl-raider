"""Rebuild the complete cast-context inventory from saved evidence; no network."""
import json
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
E = HERE / 'evidence'
FOCUS = {403876, 642, 1022, 6940, 633, 213644}
PHASES = {
    1: [(0,'approach'),(314.3,'boss1'),(414.8,'interlude'),(511.4,'boss2'),(699.9,'legion1'),(958.1,'boss3'),(1185.9,'legion2'),(1349.5,'golem'),(1434.1,'boss4')],
    2: [(0,'approach'),(295.8,'boss1'),(388.3,'interlude'),(477.7,'boss2'),(646.7,'legion1'),(938.9,'boss3'),(1152.2,'legion2'),(1410.5,'boss4')],
    3: [(0,'approach'),(285.1,'boss1'),(387.9,'interlude'),(486.6,'boss2'),(659.6,'legion1'),(974.2,'boss3'),(1217.5,'legion2'),(1517.8,'boss4')],
}

def clock(ms):
    s = ms / 1000
    return f'{int(s//60)}:{s%60:04.1f}'

def build():
    rows = []
    for i in (1, 2, 3):
        get = lambda key: json.loads((E / f'raw/run{i}_{key}.json').read_text())
        names, casts, taken, enemy, debuffs = (get(k) for k in ('names','casts','team_taken','enemy','debuffs'))
        start = names['fight_start']
        ab = lambda g: names['abilities'].get(str(g), str(g))
        heals = json.loads((E / f'scenarios/run{i}_all_lay_heals.json').read_text())['events']
        focus = [e for e in casts if e['type'] == 'cast' and e.get('abilityGameID') in FOCUS]
        for j, e in enumerate(focus, 1):
            t = e['timestamp']; pid = e['sourceID']; target = e.get('targetID')
            if target in (None, -1) or names['actors'].get(str(target)) == 'Environment':
                target = pid
            sec = (t-start)/1000
            phase = [p for at,p in PHASES[i] if at <= sec][-1]
            before, after = t-4000, t+8000
            observed = sorted({ab(x.get('abilityGameID')) for x in enemy if before <= x['timestamp'] <= after})
            dmg = Counter()
            for x in taken:
                if before <= x['timestamp'] <= after and x.get('targetID') == target:
                    dmg[ab(x.get('abilityGameID'))] += (x.get('amount') or 0) + (x.get('absorbed') or 0)
            on = {}
            for x in debuffs:
                if x['timestamp'] > t: break
                g = x.get('abilityGameID')
                if x['type'] in ('applydebuff','refreshdebuff','applydebuffstack'): on[g] = True
                if x['type'] == 'removedebuff': on.pop(g, None)
            removal = sorted({ab(x.get('abilityGameID')) for x in debuffs if x['type']=='removedebuff' and t-10 <= x['timestamp'] <= t+500})
            heal = [x for x in heals if x['type']=='heal' and abs(x['timestamp']-t)<100 and x.get('targetID')==target]
            rows.append(dict(id=f'{"ABC"[i-1]}{j:02}',run=i,time=clock(t-start),timestamp=t,spell_id=e['abilityGameID'],spell=ab(e['abilityGameID']),phase=phase,target='自己' if target==pid else '队友',enemy=observed,enemy_ids=sorted({x.get('abilityGameID') for x in enemy if before <= x['timestamp'] <= after and x.get('abilityGameID')}),damage=[{'name':k,'amount':v} for k,v in dmg.most_common()],self_debuffs=[ab(g) for g in on],self_removed=removal,healing=heal))
        assert len(focus) == len([x for x in rows if x['run']==i])
    (HERE/'cast-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    lines=['# 全部关注技能施法逐次核对','', '敌方施法和目标承伤窗口：施法前4秒至后8秒。减益列仅指惩戒本人；附近发生不等于因果。参考A/B/C对应 evidence/README.md 的 r1/r2/r3。','']
    for r in rows:
        lines += [f'## {r["id"]} · {r["time"]} · {r["spell"]} → {r["target"]} · {r["phase"]}',f'- 附近敌方技能：{"、".join(r["enemy"]) or "未记录"}',f'- 目标承伤：{"、".join(x["name"] for x in r["damage"]) or "未记录"}',f'- 本人减益：{"、".join(r["self_debuffs"]) or "无"}',f'- 本人附近移除：{"、".join(r["self_removed"]) or "无"}']
        for h in r['healing']: lines.append(f'- 圣疗有效治疗 {h.get("amount")}；过量 {h.get("overheal",0)}；事件血量 {h.get("hitPoints")}/{h.get("maxHitPoints")}')
    (HERE/'cast-audit.md').write_text('\n'.join(lines)+'\n')
    return rows

if __name__ == '__main__':
    rows=build()
    print(f'Inventoried {len(rows)} casts, by run: {dict(Counter(r["run"] for r in rows))}')
