"""ability 命令：给一个敌方技能画像——它点谁、能不能打断/驱散、减益多久、是单体还是群体、死过几个人。

技能的作用不能靠记忆猜。这里用两个来源：
1. 日志统计（本场 + 和 splits 同一批参考记录）：实际发生了什么。高分队伍怎么处理它，就是最可靠的"机制说明"。
2. Wowhead 的技能说明原文：解释为什么（伤害方式、移除后的效果等）。新技能的说明可能不全；和日志冲突时以日志为准。
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from . import data, fmt
from .api import WCLError, http_json
from .cmd_events import _ability_ids
from .context import Run, load_run

ROLE_ZH = {"tank": "坦克", "healer": "治疗", "dps": "输出", "unknown": "未知"}


@dataclass
class Profile:
    label: str
    casts: int = 0               # 敌方施放（cast 事件）
    begins: int = 0              # 敌方读条（begincast 事件）
    interrupted: int = 0
    debuffs: int = 0             # 玩家获得减益的次数
    debuff_roles: Dict[str, int] = field(default_factory=dict)
    debuff_targets: Dict[str, int] = field(default_factory=dict)
    durations: List[float] = field(default_factory=list)   # 秒
    dispelled: int = 0
    hits: int = 0
    damage: float = 0.0
    hit_roles: Dict[str, int] = field(default_factory=dict)
    hit_bursts: List[int] = field(default_factory=list)     # 同一时刻（1 秒内）被同一技能打中的人数
    kills: int = 0
    kill_names: List[str] = field(default_factory=list)


def _role(run: Run, pid: Optional[int]) -> Tuple[str, str]:
    p = run.players.get(pid) if pid is not None else None
    if not p:
        return "", ""
    return p.name, ROLE_ZH.get(p.role, p.role)


def profile_run(run: Run, ids: Set[int], label: str) -> Profile:
    id_list = ", ".join(str(i) for i in sorted(ids))
    expr = f"ability.id in ({id_list})"
    got = data.parallel({
        "casts": lambda: data.events(run, data_type="Casts", hostility="Enemies", expr=expr, limit=3000)[0],
        "debuffs": lambda: data.events(run, data_type="Debuffs", expr=expr, limit=3000)[0],
        "damage": lambda: data.events(run, data_type="DamageTaken", expr=expr, limit=5000)[0],
        "interrupts": lambda: data.events(run, data_type="Interrupts", limit=3000)[0],
        "dispels": lambda: data.events(run, data_type="Dispels", limit=3000)[0],
        "deaths": lambda: data.events(run, data_type="Deaths", limit=500)[0],
    })
    pr = Profile(label=label)
    for e in got["casts"]:
        if e.get("type") == "cast":
            pr.casts += 1
        elif e.get("type") == "begincast":
            pr.begins += 1
    pr.interrupted = sum(1 for e in got["interrupts"]
                         if e.get("type") == "interrupt" and int(e.get("extraAbilityGameID") or 0) in ids)
    pr.dispelled = sum(1 for e in got["dispels"]
                       if e.get("type") == "dispel" and int(e.get("extraAbilityGameID") or 0) in ids)
    open_: Dict[Tuple[int, int], float] = {}
    for e in sorted(got["debuffs"], key=lambda e: e["timestamp"]):
        tid = e.get("targetID")
        if tid not in run.players:
            continue
        key = (tid, int(e.get("abilityGameID") or 0))
        if e.get("type") == "applydebuff":
            name, role = _role(run, tid)
            pr.debuffs += 1
            pr.debuff_roles[role] = pr.debuff_roles.get(role, 0) + 1
            pr.debuff_targets[name] = pr.debuff_targets.get(name, 0) + 1
            open_[key] = e["timestamp"]
        elif e.get("type") == "removedebuff" and key in open_:
            pr.durations.append((e["timestamp"] - open_.pop(key)) / 1000.0)
    bursts: Dict[int, Set[int]] = {}
    for e in got["damage"]:
        tid = e.get("targetID")
        if e.get("type") != "damage" or tid not in run.players:
            continue
        pr.hits += 1
        pr.damage += (e.get("amount") or 0) + (e.get("absorbed") or 0)
        _, role = _role(run, tid)
        pr.hit_roles[role] = pr.hit_roles.get(role, 0) + 1
        if not e.get("tick"):
            bursts.setdefault(int(e["timestamp"] // 1000), set()).add(tid)
    pr.hit_bursts = [len(v) for v in bursts.values()]
    for e in got["deaths"]:
        if e.get("type") == "death" and e.get("targetID") in run.players \
                and int(e.get("killingAbilityGameID") or 0) in ids:
            pr.kills += 1
            pr.kill_names.append(_role(run, e.get("targetID"))[0])
    return pr


# ---------------------------------------------------------------- Wowhead

def _strip(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text or "")
    text = re.sub(r"<!--.*?-->", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def wowhead_text(spell_id: int, lang: str = "zh") -> Optional[Tuple[str, str]]:
    """Wowhead 技能说明 (名称, 正文)。拿不到返回 None。"""
    locale = 4 if lang == "zh" else 0
    d = http_json(f"https://nether.wowhead.com/tooltip/spell/{spell_id}?dataEnv=1&locale={locale}", ttl=7 * 86400)
    if not d or not d.get("tooltip"):
        return None
    body = _strip(d["tooltip"])
    buff = _strip(d.get("buff") or "")
    if buff and buff not in body:
        body += "\n（减益/增益说明）" + buff
    return d.get("name") or str(spell_id), body


# ---------------------------------------------------------------- 画像结论

def summarize(profiles: Sequence[Profile]) -> List[str]:
    """跨记录汇总成几条客观画像。每条都写出依据的次数。"""
    out: List[str] = []
    roles: Dict[str, int] = {}
    for p in profiles:
        for r, n in p.debuff_roles.items():
            roles[r] = roles.get(r, 0) + n
    total = sum(roles.values())
    if total:
        top_role, top_n = max(roles.items(), key=lambda kv: kv[1])
        dist = "、".join(f"{r} {n}" for r, n in sorted(roles.items(), key=lambda kv: -kv[1]))
        if top_n / total >= 0.9 and total >= 4:
            out.append(f"**点名对象：只点{top_role}**（所有记录合计 {top_n}/{total} 次落在{top_role}身上）。")
        else:
            out.append(f"点名对象：{dist}（共 {total} 次），没有固定职责。")
    casts = sum(p.casts + p.begins for p in profiles)
    intr = sum(p.interrupted for p in profiles)
    begins = sum(p.begins for p in profiles)
    if begins or intr:
        if intr == 0:
            out.append(f"打断：所有记录里有 {begins} 次读条，**0 次被打断** → 很可能不能打断（或者高分队伍都不断）。")
        else:
            out.append(f"打断：所有记录合计读条 {begins} 次，被打断 {intr} 次 → 可以打断。")
    elif casts:
        out.append(f"打断：没有读条事件（{casts} 次都是瞬发施放），不能靠打断处理。")
    debuffs = sum(p.debuffs for p in profiles)
    disp = sum(p.dispelled for p in profiles)
    if debuffs:
        if disp == 0:
            out.append(f"驱散：所有记录里 {debuffs} 次减益，**0 次被驱散** → 很可能不能驱散（或者高分队伍都不驱散）。")
        else:
            out.append(f"驱散：{debuffs} 次减益里有 {disp} 次被驱散 → 可以驱散。")
        durs = [d for p in profiles for d in p.durations]
        if durs:
            med = fmt.median(durs) or 0
            full = sum(1 for d in durs if d >= med - 0.3)
            out.append(f"减益持续：中位 {med:.1f} 秒，{full}/{len(durs)} 次持续满时长 → "
                       + ("基本没人提前解掉，只能硬扛到结束。" if full / len(durs) >= 0.9 else "有一部分被提前解掉了。"))
    bursts = [b for p in profiles for b in p.hit_bursts]
    if bursts:
        med_b = fmt.median(bursts) or 0
        out.append(f"伤害形态：实际每次命中中位 {med_b:g} 人 → " + ("实战中基本只打到一个人"
                   "（说明里如果写了范围伤害，说明队伍站开了）。" if med_b <= 1.5 else "群体伤害，会波及周围的人。"))
    if len(profiles) > 1:
        ours, refs = profiles[0], profiles[1:]
        ref_kills = sum(p.kills for p in refs)
        out.append(f"致死：本场 {ours.kills} 次" + (f"（{'、'.join(ours.kill_names)}）" if ours.kill_names else "")
                   + f"；参考 {len(refs)} 场合计 {ref_kills} 次。"
                   + (" 参考吃了同样的技能却没人死：去看参考在这几秒里做了什么（减伤、站位、治疗）。"
                      if ours.kills and not ref_kills and sum(p.debuffs + p.hits for p in refs) else ""))
    return out


def cmd_ability(run: Run, query: str, refs: int = 3, explicit: Optional[List[str]] = None,
                web: bool = True) -> str:
    ids = set(_ability_ids(run, query))
    names = sorted({run.ab(i) for i in ids})
    lines = [f"# 技能画像：{'、'.join(names)}（{', '.join(str(i) for i in sorted(ids))}）— {run.header()}"]

    from .cmd_splits import pick_refs
    chosen, _, note, _ = pick_refs(run, refs=refs, explicit=explicit)
    ref_runs: List[Tuple[str, Run]] = []
    failed: List[str] = []
    for r in chosen:
        try:
            ref_runs.append((r.label, load_run(run.client, r.code, str(r.fid))))
        except WCLError as exc:
            failed.append(f"{r.label}（{exc}）")
    profiles = [profile_run(run, ids, "本场")]
    for label, rr in ref_runs:
        # 参考记录里可能出现本场没有的同名技能 ID（同一技能的施放/减益/伤害往往是不同 ID）
        extra = {gid for gid, a in rr.abilities.items() if (a.get("name") or "") in names}
        profiles.append(profile_run(rr, ids | extra, f"参考 {label}"))

    rows = []
    for p in profiles:
        dur = fmt.median(p.durations)
        rows.append([p.label, p.casts + p.begins, f"{p.begins}/{p.interrupted}" if p.begins else "—",
                     p.debuffs, "、".join(f"{r} {n}" for r, n in p.debuff_roles.items()) or "—",
                     f"{dur:.1f}s" if dur is not None else "—", p.dispelled, p.hits, fmt.num(p.damage),
                     p.kills])
    lines += ["", f"## 每场对照（参考：{note}，和 `splits` 同一批）",
              fmt.table(["记录", "施放", "读条/被打断", "减益次数", "减益点到谁（按职责）", "减益中位持续", "被驱散",
                         "伤害命中", "伤害合计", "致死"], rows)]
    if failed:
        lines.append("（以下参考记录获取失败，未计入：" + "；".join(failed) + "）")
    if profiles[0].debuff_targets:
        lines.append("本场减益落在：" + "、".join(f"{n} {c} 次" for n, c in
                                                sorted(profiles[0].debuff_targets.items(), key=lambda kv: -kv[1])))

    lines += ["", "## 画像（从日志统计，依据是上表的次数）"] + [f"- {x}" for x in summarize(profiles)]

    if web:
        texts, seen_bodies = [], []
        for i in sorted(ids)[:6]:
            got = wowhead_text(i, run.client.lang)
            if not got:
                continue
            body = got[1]
            core = re.sub(r"\s+", "", body)
            if any(core in b or b in core for b in seen_bodies):
                continue  # 同一技能的施放/减益/伤害 ID 说明几乎一样，只留一份
            seen_bodies.append(core)
            texts.append(f"**{got[0]}（{i}）**\n{body}")
        lines += ["", "## Wowhead 技能说明（原文，解释机制用；和日志冲突时以日志为准）"]
        lines += texts or ["（没有拿到说明：网络不可用，或 Wowhead 还没有收录这个技能）"]
    lines.append("\n用法：参考吃了同样的技能却没人死时，用 `events <参考链接> --from --to` 看参考那几秒做了什么，"
                 "这比任何说明都更能告诉你下一把该怎么处理。")
    return "\n".join(lines)
