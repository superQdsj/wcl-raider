"""分页、缓存、命令错误与输出语义的离线回归。"""
import contextlib
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from support import CODE, make_run
from wclr import api, data
from wclr.api import Client, WCLError
from wclr.cli import build_parser, main
from wclr.context import load_meta
from wclr.cmd_compare import _bench_player, _bench_run, _boss_times, _logged
from wclr.cmd_deaths import _recap_fields, cmd_deaths
from wclr.cmd_events import cmd_events
from wclr.cmd_interrupts import cmd_interrupts
from wclr.cmd_overview import cmd_overview
from wclr.cmd_player import cmd_player


def setUpModule():
    global network, language
    network = patch('urllib.request.urlopen', side_effect=AssertionError('离线测试禁止网络'))
    network.start()
    language = patch('wclr.api.default_lang', return_value='zh')
    language.start()


def tearDownModule():
    language.stop()
    network.stop()


class PaginationTests(unittest.TestCase):
    def test_multiple_pages_report_relative_and_fake_excluded(self):
        r = make_run()
        pages = [{'e': {'data': [{'timestamp': 101000}, {'timestamp': 101001, 'fake': True}],
                        'nextPageTimestamp': 110000}},
                 {'e': {'data': [{'timestamp': 111000}], 'nextPageTimestamp': None}}]
        with patch('wclr.data.fetch', side_effect=pages) as fetch:
            events, truncated = data.events(r, limit=3)
        self.assertEqual([e['timestamp'] for e in events], [101000, 111000])
        self.assertFalse(truncated)
        self.assertIn('startTime: 100000', fetch.call_args_list[0].args[1])
        self.assertIn('startTime: 110000', fetch.call_args_list[1].args[1])

    def test_page_over_limit_is_bounded_even_on_last_page(self):
        with patch('wclr.data.fetch', return_value={'e': {'data': [{'timestamp': 101000}] * 100}}):
            events, truncated = data.events(make_run(), limit=3)
        self.assertEqual(len(events), 3)
        self.assertTrue(truncated)

    def test_exact_limit_without_more_is_not_truncated(self):
        with patch('wclr.data.fetch', return_value={'e': {'data': [{'timestamp': 101000}]}}):
            self.assertFalse(data.events(make_run(), limit=1)[1])

    def test_exact_limit_with_more_is_truncated(self):
        with patch('wclr.data.fetch', return_value={'e': {'data': [{'timestamp': 101000}], 'nextPageTimestamp': 110000}}):
            self.assertTrue(data.events(make_run(), limit=1)[1])

    def test_stalled_cursor_is_explicit_error(self):
        with patch('wclr.data.fetch', return_value={'e': {'data': [], 'nextPageTimestamp': 100000}}):
            with self.assertRaisesRegex(WCLError, '游标未前进'):
                data.events(make_run())

    def test_page_guard_is_reported_as_truncation(self):
        pages = [{'e': {'data': [], 'nextPageTimestamp': 100001 + i}} for i in range(50)]
        with patch('wclr.data.fetch', side_effect=pages):
            self.assertEqual(data.events(make_run()), ([], True))

    def test_outside_window_does_not_query(self):
        with patch('wclr.data.fetch') as fetch:
            self.assertEqual(data.events(make_run(), start=300000), ([], False))
            self.assertEqual(data.events(make_run(), limit=0), ([], False))
            fetch.assert_not_called()

    def test_damage_taken_source_argument_is_the_holder(self):
        with patch('wclr.data.fetch', return_value={'t': {'data': {'entries': []}}}) as fetch:
            data.damage_taken(make_run(), player=3)
        self.assertIn('sourceID: 3', fetch.call_args.args[1])
        self.assertNotIn('targetID:', fetch.call_args.args[1])

    def test_graph_total_does_not_double_count_total_row(self):
        r = make_run()
        graph = {'series': [dict(id=3, data=[10, 20], pointStart=100000, pointInterval=1000),
                            dict(id='Total', name='Total', data=[10, 20], pointStart=100000, pointInterval=1000)]}
        self.assertEqual(data.player_series_total(graph, r), ([10, 20], 100000, 1000))


