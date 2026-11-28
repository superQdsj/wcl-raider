# 副本攻略页（一个副本一页，按 DPS 专精切换）

给副本加一个专精的完整步骤见 [WORKFLOW.md](WORKFLOW.md)。

```
python3 guides/dungeons/build.py saitalisi          # 检查 + 生成 saitalisi/saitalisi.html
python3 guides/dungeons/build.py saitalisi --check  # 只检查
```

每个副本一个目录：

| 文件 | 放什么 |
|---|---|
| `dungeon.json` | 所有专精共用：首领、头像（MDT displayId）、技能说明、伤害数字、所有人都该做的事 |
| `specs/<专精>.json` | 这个专精独有：顶部按钮栏、大招怎么分、每个技能下面按什么、绝活、别这样做、日志链接 |
| `evidence/` | `src` 字段指向的原始依据：`wowhead.json`、`diag-bN.md`、`<专精>-guide.md`（MDT 快照在 `guides/tools/mechanics/<副本>.mdt.lua`，全仓库只留一份） |

`src` 写法：`wowhead:<技能ID>`、`diag-bN`、`ret-guide:L<行号>`；`user` 表示用户口述确认。
机制说明不能脑补，每条都要写出处。

只润色文字时，改 JSON 里的文字字段，改完跑一次 build。检查会拦下这几类问题：超出字数上限、报告腔（N/N 场、场均、中位、HP 百分比、M/K）、缺出处、引用了不存在的技能。

共用样式在 `_shared/page.css`。头像、横幅、专精图标都放在 `guides/icons/` 下，缺了 build 会自动下载或复制。

技能旁边的伤害类型标签（物理 / 自然 / 暗影 / 火焰……）是 build 时从 `evidence/wowhead.json` 里该技能的说明文字自动提取的，只认"造成 X 点 Y 伤害"这种写法。说明里没写伤害类型的技能不显示标签，也不要在 JSON 里手动补。
小怪技能的类型标签：打断 = MDT 标了可打断，且日志不矛盾（MDT 和日志冲突时以日志为准，例如细胞毒素 MDT 标可打断，但日志里 354 次施放 0 次读条 0 次被打断，所以不标）；钢条 = 打断不了、只能硬控（要有出处）；免控 = 打断不了，这只怪也不吃控制（MDT 的 characteristics 只有嘲讽）。
减益标签（流血 / 中毒 / 疾病 / 诅咒 / 魔法）同样自动提取：流血看 Wowhead 说明里有没有"流血"二字；中毒、疾病、诅咒、魔法看 Wowhead 的驱散类型和 MDT 技能上的 poison / disease / curse / magic 标记。
