#!/usr/bin/env python3
"""Scaffold a new DPS dungeon guide directory from the verified duya-sample template.

Creates guides/<class>/sources/<slug>-v2/ with:
  - head.part  (exact duya-sample CSS with class-appropriate :root palette)
  - body.part  (5-block DPS skeleton with bare <body>, <p class="lede">, null-safe JS)
  - build.py   (uses shared timeline.py + icons.py inject_icons + guarded {{TALENT}})
  - NOTES.md   (4-part evidence & verification template)

Usage:
  python3 guides/tools/scaffold.py --class paladin-ret --slug hongyu --dungeon 红玉新生法池 --en "Ruby Life Pools"
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Dict

TOOLS = Path(__file__).resolve().parent
GUIDES = TOOLS.parent
ROOT = GUIDES.parent
SAMPLE_HEAD = GUIDES / "rogue" / "sources" / "duya-sample" / "head.part"

# Verified dark-theme palettes for existing DPS classes (all >= 4.5:1 WCAG AA).
PALETTES: Dict[str, Dict[str, str]] = {
    "rogue": {
        "theme_name": "毒林夜色", "cls_zh": "潜行者", "spec_en": "SUBTLETY ROGUE", "spec_zh": "敏锐",
        "--bg": "#0d1210", "--nav-bg": "rgba(13,18,16,.92)",
        "--panel": "#141b18", "--panel-2": "#1a231f", "--line": "#2a3630", "--line-2": "#3c4d45",
        "--ink": "#ebe7da", "--ink-2": "#d3cec0", "--mute": "#a3b1a8", "--faint": "#84938a",
        "--gold": "#f2d24b", "--gold-dim": "#8a7a2c", "--on-gold": "#17140a",
        "--gold-bg": "rgba(242,210,75,.075)", "--gold-chip": "rgba(242,210,75,.14)", "--gold-band": "rgba(242,210,75,.12)",
        "--hero-a": "rgba(242,210,75,.14)", "--hero-b": "rgba(143,207,134,.09)",
        "--tl-e": "#8fcf86", "--tl-v": "#b59cf0",
    },
    "paladin-ret": {
        "theme_name": "圣骑士粉暗底", "cls_zh": "惩戒骑", "spec_en": "RETRIBUTION PALADIN", "spec_zh": "惩戒",
        "--bg": "#100e0d", "--nav-bg": "rgba(16,14,13,.92)",
        "--panel": "#181514", "--panel-2": "#201c1a", "--line": "#332d29", "--line-2": "#463e38",
        "--ink": "#ebe7da", "--ink-2": "#d4cec2", "--mute": "#a8a3b0", "--faint": "#8a8594",
        "--gold": "#f39cc3", "--gold-dim": "#86506a", "--on-gold": "#1b0e14",
        "--gold-bg": "rgba(243,156,195,.08)", "--gold-chip": "rgba(243,156,195,.15)", "--gold-band": "rgba(243,156,195,.13)",
        "--hero-a": "rgba(243,156,195,.14)", "--hero-b": "rgba(88,179,155,.09)",
        "--tl-e": "#6cc7ae", "--tl-v": "#e6be67",
    },
    "demonhunter-devourer": {
        "theme_name": "恶魔猎手紫暗底", "cls_zh": "噬灭恶魔猎手", "spec_en": "DEVOURER DEMON HUNTER", "spec_zh": "噬灭",
        "--bg": "#100e0d", "--nav-bg": "rgba(16,14,13,.92)",
        "--panel": "#181514", "--panel-2": "#201c1a", "--line": "#332d29", "--line-2": "#463e38",
        "--ink": "#ebe7da", "--ink-2": "#d4cec2", "--mute": "#a8a3b0", "--faint": "#8a8594",
        "--gold": "#c77ae6", "--gold-dim": "#6e3a8a", "--on-gold": "#180d1e",
        "--gold-bg": "rgba(199,122,230,.085)", "--gold-chip": "rgba(199,122,230,.15)", "--gold-band": "rgba(199,122,230,.13)",
        "--hero-a": "rgba(199,122,230,.15)", "--hero-b": "rgba(155,214,95,.09)",
        "--tl-e": "#9bd65f", "--tl-v": "#7fb0f5",
    },
    "warrior-arms": {
        "theme_name": "战士铁褐暗底", "cls_zh": "武器战", "spec_en": "ARMS WARRIOR", "spec_zh": "武器",
        "--bg": "#11100f", "--nav-bg": "rgba(17,16,15,.92)",
        "--panel": "#191715", "--panel-2": "#211e1b", "--line": "#34302b", "--line-2": "#48423b",
        "--ink": "#ece6da", "--ink-2": "#d4cec2", "--mute": "#aba49a", "--faint": "#8d867d",
        "--gold": "#d8ad7e", "--gold-dim": "#7c5e3c", "--on-gold": "#19130c",
        "--gold-bg": "rgba(216,173,126,.08)", "--gold-chip": "rgba(216,173,126,.15)", "--gold-band": "rgba(216,173,126,.13)",
        "--hero-a": "rgba(216,173,126,.14)", "--hero-b": "rgba(143,174,196,.09)",
        "--tl-e": "#8faec4", "--tl-v": "#e49d6e",
    },
    "shaman-elemental": {
        "theme_name": "萨满雷蓝暗底", "cls_zh": "元素萨满", "spec_en": "ELEMENTAL SHAMAN", "spec_zh": "元素",
        "--bg": "#0d1014", "--nav-bg": "rgba(13,16,20,.92)",
        "--panel": "#141920", "--panel-2": "#1a2029", "--line": "#2a323e", "--line-2": "#3b4655",
        "--ink": "#e8eaee", "--ink-2": "#cfd4dc", "--mute": "#a2abb8", "--faint": "#848e9c",
        "--gold": "#5fb0ff", "--gold-dim": "#2f5f8f", "--on-gold": "#08131f",
        "--gold-bg": "rgba(95,176,255,.08)", "--gold-chip": "rgba(95,176,255,.15)", "--gold-band": "rgba(95,176,255,.13)",
        "--hero-a": "rgba(95,176,255,.14)", "--hero-b": "rgba(224,168,92,.09)",
        "--tl-e": "#e0a85c", "--tl-v": "#9be06a",
    },
}


def build_head(cls_slug: str, cls_zh: str, dungeon: str, pal: Dict[str, str]) -> str:
    head = SAMPLE_HEAD.read_text(encoding="utf-8")
    head = re.sub(r"<title>.*?</title>", f"<title>{cls_zh} · {dungeon} 应对手册</title>", head)
    head = head.replace("全职业攻略样板（毒林夜色配色）", f"{cls_zh} · {dungeon}（{pal['theme_name']}）")
    for k, v in pal.items():
        if k.startswith("--"):
            head = re.sub(rf"{re.escape(k)}:[^;]+;", f"{k}:{v};", head)
    return head


def build_body(cls_zh: str, spec_zh: str, spec_en: str, dungeon: str, dungeon_en: str, date_ym: str) -> str:
    return f"""<body>

