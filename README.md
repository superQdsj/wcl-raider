<img src="assets/icon.svg" width="64" height="64" alt="">

# wcl-raider · 大秘境职业副本攻略

从高分 Warcraft Logs 大秘境录像中提取各职业处理副本机制的实际做法，整理成「**信号 → 按什么 → 为什么**」的单页 HTML 职业副本手册，并构建成静态攻略站发布到 Cloudflare Pages（https://wcl-raider.pages.dev/）。

## 已有攻略成果

所有手册都在 [`guides/`](guides/README.md)，一个职业专精一个目录，成品 HTML 与源材料放在一起：

| 职业专精 | 目录 | 覆盖进度 |
| --- | --- | --- |
| 噬灭恶魔猎手 | [`guides/demonhunter-devourer/`](guides/demonhunter-devourer/README.md) | 8/8 本齐（2026-11-15，全有证据包与源码） |
| 武器战士（屠戮者） | [`guides/warrior-arms/`](guides/warrior-arms/README.md) | 8/8 本齐（2026-11-07） |
| 神圣圣骑士 | `guides/holy-paladin/` | 8/8 本齐（第一版，2026-10-25 ~ 10-28） |
| 敏锐潜行者 | [`guides/rogue/`](guides/rogue/README.md) | 第一版 7 本（可离线重建）；新版已完成诸王之眠、夺目谷、毒牙祭坛 |
| 惩戒圣骑士（烈日先驱） | [`guides/paladin-ret/`](guides/paladin-ret/README.md) | 密谋小径、毒牙祭坛、诸王之眠（3 本，均有证据包） |

## 制作流程与数据工具

详细制作流程与派发模板见 [`guides/tools/README.md`](guides/tools/README.md)。整体为两段式流程（不使用 Claude Code skill）：

1. **采集证据包**：用 `guides/tools/wcl.py find` 选出 5 场高分限时录像，再跑 `guides/tools/evidence.py` 生成结构化证据表（窗口内外承伤对比、技能使用情境、全队承伤、减益、波次、Wowhead 技能说明、天赋数据）。
2. **分析与成稿**：阅读证据包，必要时用 `guides/tools/wcl.py events` / `spell` 补查，编写页面源码与单轨时间轴（`guides/tools/timeline.py`），生成独立 HTML 并通过 `guides/tools/icons.py` 外置共享技能图标到 `guides/icons/`。

### WCL API 凭据配置（优先 v1）

仅需 Python 3.9+ 标准库，无第三方依赖。**工具默认优先使用 WCL v1 API**（v2 GraphQL API 的每小时点数限额较紧，v1 REST API 限额更宽松且可获取同类数据）；未配置 v1 密钥时自动回退到 v2，仅 `wcl.py query`（任意 GraphQL 调试）需要 v2。

1. 在 https://www.warcraftlogs.com/api/clients/ 获取凭据：
   - **优先（v1）**：创建或查看 V1 客户端密钥（`WCL_V1_API_KEY`）。
   - **备选（v2）**：点击 Create Client（Redirect URL 填 `http://localhost`，不要勾选 Public Client），获取 `WCL_CLIENT_ID` 和 `WCL_CLIENT_SECRET`。
2. 保存凭据到 `~/.config/wcl-raider/credentials.env`（或参考 [`.env.example`](.env.example) 放到仓库根目录 `.env`，已被 `.gitignore` 忽略，**切勿将真实密钥写入仓库文档或代码**）：
   ```
   WCL_V1_API_KEY=你的 v1 API Key
   # 可选：同时配置 v2 供回退或 `wcl.py query` 使用
   WCL_CLIENT_ID=你的 Client ID
   WCL_CLIENT_SECRET=你的 Client Secret
   ```
3. 验证与常用命令（可用 `--api v1|v2` 或 `WCL_API_VERSION` 手动切换版本）：
   ```bash
   W=guides/tools/wcl.py
   python3 $W points                                             # 查看 WCL API 限额/点数余量
   python3 $W find 毒牙祭坛 --class 潜行者 --level 23 --limit 15   # 查找带日志的高分录像
   python3 $W events <WCL链接#fight=N> --ability 183752 --from 0:00 --to 10:00
   python3 $W spell 1044 213644                                  # 查询 Wowhead 技能说明与驱散类型
   ```

默认通过 `cn.warcraftlogs.com` 获取中文技能/怪物/副本名（可用 `--lang en` 或 `WCL_LANG=en` 切换英文）；API 响应会缓存在 `~/.cache/wcl-raider/`，重复查询不消耗限额/点数。

## 构建与发布站点

```bash
python3 scripts/build_site.py
```

只收集 `guides/<职业>/` 顶层的成品 HTML 和它们引用的本地图片（含 `guides/icons/` 共享图标），生成静态站点到 `dist/site/` 和压缩包 `dist/wcl-raider-site.zip`。部署方式见 [`docs/site-deployment.md`](docs/site-deployment.md)。

## 目录结构

```
guides/
├── tools/                   # 攻略制作工具
│   ├── wcl.py               # WCL / Wowhead 数据查询 CLI（find / events / spell / query / points）
│   ├── wclr/                # WCL API 客户端（优先 v1，兼容 v2）、事件拉取、Wowhead 解析底层模块
│   ├── evidence.py          # 多场录像证据包生成器
│   ├── timeline.py          # 单轨技能时间轴组件
│   ├── icons.py             # 攻略图标外置工具（提取到 guides/icons/）
│   └── classes/             # 各职业防御技能配置文件（JSON）
├── icons/                   # 所有攻略共享的外置技能图标
├── demonhunter-devourer/    # 噬灭恶魔猎手
├── warrior-arms/            # 武器战士
├── rogue/                   # 敏锐潜行者
├── paladin-ret/             # 惩戒圣骑士
└── holy-paladin/            # 神圣圣骑士
scripts/
└── build_site.py            # 静态站点构建脚本
site/                        # 站点首页 / 404 模板、样式、副本图与专精图标
docs/
└── site-deployment.md       # Cloudflare Pages 部署说明
tests/                       # 底层 wclr 离线单元测试：python3 -m unittest discover -s tests
assets/                      # 站点与 README 图标
```
