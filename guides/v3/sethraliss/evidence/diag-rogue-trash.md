$ python3 guides/tools/diag.py trash --runs guides/v3/sethraliss/drafts/rogue-subtlety/runs.json --class guides/tools/classes/rogue-sub.json
# 塞塔里斯神庙 · 全本小怪（非 Boss）· 潜行者（敏锐） 极简五维诊断
> 样本：15 场高分限时（+24×15）| 小怪中位总时长 14:01（中位 5 波）| 潜行者（敏锐）中位血量 1.06M

## ① 高频致死 / 高伤小怪技速览（按「怪物名 · 威胁技能」聚合）
- **宝珠守望者 · 蚀骨践踏**（ID:1303486，DoT）：纯裸吃中位 2.76M (260%HP)(10跳合) | 中67 / 免疫13 / 未中1（覆盖15/15场） | **2s内死1次** — *该生物猛踏地面，喷发出一股烈毒新星，对60码范围内的玩家造成116379点自然伤害，并且每1…*
- **闪电毒蛇 · 萦绕风暴**（ID:1293133，DoT）：纯裸吃中位 0 (0%HP) | 中301 / 免疫3 / 未中0（覆盖15/15场） — *每1.5秒造成96982点自然伤害。*
- **暴怒云气 · 释放电荷**（ID:1293475，直伤）：纯裸吃中位 930K (88%HP) | 中116 / 免疫6 / 未中0（覆盖15/15场） — *释放由积攒电荷积聚的所有能量，对所有玩家造成145474点自然伤害。*
- **群聚三叶虫 · 锯齿冲锋**（ID:1291399，DoT）：纯裸吃中位 649K (61%HP)(2跳合) | 中105 / 免疫0 / 未中0（覆盖15/15场） — *该生物向一名敌人冲锋，造成58189点物理伤害，并使其流血，在6秒内每1秒额外造成38793…*
- **流沙猎手 · 箭雨(1308113)**（ID:1308113，直伤）：纯裸吃中位 0 (0%HP) | 中56 / 免疫13 / 未中169（覆盖15/15场） — *施法者朝一名玩家发射连珠箭，每0.8秒造成43642点物理伤害，持续9秒。*
- **剧毒蝰蛇 · 细胞毒素**（ID:1308148，DoT）：纯裸吃中位 643K (61%HP)(2跳合) | 中91 / 免疫1 / 未中253（覆盖15/15场） — *施法者向一名玩家注射细胞毒素，造成72737点自然伤害，并且每1秒额外造成38793点自然伤…*
- **环境 · Falling**（ID:3，直伤）：纯裸吃中位 908K (85%HP) | 中1 / 免疫0 / 未中0（覆盖1/15场） | **2s内死1次** — *Word of Mass Recall (OLD) 10法力值 20秒 施法时间*
- **沙怒石拳战士 · 震地**（ID:265966，直伤）：纯裸吃中位 815K (77%HP) | 中52 / 免疫0 / 未中0（覆盖15/15场） — *施法者猛击地面，其巨大的力量会将60码范围内的所有敌人击退，并造成156627点物理伤害。*
- **塞塔里斯之眼 · 能量虹吸**（ID:1303596，DoT）：纯裸吃中位 0 (0%HP) | 中86 / 免疫0 / 未中0（覆盖15/15场） — *塞塔里斯之眼从60码内最近的玩家身上汲取能量，每1秒造成4点自然伤害。*
- **流沙猎手 · 箭雨(1308116)**（ID:1308113/1308116，Debuff）：纯裸吃中位 427K (40%HP)(3跳合) | 中53 / 免疫1 / 未中185（覆盖15/15场） — *施法者朝一名玩家发射连珠箭，每0.8秒造成43642点物理伤害，持续9秒。*
- **隐秘之牙 · 蜿蜒打击**（ID:1295610/1295635，直伤）：纯裸吃中位 444K (42%HP) | 中43 / 免疫0 / 未中198（覆盖15/15场） — *施法者传送到一名玩家处并发动打击，造成67888点自然伤害。*
- **倒刺三叶虫 · 锯齿冲锋**（ID:1291399，DoT）：纯裸吃中位 663K (62%HP)(2跳合) | 中31 / 免疫0 / 未中94（覆盖15/15场） — *该生物向一名敌人冲锋，造成58189点物理伤害，并使其流血，在6秒内每1秒额外造成38793…*
- **育巢者 · 毒箭**（ID:1310683，直伤）：纯裸吃中位 830K (78%HP) | 中4 / 免疫0 / 未中22（覆盖4/15场） — *施法者对一名玩家造成116379点自然伤害。*
- **灌注能量的唤雷者 · 闪电箭**（ID:1291262，直伤）：纯裸吃中位 792K (75%HP) | 中1 / 免疫0 / 未中14（覆盖1/15场） — *Inflicts 116379 Nature damage to an enemy.*
- **灌注能量的唤雷者 · 灌能传导**（ID:1296045/1296052，DoT）：纯裸吃中位 0 (0%HP) | 中35 / 免疫0 / 未中93（覆盖15/15场） — *施法者向玩家体内输送电流，在20秒内每1秒造成42672点自然伤害。 如果灌能传导结束，传导…*

