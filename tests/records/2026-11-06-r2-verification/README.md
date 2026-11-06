# 第二轮：仅测试与记录

执行日期：2026-11-06，Asia/Tokyo。用户要求：暂不优化，只做测试和记录。

## 结论

- 现有 **109 项离线单元测试全部通过**。
- 测试集合共 **58 个命令用例**。按工具正常 TTL 读取缓存，15 个满足预期退出码，43 个因缓存缺失或失效未执行完毕；没有观察到非缓存原因的退出码失败。
- 另做一次**历史缓存快照回放**：仅在测试进程中忽略缓存 TTL，43 个满足预期退出码，15 个仍缺缓存。该结果不代表正常 TTL 下也可离线完成，更不代表在线 API 已验证。
- **18 项定向证据检查均符合预期**，其中包括已知问题的复现。这里的“符合预期”不表示业务逻辑正确，也不表示问题已修复。
- 原始实现、skill、四份方法论文档、README、原有测试与语料清单的 SHA-256 前后相同。只新增本目录的测试脚本与记录，未进行任何优化或修复。
- 第二轮历史 OpenAI 评审仍为“需修改”：9 项 major、2 项 minor。未重新打评审分，未把历史 7.8 分冒充本次新评审结论。

## 边界与安全

没有调用子代理，也没有使用非 OpenAI 模型。历史记录只归档既有的 Sol 评审、试跑及判断输入；未找回或补写另一位评审的结果，因此**不能声称第二轮双评审完成**。

没有调用线上 WCL、OAuth 或 Raider.IO 接口。测试通过 mock 阻断 `Client._post` 与 `urllib.request.urlopen`，不会读取令牌发请求，也不会写入用户缓存。输出里的“实时请求 1 次”是工具在进入被阻断的 `_post` 前累加的计数，不是实际网络请求。

回放沿用工具原有的查询、翻译、事件解析与评分逻辑；历史回放仅替换测试进程的缓存读取 TTL。原始 TTL 结果存于本目录，忽略 TTL 的结果单独存于 `archival-replay/`。这两种结果不能合并统计为通过率。

`PASS` 只表示命令退出码符合预期。对非法输入、找不到场次/玩家/波次、非大秘境报告，预期退出码是 2，不能解读成该报告分析成功。`CACHE_MISS` 只表示未能使用现有缓存完成测试，既不是业务通过，也不是已经证明工具有缺陷。

所有样本结论仅描述本机此前保存的数据，未重新核实报告可见性、赛季规则或外部机制说明。判断输入中的外部链接及说明是历史评审证据，不是本次独立联网验证。

## 实际覆盖

- 三份第二轮样本：CN +24 `JpHdnbhYD8ZFWvma/fight=1`、EU +11 `QkyF9vA2hC7qJzGY/fight=15`、EU +12 `QkyF9vA2hC7qJzGY/fight=3`。
- 三份样本的 `runs / overview / pulls / deaths / interrupts / damage / compare / score` 和完整死亡展开，在历史缓存回放下均成功执行。
- +12 的 `interrupts --pull 8`、`damage --ability 270003`、`damage --ability 270928`、`player Nikey`、`player Hêll --ability 108271`、`score --no-compare`、带历史 judgments 的 `score` 成功执行。
- CLI 帮助、非法报告、非法波次参数、负输出长度、非有限窗口、缺失场次/玩家/波次、非大秘境报告的错误路径满足预期。
- +12 完整死亡输出确实包含 #1–#16，未出现输出截断；默认死亡输出明确显示截断提示。
- +11 的“超时完成”未被误标为放弃；样本的每死 5 秒/15 秒按已有计时数据反推，未把层数阈值当成本次已核实的新规则。

### 未完成的缓存用例（历史回放仍缺数据，共 15 项）

- +12：按中文名“剑刃风暴”查询承伤；`player Ysavia`；`player Xervdh`；`player Nikey --ability 193455`；按第8波查询敌方施法与打断事件；两段显式时间窗的原始事件；`spec Nikey`，共9项。
- 扩展语料：US +2、EU +5、KR +9、TW +5、CN +2、未完成场次的 `overview`，共6项。

不将这些用例标为通过。即使同技能的数字 ID 查询已有缓存，中文名称查询本次仍缺相应缓存；无法据此判断线上结果是否一致。原始事件命令缺缓存，也意味着本轮没有独立重建历史评审的完整因果链。

## 未修复问题台账

