"""分段计时（splits）与险情（danger）的纯函数测试；合成数据，禁止网络。"""
import unittest
from unittest.mock import patch

import support  # noqa: F401  (设置 sys.path)
from wclr.cmd_danger import find_dips, hp_points, team_moments
from wclr.cmd_splits import (
    Segment, Wave, build_segments, mob_costs, pace_excess, route_similarity, total_mobs, wave_ref_time,
)


def setUpModule():
    global network
    network = patch('urllib.request.urlopen', side_effect=AssertionError('离线测试禁止网络'))
    network.start()


def tearDownModule():
    network.stop()


def pull(start, end, enc=0, kill=None, npcs=()):
    return dict(encounterID=enc, kill=kill, startTime=start, endTime=end,
                enemyNPCs=[dict(gameID=g, minimumInstanceID=lo, maximumInstanceID=hi) for g, lo, hi in npcs])


START = 1_000_000
COUNTS = {'10': 5, '11': 2, '12': 0}


class SegmentTests(unittest.TestCase):
    def test_segments_split_on_first_kill_and_track_wipes_and_repulls(self):
        pulls = [
            pull(START + 20_000, START + 80_000, npcs=[(10, 1, 4)]),            # 4 只 10 号怪
            pull(START + 90_000, START + 150_000, enc=1, kill=True, npcs=[(99, 1, 1)]),
            pull(START + 160_000, START + 200_000, npcs=[(11, 1, 3)]),
            pull(START + 210_000, START + 230_000, enc=2, kill=False, npcs=[(98, 1, 1), (11, 4, 5)]),
            pull(START + 260_000, START + 290_000, npcs=[(11, 4, 5)]),          # 灭团后重拉：之前出现过
            pull(START + 300_000, START + 400_000, enc=2, kill=True, npcs=[(98, 1, 1)]),
            pull(START + 400_000, START + 400_500, npcs=[(10, 9, 9)]),          # 0.5 秒伪波次，忽略
        ]
        deaths = [START + 220_000, START + 221_000]
        segs = build_segments(pulls, START, START + 400_000, COUNTS, deaths)
        self.assertEqual([s.encounter for s in segs], [1, 2])
        a, b = segs
        self.assertEqual((a.start, a.end, a.dur), (0, 150_000, 150_000))
        self.assertEqual((a.pulls, a.boss, a.wipes), (1, 60_000, 0))
        self.assertEqual(a.combat, 120_000)
        self.assertEqual(a.idle, 30_000)
        self.assertEqual(a.forces, 20)
        self.assertEqual(a.mobs, {10: 4})
        self.assertEqual((b.pulls, b.wipe_count, b.wipes, b.boss, b.deaths), (2, 1, 20_000, 100_000, 2))
        self.assertEqual(b.mobs, {11: 5})                     # 重拉的 11 号怪不重复计数
        self.assertEqual(b.forces, 10)
        repull = [w for w in b.waves if w.idx == 5][0]
        self.assertEqual(repull.mobs, {})
        self.assertEqual(repull.raw, {11: 2})
        self.assertEqual(b.trash, b.combat - b.boss - b.wipes)

    def test_unfinished_run_gets_trailing_segment(self):
        pulls = [pull(START + 10_000, START + 50_000, enc=1, kill=True),
                 pull(START + 60_000, START + 90_000, npcs=[(10, 1, 1)])]
        segs = build_segments(pulls, START, START + 120_000, COUNTS, [START + 100_000])
        self.assertEqual([s.encounter for s in segs], [1, 0])
        self.assertEqual(segs[-1].end, 120_000)
        self.assertEqual(segs[-1].deaths, 1)


class RouteTests(unittest.TestCase):
    def test_similarity_ignores_zero_value_mobs_and_weights_by_forces(self):
        w = {10: 5.0, 11: 2.0, 12: 0.0}
        self.assertEqual(route_similarity({10: 4}, {10: 4, 12: 30}, w), 1.0)
        self.assertAlmostEqual(route_similarity({10: 4, 11: 2}, {10: 4}, w), 20 / 24)
        self.assertEqual(route_similarity({}, {}, w), 0.0)

    def test_total_mobs_sums_segments(self):
        self.assertEqual(total_mobs([Segment(1, 0, 1, mobs={10: 1}), Segment(2, 1, 2, mobs={10: 2, 11: 1})]),
                         {10: 3, 11: 1})

    def test_pace_excess_removes_overall_speed_gap(self):
        ours, ref = Segment(1, 0, 120_000), Segment(1, 0, 60_000)
        # 本场整体慢一倍：这一段也慢一倍，超额为 0
        self.assertEqual(pace_excess(ours, 1_200_000, ref, 600_000), 0)
        self.assertEqual(pace_excess(ours, 1_000_000, ref, 1_000_000), 60_000)