<header>
  <div class="wrap">
    <div class="eyebrow">{dungeon_en.upper()} · MYTHIC+ · {spec_en}</div>
    <h1><span class="cls">{cls_zh}</span><span class="dot">·</span>{dungeon} 应对手册</h1>
    <p class="lede">TODO：用 2–3 句概括本副本核心伤害特点、主大招节奏，以及最关键的一条例外（build_site.py 会提取此句作首页摘要）。</p>
    <div class="chips">
      <span class="chip">参考 <b>TODO 层数限时{spec_zh}（国 / 欧 / 美）</b></span>
      <span class="chip">英雄天赋 <b>TODO</b></span>
    </div>
  </div>
</header>

<nav class="nav" aria-label="阶段导航">
  <div class="wrap">
    <div class="nav-scroll">
      <a href="#prep" class="on">速记</a>
      <a href="#timeline">时间轴</a>
      <span class="sep" aria-hidden="true"></span>
      <a href="#s1">开场</a>
      <a href="#s2"><span class="n">①</span>首领一</a>
      <!-- TODO: 按副本实际路线增删段链接，勿用 00-03 撞号 -->
      <span class="sep" aria-hidden="true"></span>
      <a href="#talent">天赋</a>
    </div>
  </div>
</nav>

<main class="wrap">

