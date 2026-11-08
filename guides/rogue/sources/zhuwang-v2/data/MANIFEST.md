# MANIFEST：潜行者 敏锐 · 诸王之眠 · +20–22 限时 样本采集

| 文件 | 行数 | 报错 | 截断 |
|---|---|---|---|
| ./find.md | 70 | 否 | 否 |
| ./points.md | 2 | 否 | 否 |
| ./run1/buffs.md | 10003 | 否 | 是 |
| ./run1/casts.md | 1775 | 否 | 否 |
| ./run1/damage.md | 34 | 否 | 否 |
| ./run1/deaths.md | 3 | 否 | 否 |
| ./run1/debuffs.md | 86 | 否 | 否 |
| ./run1/dtaken.md | 492 | 否 | 否 |
| ./run1/enemycasts.md | 692 | 否 | 否 |
| ./run1/interrupts.md | 39 | 否 | 否 |
| ./run1/overview.md | 35 | 否 | 否 |
| ./run1/player.md | 102 | 否 | 否 |
| ./run1/pulls.md | 31 | 否 | 否 |
| ./run1/splits.md | 74 | 否 | 否 |
| ./run1/tactics.md | 68 | 否 | 否 |
| ./run2/buffs.md | 10003 | 否 | 是 |
| ./run2/casts.md | 1771 | 否 | 否 |
| ./run2/damage.md | 34 | 否 | 否 |
| ./run2/deaths.md | 3 | 否 | 否 |
| ./run2/debuffs.md | 90 | 否 | 否 |
| ./run2/dtaken.md | 482 | 否 | 否 |
| ./run2/enemycasts.md | 709 | 否 | 否 |
| ./run2/interrupts.md | 38 | 否 | 否 |
| ./run2/overview.md | 36 | 否 | 否 |
| ./run2/player.md | 102 | 否 | 否 |
| ./run2/pulls.md | 30 | 否 | 否 |
| ./run2/splits.md | 76 | 否 | 否 |
| ./run2/tactics.md | 76 | 否 | 否 |
| ./run3/buffs.md | 10003 | 否 | 是 |
| ./run3/casts.md | 1833 | 否 | 否 |
| ./run3/damage.md | 34 | 否 | 否 |
| ./run3/deaths.md | 106 | 否 | 否 |
| ./run3/debuffs.md | 119 | 否 | 否 |
| ./run3/dtaken.md | 477 | 否 | 否 |
| ./run3/enemycasts.md | 747 | 否 | 否 |
| ./run3/interrupts.md | 39 | 否 | 否 |
| ./run3/overview.md | 40 | 否 | 否 |
| ./run3/player.md | 102 | 否 | 否 |
| ./run3/pulls.md | 30 | 否 | 否 |
| ./run3/splits.md | 78 | 否 | 否 |
| ./run3/tactics.md | 77 | 否 | 否 |
| ./runs.md | 4 | 否 | 否 |

## 备注
- find.md：--class 敏锐 报错（敏锐是专精名），改用 --class 潜行者 重跑，结果中按专精列筛选
- find.md：三次 --level 22/21/20 返回的层数列分别为 +23/+22/+21（标题写 +22/+21/+20）
- run1：casts/buffs/dtaken/enemycasts 首跑（--limit 5000/8000，未加 --max-chars）截断，已翻倍 --limit（10000/16000）并加 --max-chars 0 重跑一次；casts/dtaken/enemycasts 重跑后不再截断，buffs 仍截断（只到 14:29.5）
- run2、run3：buffs 首跑截断，已翻倍 --limit 到 10000 重跑一次，仍截断（见上表）；其余 events 文件未截断
- 截断文件的结尾都有「输出被截断」提示；被截断的窗口不能用来判断某技能没交
