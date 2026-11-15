"""Home page and 404 page for the public guide site (Python standard library)."""

from html import escape, unescape
import json
import re
from urllib.parse import quote

# Display order and metadata: name, class, role, in-game class color, text color on that color.
CLASS_META = {
    "demonhunter-devourer": ("噬灭恶魔猎手", "恶魔猎手", "远程输出", "#A330C9", "#ffffff"),
    "warrior-arms": ("武器战", "战士", "近战输出", "#C69B6D", "#18213B"),
    "rogue": ("潜行者", "潜行者", "近战输出", "#FFF468", "#18213B"),
    "holy-paladin": ("神圣骑士", "圣骑士", "治疗", "#F48CBA", "#18213B"),
    "paladin-ret": ("惩戒骑士", "圣骑士", "近战输出", "#F48CBA", "#18213B"),
}
DUNGEONS = ["夺目谷", "塞塔里斯神庙", "密谋小径", "毒牙祭坛",
            "红玉新生法池", "纳洛拉克的洞穴", "虚空之痕竞技场", "诸王之眠"]

LEDE = re.compile(r'<p class="lede">(.*?)</p>', re.S)
TAG = re.compile(r"<[^>]+>")

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900'
         '&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">')

CSS = """
:root{
  --bg:#E7EBEF; --surface:#F5F7F9; --ink:#18213B; --slate:#586379; --faint:#8A93A4; --rule:#C7CED8;
  --c:#18213B; --on-c:#ffffff; --c-ink:#18213B;
  --display:"Noto Serif SC","Songti SC","STSong",serif;
  --body:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#10151F; --surface:#171E2B; --ink:#E5E9F0; --slate:#9AA4B6; --faint:#667086; --rule:#283143; color-scheme:dark}}
:root[data-theme="dark"]{--bg:#10151F; --surface:#171E2B; --ink:#E5E9F0; --slate:#9AA4B6; --faint:#667086; --rule:#283143; color-scheme:dark}

*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 var(--body);-webkit-font-smoothing:antialiased;
  font-variant-numeric:tabular-nums;border-top:6px solid var(--c);transition:border-color .5s}
a{color:inherit}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px;border-radius:4px}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
h1,h2,h3{font-family:var(--display);margin:0;text-wrap:balance}

/* masthead */
.mast{padding-top:56px;padding-bottom:40px}
.mast h1{font-size:clamp(34px,6vw,56px);font-weight:900;line-height:1.15;letter-spacing:.02em}
.mast p{margin:14px 0 0;max-width:34em;color:var(--slate)}

/* class switcher */
.switch{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:8px;margin:0;padding:0;list-style:none}
.switch a{display:flex;flex-direction:column;gap:2px;height:100%;padding:12px 14px 12px;text-decoration:none;border-radius:6px;
  background:var(--surface);border-top:4px solid var(--k);transition:background .25s,color .25s}
.switch a:hover{background:color-mix(in srgb,var(--k) 18%,var(--surface))}
.switch b{font:900 18px/1.3 var(--display)}
.switch span{font-size:13px;color:var(--slate);transition:color .25s}
.switch a[aria-current="true"]{background:var(--k);color:var(--on-k)}
.switch a[aria-current="true"] span{color:inherit;opacity:.8}

/* dungeon list */
.panel{margin-top:40px}
.panel h2.who{font-size:15px;font-family:var(--body);font-weight:700;color:var(--slate);margin-bottom:8px}
.js .panel h2.who{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.rows{list-style:none;margin:0;padding:0;border-top:2px solid var(--ink)}
.row{position:relative;display:grid;grid-template-columns:minmax(0,5fr) minmax(0,6fr);gap:8px 40px;align-items:baseline;
  padding:24px 0 24px 28px;border-bottom:1px solid var(--rule)}
.row::before{content:"";position:absolute;left:0;top:0;bottom:-1px;width:4px;background:var(--c);transition:width .2s,background-color .5s}
.row:hover::before,.row:focus-within::before{width:10px}
.row h3{font-size:clamp(26px,3.6vw,40px);font-weight:900;line-height:1.2;letter-spacing:.02em}
.row h3 a{text-decoration:none}
.row h3 a::after{content:"";position:absolute;inset:0}
.row:hover h3 a{text-decoration:underline;text-decoration-color:var(--c);text-decoration-thickness:4px;text-underline-offset:8px}
.row p{margin:0;color:var(--slate);font-size:15px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.row .meta{grid-column:2;display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--faint)}
.row .meta a{position:relative;z-index:1;color:var(--slate)}
.row .meta a:hover{color:var(--ink)}
.row.todo::before{background:var(--rule)}
.row.todo h3{color:var(--faint);font-weight:600}
.row.todo p{color:var(--faint)}
.row.collection{background:color-mix(in srgb,var(--c) 14%,transparent);border-bottom-color:transparent}
.row.collection h3{font-size:clamp(20px,2.6vw,26px)}

footer{margin-top:80px;padding:28px 0 48px;color:var(--faint);font-size:13px}
footer .wrap{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;padding-top:24px;box-shadow:inset 0 1px var(--rule)}

/* 404 */
.lost{min-height:calc(100vh - 6px);display:grid;align-content:center}
.lost h1{font-size:clamp(40px,8vw,80px);font-weight:900;line-height:1.1}
.lost p{color:var(--slate);margin:16px 0 28px}
.lost a{display:inline-block;padding:10px 20px;border-radius:6px;background:var(--ink);color:var(--bg);text-decoration:none;font-weight:700}

@media (max-width:760px){
  .switch{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
  .row{grid-template-columns:1fr;padding-left:20px}
  .row .meta{grid-column:1}
}
@media (max-width:480px){.wrap{padding-left:16px;padding-right:16px}.mast{padding-top:40px;padding-bottom:28px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

SCRIPT = """
(function(){
  var root=document.documentElement, tabs=[].slice.call(document.querySelectorAll('.switch a')),
      panels=[].slice.call(document.querySelectorAll('.panel'));
  if(!tabs.length) return;
  root.classList.add('js');
  function show(slug, push){
    var tab=tabs.filter(function(t){return t.dataset.slug===slug})[0]||tabs[0];
    tabs.forEach(function(t){t.setAttribute('aria-current', t===tab?'true':'false')});
    panels.forEach(function(p){p.hidden=p.id!==tab.dataset.slug});
    root.style.setProperty('--c', tab.dataset.color);
    try{localStorage.setItem('wr-class', tab.dataset.slug)}catch(e){}
    if(push) history.replaceState(null,'','#'+tab.dataset.slug);
  }
  tabs.forEach(function(t){t.addEventListener('click',function(e){e.preventDefault();show(t.dataset.slug,true)})});
  var saved=null; try{saved=localStorage.getItem('wr-class')}catch(e){}
  show(location.hash.slice(1)||saved, false);
  window.addEventListener('hashchange',function(){show(location.hash.slice(1),false)});
})();
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


