# 给副本页加一个专精：操作流程

样板：`saitalisi/`（塞塔里斯神庙），惩戒骑 `specs/ret.json` 是做好的范例。
这份文档写给接手某个专精的 agent。照着做完，副本页上就多一个可切换的专精。

## 0. 开工前

**你要准备的输入**
- 这个专精在这本的 v3 攻略 `guide.md` 和样本 `runs.json`，例如 `guides/paladin-ret/sources/saitalisi-v3/`。
  - 如果还没有：先用 `diag.py sample` 抽样本，再用 `boss` / `trash` / `inspect` 诊断，写出 guide.md。这是上游流程，不在本文范围。
- 职业配置 `guides/tools/classes/<专精>.json`，diag.py 要用它。缺了就仿照 `paladin-ret.json` 写一份。

**你只改这几个文件**
- `guides/dungeons/<副本>/specs/<专精>.json`：新建，主要工作量在这里。
- `guides/dungeons/<副本>/evidence/` 下以 `<专精>` 命名的新文件。

**不要改**
- `dungeon.json`：副本层是所有专精共用的，可能有别的 agent 同时在读写。需要补机制时，见第 3 步末尾。
- `_shared/page.css` 和 `build.py` 里的版面代码。用户在另一个对话里调界面，别覆盖。
- 不要提交 git，除非用户要求。

## 1. 收集依据（放进 evidence/）

所有 `src` 都指向这里的文件，审稿时一条条能对上。

| 文件 | 怎么来 | src 写法 |
|---|---|---|
| `<专精>-guide.md` | 把 guide.md 原样复制过来。复制后别再改，行号就是出处 | `<专精>-guide:L<行号>` |
| `diag-<专精>-b1.md` … `-b4.md`、`diag-<专精>-trash.md` | `python3 guides/tools/diag.py boss --runs <runs.json> --class <配置> --boss N`，trash 同理 | `diag-<专精>-b1`、`diag-<专精>-trash` |
| `wowhead.json`（追加） | 你的专精技能和天赋的说明，用 `wclr.wowhead.spells([...])` 拉，追加进去，别删已有条目 | `wowhead:<技能ID>` |
| `talents-<专精>.json`、`tstring-<专精>.json` | `python3 guides/dungeons/tools/talents.py <runs.json> <副本> <专精>`，会自动反向解码核对 | `talents-<专精>` |

已经有的共用依据：`mdt.lua`（`mdt:<NPC ID>`）、`trash-route.md`（`trash-route`），以及惩戒骑的 `diag-b*.md`（`diag-bN`）。可以引用，但别改。

## 2. 先读懂副本层

读一遍 `dungeon.json`，弄清楚：
- 每个首领（b1–b4）、每段小怪（t0–t3）的技能 ID 有哪些。
- 你的专精文件只能按这些 ID 挂"你要按的"，build 会检查。
- 机制说明、伤害数字、所有人都该做的事，副本层已经写了，你不重复写。

## 3. 写 specs/<专精>.json

结构完全照抄 `specs/ret.json`。各块怎么写：

| 字段 | 写什么 | 限制 |
|---|---|---|
| `spec` | 必须和 `build.py` 里 `SPEC_CATALOG` 的 id 一致（arms / rogue / ele / dh / bm） | — |
| `kit` | 顶部"我的按钮"栏：本专精常用的减伤、打断、驱散，各一句。全本通用的规则写在这里，只写一次，比如"保护祝福只挡物理" | 4–5 个 |
| `bosses.bN.plan` | "大招怎么分"三格：大招 → 留给哪个机制 → 一句话 | 最多 3 格，每句 ≤24 字 |
| `bosses.bN.do.<技能ID>` | 挂在技能下面的"你要按的"。`kind`: do（要按）/ skip（不用按，图标变灰）/ plain（补充说明）。`label` 写按钮名或"不用开" | 每条 ≤44 字 |
| `bosses.bN.trick` | 只有 guide 里有真正的技能组合时才写（如圣盾 + 牺牲）。`chart` 的时长必须来自技能说明 | 可省略 |
| `bosses.bN.donts` | 别这样做 | 最多 2 条 |
| `bosses.bN.evidence` | 从 guide 的"实测背书"里挑 4–6 个 WCL 链接，配一句白话说明 | — |
| `trash.tN` | 同上：plan、do、evidence | — |
| `talents` | `hero` 英雄天赋、`string_from` 指向 tstring 文件、`keys` 3–4 个这本用得上的天赋，`where` 指向用到它的段落 | 每条 ≤50 字 |

