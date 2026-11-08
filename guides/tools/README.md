# 职业副本手册：两段式制作（不用 skill）

2026-11-08 起的做法。便宜模型只做固定采集，强模型只做分析和写作。

1. **采集（Haiku）**：选 3 场录像，跑 `evidence.py`，得到一个证据包。
2. **写作（Opus 5.5 medium）**：先读证据包，只在需要细看时调用 `wcl.py events` 精确查询，然后写 HTML、编天赋字符串。只交付 HTML，不出 PNG 长图，不做截图和手机版检查。

为什么要先算成表：第一次试做时，Haiku 交的是整场原始事件的 Markdown。Opus 为了做窗口内外对比，在这些文件上跑了 43 轮 grep 和 Python，比单个 Opus 全包还慢。`evidence.py` 把这类确定性计算一次做完。

## evidence.py

```sh
python3 guides/tools/evidence.py --class guides/tools/classes/<职业>.json --out <证据包目录> \
    "<WCL链接#fight=N>@玩家名" "<链接>@玩家名" "<链接>@玩家名"
```

| 输出 | 内容 |
|---|---|
| `compare.md` | 本玩家承伤按「当时开着哪些防御技能」分组；还有敌方每次施放后被打到的比例。先看这个 |
| `uses.md` | 每次防御技能和低频技能的使用情境（波次、前后敌方读条、刚吃的伤害、身上减益、随后消失的减益） |
| `team.md` | 全队承伤，按波次 × 敌方技能，含同一时刻几名玩家一起吃（判断分摊或 AOE） |
| `debuffs.md` | 本玩家身上的减益和可能清掉它的技能 |
| `segments.md` | 波次时间表 |
| `spells.md` | 相关技能的 Wowhead 说明 |
| `talents.json` | 三人的天赋原始数据（有的报告没有记录） |
| `raw/*.json` | 原始事件；`run<N>_names.json` 是单位和技能 ID 到名字的对照 |

职业配置 `classes/<职业>.json` 只写防御技能：施法 ID、身上增益 ID、兜底持续时间。新职业照 `rogue.json` 写一份。

## 派发模板

### 采集（Haiku）

> 你是数据采集员，只运行命令，不做分析，不用 skill。仓库 /Users/xialiqun/.t3/projects/wcl-raider。
> 1. `python3 .claude/skills/mplus-review/scripts/wcl.py find <副本> --class <职业中文名> --level <层数> --limit 15`，层数先试 23，再试 22。
> 2. 选 3 场：专精是 <专精>；3 个不同报告、3 个不同玩家；层数高优先，同层用时短优先；尽量覆盖国服、欧服、美服。
> 3. 运行 `python3 guides/tools/evidence.py --class guides/tools/classes/<职业>.json --out guides/<职业目录>/sources/<副本拼音>-v2/evidence "<链接>@<玩家>" ×3`。
> 4. 回复：3 场的链接和玩家，以及脚本最后打印的文件大小和天赋状态。出错就原样贴出错误。

### 写作（Opus 5.5 medium）

要点：
- 不用 skill。
- **写攻略，不写统计报告**。直接告诉读者看到什么、按什么、为什么，语气照金标准（潜行者·毒牙祭坛：`python3 guides/rogue/rebuild.py --output-dir <临时目录> --include-original` 生成后看）。正文不出现参考玩家的名字，不写「3/3 人」「三场」「中位数」「共 N 次命中」「一场按 X–Y 次」这类数据口吻；路线逐段的行里不加灰色数据小字。数字只在能直接说明「为什么这样按」时用一个，比如「只吃一跳」「伤害砍半」。参考录像链接只放在页尾。
- **时间轴用单轨**：选一场有代表性的录像，用 `guides/tools/timeline.py` 生成（标签写「免疫蛇之风」「清排干体液」这种动作），不要三名玩家并排的多轨图。
- 先读证据包；`wcl.py events` 补查控制在十来次以内，每次都要带 `--ability` 和 `--from/--to`。
- 统计只是线索，要有窗口内外对比才算确认；三人做法不一致就删。
- 不要从技能名字推断机制类型。
- 照同职业已经做好的新版手册的版式写，源码放在 `sources/<副本拼音>-v2/`。
- 只交付 HTML，不出 PNG、不截图、不管手机宽度。
- 回复里列出补查了什么、证据包缺了什么。
