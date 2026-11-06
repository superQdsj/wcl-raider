"""评分 v2 的离线测试（不访问网络）。"""
import json
import os
import tempfile
import unittest

from support import make_run  # noqa: F401  (同时把 scripts 目录加入 sys.path)

from wclr import cmd_score as sc
from wclr.api import WCLError


class WeightedTests(unittest.TestCase):
    def test_skips_na_and_reports_coverage(self):
        total, cov = sc.weighted({"a": 8.0, "b": None, "c": 6.0}, {"a": 0.5, "b": 0.3, "c": 0.2})
        self.assertAlmostEqual(total, (8.0 * 0.5 + 6.0 * 0.2) / 0.7)
        self.assertAlmostEqual(cov, 0.7)

    def test_all_na(self):
        total, cov = sc.weighted({"a": None}, {"a": 1.0})
        self.assertIsNone(total)
        self.assertEqual(cov, 0.0)

    def test_show_rounds_half_up(self):
        self.assertEqual(sc.show(7.45), "7.5")
        self.assertEqual(sc.show(None), "N/A")


class ClusterTests(unittest.TestCase):
    def test_cluster_positions(self):
        deaths = [{"timestamp": t} for t in (0, 10000, 25000, 60000)]
        self.assertEqual(sc._clusters(deaths), [(1, 1), (1, 2), (1, 3), (2, 1)])


class PerUseTests(unittest.TestCase):
    def test_per_use_only_for_few_hits_per_cast(self):
        self.assertTrue(sc._per_use_ok({"uses": 10, "hits": 20, "ticks": 0}))
        self.assertFalse(sc._per_use_ok({"uses": 1, "hits": 1074, "ticks": 0}))  # 光环反复命中
        self.assertFalse(sc._per_use_ok({"uses": 0, "hits": 5}))
        self.assertFalse(sc._per_use_ok(None))


class JudgmentTests(unittest.TestCase):
    def _write(self, obj):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))
        self.addCleanup(os.remove, path)
        return path

    def test_parse_avoidable_roles_and_ids(self):
        j = {"avoidable": [{"id": 123, "roles": ["dps", "bogus"], "evidence": "e"}, 456, {"id": "x"}]}
        got = sc._avoidable(j)
        self.assertEqual(set(got), {123, 456})
        self.assertEqual(got[123]["roles"], {"dps"})
        self.assertIsNone(got[456]["roles"])

    def test_parse_death_causes_ignores_unknown_values(self):
        j = {"deaths": {"1": {"cause": "personal", "evidence": "x"}, "2": "chain", "3": {"cause": "blame"}, "a": "chain"}}
        got = sc._death_causes(j)
        self.assertEqual(got, {1: ("personal", "x"), 2: ("chain", "")})

    def test_load_judgments_errors(self):
        self.assertEqual(sc.load_judgments(None), {})
        with self.assertRaises(WCLError):
            sc.load_judgments(self._write("not json"))
        with self.assertRaises(WCLError):
            sc.load_judgments(self._write([1, 2]))
        with self.assertRaises(WCLError):
            sc.load_judgments("/nonexistent/judgments.json")
        self.assertEqual(sc.load_judgments(self._write({"avoidable": []})), {"avoidable": []})


class PenaltyTableTests(unittest.TestCase):
    def test_death_penalties_are_ordered(self):
        p = sc.DEATH_PENALTY
        self.assertGreater(p["personal"], p["shared"])
        self.assertEqual(p["shared"], p["unknown"])
        self.assertEqual(p["chain"], 0.0)

    def test_weights_sum_to_one(self):
        for role, w in sc.WEIGHTS.items():
            self.assertAlmostEqual(sum(w.values()), 1.0, msg=role)
        self.assertAlmostEqual(sum(sc.TEAM_WEIGHTS.values()), 1.0)
        self.assertNotIn("output", sc.WEIGHTS["healer"])  # 治疗 HPS 不计分


if __name__ == "__main__":
    unittest.main()