编号与严重程度沿用 `historical-sol-feedback.md`。所有项仍未修复；下列状态区分直接复现、辅助证据与仅保留历史结论，避免宣称全部重新验证。

| 编号 | 级别 | 本次记录 | 状态与证据 |
| --- | --- | --- | --- |
| R2-S1 | major | 唯一可躲技能的 roles 只有 dps/healer；坦克仍获机制10、有效权重85%、总分10 | 直接复现；`archival-replay/eu12-score-judgments.stdout.md` 与历史 judgments |
| R2-S2 | major | 文档仍用“距上次使用≥最短间隔”推出“一定不在冷却”；按波输出仍使用冷却上界估算 | 确认原文未变；未独立验证技能重置/动态冷却实例，不据此认定某人漏交技能 |
| R2-S3 | major | 失败首领到重开之间，第9/10波实际推进5.6%+6.7%，不能整段当纯损失 | 支持证据复现；`archival-replay/eu12-pulls.stdout.md`，未重新测算可省时间 |
| R2-S4 | major | Ysavia 的判断为 unknown，生存仍扣1.5；Nikey的多个未知死亡仍参与扣分 | 直接复现；带判断评分与历史 judgments，未新判个人责任 |
| R2-S5 | major | 个人打断继续用非治疗中位数9比较；Nikey的4/7额外扣0.5 | 直接复现；带判断评分，未建立个人可执行机会集 |
| R2-S6 | major | 评分输出仍含未归一化候选 | 仅复现候选存在；不能因此宣称候选已错误计入机制分，可躲性与机会基准争议保留历史评审结论 |
| R2-S7 | major | Hêll有限审查且无登记错失，技能运用仍为9、总分9.6；团队打断9.2与第8波2/5同时存在 | 直接复现；不能用权重100%或全场聚合高分代替全场覆盖和危急窗口审查；本轮未额外构造空对象判断输入 |
| R2-S8 | major | Nikey整场百分位0仍转为输出5.0并参与总分 | 直接复现；未重新匹配装等、存活机会和职责，不能由该值推出循环差 |
| R2-S9 | major | 暗影束缚“出现10/驱散28/未驱散2”；剑刃风暴汇总15次、事件18次，Hêll汇总9/事件10 | 直接复现；`eu12-interrupts.stdout.md`、`eu12-damage.stdout.md`、`eu12-damage-ability270928.stdout.md`；事件中有0伤害，未认定哪一来源错误，不混算比率 |
| R2-S10 | minor | 未完成场次罚时回退缺赛季适用边界 | 仅归档历史意见，未做跨赛季实测；未完成场次overview缺缓存 |
| R2-S11 | minor | 补查命令与局部预算的可执行性问题 | 仅归档历史意见；本轮不补改流程，也未重新执行预算耗尽场景 |

不发布上述个人分作为最终表现评级，只将其保留为缺陷证据。没有开始第三轮优化、修订或双评审；等待后续明确指示。

## 产物与复现

- `run_verification.py`：运行既有单元测试及58个命令用例，保存 stdout、stderr、退出码、字符数、耗时、截断提示和文件哈希。
- `results.json`：正常 TTL 的逐用例记录和受保护文件指纹。
- `archival-replay/results.json`：历史缓存回放的逐用例记录，包含明确的 TTL 替换说明。
- `unittest.stderr.log`：109项单元测试逐项结果；回放目录也有该日志。
- `verify_evidence.py`、`evidence-checks.json`：18项输出证据及范围检查；已知问题明确标为 `known_issue_reproduced` 等类别，不视作质量通过。
- `historical-sol-feedback.md`、`historical-sol-dryrun.md`、`historical-sol-judgments.json`：之前OpenAI评审的原样归档，不是本次新增评审。
- 每个命令各有 `*.stdout.md` 与 `*.stderr.log`，失败/缺缓存也保留日志。

从仓库根目录执行（仅使用本机已有缓存；在其他机器不保证能重放）：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/records/2026-11-06-r2-verification/run_verification.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/records/2026-11-06-r2-verification/run_verification.py --archival
PYTHONDONTWRITEBYTECODE=1 python3 tests/records/2026-11-06-r2-verification/verify_evidence.py
```

重跑会覆盖本目录对应模式的测试产物。缓存失效会增加正常TTL模式的CACHE_MISS；不含所需缓存的机器无法复现历史回放。测试驱动会完整记录命令失败，但自身退出码不汇总全部命令状态，应查看 `results.json`；证据检查脚本在任一断言不成立时返回非零。
