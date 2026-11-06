<img src="assets/icon.svg" width="64" height="64" alt="">

# wcl-raider · 大秘境战斗记录复盘

把一条 Warcraft Logs 大秘境报告链接交给 Claude Code，它会像指挥看录像一样复盘这场钥石：按首领把这一把切成几段，和路线相近的高分记录（或者你们自己上一把限时的记录）逐段、逐波比时间，讲清楚**这一把是怎么打的、时间丢在哪里、哪里差点出事、下一把怎么打**。评分（0.0–10.0）放在附录里。

它的结构是一个 **Claude Code Skill + 一个零依赖的数据工具**：
- **数据工具**（`scripts/wcl.py`）负责客观测量：通过 WCL v2 API 拉取数据，把几万条战斗事件压缩成计时、波次、死亡回放、打断、承伤、个人施法，以及与同副本同层高分记录、同专精顶尖玩家的对比，并按统一公式计算评分卡。
- **Skill**（`SKILL.md` + `references/`）负责判断：教 agent 先把这一把按时间线讲出来，再追丢时间的地方和险情的起因，最后给出能直接在语音里布置的改进。判断标准是"和路线相近的参考记录逐段比"，不是写死的规则，所以换赛季、换副本都不需要改代码。

## 快速开始

1. **创建 WCL API 客户端**：打开 https://www.warcraftlogs.com/api/clients/ （需要登录 WCL），点 "Create Client"。名称随意，Redirect URL 填 `http://localhost`，不要勾选 Public Client。
2. **保存凭据**到 `~/.config/wcl-raider/credentials.env`：
   ```
   WCL_CLIENT_ID=你的 Client ID
   WCL_CLIENT_SECRET=你的 Client Secret
   ```
   （也可以用同名环境变量，或当前目录下的 `.env`。）
3. **验证**：`python3 .claude/skills/mplus-review/scripts/wcl.py points`
4. **在本仓库里启动 Claude Code**，输入：
   ```
   /mplus-review https://www.warcraftlogs.com/reports/XXXXXXXXXXXXXXXX#fight=5
   ```
   可以附加关注点，例如 `/mplus-review <链接> 我是坦克，重点看我`，或者 `/mplus-review <链接> 快速`。

复盘报告会保存到 `reviews/` 目录，对话里给出一句话结论、分段用时表、时间丢在哪里和下一把怎么打。想和自己上一把比，就加上参考链接：`/mplus-review <链接> 参考 <上一把的链接>`。

### 在任意目录使用
把 skill 链接到个人 skill 目录：
```bash
ln -s "$(pwd)/.claude/skills/mplus-review" ~/.claude/skills/mplus-review
ln -s "$(pwd)/.claude/skills/mplus-tactics" ~/.claude/skills/mplus-tactics   # 依赖同级的 mplus-review
```

## 应对技巧复盘（mplus-tactics）

另一个 skill：从高水准记录里学习**各职业在常规循环之外用了哪些技能、什么时机、在应对哪个机制**——例如圣骑士自由祝福解定身、战士法术反射反掉读条、潜行者暗影斗篷清魔法、奶骑先牺牲祝福再圣盾术。工具会还原每一次使用时身上的减益、前后几秒的敌方读条、血线，以及之后发生了什么（驱散、减益消失、免疫/反射），再按"敌方机制 → 被什么技能应对"汇总，可选多场高分记录对照。

```
/mplus-tactics https://www.warcraftlogs.com/reports/XXXXXXXXXXXXXXXX#fight=5
/mplus-tactics <链接> 多场对照            # 再拉 3 场同副本高分记录，看哪些做法是共识
/mplus-tactics <高分链接> 我的记录 <链接>  # 对照自己的记录，找漏掉的技巧
/mplus-tactics 法师在毒牙祭坛要在什么时机用哪些技能应对哪些机制？   # 职业专题：自动找有法师的高分记录
```

## 数据工具

需要 Python 3.9+，只用标准库。所有命令都接受完整链接（会自动识别 `#fight=N`）或 16 位报告代码。

