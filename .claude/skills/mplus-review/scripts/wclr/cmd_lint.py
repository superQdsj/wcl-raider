"""lint 命令：交付前检查复盘报告的写法（不查数据对错，只查话术）。

便宜的模型最常见的两个毛病：正文里到处是"不能断言""未核实"，以及"注意减伤"这类空话。
规则写在模板里它们也会忘，所以交付前用这个命令机械地查一遍，按提示改完再交。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from .api import WCLError

# 正文里不许出现：不确定的话只放在"还没看清的"和附录里
HEDGES = ["不能断言", "不能据此", "据此断", "未核实", "没核实", "未能核实", "不代表", "仍待", "待核对", "待查", "尚未",
          "不保证", "不能当作", "不能直接", "不能简单", "不能把", "不足以", "需要进一步", "进一步核实", "无法确定",
          "无法判断", "不一定"]
# 空话：出现就要换成具体的技能、时机、人和数字
FILLERS = ["注意减伤", "准备减伤", "集中爆发", "提高输出", "提升输出", "提前准备", "加强沟通", "合理分配", "优先处理",
           "注意走位", "注意躲", "留意", "保守措施", "尽早", "及时处理"]
OPEN_SECTIONS = ("还没看清的", "附录", "数据说明", "评分")
# 换个说法的不确定措辞（"尚待确认""不能全部当成"之类）：按模式抓，避免换词绕过
HEDGE_PATTERNS = [
    r"不能.{0,6}(当成|当作|算作|算成|只看|直接|全部|据此|断定|归因|简化|推断|说明)",
    r"(尚待|有待|待确认|待核|还没.{0,4}(核实|确认|查清|查明|验证)|未.{0,2}(核实|确认|查明|验证|证实))",
    r"(无法|没法).{0,4}(确定|判断|确认|证明)",
    r"没有?.{0,2}(核实|查明|验证|证实)",
    r"(并非|不是)(已经)?(证明|确定)",
]
PROBABLY = ("很可能", "可能", "大概率", "或许", "也许", "估计")


def _sections(lines: List[str]) -> List[Tuple[str, int, int]]:
    """[(标题, 起始行号, 结束行号)]，只看二级标题。"""
    heads = [(i, ln[3:].strip()) for i, ln in enumerate(lines) if ln.startswith("## ")]
    out = []
    for k, (i, title) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        out.append((title, i, end))
    return out


def lint_text(text: str) -> List[str]:
    lines = text.splitlines()
    issues: List[str] = []
    secs = _sections(lines)
    if not secs:
        return ["找不到二级标题（## …），报告没有按模板写。"]
    maybe = 0
    for title, a, b in secs:
        if any(t in title for t in OPEN_SECTIONS):
            continue
        for i in range(a + 1, b):
            ln = lines[i]
            hit = next((w for w in HEDGES if w in ln), None)
            if not hit:
                m = next((re.search(pat, ln) for pat in HEDGE_PATTERNS if re.search(pat, ln)), None)
                hit = m.group(0) if m else None
            if hit:
                issues.append(f"第 {i + 1} 行（{title}）有\"{hit}\"：正文只写证据够的结论。证据不够就删掉这句，"
                              "或者把这件事挪到\"还没看清的\"，写清用哪条命令核实。换个说法不算改好。")
            for w in FILLERS:
                if w in ln:
                    issues.append(f"第 {i + 1} 行（{title}）有空话\"{w}\"：换成具体的技能、谁、看到什么信号时、做到什么数值。")
                    break
            maybe += sum(ln.count(w) for w in PROBABLY if w != "可能") + ln.count("可能") - ln.count("很可能")
    if maybe > 4:
        issues.append(f"正文里\"可能\"出现了 {maybe} 次：证据够的直接下结论，不够的挪到\"还没看清的\"。")

    def items(title_kw: str) -> Tuple[str, List[Tuple[int, str]]]:
        sec = next((s for s in secs if title_kw in s[0]), None)
        if not sec:
            return "", []
        title, a, b = sec
        found: List[Tuple[int, str]] = []
        for i in range(a + 1, b):
            if re.match(r"^\d+\.\s", lines[i]):
                found.append((i, lines[i]))
            elif found and lines[i].strip() and not lines[i].startswith("#"):
                j, t = found[-1]
                found[-1] = (j, t + "\n" + lines[i])
        return title, found

    title, todo = items("下一把")
    if not title:
        issues.append("缺少\"下一把怎么打\"一节。")
    else:
        if len(todo) > 3:
            issues.append(f"\"下一把怎么打\"有 {len(todo)} 条，最多 3 条：只留最能省时间、最能防翻车的。")
        for i, t in todo:
            if "复验" not in t:
                issues.append(f"第 {i + 1} 行：\"下一把怎么打\"这一条没有写复验（下一把看哪个数字就知道改好了）。")
            if re.search(r"(核实|先跑|先查|`wcl|执行前|尚待|待确认)", t.split("复验")[0]):
                issues.append(f"第 {i + 1} 行：\"下一把怎么打\"这一条还要先去核实/跑命令才能执行，那它还不是口令。"
                              "去把它核实完，核实不了就整条挪到\"还没看清的\"。")
            if not re.search(r"\d", t):
                issues.append(f"第 {i + 1} 行：\"下一把怎么打\"这一条没有任何数字（时间点、血量、DPS、次数）。")
    title, lost = items("时间丢在哪里")
    if not title:
        issues.append("缺少\"时间丢在哪里\"一节。")
    else:
        for i, t in lost:
            first = t.splitlines()[0]
            if not re.search(r"\d+:\d\d|\d+\s*秒", first):
                issues.append(f"第 {i + 1} 行：\"时间丢在哪里\"这一条的第一句没有写丢了多少时间。")
            if re.search(r"(合计|加起来|总共|两波).{0,40}(?<!慢)快\s*\d", t) or re.search(r"(合计|加起来).{0,40}(更快|快于|反而快)", t):
                issues.append(f"第 {i + 1} 行：这一条自己说了合起来并不慢，那就不是丢时间的地方，删掉或并进别的条目。")
    return issues


def cmd_lint(path: str) -> str:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise WCLError(f"读不到报告文件：{exc}") from None
    issues = lint_text(text)
    if not issues:
        return f"# 话术检查：{p.name}\n通过：正文没有不确定措辞和空话，\"下一把怎么打\"每条都有数字和复验。"
    return "\n".join([f"# 话术检查：{p.name}（{len(issues)} 处要改）"] + [f"- {x}" for x in issues] +
                     ["", "改完再跑一次，直到通过。只改写法，不要为了通过检查删掉有证据的结论。"])
