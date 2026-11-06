"""核心语义回归；合成数据，禁止网络。"""
import unittest
from unittest.mock import patch

from support import CODE, make_run
from wclr import data, fmt
from wclr.api import WCLError
from wclr.context import Pull, esc, parse_ref, select_fight
from wclr.cmd_damage import _flags, _match_abilities
from wclr.cmd_deaths import _clusters
from wclr.cmd_events import _ability_ids


def setUpModule():
    global network
    network = patch('urllib.request.urlopen', side_effect=AssertionError('离线测试禁止网络'))
    network.start()


def tearDownModule():
    network.stop()


class ReferenceTests(unittest.TestCase):
    def test_bare_and_anonymous_code(self):
        self.assertEqual(parse_ref(' <' + CODE + '> '), (CODE, None))
        self.assertEqual(parse_ref('a:' + CODE), ('a:' + CODE, None))

    def test_wcl_hosts_query_and_fragment(self):
        for host in ('www.warcraftlogs.com', 'cn.warcraftlogs.com', 'warcraftlogs.com'):
            with self.subTest(host=host):
                self.assertEqual(parse_ref(f'https://{host}/reports/{CODE}#fight=7'), (CODE, '7'))
                self.assertEqual(parse_ref(f'{host}/reports/{CODE}?fight=last'), (CODE, 'last'))

    def test_fragment_overrides_query(self):
        self.assertEqual(parse_ref(f'https://www.warcraftlogs.com/reports/{CODE}?fight=3#fight=5'), (CODE, '5'))

    def test_wowanalyzer(self):
        for suffix in ('/37-Synorc/summary', '/37', '?fight=37', '#fight=37'):
            self.assertEqual(parse_ref(f'https://wowanalyzer.com/report/{CODE}' + suffix), (CODE, '37'))

    def test_classic_explanation(self):
        for prefix in ('classic', 'sod', 'mop', 'fresh'):
            with self.assertRaisesRegex(WCLError, '经典.*没有大秘境'):
                parse_ref(f'https://{prefix}.warcraftlogs.com/reports/{CODE}')

    def test_invalid_or_foreign_ref(self):
        for ref in ('', 'short', f'https://example.com/reports/{CODE}',
                    f'https://www.warcraftlogs.com/reports/{CODE}EXTRA', 'https://[broken'):
            with self.subTest(ref=ref), self.assertRaises(WCLError):
                parse_ref(ref)

    def test_filter_name_escaping(self):
        self.assertEqual(esc('法"师\\名'), '法\\"师\\\\名')


