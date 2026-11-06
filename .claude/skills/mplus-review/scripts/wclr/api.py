"""Warcraft Logs v2 API 客户端：凭据、OAuth 令牌、GraphQL 请求、磁盘缓存、点数统计。

只依赖 Python 标准库。凭据查找顺序：
  1. 环境变量 WCL_CLIENT_ID / WCL_CLIENT_SECRET
  2. 当前目录下的 .env
  3. ~/.config/wcl-raider/credentials.env
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CONFIG_DIR = Path(os.environ.get("WCL_RAIDER_CONFIG_DIR") or (Path.home() / ".config" / "wcl-raider"))
CACHE_DIR = Path(os.environ.get("WCL_RAIDER_CACHE_DIR") or (Path.home() / ".cache" / "wcl-raider"))

# 语言即 API 主机：cn 主机会把技能/NPC/副本名翻译成中文（任何地区的日志都适用）
HOSTS = {"zh": "cn.warcraftlogs.com", "en": "www.warcraftlogs.com"}
TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
USER_AGENT = "wcl-raider-mplus-review/0.1"
RATE = "rateLimitData { limitPerHour pointsSpentThisHour pointsResetIn }"

HOUR = 3600
DAY = 24 * HOUR

SETUP_HELP = """未找到 Warcraft Logs API 凭据。

1. 打开 https://www.warcraftlogs.com/api/clients/ （需登录 WCL），点击 "Create Client"：
   名称随意，Redirect URL 填 http://localhost，不要勾选 Public Client。
2. 把得到的 Client ID / Client Secret 写入 ~/.config/wcl-raider/credentials.env：
       WCL_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
       WCL_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   （也可以用同名环境变量，或当前目录下的 .env 文件）