<section id="prep">
  <h2><span class="k">00</span>开打前速记</h2>
  <p class="sub">核心手牌定位、硬限制与必处理读条/驱散。</p>

  <div class="cores">
    <article class="core main">
      <div class="top"><img class="ic lg" src="{{{{I:0}}}}" alt=""><div><div class="nm">TODO 主手牌</div><div class="cd">冷却 · 持续</div></div></div>
      <p>TODO：管哪类机制与冷却预留原则。</p>
    </article>
    <article class="core">
      <div class="top"><img class="ic lg" src="{{{{I:0}}}}" alt=""><div><div class="nm">TODO 副手牌</div><div class="cd">冷却 · 持续</div></div></div>
      <p>TODO：一句话定位。</p>
    </article>
    <article class="core">
      <div class="top"><img class="ic lg" src="{{{{I:0}}}}" alt=""><div><div class="nm">TODO 减伤/功能</div><div class="cd">冷却 · 持续</div></div></div>
      <p>TODO：一句话定位。</p>
    </article>
  </div>

  <!-- 可选：无真实机制硬限制时删除整块 .limit -->
  <div class="limit">
    <div class="h">TODO 职业硬限制</div>
    <b>TODO</b>：只写最容易误判致死的铁律（如 30 秒自律、免疫不挡物理等）。
  </div>

  <!-- 可选：无 >=2 个核心必断/必驱目标时删除整块 .kicks-box -->
  <div class="kicks-box">
    <div class="kicks-head">
      <img class="ic" src="{{{{I:0}}}}" alt="">
      <h3>全本必断读条</h3>
      <span>点击跳到对应战斗</span>
    </div>
    <div class="kicks">
      <a class="kick" href="#k-1">
        <div class="meta"><span class="idx">01</span><span>TODO 怪名 · 所在段</span><span class="go">跳转 ↘</span></div>
        <div class="cast">TODO 读条名</div>
        <div class="why">TODO：漏断后果与打断优先级。</div>
      </a>
    </div>
  </div>
</section>

<section id="timeline">
  <h2><span class="k">01</span>一场里关键大招交在哪</h2>
  <p class="sub">一场限时实录（展示真实冷却节奏，非每波强制照搬；具体取舍见下方路线）。</p>
  <div class="tl-card">
    <div class="tl-scroll">
{{{{TIMELINE}}}}
    </div>
    <div class="legend">
      <span><i class="pri"></i>主大招</span>
      <span><i class="e"></i>副手牌 1</span>
      <span><i class="muted"></i>顺手交牌</span>
      <span><i class="boss"></i>首领战</span>
      <span><i class="trash"></i>小怪段</span>
    </div>
  </div>
</section>

