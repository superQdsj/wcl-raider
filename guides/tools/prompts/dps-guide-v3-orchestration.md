# DPS 攻略 v3 编排提示词（参数化）

参数：`<spec-slug>`（如 `hunter-bm`）、`<专精中文名>`（如 兽王猎）、`<dungeon>`（目录 slug，如 `saitalisi`）、`<副本名>`（如 塞塔里斯）。
下文 `$S` = `guides/<spec-slug>/sources/<dungeon>-v3`，`$C` = `guides/tools/classes/<spec-slug>.json`，`CK` = `python3 guides/tools/check_claims.py`。

原则：数据交给脚本（串行抓取，WCL 有单 IP 频率限制），写作串行（一个写手），审判独立（一个全新上下文）。多个专精同时做时，抓数也要排队一个一个来，只有模型写稿的部分可以并行。

禁读：`guides/<职业>/*.html`、`dist/`、`sources/*/icons.json`、`guides/tools/diag.py` 全文（用法看 `--help`）、其他专精的成稿（用本文末尾的格式卡代替）。读 diag 输出用 `grep -n` 取需要的段落。

---

## 阶段 1　数据与校准（协调者，强模型）

1. 抽样：`python3 guides/tools/diag.py sample --dungeon <副本名> --class <专精中文名> --levels 24,23,22,21 --want 15 --out $S/runs.json`
   验收：12–15 场、报告和玩家都不重复。不足 12 场就停下来告诉用户。
2. 配置：
   - `$C` 已经是 v3 格式（`defensives` 带 `tier`）：**沿用**，不重建。职业卡和副本无关，换副本只核对差异。
   - 否则按 `guides/tools/classes/paladin-ret.json` 的字段升级或新建 `$C`（`defensives` 的 `tier: normal|major`、`cd`、`dur`、`cleanse_immune`、`blocked_by_debuff`；`utilities`）。技能 ID 只从日志取，不凭记忆。
3. 落盘：`CK dump $S --wowhead`（依次跑 boss 1–4 和 trash，不要加大 `--jobs`，写到 `$S/diag/*.txt`，每份首行是命令原文）。之后一律不带 `--wowhead`。
4. 写 `$S/calibration.md`（不超过 40 行），从 `diag/*.txt` 的「② 手牌预算账」逐项抄：
   - 常规减伤和大牌各是哪些技能，「分母口径」一行原文；
   - 施法 ID 和 Buff ID 不同的技能、被动护盾、锁牌 Debuff、宠物施法；
   - 0 施放的技能（必须列出，没有就写"无"）；
   - 疑点；
   - `$C` 是沿用的：只写和该专精上一个副本 `calibration.md` 的差异（新出现的施放、新的 0 施放、新需要驱散或免疫的 Debuff），没有差异就写"无"。
5. 机制卡（**只在 `guides/tools/mechanics/<dungeon>.md` 不存在时做**，即这个副本的第一个专精）：
   - 先下载 MDT 快照：`python3 guides/tools/mdt.py --en "<副本英文名>" --out guides/tools/mechanics/<dungeon>.mdt.lua`（已存在就不要重新下载，它是固定版本）。
   - `CK mechanics $S` → 生成 `guides/tools/mechanics/<dungeon>.draft.md`：从 diag「① 机制速览」抽出的技能、ID、施放者、目标形态、周期、伤害绝对值、命中/躲避次数。「打断 / 驱散 / 吃控」一栏自动取自 MDT；和日志冲突的（例如 MDT 标可打断、日志里是瞬发）在 calibration.md 的疑点里列出。
   - 协调者只能补 Wowhead 说明里写明的内容（伤害属性、可否驱散），并注明来源；流程、场地、开门条件、几波怪、走位留「<待补>」，**不猜**。
   - 同时写一份 `<dungeon>.banned.txt`（可以为空，只有注释行）。
6. **⏸ 人工确认点**：把 calibration.md（以及第 5 步的机制卡草稿）发给用户，得到确认后才进入阶段 2。
   - 用户要求改配置时，改完重跑第 3 步。
   - 用户补完并确认机制卡后，草稿改名为 `<dungeon>.md`，删掉草稿说明段，写变更记录。
   确认后 commit：`runs.json`、`$C`、`diag/`、`calibration.md`，以及机制卡（如有）。

## 阶段 2　写稿（一个写手，顺序 boss1 → boss2 → boss3 → boss4 → trash，可用便宜模型）

每一节的做法：
1. `grep -n` 读 `$S/diag/<节>.txt`。
2. 每条结论都要先反查，并且一定用 CK 跑（这样会落盘、能被核对）：
   `CK inspect $S --boss N --ability <ID> --only-hit`（小怪用 `--trash`），查纯裸吃时加 `--only-bare`；需要用明细表核对分母时，`--limit` 不小于表头"共 N 条"。
   - 写「必交」：先看就绪未交、纯裸吃的样本，有没有真的残血或死亡；
   - 写「不交」：纯裸吃要真稳（排除外减和抬血掩护，核对起手血线）；
   - 写「免疫 / 清除 / 打断 / 驱散」：要有原始事件链接，分清"免伤但不清 Debuff""同毫秒清除""穿透不免疫"。
