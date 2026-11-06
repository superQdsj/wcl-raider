"""命令行入口：python3 wcl.py <命令> <报告链接或代码> [选项]"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import List, Optional

from .api import Client, WCLError, stderr

DESCRIPTION = """Warcraft Logs 大秘境数据工具（mplus-review skill 的数据层）。
所有命令只输出客观数据（Markdown），由 agent 负责判断与建议。
报告参数可以是完整链接（含 #fight=N 时自动选中该场）或 16 位报告代码。"""

COMMANDS = {
    "runs": "列出报告中的所有大秘境记录",
    "overview": "概览：计时/罚时/阵容/DPS/百分位/打断/药水/首领战/死亡一览",
    "pulls": "波次时间线：时长/间隔/怪物构成/进度/团队DPS/承伤/死亡",
    "deaths": "死亡复盘：致死技能、死前承伤时间线、死者施法、团灭判定",
    "interrupts": "打断：敌方读条的打断率与读完时间点、每人打断与施放计数",
    "damage": "承伤：按来源技能的伤害、命中、每人分布与标记",
    "player": "单人深挖：施法/CPM、伤害构成、承伤、增益覆盖、低频技能时间轴",
    "splits": "分段计时：按首领分段，逐段与路线相近的参考记录比用时、时间构成与拉怪差异",
    "danger": "险情：没死但血线很低的时刻、多人同时低血的团队险情，按波次汇总",
    "compare": "与同副本同层高分记录对比：用时结构、死亡、技能命中、打断率",
    "spec": "与同专精顶尖玩家对比技能施放频率（CPM）与活跃时间",
    "events": "原始事件钻取：按时间窗口/波次/类型/玩家/技能过滤",
    "score": "评分卡：团队与个人的数据分（0.0–10.0，附计算依据）",
    "tactics": "应对技巧：常规循环之外的技能在什么情境下使用、应对了哪些敌方机制（驱散/消除/免疫/反射/伴随）",
    "spell": "查技能资料（Wowhead）：名称、驱散类型、说明文字",
    "find": "按副本名（可加职业）找带日志的高分记录，给出链接（不需要报告）",
    "render": "把应对技巧报告 JSON 排成本地 HTML（可导出 PDF / PNG / Markdown）",
    "query": "执行任意 GraphQL（调试/补充查询用）",
    "points": "查看 WCL API 本小时点数余量",
}