class WaveCostTests(unittest.TestCase):
    W = {10: 5.0, 11: 2.0, 12: 0.0}

    def test_costs_split_merged_waves_by_forces(self):
        ref = Segment(1, 0, 0, waves=[
            Wave(1, 0, 60_000, 0, None, {10: 2, 11: 5}),   # 合拉：10 号占 10/20 进度 → 30 秒 / 2 只
            Wave(2, 0, 20_000, 0, None, {11: 5, 12: 3}),   # 12 号不给进度，不分时间
            Wave(3, 0, 90_000, 1, True, {99: 1}),          # 首领波次不参与
        ])
        costs = mob_costs(ref, self.W)
        self.assertAlmostEqual(costs[10], 15_000)
        self.assertAlmostEqual(costs[11], 5_000)          # (30 + 20) 秒 / 10 只
        self.assertNotIn(12, costs)

        est, cov = wave_ref_time(Wave(9, 0, 50_000, 0, None, {10: 2}), costs, self.W)
        self.assertEqual((est, cov), (30_000, 1.0))
        # 参考没拉的怪按覆盖率放大
        est, cov = wave_ref_time(Wave(9, 0, 50_000, 0, None, {10: 2, 13: 10}), costs, {**self.W, 13: 1.0})
        self.assertAlmostEqual(cov, 0.5)
        self.assertAlmostEqual(est, 60_000)

    def test_repulled_wave_costs_nothing_in_reference(self):
        self.assertEqual(wave_ref_time(Wave(5, 0, 30_000, 0, None, {}, raw={11: 2}), {11: 5_000}, self.W), (0.0, 1.0))
        self.assertEqual(wave_ref_time(Wave(5, 0, 30_000, 0, None, {}, raw={12: 2}), {}, self.W), (None, 0.0))


class DangerTests(unittest.TestCase):
    def test_hp_points_use_target_resources_only(self):
        evs = [dict(timestamp=2, targetID=1, resourceActor=2, hitPoints=50, maxHitPoints=100),
               dict(timestamp=1, targetID=1, resourceActor=2, hitPoints=90, maxHitPoints=100),
               dict(timestamp=3, targetID=1, resourceActor=1, hitPoints=10, maxHitPoints=100),
               dict(timestamp=4, targetID=7, resourceActor=2, hitPoints=10, maxHitPoints=100),
               dict(timestamp=5, targetID=1, resourceActor=2, hitPoints=10, maxHitPoints=0)]
        self.assertEqual(hp_points(evs, [1]), {1: [(1.0, 90.0), (2.0, 50.0)]})

    def test_dips_track_lowest_point_recovery_and_merge_quick_redips(self):
        pts = [(0, 100), (1000, 30), (1500, 12), (2000, 60), (3000, 20), (4000, 80),
               (20_000, 40), (30_000, 10)]
        dips = find_dips(pts, threshold=35)
        # 2000 回到 60% 后 1 秒又跌破：合并成一次，最低 12%
        self.assertEqual(dips[0], (1000, 1500, 12, 4000))
        # 最后一段没回到 50%：结束 = 最后一个点
        self.assertEqual(dips[1], (30_000, 30_000, 10, 30_000))
        self.assertEqual(len(dips), 2)

    def test_team_moments_need_several_players_in_window(self):
        pts = {1: [(1000, 40)], 2: [(2500, 30)], 3: [(4000, 45)], 4: [(60_000, 10)], 5: [(61_000, 20)]}
        moments = team_moments(pts, below=50, need=3, window=4000)
        self.assertEqual(len(moments), 1)
        ts, who = moments[0]
        self.assertEqual(ts, 4000)
        self.assertEqual([p for p, _ in who], [2, 1, 3])


if __name__ == '__main__':
    unittest.main()
