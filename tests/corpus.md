# Warcraft Logs 大秘境 QA 语料

核验日期：2026-11-06（Asia/Tokyo）。本清单为在线人工回归语料；`unittest` 只用合成数据，不访问网络、凭据或用户缓存。报告后续可能被设为私密或删除。

## 固定语料（10 条）

| 报告代码 | fight | 地区 | 副本 / 层数 | 已核实特征 |
| --- | --- | --- | --- | --- |
| `JpHdnbhYD8ZFWvma` | 1 | CN | 毒牙祭坛 +24 | 限时 +1；3 次死亡；词缀 147；反推每次 15 秒；报告起点非零，用于交叉核对死亡与读完时间基准 |
| `tgC7LXH1PJyRpKfj` | 1 | US | 毒牙祭坛 +2 | 限时 +3；1 次死亡；仅词缀 165；反推 0 秒；恶魔术士 Synorc，14 个归属宠物；玩家 `Khaterinä`、`Sìmply`；报告有 3 条钥石 |
| `QkyF9vA2hC7qJzGY` | 29 | EU | 纳洛拉克的洞穴 +5 | 限时 +3；1 次死亡；词缀 165/162；反推 0 秒；兽王猎人与恶魔术士；报告有 21 条钥石，夹有团本战斗 |
| `QkyF9vA2hC7qJzGY` | 15 | EU | 密谋小径 +11 | **超时完成**：`kill=true`、`keystoneBonus=0`；10 次死亡；第一波 5 人连续死亡，含一人复活后再死；反推每次 5 秒 |
| `QkyF9vA2hC7qJzGY` | 3 | EU | 诸王之眠 +12 | 限时 +1；16 次死亡；殓尸者姆沁巴（encounter 2142）先 `kill=false` 后 `true`，第 8/11 波，失败约 21 秒、击杀约 2:24；第 8 波 5 人死亡；每次罚时 15 秒 |
| `2D6YH98bdKkqAMz1` | 5 | KR | 诸王之眠 +9 | 限时 +3；**无死亡**；韩文玩家名；邪 DK 含 12 个归属宠物；报告有 4 条钥石 |
| `AhMVrbJgZxPWq7nQ` | 1 | TW | 密谋小径 +5 | 限时 +3；无死亡；生存猎人；繁体玩家名，用 `player 牛奶` 验证片段匹配 |
| `nQcvWw29qgzkFNyd` | 1 | CN | 红玉新生法池 +2 | 限时 +3；6 次死亡，其中两人同一毫秒死亡；词缀 165；反推 0 秒；兽王猎人；`活动炸弹` 对应 373693/1305923 两个 ID，名称过滤同时获取 |
| `yWF7rmM2BTtzP41Q` | 12 | CN | 毒牙祭坛 +24 | **未完成/放弃**；3 次死亡；记录长 6:13；进度 22.5%；friendlyPlayers 共 **12 人**，含无伤害/无专精的记录，不应解释为 12 人同时作战；`--fight last` 应选 37，默认也选最后完成的 37 |
| `1WGqgPTy62FRwDnZ` | 1 | US | 阿梅达希尔团本：瘤根 | 非大秘境报告；`runs` 显示没有大秘境，`overview` 返回中文说明、退出码 2；无需请求归档事件 |

链接格式：`https://www.warcraftlogs.com/reports/CODE#fight=N`，将 CODE/N 替换成上表代码和 fight。

## 来源与复现

用 `wcl.py query` 查询 `worldData.encounter(...).fightRankings(...)`，`bracket` 使用层数减一，过滤 `report.code` 为空的暴雪榜条目。固定样本的地区与实际 report.region 一致。查询过当前赛季 zone 55 的全部 8 个指定副本；额外抽查的塞塔里斯神庙 +9、夺目谷 +9、虚空之痕竞技场 +16 不增加到固定清单。

