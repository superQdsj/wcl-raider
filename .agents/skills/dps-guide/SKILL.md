---
name: dps-guide
description: 制作或重做魔兽世界大秘境 DPS 职业副本应对手册（两段式采集 + 骨架生成 + 天赋编码 + 单主线写作 + 自动化门禁与 6 问逻辑自检）。当用户要求制作新副本 DPS 攻略、按新样板重写攻略或测试攻略制作指引时触发。
---

# DPS 副本攻略制作工作流

制作任何 DPS 专精的大秘境攻略时，严格按以下 7 步顺序执行。**绝不整份读取已生成的 `guides/<职业>/*.html`、`dist/` 或 `icons.json`**（遵守 `CLAUDE.md`）。

## Step 0：先读唯一规范与样板参照

在动手写任何 HTML 之前，先读：
1. `guides/tools/GUIDE-SPEC.md`（板块顺序、取证门槛、颜色与发布硬规则、3 类 DPS 适配）
2. 如有需要对照写法，只读样板源码 `guides/rogue/sources/duya-sample/body.part`（不要读 `sample.html` 或 `icons.json`）。

如果是仓库里尚未出现的新 DPS 专精，先按 `GUIDE-SPEC.md` 第三节「新 DPS 专精接入 4 步清单」准备 `guides/tools/classes/<专精>.json`、`scripts/build_site.py` 的 `CLASSES` 登记与专精图标。

## Step 1：采集 5 场证据包（如尚未采集）

按 `guides/tools/README.md` 的 Haiku 采集模板（或直接跑命令）选出 5 场高分限时录像（5 个不同报告、5 个不同玩家、同专精、尽量覆盖国/欧/美）并运行：

```sh
python3 guides/tools/evidence.py \
  --class guides/tools/classes/<专精>.json \
  --out guides/<职业目录>/sources/<副本拼音>-v2/evidence \
  "<WCL链接#fight=N>@玩家名" ... # 共 5 场
```

## Step 2：生成标准骨架 + 编码天赋

1. **生成源码骨架**（严禁手工复制旧副本目录）：
   ```sh
   python3 guides/tools/scaffold.py \
     --class <职业目录> --slug <副本拼音> --dungeon <副本中文名> --en "<English Name>"
   ```
2. **编码并回解核对天赋**（同时输出国服正式中文天赋名与 5 人差异；**严禁根据英文名手译**）：
   ```sh
   python3 guides/tools/enc.py \
     --in guides/<职业目录>/sources/<副本拼音>-v2/evidence/talents.json \
     --out guides/<职业目录>/sources/<副本拼音>-v2/tstring.json
   ```
   - 若返回 `NO_TALENTS`（退出码 2）：从 `body.part` 删除 `.code-row` 导入栏并在 `NOTES.md` 说明原因；`build.py` 与前端 JS 会自动降级。
   - 若大版本节点树缺失：先跑 `python3 guides/tools/enc.py --refresh-tree`。

## Step 3：通读证据包 + 定向补查

按顺序读 `evidence/` 下的确定性表：
1. `compare.md`（直击与跳伤已拆分、含玩家最大血量%与命中场次——注意甄别仅 1–2 场的单场数据！）
2. `interrupts.md`（打断/驱散汇总 + 敌方读条形态——注意区分无 `begincast` 的瞬发引导技，常规打断断不了）
3. `debuffs.md`（本玩家减益持续与消失关联——**若打断或群控在 ≥ 2 场移除某减益，必须写进路线**）
4. `uses.md`（按代表场次细看波次内的防御/打断/保人/位移时机；已排除同刻自挂减益如自律）
5. `team.md`、`segments.md`（含首领相对开打时间 `+Xs`）、`spells.md`（含玩家基础冷却/天赋改写冷却、以及敌方非伤害机制；同时逐一核对每个首领是否有禁疗/满能量/接球等胜负机制）

**定向补查 `wcl.py events`**（控制在十来次以内，每次必带 `--ability` 与 `--from/--to`）：
- **保人型 DPS**（如惩戒骑的保护/牺牲/清毒）：直接用 `--source` 过滤施法者，`interrupts`/`dispels` 的 `--ability` 同时匹配被断/被驱技能：
  ```sh
  python3 guides/tools/wcl.py events "<WCL链接#fight=N>" --type buffs --source "<本玩家>" --target "<队友>" --ability <保人增益ID> --from m:ss --to m:ss
  python3 guides/tools/wcl.py events "<WCL链接#fight=N>" --type damage-taken --player "<队友>" --ability <敌方技能ID> --from m:ss --to m:ss
  ```

## Step 4：写作（`body.part` + `build.py` + `NOTES.md`）

