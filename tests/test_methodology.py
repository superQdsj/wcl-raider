"""方法论数据补全的离线测试；纯函数、查询范围与输出语义。"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from support import CODE, make_run
from wclr import data
from wclr.cli import build_parser, dispatch
from wclr.cmd_damage import _ability_detail, merge_damage_segments
from wclr.cmd_deaths import (
    _availability_data, _render_availability, _return_fields, cmd_deaths, first_return, spell_availability,
)
from wclr.api import WCLError
from wclr.cmd_events import cmd_events
from wclr.cmd_interrupts import (
    cmd_interrupts, enemy_cast_counts, estimate_capacity, inconsistent_counts, split_interrupts,
)
from wclr.cmd_overview import _timing_lines, cmd_overview
from wclr.cmd_player import cmd_player
from wclr.population import player_keys


def setUpModule():
    global network
    network = patch('urllib.request.urlopen', side_effect=AssertionError('离线测试禁止网络'))
    network.start()


def tearDownModule():
    network.stop()


def action(timestamp, **values):
    event = dict(type='cast', sourceID=3, targetID=3, abilityGameID=100, timestamp=timestamp)
    event.update(values)
    return event


class ReturnTests(unittest.TestCase):
    def setUp(self):
        self.death = dict(targetID=3, timestamp=100000)

    def test_earliest_cast_in_unsorted_events_and_self_buffs_ignored(self):
        # 自身增益（被动光环、复活时自动恢复的增益）不算回归，只认主动施法
        buff = action(112000, type='applybuff')
        self.assertEqual(first_return(self.death, [action(120000), buff, action(115000)])['timestamp'], 115000)
        cast = action(105000)
        self.assertIs(first_return(self.death, [buff, cast]), cast)
        self.assertIsNone(first_return(self.death, [buff]))

    def test_casts_within_one_second_after_death_are_ignored(self):
        self.assertIsNone(first_return(self.death, [action(100100), action(100999)]))
        self.assertEqual(first_return(self.death, [action(100100), action(101000)])['timestamp'], 101000)

    def test_excludes_passive_incoming_pet_fake_and_begin_cast(self):
        ignored = [action(101000, abilityGameID=1), action(102000, sourceID=6),
                   action(103000, type='applybuff', sourceID=2),
                   action(104000, type='applybuff', targetID=2),
                   action(105000, type='begincast'), action(106000, fake=True),
                   action(107000, type='damage')]
        self.assertIsNone(first_return(self.death, ignored))

    def test_strictly_after_death_and_inclusive_300_seconds(self):
        self.assertIsNone(first_return(self.death, [action(99999), action(100000), action(400001)]))
        self.assertEqual(first_return(self.death, [action(400000)])['timestamp'], 400000)
        self.assertIsNone(first_return(self.death, []))

    def test_batch_fields_have_one_alias_per_death_small_limit_and_names(self):
        run = make_run()
        run.players[3].name = 'A"\\B'
        fields = _return_fields(run, [dict(targetID=3, timestamp=101000), dict(targetID=3, timestamp=190000)])
        self.assertIn('r0: events', fields)
        self.assertIn('r1: events', fields)
        self.assertEqual(fields.count('limit: 3'), 2)
        self.assertIn('startTime: 102000', fields)
        self.assertIn('endTime: 200000', fields)
        self.assertIn('source.name', fields)
        self.assertIn('type = \\"cast\\"', fields)
        self.assertNotIn('target.id', fields)

    def test_death_at_fight_end_does_not_reverse_query_window(self):
        fields = _return_fields(make_run(), [dict(targetID=3, timestamp=200000)])
        self.assertIn('startTime: 200000, endTime: 200000', fields)


class AvailabilityTests(unittest.TestCase):
    def test_available_at_exact_shortest_interval(self):
        self.assertEqual(spell_availability([20000, 10000, 30000], 40000), (10000, 10000, '可用'))

    def test_shortest_interval_uses_whole_fight(self):
        self.assertEqual(spell_availability([10000, 40000, 50000], 15000), (5000, 10000, '可能在冷却'))

    def test_cast_in_same_millisecond_as_death_is_not_assumed_unused(self):
        self.assertEqual(spell_availability([10000, 20000], 20000), (0, 10000, '可能在冷却'))

    def test_once_and_never_used_before_death(self):
        self.assertEqual(spell_availability([10000], 20000), (10000, None, '无法判定'))
        self.assertEqual(spell_availability([30000], 20000), (None, None, '死前未用过（可用性未知）'))
        self.assertEqual(spell_availability([30000, 40000], 20000), (None, 10000, '死前未用过（可用性未知）'))
        self.assertEqual(spell_availability([], 20000), (None, None, '死前未用过（可用性未知）'))

    def test_candidate_filter_and_single_table_plus_event_query(self):
        run = make_run(endTime=220000)
        run.pulls = [SimpleNamespace(start=100000, end=220000)]
        entries = [dict(guid=1, total=2), dict(guid=1766, total=2), dict(guid=101, total=4),
                   dict(guid=102, total=3), dict(guid=103, total=1)]
        with patch('wclr.cmd_deaths.data.casts', return_value={'entries': entries}) as casts, \
                patch('wclr.cmd_deaths.fetch', return_value={'e': {'data': [action(110000, abilityGameID=102)]}}) as fetch:
            info = _availability_data(run, 3)
        casts.assert_called_once_with(run, 3)
        fetch.assert_called_once()
        self.assertEqual([entry['guid'] for entry in info['entries']], [102, 103])
        self.assertIn('ability.id in (102, 103)', fetch.call_args.args[1])
        self.assertIn('sourceID: 3', fetch.call_args.args[1])

    def test_at_most_twelve_candidates(self):
        run = make_run(endTime=220000)
        run.pulls = [SimpleNamespace(start=100000, end=220000)]
        entries = [dict(guid=100 + index, total=2) for index in range(14)]
        with patch('wclr.cmd_deaths.data.casts', return_value={'entries': entries}), \
                patch('wclr.cmd_deaths.fetch', return_value={'e': {'data': []}}):
            self.assertEqual(len(_availability_data(run, 3)['entries']), 12)

    def test_no_candidates_no_second_query(self):
        with patch('wclr.cmd_deaths.data.casts', return_value={}), patch('wclr.cmd_deaths.fetch') as fetch:
            self.assertEqual(_availability_data(make_run(), 3)['events'], [])
        fetch.assert_not_called()

    def test_incomplete_events_do_not_assert_availability(self):
        death = dict(targetID=3, timestamp=140000)
        info = dict(entries=[dict(guid=100, total=3)], events=[action(105000), action(125000)], truncated=False)
        output = '\n'.join(_render_availability(make_run(), death, info))
        self.assertIn('数据不全（无法判定）', output)
        info['entries'][0]['total'] = 2
        info['truncated'] = True
        self.assertIn('数据不全（无法判定）', '\n'.join(_render_availability(make_run(), death, info)))


class DamageSegmentTests(unittest.TestCase):
    def test_inclusive_gap_chained_merge_and_sorted_output(self):
        events = [action(timestamp, type='damage', amount=10) for timestamp in [8001, 5500, 1000, 3000]]
        segments = merge_damage_segments(events)[3]
        self.assertEqual([(item['start'], item['end']) for item in segments], [(1000, 5500), (8001, 8001)])
        self.assertEqual(segments[0]['hits'], 3)

    def test_players_independent_absorbed_not_overkill_and_ticks(self):
        events = [action(1000, type='damage', amount=10, absorbed=5, overkill=100),
                  action(1100, type='damage', targetID=4, amount=40),
                  action(1500, type='damage', amount=20, tick=True),
                  action(1600, type='damage', amount=999, fake=True), action(1700)]
        segments = merge_damage_segments(events)
        self.assertEqual(segments[3][0]['damage'], 35)
        self.assertEqual((segments[3][0]['hits'], segments[3][0]['ticks']), (1, 1))
        self.assertEqual(segments[4][0]['damage'], 40)
        self.assertEqual(merge_damage_segments([]), {})

    def test_ability_output_shows_first_eight_segments_chronologically(self):
        run = make_run()
        events = [action(110000 + index * 3000, type='damage', amount=10) for index in reversed(range(10))]
        with patch('wclr.cmd_damage.data.events', return_value=(events, False)):
            output = _ability_detail(run, '100')
        segments = output.split('## 受伤段', 1)[1].split('## 直接命中', 1)[0]
        self.assertEqual(segments.count('| 0/1 |'), 8)
        self.assertLess(segments.index('0:10.0–0:10.0'), segments.index('0:13.0–0:13.0'))
        self.assertIn('其余 2 段略', segments)


class InterruptMetricTests(unittest.TestCase):
    def test_pure_and_control_by_id_not_misleading_name(self):
        abilities = [dict(guid=1766, name='脚踢', total=3), dict(guid=999, name='Kick', total=2)]
        self.assertEqual(split_interrupts(abilities, 5), (3, 2))

    def test_missing_ids_localized_and_shared_alias_names(self):
        self.assertEqual(split_interrupts([dict(name='法术封锁', total=4), dict(name='恐惧', total=2)],
                                         6, ['法术封锁']), (4, 2))
        self.assertEqual(split_interrupts([dict(name='Spell Lock', total=4)], 4), (4, 0))
        self.assertEqual(split_interrupts([], 0), (0, 0))

    def test_count_inconsistency_boundaries(self):
        for values, expected in [((20, 21, 0), True), ((20, 10, 11), False), ((20, 10, 12), True),
                                 ((0, 0, 0), False), ((0, 0, 1), True), ((100, 30, 70), False)]:
            with self.subTest(values=values):
                self.assertEqual(inconsistent_counts(*values), expected)

    def test_capacity_in_ms_and_missing_intervals(self):
        self.assertEqual(estimate_capacity(60000, [15000, 24000, None, 0, -1]), 6.5)
        self.assertEqual(estimate_capacity(60000, []), 0)
        self.assertEqual(estimate_capacity(-1, [15000]), 0)

    def test_enemy_cast_counts_do_not_duplicate_begin_and_completion(self):
        events = [action(1000, type='begincast', sourceID=10, sourceInstance=1),
                  action(1200, type='cast', sourceID=10, sourceInstance=1),
                  action(1500, type='begincast', sourceID=10, sourceInstance=2),
                  action(1700, type='begincast', sourceID=11),
                  action(1800, type='cast', sourceID=12, abilityGameID=101),
                  action(1900, type='begincast', sourceID=10, fake=True)]
        self.assertEqual(enemy_cast_counts(events, [100, 101, 102]), {100: (3, 3), 101: (1, 1), 102: (0, 0)})


class CommandIntegrationTests(unittest.TestCase):
    def test_missing_pull_is_chinese_error_without_querying(self):
        with patch('wclr.cmd_interrupts.data.parallel') as parallel, self.assertRaisesRegex(WCLError, '没有第 2 波'):
            cmd_interrupts(make_run(), pull=2)
        parallel.assert_not_called()

    def test_no_interrupt_pull_does_not_claim_no_interrupts_for_whole_fight(self):
        run = make_run()
        run.pulls = [SimpleNamespace(idx=1, start=120000, end=140000, dur=20000)]
        with patch('wclr.cmd_interrupts.data.parallel', return_value={'table': {}, 'disp': {}}):
            output = cmd_interrupts(run, pull=1)
        self.assertIn('本波没有任何敌方技能', output)
        self.assertIn('本波没有驱散记录', output)
        self.assertNotIn('本场没有', output)

    def test_all_deaths_have_returns_even_without_details(self):
        run = make_run()
        deaths = [dict(targetID=3, type='death', timestamp=110000), dict(targetID=4, type='death', timestamp=130000)]
        with patch('wclr.cmd_deaths.data.parallel', return_value={'events': deaths, 'table': {}}), \
                patch('wclr.cmd_deaths.fetch', return_value={'r0': {'data': [action(120000)]}, 'r1': {'data': []}}) as fetch, \
                patch('wclr.cmd_deaths._availability_data') as availability:
            output = cmd_deaths(run, detail=0)
        fetch.assert_called_once()
        self.assertIn('r0: events', fetch.call_args.args[1])
        self.assertIn('r1: events', fetch.call_args.args[1])
        self.assertIn('+10.0秒', output)
        self.assertIn('300 秒内无动作', output)
        self.assertIn('缺席时长的上界', output)
        self.assertIn('可能漏掉非常规复活', output)
        availability.assert_not_called()

    def test_repeated_deaths_reuse_cast_queries(self):
        run = make_run()
        deaths = [dict(targetID=3, type='death', timestamp=timestamp) for timestamp in [110000, 140000]]
        entries = [dict(guid=100, name='减伤', total=2)]
        run.pulls = [SimpleNamespace(start=100000, end=200000, idx=1, dur=100000, is_boss=False, mobs=[], name='测试波')]
        with patch('wclr.cmd_deaths.data.parallel', return_value={'events': deaths, 'table': {}}), \
                patch('wclr.cmd_deaths.data.casts', return_value={'entries': entries}) as casts, \
                patch('wclr.cmd_deaths.fetch', side_effect=[{'r0': {'data': []}, 'r1': {'data': []}},
                      {'e': {'data': [action(105000), action(125000)]}}, {'d0': {'data': []}, 'd1': {'data': []}}]) as fetch:
            output = cmd_deaths(run)
        casts.assert_called_once_with(run, 3)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(output.count('#### 技能可用性'), 2)
        self.assertIn('可能在冷却', output)
        self.assertIn('充能类技能不适用', output)

    def test_pull_tables_scoped_but_player_interval_uses_whole_fight(self):
        run = make_run()
        run.abilities[1766] = {'name': '脚踢'}
        run.pulls = [SimpleNamespace(idx=1, start=120000, end=140000, dur=20000)]
        table = {'entries': [dict(guid=100, spellsBegun=2, spellsInterrupted=3, spellsCompleted=0,
                                 details=[dict(id=3, total=3, abilities=[dict(guid=1766, name='脚踢', total=2),
                                                                      dict(guid=999, name='恐惧', total=1)])])]}
        kicks = [action(timestamp, abilityGameID=1766) for timestamp in [105000, 125000, 145000]]

        def events(*args, **kwargs):
            if kwargs.get('hostility') == 'Enemies':
                return [action(122000, type='begincast', sourceID=10),
                        action(123000, type='cast', sourceID=10)], False
            self.assertNotIn('start', kwargs)
            return kicks, False

        with patch('wclr.cmd_interrupts.data.window_table', side_effect=[table, {}]) as window_table, \
                patch('wclr.cmd_interrupts.data.events', side_effect=events):
            output = cmd_interrupts(run, pull=1)
        self.assertEqual(window_table.call_count, 2)
        self.assertEqual(window_table.call_args_list[0].args, (run, 'Interrupts', 120000, 140000))
        self.assertEqual(window_table.call_args_list[1].args, (run, 'Dispels', 120000, 140000))
        self.assertIn('不一致', output)
        self.assertIn('| 2 | 1 | 脚踢(1766) 1 |', output)
        self.assertIn('20.0 秒', output)
        self.assertIn('= 1.0 次', output)
        self.assertIn('需要打断的读条总数', output)

    def test_window_table_clamps_report_times(self):
        with patch('wclr.data.fetch', return_value={'t': {'data': {}}}) as fetch:
            data.window_table(make_run(), 'Interrupts', 90000, 300000)
        self.assertIn('startTime: 100000, endTime: 200000', fetch.call_args.args[1])

    # make_run 的副本英文名是 'Test Dungeon'；限时 120 秒，官方用时 90 秒。
    TIMERS = [{'name': 'Other Dungeon', 'short_name': 'OD', 'keystone_timer_seconds': 1800},
              {'name': 'Test Dungeon', 'short_name': 'TD', 'keystone_timer_seconds': 120}]

    def test_overview_population_reliability_and_adjusted_time(self):
        run = make_run()
        keys = player_keys(run)
        ranks = [{'roles': {'dps': {'characters': [dict(name='猎人', bracketPercent=12, rankPercent=50)]}}}]
        for population, expected in [({'count': 4, 'more': False}, '12（样本 4 人，不可靠）'),
                                     ({'count': 20, 'more': False}, '12（样本 20 人）'),
                                     ({'count': 4, 'more': True}, '12（样本 4 人）')]:
            with self.subTest(population=population), \
                    patch('wclr.context.rio_static_data', return_value=self.TIMERS), \
                    patch('wclr.cmd_overview.data.parallel', return_value={
                        'dd': {}, 'intr': {}, 'rkd': ranks, 'rkh': [], 'populations': {keys[3]: population}}):
                output = cmd_overview(run)
                self.assertIn(expected, output)
                self.assertIn('样本小时百分位的噪声很大', output)
        with patch.object(run, 'death_penalty', return_value=(5000, '测试')):
            self.assertIn('1:30.0 − 2 × 5 秒 = 1:20.0', '\n'.join(_timing_lines(run, 2)))

    def test_overview_timer_matches_dungeon_and_computes_upgrade_lines(self):
        run = make_run()
        with patch('wclr.context.rio_static_data', return_value=self.TIMERS) as static:
            lines = '\n'.join(_timing_lines(run, 0))
            self.assertEqual(run.timer_ms(), 120000)
            run.timer_ms()
        static.assert_called_once()  # 限时只查一次，结果缓存在 Run 上
        # 120 秒限时：+2 线 = 0.8 × 120 = 96 秒（90 秒已达成），+3 线 = 72 秒（差 18 秒）
        self.assertIn('官方用时 1:30.0 / 限时 2:00 → 剩余 0:30.0', lines)
        self.assertIn('+2 线 1:36（已达成）', lines)
        self.assertIn('+3 线 1:12（差 0:18.0）', lines)

    def test_overview_timer_unavailable_says_so_instead_of_guessing(self):
        for static in ([], [{'name': 'Other Dungeon', 'keystone_timer_seconds': 1800}]):
            with self.subTest(static=static), patch('wclr.context.rio_static_data', return_value=static):
                run = make_run()
                lines = '\n'.join(_timing_lines(run, 0))
                self.assertIsNone(run.timer_ms())
                self.assertIn('官方用时 1:30.0（未能从 Raider.IO 获取该副本限时）', lines)
                self.assertNotIn('限时 30:00', lines)

    def test_player_ability_only_fetches_filtered_casts_and_shows_each_time(self):
        run = make_run()
        run.abilities.update({100: {'name': '测试减伤'}, 101: {'name': '测试光环'}})
        events = [action(140000), action(110000), action(160000), action(150000, sourceID=4)]
        with patch('wclr.cmd_player.data.events', return_value=(events, False)) as fetch, \
                patch('wclr.cmd_player.data.parallel') as parallel:
            output = cmd_player(run, '猎人', ability='测试减伤')
        parallel.assert_not_called()
        self.assertEqual(fetch.call_args.kwargs['source'], 3)
        self.assertEqual(fetch.call_args.kwargs['expr'], 'type = "cast" and ability.id in (100)')
        self.assertIn('3 次；最短/最长间隔 20.0/30.0 秒', output)
        self.assertLess(output.index('0:10.0'), output.index('0:40.0'))

    def test_player_rare_threshold_is_1_2_without_old_four_cast_floor(self):
        run = make_run(endTime=220000)
        run.pulls = [SimpleNamespace(start=100000, end=220000, is_boss=False)]
        got = dict(casts={'entries': [dict(guid=100, total=2), dict(guid=101, total=3)]},
                   dmg={}, taken={}, buffs={}, dd_all={}, rk=[])
        with patch('wclr.cmd_player.data.parallel', return_value=got), \
                patch('wclr.cmd_player.data.events', return_value=([], False)) as fetch:
            cmd_player(run, '猎人')
        self.assertEqual(fetch.call_args.kwargs['expr'], 'type = "cast" and ability.id in (100)')

    def test_player_rare_threshold_includes_exact_1_2(self):
        run = make_run(endTime=400000)
        run.pulls = [SimpleNamespace(start=100000, end=400000, is_boss=False)]
        got = dict(casts={'entries': [dict(guid=100, total=6), dict(guid=101, total=7)]},
                   dmg={}, taken={}, buffs={}, dd_all={}, rk=[])
        with patch('wclr.cmd_player.data.parallel', return_value=got), \
                patch('wclr.cmd_player.data.events', return_value=([], False)) as fetch:
            cmd_player(run, '猎人')
        self.assertEqual(fetch.call_args.kwargs['expr'], 'type = "cast" and ability.id in (100)')

    def test_player_rare_timeline_limit_is_25(self):
        run = make_run(endTime=220000)
        run.pulls = [SimpleNamespace(start=100000, end=220000, is_boss=False)]
        got = dict(casts={'entries': [dict(guid=100 + index, total=1) for index in range(30)]},
                   dmg={}, taken={}, buffs={}, dd_all={}, rk=[])
        with patch('wclr.cmd_player.data.parallel', return_value=got), \
                patch('wclr.cmd_player.data.events', return_value=([], False)) as fetch:
            cmd_player(run, '猎人', top=100)
        expression = fetch.call_args.kwargs['expr']
        self.assertIn('124)', expression)
        self.assertNotIn('125', expression)

    def test_events_all_player_is_explicitly_bidirectional(self):
        args = build_parser().parse_args(['events', CODE, '--type', 'all', '--player', '猎人'])
        with patch('wclr.cmd_events.data.events', return_value=([], False)) as fetch:
            output = cmd_events(make_run(), args)
        self.assertEqual(fetch.call_args.kwargs['expr'], '(source.name = "猎人" or target.name = "猎人")')
        self.assertIn('玩家双向过滤：施放或承受', output)
        self.assertIn('双向过滤', build_parser()._subparsers._group_actions[0].choices['events'].format_help())

    def test_new_cli_options_dispatch(self):
        run = make_run()
        parser = build_parser()
        with patch('wclr.context.load_run', return_value=run), \
                patch('wclr.cmd_interrupts.cmd_interrupts', return_value='ok') as interrupts:
            self.assertEqual(dispatch(None, parser.parse_args(['interrupts', CODE, '--pull', '2'])), 'ok')
        interrupts.assert_called_once_with(run, times=8, pull=2)
        with patch('wclr.context.load_run', return_value=run), \
                patch('wclr.cmd_player.cmd_player', return_value='ok') as player:
            self.assertEqual(dispatch(None, parser.parse_args(['player', CODE, '猎人', '--ability', '100'])), 'ok')
        player.assert_called_once_with(run, '猎人', top=15, ability='100')


if __name__ == '__main__':
    unittest.main()