<section id="route">
  <h2><span class="k">02</span>按路线逐段</h2>
  <p class="sub">看到什么 → 按什么 → 为什么。带「必做」标签的高亮行是每把必做的关键动作。</p>

  <div class="route">

    <article class="stop trash" id="s1">
      <div class="node">怪</div>
      <div class="stop-body">
        <div class="stop-head"><h3>开场 → 首领一</h3><span class="kind">TRASH · TODO 小怪名单</span></div>
        <div class="rhythm"><span class="lbl">节奏</span>TODO：1–2 句（建议 ≤ 90 字），写清冷却取舍结论与未转好备选。</div>
        <div class="rows">
          <div class="row" id="k-1">
            <div class="mech"><img class="ic" src="{{{{I:0}}}}" alt=""><div><div class="n">TODO 机制名</div><div class="s">怪名 · 性质与持续</div></div></div>
            <div class="to">→</div>
            <div class="skill"><span class="btn-chip"><img class="ic sm" src="{{{{I:0}}}}" alt="">技能名</span><span class="tgt">给队友（保人用，否则删）</span></div>
            <div class="why">TODO：1–2 句（建议 ≤ 45 字），写按键时机与核心原因；不复述左列属性与节奏栏。</div>
          </div>
        </div>
        <div class="stop-foot">
          <div class="plan"><span>TODO 建议节奏</span></div>
          <a class="next" href="#s2">下一段：首领一 ↓</a>
        </div>
      </div>
    </article>

    <article class="stop boss" id="s2">
      <div class="node">1</div>
      <div class="stop-body">
        <div class="stop-head"><h3>首领一</h3><span class="kind">BOSS 1</span></div>
        <div class="rhythm"><span class="lbl">节奏</span>TODO：1–2 句（建议 ≤ 90 字，复杂首领 ≤ 130 字），写首领核心轴结论与大招分配。</div>
        <div class="rows">
          <div class="row must">
            <div class="mech"><img class="ic" src="{{{{I:0}}}}" alt=""><div><div class="n"><span class="badge-must">必做</span>TODO 必做机制</div><div class="s">性质与时机</div></div></div>
            <div class="to">→</div>
            <div class="skill"><span class="btn-chip pri"><img class="ic sm" src="{{{{I:0}}}}" alt="">主技能</span></div>
            <div class="why">TODO：1–2 句（必做/步骤行建议 ≤ 70 字），写精确时机与收益；细节推演记 NOTES.md。</div>
          </div>
        </div>
        <div class="stop-foot">
          <div class="plan"><span>TODO 建议节奏</span></div>
          <a class="next" href="#talent">查看天赋 ↓</a>
        </div>
      </div>
    </article>

  </div>
</section>

<section id="talent">
  <h2><span class="k">03</span>天赋</h2>
  <p class="sub">取自限时录像的天赋。复制字符串，在游戏天赋界面点「导入」。</p>
  <div class="talent">
    <!-- 若 5 场均无 WCL 天赋记录，删除下方 .code-row 并在 NOTES.md 注明 -->
    <div class="code-row">
      <code id="talent-code">{{{{TALENT}}}}</code>
      <button type="button" id="copy-btn">复制</button>
    </div>
    <p class="tal-label">这几个防御/功能天赋不要动</p>
    <div class="tal-grid">
      <div class="tal key"><img class="ic" src="{{{{I:0}}}}" alt=""><div><b>TODO 天赋 1</b><span>一句话说明实效。</span></div></div>
      <div class="tal key"><img class="ic" src="{{{{I:0}}}}" alt=""><div><b>TODO 天赋 2</b><span>一句话说明实效。</span></div></div>
    </div>
    <p class="tal-note">常见可换：<b>TODO</b>。</p>
  </div>
</section>

</main>

<footer>
  <div class="wrap">
    <div>{cls_zh} · {dungeon} 应对手册 · {date_ym}</div>
    <div class="refs">参考录像：
      <!-- TODO: 填入 5 场 WCL 链接（玩家名 + 层数 + 用时，正文禁止出现玩家名） -->
      <a href="https://www.warcraftlogs.com/reports/TODO#fight=1">TODO +24 00:00</a>
    </div>
  </div>
</footer>

