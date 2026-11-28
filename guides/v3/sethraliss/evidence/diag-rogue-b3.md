$ python3 guides/tools/diag.py boss --runs guides/v3/sethraliss/drafts/rogue-subtlety/runs.json --class guides/tools/classes/rogue-sub.json --boss 3
# 塞塔里斯神庙 · 加瓦兹特（encounter 2126）· 潜行者（敏锐） 极简五维诊断
> 样本：15 场高分限时（+24×15，不同报告/玩家）| 中位战斗时长 3:53 | 潜行者（敏锐）中位血量 1.05M | 拉入小怪合波 15/15 场

## ① 机制速览（按敌方关键技能施放主键，DoT 按单目标完整归并）
- *（合波带入小怪威胁技）*：
  - **[小怪:闪电尖塔] 镀流**（闪电尖塔, ID:266923）：点/扫3人(最高5)+Debuff | 周期 ~4.0s | 纯裸吃中位 184K (17%HP) | 共456波（中207 / 免疫0 / 躲避未中249） — *加瓦兹特的尖塔每0.5秒造成24246点自然伤害，但无法对加瓦兹特施加充能。 受此影响时，受害者受到的物…*
  - **[小怪:加瓦兹特] 诱导**（加瓦兹特, ID:1290531）：全队AOE | 周期 ~23s | 纯裸吃中位 838K (80%HP) | 共149波（中144 / 免疫2 / 躲避未中3） — *加瓦兹特释放出一道电能脉冲，对所有敌人造成145474点自然伤害，并产生一个诱导力场。*
  - **[小怪:加瓦兹特] 诱导力场**（加瓦兹特, ID:1291815）：单点1人(最高3)+DoT | 周期 ~46s | 有覆盖中位 0 (0%HP) | 共25波（中12 / 免疫1 / 躲避未中12） — *静电场每1秒对站在其中的玩家造成96982点自然伤害。*
  - **[小怪:加瓦兹特] 放电**（加瓦兹特, ID:266512）：全队AOE+Debuff | 周期 一次性/不固定 | 纯裸吃中位 886K (84%HP) | 共2波（中2 / 免疫0 / 躲避未中0） — *加瓦兹特消耗能量电击所有玩家，造成164870点自然伤害并使其造成的伤害降低50%，持续20秒。 消耗能…*

## ② 手牌预算账
- **佯攻**（常规）：实际CD 5s(实测最小5.0s) | 开怪前在CD 0/15 | Boss场均 13.33次（15/15场用过，全本共986次）
- **暗影斗篷**（大牌）：实际CD 121s(实测最小121.3s) | 开怪前在CD 1/15 | Boss场均 1.60次（14/15场用过，全本共100次）
- **闪避**（大牌）：实际CD 120s(实测最小120.0s) | 开怪前在CD 3/15 | Boss场均 1.27次（13/15场用过，全本共99次）
- 功能/应急牌（Boss内用过）：猩红之瓶 0.60次/场(4/15场) | 消失 1.20次/场(12/15场) | 暗影步 0.13次/场(2/15场) | 疾跑 0.13次/场(2/15场) | 嫁祸诀窍 0.13次/场(2/15场) | 毒刃 0.27次/场(3/15场)
- 分母口径：常规减伤 = `佯攻`；大牌免疫 = `暗影斗篷、闪避`

## ③ 正例 vs 反例对照（被动盾与明确外减单独隔离为「其他覆盖」，最危样本附 WCL 锚点）
### 合波带入小怪威胁技
- **[小怪:闪电尖塔] 镀流**（共456波：中/免疫207，躲避/未中249）
  - 正例·常规(佯攻×92)：92次 | 起手100%(低42%) → 剩血52%(低20%) | 叠伤2/92
  - 正例·大牌(佯攻+闪避×25/闪避×11/暗影斗篷×8/佯攻+暗影斗篷×4/佯攻+闪避+暗影斗篷×1)：49次 | 起手100%(低10%) → 剩血55%(低0%) | **2s内死2次**
  - 其他覆盖(集结呐喊×2)：2次 | 起手80%(低60%) → 剩血50%(低42%)
  - 反例A·纯裸吃就绪未交：64次 | 起手100%(低50%) → 剩血78%(低19%) | 最危:[r04@3:38.1](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=14634307&end=14640307) (100%→19%[窗内抬血1.08M])
