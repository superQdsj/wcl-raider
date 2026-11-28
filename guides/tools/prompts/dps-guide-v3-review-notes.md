# DPS 攻略 v3：新编排与机械闸门（评审结论）

**结论**：新编排保留了旧版三阶段的骨架，主要改了三处：
- 诊断数据由脚本一次性落盘，所有人共用；
- 写作改为一个写手顺序写；
- 审判官在全新上下文里工作，进审判前先过一道机械闸门。

用 hunter-bm 现有稿件试跑闸门，结果如下：
- 链接全部属于样本内的报告，rNN 标签也都对得上；
- 但有 15/82 条链接不是 diag 输出的原样链接，而是手工改过时间戳的；
- 2 份稿件超出字数上限；
- diag 输出和稿件对"本人死亡次数"的统计系统性不一致，需要人工确认。

上一轮审判官对这几点都没有提出异议。

## 文件

| 文件 | 作用 |
|---|---|
| `guides/tools/prompts/dps-guide-v3-orchestration.md` | 新提示词，参数化，不绑定 agy 或 Claude Code |
| `guides/tools/check_claims.py` | 落盘、闸门、拼接脚本（只用标准库） |
| `tests/test_check_claims.py` | 7 个离线测试；`python3 -m unittest discover -s tests` 全部 65 个通过 |
| `guides/tools/prompts/_trial/` | 试跑产物（约 2.1MB，未 commit，**可以整个删掉**） |

## 新旧提示词的主要差异

| | 旧版 | 新版 |
|---|---|---|
| 编排 | 4 个写手 + 1 个审判官（swarm） | 1 个写手顺序写；1 个审判官，全新上下文。swarm 只在多专精同时出稿时使用 |
| 诊断数据 | 每个 agent 各自跑 boss/inspect | `CK dump` 并行落盘到 `diag/`；inspect 也通过 `CK inspect` 落盘，首行记录命令原文 |
| 标杆 | 每个 agent 读 28KB 的 ret guide.md | 提示词末尾附一张约 600 字的格式卡；禁止读其他专精的成稿 |
| 配置校准 | 写手自己判断"五维正常" | 产出 `calibration.md`（分母口径、施法 ID 与 Buff ID 不同的技能、0 施放技能），**等用户确认后**才写稿 |
| 证据 | 散文里夹着链接 | 每条口诀在 `claims.json` 里有对应条目：类型、技能 ID、n/m、最低血线、链接、来源文件 |
| 核对链接和数字 | 审判官手工核对 | 脚本核对；审判官只看语义问题（漏掉的反例、起手血线、尾跳、死亡归属） |
| 退出条件 | "直到全部签字放行" | 逐条判 通过 / 打回（附反例链接）/ 删除；最多 2 轮；剩下的标【待定】交用户 |
| 机制文字 | 没有约束（f834b6c 的"搬球"错误从 ret 带到了 hunter） | 只能来自副本级共享源、MDT、Wowhead、日志或用户；配合禁用说法清单 |
| 篇幅 | "严格对齐"，没有给数字 | Boss 可见字符 ≤2200，小怪 ≤3200（按 ret 的最大值 1980 / 2706 留了余量） |
| 汇总与回复 | 模型重写 guide.md，回复里贴全文 | `CK merge` 拼接；回复只给路径、commit、校准要点、反例清单（没有就写 0） |
| 配置出错 | 没有上报通道 | 写手停笔写进「待修」；协调者改配置、重跑 dump、重新 check |

新提示词共 4223 字符，其中格式卡和 claims 结构占约 1100，比旧版略长。它省下的是每个 agent 读 28KB 标杆的开销，以及 5 个冷启动 agent 重复跑同样的查询。

## 脚本用法

```bash
CK="python3 guides/tools/check_claims.py"; S=guides/v3/<dungeon>/drafts/<spec>
$CK dump    $S [--wowhead]                    # 并行跑 boss1-4 + trash，写到 $S/diag/
$CK inspect $S --boss 2 --ability 1293048 --only-bare [--limit 200]   # 跑完落盘并打印
$CK check   $S [--banned 禁用说法.txt] [--quiet] [--strict-numbers]   # 有 FAIL 时退出码为 1
$CK merge   $S --spec-name 兽王猎 [--diff]    # 拼接 guide.md；--diff 只比较不写入
```

职业配置默认按目录推断为 `classes/<spec-slug>.json`（`<spec>` 到 `<spec-slug>` 的对照见 `check_claims.py` 的 `CLASS_JSON`）。`--diag-dir` 可以把 diag 指向别的目录。

`check` 逐条输出 PASS / FAIL / WARN / INFO：
- **(a) 链接**：每条 WCL 链接必须逐字出现在 `diag/*.txt` 里；报告 code 必须在 runs.json 中；`[rNN@…]` 标签必须和 runs.json 的 code、fight 对应。
- **(b) claims.json**：
  - 每条口诀都有 claim；claim 的类型属于该条的标签；来源文件存在，命令原文与来源文件首行一致；技能 ID 出现在来源里。
  - 必交 / 不交必须基于纯裸吃样本，并且给出 m 和 min_hp。
  - n、m、min_hp 按 `where` 条件（cover / status / remaining_lt / remaining_ge）在明细表里**重新计数**。如果明细表被 `--limit` 截断，就退回到在原文里查找这个数字。
  - 这些数字也必须写进了稿件；links 和 quote 必须同时出现在稿件和来源里。
  - 没有 claims.json 时，稿件里的数字原文（`x%→y%`、`1.63M`、`n/m`）只按"能否在 diag 里找到"记 INFO；加 `--strict-numbers` 后改记 FAIL。