**写作规则**（build 会拦下前三条）
- 每条都要有 `src`。
- 伤害写绝对值"约 91 万"，不写"几成血"，不写 HP 百分比，不写 M/K。
- 不写报告腔："13/15 场""场均""中位""Δt"一律不出现，也不写玩家名字。
- 写"信号 → 按什么 → 为什么"，句子短，口语化。文字以后可能交给别的模型润色，结构比文笔重要。
- 某个技能你的专精不用管，就别挂 do。

**副本层需要补东西时**：比如你的专精要处理一个副本层没列的技能，或者发现机制说明有误。不要直接改 `dungeon.json`，在交付说明里列出来，写清楚改什么、出处在哪，由用户或主会话统一合并。

## 4. 生成和检查

```
python3 guides/dungeons/build.py saitalisi
```

- 检查没过会列出每一处问题，逐条修掉再跑。
- 通过后会生成 `saitalisi/saitalisi.html`。打开时在链接后加 `#<专精>` 就直接是你的专精视图。
- 截图自查（headless Chrome）：桌面宽 1280，手机用 390 宽的 iframe 包一层。只看一遍，修一轮，不要反复截。
- 别的 agent 同时也会跑 build。生成的 HTML 每次都是由所有专精文件重新拼出来的，互相覆盖没关系。如果检查报的是别人那份 JSON 的错，等一下再跑。

## 5. 交付

给用户的说明只写这几项：
- 页面路径，带 `#<专精>`。
- 哪些内容是你判断取舍的，请用户重点看。
- 需要合并进副本层的改动（如果有）。
- 没能查实、所以没写的东西。

## 踩过的坑（必读）

- **机制不能脑补。** 一个技能在哪、刷几个、点谁、什么时候出，只写 Wowhead、MDT、日志或用户说过的。查不清就跑 `diag.py inspect --ability <ID>`，还查不清就问用户。
  - 反例：诱导力场被写成"每个人脚下一个电圈"，实际是首领脚下一大滩，坦克要拖走。
- **中文怪名要和 NPC ID 对上。** 从日志 actors 里查名字和 gameID 的对应，不要按英文名自己翻译。
  - 反例：MDT 的 Static Anomaly（134691）在国服日志里叫"静电充能"。
- **小怪分在哪段不靠印象。** 看 `evidence/trash-route.md`，它由 `tools/trash_route.py` 按"开打前已杀了几个首领"统计出来。
- **这些标签都是 build 自动加的，JSON 里不要手写：**
  - 类型标签：【打断】【钢条】【免控】。
  - 伤害类型：物理、自然、暗影……
  - 减益标签：流血、中毒、诅咒、魔法……
  - 它们来自 Wowhead 说明和 MDT 标记，说明里没写就不显示。
- **小怪的【钢条】**（打断不了、只能硬控）要有出处，比如 guide 里写了"用晕停它"。光凭 MDT 显示"不可打断"不够。
- **Wowhead 说明里的伤害数字是基础值**，不能和 +23/+24 的实测数字混用。没有实测，就不写伤害数字。

## 新副本（不是新专精）时多做的事

由一个会话先做好副本层，再分给各专精：
1. 从 MDT 仓库 `Nnoggie/MythicDungeonTools` 的 `Midnight/<副本>.lua` 下载到 `evidence/mdt.lua`。
2. 跑 `tools/trash_route.py <runs.json> > evidence/trash-route.md`。
3. 收集首领和小怪技能的 Wowhead 说明。
4. 用日志核对 NPC 名字。
5. 写 `dungeon.json`：首领、小怪段、`route`、头像用 MDT 的 displayId。
6. 生成一次页面，请用户确认版面，再按本文档分给各专精。
