"""报告链接解析，以及一次大秘境记录（Run）的上下文：玩家、波次、技能名、计时等。"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import fmt
from .api import DAY, HOUR, RATE, Client, WCLError, http_json, rio_static_data

CODE_RE = re.compile(r"^(?:a:)?[A-Za-z0-9]{16}$")
REPORT_PATH_RE = re.compile(r"/reports?/((?:a:)?[A-Za-z0-9]{16})(?=/|$)(?:/(\d+))?")
CLASSIC_PREFIXES = ("classic.", "fresh.", "sod.", "vanilla.", "era.", "tbc.", "wotlk.", "cata.", "mop.")

# 已核实的词缀中文名（来自 Raider.IO 中文接口）；其余词缀会尝试从 Raider.IO 当周词缀补全
AFFIX_NAMES = {
    9: ("残暴", "Tyrannical"),
    10: ("强韧", "Fortified"),
    147: ("萨拉塔斯的狡诈", "Xal'atath's Guile"),
    162: ("萨拉塔斯的交易：脉冲", "Xal'atath's Bargain: Pulsar"),
}

DEATH_PENALTY_AFFIXES = {147, 152}  # 狡诈 / 挑战者的危境：每次死亡 15 秒
NO_PENALTY_AFFIX = 165  # 午夜 S2 的 +2–+5 词缀，死亡不罚时（数据反推）
COUNTDOWN_MS = 10000  # WCL 战斗从插入钥石开始，游戏内计时在 10 秒倒计时后开始


def parse_ref(ref: str) -> Tuple[str, Optional[str]]:
    """从 WCL / WoWAnalyzer 链接或裸代码中提取 (报告代码, fight 参数)。"""
    text = (ref or "").strip().strip("<>").strip()
    if not text:
        raise WCLError("请提供 Warcraft Logs 报告链接或 16 位报告代码。")
    if CODE_RE.match(text):
        return text, None
    m = re.match(r"^((?:a:)?[A-Za-z0-9]{16})#(?:fight=)?(\d+|last)$", text)
    if m:
        return m.group(1), m.group(2)
    try:
        url = urllib.parse.urlparse(text if "://" in text else "https://" + text)
        host = (url.hostname or "").lower()
    except ValueError:
        raise WCLError("报告链接格式无效。") from None
    if any(host.startswith(p) for p in CLASSIC_PREFIXES):
        raise WCLError(f"{host} 是经典怀旧服的日志站点，经典服没有大秘境，本工具只支持正式服日志。")
    if host not in ("warcraftlogs.com", "www.warcraftlogs.com", "cn.warcraftlogs.com",
                    "wowanalyzer.com", "www.wowanalyzer.com"):
        raise WCLError("请使用正式服 Warcraft Logs 或 WoWAnalyzer 报告链接。")
    match = REPORT_PATH_RE.search(url.path)
    if not match:
        raise WCLError(f"无法从链接中识别报告代码：{text}\n示例：https://www.warcraftlogs.com/reports/AbCdEf1234567890#fight=5")
    code, path_fight = match.group(1), match.group(2)
    fight: Optional[str] = None
    for part in (url.query, url.fragment):
        qs = urllib.parse.parse_qs(part)
        if qs.get("fight"):
            fight = qs["fight"][0]
    if fight is None and path_fight:
        fight = path_fight  # wowanalyzer.com/report/CODE/12-...
    return code, fight


@dataclass
class Player:
    id: int
    name: str
    server: str
    cls: str
    spec: str
    role: str  # tank / healer / dps / unknown
    ilvl: Optional[float] = None
    potions: int = 0
    healthstones: int = 0
    pets: List[int] = field(default_factory=list)

    @property
    def spec_zh(self) -> str:
        return fmt.class_spec(self.cls, self.spec)

    @property
    def label(self) -> str:
        return f"{self.name}({self.spec_zh})"


@dataclass
class Pull:
    idx: int
    id: int
    name: str
    encounter_id: int
    start: float
    end: float
    kill: Optional[bool]
    mobs: List[Tuple[str, int]]
    forces: float
    boss_names: List[str]

    @property
    def dur(self) -> float:
        return self.end - self.start

    @property
    def is_boss(self) -> bool:
        return self.encounter_id > 0


Q_META = """query($code: String!) {
  reportData { report(code: $code) {
    code title startTime endTime visibility
    region { slug name }
    zone { id name expansion { id name } }
    masterData { lang
      actors { id name type subType server petOwner gameID }
      abilities { gameID name icon type } }
    fights { id name encounterID difficulty kill startTime endTime keystoneLevel keystoneAffixes
      keystoneBonus keystoneTime rating averageItemLevel countReached countRequired inProgress }
  } }
  %s
}""" % RATE

Q_FIGHT_EN = """query($code: String!, $fid: [Int]!) {
  reportData { report(code: $code) { fights(fightIDs: $fid) { id name } } }
  %s
}""" % RATE

Q_FIGHT = """query($code: String!, $fid: [Int]!) {
  reportData { report(code: $code) {
    fights(fightIDs: $fid) { id npcCountMap friendlyPlayers gameZone { id name }
      dungeonPulls { id name encounterID kill startTime endTime
        enemyNPCs { id gameID minimumInstanceID maximumInstanceID } } }
    summary: table(dataType: Summary, fightIDs: $fid)
  } }
  %s
}""" % RATE


def is_mplus(fight: Dict[str, Any]) -> bool:
    return fight.get("difficulty") == 10 and (fight.get("keystoneLevel") or 0) > 0


def result_label(fight: Dict[str, Any]) -> str:
    bonus = fight.get("keystoneBonus") or 0
    if fight.get("kill"):
        return f"限时 +{bonus}" if bonus >= 1 else "超时完成"
    return "未完成"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


class Run:
    """一次大秘境记录的上下文。时间戳均为报告相对毫秒；对外展示用 t() 转为相对钥石开始的 m:ss。"""

    def __init__(self, client: Client, code: str, meta: Dict[str, Any], fight: Dict[str, Any],
                 ttl: float, dungeon_en: Optional[str], detail: Dict[str, Any]):
        self.client = client
        self.code = code
        self.ttl = ttl
        self.report = meta
        self.fight = fight
        self.fight_id: int = fight["id"]
        self.mplus_fights = [f for f in meta.get("fights") or [] if is_mplus(f)]
        self.start: float = fight["startTime"]
        self.end: float = fight["endTime"]
        self.duration: float = self.end - self.start
        self.level: int = fight.get("keystoneLevel") or 0
        self.affixes: List[int] = fight.get("keystoneAffixes") or []
        self.bonus: int = fight.get("keystoneBonus") or 0
        self.keystone_time: Optional[int] = fight.get("keystoneTime")
        self.kill: bool = bool(fight.get("kill"))
        self.dungeon: str = fight.get("name") or "?"
        self.dungeon_en: str = dungeon_en or self.dungeon
        self.encounter_id: int = fight.get("encounterID") or 0
        md = meta.get("masterData") or {}
        self.lang_src: str = md.get("lang") or "?"
        self.actors: Dict[int, Dict[str, Any]] = {a["id"]: a for a in md.get("actors") or []}
        self.abilities: Dict[int, Dict[str, Any]] = {int(a["gameID"]): a for a in md.get("abilities") or []}
        fd = (detail.get("fights") or [{}])[0]
        self.npc_count: Dict[str, float] = fd.get("npcCountMap") or {}
        self.summary: Dict[str, Any] = (detail.get("summary") or {}).get("data") or {}
        self.players: Dict[int, Player] = self._players(fd.get("friendlyPlayers") or [])
        self.pet_owner: Dict[int, int] = {}
        for actor in self.actors.values():
            owner = actor.get("petOwner")
            if actor.get("type") == "Pet" and owner in self.players:
                self.pet_owner[actor["id"]] = owner
                self.players[owner].pets.append(actor["id"])
        self.raw_pulls: List[Dict[str, Any]] = fd.get("dungeonPulls") or []
        self.pulls: List[Pull] = self._pulls(self.raw_pulls)
        self._timer: Optional[int] = None
        self._timer_loaded = False

    # ------------------------------------------------------------ building
    def _players(self, friendly_ids: List[int]) -> Dict[int, Player]:
        out: Dict[int, Player] = {}
        details = self.summary.get("playerDetails") or {}
        for role_key, role in (("tanks", "tank"), ("healers", "healer"), ("dps", "dps")):
            for p in details.get(role_key) or []:
                specs = p.get("specs") or []
                spec = specs[0] if specs and isinstance(specs[0], str) else (specs[0].get("spec") if specs else "")
                if not spec and p.get("icon") and "-" in p["icon"]:
                    spec = p["icon"].split("-", 1)[1]
                out[p["id"]] = Player(
                    id=p["id"], name=p.get("name") or "?", server=p.get("server") or "",
                    cls=p.get("type") or "", spec=spec or "", role=role,
                    ilvl=p.get("maxItemLevel") or p.get("minItemLevel"),
                    potions=p.get("potionUse") or 0, healthstones=p.get("healthstoneUse") or 0,
                )
        for pid in friendly_ids:  # 极少数情况下 playerDetails 缺人
            if pid not in out and pid in self.actors and self.actors[pid].get("type") == "Player":
                a = self.actors[pid]
                out[pid] = Player(id=pid, name=a.get("name") or "?", server=a.get("server") or "",
                                  cls=a.get("subType") or "", spec="", role="unknown")
        order = {"tank": 0, "healer": 1, "dps": 2}
        return dict(sorted(out.items(), key=lambda kv: (order.get(kv[1].role, 3), kv[1].name)))

    def _pulls(self, raw: List[Dict[str, Any]]) -> List[Pull]:
        pulls: List[Pull] = []
        for p in raw:
            if p["endTime"] - p["startTime"] < 1000:
                continue  # WCL 偶尔在结尾生成 0.1 秒的伪波次
            counts: Dict[str, int] = {}
            forces = 0.0
            bosses: List[str] = []
            for npc in p.get("enemyNPCs") or []:
                actor = self.actors.get(npc.get("id"), {})
                name = actor.get("name") or f"NPC{npc.get('gameID')}"
                lo, hi = npc.get("minimumInstanceID") or 1, npc.get("maximumInstanceID") or 1
                n = max(1, hi - lo + 1)
                counts[name] = counts.get(name, 0) + n
                forces += float(self.npc_count.get(str(npc.get("gameID")), 0) or 0) * n
                if actor.get("subType") == "Boss" and name not in bosses:
                    bosses.append(name)
            mobs = sorted(counts.items(), key=lambda kv: -kv[1])
            pulls.append(Pull(idx=len(pulls) + 1, id=p["id"], name=p.get("name") or "?",
                              encounter_id=p.get("encounterID") or 0, start=p["startTime"], end=p["endTime"],
                              kill=p.get("kill"), mobs=mobs, forces=forces, boss_names=bosses))
        return pulls

    # ------------------------------------------------------------ helpers
    @property
    def url(self) -> str:
        return f"https://www.warcraftlogs.com/reports/{self.code}#fight={self.fight_id}"

    @property
    def result(self) -> str:
        return result_label(self.fight)

    def rel(self, ts: float) -> float:
        return ts - self.start

    def t(self, ts: Optional[float], precise: bool = False) -> str:
        return fmt.clock(None if ts is None else ts - self.start, precise)

    def pull_of(self, ts: float, slack: float = 3000) -> Optional[Pull]:
        exact = [p for p in self.pulls if p.start <= ts <= p.end]
        if exact:
            return max(exact, key=lambda p: p.start)
        nearby = [p for p in self.pulls if p.start - 500 <= ts <= p.end + slack]
        return min(nearby, key=lambda p: min(abs(ts - p.start), abs(ts - p.end))) if nearby else None

    def pull_tag(self, ts: float) -> str:
        p = self.pull_of(ts)
        if p:
            return f"#{p.idx}"
        prev = [q for q in self.pulls if q.end < ts]
        return f"#{prev[-1].idx}后间隔" if prev else "开怪前"

    def pull_desc(self, p: Pull, mobs: int = 3) -> str:
        if p.is_boss:
            boss = "、".join(p.boss_names) or p.name
            return f"首领 {boss}" + ("" if p.kill else "（未击杀）")
        parts = [f"{n}×{c}" for n, c in p.mobs[:mobs]]
        if len(p.mobs) > mobs:
            parts.append(f"+{len(p.mobs) - mobs}种")
        return "小怪 " + " ".join(parts)

    def ab(self, gid: Any) -> str:
        try:
            gid = int(gid)
        except (TypeError, ValueError):
            return f"技能{gid}"
        if gid == 1:
            return "近战"
        a = self.abilities.get(gid)
        return (a or {}).get("name") or f"技能{gid}"

    def actor_name(self, aid: Optional[int], inst: Optional[int] = None) -> str:
        if aid is None or aid == -1:
            return "环境"
        if aid in self.players:
            return self.players[aid].name
        a = self.actors.get(aid)
        if not a:
            return f"#{aid}"
        name = a.get("name") or f"#{aid}"
        if a.get("type") == "Pet" and a.get("petOwner") in self.players:
            return f"{name}[{self.players[a['petOwner']].name}的宠物]"
        if inst and a.get("type") == "NPC":
            return f"{name}#{inst}"
        return name

    def owner(self, aid: int) -> Optional[int]:
        if aid in self.players:
            return aid
        return self.pet_owner.get(aid)

    def find_player(self, query: str) -> Player:
        q = (query or "").strip()
        if not q:
            raise WCLError("请指定玩家名。")
        players = list(self.players.values())
        role_words = {"tank": "tank", "t": "tank", "坦克": "tank", "坦": "tank",
                      "healer": "healer", "heal": "healer", "治疗": "healer", "奶": "healer", "n": "healer"}
        if q.lower() in role_words:
            hits = [p for p in players if p.role == role_words[q.lower()]]
            if len(hits) == 1:
                return hits[0]
        for test in (lambda p: p.name == q,
                     lambda p: p.name.lower() == q.lower(),
                     lambda p: p.name.lower().startswith(q.lower()),
                     lambda p: q.lower() in p.name.lower(),
                     lambda p: q.lower() in (p.spec + p.cls).lower() or q in p.spec_zh):
            hits = [p for p in players if test(p)]
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                raise WCLError(f"玩家名 '{q}' 不唯一：" + "、".join(p.label for p in hits))
        raise WCLError(f"找不到玩家 '{q}'。本场队员：" + "、".join(p.label for p in players))

    def combat_ms(self) -> float:
        total, cur_s, cur_e = 0.0, None, None
        for p in sorted(self.pulls, key=lambda x: x.start):
            if cur_e is None or p.start > cur_e:
                if cur_e is not None:
                    total += cur_e - cur_s
                cur_s, cur_e = p.start, p.end
            else:
                cur_e = max(cur_e, p.end)
        if cur_e is not None:
            total += cur_e - cur_s
        return total

    def affix_names(self) -> List[str]:
        names = dict(AFFIX_NAMES)
        unknown = [a for a in self.affixes if a not in names]
        if unknown:
            for region in ("us", "eu", "cn"):
                data = http_json(f"https://raider.io/api/v1/mythic-plus/affixes?region={region}&locale=cn", ttl=DAY) or {}
                for a in data.get("affix_details") or []:
                    names.setdefault(a.get("id"), (a.get("name"), a.get("name")))
        return [f"{names[a][0]}({a})" if a in names else f"词缀{a}" for a in self.affixes]

    def timer_ms(self) -> Optional[int]:
        """限时（毫秒），来自 Raider.IO 静态数据，按英文副本名匹配。"""
        if self._timer_loaded:
            return self._timer
        self._timer_loaded = True
        exp = ((self.report.get("zone") or {}).get("expansion") or {}).get("id")
        want = _norm(self.dungeon_en)
        for d in rio_static_data(exp):
            if want and (_norm(d.get("name", "")) == want or _norm(d.get("short_name", "")) == want):
                secs = d.get("keystone_timer_seconds")
                if secs:
                    self._timer = int(secs) * 1000
                    break
        return self._timer

    def death_penalty(self, deaths: int) -> Tuple[int, str]:
        """估计每次死亡的罚时（毫秒）。优先用官方计时与实际时长反推，其次看词缀。"""
        if self.kill and self.keystone_time and deaths > 0:
            est = (self.keystone_time - (self.duration - COUNTDOWN_MS)) / deaths
            rounded = int(round(est / 5000.0)) * 5000
            if 0 <= rounded <= 30000 and abs(est - rounded) <= 2500:
                return rounded, "由官方计时与实际时长反推"
        # 午夜 S2 实测（各层 8–10 场带死亡记录反推）：+2–+5（带 165 号词缀）0 秒；+6–+11 5 秒；+12 起（147 狡诈）15 秒
        if DEATH_PENALTY_AFFIXES & set(self.affixes):
            return 15000, "按词缀推断（萨拉塔斯的狡诈：15 秒）"
        if NO_PENALTY_AFFIX in self.affixes or (0 < self.level <= 5):
            return 0, "按层数/词缀推断（+2–+5 死亡不罚时）"
        return 5000, "按层数推断（+6–+11：5 秒）"

    def player_deaths(self) -> List[Dict[str, Any]]:
        """Summary 表中的玩家死亡（deathTime 为相对战斗开始的毫秒）。"""
        out = []
        for d in self.summary.get("deathEvents") or []:
            if d.get("id") in self.players:
                out.append(d)
        return sorted(out, key=lambda d: d.get("deathTime") or 0)

    def header(self) -> str:
        region = (self.report.get("region") or {}).get("slug") or "?"
        when = time.strftime("%Y-%m-%d", time.localtime((self.report.get("startTime") or 0) / 1000))
        name = self.dungeon if self.dungeon == self.dungeon_en else f"{self.dungeon} {self.dungeon_en}"
        return (f"{name} +{self.level} · {self.result} · 报告 {self.code} fight {self.fight_id} · "
                f"{region} · {when}")

    def prior_attempts(self) -> List[Dict[str, Any]]:
        """同一份报告里、这一把之前的同副本记录（任何层数、任何结果），按时间顺序。"""
        return [f for f in self.mplus_fights
                if f.get("encounterID") == self.encounter_id and f["startTime"] < self.fight["startTime"]]

    def prior_attempts_note(self) -> List[str]:
        prior = self.prior_attempts()
        if not prior:
            return []
        same = [f for f in prior if f.get("keystoneLevel") == self.level]
        failed = [f for f in same if not f.get("kill")]
        out = [f"- 这一把之前，本报告里同副本还有 {len(prior)} 条记录"
               + (f"（同层 +{self.level} 的 {len(same)} 条里 {len(failed)} 条没打完）" if same else "") + "："]
        for f in prior:
            dur = f["endTime"] - f["startTime"]
            req, got = f.get("countRequired"), f.get("countReached")
            out.append(f"  - fight {f['id']} +{f.get('keystoneLevel')} {result_label(f)}，"
                       f"{fmt.clock(f.get('keystoneTime'), True) if f.get('kill') and f.get('keystoneTime') else fmt.clock(dur) + '（实际）'}"
                       + (f"，进度 {fmt.pct(got, req, 1)}" if req else ""))
        if failed:
            out.append(f"- 同一把钥石连续 {len(failed)} 次没打完才打出这一把：复盘时要讲这件事（之前倒在哪里、这把是不是还在同一处险些出事）。"
                       f"用 `wcl pulls <链接> --fight N` 看之前那几次停在哪一波。")
        return out

    def other_runs_note(self) -> str:
        if len(self.mplus_fights) <= 1:
            return ""
        return (f"（该报告共有 {len(self.mplus_fights)} 条大秘境记录，当前为 fight {self.fight_id}；"
                f"用 `runs` 查看全部，用 --fight N 指定）")


def load_meta(client: Client, code: str) -> Tuple[Dict[str, Any], float]:
    data = client.gql(Q_META, {"code": code}, ttl=DAY)
    report = (data.get("reportData") or {}).get("report")
    if not report:
        raise WCLError(f"报告 {code} 不存在或无权访问。")
    ttl = DAY
    end = report.get("endTime") or 0
    live = any(f.get("inProgress") for f in report.get("fights") or [])
    if live or (time.time() * 1000 - end) < 3 * HOUR * 1000:
        ttl = 300.0  # 刚上传或仍在实时记录的报告：缓存只保留 5 分钟
        if client.last_age > ttl:
            data = client.gql(Q_META, {"code": code}, ttl=ttl)
            report = data["reportData"]["report"]
    return report, ttl


def select_fight(meta: Dict[str, Any], hint: Optional[str]) -> Dict[str, Any]:
    fights = meta.get("fights") or []
    mplus = [f for f in fights if is_mplus(f)]
    if hint:
        h = str(hint).strip().lower()
        if h == "last":
            if not mplus:
                raise WCLError("该报告里没有大秘境记录。")
            return mplus[-1]
        try:
            fid = int(h)
        except ValueError:
            raise WCLError(f"无效的 fight 参数：{hint}") from None
        for f in fights:
            if f["id"] == fid:
                if not is_mplus(f):
                    raise WCLError(f"fight {fid}（{f.get('name')}）不是大秘境记录。用 `runs` 查看报告中的大秘境。")
                return f
        raise WCLError(f"报告中没有 fight {fid}。用 `runs` 查看可选记录。")
    if not mplus:
        raise WCLError("该报告里没有大秘境记录（只支持正式服大秘境日志）。")
    done = [f for f in mplus if f.get("kill")]
    return (done or mplus)[-1]


def load_run(client: Client, ref: str, fight: Optional[str] = None) -> Run:
    code, hint = parse_ref(ref)
    meta, ttl = load_meta(client, code)
    chosen = select_fight(meta, fight if fight is not None else hint)
    fid = chosen["id"]
    variables = {"code": code, "fid": [fid]}
    detail = (client.gql(Q_FIGHT, variables, ttl=ttl).get("reportData") or {}).get("report") or {}
    dungeon_en = None
    if client.lang != "en":
        en_ttl = 7 * DAY if ttl >= DAY else ttl
        en = (client.gql(Q_FIGHT_EN, variables, lang="en", ttl=en_ttl).get("reportData") or {}).get("report") or {}
        names = {f["id"]: f.get("name") for f in en.get("fights") or []}
        dungeon_en = names.get(fid)
    return Run(client, code, meta, chosen, ttl, dungeon_en, detail)


def report_q(fields: str, extra_vars: str = "") -> str:
    """构造 report 级查询：变量 $code、$fid 固定可用。"""
    return ("query($code: String!, $fid: [Int]!%s) {\n  reportData { report(code: $code) {\n%s\n  } }\n  %s\n}"
            % (extra_vars, fields, RATE))


def fetch(run: Run, fields: str, extra: Optional[Dict[str, Any]] = None, extra_vars: str = "",
          partial: bool = False) -> Dict[str, Any]:
    """在当前 run 的报告上执行字段查询（自动带上 $code/$fid）。"""
    variables = {"code": run.code, "fid": [run.fight_id]}
    variables.update(extra or {})
    data = run.client.gql(report_q(fields, extra_vars), variables, ttl=run.ttl, partial=partial)
    report = (data.get("reportData") or {}).get("report") or {}
    if data.get("_errors"):
        report["_errors"] = data["_errors"]
    return report


def table_data(obj: Any) -> Dict[str, Any]:
    """table(...) 字段返回 {"data": {...}}，取出内部 data。"""
    if isinstance(obj, dict):
        inner = obj.get("data")
        if isinstance(inner, dict):
            return inner
        return obj
    return {}


def esc(name: str) -> str:
    """用于 WCL filterExpression 的字符串转义。"""
    return (name or "").replace("\\", "\\\\").replace('"', '\\"')
