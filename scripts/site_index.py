"""Home page and 404 page for the public guide site (Python standard library)."""

from html import escape, unescape
import re
from urllib.parse import quote

# Display order and metadata. Colors are the in-game class colors.
CLASS_META = {
    "demonhunter-devourer": ("噬灭恶魔猎手", "恶魔猎手", "远程输出", "#A330C9"),
    "warrior-arms": ("武器战", "战士", "近战输出", "#C69B6D"),
    "rogue": ("潜行者", "潜行者", "近战输出", "#FFF468"),
    "holy-paladin": ("神圣骑士", "圣骑士", "治疗", "#F48CBA"),
    "paladin-ret": ("惩戒骑士", "圣骑士", "近战输出", "#F48CBA"),
}
DUNGEONS = ["夺目谷", "塞塔里斯神庙", "密谋小径", "毒牙祭坛",
            "红玉新生法池", "纳洛拉克的洞穴", "虚空之痕竞技场", "诸王之眠"]

LEDE = re.compile(r'<p class="lede">(.*?)</p>', re.S)
TAG = re.compile(r"<[^>]+>")

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900'
         '&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">')

CSS = """
:root{
  --bg:#0f0d0c; --panel:#171412; --panel-2:#1f1b18; --line:#2f2925; --line-2:#3d3530;
  --ink:#ece7db; --mute:#a29c92; --faint:#6c665e; --gold:#e2b45c; --gold-dim:#7a5f2c;
  --display:"Noto Serif SC","Songti SC","STSong",serif;
  --body:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
  color-scheme:dark;
}
*{box-sizing:border-box}
html{background:var(--bg);scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 var(--body);-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
a:focus-visible{outline:2px solid var(--gold);outline-offset:2px;border-radius:6px}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
h1,h2,h3{font-family:var(--display);margin:0;letter-spacing:.01em;text-wrap:balance}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}

/* hero */
header.hero{position:relative;overflow:hidden;border-bottom:1px solid var(--line);
  background:
   radial-gradient(800px 340px at 88% -10%,rgba(163,48,201,.16),transparent 70%),
   radial-gradient(700px 320px at 8% 120%,rgba(226,180,92,.10),transparent 70%),
   radial-gradient(500px 260px at 55% 40%,rgba(244,140,186,.05),transparent 70%)}
header.hero::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.35;
  background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);
  background-size:56px 56px;mask-image:radial-gradient(ellipse at 70% 30%,#000 0%,transparent 65%)}
.hero .wrap{position:relative;z-index:1;padding-top:72px;padding-bottom:56px}
.eyebrow{font:700 12px var(--mono);letter-spacing:.2em;color:var(--gold);display:flex;align-items:center;gap:10px}
.eyebrow::before{content:"";width:28px;height:1px;background:var(--gold)}
.hero h1{font-size:clamp(40px,7vw,68px);font-weight:900;line-height:1.08;margin:18px 0 0}
.hero h1 em{font-style:normal;background:linear-gradient(100deg,#f3d28c,#e2b45c 45%,#c77ae6);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.hero p.dek{max-width:620px;color:var(--mute);font-size:16px;margin:18px 0 0}
.stats{display:flex;flex-wrap:wrap;gap:12px;margin-top:34px}
.stat{background:rgba(23,20,18,.7);border:1px solid var(--line);border-radius:12px;padding:12px 18px;min-width:120px;backdrop-filter:blur(4px)}
.stat b{display:block;font:700 26px var(--mono);color:var(--ink);line-height:1.2}
.stat span{font-size:12px;color:var(--faint);letter-spacing:.06em}
.jump{display:flex;flex-wrap:wrap;gap:8px;margin-top:28px}
.chip{display:inline-flex;align-items:center;gap:8px;padding:7px 14px;border:1px solid var(--line-2);border-radius:999px;
  font-size:13px;color:var(--ink);background:var(--panel);transition:border-color .15s,background .15s}
.chip:hover{border-color:var(--c);background:var(--panel-2)}
.chip i{width:8px;height:8px;border-radius:50%;background:var(--c);box-shadow:0 0 10px var(--c)}

/* section headings */
section{padding:56px 0 8px}
.sec-h{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:20px}
.sec-h h2{font-size:26px;font-weight:900;display:flex;align-items:baseline;gap:14px}
.sec-h h2 .k{font:700 12px var(--mono);color:var(--gold);letter-spacing:.14em}
.sec-h p{margin:0;color:var(--mute);font-size:14px}

/* matrix */
.matrix-box{border:1px solid var(--line);border-radius:14px;background:var(--panel);overflow-x:auto}
table.matrix{width:100%;border-collapse:collapse;min-width:720px}
.matrix th,.matrix td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:center;font-size:13px;white-space:nowrap}
.matrix tr:last-child td{border-bottom:0}
.matrix thead th{font-weight:500;color:var(--mute);background:var(--panel-2);position:sticky;top:0}
.matrix thead th span{display:inline-flex;align-items:center;gap:7px}
.matrix thead th i{width:7px;height:7px;border-radius:50%;background:var(--c)}
.matrix th[scope=row]{text-align:left;font-family:var(--display);font-weight:600;font-size:15px;color:var(--ink)}
.matrix td a{display:inline-flex;align-items:center;justify-content:center;width:34px;height:28px;border-radius:7px;
  background:color-mix(in srgb,var(--c) 14%,transparent);border:1px solid color-mix(in srgb,var(--c) 40%,transparent);
  color:var(--c);font-weight:700;transition:transform .12s,background .12s}
.matrix td a:hover{transform:translateY(-1px);background:color-mix(in srgb,var(--c) 28%,transparent)}
.matrix td .none{color:var(--faint)}
.matrix th:first-child{position:sticky;left:0;z-index:1;background:var(--panel);box-shadow:1px 0 0 var(--line)}
.matrix thead th:first-child{background:var(--panel-2);z-index:2}
.matrix tbody tr:hover{background:rgba(255,255,255,.015)}

/* class sections */
.cls{margin-top:40px;scroll-margin-top:20px}
.cls-head{display:flex;align-items:center;gap:16px;padding:18px 20px;border:1px solid var(--line);border-radius:14px 14px 0 0;
  background:linear-gradient(100deg,color-mix(in srgb,var(--c) 16%,var(--panel)) 0%,var(--panel) 60%);border-bottom:0;position:relative}
.cls-head::before{content:"";position:absolute;left:0;top:14px;bottom:14px;width:3px;border-radius:0 3px 3px 0;background:var(--c)}
.sigil{width:46px;height:46px;flex:none;border-radius:12px;display:grid;place-items:center;font:900 20px var(--display);
  color:#0f0d0c;background:var(--c);box-shadow:0 0 24px color-mix(in srgb,var(--c) 40%,transparent)}
.cls-head h3{font-size:22px;font-weight:900}
.cls-head .meta{color:var(--mute);font-size:13px;margin-top:2px}
.cls-head .count{margin-left:auto;text-align:right;font:700 22px var(--mono);color:var(--c);line-height:1.1}
.cls-head .count small{display:block;font:400 11px var(--body);color:var(--faint);letter-spacing:.06em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:0 0 14px 14px;overflow:hidden}
.card{background:var(--panel);padding:18px 18px 16px;display:flex;flex-direction:column;gap:8px;min-height:168px;transition:background .15s;position:relative}
.card:hover{background:var(--panel-2)}
.card a.main::after{content:"";position:absolute;inset:0}
.card .top{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.card h4{margin:0;font:600 17px var(--display);color:var(--ink)}
.card:hover h4{color:var(--c)}
.card .date{font:500 11px var(--mono);color:var(--faint)}
.card p{margin:0;color:var(--mute);font-size:13px;line-height:1.6;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card .foot{margin-top:auto;display:flex;align-items:center;gap:10px;font-size:12px;color:var(--faint);flex-wrap:wrap}
.card .go{color:var(--c);font-weight:500}
.card .old{position:relative;z-index:1;color:var(--faint);border-bottom:1px dashed var(--line-2)}
.card .old:hover{color:var(--ink)}
.card.feature{grid-column:1/-1;min-height:0;flex-direction:row;align-items:center;gap:18px;
  background:linear-gradient(90deg,color-mix(in srgb,var(--c) 9%,var(--panel)),var(--panel))}
.card.feature .badge{font:700 11px var(--mono);letter-spacing:.14em;color:#0f0d0c;background:var(--c);padding:3px 8px;border-radius:5px;flex:none}
.card.feature p{-webkit-line-clamp:2}
.card.feature .body{display:flex;flex-direction:column;gap:4px;min-width:0}
.card.empty{background:repeating-linear-gradient(135deg,var(--panel) 0 10px,#151210 10px 20px);min-height:0}
.card.empty h4{color:var(--faint)}
.card.empty p{color:var(--faint)}

footer{margin-top:72px;border-top:1px solid var(--line);padding:28px 0 40px;color:var(--faint);font-size:13px}
footer .wrap{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}

@media (max-width:640px){
  .hero .wrap{padding-top:48px;padding-bottom:40px}
  .stat{min-width:0;flex:1 1 40%}
  .cls-head{padding:16px}
  .cls-head .count{font-size:18px}
  .card.feature{flex-direction:column;align-items:flex-start}
  .card{min-height:0}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
"""


