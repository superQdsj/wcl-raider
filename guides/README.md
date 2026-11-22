# 职业副本手册

一个职业专精一个目录：成品（`<日期>-<副本>-<职业>.html`）直接放在目录顶层，每本的源码放在 `sources/<副本>/`，能离线重建。制作流程和工具见 [`tools/README.md`](tools/README.md)（不用 skill）。

| 目录 | 职业 | 状态 | 源材料 |
| --- | --- | --- | --- |
| [`warrior-arms/`](warrior-arms/README.md) | 武器战（屠戮者） | 八本完成（2026-11-07） | 塞塔里斯、虚空之痕、诸王之眠有 `sources/<副本>/` 可重建；其余只有成品 |
| [`rogue/`](rogue/README.md) | 潜行者 | 七本第一版（2026-10-28）；新版已做诸王之眠、夺目谷（2026-11-08）、毒牙祭坛（五场，2026-11-15） | 第一版归档可用 `rebuild.py` 重建；新版在 `sources/<副本>-v2/` |
| [`paladin-ret/`](paladin-ret/README.md) | 惩戒骑（烈日先驱） | 密谋小径（+22，2026-11-08）、毒牙祭坛（+23，2026-11-15）、诸王之眠（+23/+24，2026-11-21） | 三本都可重建（诸王之眠源码在 `sources/zhuwang-v2/`，证据包在 `sources/zhuwang/evidence/`） |
| [`demonhunter-devourer/`](demonhunter-devourer/README.md) | 恶魔猎手（噬灭） | 八本完成（+22，2026-11-15） | `sources/<副本>-v2/` 可重建，含证据包 |
| [`shaman-elemental/`](shaman-elemental/README.md) | 元素萨满（先知） | 毒牙祭坛（+23，2026-11-22） | `sources/duya-v2/` 可重建，含证据包 |
| `holy-paladin/` | 神圣骑士 | 八本完成（第一版，2026-10-25 ~ 10-28） | 只有成品，没有保存源材料 |