def _nonnegative(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("必须大于等于 0")
    return value


def _positive(text: str) -> int:
    value = _nonnegative(text)
    if value == 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return value


def _seconds(text: str) -> float:
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("秒数必须是大于 0 的有限数值")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wcl.py", description=DESCRIPTION,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=["zh", "en"], help="名称语言：zh=中文（默认，经 cn.warcraftlogs.com 翻译），en=英文")
    parser.add_argument("--refresh", action="store_true", help="忽略本地缓存重新拉取")
    sub = parser.add_subparsers(dest="cmd", metavar="命令")

    def add(name: str, report: bool = True) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=COMMANDS[name], description=COMMANDS[name])
        if report:
            p.add_argument("report", help="WCL 报告链接或报告代码")
            p.add_argument("--fight", help="fight 编号（覆盖链接中的 fight 参数；'last' 表示最后一条大秘境）")
            p.add_argument("--max-chars", type=_nonnegative, default=10000,
                           help="输出长度上限（默认 10000 字符，0=不截断）")
        p.add_argument("--lang", choices=["zh", "en"], default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        p.add_argument("--refresh", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        return p

    add("runs")
    add("overview")
    add("pulls")
    p = add("deaths")
    p.add_argument("--detail", type=_nonnegative, default=12, help="最多展开多少次死亡的逐条时间线（默认 12，0=只列表）")
    p.add_argument("--window", type=_seconds, default=10.0, help="死前时间线窗口秒数（默认 10）")
    p = add("interrupts")
    p.add_argument("--times", type=_nonnegative, default=8, help="每个技能列出的漏断时间点数量（默认 8）")
    p.add_argument("--pull", type=_positive, help="只分析第 N 波，并估算打断容量")
    p = add("damage")
    p.add_argument("--top", type=_positive, default=25, help="列出的技能数量（默认 25）")
    p.add_argument("--melee", action="store_true", help="把近战普攻也列入表格")
    p.add_argument("--ability", help="只看某个技能（技能 ID 或名称片段），展开每人命中明细")
    p = add("player")
    p.add_argument("name", help="玩家名（支持前缀/片段；也可用 坦克/治疗）")
    p.add_argument("--top", type=_positive, default=15, help="各表列出的行数（默认 15）")
    p.add_argument("--ability", help="只看该玩家指定技能的每次施放、波次与最短/最长间隔（ID 或名称片段）")
    p = add("splits")
    p.add_argument("--refs", type=_positive, default=3, help="选用的参考记录数量（默认 3）")
    p.add_argument("--candidates", type=_positive, default=8,
                   help="从排名里拉取多少条候选记录来挑路线最像的（默认 8，每条约 1–3 点）")
    p.add_argument("--level", type=_positive, help="参考记录的钥石层数（默认与本场相同）")
    p.add_argument("--ref", action="append", metavar="报告",
                   help="指定参考记录（链接或 CODE#fight，可重复），例如自己上一把限时的记录")
    p = add("danger")
    p.add_argument("--threshold", type=float, default=35.0, help="个人险情的血量阈值（%%，默认 35）")
    p.add_argument("--team-below", type=float, default=50.0, help="团队险情：多人同时低于这个血量（%%，默认 50）")
    p.add_argument("--top", type=_positive, default=25, help="列出的险情数量（默认 25）")
    p = add("compare")
    p.add_argument("--runs", type=_positive, default=3, help="对比的高分记录数量（默认 3，每条约消耗 3 点）")
    p.add_argument("--level", type=_positive, help="对比的钥石层数（默认与本场相同）")
    p.add_argument("--top", type=_positive, default=15, help="各对比表列出的行数（默认 15）")
    p = add("spec")
    p.add_argument("name", help="玩家名")
    p.add_argument("--players", type=_positive, default=3, help="对比的同专精顶尖玩家数量（默认 3）")
    p.add_argument("--level", type=_positive, help="对比的钥石层数（默认与本场相同）")
    p.add_argument("--top", type=_positive, default=25, help="列出的技能数量（默认 25）")
    p = add("events")
    p.add_argument("--from", dest="t_from", help="开始时间（相对钥石开始，如 12:30 或 750）")
    p.add_argument("--to", dest="t_to", help="结束时间（同上）")
    p.add_argument("--pull", type=_positive, help="只看第 N 波（自动设置时间窗口）")
    p.add_argument("--type", default="all",
                   help="damage-taken | damage-done | healing | casts | enemy-casts | buffs | debuffs | deaths | "
                        "interrupts | dispels | all（默认 all）")
    p.add_argument("--player", help="玩家名：all 双向过滤（施放或承受）；damage-taken/healing 看其承受，其余看其发出")
    p.add_argument("--target", help="目标名（任意单位名称，精确匹配）")
    p.add_argument("--ability", help="技能 ID 或名称片段")
    p.add_argument("--filter", help="原生 WCL filterExpression（与其他过滤条件取 AND）")
    p.add_argument("--limit", type=_positive, default=150, help="最多输出多少条（默认 150）")
    p = add("score")
    p.add_argument("--judgments", help="已核实的结构化判断 JSON 文件（可躲技能、死亡归因、技能运用；格式见 references/scoring.md）")
    p.add_argument("--no-compare", action="store_true", help="不拉取同层高分记录（关键打断为 N/A，不给出暴露偏离候选）")
    p = add("tactics")
    p.add_argument("--player", help="只看某名玩家（名称片段或 坦克/治疗）")
    p.add_argument("--ability", help="逐次列出某个额外技能每次使用的情境（技能 ID 或名称片段）")
    p.add_argument("--top", type=_positive, default=12, help="每名玩家列出的技能数、每张表的行数基数（默认 12）")
    p.add_argument("--detail", type=_positive, default=40, help="--ability 时最多列出多少次使用（默认 40）")
    p.add_argument("--no-wowhead", action="store_true", help="不向 Wowhead 查询驱散类型与技能说明")
    p.add_argument("--refs", type=_nonnegative, default=0,
                   help="再分析 N 场同副本同层的高分记录做多场对照（默认 0；每场首次约 20–40 点）")
    p.add_argument("--ref", action="append", metavar="报告", help="指定对照记录（链接或 CODE#fight，可重复）")
    p.add_argument("--class", dest="cls", metavar="职业",
                   help="只看某职业/专精（法师、冰法、Mage、奶骑…）；配合 --refs 时从该职业的个人排名里取对照，并输出跨场职业汇总")
    p.set_defaults(max_chars=60000)  # 几张汇总表一起看才有意义（含多场对照），默认放宽
    p = add("spell", report=False)
    p.add_argument("ids", nargs="+", help="技能 ID（可多个）")
    p = add("find", report=False)
    p.add_argument("dungeon", help="副本名（中/英文片段，例如 毒牙祭坛）或 encounter ID")
    p.add_argument("--class", dest="cls", metavar="职业", help="只找有该职业/专精的记录（法师、冰法、Mage…）")
    p.add_argument("--level", type=_positive, help="钥石层数（默认全部层数）")
    p.add_argument("--limit", type=_positive, default=8, help="列出多少条（默认 8）")
    p = add("render", report=False)
    p.add_argument("json", help="报告 JSON（格式见 mplus-tactics/references/report-schema.md）")
    p.add_argument("--out", help="HTML 输出路径（默认与 JSON 同名 .html）")
    p.add_argument("--pdf", help="同时导出 PDF 到这个路径（含附录）")
    p.add_argument("--png", help="同时导出整页 PNG 到这个路径（不含附录）")
    p.add_argument("--md", help="同时导出 Markdown 到这个路径")
    p.add_argument("--force", action="store_true", help="检查不通过也照样渲染（只在确有必要时用）")
    p = add("query", report=False)
    p.add_argument("graphql", help="GraphQL 查询文本，或 @文件路径")
    p.add_argument("--vars", help="JSON 变量")
    p.add_argument("--max-chars", type=_nonnegative, default=6000, help="输出截断长度（默认 6000，0=不截断）")
    add("points", report=False)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 1
    client = Client(lang=getattr(args, "lang", None), refresh=getattr(args, "refresh", False))
    try:
        out = dispatch(client, args)
        if args.cmd != "query" and getattr(args, "max_chars", 1):
            from .fmt import limit_output
            out = limit_output(out, getattr(args, "max_chars", 10000) or 10000)
    except WCLError as exc:
        stderr(f"错误：{exc}")
        if client.live or client.cached:
            stderr(f"— {client.footer()}")
        return 2
    except KeyboardInterrupt:
        return 130
    sys.stdout.write(out.rstrip() + "\n")
    sys.stdout.flush()
    stderr(f"— {client.footer()}")
    return 0


def dispatch(client: Client, args: argparse.Namespace) -> str:
    cmd = args.cmd
    if cmd == "points":
        from .api import RATE
        data = client.gql("{ %s }" % RATE, ttl=0)
        r = client.rate or data.get("rateLimitData") or {}
        return (f"WCL API：本小时已用 {r.get('pointsSpentThisHour', 0):.1f}/{r.get('limitPerHour')} 点，"
                f"{int(r.get('pointsResetIn') or 0) // 60} 分钟后重置。语言：{client.lang}（主机 {client.host}）")
    if cmd == "query":
        text = args.graphql
        if text.startswith("@"):
            try:
                with open(text[1:], encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeError) as exc:
                raise WCLError(f"无法读取查询文件：{exc}") from None
        try:
            variables = json.loads(args.vars) if args.vars else {}
        except ValueError as exc:
            raise WCLError(f"--vars 必须是 JSON 对象：{exc}") from None
        if not isinstance(variables, dict):
            raise WCLError("--vars 必须是 JSON 对象。")
        data = client.gql(text, variables, ttl=0)
        out = json.dumps(data, ensure_ascii=False, indent=1)
        if args.max_chars and len(out) > args.max_chars:
            note = f"\n…（已截断，共 {len(out)} 字符；用 --max-chars 0 查看全部）"
            out = out[:max(0, args.max_chars - len(note))] + note[:args.max_chars]
        return out
    if cmd == "spell":
        return cmd_spell(client, args.ids)
    if cmd == "find":
        from .cmd_find import cmd_find
        return cmd_find(client, args.dungeon, args.cls, level=args.level, limit=args.limit)
    if cmd == "render":
        from .report import cmd_render
        return cmd_render(args.json, out=args.out, pdf=args.pdf, png=args.png, md=args.md, force=args.force,
                          lang=client.lang)
    if cmd == "runs":
        from .cmd_overview import cmd_runs
        return cmd_runs(client, args.report)

    from .context import load_run
    run = load_run(client, args.report, args.fight)
    if cmd == "overview":
        from .cmd_overview import cmd_overview
        return cmd_overview(run)
    if cmd == "pulls":
        from .cmd_overview import cmd_pulls
        return cmd_pulls(run)
    if cmd == "deaths":
        from .cmd_deaths import cmd_deaths
        return cmd_deaths(run, detail=args.detail, window=args.window)
    if cmd == "interrupts":
        from .cmd_interrupts import cmd_interrupts
        return cmd_interrupts(run, times=args.times, pull=args.pull)
    if cmd == "damage":
        from .cmd_damage import cmd_damage
        return cmd_damage(run, top=args.top, melee=args.melee, ability=args.ability)
    if cmd == "player":
        from .cmd_player import cmd_player
        return cmd_player(run, args.name, top=args.top, ability=args.ability)
    if cmd == "splits":
        from .cmd_splits import cmd_splits
        return cmd_splits(run, refs=args.refs, candidates=args.candidates, level=args.level, explicit=args.ref)
    if cmd == "danger":
        from .cmd_danger import cmd_danger
        return cmd_danger(run, threshold=args.threshold, team_below=args.team_below, top=args.top)
    if cmd == "compare":
        from .cmd_compare import cmd_compare
        return cmd_compare(run, runs=args.runs, level=args.level, top=args.top)
    if cmd == "spec":
        from .cmd_compare import cmd_spec
        return cmd_spec(run, args.name, players=args.players, level=args.level, top=args.top)
    if cmd == "events":
        from .cmd_events import cmd_events
        return cmd_events(run, args)
    if cmd == "score":
        from .cmd_score import cmd_score
        return cmd_score(run, use_compare=not args.no_compare, judgments=args.judgments)
    if cmd == "tactics":
        from .cmd_tactics import cmd_tactics
        return cmd_tactics(run, player=args.player, ability=args.ability, top=args.top, detail=args.detail,
                           wowhead=not args.no_wowhead, refs=args.refs, explicit=args.ref, cls_text=args.cls)
    raise WCLError(f"未知命令：{cmd}")


def cmd_spell(client: Client, ids: List[str]) -> str:
    from .wowhead import spell
    out = []
    for raw in ids:
        if not raw.strip().isdigit():
            raise WCLError(f"技能 ID 必须是数字：{raw}")
        info = spell(int(raw), client.lang)
        if not info:
            out.append(f"## {raw}\n（Wowhead 没有返回该技能，或网络不可用；可人工查看 https://www.wowhead.com/spell={raw}）")
            continue
        parts = [f"## {info['name']}（{raw}）" + (f" · 驱散类型：{info['dispel']}" if info.get("dispel") else ""),
                 info.get("description") or "（无说明）"]
        if info.get("aura"):
            parts.append("减益/增益效果：" + info["aura"].replace("\n", " / "))
        parts.append(f"https://www.wowhead.com/spell={raw}")
        out.append("\n".join(parts))
    return "\n\n".join(out)
