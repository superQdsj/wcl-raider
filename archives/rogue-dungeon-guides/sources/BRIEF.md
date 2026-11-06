# 潜行者副本攻略：子代理共用说明

## 目标
为潜行者（Rogue）做一份**单个大秘境副本**的攻略 HTML 和 PNG，质量要和已完成的毒牙祭坛版一样：
- 成品 HTML：/Users/xialiqun/.t3/worktrees/wcl-raider/t3-8300a0f4/reviews/2026-10-28-毒牙祭坛-潜行者.html
- 页面源文件（带占位符，结构和 CSS 照它来）：/private/tmp/claude-501/-Users-xialiqun--t3-worktrees-wcl-raider-t3-8300a0f4/6f568a29-46d7-4218-9a90-cb710d8ee564/scratchpad/rogue.src.html
- 成品图（看一下视觉效果）：/Users/xialiqun/.t3/worktrees/wcl-raider/t3-8300a0f4/reviews/2026-10-28-毒牙祭坛-潜行者.png

先打开源文件，再看 PNG 的局部（用 sips 裁剪，没有 PIL），把这套设计吃透。新页面**沿用同一套设计系统**：深色主题、金色作唯一强调色、同样的字体、同样的章节骨架。只换内容，副本名和配色细节可以按副本主题微调（例如 --venom 换成适合该副本的次色），但整体要像同一系列。

## 写作要求（用户明确提过的，必须遵守）
- 这是**攻略**，不是数据报告。每条写成「信号 → 按什么 → 为什么」。
- 不写证据类文字：不写"三名都这样打""日志里 6 次全部命中""没点这个天赋就没有…"，也不写阵容和数据来源段落。
- 用了某个技能就一定有原因。查技能说明（`wcl spell <ID>`）和天赋，弄清楚它解决了什么。闪避这类技能要看伤害：没掉血说明闪掉了；掉了血说明没闪掉，减伤可能来自天赋（例如飘忽不定：闪避期间受到的所有伤害降低 20%）。
- 对方机制要用对 ID，用 `wcl spell` 核对名称。
- 直接推荐顶尖玩家用的天赋。页面最后放可导入的天赋字符串（带复制按钮）、关键天赋卡片和 3 个录像链接。
- 中文写作。

## 章节骨架（照毒牙祭坛版）
页头标签 → 01 全程关键技能时间线 → 02 四个关键时刻 → 03 一个深挖专题（该副本最值得讲的一个技巧，配小图表）→ 04 按路线分段（信号 → 技能 → 为什么）→ 05 工具箱 → 06 常见负面效果表 → 07 天赋（字符串、复制按钮、天赋卡片、录像链接）。
内容不够撑某个章节就合并或删掉，不要硬凑。

## 数据工具
工作目录：/Users/xialiqun/.t3/worktrees/wcl-raider/t3-8300a0f4/.claude/skills/mplus-review/scripts
W="python3 wcl.py"
- `$W find <副本名> --class 潜行者 --limit 8`：找高分潜行者记录。挑同一专精、限时、层数最高的 3 场。
- `$W tactics <链接> --class 潜行者 --refs 2`：常规循环之外的技能用法和对应机制（多场对照）。也可以对每场单独跑。
- `$W events`、`$W pulls`、`$W spell <ID>`、`$W damage`：按需深挖。用 `$W <cmd> --help` 看参数。
- 规则说明可以看 /Users/xialiqun/.t3/worktrees/wcl-raider/t3-8300a0f4/.claude/skills/mplus-tactics/SKILL.md（只看数据流程部分；**不要**用 `wcl render` 的模板做最终页面）。
- **API 点数**：所有代理共用每小时 1000 点。你的预算约 100 点。大查询前先跑 `$W points`；超过 900 就停止拉新数据，用缓存数据完成。

## 图标
- 技能图标：`$W tactics ... ` 之后，可以把 tactics JSON 交给 `$W render` 生成一个临时 HTML，放在你自己的目录里；再用正则 `spell=(\d+)[^>]*>\s*<img[^>]*src="(data:image/[^"]+)"` 抽出 base64 图标，存进你自己的 icons.json。也可以按 Raidbots 或 Wowhead 的图标名，从 https://wow.zamimg.com/images/wow/icons/large/<icon>.jpg 下载。最终 HTML 里图标都内嵌为 base64。
- 天赋图标：Raidbots 数据 /private/tmp/claude-501/-Users-xialiqun--t3-worktrees-wcl-raider-t3-8300a0f4/6f568a29-46d7-4218-9a90-cb710d8ee564/scratchpad/dl/talents.json 里每个条目都有 `icon` 字段，用 zamimg 下载。

## 天赋字符串
- 天赋来源：WCL GraphQL `playerDetails(fightIDs:[f], includeCombatantInfo:true)`，在 combatantInfo.talentTree 里，是一组 {id(entryId), rank, nodeID}。参考代码：
```
import sys; sys.path.insert(0,'.')
from wclr.api import Client, RATE
q="query($c:String,$f:[Int]){ %s reportData{report(code:$c){playerDetails(fightIDs:$f, includeCombatantInfo:true)}}}"%RATE
d=Client().gql(q,{"c":code,"f":[fid]})
pd=d["reportData"]["report"]["playerDetails"]["data"]["playerDetails"]  # 按职责分组 -> 列表，取 type=="Rogue"
```
- 编码器：/private/tmp/claude-501/-Users-xialiqun--t3-worktrees-wcl-raider-t3-8300a0f4/6f568a29-46d7-4218-9a90-cb710d8ee564/scratchpad/enc.py，解码器：/private/tmp/claude-501/-Users-xialiqun--t3-worktrees-wcl-raider-t3-8300a0f4/6f568a29-46d7-4218-9a90-cb710d8ee564/scratchpad/dec.py。复制到你自己的目录再改，不要改原文件。注意以下几点：
  - specId 要换成实际专精：敏锐 261，奇袭 259，狂徒 260。
  - 英雄天赋子树节点（脚本里写死了 99842 → entry 123370 欺诈者）要按实际英雄天赋改：在 Raidbots 数据的 subTreeNodes 里找，entry 下标就是选项序号。
  - 分档节点（tiered）要把多个条目的 rank 加起来。
  - 编码完要解码回去，核对与 WCL 天赋一致。
- 3 名玩家的天赋不同时，推荐最常见的配置，或者用排名第 1 那名玩家的。

## 交付
- 你自己的临时目录：/private/tmp/claude-501/-Users-xialiqun--t3-worktrees-wcl-raider-t3-8300a0f4/6f568a29-46d7-4218-9a90-cb710d8ee564/scratchpad/<副本拼音>/。所有临时文件都放这里，包括 src.html、icons.json、build.py 的副本。
- HTML：/Users/xialiqun/.t3/worktrees/wcl-raider/t3-8300a0f4/reviews/2026-10-28-<副本名>-潜行者.html
- PNG：同一路径，扩展名换成 .png。导出方法：
```
cd /Users/xialiqun/.t3/worktrees/wcl-raider/t3-8300a0f4/.claude/skills/mplus-review/scripts && python3 -c "
from pathlib import Path; from wclr.export import export
export(Path('<html>'), png='<png>')"
```
- 导出后裁几段 PNG 自己看一遍，检查有没有重叠、截断、空白区块，有问题就修。
- 最终回复（简短）：用了哪 3 场（链接）、专精/英雄天赋、深挖专题是什么、天赋字符串、两个文件的路径、拿不准的地方。