## ② 小怪手牌与控断预算账
- **佯攻**（常规）：实际CD 5s(实测最小5.0s) | 小怪场均 29.27次（共439次，15/15场；全本共986次）
- **暗影斗篷**（大牌）：实际CD 121s(实测最小121.3s) | 小怪场均 2.33次（共35次，14/15场；全本共100次）
- **闪避**（大牌）：实际CD 120s(实测最小120.0s) | 小怪场均 3.40次（共51次，15/15场；全本共99次）
- 功能/应急/控断牌（小怪战）：猩红之瓶 1.00次/场(共15次,8/15场) | 消失 1.20次/场(共18次,7/15场) | 暗影步 8.67次/场(共130次,15/15场) | 疾跑 4.73次/场(共71次,15/15场) | 嫁祸诀窍 4.40次/场(共66次,13/15场) | 脚踢 20.27次/场(共304次,15/15场) | 致盲 2.13次/场(共32次,14/15场) | 肾击 0.80次/场(共12次,9/15场) | 毒刃 0.53次/场(共8次,2/15场) | 扰乱 0.07次/场(共1次,1/15场)
- 打断实锤（共 265 次，场均 17.7 次）：`灌注能量的唤雷者:闪电箭(1291262)` ×110 | `育巢者:毒箭(1310683)` ×65 | `风暴能手:闪电箭(1291262)` ×45 | `无信征服者:扰乱心智(1293307)` ×45

## ③ 正例 vs 反例对照（Top 12 高威胁小怪技，含被动盾与外减隔离 + WCL 锚点）
- **宝珠守望者 · 蚀骨践踏**（中/免疫80，未中1）
  - 正例·常规(佯攻×49)：49次 | 起手100%(低100%) → 剩血45%(低12%) | **2s内死1次**，叠伤2/49
  - 正例·大牌(佯攻+闪避×16/暗影斗篷×10/佯攻+暗影斗篷×2/闪避×1/暗影斗篷+闪避×1)：30次 | 起手100%(低99%) → 剩血56%(低33%) | 免疫13次
  - 反例A·纯裸吃就绪未交：1次 | 起手100%(低100%) → 剩血42%(低42%) | 最危:[r04@26:10.9](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=14814409&end=14820409) (100%→42%[盾吸1.04M])
