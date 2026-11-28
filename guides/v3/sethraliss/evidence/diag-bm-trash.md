$ python3 guides/tools/diag.py trash --runs guides/v3/sethraliss/drafts/hunter-beastmastery/runs.json --class guides/tools/classes/hunter-bm.json --no-wowhead
# 塞塔里斯神庙 · 全本小怪（非 Boss）· 猎人（野兽控制） 极简五维诊断
> 样本：15 场高分限时（+24×1 / +23×14）| 小怪中位总时长 14:12（中位 5 波）| 猎人（野兽控制）中位血量 1.17M

## ① 高频致死 / 高伤小怪技速览（按「怪物名 · 威胁技能」聚合）
- **暴怒云气 · 释放电荷**（ID:1293475，直伤）：纯裸吃中位 796K (68%HP) | 中109 / 免疫7 / 未中0（覆盖15/15场） | **2s内死2次**
- **静电充能 · 火花步**（ID:264763，直伤）：纯裸吃中位 305K (26%HP) | 中284 / 免疫3 / 未中98（覆盖11/15场） | **2s内死2次**
- **宝珠守望者 · 蚀骨践踏**（ID:1303486，DoT）：纯裸吃中位 2.35M (200%HP)(10跳合) | 中70 / 免疫9 / 未中0（覆盖15/15场） | **2s内死1次**
- **群聚三叶虫 · 锯齿冲锋**（ID:1291399，DoT）：纯裸吃中位 1.64M (140%HP)(7跳合) | 中86 / 免疫0 / 未中0（覆盖15/15场） | **2s内死1次**
- **剧毒蝰蛇 · 细胞毒素**（ID:1308148，DoT）：纯裸吃中位 437K (37%HP) | 中83 / 免疫0 / 未中267（覆盖15/15场） | **2s内死2次**
- **倒刺三叶虫 · 锯齿冲锋**（ID:1291399，DoT）：纯裸吃中位 623K (53%HP)(2跳合) | 中44 / 免疫0 / 未中95（覆盖15/15场） | **2s内死1次**
- **沙怒石拳战士 · 震地**（ID:265966，直伤）：纯裸吃中位 839K (71%HP) | 中39 / 免疫7 / 未中0（覆盖15/15场）
- **静电异常体 · 火花步**（ID:264763，直伤）：纯裸吃中位 328K (28%HP) | 中102 / 免疫0 / 未中42（覆盖4/15场）
- **流沙猎手 · 箭雨(1308113)**（ID:1308113，直伤）：纯裸吃中位 0 (0%HP) | 中56 / 免疫11 / 未中189（覆盖15/15场）
- **火花引导者 · 不羁的火花(267483)**（ID:267483，直伤）：纯裸吃中位 1.05M (90%HP) | 中1 / 免疫2 / 未中0（覆盖3/15场） | **2s内死1次**
- **流沙猎手 · 箭雨(1308116)**（ID:1308113/1308116，Debuff）：纯裸吃中位 399K (34%HP)(2跳合) | 中56 / 免疫1 / 未中200（覆盖15/15场）
- **隐秘之牙 · 蜿蜒打击**（ID:1295610/1295635，直伤）：纯裸吃中位 419K (36%HP) | 中50 / 免疫0 / 未中186（覆盖15/15场）
- **灌注能量的唤雷者 · 灌能传导**（ID:1296045/1296052，DoT）：纯裸吃中位 236K (20%HP) | 中37 / 免疫0 / 未中95（覆盖15/15场）
- **塞塔里斯之眼 · 能量虹吸**（ID:1303596，DoT）：纯裸吃中位 254K (22%HP) | 中37 / 免疫0 / 未中0（覆盖13/15场）
- **育巢者 · 毒箭**（ID:1310683，直伤）：纯裸吃中位 711K (61%HP) | 中5 / 免疫0 / 未中16（覆盖4/15场）

