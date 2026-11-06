"""首领战伤害去向（splits）与复活/免死分类（spells）的纯函数测试；合成数据，禁止网络。"""
import unittest
from unittest.mock import patch

import support  # noqa: F401  (设置 sys.path)
from wclr.cmd_splits import BossDamage, boss_damage_from_entries, boss_hint
from wclr.spells import res_kind


def setUpModule():
    global network
    network = patch('urllib.request.urlopen', side_effect=AssertionError('离线测试禁止网络'))
    network.start()


def tearDownModule():
    network.stop()


class BossDamageTests(unittest.TestCase):
    def test_boss_type_wins_over_name(self):
        entries = [dict(name='首领', type='Boss', total=100, sources=[dict(name='A', total=60), dict(name='B', total=40)]),
                   dict(name='小蛇', type='NPC', total=50)]
        bd = boss_damage_from_entries(entries, 10_000, ['小蛇'])
        self.assertEqual((bd.boss, bd.other_total, bd.players), (100, 50, {'A': 60, 'B': 40}))
        self.assertEqual(bd.boss_dps, 10)

    def test_name_fallback_and_no_body(self):
        bd = boss_damage_from_entries([dict(name='加瓦兹特', type='NPC', total=80)], 8_000, ['加瓦兹特'])
        self.assertEqual((bd.boss, bd.other_total), (80, 0))
        bd = boss_damage_from_entries([dict(name='小怪', type='NPC', total=80)], 8_000, ['化身'])
        self.assertEqual((bd.boss, bd.other_total), (0, 80))

    def test_hint_detects_kill_time_threshold(self):
        ours = BossDamage(dur=195_000, boss=89e6, other={'蛇': 124e6, '飞蛇': 84e6}, players={})
        refs = [BossDamage(133_000, 89e6, {'x': 160e6}, {}), BossDamage(137_000, 89e6, {'x': 144e6}, {}),
                BossDamage(198_000, 89e6, {'x': 207e6}, {})]
        hint = boss_hint(ours, refs)
        self.assertIn('击杀时间门槛', hint)
        self.assertIn('多打了一轮小怪', hint)
        self.assertIn('首领血量一样', hint)

    def test_hint_silent_when_close(self):
        ours = BossDamage(dur=180_000, boss=1e8, other={}, players={})
        self.assertEqual(boss_hint(ours, [BossDamage(175_000, 1e8, {}, {})]), '')


class SpellTests(unittest.TestCase):
    def test_res_kinds(self):
        self.assertEqual(res_kind(61999, 1, 2), '战复')
        self.assertEqual(res_kind(95750, 2, 2), '战复')      # 灵魂石：复活事件来源可能是自己
        self.assertEqual(res_kind(20608, 2, 2), '自我复活')
        self.assertEqual(res_kind(2006, 1, 2), '脱战复活')
        self.assertEqual(res_kind(999, 1, 2), '复活')


if __name__ == '__main__':
    unittest.main()