- **闪电毒蛇 · 萦绕风暴**（中/免疫304，未中0）
  - 正例·常规(佯攻×59)：59次 | 起手— → 剩血—
  - 正例·大牌(闪避×12/暗影斗篷×8/佯攻+闪避×8/佯攻+暗影斗篷×1)：29次 | 起手100%(低100%) → 剩血65%(低65%) | 免疫3次，叠伤3/29
  - 其他覆盖(集结呐喊×11/牺牲祝福×3/作茧缚命×2/灵魂链接×1)：18次 | 起手— → 剩血—
  - 反例A·纯裸吃就绪未交：198次 | 起手100%(低91%) → 剩血45%(低28%) | 叠伤5/198，最危:[r15@8:44.6](https://www.warcraftlogs.com/reports/Xra2gck8z4dD1VvF#fight=1&view=events&start=10348680&end=10354680) (100%→28%[无外减])
- **暴怒云气 · 释放电荷**（中/免疫122，未中0）
  - 正例·常规(佯攻×104)：104次 | 起手100%(低79%) → 剩血57%(低15%) | 叠伤7/104
  - 正例·大牌(暗影斗篷×6/闪避×3/佯攻+闪避×3/佯攻+暗影斗篷×1)：13次 | 起手100%(低100%) → 剩血62%(低15%) | 免疫6次
  - 其他覆盖(集结呐喊×3)：3次 | 起手100%(低100%) → 剩血59%(低29%)
  - 反例A·纯裸吃就绪未交：2次 | 起手100%(低100%) → 剩血61%(低55%) | 最危:[r07@15:39.4](https://www.warcraftlogs.com/reports/vwJN42fQXTk9Am83#fight=4&view=events&start=2224310&end=2230310) (100%→55%[盾吸696K])
- **群聚三叶虫 · 锯齿冲锋**（中/免疫105，未中0）
  - 正例·常规(佯攻×69)：69次 | 起手100%(低89%) → 剩血57%(低5%) | 叠伤11/69
  - 正例·大牌(佯攻+闪避×12/佯攻+暗影斗篷×3/闪避×2/暗影斗篷×1)：18次 | 起手100%(低100%) → 剩血61%(低13%) | 叠伤3/18
  - 其他覆盖(集结呐喊×2)：2次 | 起手100%(低100%) → 剩血64%(低45%)
  - 反例A·纯裸吃就绪未交：16次 | 起手100%(低100%) → 剩血66%(低26%) | 叠伤1/16，最危:[r07@8:20.8](https://www.warcraftlogs.com/reports/vwJN42fQXTk9Am83#fight=4&view=events&start=1785703&end=1791703) (100%→26%[盾吸209K])
- **流沙猎手 · 箭雨(1308113)**（中/免疫69，未中169）
  - 正例·常规(佯攻×9)：9次 | 起手— → 剩血— | 免疫4次，叠伤3/9
  - 正例·大牌(闪避×2/佯攻+暗影斗篷×1/暗影斗篷×1/佯攻+闪避×1)：5次 | 起手— → 剩血— | 免疫4次，叠伤1/5
  - 其他覆盖(集结呐喊×5/牺牲祝福×1)：6次 | 起手— → 剩血—
  - 反例A·纯裸吃就绪未交：49次 | 起手— → 剩血— | 免疫5次，叠伤3/49
- **剧毒蝰蛇 · 细胞毒素**（中/免疫92，未中253）
  - 正例·常规(佯攻×30)：30次 | 起手100%(低73%) → 剩血61%(低18%) | 叠伤9/30
  - 正例·大牌(佯攻+闪避×3/暗影斗篷×2/闪避×1/佯攻+暗影斗篷×1)：7次 | 起手100%(低69%) → 剩血65%(低51%) | 免疫1次，叠伤3/7
  - 其他覆盖(灵魂链接×1)：1次 | 起手100%(低100%) → 剩血65%(低65%)
  - 反例A·纯裸吃就绪未交：54次 | 起手100%(低75%) → 剩血59%(低20%) | 叠伤3/54，最危:[r15@7:00.6](https://www.warcraftlogs.com/reports/Xra2gck8z4dD1VvF#fight=1&view=events&start=10244722&end=10250722) (75%→20%[无外减])
- **环境 · Falling**（中/免疫1，未中0）
  - 反例A·纯裸吃就绪未交：1次 | 起手100%(低100%) → 剩血0%(低0%) | **2s内死1次**，最危:[r03@23:12.5](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=1756657&end=1762657) (100%→0%[无外减])
- **沙怒石拳战士 · 震地**（中/免疫52，未中0）
  - 正例·常规(佯攻×36)：36次 | 起手100%(低85%) → 剩血60%(低27%) | 叠伤10/36
  - 正例·大牌(佯攻+闪避×10/闪避×2/佯攻+暗影斗篷×1)：13次 | 起手100%(低85%) → 剩血72%(低31%) | 叠伤4/13
  - 其他覆盖(灵魂链接×1)：1次 | 起手97%(低97%) → 剩血12%(低12%)
  - 反例A·纯裸吃就绪未交：2次 | 起手100%(低100%) → 剩血23%(低14%) | 最危:[r04@1:15.4](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=13318983&end=13324983) (100%→14%[无外减])
- **塞塔里斯之眼 · 能量虹吸**（中/免疫86，未中0）
  - 正例·常规(佯攻×14)：14次 | 起手100%(低69%) → 剩血85%(低54%) | 叠伤2/14
  - 正例·大牌(佯攻+暗影斗篷×2)：2次 | 起手— → 剩血—
  - 反例A·纯裸吃就绪未交：70次 | 起手100%(低100%) → 剩血70%(低42%) | 最危:[r08@23:25.7](https://www.warcraftlogs.com/reports/BLmWKxty6VMNvhR4#fight=1&view=events&start=10340772&end=10346772) (100%→42%[无外减])
- **流沙猎手 · 箭雨(1308116)**（中/免疫54，未中185）
  - 正例·常规(佯攻×9)：9次 | 起手100%(低69%) → 剩血82%(低52%) | 叠伤5/9
  - 正例·大牌(佯攻+闪避×1/暗影斗篷×1)：2次 | 起手100%(低100%) → 剩血75%(低75%) | 免疫1次，叠伤1/2
  - 其他覆盖(集结呐喊×3/牺牲祝福×1)：4次 | 起手100%(低100%) → 剩血81%(低61%) | 叠伤1/4
  - 反例A·纯裸吃就绪未交：39次 | 起手100%(低83%) → 剩血78%(低26%) | 叠伤6/39，最危:[r05@0:54.5](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=3358886&end=3364886) (100%→26%[盾吸153K])
- **隐秘之牙 · 蜿蜒打击**（中/免疫43，未中198）
  - 正例·常规(佯攻×11)：11次 | 起手100%(低67%) → 剩血74%(低26%) | 叠伤9/11
  - 正例·大牌(佯攻+闪避×2/闪避×1)：3次 | 起手100%(低100%) → 剩血82%(低80%) | 叠伤2/3
  - 其他覆盖(集结呐喊×2/外部保护×1)：3次 | 起手100%(低82%) → 剩血59%(低37%) | 叠伤1/3
  - 反例A·纯裸吃就绪未交：26次 | 起手100%(低64%) → 剩血65%(低15%) | 叠伤6/26，最危:[r03@0:27.7](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=391853&end=397853) (64%→15%[无外减])
- **倒刺三叶虫 · 锯齿冲锋**（中/免疫31，未中94）
  - 正例·常规(佯攻×15)：15次 | 起手100%(低60%) → 剩血57%(低18%) | 叠伤3/15
  - 正例·大牌(闪避×3/佯攻+闪避×2)：5次 | 起手100%(低100%) → 剩血76%(低58%) | 叠伤1/5
  - 其他覆盖(集结呐喊×1)：1次 | 起手100%(低100%) → 剩血72%(低72%) | 叠伤1/1
  - 反例A·纯裸吃就绪未交：10次 | 起手100%(低100%) → 剩血60%(低42%) | 叠伤1/10，最危:[r13@6:13.8](https://www.warcraftlogs.com/reports/DTNp3wMR7jdCnKWr#fight=3&view=events&start=647390&end=653390) (100%→42%[盾吸176K])

## ④ 小怪死点 & 残血（<20% HP）前 5 秒连招
- 总计：**死亡 2 次 / 残血(<20%) 17 次**（覆盖 15 场）
- 高频连招模式：`蚀骨践踏` ×3 | `虚空侵染外壳符文 + 蚀骨践踏 + 虚空侵染外壳符文` ×3 | `虚空侵染外壳符文 + 释放电荷` ×2 | `锯齿冲锋 + 虚空侵染外壳符文 + 蜿蜒打击` ×1 | `Falling` ×1 | `蜿蜒打击 + 震地` ×1
  - [r03@23:12.5](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=1756687&end=1762687) 叶落初冬 **死亡(0%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:暗影斗篷/闪避]：-0.0s Falling 908K→0%
  - [r09@24:22.0](https://www.warcraftlogs.com/reports/4PZxpvB9dMcD8Jgw#fight=1&view=events&start=12224907&end=12230907) 斗篷小王子 **死亡(0%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:暗影斗篷]：-2.9s 蚀骨践踏 120K(吸2.58K)→42% → -1.9s 蚀骨践踏 206K(吸18.5K)→51% → -1.9s 虚空侵染外壳符文 795→51% → -0.9s 蚀骨践踏 222K(吸2.74K)→47% → -0.9s 虚空侵染外壳符文 795→47% → -0.0s 近战 539K(吸2.89K)→0%
  - [r09@6:33.9](https://www.warcraftlogs.com/reports/4PZxpvB9dMcD8Jgw#fight=1&view=events&start=11156825&end=11162825) 斗篷小王子 **残血(5%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:暗影斗篷/闪避]：-2.0s 锯齿冲锋 125K(吸57.7K)→48% → -1.2s 虚空侵染外壳符文 0(吸640) → -1.0s 锯齿冲锋 120K(吸82.8K)→87% → -0.2s 虚空侵染外壳符文 0(吸795) → -0.1s 萦绕风暴 530K(吸134K)→32% → +0.0s 锯齿冲锋 252K→5%
  - [r05@24:05.3](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=4749634&end=4755634) 霸天横刀 **残血(6%)** [身上:佯攻 | 大牌就绪:暗影斗篷]：-2.0s 蚀骨践踏 242K→24% → -2.0s 虚空侵染外壳符文 880→24% → -1.0s 蚀骨践踏 242K→18% → -1.0s 虚空侵染外壳符文 880→18% → -0.0s 蚀骨践踏 118K→6% → +0.0s 虚空侵染外壳符文 508(吸126)→6%
  - [r04@25:51.7](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=14795265&end=14801265) 黑川茜贼贼 **残血(12%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:闪避]：-5.0s 蚀骨践踏 199K(吸1.52K)→60% → -4.0s 蚀骨践踏 177K(吸18.6K)→55% → -3.0s 蚀骨践踏 227K(吸2.26K)→47% → -2.0s 蚀骨践踏 226K(吸2.50K)→24% → -1.0s 蚀骨践踏 226K(吸3.17K)→33% → +0.0s 蚀骨践踏 229K→12%
  - [r08@1:07.3](https://www.warcraftlogs.com/reports/BLmWKxty6VMNvhR4#fight=1&view=events&start=9002435&end=9008435) 啊晴丶 **残血(12%)** [身上:外减:灵魂链接 | 常规就绪:佯攻，大牌就绪:暗影斗篷]：+0.0s 震地 844K(吸100K)→12%
  - [r15@11:49.6](https://www.warcraftlogs.com/reports/Xra2gck8z4dD1VvF#fight=1&view=events&start=10533668&end=10539668) 等一只七影蝶 **残血(13%)** [身上:佯攻 | 大牌就绪:暗影斗篷/闪避]：-4.0s 锯齿冲锋 157K(吸187K)→83% → -3.0s 锯齿冲锋 253K(吸1.54K)→66% → -2.0s 锯齿冲锋 204K→51% → -1.0s 锯齿冲锋 156K(吸19.8K)→35% → +0.0s 锯齿冲锋 213K(吸3.02K)→13%
  - [r13@11:01.3](https://www.warcraftlogs.com/reports/DTNp3wMR7jdCnKWr#fight=3&view=events&start=934933&end=940933) Paparan **残血(14%)** [身上:佯攻 | 大牌就绪:暗影斗篷]：-1.5s 锯齿冲锋 167K(吸44.4K)→48% → -1.5s 虚空侵染外壳符文 636→60% → -0.6s 细胞毒素 143K(吸2.25K)→84% → -0.5s 锯齿冲锋 165K(吸18.2K)→67% → -0.5s 虚空侵染外壳符文 488(吸122)→67% → +0.0s 毒箭 487K(吸124K)→14%
  - [r04@1:15.4](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=13318983&end=13324983) 黑川茜贼贼 **残血(14%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:暗影斗篷]：-3.8s 蜿蜒打击 176K(吸178K)→80% → +0.0s 震地 776K(吸48.6K)→14%
  - [r10@16:39.3](https://www.warcraftlogs.com/reports/fap9JHybDMvNTcgZ#fight=19&view=events&start=13982813&end=13988813) 弋江水 **残血(15%)** [身上:闪避 | 常规就绪:佯攻，大牌就绪:暗影斗篷]：-4.9s 虚空侵染外壳符文 0(吸841) → -3.9s 虚空侵染外壳符文 0(吸841) → -2.9s 虚空侵染外壳符文 0(吸841) → +0.0s 释放电荷 770K(吸133K)→15%
  - [r03@0:27.7](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=391853&end=397853) 叶落初冬 **残血(15%)** [纯裸吃 | 常规就绪:佯攻，大牌就绪:暗影斗篷/闪避]：-2.1s 虚空侵染外壳符文 841→71% → -1.1s 锯齿冲锋 257K(吸23.7K)→49% → -1.1s 虚空侵染外壳符文 841→49% → -0.1s 锯齿冲锋 238K(吸2.83K)→64% → -0.1s 虚空侵染外壳符文 760→64% → +0.0s 蜿蜒打击 441K(吸2.33K)→15%
  - [r09@17:05.9](https://www.warcraftlogs.com/reports/4PZxpvB9dMcD8Jgw#fight=1&view=events&start=11788827&end=11794827) 斗篷小王子 **残血(15%)** [身上:佯攻 | 大牌就绪:暗影斗篷]：-4.9s 虚空侵染外壳符文 0(吸662) → +0.0s 释放电荷 768K(吸113K)→15%

## ⑤ 免疫 / 清除 / 解控 / 驱散交互实锤
- 驱散实锤：15 场小怪战未检测到玩家主动驱散。
- 清除实锤：`暗影斗篷` → 提前清掉 `细胞毒素(1308148)` ×6次（Δt中位 +0ms，已持续 1.1s / 自然6.8s，样本 [r03@7:07.6](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=791763&end=797763)、[r03@9:16.7](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=920842&end=926842)、[r05@10:59.5](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=3963862&end=3969862)）
- 清除实锤：`暗影斗篷` → 提前清掉 `蚀骨践踏(1303486)` ×2次（Δt中位 +0ms，已持续 3.9s / 自然10.0s，样本 [r06@25:10.0](https://www.warcraftlogs.com/reports/tBKM3YnmzZFhaLbc#fight=7&view=events&start=4388564&end=4394564)、[r08@24:37.8](https://www.warcraftlogs.com/reports/BLmWKxty6VMNvhR4#fight=1&view=events&start=10412896&end=10418896)）
- （已排除伪清除：`暗影斗篷` 旁 `细胞毒素` 消失 ×1次，实为队友驱散）
- 混合交互：`闪避` vs `蚀骨践踏(1303486)`（0伤 ×1次 / 仍掉血 ×154次 中位157K，样本 [r01@24:51.6](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9240861&end=9246861)、[r01@24:52.6](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9241870&end=9247870)、[r01@24:53.7](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9242875&end=9248875)）
- 穿透实锤：`闪避` **不免疫** `锯齿冲锋(1291399)`（仍吃中位 162K ×73次，样本 [r01@6:51.7](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=8160938&end=8166938)、[r01@6:52.7](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=8161942&end=8167942)、[r01@6:53.7](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=8162940&end=8168940)）
- 免疫实锤：`暗影斗篷` 完全免疫 `蚀骨践踏(1303486)`（0伤 ×13次，样本 [r01@24:37.7](https://www.warcraftlogs.com/reports/HG7dTNB6MDVf8hzq#fight=1&view=events&start=9226931&end=9232931)、[r02@24:41.1](https://www.warcraftlogs.com/reports/F1vmzABpngjq4rw2#fight=1&view=events&start=6962872&end=6968872)、[r03@23:41.0](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=1785100&end=1791100)）
- 穿透实锤：`闪避` **不免疫** `震地(265966)`（仍吃中位 462K ×11次，样本 [r04@1:07.0](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=13310494&end=13316494)、[r05@0:36.3](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=3340679&end=3346679)、[r08@0:37.0](https://www.warcraftlogs.com/reports/BLmWKxty6VMNvhR4#fight=1&view=events&start=8972102&end=8978102)）
- 穿透实锤：`暗影斗篷` **不免疫** `锯齿冲锋(1291399)`（仍吃中位 229K ×8次，样本 [r03@7:10.5](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=794629&end=800629)、[r03@7:11.5](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=795639&end=801639)、[r03@7:12.5](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=796637&end=802637)）
- 穿透实锤：`闪避` **不免疫** `释放电荷(1293475)`（仍吃中位 598K ×6次，样本 [r02@17:34.4](https://www.warcraftlogs.com/reports/F1vmzABpngjq4rw2#fight=1&view=events&start=6536180&end=6542180)、[r03@18:06.2](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=1450341&end=1456341)、[r08@17:12.9](https://www.warcraftlogs.com/reports/BLmWKxty6VMNvhR4#fight=1&view=events&start=9968022&end=9974022)）
- 免疫实锤：`暗影斗篷` 完全免疫 `释放电荷(1293475)`（0伤 ×6次，样本 [r03@16:49.3](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=1373485&end=1379485)、[r05@16:05.5](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=4269869&end=4275869)、[r06@17:25.0](https://www.warcraftlogs.com/reports/tBKM3YnmzZFhaLbc#fight=7&view=events&start=3923470&end=3929470)）
- 穿透实锤：`闪避` **不免疫** `细胞毒素(1308148)`（仍吃中位 181K ×5次，样本 [r03@10:35.0](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=999157&end=1005157)、[r04@11:04.0](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=13907508&end=13913508)、[r12@7:10.9](https://www.warcraftlogs.com/reports/7N92JyPbGhRMrKCQ#fight=1&view=events&start=15093719&end=15099719)）
- 混合交互：`暗影斗篷` vs `萦绕风暴(1293133)`（0伤 ×3次 / 仍掉血 ×1次 中位635K，样本 [r04@10:52.6](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=13896153&end=13902153)、[r05@6:58.3](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=3722631&end=3728631)、[r09@9:32.8](https://www.warcraftlogs.com/reports/4PZxpvB9dMcD8Jgw#fight=1&view=events&start=11335713&end=11341713)）
- 穿透实锤：`闪避` **不免疫** `灌能传导(1296052)`（仍吃中位 221K ×4次，样本 [r08@17:06.0](https://www.warcraftlogs.com/reports/BLmWKxty6VMNvhR4#fight=1&view=events&start=9961136&end=9967136)、[r12@18:29.5](https://www.warcraftlogs.com/reports/7N92JyPbGhRMrKCQ#fight=1&view=events&start=15772357&end=15778357)、[r12@18:30.5](https://www.warcraftlogs.com/reports/7N92JyPbGhRMrKCQ#fight=1&view=events&start=15773346&end=15779346)）
- 免疫实锤：`暗影斗篷` 完全免疫 `沙爆箭(1292585)`（0伤 ×3次，样本 [r03@0:48.7](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=412806&end=418806)、[r05@1:07.2](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=3371590&end=3377590)、[r05@1:07.2](https://www.warcraftlogs.com/reports/catLdGMDyhBCJ3RQ#fight=9&view=events&start=3371590&end=3377590)）
- 免疫实锤：`闪避` 完全免疫 `箭雨(1308113)`（0伤 ×3次，样本 [r03@8:17.2](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=861344&end=867344)、[r06@10:08.7](https://www.warcraftlogs.com/reports/tBKM3YnmzZFhaLbc#fight=7&view=events&start=3487172&end=3493172)、[r08@10:07.8](https://www.warcraftlogs.com/reports/BLmWKxty6VMNvhR4#fight=1&view=events&start=9542934&end=9548934)）
- 穿透实锤：`闪避` **不免疫** `蜿蜒打击(1295635)`（仍吃中位 283K ×3次，样本 [r04@1:11.7](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24&view=events&start=13315233&end=13321233)、[r08@0:38.1](https://www.warcraftlogs.com/reports/BLmWKxty6VMNvhR4#fight=1&view=events&start=8973197&end=8979197)、[r12@0:40.7](https://www.warcraftlogs.com/reports/7N92JyPbGhRMrKCQ#fight=1&view=events&start=14703533&end=14709533)）
- 免疫实锤：`闪避` 完全免疫 `箭雨(1308116)`（0伤 ×2次，样本 [r03@10:34.8](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=998996&end=1004996)、[r03@10:35.6](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=999727&end=1005727)）
- 免疫实锤：`暗影斗篷` 完全免疫 `箭雨(1308113)`（0伤 ×1次，样本 [r03@0:47.3](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1&view=events&start=411413&end=417413)）
— WCL API (v1)：实时请求 1 次，缓存命中 207 次；v1 限额剩余 765/800 次
