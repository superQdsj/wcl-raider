"""命令行入口：python3 guides/tools/wcl.py <命令> [选项]"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .api import Client, WCLError, stderr

DESCRIPTION = """Warcraft Logs 大秘境数据查询工具（用于职业副本攻略的录像检索、事件补查与技能查询）。
所有命令只输出客观数据（Markdown 或 JSON）。
报告参数可以是完整链接（含 #fight=N 时自动选中该场）或 16 位报告代码。"""

COMMANDS = {
    "find": "按副本名（可加职业）找带日志的高分记录，给出链接（不需要报告）",
    "events": "原始事件钻取：按时间窗口/波次/类型/玩家/技能过滤",
    "spell": "查技能资料（Wowhead）：名称、驱散类型、说明文字",
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wcl.py", description=DESCRIPTION,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=["zh", "en"], help="名称语言：zh=中文（默认，经 cn.warcraftlogs.com 翻译），en=英文")
    parser.add_argument("--api", choices=["auto", "v1", "v2"], help="WCL API 版本：auto=优先 v1（默认），v1=强制 v1，v2=强制 v2")
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
        p.add_argument("--api", choices=["auto", "v1", "v2"], default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        p.add_argument("--refresh", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        return p

    p = add("find", report=False)
    p.add_argument("dungeon", help="副本名（中/英文片段，例如 毒牙祭坛）或 encounter ID")
    p.add_argument("--class", dest="cls", metavar="职业", help="只找有该职业/专精的记录（法师、冰法、Mage…）")
    p.add_argument("--level", type=_positive, help="钥石层数（默认全部层数）")
    p.add_argument("--limit", type=_positive, default=8, help="列出多少条（默认 8）")

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

    p = add("spell", report=False)
    p.add_argument("ids", nargs="+", help="技能 ID（可多个）")

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
    client = Client(
        lang=getattr(args, "lang", None),
        refresh=getattr(args, "refresh", False),
        api_version=getattr(args, "api", None),
    )
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
        if client.use_v1:
            client.v1_get("classes", ttl=0)
            r = client.v1_rate or {}
            return (f"WCL API (v1)：当前窗口剩余 {r.get('remaining', '?')}/{r.get('limit', '?')} 次请求。"
                    f"语言：{client.lang}（主机 {client.host}）")
        from .api import RATE
        data = client.gql("{ %s }" % RATE, ttl=0)
        r = client.rate or data.get("rateLimitData") or {}
        return (f"WCL API (v2)：本小时已用 {r.get('pointsSpentThisHour', 0):.1f}/{r.get('limitPerHour')} 点，"
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
    if cmd == "events":
        from .context import load_run
        from .cmd_events import cmd_events
        run = load_run(client, args.report, args.fight)
        return cmd_events(run, args)
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
