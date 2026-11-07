"""离线测试夹具，不读取用户凭据或缓存。"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# wclr 的磁盘缓存默认在 ~/.cache/wcl-raider，且在导入 wclr.api 时就定下目录。
# 测试必须在导入前把它指向空的临时目录：否则用户本机缓存里恰好有的 Raider.IO/WCL 响应
# 会让本该联网的代码路径悄悄通过，缓存过期后才在别处失败（结果取决于机器和日期）。
_CACHE = tempfile.mkdtemp(prefix='wcl-raider-test-cache-')
os.environ['WCL_RAIDER_CACHE_DIR'] = _CACHE
atexit.register(shutil.rmtree, _CACHE, ignore_errors=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.claude/skills/mplus-review/scripts'))

from wclr import api
from wclr.context import Run

assert api.CACHE_DIR == Path(_CACHE), 'wclr.api 在 support 之前被导入，测试会读到用户缓存'


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