class CacheTests(unittest.TestCase):
    def test_atomic_concurrent_writes_leave_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'shared.json'
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i: api._cache_put(path, {'i': i, 'payload': '中文' * 1000}), range(40)))
            value = json.loads(path.read_text())
            self.assertIn(value['i'], range(40))
            self.assertEqual(value['payload'], '中文' * 1000)
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_ttl_and_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'cache.json'
            api._cache_put(p, {'valid': 1})
            self.assertEqual(api._cache_get(p, 3600), {'valid': 1})
            self.assertIsNone(api._cache_get(p, -1))
            p.write_text('{broken')
            self.assertIsNone(api._cache_get(p, 3600))

    def test_partial_results_are_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp, patch('wclr.api.CACHE_DIR', Path(tmp)):
            c = Client(lang='zh')
            with patch.object(c, '_post', side_effect=[{'_errors': ['临时错误'], 'a': None}, {'a': 1}]) as post:
                self.assertIn('_errors', c.gql('{a}', partial=True))
                self.assertEqual(c.gql('{a}'), {'a': 1})
                self.assertEqual(c.gql('{a}'), {'a': 1})
                self.assertEqual(post.call_count, 2)
                self.assertEqual((c.live, c.cached), (2, 1))

    def test_legacy_partial_cache_not_reused(self):
        c = Client(lang='zh')
        with patch('wclr.api._cache_get', return_value={'_errors': ['old error']}), \
                patch.object(c, '_post', return_value={'a': 1}) as post, patch('wclr.api._cache_put'):
            self.assertEqual(c.gql('{a}'), {'a': 1})
            post.assert_called_once()

    def test_concurrent_client_counters_and_out_of_order_rates(self):
        c = Client(lang='zh')
        with patch.object(c, '_post', return_value={'a': 1}):
            result = data.parallel({str(i): lambda: c.gql('{a}', ttl=0) for i in range(40)}, workers=8)
        self.assertEqual(len(result), 40)
        self.assertEqual(c.live, 40)
        c._record_rate(dict(pointsSpentThisHour=50, pointsResetIn=100))
        c._record_rate(dict(pointsSpentThisHour=40, pointsResetIn=100))
        self.assertEqual(c.rate['pointsSpentThisHour'], 50)
        c._record_rate(dict(pointsSpentThisHour=1, pointsResetIn=3600))
        self.assertEqual(c.rate['pointsSpentThisHour'], 1)

    def test_parallel_propagates_failure(self):
        def fail():
            raise WCLError('缺失表')
        with self.assertRaisesRegex(WCLError, '缺失表'):
            data.parallel({'ok': lambda: 1, 'bad': fail})

    def test_live_meta_reloads_old_cached_result(self):
        report = dict(endTime=1000, fights=[{'inProgress': True}])
        client = Mock(last_age=600)
        client.gql.return_value = {'reportData': {'report': report}}
        _, ttl = load_meta(client, CODE)
        self.assertEqual(ttl, 300)
        self.assertEqual(client.gql.call_count, 2)
        self.assertEqual(client.gql.call_args.kwargs['ttl'], 300)

    def test_recent_and_old_report_ttls(self):
        for end, expected in [(999000, 300), (0, api.DAY)]:
            client = Mock(last_age=1)
            client.gql.return_value = {'reportData': {'report': dict(endTime=end, fights=[])}}
            with patch('wclr.context.time.time', return_value=1000 if end else 20000):
                self.assertEqual(load_meta(client, CODE)[1], expected)
            self.assertEqual(client.gql.call_count, 1)