## ② 小怪手牌与控断预算账
- **优胜劣汰**（常规）：实际CD 7s(实测最小7.1s) | 小怪场均 8.60次（共129次，15/15场；全本共241次）
- **灵龟守护**（大牌）：实际CD 124s(实测最小124.3s) | 小怪场均 2.00次（共30次，15/15场；全本共44次）
- 功能/应急/控断牌（小怪战）：意气风发 3.13次/场(共47次,15/15场) | 逃脱 2.40次/场(共36次,14/15场) | 猎豹守护 2.13次/场(共32次,15/15场) | 反制射击 10.47次/场(共157次,15/15场) | 胁迫 1.87次/场(共28次,12/15场) | 冰冻陷阱 1.87次/场(共28次,12/15场) | 宁神射击 4.80次/场(共72次,11/15场) | 束缚射击 0.20次/场(共3次,2/15场) | 误导 3.73次/场(共56次,5/15场) | 原始暴怒 0.67次/场(共10次,5/15场) | 治疗宠物 0.13次/场(共2次,2/15场)
- 打断实锤（共 124 次，场均 8.3 次）：`灌注能量的唤雷者:闪电箭(1291262)` ×61 | `风暴能手:闪电箭(1291262)` ×28 | `无信征服者:扰乱心智(1293307)` ×22 | `育巢者:毒箭(1310683)` ×12 | `扭曲的妖术师:烈焰震击(268013)` ×1