```bash
W=.claude/skills/mplus-review/scripts/wcl.py
python3 $W runs     <链接>            # 报告里的所有钥石记录
python3 $W overview <链接>            # 计时/罚时/阵容/DPS/同层百分位/打断/药水石头
python3 $W splits   <链接> [--ref 链接]   # 分段计时：按首领分段，逐段/逐波与路线相近的参考记录比用时和拉怪
python3 $W danger   <链接>            # 险情：没死但血线很低的时刻、多人同时低血
python3 $W pulls    <链接>            # 波次时间线
python3 $W deaths   <链接>            # 死亡回放（血线、承伤、死者施法、团灭归组）
python3 $W interrupts <链接>          # 打断率、漏断时间点、每人打断
python3 $W damage   <链接> [--ability 技能]   # 承伤构成与每人分布
python3 $W compare  <链接>            # 与同层高分记录对比
python3 $W player   <链接> <玩家>     # 单人深挖
python3 $W spec     <链接> <玩家>     # 与同专精顶尖玩家对比 CPM
python3 $W events   <链接> --pull 7 --type interrupts   # 原始事件钻取
python3 $W score    <链接>            # 评分卡
python3 $W tactics  <链接> [--refs 3] [--ability 技能] [--player 玩家] [--class 职业]   # 应对技巧：额外技能的情境与效果
python3 $W find     <副本名> [--class 职业] [--level N]   # 没有链接时找高分记录
python3 $W render   <报告.json> [--pdf x.pdf] [--png x.png] [--md x.md]   # 报告排版：本地 HTML，可导出 PDF/PNG（需 playwright + Chrome）
python3 $W spell    <技能ID…>         # Wowhead 技能说明与驱散类型
python3 $W --help
```

- **语言**：默认通过 `cn.warcraftlogs.com` 获取中文技能/怪物/副本名（任何地区的日志都适用）。`--lang en` 或 `WCL_LANG=en` 切换为英文。
- **API 点数**：WCL 每个客户端每小时 1000 点。一次完整复盘大约消耗 60–100 点（首次 `splits` 约 20–30 点，之后缓存 7 天）。数据会缓存在 `~/.cache/wcl-raider/`，重复查询不再消耗点数。每条命令都会在 stderr 打印本小时已用点数。
- **限制**：只支持正式服大秘境；只能读取公开或未列出（unlisted）的报告，私密报告需要上传者修改可见性。

## 评分体系

0.0–10.0，保留一位小数：9.5+ 顶尖 · 8.5 优秀 · 7.5 良好 · 6.5 及格 · <6.5 不及格。
- **团队**：计时、节奏（与同层高分对比）、存活、打断协作。
- **个人**：生存、机制（可躲伤害）、打断、输出、执行（活跃时间），按坦克/治疗/输出各自的权重加权。
- **数据分**由统一公式计算，可复现、可跨场比较；agent 复盘时可以在每个维度 ±1.0 内结合上下文修正，并写明理由。公式见 [`references/scoring.md`](.claude/skills/mplus-review/references/scoring.md)。

## 目录结构

```
.claude/skills/mplus-tactics/   # 应对技巧复盘（共用 mplus-review 的数据工具）
├── SKILL.md
└── references/              # 方法（method）、职业应对手段速查（class-counters）、报告模板
.claude/skills/mplus-review/
├── SKILL.md                 # 复盘流程（agent 的工作说明）
├── references/
│   ├── playbook.md          # 复盘方法论：讲故事 → 时间丢在哪 → 险情 → 下一把怎么打
│   ├── scoring.md           # 评分公式与修正规则
│   ├── data-notes.md        # 数据口径与 WCL API 备忘
│   └── report-template.md   # 报告模板
└── scripts/
    ├── wcl.py               # 数据工具入口
    └── wclr/                # API 客户端、上下文、各命令实现
tests/                       # 离线单元测试：python3 -m unittest discover -s tests
```