- **(c) 格式**：标题行、一句话流程、可见字符上限、口诀条数（Boss 3–5 / 小怪 5–7）、标签覆盖、背书行数（每行都要有链接）、不能出现"第 N 轮"或表格。
- **(d) 机制文字**：只做到禁用说法黑名单（`--banned`，每行一个正则）。见文末"仍未解决"。

## hunter-bm 试跑（对上一轮审判官的抽检）

做法：
1. 用 `CK dump` 把 boss1-4 和 trash 落盘到 `_trial/hunter-bm/diag/`（全部命中缓存，耗时 5 秒）。
2. 旧流程没有记录写手跑过哪些 inspect，所以按 diag 和稿件里出现的 70 个技能 ID 补跑了 inspect（`--limit 1000`），作为能找到的最大集合。
3. 带禁用说法清单 `搬球 / 搬运宝珠` 跑 `check --allow-no-claims`。

| 稿件 | 链接逐字命中（只用 boss/trash 输出 → 补齐 inspect 后） | 数字原文命中 | 可见字符 | 格式 / 标签 |
|---|---|---|---|---|
| boss1 | 7/10 → 9/10 | 6/9 | 1680 | PASS |
| boss2 | 4/12 → 6/12 | 17/22 | 2111 | PASS |
| boss3 | 3/10 → 7/10 | 10/19 | 1927 | PASS |
| boss4 | 2/16 → 11/16 | 18/25 | **2655 > 2200 FAIL** | PASS |
| trash | 28/34 → 34/34 | 24/25 | **3620 > 3200 FAIL** | PASS |

总计：PASS 88 / FAIL 6 / WARN 1 / INFO 5。所有链接的报告和 rNN 标签都与 runs.json 一致。

发现的问题：
1. **15 条链接是手工改过时间戳的。** 它们都和 diag 里同一场战斗的某条链接只差 16ms–2.1s。例如 boss2 写"灵龟不免疫毒蛇"时引用的是 `r06@2:16.4`（开龟那一刻），diag 给的是 `r06@2:17.0`。链接没有伪造，但脚本无法核对。新提示词规定"链接只能从 diag 复制"。
2. **死亡数和 diag 对不上，需要人工确认。** diag「④ 死点」给出的死亡数是 boss1 1 / boss2 1 / boss3 2 / boss4 16。稿件按 `targetID == player_id` 改成了 0 / 0 / 1 / 2，但这次查询没有落盘，无法复核。
   - boss4 里 r01 在同一次拉怪中被记了 4 次"死亡"，说明 diag ④ 很可能把队友的死亡算进来了。按规定我没有改 diag.py。
   - 但 boss2 的 `r15@0:42.7 荒野之息` 就是 r15 的猎人本人。diag 记为开着灵龟时死亡，稿件写"本人 0 死"。可能是假死被误判为死亡，**需要人看一下**。
3. **数字有约四分之一找不到原文**（75/100 命中）。没命中的主要是写手自己汇总的分数和中位数（如 13/18、22/23、2.74M）。这类数字只有写进 claims.json 并用 `where` 重新计数，才能核对。
4. **boss2 核心数字核对通过。** 在 `_trial/hunter-bm/claims.boss2-demo.json` 里给 boss2 写了 6 条 claim，用明细表重新计数，以下与稿件一致：蛇群 m=21、最低 78%；钻地之震 m=26、最低 38%；雷霆喷吐 18 次中 3 残、最低 3%；毒蛇风暴 24 次中 1 残、最低 14%。唯一的 FAIL 就是上面第 1 条说的那条手改链接。
5. **黑名单能拦住已知错误。** 用 f834b6c 修正前的 trash.md（c7ecbbc 版本）跑，`搬球` 被拦下；当前版本通过。
6. **拼接可以完全替代模型汇总。** 用现有页眉跑 `merge --diff`，与 hunter 的 guide.md 逐字一致。ret 的正文在把一级标题改成二级后也一致（ret 各节的 md 用的是 `# ` 一级标题，`check` 两种都接受）。

用 ret 校准过格式门槛：ret 五份稿件的格式和字数全部通过，只有小怪缺【驱散/功能牌】记了 WARN。ret 的 `dump` 需要实时请求，这次失败了（SSL 异常和"报告中没有 fight 1"），所以没有核对 ret 的链接。

## 仍未解决

- **机制文字 (d)**：只有黑名单，只能拦住已经发现过的错误。`guides/tools/mechanics/<dungeon>.md`（共享机制源）和 `<dungeon>.banned.txt` 还不存在，需要先建，并由用户确认。
- **diag ④ 死亡归属**：疑似有 bug，建议修 diag.py，让它按 `targetID == player_id` 过滤。在修好之前，审判清单要求人工核对。
- **boss/trash 汇总行的数字**（如"反例A·纯裸吃 24 次"）：目前只能按原文字面匹配，没有结构化解析。
- **`diag/` 要不要 commit**：只有 boss 和 trash 输出时约 40KB；inspect 用 `--limit 1000` 时会到 2MB。建议 inspect 默认 `--limit 200`，只在需要核对分母时放大。
- **按 agent 选模型**：提示词写了"写手用便宜模型、审判官用强模型"，但 agy 是否支持按 agent 指定模型未核实。
- **`_trial/`**：试跑产物，确认后可以 `rm -rf guides/tools/prompts/_trial`。