严格遵循 `GUIDE-SPEC.md` 的五块结构与硬规则：
- **页头 + 吸顶导航**：保留裸 `<body>` 与 `<p class="lede">`；导航段名不与 `00–03` 撞号；记得把骨架里的 `TODO 层数` 改成实际参考层数。
- **00 速记区（`#prep`）**：3–4 张核心手牌（冷却/充能/持续核对 `spells.md`，不提前展开首领流程，不夸大清除边界）+ 至多 1 条真实机制硬限制（无则省略 `.limit`）+ 可选全本必断/必驱清单（≥ 2 个集中目标才放，点击直跳对应行 `id="k-..."`）。
- **01 单轨时间轴（`#timeline`）**：按「必做覆盖最多、低样本备选最少」选 1 场代表录像填 `TOTAL_SEC`、`BANDS`、`MARKS`（常规 6–14 点，干净覆盖时可 5 点，标签 ≤ 8 字；不画低样本兜底点；图注标明单场实录）。
- **02 按路线逐段（`#route`）**：一条主线讲到底；必做行 3–6 行（每行至多 1 个 `.btn-chip.pri`）；给队友交牌用 `[技能] <span class="tgt">给目标</span>`，非目标文字用 `.act-note`；每段节奏写清冷却余量条件与未转好备选；复杂首领用 `.row.step` 拆清读条开始 / 生效 / 减益倒计时；对比条只放跨场稳定且直击/跳伤不混算的数据（`0 · 免疫` 条按 `GUIDE-SPEC.md` 双条件裁决）。
- **03 天赋与页尾（`#talent` + `footer`）**：3–4 个不要动的防御/功能天赋 + 1 句常见可换（全部用 `enc.py` 国服中文名）；5 场 WCL 参考链接只放页尾。
- **`NOTES.md`**：写全 4 块——样本与根目录重建命令、技能窗口与量化证据、删掉的低样本打法、天赋 0 差异核对与补查记录（清零所有 `TODO`）。

## Step 5：构建并跑自动化门禁 `check.py`

```sh
python3 guides/<职业目录>/sources/<副本拼音>-v2/build.py
python3 guides/tools/check.py guides/<职业目录>/<YYYY-MM-DD>-<副本中文名>-<职业>.html \
  --source-dir guides/<职业目录>/sources/<副本拼音>-v2 --published
```

- `build.py` 会自动通过 `guides/tools/icons.py` 补拉缺失图标并外链至 `guides/icons/`。
- `check.py` 必须 **0 error**；所有 warning（含对比条交叉校验、多 `.pri` 按钮、时间轴点数/间距）逐条核对确认。

## Step 6：执行「6 问实战逻辑自检」

`check.py` 通过后，逐条对照 `evidence/` 回答以下 6 问，发现不自洽立刻修改源码并重建重验：

1. **冷却算术 & 多段机制总耗时**：所有「顺手交」「两拨各交」「隔轮交」是否写清 `≥ 冷却` 条件与备选？多段机制总耗时（读条 + 延迟爆炸）是否超过免疫/减伤持续时间，已写明延后开启时机？
2. **时间起算点**：多阶段首领步骤是否把「开始读条 / 技能生效 / 减益倒计时」彻底拆清，并核对过 `segments.md` 的相对开打时间？
3. **样本纯净度 & 直击/跳伤拆分**：正文推荐与对比条里有没有混入 1–2 场单场数据或混算直击与跳伤？兜底打法是否已标「兜底/备选」且移出主轴时间轴？
4. **非伤害胜负机制 & 单断 vs 群控**：每个首领是否已核对 `spells.md`/Wowhead 的禁疗、满能量、接球、钻地等非伤害机制？`interrupts.md` 无 `begincast` 的引导技与 `debuffs.md` 中 ≥ 2 场被控/断移除的减益是否全部正确落进路线？
5. **实录与文案三处一致**：时间轴每一点是预开还是事后清，与正文是否一致？导语、速记、路线口径（尤其免疫能否清减益）是否完全对齐？关键触发时机是否无遗漏？
6. **国服中文名零手译**：所有天赋和技能中文名是否均取自 `enc.py` / `spells.md`，无自行意译？

## Step 7：交付与汇报

- 只交付 HTML，不出 PNG、不截图、不管手机宽度。
- 在最终回复中列出：成品与源码路径、`check.py` 结果、补查了什么、`evidence/` 缺了什么、以及删掉了哪些低样本打法。
- 若属于新职业/新专精的第一本攻略或用户要求盲测验证，再按 `.agents/skills/council/SKILL.md` 发起三方 Council 评审。
