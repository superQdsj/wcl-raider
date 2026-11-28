# v3 攻略：怎么开始

完整流程在 [`dps-guide-v3-orchestration.md`](dps-guide-v3-orchestration.md)。这一页只讲怎么起头，以及每一步要你确认什么。

## 先记住：抓数一次只跑一个专精

- WCL 对单个 IP 有频率限制，v1 和 v2 共用。并发太高会返回 429。
- 一个全新专精抓一遍大约 200 次请求。diag 每场每类事件只按整场查一次，各节在本地切片。
- 碰到 429，客户端会按 `retry-after` 等待后重试，最多等 1 小时（环境变量 `WCL_429_MAX_WAIT`）。
- `check_claims.py dump` 默认一节一节地跑，**不要加大 `--jobs`**。diag 内部同时拉 2 场（环境变量 `WCL_FETCH_WORKERS`）。
- 多个专精一起做时，抓数要排队一个一个来。写稿和审判不发请求，可以同时开多个会话。
- 只有阶段 1 会联网。已经结束的报告缓存 30 天，阶段 2–5 的 `inspect` 隔多久跑都走缓存。

## 要不要开 worktree

- **做攻略内容（新专精、新副本）**：不用，留在 `t3/dps-guide-v3`。每个专精只写自己的目录和 `classes/<spec>.json`，互不冲突。
  - 提交时只 `git add` 自己的路径，不要用 `git add -A`。
  - 两个会话同时提交时，可能报 `index.lock` 已存在，等几秒重试即可。
- **改工具代码（`diag.py`、`check_claims.py`、`wclr/`）**：要开 worktree，验证通过后再合并，避免影响正在跑的会话。
- 缓存（`~/.cache/wcl-raider`）所有 worktree 共用。

## 四种情况

| | 已有 v3 职业卡 | 没有 v3 职业卡 |
|---|---|---|
| **老副本**（已有 `guides/tools/mechanics/<dungeon>.md`） | ① 职业卡沿用，机制卡直接引用 | ② 先建职业卡 |
| **新副本**（没有机制卡） | ③ 先建机制卡 | ④ 两样都建 |

- **v3 职业卡**：`guides/tools/classes/<spec-slug>.json`，`defensives` 里带 `tier` 字段。目前有 `paladin-ret`、`hunter-bm`；`rogue-sub` 已经建好，还在等确认。
- **机制卡**：目前只有塞塔里斯（`sethraliss.md`，以及 MDT 快照 `sethraliss.mdt.lua`、禁用说法清单 `sethraliss.banned.txt`）。

这些不用自己判断：提示词第 2 步会检查职业卡，第 5 步会检查机制卡，存在就沿用，不存在就新建。所以四种情况用的是**同一份提示词**，只有参数不同。

## 提示词

开一个新会话，发：

```
按 guides/tools/prompts/dps-guide-v3-orchestration.md 执行。
参数：<spec>=XXX，<spec-slug>=XXX，<专精中文名>=XXX，<dungeon>=XXX，<副本名>=XXX，<副本英文名>=XXX。
先只做阶段 1，到人工确认点停下，把 calibration.md（以及机制卡草稿，如果有）给我看。
```

| 参数 | 含义 | 例子 |
|---|---|---|
| `<spec>` | 草稿目录名，专精英文全称 | `hunter-beastmastery` |
| `<spec-slug>` | 职业卡文件名（沿用 v2 的旧名，对照见 `check_claims.py` 的 `CLASS_JSON`） | `hunter-bm` |
| `<专精中文名>` | 抽样时用来识别专精 | `兽王猎` |
| `<dungeon>` | 副本目录名，用英文：取 `scripts/build_site.py` 里 `DUNGEON_INFO` 的短名（`sethraliss`、`kingsrest` 等） | `sethraliss` |
| `<副本名>` | 能在 WCL 副本列表里唯一认出这个副本的名称片段 | `塞塔里斯` |
| `<副本英文名>` | 用来下载 MDT 快照（只有新副本会用到） | `Temple of Sethraliss` |

如果某个专精的旧配置还被旧攻略用着（比如 `rogue.json`），就另起一个新的 slug，并在提示词里加一句："新建 `guides/tools/classes/<新 slug>.json`，不要改旧的"。

## 你要确认什么

阶段 1 结束只有一个确认点。

- **calibration.md**（四种情况都有）
  - 职业卡是沿用的：只看和上一个副本的差异。比如之前 0 施放、这次用上了的技能，新出现的要驱散或免疫的 Debuff。
  - 职业卡是新建的：看完整配置，重点核对常规减伤和大牌有没有分对，施法 ID 和 Buff ID 是否一致，有没有 0 施放的技能。
- **机制卡草稿**（③ 和 ④）：`guides/tools/mechanics/<dungeon>.draft.md`，**只挑错，不填空**。
  - 流程是从日志推出来的：中位时长、同场单位、击杀顺序、首次施放、小怪分段。
  - 「打断 / 驱散 / 吃控」来自 MDT。能否打断已经用日志核对过，冲突时以日志为准，格内写明证据。
  - 场地、走位、开门条件这类日志看不出来的不写。

你确认之后，后面四种情况都一样：写稿 → 脚本闸门（`check_claims.py check`）→ 独立审判（全新上下文）→ 脚本拼接 guide.md。

## 常用命令

```
CK=python3 guides/tools/check_claims.py
$CK dump      <src>            # 落盘 boss1-4 + trash 的 diag 输出（串行）
$CK mechanics <src>            # 生成机制卡草稿（新副本）
$CK inspect   <src> --boss N --ability <ID> --only-bare
$CK check     <src> --banned guides/tools/mechanics/<dungeon>.banned.txt
$CK merge     <src> --spec-name <专精中文名>
python3 guides/tools/mdt.py --en "<副本英文名>" --out guides/tools/mechanics/<dungeon>.mdt.lua   # 已存在就不要重下
```

`<src>` = `guides/v3/<dungeon>/drafts/<spec>`。