3. 按格式卡写 `$S/<节>.md`，同时往 `$S/claims.json` 加这一节的条目（结构见下）。
4. 写完跑 `CK check $S --allow-no-claims --quiet`，确认这一节没有 FAIL 再写下一节。

机制文字（场地、点名、走位、几波怪）只能来自 `guides/tools/mechanics/<dungeon>.md`、MDT、Wowhead、diag「① 机制速览」或用户，不能抄其他专精的稿子，也不能猜。写手只写本专精的应对。发现卡上没有的机制：不写进稿子，记进 calibration.md 的「机制待补」，由协调者交用户确认后补进机制卡。

发现配置错误（漏了技能 ID、tier 分错、施法 ID 和 Buff ID 混了）：停笔，把问题写进 calibration.md 的「待修」，交回协调者。协调者改 `$C` → 重跑 `CK dump` → 已写的节重新 check。写手自己不改 `$C`、`runs.json`、`diag.py`。

### claims.json 结构

```json
{"boss2": [
  {"rule": 2, "type": "必交", "ability": ["1289602"],
   "source": "inspect-boss2-1289602-hit-l200.txt",
   "command": "（可选）落盘文件首行的命令原文",
   "where": {"cover": "纯裸吃", "status": "hit", "remaining_lt": 20},
   "n": 3, "m": 18, "min_hp": 3,
   "links": ["https://www.warcraftlogs.com/reports/...", "..."],
   "quote": ["（可选）来源里逐字出现的片段，如 反制射击 1.53次/场"]}
]}
```

- 每条口诀至少要有一条 claim；`type` 必须是该条【】标签里的一个词。
- 「必交」「不交」必须有 `m`、`min_hp`，而且基于纯裸吃（`--only-bare`，或 `where.cover = 纯裸吃`）。
- 「免疫 / 清除 / 打断 / 驱散」必须有 `links`。
- 链接一律从 diag 输出里复制，不能手改时间戳。要引用施法时刻（diag 里没有的那种），先用 inspect 找到最近的那一行，引用那一行的链接。

## 阶段 3　机械闸门

`CK check $S --banned guides/tools/mechanics/<dungeon>.banned.txt`（文件不存在就去掉这个参数）。退出码为 0 才进入审判。脚本能查的东西审判官不再手工核对。

## 阶段 4　审判（全新上下文，强模型；不给写手的对话和过程）

输入只有：`$S/*.md`、`claims.json`、`diag/`、`calibration.md`、本节"审判清单"、`CK inspect` 的用法。
对每一条口诀判一个结果，写进 `$S/review.md`（一条一行）：
- **通过**；
- **打回**：必须附反例链接，而且反例来自 diag/ 或审判官自己用 `CK inspect` 跑出来的落盘文件；
- **删除**：没有日志实锤。

审判清单：
- 非纯裸吃样本里有没有漏掉的死亡或残血；
- 「不交」的分母有没有混进起手血线不到 80% 的样本；
- 减伤持续时间盖不盖得住 DoT 全程（尾跳风险）；
- 免疫 / 清除三种情况有没有分清；
- 机制文字有没有来源。

退出条件：写手按 review.md 修改 → 重跑阶段 3 → 审判官**只复审被打回的条目**。最多 2 轮。之后仍有争议的条目，在 md 里该条口诀的标签前加【待定】，在 review.md 里列明双方证据，交用户决定。

## 阶段 5　汇总交付（协调者）

1. `CK merge $S --spec-name <专精中文名>`（脚本拼接，不让模型重写）；再跑一次阶段 3。
2. commit：`*.md`、`claims.json`、`review.md`、`guide.md`。
3. 回复用户，只包含：guide.md 路径和 commit hash；校准要点（3–5 行，引自 calibration.md）；审判拦下的反例清单（"条目 → 原结论 → 反例链接 → 处理结果"，没有就写 0）；【待定】条目。不贴 guide.md 全文。

---

## 格式卡（写手只看这一段，不读其他专精的成稿）

```
## 老 N：<Boss 名>（<副本全名> · <专精中文名>）

> **一句话流程**：<场次与中位时长>，<阶段/转火顺序>；**<本专精 15 场死/残概况，真危点>**。

1. **【不交】<条件>**：<纯裸吃 m 次、最低 x%>……
2. **【必交】<条件> → 交「<技能>」**：<就绪未交裸吃 n/m 残、最危链接>；<交牌后中位/最低>……
3. **【交互】或【贪输出】<……>**
4. **【避坑】<……>**

- *实测背书 ①（<样本与死残数>）*：<带 [rNN@m:ss.s](链接) 的事实>
- *实测背书 ②（<交互实锤>）*：<……>
```

- Boss：3–5 条口诀，必须有【不交】【必交】【避坑】，再加【交互】或【贪输出】中至少一条；实测背书正好 2 行。可见字符不超过 2200（链接只计方括号里的文字）。
- 全本小怪：5–7 条口诀，覆盖【必交】、免疫或清除、驱散或功能牌、控断、【避坑】；实测背书 2–3 行。可见字符不超过 3200。
- 不写固定轮次时间表。伤害写绝对值（如"约 74 万"），层数说明全稿只写一次。
- 样本只含限时成功局。页眉已经注明这一点，正文不要把"15 场都没死"写成"必然安全"。