## ③ 正例 vs 反例对照（Top 12 高威胁小怪技，含被动盾与外减隔离 + WCL 锚点）
- **暴怒云气 · 释放电荷**（中/免疫116，未中0）
  - 正例·常规(优胜劣汰×27)：27次 | 起手100%(低67%) → 剩血55%(低14%) | 叠伤14/27
  - 正例·大牌(灵龟守护×8)：8次 | 起手78%(低78%) → 剩血6%(低6%) | 免疫7次，叠伤4/8
  - 其他覆盖(集结呐喊×5/作茧缚命×4/牺牲祝福×4/反魔法领域×2)：17次 | 起手100%(低78%) → 剩血48%(低0%) | **2s内死1次**，叠伤10/17
  - 反例A·纯裸吃就绪未交：64次 | 起手100%(低79%) → 剩血29%(低6%) | **2s内死1次**，叠伤22/64，最危:[r14@18:15.2](https://www.warcraftlogs.com/reports/Xf3rJT9kAWn7cBj1#fight=1&view=events&start=1090167&end=1096167) (100%→6%[无外减])
- **静电充能 · 火花步**（中/免疫287，未中98）
  - 正例·常规(优胜劣汰×29)：29次 | 起手100%(低53%) → 剩血83%(低36%) | 叠伤12/29
  - 正例·大牌(灵龟守护×9)：9次 | 起手100%(低92%) → 剩血74%(低66%) | 免疫3次，叠伤1/9
  - 其他覆盖(集结呐喊×12/牺牲祝福×6/外部保护×3/反魔法领域×1)：22次 | 起手100%(低50%) → 剩血80%(低27%) | **2s内死1次**，叠伤7/22
  - 反例A·纯裸吃就绪未交：227次 | 起手100%(低7%) → 剩血72%(低0%) | **2s内死1次**，叠伤32/227，最危:[r12@17:51.5](https://www.warcraftlogs.com/reports/rMj1DR4Jc7knBvXY#fight=11&view=events&start=4472687&end=4478687) (33%→3%[无外减])
- **宝珠守望者 · 蚀骨践踏**（中/免疫79，未中0）
  - 正例·常规(优胜劣汰×30)：30次 | 起手100%(低99%) → 剩血51%(低19%)
  - 正例·大牌(灵龟守护×10)：10次 | 起手100%(低100%) → 剩血0%(低0%) | 免疫9次，**2s内死1次**
  - 其他覆盖(灵魂链接×2/作茧缚命×1/作茧缚命+集结呐喊×1)：4次 | 起手100%(低95%) → 剩血39%(低17%) | 叠伤2/4
  - 反例A·纯裸吃就绪未交：35次 | 起手100%(低94%) → 剩血38%(低15%) | 叠伤2/35，最危:[r15@25:39.2](https://www.warcraftlogs.com/reports/9MarxmXNzvR1HLWw#fight=25&view=events&start=14202662&end=14208662) (100%→15%[盾吸314K])
- **群聚三叶虫 · 锯齿冲锋**（中/免疫86，未中0）
  - 正例·常规(优胜劣汰×21)：21次 | 起手100%(低76%) → 剩血45%(低13%) | 叠伤2/21
  - 其他覆盖(作茧缚命×2/集结呐喊×2/灵魂链接×2/牺牲祝福×1)：7次 | 起手100%(低77%) → 剩血38%(低9%) | 叠伤2/7
  - 反例A·纯裸吃就绪未交：58次 | 起手100%(低70%) → 剩血52%(低18%) | **2s内死1次**，叠伤6/58，最危:[r08@6:34.8](https://www.warcraftlogs.com/reports/mty8v7KBjLpJRbP4#fight=16&view=events&start=24374825&end=24380825) (100%→18%[盾吸345K])
- **剧毒蝰蛇 · 细胞毒素**（中/免疫83，未中267）
  - 正例·常规(优胜劣汰×3)：3次 | 起手85%(低63%) → 剩血44%(低39%) | 叠伤2/3
  - 其他覆盖(集结呐喊×1/灵魂链接×1)：2次 | 起手100%(低100%) → 剩血48%(低28%)
  - 反例A·纯裸吃就绪未交：78次 | 起手100%(低56%) → 剩血64%(低0%) | **2s内死2次**，叠伤9/78，最危:[r04@7:20.8](https://www.warcraftlogs.com/reports/4bkHAZT9Bhfntamr#fight=17&view=events&start=11177864&end=11183864) (56%→21%[无外减])
- **倒刺三叶虫 · 锯齿冲锋**（中/免疫44，未中95）
  - 正例·常规(优胜劣汰×20)：20次 | 起手100%(低58%) → 剩血41%(低20%) | 叠伤8/20
  - 正例·大牌(灵龟守护×2)：2次 | 起手100%(低100%) → 剩血63%(低61%) | 叠伤1/2
  - 其他覆盖(牺牲祝福×1)：1次 | 起手100%(低100%) → 剩血39%(低39%) | 叠伤1/1
  - 反例A·纯裸吃就绪未交：21次 | 起手100%(低69%) → 剩血49%(低0%) | **2s内死1次**，叠伤5/21，最危:[r08@0:23.0](https://www.warcraftlogs.com/reports/mty8v7KBjLpJRbP4#fight=16&view=events&start=24002935&end=24008935) (100%→23%[无外减])
- **沙怒石拳战士 · 震地**（中/免疫46，未中0）
  - 正例·常规(优胜劣汰×24)：24次 | 起手100%(低74%) → 剩血60%(低23%) | 免疫3次，叠伤10/24
  - 正例·大牌(灵龟守护×4)：4次 | 起手85%(低85%) → 剩血19%(低19%) | 免疫3次，叠伤3/4
  - 其他覆盖(集结呐喊×2/牺牲祝福×2)：4次 | 起手91%(低80%) → 剩血34%(低16%) | 叠伤3/4
  - 反例A·纯裸吃就绪未交：14次 | 起手100%(低100%) → 剩血31%(低19%) | 免疫1次，叠伤1/14，最危:[r13@1:24.4](https://www.warcraftlogs.com/reports/6vqwKjN1W27rXVbP#fight=6&view=events&start=4897568&end=4903568) (100%→19%[无外减])
- **静电异常体 · 火花步**（中/免疫102，未中42）
  - 正例·常规(优胜劣汰×16)：16次 | 起手100%(低76%) → 剩血80%(低58%) | 叠伤4/16
  - 其他覆盖(作茧缚命×6/反魔法领域×2)：8次 | 起手100%(低49%) → 剩血67%(低18%) | 叠伤1/8
  - 反例A·纯裸吃就绪未交：78次 | 起手100%(低40%) → 剩血66%(低4%) | 叠伤11/78，最危:[r01@19:32.9](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=10738848&end=10744848) (40%→4%[无外减])
- **流沙猎手 · 箭雨(1308113)**（中/免疫67，未中189）
  - 正例·常规(优胜劣汰×2)：2次 | 起手— → 剩血—
  - 正例·大牌(灵龟守护×1)：1次 | 起手— → 剩血— | 免疫1次
  - 其他覆盖(集结呐喊×5/作茧缚命×1)：6次 | 起手— → 剩血—
  - 反例A·纯裸吃就绪未交：58次 | 起手— → 剩血— | 免疫10次，叠伤2/58
- **火花引导者 · 不羁的火花(267483)**（中/免疫3，未中0）
  - 正例·大牌(灵龟守护×2)：2次 | 起手— → 剩血— | 免疫2次
  - 反例A·纯裸吃就绪未交：1次 | 起手20%(低20%) → 剩血0%(低0%) | **2s内死1次**，最危:[r09@23:41.8](https://www.warcraftlogs.com/reports/YzFTRXVKZQPNpgtG#fight=1&view=events&start=2731198&end=2737198) (20%→0%[无外减])
- **流沙猎手 · 箭雨(1308116)**（中/免疫57，未中200）
  - 正例·常规(优胜劣汰×4)：4次 | 起手97%(低83%) → 剩血61%(低12%) | 叠伤1/4
  - 其他覆盖(集结呐喊×5/作茧缚命×1)：6次 | 起手100%(低39%) → 剩血74%(低20%) | 叠伤2/6
  - 反例A·纯裸吃就绪未交：47次 | 起手100%(低67%) → 剩血71%(低17%) | 免疫1次，叠伤10/47，最危:[r13@6:33.2](https://www.warcraftlogs.com/reports/6vqwKjN1W27rXVbP#fight=6&view=events&start=5206440&end=5212440) (81%→17%[盾吸208K])
- **隐秘之牙 · 蜿蜒打击**（中/免疫50，未中186）
  - 正例·常规(优胜劣汰×4)：4次 | 起手100%(低84%) → 剩血86%(低57%) | 叠伤1/4
  - 正例·大牌(灵龟守护×3)：3次 | 起手91%(低65%) → 剩血73%(低29%) | 叠伤3/3
  - 其他覆盖(集结呐喊×4)：4次 | 起手100%(低40%) → 剩血67%(低13%) | 叠伤2/4
  - 反例A·纯裸吃就绪未交：39次 | 起手100%(低55%) → 剩血63%(低19%) | 叠伤13/39，最危:[r06@1:36.4](https://www.warcraftlogs.com/reports/vtQrhmG1dgp87wMY#fight=2&view=events&start=334435&end=340435) (55%→19%[无外减])

## ④ 小怪死点 & 残血（<20% HP）前 5 秒连招
- 总计：**死亡 6 次 / 残血(<20%) 32 次**（覆盖 15 场）
- 高频连招模式：`释放电荷` ×4 | `蚀骨践踏` ×3 | `火花步 + 释放电荷` ×3 | `毒箭` ×2 | `火花步 + 极其锋利的海贝 + 释放电荷` ×2 | `火花步 + 释放电荷 + 火花步` ×2
  - [r01@27:06.5](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=11192442&end=11198442) Banshers **死亡(0%)** [身上:灵龟守护 | 常规就绪:优胜劣汰]：-4.0s 蚀骨践踏 202K→30% → -3.0s 蚀骨践踏 202K→17% → -2.0s 蚀骨践踏 201K→7% → -1.0s 蚀骨践踏 199K→7% → -0.0s 蚀骨践踏 82.4K→0%
  - [r04@7:21.5](https://www.warcraftlogs.com/reports/4bkHAZT9Bhfntamr#fight=17&view=events&start=11178561&end=11184561) 纯变态 **死亡(0%)** [纯裸吃 | 常规就绪:优胜劣汰]：-4.0s 锯齿冲锋 261K→74% → -3.0s 锯齿冲锋 261K→65% → -2.0s 锯齿冲锋 261K→74% → -1.0s 锯齿冲锋 261K→50% → -0.7s 细胞毒素 350K(吸96.0K)→21% → -0.0s 锯齿冲锋 241K→0%
  - [r05@17:46.0](https://www.warcraftlogs.com/reports/8axZjYzCmTfqk2QL#fight=1&view=events&start=12287394&end=12293394) 月丶镀月光 **死亡(0%)** [身上:外减:外部保护 | 常规就绪:优胜劣汰，大牌就绪:灵龟守护]：-0.6s 火花步 225K(吸63.1K)→79% → -0.0s 释放电荷 828K(吸1.80K)→0%
  - [r08@6:39.4](https://www.warcraftlogs.com/reports/mty8v7KBjLpJRbP4#fight=16&view=events&start=24379347&end=24385347) Anuanlr **死亡(0%)** [纯裸吃 | 常规就绪:优胜劣汰，大牌就绪:灵龟守护]：-3.5s 锯齿冲锋 233K(吸1.15K)→78% → -2.5s 锯齿冲锋 175K(吸46.8K)→83% → -1.5s 锯齿冲锋 221K(吸1.51K)→64% → -1.0s 细胞毒素 325K(吸42.9K)→34% → -0.5s 锯齿冲锋 220K(吸3.00K)→18% → -0.0s 细胞毒素 187K→0%
  - [r09@23:41.8](https://www.warcraftlogs.com/reports/YzFTRXVKZQPNpgtG#fight=1&view=events&start=2731226&end=2737226) 无念 **死亡(0%)** [纯裸吃 | 常规就绪:优胜劣汰]：-0.0s 不羁的火花 1.05M→0%
  - [r12@16:26.4](https://www.warcraftlogs.com/reports/rMj1DR4Jc7knBvXY#fight=11&view=events&start=4387635&end=4393635) Talent **死亡(0%)** [纯裸吃 | 常规就绪:优胜劣汰]：-2.4s 火花步 253K(吸43.0K)→75% → -1.1s 释放电荷 804K→7% → -0.0s 火花步 68.3K(吸3.90K)→0%
  - [r12@17:51.5](https://www.warcraftlogs.com/reports/rMj1DR4Jc7knBvXY#fight=11&view=events&start=4472687&end=4478687) Talent **残血(3%)** [纯裸吃 | 常规就绪:优胜劣汰]：-0.7s 释放电荷 725K(吸61.4K)→29% → +0.0s 火花步 310K(吸2.97K)→3%
  - [r01@19:32.9](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=10738848&end=10744848) Banshers **残血(4%)** [纯裸吃 | 常规就绪:优胜劣汰，大牌就绪:灵龟守护]：-3.2s 火花步 353K→54% → -0.7s 释放电荷 817K(吸133K)→18% → +0.0s 火花步 353K→4%
  - [r14@18:15.2](https://www.warcraftlogs.com/reports/Xf3rJT9kAWn7cBj1#fight=1&view=events&start=1090167&end=1096167) Yootoo **残血(6%)** [纯裸吃 | 常规就绪:优胜劣汰，大牌就绪:灵龟守护]：-2.2s 火花步 227K(吸80.9K)→79% → -0.4s 极其锋利的海贝 128(吸1.54K)→100% → +0.0s 释放电荷 1.01M(吸953)→6%
  - [r15@17:17.6](https://www.warcraftlogs.com/reports/9MarxmXNzvR1HLWw#fight=25&view=events&start=13701030&end=13707030) 荒野之息 **残血(6%)** [身上:灵龟守护 | 常规就绪:优胜劣汰]：-0.2s 火花步 232K(吸43.4K)→78% → +0.0s 释放电荷 743K(吸1.70K)→6%
  - [r15@16:54.5](https://www.warcraftlogs.com/reports/9MarxmXNzvR1HLWw#fight=25&view=events&start=13677946&end=13683946) 荒野之息 **残血(6%)** [纯裸吃 | 常规就绪:优胜劣汰，大牌就绪:灵龟守护]：-5.0s 火花步 162K(吸22.8K)→84% → -2.4s 灌能传导 233K(吸22.2K)→78% → -1.4s 火花步 309K(吸1.67K)→70% → +0.0s 释放电荷 840K(吸1.92K)→6%
  - [r05@18:18.4](https://www.warcraftlogs.com/reports/8axZjYzCmTfqk2QL#fight=1&view=events&start=12319880&end=12325880) 月丶镀月光 **残血(9%)** [身上:灵龟守护 | 常规就绪:优胜劣汰]：-2.2s 极其锋利的海贝 0(吸1.48K) → -1.2s 极其锋利的海贝 0(吸1.48K) → -1.0s 灌能传导 209K(吸21.3K)→48% → -0.5s 火花步 257K(吸27.1K)→31% → -0.1s 极其锋利的海贝 1.50K→31% → +0.0s 灌能传导 233K→9%

## ⑤ 免疫 / 清除 / 解控 / 驱散交互实锤
- 驱散实锤：`宁神射击` → 驱散 `积攒电荷(1310739)` ×75次（自驱 0 / 驱队友 75，样本 [r01@17:37.9](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=10623837&end=10629837)、[r01@17:53.5](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=10639359&end=10645359)、[r01@17:53.5](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=10639434&end=10645434)）
- 驱散实锤：`紧急药膏` → 驱散 `细胞毒素(1308148)` ×46次（自驱 46 / 驱队友 0，样本 [r01@11:48.2](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=10274129&end=10280129)、[r02@6:15.7](https://www.warcraftlogs.com/reports/fAvBRtjbKxGqdMWL#fight=185&view=events&start=234423457&end=234429457)、[r02@6:56.6](https://www.warcraftlogs.com/reports/fAvBRtjbKxGqdMWL#fight=185&view=events&start=234464368&end=234470368)）
- 驱散实锤：`逃脱` → 驱散 `极化力场(273274)` ×2次（自驱 2 / 驱队友 0，样本 [r01@24:42.4](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=11048257&end=11054257)、[r14@23:36.1](https://www.warcraftlogs.com/reports/Xf3rJT9kAWn7cBj1#fight=1&view=events&start=1411064&end=1417064)）
- 清除实锤：`逃脱` → 提前清掉 `极化力场(273274)` ×2次（Δt中位 +0ms，已持续 0.8s / 自然2.6s，样本 [r01@24:42.4](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=11048257&end=11054257)、[r14@23:36.1](https://www.warcraftlogs.com/reports/Xf3rJT9kAWn7cBj1#fight=1&view=events&start=1411064&end=1417064)）
- （已排除伪清除：`灵龟守护` 旁 `细胞毒素` 消失 ×1次，实为队友驱散）
- 免疫实锤：`灵龟守护` 完全免疫 `蚀骨践踏(1303486)`（0伤 ×9次，样本 [r02@23:12.9](https://www.warcraftlogs.com/reports/fAvBRtjbKxGqdMWL#fight=185&view=events&start=235440622&end=235446622)、[r02@25:32.1](https://www.warcraftlogs.com/reports/fAvBRtjbKxGqdMWL#fight=185&view=events&start=235579812&end=235585812)、[r03@23:34.8](https://www.warcraftlogs.com/reports/q34DNjVBPxznT7Yr#fight=9&view=events&start=8730471&end=8736471)）
- 免疫实锤：`灵龟守护` 完全免疫 `释放电荷(1293475)`（0伤 ×7次，样本 [r02@18:03.4](https://www.warcraftlogs.com/reports/fAvBRtjbKxGqdMWL#fight=185&view=events&start=235131143&end=235137143)、[r03@16:27.8](https://www.warcraftlogs.com/reports/q34DNjVBPxznT7Yr#fight=9&view=events&start=8303479&end=8309479)、[r06@17:18.5](https://www.warcraftlogs.com/reports/vtQrhmG1dgp87wMY#fight=2&view=events&start=1276512&end=1282512)）
- 免疫实锤：`灵龟守护` 完全免疫 `不羁的火花(267483)`（0伤 ×6次，样本 [r01@24:43.6](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=11049496&end=11055496)、[r09@16:31.4](https://www.warcraftlogs.com/reports/YzFTRXVKZQPNpgtG#fight=1&view=events&start=2300801&end=2306801)、[r09@23:26.5](https://www.warcraftlogs.com/reports/YzFTRXVKZQPNpgtG#fight=1&view=events&start=2715892&end=2721892)）
- 免疫实锤：`灵龟守护` 完全免疫 `不羁的火花(1225638)`（0伤 ×6次，样本 [r01@24:43.6](https://www.warcraftlogs.com/reports/LWVXMkN8n3hACQrt#fight=10&view=events&start=11049496&end=11055496)、[r09@16:31.4](https://www.warcraftlogs.com/reports/YzFTRXVKZQPNpgtG#fight=1&view=events&start=2300801&end=2306801)、[r09@23:26.5](https://www.warcraftlogs.com/reports/YzFTRXVKZQPNpgtG#fight=1&view=events&start=2715892&end=2721892)）
- 免疫实锤：`灵龟守护` 完全免疫 `震地(265966)`（0伤 ×3次，样本 [r03@0:36.3](https://www.warcraftlogs.com/reports/q34DNjVBPxznT7Yr#fight=9&view=events&start=7351973&end=7357973)、[r11@0:40.7](https://www.warcraftlogs.com/reports/c2wB9tvFMrqm3yJg#fight=29&view=events&start=15330077&end=15336077)、[r12@1:46.2](https://www.warcraftlogs.com/reports/rMj1DR4Jc7knBvXY#fight=11&view=events&start=3507415&end=3513415)）
- 穿透实锤：`灵龟守护` **不免疫** `灌能传导(1296052)`（仍吃中位 163K ×3次，样本 [r05@18:19.5](https://www.warcraftlogs.com/reports/8axZjYzCmTfqk2QL#fight=1&view=events&start=12320892&end=12326892)、[r05@18:20.5](https://www.warcraftlogs.com/reports/8axZjYzCmTfqk2QL#fight=1&view=events&start=12321890&end=12327890)、[r06@17:18.3](https://www.warcraftlogs.com/reports/vtQrhmG1dgp87wMY#fight=2&view=events&start=1276312&end=1282312)）
- 免疫实锤：`灵龟守护` 完全免疫 `火花步(264763)`（0伤 ×2次，样本 [r02@18:02.8](https://www.warcraftlogs.com/reports/fAvBRtjbKxGqdMWL#fight=185&view=events&start=235130583&end=235136583)、[r03@16:28.3](https://www.warcraftlogs.com/reports/q34DNjVBPxznT7Yr#fight=9&view=events&start=8303993&end=8309993)）
- 穿透实锤：`灵龟守护` **不免疫** `锯齿冲锋(1291399)`（仍吃中位 137K ×1次，样本 [r03@0:36.7](https://www.warcraftlogs.com/reports/q34DNjVBPxznT7Yr#fight=9&view=events&start=7352427&end=7358427)）
- 免疫实锤：`灵龟守护` 完全免疫 `箭雨(1308113)`（0伤 ×1次，样本 [r09@1:23.8](https://www.warcraftlogs.com/reports/YzFTRXVKZQPNpgtG#fight=1&view=events&start=1393181&end=1399181)）
- 免疫实锤：`灵龟守护` 完全免疫 `乱射(273225)`（0伤 ×1次，样本 [r09@6:11.6](https://www.warcraftlogs.com/reports/YzFTRXVKZQPNpgtG#fight=1&view=events&start=1681015&end=1687015)）
— WCL API (v1)：实时请求 1 次，缓存命中 192 次；v1 限额剩余 787/800 次
