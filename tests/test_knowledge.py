"""首领战伤害去向（splits）与复活/免死分类（spells）的纯函数测试；合成数据，禁止网络。"""
import unittest
from unittest.mock import patch

import support  # noqa: F401  (设置 sys.path)
from wclr.cmd_splits import BossDamage, boss_damage_from_entries, boss_hint
from wclr.spells import res_kind
from wclr.cmd_ability import Profile, _strip, summarize


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


class AbilityProfileTests(unittest.TestCase):
    def profiles(self, our_kills=1, ref_kills=0, dispelled=0, interrupted=0):
        ours = Profile('本场', begins=7, interrupted=interrupted, debuffs=7, debuff_roles={'治疗': 7},
                       durations=[4.0] * 7, dispelled=dispelled, hits=35, hit_bursts=[1] * 7, kills=our_kills,
                       kill_names=['小妤'] * our_kills)
        refs = [Profile(f'参考{i}', begins=5, debuffs=5, debuff_roles={'治疗': 5}, durations=[4.0] * 5, hits=25,
                        hit_bursts=[1] * 5, kills=ref_kills) for i in range(3)]
        return [ours] + refs

    def test_healer_only_not_dispellable_not_interruptible(self):
        text = '\n'.join(summarize(self.profiles()))
        self.assertIn('只点治疗', text)
        self.assertIn('22/22', text)
        self.assertIn('0 次被打断', text)
        self.assertIn('0 次被驱散', text)
        self.assertIn('持续满时长', text)
        self.assertIn('参考吃了同样的技能却没人死', text)

    def test_dispellable_and_interruptible_when_seen(self):
        text = '\n'.join(summarize(self.profiles(dispelled=2, interrupted=3)))
        self.assertIn('可以驱散', text)
        self.assertIn('可以打断', text)

    def test_mixed_targets_not_called_fixed(self):
        p = Profile('本场', debuffs=6, debuff_roles={'治疗': 3, '输出': 3})
        self.assertIn('没有固定职责', '\n'.join(summarize([p])))

    def test_strip_wowhead_html(self):
        self.assertEqual(_strip('<div class="q">持续4秒<br />被移除时 &amp; 爆炸<!--x--></div>'), '持续4秒\n被移除时 & 爆炸')


if __name__ == '__main__':
    unittest.main()


class LintTests(unittest.TestCase):
    GOOD = """# 标题
## 一句话
超时 40 秒。
## 时间丢在哪里
1. **首领甲：多花 0:58。** 首领血量一样。
## 下一把怎么打
1. **开怪 2:20 内打死首领甲。** 复验：首领战 ≤ 2:20。
## 还没看清的
- 某技能能不能驱散未核实。
"""

    def test_good_report_passes_and_open_section_may_hedge(self):
        from wclr.cmd_lint import lint_text
        self.assertEqual(lint_text(self.GOOD), [])

    def test_flags_hedges_fillers_missing_check_and_offset_items(self):
        from wclr.cmd_lint import lint_text
        bad = self.GOOD.replace('首领血量一样。', '首领血量一样，不能断言是谁的问题。两波合计 2:27，比参考快 0:21。') \
                       .replace('复验：首领战 ≤ 2:20。', '注意减伤。')
        text = '\n'.join(lint_text(bad))
        self.assertIn('不能断言', text)
        self.assertIn('注意减伤', text)
        self.assertIn('没有写复验', text)
        self.assertIn('合起来并不慢', text)


class LintGamingTests(unittest.TestCase):
    def test_reworded_hedges_and_unverified_calls_are_caught(self):
        from wclr.cmd_lint import lint_text
        text = LintTests.GOOD.replace('首领血量一样。', '首领血量一样，能不能断尚待确认，2:45 不能全部当成可节省时间。') \
            .replace('复验：首领战 ≤ 2:20。', '执行前先跑 `wcl ability`。复验：首领战 ≤ 2:20。')
        out = '\n'.join(lint_text(text))
        self.assertIn('尚待', out)
        self.assertIn('不能全部当成', out)
        self.assertIn('还不是口令', out)

    def test_code_hash_fight_shorthand(self):
        from wclr.context import parse_ref
        self.assertEqual(parse_ref('Zb4gAkpMnQ8LPcd1#4'), ('Zb4gAkpMnQ8LPcd1', '4'))