<script>
(function(){{
  var btn=document.getElementById("copy-btn"), code=document.getElementById("talent-code");
  if(btn&&code){{
    btn.addEventListener("click",function(){{
      var t=code.textContent.trim();
      function done(){{btn.textContent="已复制";setTimeout(function(){{btn.textContent="复制";}},1600);}}
      function fallback(){{var r=document.createRange();r.selectNodeContents(code);var sel=window.getSelection();sel.removeAllRanges();sel.addRange(r);try{{document.execCommand("copy");done();}}catch(e){{btn.textContent="已选中，按 Ctrl+C";}}}}
      if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(t).then(done,fallback);}}else{{fallback();}}
    }});
  }}

  var links={{}};
  document.querySelectorAll(".nav a[href^='#']").forEach(function(a){{links[a.getAttribute("href").slice(1)]=a;}});
  var targets=Object.keys(links).map(function(id){{return document.getElementById(id);}}).filter(Boolean);
  function spy(){{
    var y=window.scrollY+110, cur=targets[0]?targets[0].id:null;
    targets.forEach(function(el){{if(el.getBoundingClientRect().top+window.scrollY<=y) cur=el.id;}});
    if(targets.length&&window.innerHeight+window.scrollY>=document.documentElement.scrollHeight-4) cur=targets[targets.length-1].id;
    Object.keys(links).forEach(function(id){{links[id].classList.toggle("on",id===cur);}});
  }}
  window.addEventListener("scroll",spy,{{passive:true}}); spy();
}})();
</script>
</body>
</html>
"""


def build_script(out_rel: str) -> str:
    return f'''"""Offline/auto-icon rebuild: python3 build.py [out.html]
Default output: {out_rel}
Uses shared guides/tools/timeline.py and guides/tools/icons.py (inject_icons)."""
import json
import os
import re
import sys

H = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = H  # 如复用兄弟目录证据/天赋，改为对应路径并在 NOTES.md 说明
TOOLS = os.path.join(H, '../../../tools')
sys.path.insert(0, TOOLS)
from icons import externalize, inject_icons
from timeline import GOLD_TL_CSS, timeline

# TODO: 填入代表性录像的总时长（秒）、波次带 BANDS 与关键技能标记 MARKS（标签 <= 8 字，常规 6-14 点）
TOTAL_SEC = 1800.0
BANDS = [
    ('0:10', '5:00', '开场小怪', 'trash'),
    ('5:10', '9:00', '首领一', 'boss'),
]
# '' = 主大招 (--gold), 'e' = 副手牌1 (--tl-e), 'v' = 副手牌2 (--tl-v), 'muted' = 顺手交牌 (灰)
MARKS = [
    ('6:00', '', 0, 'TODO 标记'),
]

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '{out_rel}')

s = (open(os.path.join(H, 'head.part'), encoding='utf-8').read()
     + open(os.path.join(H, 'body.part'), encoding='utf-8').read())
s = s.replace('{{{{TLCSS}}}}', GOLD_TL_CSS)
s = s.replace('{{{{TIMELINE}}}}', timeline(TOTAL_SEC, BANDS, MARKS))
if '{{{{TALENT}}}}' in s:
    s = s.replace('{{{{TALENT}}}}', json.load(open(os.path.join(DATA_DIR, 'tstring.json'), encoding='utf-8'))['string'])

fallback_ic = os.path.join(DATA_DIR, 'icons.json')
s, n_icons, n_fetched = inject_icons(s, out, fallback_json=fallback_ic if os.path.isfile(fallback_ic) else None)
assert '{{{{' not in s, re.findall(r'\\{{\\{{[^}}]*\\}}\\}}', s)[:5]

with open(out, 'w', encoding='utf-8') as f:
    f.write(s)
print(f'{{out}} ({{len(s)}} bytes) | icons={{n_icons}} (newly fetched={{n_fetched}})')
ext_n, ext_saved = externalize(out)
if ext_n:
    print(f'externalized extra base64: {{ext_n}} (-{{ext_saved}} bytes)')
'''


def build_notes(cls_slug: str, slug: str, cls_zh: str, dungeon: str, out_name: str) -> str:
    return f"""# {dungeon} · {cls_zh} — 结论依据