class FormatTests(unittest.TestCase):
    def test_number_units_and_missing(self):
        for value, expected in [(None, '—'), (0, '0'), (999, '999'), (1234, '1.23K'),
                                (-1234, '-1.23K'), (12345678, '12.3M'), (1000000000, '1.00B')]:
            with self.subTest(value=value):
                self.assertEqual(fmt.num(value), expected)

    def test_clock_boundaries(self):
        self.assertEqual(fmt.clock(None), '—')
        self.assertEqual(fmt.clock(59999), '0:59')
        self.assertEqual(fmt.clock(59999, True), '1:00.0')
        self.assertEqual(fmt.clock(-1234, True), '-0:01.2')
        self.assertEqual(fmt.clock(3661000), '61:01')

    def test_parse_clock(self):
        for text, value in [('12:34', 754000), ('12:34.5', 754500), ('754.5s', 754500),
                            ('1:02:03', 3723000), ('-1:02', -62000), (' 0 ', 0)]:
            self.assertEqual(fmt.parse_clock(text), value)

    def test_invalid_times(self):
        for text in ('bad', '', '1:60', 'NaN', 'inf', '--1', '1:-2', '1.5:02', '1e309', '1:2:3:4'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                fmt.parse_clock(text)

    def test_percent_missing_zero_and_ratio(self):
        self.assertEqual(fmt.pct(None, 5), '—')
        self.assertEqual(fmt.pct(1, 0), '—')
        self.assertEqual(fmt.pct(0, 5), '0%')
        self.assertEqual(fmt.pct(1, 3, 1), '33.3%')
        self.assertEqual(fmt.pct(23.5, digits=1), '23.5%')

    def test_markdown_cells_and_output_budget(self):
        self.assertEqual(fmt.cell('a|b\nc'), 'a\\|b c')
        text = '\n'.join('x' * 90 for _ in range(100))
        out = fmt.limit_output(text)
        self.assertLessEqual(len(out), 6000)
        self.assertIn('已截断', out)
        self.assertEqual(fmt.limit_output('small'), 'small')


class RunTests(unittest.TestCase):
    def test_low_key_zero_penalty_real_observation(self):
        # +2 红玉：6 次死亡；官方与实际净时长只差 1.698 秒。
        r = make_run(startTime=0, endTime=873220, keystoneTime=864918, keystoneLevel=2)
        self.assertEqual(r.death_penalty(6)[0], 0)
        self.assertIn('反推', r.death_penalty(6)[1])

    def test_single_death_zero_penalty(self):
        r = make_run(startTime=0, endTime=953695, keystoneTime=945728, keystoneLevel=2)
        self.assertEqual(r.death_penalty(1)[0], 0)

    def test_standard_and_heavy_penalty(self):
        self.assertEqual(make_run(keystoneTime=100000).death_penalty(2)[0], 5000)
        self.assertEqual(make_run(keystoneTime=135000).death_penalty(3)[0], 15000)

    def test_affix_and_level_fallback(self):
        # 无法反推时按午夜 S2 实测规则：+2–+5（165 号词缀）0 秒；+6–+11 5 秒；147/152 词缀 15 秒
        for affix in (147, 152):
            self.assertEqual(make_run(keystoneTime=None, keystoneAffixes=[affix]).death_penalty(0)[0], 15000)
        for level in (2, 5):
            r = make_run(keystoneTime=None, keystoneLevel=level)
            self.assertEqual(r.death_penalty(2)[0], 0)
            self.assertIn('推断', r.death_penalty(2)[1])
        self.assertEqual(make_run(keystoneTime=None, keystoneLevel=9, keystoneAffixes=[165]).death_penalty(1)[0], 0)
        for level in (6, 11):
            r = make_run(keystoneTime=None, keystoneLevel=level)
            self.assertEqual(r.death_penalty(2)[0], 5000)
            self.assertIn('推断', r.death_penalty(2)[1])

    def test_incomplete_or_implausible_time_not_inferred(self):
        self.assertNotIn('反推', make_run(kill=False, keystoneTime=90000).death_penalty(1)[1])
        self.assertNotIn('反推', make_run(keystoneTime=1000).death_penalty(1)[1])

    def test_summary_death_time_is_fight_relative(self):
        r = make_run()
        r.summary['deathEvents'] = [dict(id=3, deathTime=5000), dict(id=6, deathTime=1000)]
        self.assertEqual(len(r.player_deaths()), 1)
        self.assertEqual(r.t(r.start + r.player_deaths()[0]['deathTime']), '0:05')

    def test_pet_ownership(self):
        r = make_run()
        self.assertEqual(r.owner(6), 3)
        self.assertEqual(r.players[3].pets, [6])
        self.assertIsNone(r.owner(999))
        self.assertIn('猎人', r.actor_name(6))

    def test_fallback_player_role_is_unknown(self):
        r = make_run()
        r.actors[99] = dict(id=99, name='旁观者', type='Player', subType='Hunter')
        self.assertEqual(r._players([99])[99].role, 'unknown')

    def test_player_selection_unicode_and_ambiguity(self):
        r = make_run()
        r.players[3].name = 'Sìmply'
        self.assertEqual(r.find_player('SÌM').id, 3)
        self.assertEqual(r.find_player('治疗').id, 2)
        r.players[4].name = 'Sìmplytoo'
        with self.assertRaisesRegex(WCLError, '不唯一'):
            r.find_player('Sìmp')

    def test_pull_slack_does_not_steal_next_pull(self):
        r = make_run()
        r.pulls = [Pull(i, i, '测试', 0, a, b, True, [], 0, [])
                   for i, a, b in [(1, 100000, 110000), (2, 111000, 120000)]]
        self.assertEqual(r.pull_of(111100).idx, 2)
        self.assertEqual(r.pull_of(110100).idx, 1)
        self.assertIsNone(r.pull_of(130000))
        self.assertEqual(r.combat_ms(), 19000)

    def test_combat_union_not_double_counted(self):
        r = make_run()
        r.pulls = [Pull(i, i, '测试', 0, a, b, True, [], 0, [])
                   for i, a, b in [(1, 100000, 110000), (2, 105000, 115000)]]
        self.assertEqual(r.combat_ms(), 15000)

    def test_default_fight_and_last(self):
        base = dict(difficulty=10, keystoneLevel=5)
        a, b = dict(base, id=2, kill=True), dict(base, id=7, kill=False)
        raid = dict(id=9, name='Raid', difficulty=4, kill=True)
        meta = {'fights': [a, b, raid]}
        self.assertIs(select_fight(meta, None), a)
        self.assertIs(select_fight(meta, 'last'), b)
        self.assertIs(select_fight(meta, '7'), b)
        self.assertIs(select_fight({'fights': [b]}, None), b)
        for hint in ('9', '99', 'invalid'):
            with self.assertRaises(WCLError):
                select_fight(meta, hint)

    def test_non_mplus_report_errors(self):
        for hint in (None, 'last'):
            with self.assertRaisesRegex(WCLError, '没有大秘境'):
                select_fight({'fights': []}, hint)


class DataSemanticsTests(unittest.TestCase):
    def test_death_clusters_sorted_inclusive_and_chained(self):
        deaths = [dict(timestamp=t) for t in (40000, 0, 20000, 60001)]
        clusters = _clusters(deaths)
        self.assertEqual([[d['timestamp'] for d in g] for g in clusters], [[0, 20000, 40000], [60001]])
        self.assertEqual(_clusters([]), [])
        self.assertEqual(deaths[0]['timestamp'], 40000)

    def test_interrupt_entries_nested_flat_and_channel(self):
        a, b, c = {'spellsBegun': 0}, {'spellsInterrupted': 2}, {'spellsBegun': 4, 'spellChannelsInterrupted': 1}
        tbl = {'entries': [{'entries': [a, None, {'entries': [b]}]}, c]}
        self.assertEqual(data.interrupt_entries(tbl), [a, b, c])
        self.assertEqual(data.interrupt_entries({}), [])

    def test_window_rate_weighted_partial_bins(self):
        self.assertEqual(data.window_rate([100, 300], 1000, 1000, 1500, 2500), 200)
        self.assertEqual(data.window_rate([0, 0], 1000, 1000, 1000, 3000), 0)

    def test_window_rate_missing_coverage_is_not_zero(self):
        for args in [([], 0, 1000, 0, 1), ([1], 0, 0, 0, 1),
                     ([1], 0, 1000, 1, 1), ([1], 0, 1000, 2000, 3000),
                     ([1], 0, 1000, -500, 500)]:
            self.assertIsNone(data.window_rate(*args))

    def test_tank_dominance_is_not_exclusive(self):
        r = make_run()
        self.assertEqual(_flags(r, 100, [(1, 95, 1), (2, 5, 1)]), '坦克占95%')
        self.assertEqual(_flags(r, 100, [(1, 100, 1)]), '仅坦克')
        self.assertEqual(_flags(r, 0, []), '')

    def test_even_distribution_requires_everyone(self):
        r = make_run()
        self.assertNotIn('全员', _flags(r, 100, [(i, 25, 1) for i in range(1, 5)]))
        self.assertIn('全员承伤接近', _flags(r, 100, [(i, 20, 1) for i in range(1, 6)]))
        self.assertIn('只打中:Dps', _flags(r, 100, [(4, 100, 1)]))
        self.assertIn('集中:Dps80%', _flags(r, 100, [(1, 10, 1), (2, 5, 1), (3, 5, 1), (4, 80, 2), (5, 0, 0)]))

    def test_same_name_multiple_ability_ids(self):
        r = make_run()
        r.abilities = {10: {'name': '同名'}, 11: {'name': '同名'}}
        self.assertEqual(_match_abilities(r, '同名'), [10, 11])
        self.assertEqual(_ability_ids(r, '同名'), [10, 11])
        self.assertEqual(_match_abilities(r, '123'), [123])
        r.abilities = {i: {'name': '同名'} for i in range(31)}
        for fn in (_match_abilities, _ability_ids):
            with self.assertRaisesRegex(WCLError, '指定技能 ID'):
                fn(r, '同名')


if __name__ == '__main__':
    unittest.main()