3. 运行 `python3 <skill>/scripts/wcl.py points` 验证。"""


class WCLError(RuntimeError):
    """面向用户的错误（消息已是中文说明）。"""


# ---------------------------------------------------------------- credentials

def _read_env_file(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        out[key] = val.strip().strip('"').strip("'")
    return out


def load_credentials() -> Tuple[str, str]:
    cid = (os.environ.get("WCL_CLIENT_ID") or "").strip()
    sec = (os.environ.get("WCL_CLIENT_SECRET") or "").strip()
    if cid and sec:
        return cid, sec
    for path in (Path.cwd() / ".env", CONFIG_DIR / "credentials.env"):
        vals = _read_env_file(path)
        if vals.get("WCL_CLIENT_ID") and vals.get("WCL_CLIENT_SECRET"):
            return vals["WCL_CLIENT_ID"], vals["WCL_CLIENT_SECRET"]
    raise WCLError(SETUP_HELP)


def default_lang() -> str:
    for source in (os.environ, _read_env_file(Path.cwd() / ".env"), _read_env_file(CONFIG_DIR / "credentials.env")):
        val = (source.get("WCL_LANG") or "").strip().lower()
        if val in HOSTS:
            return val
    return "zh"


# ---------------------------------------------------------------- files

def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(str(tmp), str(path))


def _cache_get(path: Path, ttl: float) -> Optional[Any]:
    try:
        if time.time() - path.stat().st_mtime > ttl:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _cache_put(path: Path, value: Any) -> None:
    try:
        _write_private(path, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    except OSError:
        pass  # 缓存写失败不影响功能


# ---------------------------------------------------------------- token

def get_token(force: bool = False) -> str:
    cid, sec = load_credentials()
    tag = hashlib.sha256(cid.encode()).hexdigest()[:16]
    path = CACHE_DIR / "token.json"
    if not force:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("client") == tag and cached.get("expires_at", 0) > time.time() + HOUR:
                return cached["access_token"]
        except (OSError, ValueError, KeyError):
            pass
    req = urllib.request.Request(
        TOKEN_URL,
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{cid}:{sec}".encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401):
            raise WCLError("WCL 凭据无效：Client ID / Secret 不正确，或该客户端已被删除。\n\n" + SETUP_HELP) from None
        raise WCLError(f"获取 WCL 访问令牌失败：HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise WCLError(f"无法连接 warcraftlogs.com：{getattr(exc, 'reason', exc)}") from None
    token = payload["access_token"]
    _write_private(path, json.dumps({
        "client": tag,
        "access_token": token,
        "expires_at": time.time() + float(payload.get("expires_in", HOUR)),
    }))
    return token


# ---------------------------------------------------------------- errors

_ERROR_HINTS = [
    ("permission", "无权查看该报告：它可能是私密报告（private）。只能分析公开或未列出（unlisted）的报告，请让上传者把报告改为公开/未列出。"),
    ("does not exist", "报告不存在：请检查链接或报告代码是否完整（16 位字母数字）。"),
    ("archived", "该报告已被 WCL 归档，事件/表格数据需要上传者有订阅才能访问。"),
]


def _explain(messages: str) -> str:
    low = messages.lower()
    for needle, hint in _ERROR_HINTS:
        if needle in low:
            return f"{hint}\n（WCL 原始错误：{messages}）"
    return f"WCL API 返回错误：{messages}"


# ---------------------------------------------------------------- client

class Client:
    """GraphQL 客户端，带磁盘缓存和点数统计。"""

    def __init__(self, lang: Optional[str] = None, refresh: bool = False):
        self.lang = lang if lang in HOSTS else default_lang()
        self.refresh = refresh
        self.live = 0
        self.cached = 0
        self.rate: Optional[Dict[str, Any]] = None
        self.last_age = 0.0  # 上一次 gql() 结果的缓存年龄（秒），实时请求为 0
        self._force_token = False
        self._lock = threading.Lock()
        self._reset_at = 0.0

    def _record_rate(self, rate: Optional[Dict[str, Any]]) -> None:
        if not rate:
            return
        reset_at = time.time() + (rate.get("pointsResetIn") or 0)
        with self._lock:
            # 并发响应可能乱序；同一小时保留已见的最大点数。
            if (self.rate is None or abs(reset_at - self._reset_at) > 120
                    or rate.get("pointsSpentThisHour", 0) >= self.rate.get("pointsSpentThisHour", 0)):
                self.rate = rate
                self._reset_at = reset_at

    @property
    def host(self) -> str:
        return HOSTS[self.lang]

    # -- public -----------------------------------------------------------
    def gql(self, query: str, variables: Optional[Dict[str, Any]] = None, *,
            lang: Optional[str] = None, ttl: float = 12 * HOUR, partial: bool = False) -> Dict[str, Any]:
        """执行 GraphQL 查询并返回 data。

        查询文本里应包含顶层 `rateLimitData`（用 api.RATE），以便统计点数。
        partial=True 时允许部分字段报错（批量别名查询中个别报告失效），错误放在 data["_errors"]。
        """
        host = HOSTS[lang] if lang in HOSTS else self.host
        variables = variables or {}
        key = hashlib.sha256(json.dumps([host, query, variables], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path = CACHE_DIR / "gql" / key[:2] / f"{key}.json"
        if ttl > 0 and not self.refresh:
            hit = _cache_get(path, ttl)
            if hit is not None and hit.get("_errors"):
                hit = None  # 旧版留下的部分错误缓存也不能当成完整数据复用
            if hit is not None:
                with self._lock:
                    self.cached += 1
                try:
                    self.last_age = time.time() - path.stat().st_mtime
                except OSError:
                    self.last_age = 0.0
                return hit
        with self._lock:
            self.live += 1
        data = self._post(host, query, variables, partial)
        self.last_age = 0.0
        rate = data.pop("rateLimitData", None)
        self._record_rate(rate)
        if ttl > 0 and not data.get("_errors"):
            _cache_put(path, data)
        return data

    def footer(self) -> str:
        parts = [f"WCL API：实时请求 {self.live} 次，缓存命中 {self.cached} 次"]
        if self.rate:
            spent = self.rate.get("pointsSpentThisHour")
            limit = self.rate.get("limitPerHour")
            reset = self.rate.get("pointsResetIn") or 0
            parts.append(f"本小时已用 {spent:.0f}/{limit} 点（{int(reset) // 60} 分钟后重置）")
        return "；".join(parts)

    # -- internals ----------------------------------------------------------
    def _post(self, host: str, query: str, variables: Dict[str, Any], partial: bool) -> Dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        last_exc: Optional[BaseException] = None
        for attempt in range(4):
            token = get_token(force=self._force_token)
            self._force_token = False
            req = urllib.request.Request(
                f"https://{host}/api/v2/client",
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 401 and attempt == 0:
                    self._force_token = True
                    continue
                if exc.code == 429:
                    raise WCLError(
                        "WCL API 点数已用完（该客户端每小时 1000 点）。请等待重置后再试；"
                        "已拉取过的数据会走缓存，不再消耗点数。") from None
                if exc.code >= 500 and attempt < 3:
                    last_exc = exc
                    time.sleep(2 * (attempt + 1))
                    continue
                detail = exc.read()[:300].decode("utf-8", "replace")
                raise WCLError(f"WCL API 请求失败：HTTP {exc.code} {detail}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_exc = exc
                if attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise WCLError(f"无法连接 {host}：{getattr(exc, 'reason', exc)}") from None
            errors = payload.get("errors") or []
            data = payload.get("data")
            self._record_rate((data or {}).get("rateLimitData"))
            if errors:
                messages = "; ".join(str(err.get("message", "")) for err in errors)
                if not partial or not data:
                    raise WCLError(_explain(messages))
                data["_errors"] = [str(err.get("message", "")) for err in errors]
            return data or {}
        raise WCLError(f"WCL API 请求多次失败：{last_exc}")


# ---------------------------------------------------------------- raider.io

def http_json(url: str, ttl: float = DAY) -> Optional[Any]:
    """GET 公共 JSON（Raider.IO 等），失败返回 None。"""
    key = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE_DIR / "http" / f"{key}.json"
    hit = _cache_get(path, ttl)
    if hit is not None:
        return hit
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            value = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
        return None
    _cache_put(path, value)
    return value


def rio_static_data(wcl_expansion_id: Optional[int]) -> List[Dict[str, Any]]:
    """Raider.IO 各赛季副本（含限时秒数）。WCL 资料片 ID + 4 = Raider.IO expansion_id（午夜：7 → 11）。"""
    candidates: List[int] = []
    if wcl_expansion_id is not None:
        candidates.append(int(wcl_expansion_id) + 4)
    candidates += [11, 12, 10]
    seen = set()
    dungeons: List[Dict[str, Any]] = []
    for exp in candidates:
        if exp in seen:
            continue
        seen.add(exp)
        data = http_json(f"https://raider.io/api/v1/mythic-plus/static-data?expansion_id={exp}")
        if not data:
            continue
        for season in data.get("seasons") or []:
            for d in season.get("dungeons") or []:
                dungeons.append(d)
        for d in data.get("dungeons") or []:
            dungeons.append(d)
    return dungeons


def stderr(msg: str) -> None:
    print(msg, file=sys.stderr)
