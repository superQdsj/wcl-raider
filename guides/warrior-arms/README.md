# 武器战副本手册

职业为战士，专精为武器，英雄天赋为屠戮者。制作流程见 [`../tools/README.md`](../tools/README.md)。

## 状态（2026-11-08，八本齐）

| 副本 | 状态 |
| --- | --- |
| 红玉新生法池 | 第二版完成：[手册](2026-11-07-红玉新生法池-武器战.html) · [长图](2026-11-07-红玉新生法池-武器战.png)。参考录像：[Mjtwarrior](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=13) · [人艰不拆战](https://www.warcraftlogs.com/reports/Kzg6XDw3V2FnWZcd#fight=1) · [Rosebankk](https://www.warcraftlogs.com/reports/TFfB8XRw6HPVLjN2#fight=4) |
| 毒牙祭坛 | 完成：[手册](2026-11-07-毒牙祭坛-武器战.html) · [长图](2026-11-07-毒牙祭坛-武器战.png)。参考录像：[末诚](https://www.warcraftlogs.com/reports/1AWhVvdLbpy2gPak#fight=36) · [Mjtwarrior](https://www.warcraftlogs.com/reports/1AWhVvdLbpy2gPak#fight=44) · [暗夜白昼](https://www.warcraftlogs.com/reports/JpHdnbhYD8ZFWvma#fight=1) |
| 密谋小径 | 完成（不用 skill，手工分析 +23）：[手册](2026-11-07-密谋小径-武器战.html) · [长图](2026-11-07-密谋小径-武器战.png)。参考录像：[Иутир](https://www.warcraftlogs.com/reports/vbq6AXY4ByjVgx2D#fight=29) · [Madenianarch](https://www.warcraftlogs.com/reports/fWtc3hx6GZaJTmbD#fight=39) · [Yarrgiwr](https://www.warcraftlogs.com/reports/tg6k3ZvFd24pJrhT#fight=4) |
| 夺目谷 | 完成（自由版式）：[手册](2026-11-07-夺目谷-武器战.html) · [长图](2026-11-07-夺目谷-武器战.png)。参考录像：[Venzèr](https://www.warcraftlogs.com/reports/8yZD1VXdvf42qcFR#fight=3) · [Yarrgiwr](https://www.warcraftlogs.com/reports/FHJ6XPcCvnWwLM23#fight=6) · [Zitee](https://www.warcraftlogs.com/reports/VDBjgqz8xnMCkH6p#fight=10) |
| 纳洛拉克的洞穴 | 完成（不走 skill，自由版式）：[手册](2026-11-07-纳洛拉克的洞穴-武器战.html) · [长图](2026-11-07-纳洛拉克的洞穴-武器战.png)。参考录像：[Doxorsw](https://www.warcraftlogs.com/reports/jH7dWrY18QF2MzqJ#fight=1) · [Yarrgiwr](https://www.warcraftlogs.com/reports/jnHZFBVRN4M3DxpX#fight=7) · [Crimsfeel](https://www.warcraftlogs.com/reports/JGXt7TkQ2gm3FWfR#fight=11) |
| 塞塔里斯神庙 | 完成（不用 skill，手写）：[手册](2026-11-07-塞塔里斯神庙-武器战.html) · [长图](2026-11-07-塞塔里斯神庙-武器战.png)；源文件 `sources/sethraliss/`（`python3 sources/sethraliss/build.py sources/sethraliss <输出.html>`）。参考录像（+22）：[Diffw](https://www.warcraftlogs.com/reports/4Ab97gnVjKhZP1Nf#fight=8) · [Swordish](https://www.warcraftlogs.com/reports/r1ChwFYjNM7XkWp9#fight=20) · [咙咚哐咙咚哐](https://www.warcraftlogs.com/reports/XtNDVkrqb8LaK36M#fight=7) |
| 虚空之痕竞技场 | 完成（自由版式）：[手册](2026-11-07-虚空之痕竞技场-武器战.html) · [长图](2026-11-07-虚空之痕竞技场-武器战.png)；源文件 `sources/voidscar/`。参考录像：[Miratrixwar](https://www.warcraftlogs.com/reports/6TCrNBtdvnMDV78p#fight=2) · [Statikkw](https://www.warcraftlogs.com/reports/HDjaYfxXJWwCb9Kg#fight=6) · [Timeevo](https://www.warcraftlogs.com/reports/vN9PxrQFX2fJ3mjM#fight=19) |
| 诸王之眠 | 完成（自由版式）：[手册](2026-11-07-诸王之眠-武器战.html) · [长图](2026-11-07-诸王之眠-武器战.png)；源文件 `sources/zhuwang-freeform/`。参考录像（+22）：[Yarrgiwr](https://www.warcraftlogs.com/reports/DGtXrcbpV3YhN81A#fight=9) · [一戰成名](https://www.warcraftlogs.com/reports/Z4WCnjBGyMzKfwdb#fight=2) · [Ptz](https://www.warcraftlogs.com/reports/vxWqaMdprBXmcHPG#fight=14) |

## 文件

- 塞塔里斯神庙、虚空之痕竞技场、诸王之眠的源码在 `sources/<副本>/`，能离线重建。
- 其余几本（含旧 skill 生成的红玉新生法池、毒牙祭坛和八本目录页）只保留成品 HTML。

## 关键核对与边界

- 三重喷吐、同步毒液、混沌弹幕的反射有命中记录；没有据此宣称所有法术或整段持续伤害都能反射。
- 尖刺盾牌存在反射命中，但不推荐把一次反射扩大成持续无脑打盾；正文要求效果结束或消耗后停手转火。
- 自动分析曾将集结呐喊附近的免疫事件归到集结；它本身没有免疫机制，正文没有沿用这种归因。
- 恐惧咆哮（1252406）的说明是击退与12秒暗影持续伤害，不因名称含「恐惧」就宣称狂暴之怒能清除。
- 地缚印记（1307205）是持续自然伤害；风暴之眼（372963）是冰霜易伤，都没有直接当成可冲锋清除的减速。
- 冰雹炸弹（384024）是碰触触发的地雷并降低急速，不写成必须带离队友的定时点名炸弹。
- 风暴之眼（372963）只对身处风眼内的玩家生效；冲锋是把人带出风眼，不是驱散，正文按「离开即消失」写。
- 雷霆践踏（392406）造成自然伤害，不因「践踏」二字把它写成物理伤害。
- 蚀骨践踏（1303486）是自然持续伤害，未标记为可驱散的中毒；不因为文字写「烈毒」就建议队友驱毒。
- 冰川之墓没有作为稳定自解技巧推荐；采用减伤配合队伍击破冰墓的正常解法。
- 电闪雷鸣先按分工完成冲刺分摊，再处理20码惊雷；诸王之眠翻滚照常分摊，不编造飞跃、嘲讽等稳定跳点名技巧。
- 正文中通用的「未验证可反射」技能，只按已核对的伤害类型推荐魔法减伤或全伤减免，不宣称免疫、清层或取消引导。

关键核对是第一版留下的机制事实，重写其余副本时仍然适用。
