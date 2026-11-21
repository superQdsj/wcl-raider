# 惩戒骑副本手册

- [红玉新生法池 · +23](2026-11-22-红玉新生法池-惩戒骑.html)：自由祝福给坦克清梅莉杜莎冰寒利爪、圣佑术分段覆盖地狱烈火与递增易伤、圣盾术免疫雷暴区闪电涌流、牺牲祝福给基拉卡烈焰喷吐队友。
- [塞塔里斯神庙 · +23 / +24](2026-11-22-塞塔里斯神庙-惩戒骑.html)：保护与圣盾清锯齿冲锋流血、清毒术解细胞毒素、圣盾交双首领电闪雷鸣与化身二次腐化、牺牲祝福给加瓦兹特接光束队友、圣疗术给化身。
- [虚空之痕竞技场 · +23](2026-11-22-虚空之痕竞技场-惩戒骑.html)：圣盾 + 牺牲接塔兹拉尔空灵冲刺和煞戎努斯星辰坠击，圣佑按轮次接冲刺 / 剧毒光环 / 恐惧咆哮 / 星辰坠击，牺牲转好给虚空光束目标。
- [诸王之眠 · +23 / +24](2026-11-21-诸王之眠-惩戒骑.html)：用保护祝福和圣盾术清流血、清毒术解毒，按伤害时间轴交圣佑术。
- [毒牙祭坛 · +23](2026-11-15-毒牙祭坛-惩戒骑.html)：圣盾和保护祝福清鲜血献祭（保护给队友）、圣盾清拉维毒球再接牺牲、自由祝福解麻痹射击、祖尔加切骨者牺牲给飞斧目标，责难专断四种读条。
- [密谋小径 · +22](2026-11-08-密谋小径-惩戒骑.html)：牺牲祝福（正义保护）免疫赞恩毒伤和断心药膏、保护祝福免疫绝命凶径、圣盾掐断吸取生命、牺牲＋圣盾，以及各首领群伤交圣佑术。

重建命令（新 v2 自动通过 `guides/tools/icons.py` 外链图标）：

```sh
python3 guides/paladin-ret/sources/hongyu-v2/build.py
python3 guides/paladin-ret/sources/saitalisi-v2/build.py
python3 guides/paladin-ret/sources/xukong-v2/build.py
python3 guides/paladin-ret/sources/mimou-v2/build.py
python3 guides/paladin-ret/sources/duya-v2/build.py
python3 guides/paladin-ret/sources/zhuwang-v2/build.py
```

- `sources/mimou-v2/`：页面源码（`head.part` 样式、`body.part` 正文、`build.py` 含单轨时间轴）、天赋编码 `enc.py`、`NOTES.md` 关键结论的数据依据。
- `sources/duya-v2/`：毒牙祭坛，同样的结构，证据包（五场 +23）在 `evidence/`。
- `sources/zhuwang-v2/`：诸王之眠的页面源码（系统字体，不用 Google Fonts）、`enc.py`、`NOTES.md`。
- `sources/zhuwang/evidence/`：诸王之眠的证据包，收录五场 +23 / +24 限时录像。
- `sources/mimouxiaojing/`：三场 +22 的证据包、场景还原和全部关注技能施法的逐次核对（第一版手册的研究材料）。