class CommandTests(unittest.TestCase):
    def test_player_buff_denominator_and_table_names_and_top(self):
        r = make_run()
        r.abilities[30146] = {'name': '召唤恶魔卫士'}
        r.summary['damageDone'] = [{'id': 3, 'total': 1000}]
        got = dict(casts={'entries': [dict(guid=100 + i, name=f'技能{i}', total=100 - i) for i in range(10)]},
                   dmg={'entries': [dict(guid=30146, name='Rinnvazul', total=1000)]},
                   taken={}, dd_all={}, rk=[],
                   buffs=dict(startTime=0, endTime=7000000, totalTime=100000,
                              auras=[dict(name='光环', guid=10, totalUptime=96000, totalUses=1)]))
        with patch('wclr.cmd_player.data.parallel', return_value=got):
            out = cmd_player(r, '猎人', top=5)
        self.assertIn('96%', out)
        self.assertIn('Rinnvazul(30146)', out)
        self.assertNotIn('召唤恶魔卫士(30146)', out)
        self.assertIn('技能4(104)', out)
        self.assertNotIn('技能5(105)', out)

    def test_overview_pet_interrupt_attributed_to_owner(self):
        r = make_run()
        r.timer_ms = lambda: None
        r.affix_names = lambda: []
        got = dict(dd={}, intr={'entries': [dict(spellsBegun=5, details=[dict(id=6, total=3)])]}, rkd=[], rkh=[])
        with patch('wclr.cmd_overview.data.parallel', return_value=got):
            out = cmd_overview(r)
        row = next(line for line in out.splitlines() if line.startswith('| 猎人 |'))
        self.assertIn('| 0 | 3 | 0 | 0 |', row)
        self.assertIn('非 GCD 利用率', out)

    def test_interrupt_same_name_ids_subtracted_once(self):
        r = make_run()
        r.abilities = {19647: {'name': '法术封锁'}, 119910: {'name': '法术封锁'}}
        got = {'table': {'entries': [dict(guid=99, spellsBegun=4, spellsInterrupted=4,
                    details=[dict(id=6, total=4, abilities=[dict(name='法术封锁', total=4)])])]},
               'kicks': ([dict(sourceID=6, abilityGameID=gid) for gid in (19647, 19647, 119910, 119910)], False)}
        with patch('wclr.cmd_interrupts.data.parallel', return_value=got):
            out = cmd_interrupts(r)
        row = next(line for line in out.splitlines() if line.startswith('| 猎人('))
        self.assertIn('| 4 |', row)
        self.assertIn('| 0 |', row)
        self.assertIn('汇总差值', out)

    def test_no_death_and_no_interrupt_outputs(self):
        r = make_run()
        with patch('wclr.cmd_deaths.data.parallel', return_value={'table': {}, 'events': []}):
            self.assertIn('没有玩家死亡', cmd_deaths(r))
        with patch('wclr.cmd_interrupts.data.parallel', return_value={'table': {}}):
            self.assertIn('未记录打断', cmd_interrupts(r))

    def test_death_partial_error_not_reported_as_no_damage(self):
        r = make_run()
        got = {'table': {}, 'events': [dict(type='death', targetID=3, timestamp=110000)]}
        with patch('wclr.cmd_deaths.data.parallel', return_value=got), \
                patch('wclr.cmd_deaths.data.casts', return_value={}), \
                patch('wclr.cmd_deaths.fetch', return_value={'d0': None, '_errors': ['窗口错误']}):
            out = cmd_deaths(r)
        self.assertIn('部分死亡窗口获取失败', out)
        self.assertIn('无法判断', out)
        self.assertNotIn('未查到伤害事件', out)

    def test_death_recap_uses_names_and_clamped_report_timestamps(self):
        r = make_run()
        r.players[3].name = 'A"\\B'
        fields = _recap_fields(r, [dict(targetID=3, timestamp=101000)], 10000)
        self.assertIn('startTime: 100000', fields)
        self.assertIn('endTime: 101300', fields)
        self.assertIn('target.name', fields)
        self.assertNotIn('target.id', fields)
        self.assertIn('nextPageTimestamp', fields)

    def test_player_target_filter_uses_name(self):
        r = make_run()
        r.players[3].name = 'Sìmply'
        args = build_parser().parse_args(['events', CODE, '--type', 'damage-taken', '--player', 'Sìmply'])
        with patch('wclr.cmd_events.data.events', return_value=([], False)) as events:
            cmd_events(r, args)
        self.assertEqual(events.call_args.kwargs['expr'], 'target.name = "Sìmply"')

    def test_bad_time_is_chinese_cli_error(self):
        r = make_run()
        args = build_parser().parse_args(['events', CODE, '--from', 'NaN'])
        with self.assertRaisesRegex(WCLError, '无效时间'):
            cmd_events(r, args)

    def test_benchmark_partial_errors_are_excluded(self):
        r = make_run()
        r.client = Mock()
        r.client.gql.return_value = {'_errors': ['missing'], 'reportData': {'report': {'fights': [{'id': 1}]}}}
        self.assertEqual(_bench_run(r, CODE, 1), {})
        self.assertIsNone(_bench_player(r, {'report': {'code': CODE, 'fightID': 1}}))

    def test_unlogged_rankings_and_self_are_skipped(self):
        r = make_run()
        other = {'report': {'code': 'OtherCode1234567X', 'fightID': 2}}
        rows = [{'report': {'code': None}}, {'report': {'code': CODE, 'fightID': 1}}, other]
        self.assertEqual(_logged(rows, r), [other])

    def test_boss_failed_attempt_separate_from_kill_time(self):
        pulls = [dict(encounterID=10, kill=False, startTime=10000, endTime=30000),
                 dict(encounterID=10, kill=True, startTime=50000, endTime=110000)]
        self.assertEqual(_boss_times(pulls), {10: (60000, 2, 80000)})

    def test_query_input_errors_have_no_traceback_or_network(self):
        for argv in [['query', '{}', '--vars', 'bad'], ['query', '{}', '--vars', '[]'],
                     ['query', '@/does/not/exist']]:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(main(argv), 2)
            self.assertIn('错误：', err.getvalue())
            self.assertNotIn('Traceback', err.getvalue())

    def test_query_output_budget_includes_truncation_notice(self):
        client = Client(lang='zh')
        for limit in (1, 100, 6000):
            out = io.StringIO()
            with patch('wclr.cli.Client', return_value=client), \
                    patch.object(client, 'gql', return_value={'data': '中文' * 5000}), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['query', '{}', '--max-chars', str(limit)]), 0)
            self.assertLessEqual(len(out.getvalue().rstrip('\n')), limit)
            if limit >= 100:
                self.assertIn('已截断', out.getvalue())

    def test_invalid_numeric_options_rejected_by_parser(self):
        for argv in [['events', CODE, '--limit', '-1'], ['events', CODE, '--pull', '0'],
                     ['deaths', CODE, '--window', 'nan'], ['deaths', CODE, '--detail', '-1'],
                     ['damage', CODE, '--top', '0'], ['compare', CODE, '--runs', '-1']]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                build_parser().parse_args(argv)
            self.assertEqual(exc.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
