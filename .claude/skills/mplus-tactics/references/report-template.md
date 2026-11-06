# 报告模板（写 JSON，交给 `wcl render` 排版）

报告是给要照着打的玩家看的攻略：扫一眼就知道**看到什么 → 按什么 → 为什么**。

**你只写内容**：一份 JSON。版面、图标、颜色、技能图标、Wowhead 悬停说明都由 `wcl render` 的固定模板生成，**不要自己写 HTML 或 Markdown 版面**。`render` 会先检查下面的写作规则，不合格就报错，并指出哪个字段有问题。按报错改 JSON 后重跑，直到通过。`--force` 只在确实需要时用。

完整示例（照着改）：
- 职业专题：`references/example-class.json`
- 整队版：`references/example-team.json`

两种报告：
- **team（整队版）**：用户给了一条记录，想知道"这把高手怎么处理机制"。每行要写 `who`（哪个职业或角色）。
- **class（职业专题）**：用户问的是某个职业。整篇只写这个职业，不写 `who`；有 `toolbox`（工具箱）。

## 字段

| 字段 | 必填 | 写什么 |
|---|---|---|
| `kind` | ✓ | `"class"` 或 `"team"` |
| `class` / `class_name` | class ✓ | 英文职业名（`Mage`、`Paladin`… 决定主题色）/ 中文名（`法师`，标题里会着色） |
| `title` | ✓ | 职业专题：`"<职业> · <副本> 应对手册"`；整队版：`"<副本> +<层数> · 高手怎么处理机制"` |
| `dungeon`、`date` | ✓ | 副本名；主场次钥石日期 |
| `meta` | | 顶部信息条：`[{label, value}]`，例如 数据 / 玩家 / 结果 / 阵容 / 对照 |
| `summary` | | 一句话：这个副本对读者最要紧的是什么（≤ 90 字） |
| `highlights` | ✓ | 1–3 条"先学这几招"：`{signal, action, note, where, who?}` |
| `toolbox` | class | 工具箱：`[{spell, id, type, handles, timing, usage, spec?}]` |
| `route` | ✓ | 按副本流程，每段 `{kind: boss/trash, name, number?, rows, tip?}` |
| `route[].rows` | ✓ | `{mechanic, mechanic_id, tags, signal, action, why, who?}` |
| `debuffs` | | 常中的减益：`[{name, id, tags, self, handling}]`，`self` 为 null 表示自己不能解 |
| `dont` / `unclear` | | 别这样做 / 还没看清的：`[{title, text}]`，一条一句 |
| `appendix` | | 证据都在这里：`runs`、`runs_note`、`evidence[{mechanic, response, evidence, strength}]`、`verify`、`notes` |

`action`（以及 `toolbox` 的每一行）是一个技能：`{"spell": "操控时间", "id": 342245, "type": "减伤"}`。
- `id` 填玩家技能 ID（`tactics` 输出里有），用来显示图标和悬停说明。`mechanic_id` / `debuffs[].id` 填敌方技能 ID。
- `type` 只能是：反射 · 免疫 · 减伤 · 驱散 · 自解 · 外部 · 位移 · 解控 · 走位 · 治疗 · 控制 · 打断。
- `tags` 每个机制最多 3 个，只能是：点名 · 读条 · 全团 · 正面 · 地面 · 击退 · 打断 · 魔法 · 中毒 · 疾病 · 诅咒 · 流血 · 减速 · 定身 · 恐惧 · 不可驱散。
- `tip.kind`：`tip`（💡 小技巧）· `warn`（⚠️ 注意 / 反例）· `replay`（🎬 值得回放的时间点）。每段最多一个。
- `usage`（常用度）：3 = 每场都用 · 2 = 多数场用 · 1 = 只见过一场。
- `strength`（附录证据强度）：强 / 中 / 弱。

## 每节怎么写

**highlights（⭐）**：最多 3 条，证据够硬的才放，不够就写 1–2 条，不凑数。`signal` 是玩家在屏幕上看到的东西（"践踏读条""麻痹射击上身"）；`note` 一句话讲为什么值得学，最多一个数字；`where` 写在哪（"首领 1""第 8 波"）。

**toolbox（职业专题）**：放驱散、自解、免疫、减伤、位移、解控类，并且 ≥ 2 场都用过的技能，按常用度排。冷却好就用的减伤也放，`timing` 写"冷却好就用"；`handles` 填数据里它最常顶的伤害。输出、增益、饰品、消耗品不放。只有某个专精才有的技能写 `spec`（例如 `"奥术"`）。

**route（按副本流程）**：
- 段落和工具"按位置"表一致：每个首领战一段，两个首领之间的小怪一段。`name` 直接抄工具的位置名，去掉前面的图标（`"首领 1 · 拉维"`、`"小怪 · 开场 → 拉维"`）。首领编号以工具为准，跳过的首领用 `number` 写对编号。
- 只写 ≥ 2 场都出现、而且对得上某个机制的组合。没有内容的段整段不写。
- `signal` 写屏幕上看得到的东西。`why` 写原理："吃完伤害再回溯""开盾时移除减速"。职业专题的 `why` 不能有数字，证据放附录。

**debuffs（🩹）**：这个职业（或全队）常中的减益。`self` 写能自己解的技能，需要天赋就注明；`handling` 写一般怎么处理，可以写别的职业。

**unclear（❓）**：证据不足的线索，一条一句，说清楚为什么还不能下结论。核实命令放 `appendix.verify`。

**appendix**：对照记录、证据明细（次数、场次、倍数、时间戳都写在这里）、核实命令、数据口径。HTML 里默认折叠，PDF 里展开。

## 写作规则（render 会检查）
- 正文（appendix 和 meta 以外）不出现：hitType、伴随、倍、×、`/3 场`、`wcl `、p 值、推断消除。翻成玩家听得懂的话：
  | 工具里 | 正文里 |
  |---|---|
  | 免疫 ×8 | 整段免疫 |
  | 4/4 场（2 队） | 两队都这样打 / usage 3 |
  | 推断消除 | 用完减益就没了 |
  | 伴随 5.7 倍 | 几乎每次读条都开 |
- 长度上限：`signal` 15 字 · `why` 16 字 · `handles` 20 字 · `timing` 16 字 · `handling` 26 字 · `note` / `tip` 44 字 · `summary` 90 字。
- 证据强弱靠措辞：强 → 直接说；中 → "习惯在……"；弱 → 不进正文，放 `unclear`。
- 需要天赋才成立的，写"（需天赋「X」）"。日志里看不到天赋，附录写明是推断。

## 渲染与交付
```
wcl render reviews/<名字>.json                          # 生成同名 .html（本地打开，联网时悬停技能看说明）
wcl render reviews/<名字>.json --pdf reviews/<名字>.pdf  # 用户要 PDF 时（含附录）
wcl render reviews/<名字>.json --png reviews/<名字>.png  # 用户要图片时（整页长图，不含附录）
wcl render reviews/<名字>.json --md  reviews/<名字>.md   # 需要纯文本版时
```
默认只生成 HTML。用户说要 PDF 或图片时再加对应参数。