```graphql
query {
  worldData {
    us: encounter(id: 12993) { fightRankings(bracket: 1, serverRegion: "US", page: 1) }
    eu: encounter(id: 12825) { fightRankings(bracket: 4, serverRegion: "EU", page: 1) }
    kr: encounter(id: 61762) { fightRankings(bracket: 8, serverRegion: "KR", page: 1) }
    tw: encounter(id: 12813) { fightRankings(bracket: 4, serverRegion: "TW", page: 1) }
    cn: encounter(id: 112521) { fightRankings(bracket: 1, serverRegion: "CN", page: 1) }
  }
  rateLimitData { limitPerHour pointsSpentThisHour pointsResetIn }
}
```

`QkyF9vA2hC7qJzGY` 的 fight 15 经 `runs` 发现；fight 3 经查询全报告 `dungeonPulls { encounterID kill }` 定位首领重试。团本来源为 `worldData.encounter(id: 2820).fightRankings(difficulty: 4, page: 1)`。`spec` 同时验证 `characterRankings`、bracket 换算、无日志条目跳过，以及完整 sourceID Casts 查询。

```sh
python3 .claude/skills/mplus-review/scripts/wcl.py runs QkyF9vA2hC7qJzGY
python3 .claude/skills/mplus-review/scripts/wcl.py pulls QkyF9vA2hC7qJzGY --fight 3
python3 .claude/skills/mplus-review/scripts/wcl.py deaths QkyF9vA2hC7qJzGY --fight 15 --detail 0
python3 .claude/skills/mplus-review/scripts/wcl.py player tgC7LXH1PJyRpKfj Synorc --fight 1 --top 5
python3 .claude/skills/mplus-review/scripts/wcl.py damage nQcvWw29qgzkFNyd --ability 活动炸弹
python3 .claude/skills/mplus-review/scripts/wcl.py overview 'https://cn.warcraftlogs.com/reports/yWF7rmM2BTtzP41Q?fight=12' --fight last
python3 .claude/skills/mplus-review/scripts/wcl.py events 'https://wowanalyzer.com/report/tgC7LXH1PJyRpKfj/1-Synorc' --from 14:00 --to 14:30 --type damage-taken --limit 8
python3 .claude/skills/mplus-review/scripts/wcl.py compare tgC7LXH1PJyRpKfj --fight 1 --runs 1
python3 .claude/skills/mplus-review/scripts/wcl.py spec tgC7LXH1PJyRpKfj Synorc --fight 1 --players 1
python3 -m unittest discover -s tests -v
```

## 交叉核对结果

- **低层罚时**：红玉 +2 实际 873220 ms、官方 864918 ms、死亡 6 次，`(864918 - (873220 - 10000)) / 6 = 283 ms`，属于记录尾部误差，支持 0 秒，不能回退到 5 秒。毒牙 +2 单次死亡反推 2033 ms、纳洛拉克 +5 反推 1325 ms，也均归到 0 秒。塞塔里斯 +9 单次死亡反推 6381 ms，归到 5 秒。+11 的 10 次死亡反推 5123 ms/次；+12/+24 归到 15 秒。不能据这些点直接推断全部赛季/层数的默认罚时阈值。
- **宠物伤害**：Synorc 的 Summary、DamageDone 玩家总表、带 sourceID 的技能/合并项总和均为 **126558009**，宠物已归属主人，不应再额外加一遍。graph 只列 5 名主人和 Total，Total 不再计入相加。WCL 的合并项名称优先采用表内 name，避免将宠物名称或分组误标为另一个召唤技能。
- **增益覆盖**：该场 Buffs `totalTime=953695`，但 `startTime=0/endTime=6922171` 是全报告范围；原逻辑把接近全程的虔诚光环显示为约 14%，修正后为约 98%。覆盖率以 `totalTime` 为分母，缺失时用选定 fight 时长。
- **进度与首领尝试**：EU 诸王 +12 按死亡事件计算的各波进度合计与官方同为 96.5%；忠实显示 WCL 原值，不把完成场强行改成 100%。未击杀尝试单独计数，击杀用时只取成功那一次。
- **时间基准**：Summary deathTime 和 Interrupts missedCasts timestamp 加 fight.start 后再定位；Deaths 表、events、dungeonPulls 已是报告相对时间，保持原值。事件窗口和死亡窗口都限定在所选 fight 内。
- **事件伤害口径**：死亡窗口与技能钻取按 `amount + absorbed` 汇总，并明确标注不含 overkill；原始事件另列吸收/过量，不能把这些汇总直接当作所有 WCL 表格的原始伤害总量。
- **命令覆盖**：`runs/overview/pulls/deaths/interrupts/damage/damage --ability/player/compare/spec/events/query/points` 均已真实运行；events 的 all、damage-taken、damage-done、healing、casts、enemy-casts、buffs、debuffs、deaths、interrupts、dispels 共 11 类型均已运行。另测带重音/韩文/繁体名、片段名、`--target`、`--filter`、`--fight last`、WoWAnalyzer 链接、非大秘境 fight 和非法输入。
- **输出预算**：普通命令在 CLI 层最多 6000 字符，截断时有明确提示；死亡和默认 all 事件的大输出已触发并验证。query 默认同为 6000，显式 `--max-chars 0` 仍可获取完整原始 JSON。`player --top 5` 现会约束技能/伤害/承伤/增益表。
- **无打断边界**：真实样本覆盖了某玩家/窗口无打断；整场完全没有打断数据的边界用合成数据验证，没有为寻找该情况继续消耗 API 点数。

