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
    "ability": "技能画像：点谁、能否打断/驱散、减益多久、单体还是群体、致死次数（本场 vs 参考）+ Wowhead 说明",
    "score": "评分卡：团队与个人的数据分（0.0–10.0，附计算依据）",
    "lint": "话术检查：交付前检查复盘报告正文里的不确定措辞、空话、口令有没有数字和复验",
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
    p = add("ability")
    p.add_argument("name", help="敌方技能：技能 ID 或名称片段（同名的施放/减益/伤害 ID 会一起统计）")
    p.add_argument("--refs", type=_positive, default=3, help="参考记录数量（默认 3，和 splits 选同一批）")
    p.add_argument("--ref", action="append", metavar="报告", help="指定参考记录（链接或 CODE#fight，可重复）")
    p.add_argument("--no-web", action="store_true", help="不查 Wowhead 说明")
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
    p.add_argument("--limit", type=_positive, default=400, help="最多输出多少条（默认 400；繁忙窗口加大到 1000–2000）")
    p = add("score")
    p.add_argument("--judgments", help="已核实的结构化判断 JSON 文件（可躲技能、死亡归因、技能运用；格式见 references/scoring.md）")
    p.add_argument("--no-compare", action="store_true", help="不拉取同层高分记录（关键打断为 N/A，不给出暴露偏离候选）")
    p = add("lint", report=False)
    p.add_argument("file", help="复盘报告的 Markdown 文件路径")
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
    if client.live or client.cached:
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
    if cmd == "lint":
        from .cmd_lint import cmd_lint
        return cmd_lint(args.file)
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
    if cmd == "ability":
        from .cmd_ability import cmd_ability
        return cmd_ability(run, args.name, refs=args.refs, explicit=args.ref, web=not args.no_web)
    if cmd == "score":
        from .cmd_score import cmd_score
        return cmd_score(run, use_compare=not args.no_compare, judgments=args.judgments)
    raise WCLError(f"未知命令：{cmd}")