def _parse(path, slug):
    """Split '2026-11-07-夺目谷-武器战' into (date, dungeon or None, title)."""
    parts = path.stem.split("-")
    date, rest = "-".join(parts[:3]), parts[3:]
    dungeon = next((p for p in rest if p in DUNGEONS), None)
    html_text = path.read_text(encoding="utf-8")
    m = LEDE.search(html_text)
    lede = " ".join(unescape(TAG.sub("", m.group(1))).split()) if m else ""
    title = re.search(r"<title>(.*?)</title>", html_text, re.S)
    title = unescape(title.group(1)).strip() if title else path.stem
    return {"date": date, "dungeon": dungeon, "lede": lede, "title": title, "path": path}


def _href(path, root):
    return quote(path.relative_to(root).as_posix())


def _page(title, description, body):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="theme-color" content="#0f0d0c">
<link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
{FONTS}
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""


def write_pages(guides, root, output):
    """guides: [(slug, [html paths newest first])]."""
    classes = []
    for slug, pages in guides:
        name, family, role, color = CLASS_META[slug]
        entries = [_parse(p, slug) for p in pages]
        by_dungeon, overview = {}, []
        for e in entries:  # newest first, so the first per dungeon is current
            (by_dungeon.setdefault(e["dungeon"], []) if e["dungeon"] else overview).append(e)
        classes.append({"slug": slug, "name": name, "family": family, "role": role,
                        "color": color, "by": by_dungeon, "overview": overview, "count": len(entries)})

    total = sum(c["count"] for c in classes)
    covered = sum(len(c["by"]) for c in classes)
    latest = max(e["date"] for c in classes for v in c["by"].values() for e in v)

    chips = "".join(
        f'<a class="chip" href="#{c["slug"]}" style="--c:{c["color"]}"><i></i>{escape(c["name"])}</a>'
        for c in classes)

    head_cells = "".join(
        f'<th scope="col" style="--c:{c["color"]}"><span><i></i>{escape(c["name"])}</span></th>' for c in classes)
    rows = []
    for d in DUNGEONS:
        cells = []
        for c in classes:
            hit = c["by"].get(d)
            if hit:
                cells.append(f'<td style="--c:{c["color"]}"><a href="{_href(hit[0]["path"], root)}" '
                             f'title="{escape(c["name"])} · {escape(d)}" aria-label="{escape(c["name"])} · {escape(d)}">✓</a></td>')
            else:
                cells.append('<td><span class="none" aria-label="暂无">—</span></td>')
        rows.append(f'<tr><th scope="row">{escape(d)}</th>{"".join(cells)}</tr>')

    sections = []
    for c in classes:
        cards = []
        for e in c["overview"]:
            cards.append(f'''<article class="card feature">
<span class="badge">合集</span>
<div class="body"><h4><a class="main" href="{_href(e["path"], root)}">{escape(e["title"])}</a></h4>
<p>{escape(e["lede"])}</p></div></article>''')
        for d in DUNGEONS:
            versions = c["by"].get(d)
            if not versions:
                cards.append(f'<article class="card empty"><div class="top"><h4>{escape(d)}</h4></div><p>整理中</p></article>')
                continue
            cur, old = versions[0], versions[1:]
            old_links = "".join(
                f'<a class="old" href="{_href(o["path"], root)}">旧版 {o["date"][5:]}</a>' for o in old)
            cards.append(f'''<article class="card">
<div class="top"><h4><a class="main" href="{_href(cur["path"], root)}">{escape(d)}</a></h4><span class="date">{cur["date"]}</span></div>
<p>{escape(cur["lede"])}</p>
<div class="foot"><span class="go">阅读手册 →</span>{old_links}</div>
</article>''')
        sections.append(f'''<div class="cls" id="{c["slug"]}" style="--c:{c["color"]}">
<div class="cls-head"><div class="sigil" aria-hidden="true">{escape(c["name"][0])}</div>
<div><h3>{escape(c["name"])}</h3><div class="meta">{escape(c["family"])} · {escape(c["role"])}</div></div>
<div class="count">{len(c["by"])}<span style="color:var(--faint)">/{len(DUNGEONS)}</span><small>副本已覆盖</small></div></div>
<div class="grid">{"".join(cards)}</div></div>''')

    body = f'''<header class="hero"><div class="wrap">
<div class="eyebrow">WCL RAIDER · MYTHIC+</div>
<h1>大秘境<em>作战手册</em></h1>
<p class="dek">从高分 Warcraft Logs 记录里整理的职业副本手册：每个首领和小怪技能该交哪个技能、什么时候交，按路线从头讲到尾。</p>
<div class="stats">
<div class="stat"><b>{total}</b><span>篇手册</span></div>
<div class="stat"><b>{len(classes)}</b><span>个专精</span></div>
<div class="stat"><b>{len(DUNGEONS)}</b><span>个副本 · 覆盖 {covered} 格</span></div>
<div class="stat"><b>{latest[5:].replace("-", ".")}</b><span>最近更新 · {latest[:4]}</span></div>
</div>
<nav class="jump" aria-label="按职业跳转">{chips}</nav>
</div></header>
<main class="wrap">
<section aria-labelledby="h-matrix">
<div class="sec-h"><h2 id="h-matrix"><span class="k">01</span>按副本速查</h2><p>点亮的格子直接打开该职业在该副本的最新手册。</p></div>
<div class="matrix-box"><table class="matrix"><thead><tr><th scope="col">副本</th>{head_cells}</tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
</section>
<section aria-labelledby="h-classes">
<div class="sec-h"><h2 id="h-classes"><span class="k">02</span>按职业浏览</h2><p>每张卡片是该副本最新一版的开篇摘要；旧版保留在卡片底部。</p></div>
{"".join(sections)}
</section>
</main>
<footer><div class="wrap"><span>数据来自 Warcraft Logs 公开记录，技能数值以游戏内为准。</span><span class="mono">wcl-raider</span></div></footer>'''
    (output / "index.html").write_text(
        _page("大秘境作战手册 · wcl-raider", "按职业和副本整理的魔兽世界大秘境应对手册。", body), encoding="utf-8")

    not_found = '''<header class="hero" style="min-height:100vh;display:grid;place-items:center;border:0"><div class="wrap" style="text-align:center">
<div class="eyebrow" style="justify-content:center">404 · NOT FOUND</div>
<h1>这条路<em>走不通</em></h1>
<p class="dek" style="margin-left:auto;margin-right:auto">页面不存在，可能是手册换了新版本。</p>
<div class="jump" style="justify-content:center"><a class="chip" href="/" style="--c:#e2b45c"><i></i>返回攻略首页</a></div>
</div></header>'''
    (output / "404.html").write_text(_page("页面未找到 · wcl-raider", "页面未找到", not_found), encoding="utf-8")
    icon = root / "assets" / "icon.svg"
    if icon.is_file():
        (output / "assets").mkdir(exist_ok=True)
        (output / "assets" / "icon.svg").write_bytes(icon.read_bytes())
