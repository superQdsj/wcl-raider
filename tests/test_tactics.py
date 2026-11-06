"""tactics（应对技巧）分析的语义回归；合成数据，禁止网络。"""
import unittest
from unittest.mock import patch

from support import make_run
from wclr import catalog, cmd_tactics as T, wowhead

NPC = 10


def setUpModule():
    global network
    network = patch('urllib.request.urlopen', side_effect=AssertionError('离线测试禁止网络'))
    network.start()


def tearDownModule():
    network.stop()


def cast(ts, src, gid, tgt=-1):
    return dict(timestamp=ts, type='cast', sourceID=src, targetID=tgt, abilityGameID=gid)


def ecast(ts, gid, kind='begincast', tgt=-1):
    return dict(timestamp=ts, type=kind, sourceID=NPC, sourceInstance=1, targetID=tgt, abilityGameID=gid)


def aura(gid, tgt, start, end, inst=1):
    base = dict(sourceID=NPC, sourceInstance=inst, targetID=tgt, abilityGameID=gid)
    return [dict(base, timestamp=start, type='applydebuff'), dict(base, timestamp=end, type='removedebuff')]


def dmg(ts, tgt, gid, amount=1000, hit=1, hp=50000, maxhp=100000):
    return dict(timestamp=ts, type='damage', sourceID=NPC, targetID=tgt, abilityGameID=gid, amount=amount,
                hitType=hit, hitPoints=hp, maxHitPoints=maxhp, resourceActor=2)


def base_events():
    """战斗 100s–200s（报告相对毫秒 100000–200000）。玩家：1 坦克圣骑 2 牧师 3 猎人 4 法师 5 术士。"""
    debuffs, casts, dispels, taken, ecasts = [], [], [], [], []
    # 1) 牧师给法师驱散 9001（WCL 驱散事件）
    debuffs += aura(9001, 4, 110000, 112000)
    casts.append(cast(112000, 2, 527, tgt=4))
    dispels.append(dict(timestamp=112000, type='dispel', sourceID=2, targetID=4, abilityGameID=527,
                        extraAbilityGameID=9001))
    # 2) 9002 正常持续 10 秒；猎人假死后 20ms 消失
    for i, tgt in enumerate((1, 2, 4, 5)):
        debuffs += aura(9002, tgt, 120000 + i * 1000, 130000 + i * 1000, inst=i + 2)
    debuffs += aura(9002, 3, 140000, 143020, inst=9)
    casts.append(cast(143000, 3, 5384))
    # 3) 法师寒冰屏障后免疫 9003
    casts.append(cast(150000, 4, 45438))
    taken.append(dmg(152000, 4, 9003, amount=0, hit=10))
    # 4) 术士四次在敌方读条 9004 后 1 秒开不灭决心
    for t in (105000, 135000, 165000, 195000):
        ecasts.append(ecast(t, 9004))
        casts.append(cast(t + 1000, 5, 104773))
    # 5) 打断不展开；高频输出技能不选
    casts.append(cast(170000, 3, 147362))
    for t in range(100000, 200000, 1500):
        casts.append(cast(t, 4, 7777))
    # 6) 连用：圣骑士两次 牺牲祝福 → 圣盾术
    for t in (115000, 175000):
        casts.append(cast(t, 1, 6940, tgt=2))
        casts.append(cast(t + 2000, 1, 642))
    dd = {'entries': [{'id': 4, 'total': 1000, 'abilities': [{'guid': 7777, 'total': 900}]}]}
    return dict(casts=casts, ecasts=ecasts, debuffs=debuffs, dispels=dispels, taken=taken, dd=dd, heal={},
                deaths={})


class TacticsAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.run = make_run(startTime=100000, endTime=200000)
        self.res = T.analyze(self.run, base_events())

    def uses(self, pid, gid):
        return [u for u in self.res.uses if u.player == pid and u.gid == gid]

    def test_extra_selection(self):
        self.assertIn((2, 527), self.res.extra)
        self.assertIn((5, 104773), self.res.extra)
        self.assertNotIn((4, 7777), self.res.extra, '高频且占伤害大头的技能不是额外技能')
        self.assertNotIn((3, 147362), self.res.extra, '打断另有命令')
        self.assertEqual(self.res.skipped[3], [(147362, 1)])

    def test_dispel_event_attributed_to_cast(self):
        u = self.uses(2, 527)[0]
        self.assertEqual(u.subject, 4)
        self.assertEqual(u.removed, [(9001, 4, False)])
        a = next(a for a in self.res.auras if a.gid == 9001)
        self.assertEqual((a.reason, a.by), ('驱散', (2, 527)))

    def test_inferred_self_cleanse(self):
        self.assertEqual(self.res.full_dur[9002], 10000)
        u = self.uses(3, 5384)[0]
        self.assertEqual(u.removed, [(9002, 3, True)])
        self.assertIn(9002, u.active)
        a = next(a for a in self.res.auras if a.gid == 9002 and a.target == 3)
        self.assertEqual((a.reason, a.by, a.inferred), ('提前消失', (3, 5384), True))

    def test_immunity_attribution(self):
        u = self.uses(4, 45438)[0]
        self.assertEqual(dict(u.blocked), {(10, 9003): 1})
        self.assertFalse(self.res.blocks_unattributed)

    def test_association_with_enemy_cast(self):
        rows = self.res.assoc[(5, 104773)]
        self.assertTrue(rows)
        top = rows[0]
        self.assertEqual(top['name'], self.run.ab(9004))
        self.assertEqual((top['n'], top['of']), (4, 4))
        self.assertEqual(top['chans'].get('前读条'), 4)
        self.assertGreaterEqual(top['lift'], T.MIN_LIFT)
        self.assertLessEqual(top['p'], T.MAX_P)

    def test_class_focus_and_digest(self):
        out = T.render(self.run, self.res, cls=('Mage', None))
        self.assertIn('只看法师', out)
        self.assertIn('### Dps', out)
        self.assertNotIn('### 术士', out)
        digest = T.class_digest([(self.run, self.res)], 'Mage')
        self.assertIn('## 七、职业汇总：法师（1 场）', digest)
        self.assertIn('45438', digest)
        self.assertIn('预开免疫1', digest)
        self.assertIn('驱散', digest)  # 法师身上的 9001 被牧师驱散
        self.assertIn('牧师·', digest)
        none = T.render(self.run, self.res, cls=('Druid', None))
        self.assertIn('本场没有德鲁伊', none)

    def test_timing_of(self):
        self.assertEqual(T.timing_of(self.uses(2, 527)[0]), '上身后解')
        self.assertEqual(T.timing_of(self.uses(4, 45438)[0]), '预开免疫')

    def test_combo(self):
        self.assertIn((6940, 642, 2, 2000, 0), self.res.combos[1])

    def test_combo_counts_both_orders(self):
        ev = base_events()
        ev['casts'].append(cast(185000, 1, 642))
        ev['casts'].append(cast(186000, 1, 6940, tgt=2))
        res = T.analyze(make_run(startTime=100000, endTime=200000), ev)
        self.assertIn((6940, 642, 3, 2000, 1), res.combos[1])

    def test_render_sections(self):
        out = T.render(self.run, self.res)
        for heading in ('## 一、敌方机制', '## 二、敌方减益', '## 三、每名玩家'):
            self.assertIn(heading, out)
        self.assertIn('驱散', out)
        self.assertIn('常连用', out)
        detail = T.render(self.run, self.res, ability='5384')
        self.assertIn('消失:', detail)


class CoincidenceFilterTests(unittest.TestCase):
    def test_single_unknown_removal_is_dropped(self):
        ev = base_events()
        # 9005 常规 10 秒；一次未分类技能后 0.1 秒提前消失——只出现一次，视为巧合
        for i, tgt in enumerate((1, 2, 3, 4)):
            ev['debuffs'] += aura(9005, tgt, 101000 + i * 500, 111000 + i * 500, inst=20 + i)
        ev['debuffs'] += aura(9005, 5, 180000, 182100, inst=30)
        ev['casts'].append(cast(182000, 5, 8888))
        res = T.analyze(make_run(startTime=100000, endTime=200000), ev)
        u = next(u for u in res.uses if u.gid == 8888)
        self.assertEqual(u.removed, [])
        a = next(a for a in res.auras if a.gid == 9005 and a.target == 5)
        self.assertEqual(a.reason, '提前消失')
        self.assertIsNone(a.by)


