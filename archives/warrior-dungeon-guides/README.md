# 武器战副本手册

职业为战士，专精为武器，英雄天赋为屠戮者。制作流程与写作规范见 `mplus-class-guide` skill（`.claude/skills/mplus-class-guide/`）。

## 状态（2026-11-07）

| 副本 | 状态 |
| --- | --- |
| 红玉新生法池 | 第二版完成：[手册](../../reviews/2026-11-07-红玉新生法池-武器战.html) · [长图](../../reviews/2026-11-07-红玉新生法池-武器战.png)。也是 skill 的样板 |
| 其余七本 | 第一版内容套模板、质量低，已删除，待按 skill 重写。三场录像的源材料仍保留在 `sources/<副本>/` |

[目录页](../../reviews/2026-11-07-武器战-八本手册.html)会列出全部八本，未完成的标为「重写中」。

## 文件说明

- `guides.py`：内容源稿，只放已完成的副本。字段说明见 skill 的 `references/writing.md`。
- `build.py`：离线 HTML 构建器，复用潜行者手册的设计样式，内嵌所有技能与天赋图标。
- `talents.py`：武器专精（71）的天赋编码、解码与逐节点回验，正确合并分档节点各条目的等级。
- `research.py`：用项目已有的 WCL 客户端筛选限时武器战记录，保存应对分析。需要 WCL 凭据。
- `prepare.py`：从保存的记录准备技能说明、图标与天赋快照。需要联网，不属于离线重建流程。
- `sources/arms-tree.json`：武器天赋树快照（来自 Raidbots）。
- `sources/design.css`：潜行者毒牙祭坛原稿的设计系统快照。
- `sources/spells.json`、`sources/icons/`：Wowhead 技能说明与 JPEG 图标。
- `sources/<副本>/`：`rankings.json` 候选排名，`selected.json` 采用的三场，`<报告>-<场次>.md` 应对分析，`<报告>-<场次>.json` 记录摘录（战士技能使用情境、负面效果、敌方读条），`mechanics.json` 机制名到技能 ID，`talents.json` 三名玩家的天赋与回验字符串。

记录摘录不是完整的 WCL 缓存；重新做事件分析可能还要访问 WCL API。

## 参考场次

共24场，均为 +24、限时完成、武器专精。每本的三个链接也位于手册末尾。

| 副本 | 参考一 | 参考二 | 参考三 |
| --- | --- | --- | --- |
| 毒牙祭坛 | [末诚](https://www.warcraftlogs.com/reports/1AWhVvdLbpy2gPak#fight=36) | [Mjtwarrior](https://www.warcraftlogs.com/reports/1AWhVvdLbpy2gPak#fight=44) | [暗夜白昼](https://www.warcraftlogs.com/reports/JpHdnbhYD8ZFWvma#fight=1) |
| 夺目谷 | [暗夜白昼](https://www.warcraftlogs.com/reports/CG3RbAdqgMvt7nP4#fight=1) | [Rosebankk](https://www.warcraftlogs.com/reports/1b9v7Z4FqkCwxpdX#fight=13) | [末诚](https://www.warcraftlogs.com/reports/KYLq6BtVQvcfkGhd#fight=10) |
| 红玉新生法池 | [Mjtwarrior](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=13) | [人艰不拆战](https://www.warcraftlogs.com/reports/Kzg6XDw3V2FnWZcd#fight=1) | [Rosebankk](https://www.warcraftlogs.com/reports/TFfB8XRw6HPVLjN2#fight=4) |
| 密谋小径 | [奶什么球](https://www.warcraftlogs.com/reports/1AWhVvdLbpy2gPak#fight=59) | [暗夜白昼](https://www.warcraftlogs.com/reports/31F8rbhd7VtWTxCH#fight=1) | [Mjtwarrior](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=18) |
| 纳洛拉克的洞穴 | [Crimsfeel](https://www.warcraftlogs.com/reports/BV19wgKxrnZ2dFj8#fight=1) | [Rosebankk](https://www.warcraftlogs.com/reports/GmjDn46rYhbKHzfw#fight=46) | [生气大王子](https://www.warcraftlogs.com/reports/HYrDhJX9pAgvTBQR#fight=41) |
| 塞塔里斯神庙 | [Crimsfeel](https://www.warcraftlogs.com/reports/F1vmzABpngjq4rw2#fight=1) | [暗夜白昼](https://www.warcraftlogs.com/reports/JR9FpGthrn3CmcAk#fight=1) | [Mjtwarrior](https://www.warcraftlogs.com/reports/nJWT6jHVAXvCwYym#fight=24) |
| 虚空之痕竞技场 | [Mjtwarrior](https://www.warcraftlogs.com/reports/B6nk2TZhgqPxDFfb#fight=1) | [末诚](https://www.warcraftlogs.com/reports/KhbZy8Rv6kdWtn2J#fight=31) | [暗夜白昼](https://www.warcraftlogs.com/reports/1dCwc4LGmknFb2VA#fight=1) |
| 诸王之眠 | [Rosebankk](https://www.warcraftlogs.com/reports/1b9v7Z4FqkCwxpdX#fight=7) | [末诚](https://www.warcraftlogs.com/reports/GJgWMpTVHcwqkYtA#fight=1) | [Doxorsw](https://www.warcraftlogs.com/reports/M2hG3PrzQWdCnL9K#fight=5) |

推荐天赋使用高分玩家实际选点，不自行拼接新的配点。优先采用排名靠前且包含正文所需工具的配置；诸王之眠采用末诚的无所畏惧配置，而不是将 Rosebankk 的狂暴之吼配置错误解释成可清减速。
所有24份原始天赋均编码后解码，逐个节点核对等级、选择分支与屠戮者子树。未进入游戏实际操作导入；游戏更新后仍需重新核对树版本。

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

## 离线重建

只重建 HTML 需要 Python 3 标准库；支持从任意工作目录执行：

```sh
python3 archives/warrior-dungeon-guides/build.py --output-dir <临时目录>
```

重建到项目 `reviews/` 并为已完成的每本导出 PNG：

```sh
python3 archives/warrior-dungeon-guides/build.py --png
```

PNG 复用项目现有 `wclr.export.export`，需要 Playwright 与 Chrome 或 Chromium。全部图标均为内嵌 JPEG。字体与潜行者原版一致，使用 Noto Serif SC、Noto Sans SC 和 JetBrains Mono；无法加载在线字体时回退系统字体，正文仍可离线阅读。
已存在的同名成品会被覆盖。

版式沿用潜行者原版 CSS，再加第二版组件（多技能行、标签、`combo` 分步专题），写在 `build.py` 的 `EXTRA_CSS`。

## 校验

```sh
python3 -m unittest discover -s tests -p test_warrior_guides.py -v
```
