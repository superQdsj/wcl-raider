"""离线测试夹具，不读取用户凭据或缓存。"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.claude/skills/mplus-review/scripts'))

from wclr.context import Run


CODE = 'AbCdEf1234567890'


def make_run(**overrides):
    fight = dict(id=1, name='测试副本', encounterID=12993, difficulty=10,
                 keystoneLevel=5, keystoneAffixes=[], keystoneBonus=1, kill=True,
                 startTime=100000, endTime=200000, keystoneTime=90000)
    fight.update(overrides)
    actors = [dict(id=1, name='Tank', type='Player', subType='Paladin'),
              dict(id=2, name='Healer', type='Player', subType='Priest'),
              dict(id=3, name='猎人', type='Player', subType='Hunter'),
              dict(id=4, name='Dps', type='Player', subType='Mage'),
              dict(id=5, name='术士', type='Player', subType='Warlock'),
              dict(id=6, name='宠物', type='Pet', petOwner=3)]
    meta = dict(code=CODE, region={'slug': 'US'}, startTime=0, endTime=0,
                masterData={'actors': actors, 'abilities': []}, fights=[fight])
    summary = {'playerDetails': {
        'tanks': [dict(id=1, name='Tank', type='Paladin', specs=['Protection'])],
        'healers': [dict(id=2, name='Healer', type='Priest', specs=['Holy'])],
        'dps': [dict(id=3, name='猎人', type='Hunter', specs=['BeastMastery']),
                dict(id=4, name='Dps', type='Mage', specs=['Arcane']),
                dict(id=5, name='术士', type='Warlock', specs=['Demonology'])]}}
    detail = {'fights': [{'friendlyPlayers': [1, 2, 3, 4, 5], 'dungeonPulls': []}],
              'summary': {'data': summary}}
    return Run(SimpleNamespace(lang='zh'), CODE, meta, fight, 86400, 'Test Dungeon', detail)
