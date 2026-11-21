"""分页、缓存、events/query 命令错误与输出语义的离线回归。"""
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
from wclr.cmd_events import cmd_events
from wclr.context import load_meta


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
    def test_player_target_filter_uses_name(self):
        r = make_run()
        r.players[3].name = 'Sìmply'
        args = build_parser().parse_args(['events', CODE, '--type', 'damage-taken', '--player', 'Sìmply'])
        with patch('wclr.cmd_events.data.events', return_value=([], False)) as events:
            cmd_events(r, args)
        self.assertEqual(events.call_args.kwargs['expr'], 'target.name = "Sìmply"')

    def test_events_all_player_is_explicitly_bidirectional(self):
        args = build_parser().parse_args(['events', CODE, '--type', 'all', '--player', '猎人'])
        with patch('wclr.cmd_events.data.events', return_value=([], False)) as fetch:
            output = cmd_events(make_run(), args)
        self.assertEqual(fetch.call_args.kwargs['expr'], '(source.name = "猎人" or target.name = "猎人")')
        self.assertIn('玩家双向过滤：施放或承受', output)
        self.assertIn('双向过滤', build_parser()._subparsers._group_actions[0].choices['events'].format_help())

    def test_bad_time_is_chinese_cli_error(self):
        r = make_run()
        args = build_parser().parse_args(['events', CODE, '--from', 'NaN'])
        with self.assertRaisesRegex(WCLError, '无效时间'):
            cmd_events(r, args)

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
                     ['find', '毒牙祭坛', '--level', '0'], ['find', '毒牙祭坛', '--limit', '-1']]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                build_parser().parse_args(argv)
            self.assertEqual(exc.exception.code, 2)


class V1AdapterTests(unittest.TestCase):
    def test_auto_mode_prefers_v1_when_key_present(self):
        with patch('wclr.api.load_v1_key', return_value='dummy-v1-key'):
            self.assertTrue(Client(lang='zh', api_version='auto').use_v1)
            self.assertTrue(Client(lang='zh', api_version='v1').use_v1)
            self.assertFalse(Client(lang='zh', api_version='v2').use_v1)
        with patch('wclr.api.load_v1_key', return_value=None):
            self.assertFalse(Client(lang='zh', api_version='auto').use_v1)
            self.assertTrue(Client(lang='zh', api_version='v1').use_v1)

    def test_v1_meta_and_events_normalization(self):
        from wclr.context import _v1_pulls, _v1_to_meta
        raw = {
            'lang': 'zh', 'title': 't', 'start': 1000, 'end': 2000, 'zone': 55,
            'friendlies': [{'id': 6, 'name': 'Tank', 'type': 'Druid', 'server': 'S', 'region': 'CN', 'fights': [{'id': 9}]}],
            'enemies': [{'id': 455, 'name': 'Mob', 'type': 'NPC', 'guid': 241813}],
            'friendlyPets': [{'id': 17, 'name': 'Pet', 'type': 'Pet', 'petOwner': 6, 'guid': 226269}],
            'fights': [{
                'id': 9, 'boss': 12825, 'start_time': 100000, 'end_time': 200000, 'name': '纳洛拉克的洞穴',
                'difficulty': 10, 'kill': True, 'keystoneLevel': 22, 'affixes': [10, 9, 147],
                'completionTime': 90000, 'dungeonPulls': [{
                    'id': 1, 'boss': 0, 'start_time': 101000, 'end_time': 150000, 'name': 'P1', 'kill': False,
                    'enemies': [[241813, 455, 1, 3, 1, 1]],
                }],
            }],
        }
        meta = _v1_to_meta(CODE, raw)
        self.assertEqual(meta['region']['slug'], 'CN')
        self.assertEqual(meta['fights'][0]['encounterID'], 12825)
        self.assertEqual(meta['fights'][0]['keystoneTime'], 90000)
        pulls = _v1_pulls(meta['fights'][0]['_v1_raw'])
        self.assertEqual(pulls[0]['enemyNPCs'][0], {'gameID': 241813, 'id': 455, 'minimumInstanceID': 1, 'maximumInstanceID': 3})

        r = make_run()
        r.client = Client(lang='zh', api_version='v1')
        pages = [
            {'events': [
                {'timestamp': 101000, 'type': 'damage', 'ability': {'guid': 8921, 'name': '月火术', 'type': 64}},
                {'timestamp': 101001, 'fake': True},
            ], 'nextPageTimestamp': 110000},
            {'events': [
                {'timestamp': 111000, 'type': 'interrupt',
                 'ability': {'guid': 1766, 'name': '脚踢'},
                 'extraAbility': {'guid': 9999, 'name': '敌方读条'}},
            ]},
        ]
        with patch.object(r.client, 'v1_get', side_effect=pages):
            evs, truncated = data.events(r, data_type='All', limit=5)
        self.assertFalse(truncated)
        self.assertEqual([e['abilityGameID'] for e in evs], [8921, 1766])
        self.assertEqual(evs[1]['extraAbilityGameID'], 9999)
        self.assertEqual(r.ab(8921), '月火术')
        self.assertEqual(r.ab(9999), '敌方读条')

    def test_v1_resolve_dungeon_and_find_runs(self):
        from wclr.cmd_find import find_runs, resolve_dungeon
        c = Client(lang='zh', api_version='v1')
        zones = [
            {'id': 56, 'name': 'PTR Zone', 'encounters': [{'id': 999, 'name': '毒牙祭坛'}]},
            {'id': 55, 'name': 'Mythic+ Season 2', 'encounters': [{'id': 12825, 'name': '毒牙祭坛'}]},
        ]
        with patch.object(c, 'v1_get', return_value=zones):
            self.assertEqual(resolve_dungeon(c, '毒牙祭坛'), (12825, '毒牙祭坛'))

        classes = [{'id': 12, 'name': 'Demon Hunter', 'specs': [{'id': 1, 'name': 'Havoc'}, {'id': 3, 'name': 'Devourer'}]}]
        rk = {'hasMorePages': False, 'rankings': [
            {'name': 'NoLog', 'class': 12, 'spec': 3, 'reportID': '', 'fightID': None, 'keystoneLevel': 25},
            {'name': 'PlayerA', 'class': 12, 'spec': 3, 'reportID': CODE, 'fightID': 9, 'keystoneLevel': 23,
             'duration': 1500000, 'regionName': '欧服'},
        ]}
        with patch.object(c, 'v1_get', side_effect=[classes, rk]) as v1_get:
            rows, note = find_runs(c, 12825, cls='DemonHunter', spec='Devourer', level=23, want=5)
        self.assertEqual(note, '+23')
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['code'], rows[0]['fid'], rows[0]['level']), (CODE, 9, 23))
        self.assertEqual(v1_get.call_args_list[1].args[1]['bracket'], 22)


if __name__ == '__main__':
    unittest.main()
