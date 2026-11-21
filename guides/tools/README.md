# DPS 职业副本手册：两段式制作

2026-11-08 起改为两段式（便宜模型固定采集 + 主会话亲自分析写作）；现行攻略面向 **DPS 专精**，唯一制作标准见 **`guides/tools/GUIDE-SPEC.md`**，完整可触发工作流见项目 skill **`.agents/skills/dps-guide/SKILL.md`**，唯一样板页在 `guides/rogue/sources/duya-sample/`。

1. **采集（Haiku 子代理）**：选 5 场录像，跑 `evidence.py`，得到确定性计算后的证据包。数据工具优先使用 WCL v1 API（`WCL_V1_API_KEY`），未配置时自动回退 v2（配置见根目录 `README.md`）。
2. **写作与验收（主会话亲自做）**：读证据包 → `scaffold.py` 建骨架 → `enc.py` 编天赋 → 按 `GUIDE-SPEC.md` 写页面 → `build.py`（自动外链并补拉缺失图标）→ 跑 `check.py` 0 error + 4 问实战逻辑自检。只交付 HTML，不出 PNG 长图、不截图、不管手机宽度。

为什么要先算成表：第一次试做时，Haiku 交的是整场原始事件 Markdown，主会话为了做窗口内外对比跑了 43 轮 grep 和 Python。`evidence.py` 把这类确定性计算一次做完。

## 工具一览（`guides/tools/`）

| 工具 | 作用 | 常用命令 |
| --- | --- | --- |
| `evidence.py` | 采集 5 场录像生成确定性证据包 | `python3 guides/tools/evidence.py --class guides/tools/classes/<专精>.json --out <目录>/evidence "<链接>@玩家" ×5` |
| `scaffold.py` | 从定版样板一键生成 `sources/<副本>-v2/` 骨架 | `python3 guides/tools/scaffold.py --class <职业目录> --slug <拼音> --dungeon <中文名> --en "<English>"` |
| `enc.py` | 共享天赋编码器 + 回解 0 差异校验 + 5 人差异对比 | `python3 guides/tools/enc.py --in <dir>/evidence/talents.json --out <dir>/tstring.json` |
| `icons.py` | 解析 `{{I:技能ID}}`、自动补拉缺失图标并外链到 `guides/icons/` | `build.py` 调用 `inject_icons()`；手动补拉 `python3 guides/tools/icons.py --fetch <ID...>` |
| `timeline.py` | 共享单轨时间轴与图例样式（禁止在副本目录分叉） | `build.py` 导入 `GOLD_TL_CSS, timeline` |
| `check.py` | 自动化门禁（离线纯度、对比度、锚点、禁词、时间轴、发布契约） | `python3 guides/tools/check.py <页面.html> --source-dir <源码目录> --published` |
| `wcl.py` | 选场（`find`）与定向补查事件（`events`） | `python3 guides/tools/wcl.py find <副本> --class <职业> --level 23 --limit 15` |

### `evidence.py` 输出说明

| 输出 | 内容 |
| --- | --- |
| `compare.md` | 本玩家承伤按「当时开着哪些防御技能」分组；还有敌方每次施放后被打到的比例。先看这个 |
| `uses.md` | 每次防御技能和低频技能的使用情境（波次、前后敌方读条、刚吃的伤害、身上减益、随后消失的减益） |
| `team.md` | 全队承伤，按波次 × 敌方技能，含同一时刻几名玩家一起吃（判断分摊或 AOE） |
| `debuffs.md` | 本玩家身上的减益和可能清掉它的技能 |
| `segments.md` | 波次时间表 |
| `spells.md` | 相关技能的 Wowhead 说明 |
| `talents.json` | 五人的天赋原始数据（有的报告没有记录） |
| `raw/*.json` | 原始事件；`run<N>_names.json` 是单位和技能 ID 到名字的对照 |

职业配置 `classes/<专精>.json` 写防御技能（施法 ID、增益 ID、兜底持续秒数）和必列低频技能 `always`（打断、控制、保人、位移）。新 DPS 专精照 `rogue.json` / `paladin-ret.json` 写一份。

## 派发模板

### 采集（Haiku）

> 你是数据采集员，只运行命令，不做分析，不用 skill。仓库 /Users/xialiqun/.t3/projects/wcl-raider。
> 1. `python3 guides/tools/wcl.py find <副本> --class <职业中文名> --level <层数> --limit 15`，层数先试 23，再试 22。
> 2. 选 5 场：专精是 <专精>；5 个不同报告、5 个不同玩家；层数高优先，同层用时短优先；尽量覆盖国服、欧服、美服。
> 3. 运行 `python3 guides/tools/evidence.py --class guides/tools/classes/<专精>.json --out guides/<职业目录>/sources/<副本拼音>-v2/evidence "<链接>@<玩家>" ×5`。
> 4. 回复：5 场的链接和玩家，以及脚本最后打印的文件大小和天赋状态。出错就原样贴出错误。

### 写作（主会话）

主会话自己读证据包、补查、写 HTML，不派写作子代理。

- **唯一标准与工作流**：严格遵循 **`guides/tools/GUIDE-SPEC.md`**（或加载项目 skill `.agents/skills/dps-guide/SKILL.md`），以 **`guides/rogue/sources/duya-sample/`** 为样板参照，通过 **`guides/tools/scaffold.py`** 起手并用 **`guides/tools/check.py`** 验收。
- **证据补查流程**：先读证据包；需要细看（尤其是保人型 DPS 给队友套增益后的目标承伤）时再调用 `wcl.py events`，补查控制在十来次以内，每次带 `--ability` 和 `--from/--to`，结果记入 `NOTES.md`。
- **交付与汇报**：只交付 HTML，不出 PNG、不截图、不管手机宽度；回复里列出补查了什么、证据包缺了什么，以及 `check.py` 结果。
