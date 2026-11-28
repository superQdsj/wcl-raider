"""v1 限流（HTTP 429）等待重试。离线，不联网。"""
import io
import json
import unittest
import urllib.error
from unittest import mock

import support  # noqa: F401  （把 guides/tools 加进 sys.path，并隔离缓存）
from wclr import api


def _http_429(headers=None):
    return urllib.error.HTTPError("u", 429, "Too Many Requests", headers or {}, io.BytesIO(b""))


class _Resp:
    headers = {}

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class V1RateLimitTest(unittest.TestCase):
    def setUp(self):
        self.client = api.Client.__new__(api.Client)
        self.client._lock = mock.MagicMock()
        self.client.v1_rate = None
        p = mock.patch.object(api, "load_v1_key", return_value="k")
        p.start()
        self.addCleanup(p.stop)

    def test_waits_then_succeeds_without_using_retry_budget(self):
        seq = [_http_429({"Retry-After": "5"})] * 5 + [_Resp(json.dumps({"ok": 1}).encode())]

        def fake(req, timeout):
            r = seq.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(api.urllib.request, "urlopen", side_effect=fake), \
                mock.patch.object(api.time, "sleep") as sl:
            out = self.client._v1_fetch("h", "report/x", {})
        self.assertEqual(out, {"ok": 1})
        self.assertEqual([c.args[0] for c in sl.call_args_list], [6.0] * 5)

    def test_gives_up_after_max_wait(self):
        with mock.patch.object(api, "V1_429_MAX_WAIT", 120.0), \
                mock.patch.object(api.urllib.request, "urlopen", side_effect=lambda *a, **k: (_ for _ in ()).throw(_http_429())), \
                mock.patch.object(api.time, "sleep") as sl:
            with self.assertRaises(api.WCLError):
                self.client._v1_fetch("h", "report/x", {})
        self.assertEqual(sum(c.args[0] for c in sl.call_args_list), 120.0)

    def test_delay_parsing(self):
        self.assertEqual(api._v1_429_delay({}, 0), 60.0)
        self.assertEqual(api._v1_429_delay({"Retry-After": "10"}, 0), 11.0)
        self.assertIsNone(api._v1_429_delay({}, api.V1_429_MAX_WAIT))


if __name__ == "__main__":
    unittest.main()
