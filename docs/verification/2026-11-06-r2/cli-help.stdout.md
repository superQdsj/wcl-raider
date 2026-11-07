usage: wcl.py [-h] [--lang {zh,en}] [--refresh] 命令 ...

Warcraft Logs 大秘境数据工具（mplus-review skill 的数据层）。
所有命令只输出客观数据（Markdown），由 agent 负责判断与建议。
报告参数可以是完整链接（含 #fight=N 时自动选中该场）或 16 位报告代码。

positional arguments:
  命令
    runs          列出报告中的所有大秘境记录
    overview      概览：计时/罚时/阵容/DPS/百分位/打断/药水/首领战/死亡一览
    pulls         波次时间线：时长/间隔/怪物构成/进度/团队DPS/承伤/死亡
    deaths        死亡复盘：致死技能、死前承伤时间线、死者施法、团灭判定
    interrupts    打断：敌方读条的打断率与读完时间点、每人打断与施放计数
    damage        承伤：按来源技能的伤害、命中、每人分布与标记
    player        单人深挖：施法/CPM、伤害构成、承伤、增益覆盖、低频技能时间轴
    compare       与同副本同层高分记录对比：用时结构、死亡、技能命中、打断率
    spec          与同专精顶尖玩家对比技能施放频率（CPM）与活跃时间
    events        原始事件钻取：按时间窗口/波次/类型/玩家/技能过滤
    score         评分卡：团队与个人的数据分（0.0–10.0，附计算依据）
    query         执行任意 GraphQL（调试/补充查询用）
    points        查看 WCL API 本小时点数余量

options:
  -h, --help      show this help message and exit
  --lang {zh,en}  名称语言：zh=中文（默认，经 cn.warcraftlogs.com 翻译），en=英文
  --refresh       忽略本地缓存重新拉取