def _date(d):
    y, m, day = d.split("-")
    return f"{y}年{int(m)}月{int(day)}日"


def _page(title, description, body, script=""):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="theme-color" content="#E7EBEF" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#10151F" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
{FONTS}
<style>{CSS}</style>
</head>
<body>
{body}
{f"<script>{script}</script>" if script else ""}
</body>
</html>
"""


def write_pages(guides, root, output):
    """guides: [(slug, [html paths newest first])]."""
    classes = []
    for slug, pages in guides:
        name, family, role, color, on = CLASS_META[slug]
        entries = [_parse(p, slug) for p in pages]
        by_dungeon, overview = {}, []
        for e in entries:  # newest first, so the first per dungeon is current
            (by_dungeon.setdefault(e["dungeon"], []) if e["dungeon"] else overview).append(e)
        classes.append({"slug": slug, "name": name, "family": family, "role": role,
                        "color": color, "on": on, "by": by_dungeon, "overview": overview})

    tabs = "".join(
        f'<li><a href="#{c["slug"]}" data-slug="{c["slug"]}" data-color="{c["color"]}" '
        f'style="--k:{c["color"]};--on-k:{c["on"]}"><b>{escape(c["name"])}</b>'
        f'<span>{escape(c["role"])}，{len(c["by"])} 个副本</span></a></li>'
        for c in classes)

    panels = []
    for c in classes:
        rows = []
        for e in c["overview"]:
            rows.append(f'''<li class="row collection"><h3><a href="{_href(e["path"], root)}">{escape(e["title"])}</a></h3>
<p>{escape(e["lede"])}</p></li>''')
        for d in DUNGEONS:
            versions = c["by"].get(d)
            if not versions:
                rows.append(f'<li class="row todo"><h3>{escape(d)}</h3><p>这本手册还在整理。</p></li>')
                continue
            cur, old = versions[0], versions[1:]
            old_links = "".join(
                f'<a href="{_href(o["path"], root)}">{_date(o["date"])}的旧版</a>' for o in old)
            rows.append(f'''<li class="row"><h3><a href="{_href(cur["path"], root)}">{escape(d)}</a></h3>
<p>{escape(cur["lede"])}</p>
<div class="meta"><span>{_date(cur["date"])}更新</span>{old_links}</div></li>''')
        panels.append(f'''<section class="panel" id="{c["slug"]}" style="--c:{c["color"]}" aria-label="{escape(c["name"])}">
<h2 class="who">{escape(c["name"])}</h2>
<ol class="rows">{"".join(rows)}</ol></section>''')

    body = f'''<header class="wrap mast">
<h1>大秘境作战手册</h1>
<p>按专精和副本整理的应对手册。先选你的专精，再打开这周要打的副本：每个首领和小怪技能该交什么、什么时候交，按路线从头讲到尾。</p>
</header>
<main class="wrap">
<nav aria-label="选择专精"><ul class="switch" style="--n:{len(classes)}">{tabs}</ul></nav>
{"".join(panels)}
</main>
<footer><div class="wrap"><span>内容整理自 Warcraft Logs 公开的高分记录，技能数值以游戏内为准。</span><span>wcl-raider</span></div></footer>'''
    (output / "index.html").write_text(
        _page("大秘境作战手册", "按专精和副本整理的魔兽世界大秘境应对手册。", body, SCRIPT), encoding="utf-8")

    not_found = '''<main class="wrap lost">
<h1>这条路走不通</h1>
<p>这个页面不存在。手册换了新版本后，旧链接可能已经失效。</p>
<div><a href="/">回到手册首页</a></div>
</main>'''
    (output / "404.html").write_text(_page("页面未找到", "页面未找到", not_found), encoding="utf-8")
    icon = root / "assets" / "icon.svg"
    if icon.is_file():
        (output / "assets").mkdir(exist_ok=True)
        (output / "assets" / "icon.svg").write_bytes(icon.read_bytes())