class AuraEndingTests(unittest.TestCase):
    def test_simultaneous_end_is_not_attributed(self):
        ev = base_events()
        for i, tgt in enumerate((1, 2, 3)):
            ev['debuffs'] += aura(9006, tgt, 101000, 111000, inst=40 + i)
        # 三人同一时刻提前失去 9006：机制自己结束，即使有人刚好开了技能也不归因
        for i, tgt in enumerate((1, 2, 4)):
            ev['debuffs'] += aura(9006, tgt, 150000, 153000 + i * 50, inst=50 + i)
        ev['casts'].append(cast(152950, 4, 31224))
        res = T.analyze(make_run(startTime=100000, endTime=200000), ev)
        late = [a for a in res.auras if a.gid == 9006 and a.start == 150000]
        self.assertEqual({a.reason for a in late}, {'同时结束'})
        self.assertEqual([u.removed for u in res.uses if u.gid == 31224], [[]])

    def test_full_duration_ignores_dispelled_and_uses_known(self):
        ev = base_events()
        res = T.analyze(make_run(startTime=100000, endTime=200000), ev, known_dur={9001: 14000})
        self.assertEqual(res.full_dur[9001], 14000)
        a = next(a for a in res.auras if a.gid == 9001)
        self.assertEqual(a.reason, '驱散')

    def test_encounter_applied_cast(self):
        ev = base_events()
        for t in (120000, 160000):
            for pid in (1, 2, 3, 4, 5):
                ev['casts'].append(cast(t + pid * 10, pid, 1287798))
        res = T.analyze(make_run(startTime=100000, endTime=200000), ev)
        self.assertEqual(res.extra[(3, 1287798)]['cat'], '副本效果')

    def test_parse_class(self):
        from wclr.fmt import parse_class
        self.assertEqual(parse_class('法师'), ('Mage', None))
        self.assertEqual(parse_class('冰法'), ('Mage', 'Frost'))
        self.assertEqual(parse_class('Frost Mage'), ('Mage', 'Frost'))
        self.assertEqual(parse_class('奶骑'), ('Paladin', 'Holy'))
        self.assertEqual(parse_class('鲜血DK'), ('DeathKnight', 'Blood'))
        self.assertEqual(parse_class('防战'), ('Warrior', 'Protection'))
        with self.assertRaises(ValueError):
            parse_class('路人')

    def test_team_ids(self):
        rosters = [{'a', 'b', 'c', 'd', 'e'}, {'a', 'b', 'c', 'x', 'y'}, {'p', 'q', 'r', 's', 't'},
                   {'x', 'y', 'q', 'r', 'z'}]
        # 第 4 场与第 2、3 场各只有 2 人相同，不并入任何一队
        self.assertEqual(T.team_ids(rosters), [0, 0, 1, 2])


class HelperTests(unittest.TestCase):
    def test_poisson_tail(self):
        self.assertEqual(T.poisson_tail(0, 1.0), 1.0)
        self.assertAlmostEqual(T.poisson_tail(1, 1.0), 1 - 2.718281828 ** -1, places=6)
        self.assertLess(T.poisson_tail(5, 0.5), 0.001)

    def test_catalog(self):
        self.assertEqual(catalog.category(4987), '驱散')
        self.assertEqual(catalog.category(1766), '打断')
        self.assertEqual(catalog.category(123, '浓缩银月城生命药水'), '消耗品')
        self.assertIsNone(catalog.category(123, '某技能'))

    def test_wowhead_parse_and_classify(self):
        payload = {
            'name': '麻痹射击',
            'tooltip': '<table><tr><td><b>麻痹射击</b></td></tr></table><table><tr><td><div class="q">'
                       '造成自然伤害，持续14秒。<br /><br />移动速度降低10%。</div></td></tr></table>',
            'buff': '<table><tr><td><table width="100%"><tr><td><b class="q">麻痹射击</b></td>'
                    '<th class="q"><b class="q">魔法</b></th></tr></table></td></tr></table>'
                    '<table><tr><td>移动速度降低10%。</td></tr></table>',
        }
        info = wowhead.parse_tooltip(payload)
        self.assertEqual(info['dispel'], '魔法')
        self.assertIn('持续14秒', info['description'])
        self.assertEqual(info['aura'], '移动速度降低10%。')
        self.assertIsNone(info['duration_ms'])
        self.assertEqual(wowhead.parse_duration('移动速度降低10%。持续14秒'), 14000)
        self.assertEqual(wowhead.parse_duration('20 seconds remaining'), 20000)
        self.assertEqual(wowhead.classify({'description': '提供魔法免疫，并移除所有有害法术效果'}), '免疫')
        self.assertEqual(wowhead.classify({'description': '使你受到的伤害降低30%'}), '减伤')
        self.assertEqual(wowhead.classify({'description': '造成100点物理伤害'}), '伤害')


if __name__ == '__main__':
    unittest.main()