- **[小怪:加瓦兹特] 诱导**（共149波：中/免疫146，躲避/未中3）
  - 正例·常规(佯攻×129)：129次 | 起手100%(低100%) → 剩血58%(低35%)
  - 正例·大牌(闪避×3/佯攻+闪避×3/暗影斗篷×2)：8次 | 起手100%(低100%) → 剩血50%(低22%) | 免疫2次
  - 反例A·纯裸吃就绪未交：9次 | 起手100%(低92%) → 剩血20%(低0%) | **2s内死1次**，最危:[r02@0:47.0](https://www.warcraftlogs.com/reports/F1vmzABpngjq4rw2#fight=1&view=events&start=6680587&end=6686587) (100%→5%[窗内抬血423K])
- **[小怪:加瓦兹特] 诱导力场**（共25波：中/免疫13，躲避/未中12）
  - 正例·常规(佯攻×9)：9次 | 起手— → 剩血—
  - 正例·大牌(佯攻+闪避×3/暗影斗篷×1)：4次 | 起手— → 剩血— | 免疫1次
  - 反例A·纯裸吃就绪未交：0次
- **[小怪:加瓦兹特] 放电**（共2波：中/免疫2，躲避/未中0）
  - 正例·常规(佯攻×1)：1次 | 起手100%(低100%) → 剩血47%(低47%) | 叠伤1/1
  - 反例A·纯裸吃就绪未交：1次 | 起手100%(低100%) → 剩血31%(低31%) | 最危:[r13@1:00.9](https://www.warcraftlogs.com/reports/DTNp3wMR7jdCnKWr#fight=3&view=events&start=1487187&end=1493187) (100%→31%[盾吸261K,窗内抬血597K])

## ④ 死点 & 残血（<20% HP）前 5 秒连招
- 总计：**死亡 2 次 / 残血(<20%) 4 次**（覆盖 15 场）
- 高频连招模式：`诱导` ×3 | `镀流` ×3
  - [r12@1:09.5](https://www.warcraftlogs.com/reports/7N92JyPbGhRMrKCQ#fight=1&view=events&start=15890903&end=15896903) 叮呤灵 **死亡(0%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:闪避]：-0.0s 诱导 908K(吸18.9K)→0%
  - [r13@0:36.6](https://www.warcraftlogs.com/reports/DTNp3wMR7jdCnKWr#fight=3&view=events&start=1462850&end=1468850) Paparan **死亡(0%)** [身上:佯攻+闪避 | 大牌就绪:暗影斗篷]：-2.5s 镀流 120K→52% → -2.0s 镀流 120K→38% → -1.5s 镀流 117K→26% → -1.0s 镀流 117K→15% → -0.5s 镀流 93.4K(吸23.4K)→5% → -0.0s 镀流 104K→0%
  - [r02@0:47.0](https://www.warcraftlogs.com/reports/F1vmzABpngjq4rw2#fight=1&view=events&start=6680587&end=6686587) Speedamn **残血(5%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:暗影斗篷/闪避]：+0.0s 诱导 859K(吸71.4K)→5%
  - [r02@0:24.0](https://www.warcraftlogs.com/reports/F1vmzABpngjq4rw2#fight=1&view=events&start=6657493&end=6663493) Speedamn **残血(14%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:暗影斗篷/闪避]：+0.0s 诱导 780K(吸57.8K)→14%
  - [r02@1:23.0](https://www.warcraftlogs.com/reports/F1vmzABpngjq4rw2#fight=1&view=events&start=6716501&end=6722501) Speedamn **残血(14%)** [身上:佯攻+闪避 | 大牌就绪:暗影斗篷]：-2.5s 镀流 61.3K(吸85.8K)→93% → -2.0s 镀流 163K→76% → -1.5s 镀流 145K(吸36.3K)→60% → -1.0s 镀流 145K→44% → -0.5s 镀流 145K→30% → +0.0s 镀流 145K→14%
  - [r04@3:40.6](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=14636810&end=14642810) 黑川茜贼贼 **残血(19%)** [纯裸吃 | 常规就绪:佯攻]：-2.5s 镀流 75.1K(吸67.1K)→92% → -2.0s 镀流 125K(吸32.8K)→82% → -1.5s 镀流 168K→64% → -1.0s 镀流 166K(吸2.03K)→47% → -0.5s 镀流 168K→34% → +0.0s 镀流 166K(吸2.86K)→19%

## ⑤ 免疫 / 清除交互实锤
- 清除实锤：`暗影斗篷` → 提前清掉 `放电(266512)` ×1次（Δt中位 +0ms，已持续 3.7s / 自然20.0s，样本 [r05@0:21.3](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=4474979&end=4480979)）
- 穿透实锤：`闪避` **不免疫** `镀流(266923)`（仍吃中位 116K ×123次，样本 [r01@0:39.2](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=8932445&end=8938445)、[r01@0:39.7](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=8932946&end=8938946)、[r02@1:23.5](https://www.warcraftlogs.com/reports/F1vmzABpngjq4rw2#fight=1&view=events&start=6716999&end=6722999)）
- 穿透实锤：`闪避` **不免疫** `诱导(1290531)`（仍吃中位 573K ×6次，样本 [r01@0:45.8](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=8939008&end=8945008)、[r01@3:04.3](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9077478&end=9083478)、[r04@0:46.5](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=14462704&end=14468704)）
- 免疫实锤：`暗影斗篷` 完全免疫 `诱导力场(1291815)`（0伤 ×3次，样本 [r01@3:27.4](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9100650&end=9106650)、[r01@3:28.0](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9101261&end=9107261)、[r01@3:28.8](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9101975&end=9107975)）
- 免疫实锤：`暗影斗篷` 完全免疫 `诱导(1290531)`（0伤 ×2次，样本 [r01@3:26.9](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9100109&end=9106109)、[r06@3:28.1](https://www.warcraftlogs.com/reports/tBKM3YnmzZFhaLbc#fight=7&view=events&start=4257147&end=4263147)）
— WCL API (v1)：实时请求 0 次，缓存命中 208 次