## 样本与重建

- 五场限时录像（证据包在 `evidence/`）：
  - r1 TODO
  - r2 TODO
  - r3 TODO
  - r4 TODO
  - r5 TODO
- 编码天赋（仓库根目录执行）：
  `python3 guides/tools/enc.py --in guides/{cls_slug}/sources/{slug}-v2/evidence/talents.json --out guides/{cls_slug}/sources/{slug}-v2/tstring.json`
- 重建与门禁校验（仓库根目录执行）：
  `python3 guides/{cls_slug}/sources/{slug}-v2/build.py && python3 guides/tools/check.py guides/{cls_slug}/{out_name} --source-dir guides/{cls_slug}/sources/{slug}-v2 --published`

## 技能基础窗口与关键结论依据

### 技能基础窗口来源（`evidence/spells.md`）
- TODO：核对 `spells.md` 输出的基础冷却、充能、持续秒数与天赋改写冷却（不要仅靠最短施放间隔反推冷却）。

### 关键结论（窗口内外对比）
- TODO：按波次/机制记录 `compare.md`（注意直击/跳伤已拆分）、`uses.md`、`interrupts.md`、`debuffs.md` 与保人补查的量化依据。

## 删掉的低样本打法

- TODO：记录 5 场里仅 1–2 人做、未写入正文常规推荐的打法（或明确单场观察未进对比条）。

## 天赋核对与补查

- 天赋：`enc.py` 编码后解码 0 不一致（或记录 5 场均无天赋数据并省略导入栏）；写出 5 人天赋差异。
- `wcl.py events` 补查：记录补查了哪些窗口、结论是什么，以及证据包缺了什么。
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Scaffold a new DPS guide source directory.")
    ap.add_argument("--class", dest="cls", required=True, help="Class directory slug under guides/ (e.g. paladin-ret)")
    ap.add_argument("--slug", required=True, help="Dungeon pinyin slug (e.g. hongyu -> sources/hongyu-v2/)")
    ap.add_argument("--dungeon", required=True, help="Chinese dungeon name matching build_site.py DUNGEON_INFO")
    ap.add_argument("--en", required=True, help="English dungeon name")
    ap.add_argument("--cls-zh", help="Override Chinese class/spec display name")
    ap.add_argument("--spec-en", help="Override English spec eyebrow")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="YYYY-MM-DD for default output filename")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files in target directory")
    args = ap.parse_args()

    pal = dict(PALETTES.get(args.cls, PALETTES["rogue"]))
    cls_zh = args.cls_zh or pal["cls_zh"]
    spec_en = args.spec_en or pal["spec_en"]
    spec_zh = pal["spec_zh"]
    if args.cls not in PALETTES:
        print(f"NOTE: '{args.cls}' not in built-in PALETTES; copied rogue defaults — update :root colors per GUIDE-SPEC.md.")

    target = GUIDES / args.cls / "sources" / f"{args.slug}-v2"
    if target.exists() and not args.force and (target / "body.part").exists():
        raise SystemExit(f"Target already exists with body.part: {target} (pass --force to overwrite)")
    target.mkdir(parents=True, exist_ok=True)

    out_name = f"{args.date}-{args.dungeon}-{cls_zh}.html"
    out_rel = f"../../{out_name}"

    (target / "head.part").write_text(build_head(args.cls, cls_zh, args.dungeon, pal), encoding="utf-8")
    (target / "body.part").write_text(build_body(cls_zh, spec_zh, spec_en, args.dungeon, args.en, args.date[:7]), encoding="utf-8")
    (target / "build.py").write_text(build_script(out_rel), encoding="utf-8")
    (target / "NOTES.md").write_text(build_notes(args.cls, args.slug, cls_zh, args.dungeon, out_name), encoding="utf-8")

    print(f"Scaffolded: {target}")
    print(f"Default output: guides/{args.cls}/{out_name}")


if __name__ == "__main__":
    main()