## 审查结论与保留限制

- 实时或报告结束不足 3 小时的缓存 TTL 为 300 秒，其余元数据 1 天；旧实时元数据命中后会按 300 秒重新校验。离线测试覆盖实时、近期和历史报告。报告结束很久后才追加上传的新战斗仍可能受 1 天 TTL 影响，可按需手动 `--refresh`。
- 缓存已有“进程 ID + 线程 ID 临时文件 + 原子替换”，40 次并发写回归未出现损坏；客户端统计加锁，同一小时乱序响应保留已见最大点数。并发同一冷查询仍可能重复请求；token 同时过期也没有跨进程互斥，建议未来加入按 key 的请求合并与 token 锁。
- events 分页严格限制返回条数，排除 fake 事件；停滞游标报错，50 页保护和超量都返回截断标志。死亡详情的批量窗口保留 2000 条上限，会显式警告，不把部分数据当成完整值；深入时用 events 缩小窗口分页。
- partial GraphQL 错误不写缓存，也不复用旧错误缓存；死亡窗口失败有明确提示，对比样本字段失败整条排除，避免把缺失表当 0。
- 无官方完成计时且无 147/152 词缀时，仍保留 5 秒**默认估算**，输出明确提示低层可能为 0 秒；尚未核实当前赛季 +6/+7 的阈值、全部旧赛季规则。不要对放弃场的默认罚时当作实测值。
- WCL 的 activeTime 是伤害表统计，不是 GCD 利用率；同名打断手段缺少技能 ID，按名称合并后只给汇总差值，不能精确推出空断次数。连续死亡仅为按时间间隔归组，“疑似团灭”不构成因果判断。
- 查询无 `--refresh`；复用已有缓存，compare/spec 在线抽查各限制 1 条。点数起点约 170.1，最后约 396；共享账户增量约 **226 点**，作为本任务保守估计，低于 300 点预算。未记录任何凭据/令牌。

## 参数同步事项

没有新增或重命名命令/参数。`query --max-chars` 默认由 20000 改为 **6000**，0 仍表示不截断；数值选项现在拒绝负数，`--limit/--pull/--top/--runs/--players/--level` 要求大于 0，`--detail/--times/--max-chars` 可为 0，`--window` 要求有限正数。普通命令增加自动输出长度上限。本次未修改 SKILL.md、references 或 README.md；工作区其他并行修改保留。

## 离线验证记录

`python3 -m unittest discover -s tests -v`：**64 tests / OK**。执行环境为 Python 3.14.3；另外全部脚本和测试通过 `ast.parse(..., feature_version=(3, 9))` 语法检查。使用的 API 均属 Python 3.9 标准库；尚未在实际 Python 3.9 解释器上跑测试。
