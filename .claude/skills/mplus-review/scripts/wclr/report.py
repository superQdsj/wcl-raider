"""render 命令：把结构化的应对技巧报告（JSON）排成本地 HTML（可导出 PDF / PNG / Markdown）。

模型只写内容（JSON，格式见 mplus-tactics/references/report-schema.md），样式全部由这里的固定模板决定；
写作规则（单元格长度、标签集合、正文里不出现工具术语）在渲染前统一检查，不合格就报错。
"""
from __future__ import annotations

import base64
import html
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .api import CACHE_DIR, USER_AGENT, WCLError

# ---------------------------------------------------------------- 词表
TAGS: Dict[str, Tuple[str, str]] = {   # 标签 -> (图标, 色组)
    "点名": ("🎯", "warn"), "读条": ("🌀", "warn"), "全团": ("💥", "warn"), "正面": ("🔺", "warn"),
    "地面": ("🔥", "warn"), "击退": ("💨", "warn"), "打断": ("🤐", "warn"),
    "魔法": ("✨", "magic"), "中毒": ("☠️", "poison"), "疾病": ("🦠", "disease"), "诅咒": ("🧿", "curse"),
    "流血": ("🩸", "bleed"), "减速": ("🐌", "cc"), "定身": ("⛓️", "cc"), "恐惧": ("😱", "cc"),
    "不可驱散": ("🚫", "muted"),
}
ACTIONS: Dict[str, Tuple[str, str]] = {   # 动作类型 -> (图标, 色组)
    "反射": ("🔁", "reflect"), "免疫": ("🛡️", "immune"), "减伤": ("🛡️", "defense"),
    "驱散": ("🧹", "cleanse"), "自解": ("🧹", "cleanse"), "外部": ("🤝", "external"),
    "位移": ("🏃", "move"), "解控": ("🏃", "move"), "走位": ("🏃", "move"),
    "治疗": ("💚", "heal"), "控制": ("✋", "control"), "打断": ("🤐", "control"),
}
TIP_KINDS = {"tip": ("💡", "提示"), "warn": ("⚠️", "注意"), "replay": ("🎬", "回放")}
STRENGTH = {"强", "中", "弱"}
CLASS_COLORS = {
    "DeathKnight": "#C41E3A", "DemonHunter": "#A330C9", "Druid": "#FF7C0A", "Evoker": "#33937F",
    "Hunter": "#AAD372", "Mage": "#3FC7EB", "Monk": "#00FF98", "Paladin": "#F48CBA", "Priest": "#B8B8B8",
    "Rogue": "#FFF468", "Shaman": "#0070DD", "Warlock": "#8788EE", "Warrior": "#C69B6D",
}
BANNED = ["hitType", "伴随", "倍", "×", "/2 场", "/3 场", "/4 场", "/2场", "/3场", "/4场", "wcl ", "p 值", "推断消除"]
LIMITS = {"signal": 15, "why": 16, "handles": 20, "timing": 16, "handling": 26, "note": 44, "summary": 90}


# ---------------------------------------------------------------- 校验
def _digits(text: str) -> int:
    return len(re.findall(r"\d+(?:\.\d+)?", text or ""))


def _spell_ok(obj: Any) -> bool:
    return isinstance(obj, dict) and bool(obj.get("spell"))


def validate(data: Dict[str, Any]) -> List[str]:
    """返回所有问题（空列表 = 通过）。路径写法：route[1].rows[0].why。"""
    errs: List[str] = []

    def need(cond: bool, path: str, msg: str) -> None:
        if not cond:
            errs.append(f"{path}：{msg}")

    def length(text: Any, key: str, path: str) -> None:
        if isinstance(text, str) and len(text) > LIMITS[key]:
            errs.append(f"{path}：{len(text)} 字，超过 {LIMITS[key]} 字（「{text}」）")

    def tags(lst: Any, path: str) -> None:
        if lst is None:
            return
        need(isinstance(lst, list) and len(lst) <= 3, path, "标签要是列表，最多 3 个")
        for t in lst or []:
            need(t in TAGS, path, f"标签 '{t}' 不在规范集里（{'、'.join(TAGS)}）")

    def action(obj: Any, path: str) -> None:
        need(_spell_ok(obj), path, "要是 {spell, id, type} 对象")
        if _spell_ok(obj):
            need(obj.get("type") in ACTIONS, path, f"type '{obj.get('type')}' 不在 {'、'.join(ACTIONS)} 里")

    kind = data.get("kind")
    need(kind in ("class", "team"), "kind", "要是 class（职业专题）或 team（整队版）")
    for key in ("title", "dungeon"):
        need(bool(data.get(key)), key, "必填")
    if kind == "class":
        need(data.get("class") in CLASS_COLORS, "class", f"职业专题要写英文职业名：{'、'.join(CLASS_COLORS)}")
    length(data.get("summary"), "summary", "summary")
    hl = data.get("highlights") or []
    need(1 <= len(hl) <= 3, "highlights", "1–3 条")
    for i, h in enumerate(hl):
        p = f"highlights[{i}]"
        need(bool(h.get("signal")), p, "signal 必填")
        action(h.get("action"), p + ".action")
        length(h.get("signal"), "signal", p + ".signal")
        length(h.get("note"), "note", p + ".note")
        need(_digits(h.get("note", "")) <= 1, p + ".note", "最多一个数字")
        if kind == "team":
            need(bool(h.get("who")), p, "整队版要写 who（职业）")
    for i, t in enumerate(data.get("toolbox") or []):
        p = f"toolbox[{i}]"
        action(t, p)
        need(t.get("usage") in (1, 2, 3), p + ".usage", "常用度 1–3（●○○ / ●●○ / ●●●）")
        length(t.get("handles"), "handles", p + ".handles")
        length(t.get("timing"), "timing", p + ".timing")
    route = data.get("route") or []
    need(bool(route), "route", "至少一段")
    for i, seg in enumerate(route):
        p = f"route[{i}]"
        need(seg.get("kind") in ("boss", "trash"), p + ".kind", "boss 或 trash")
        need(bool(seg.get("name")), p + ".name", "必填（直接用工具'按位置'表的位置名）")
        need(bool(seg.get("rows")), p + ".rows", "至少一行；没有内容的段整段删掉")
        for j, r in enumerate(seg.get("rows") or []):
            q = f"{p}.rows[{j}]"
            need(bool(r.get("mechanic")), q, "mechanic 必填")
            tags(r.get("tags"), q + ".tags")
            action(r.get("action"), q + ".action")
            length(r.get("signal"), "signal", q + ".signal")
            length(r.get("why"), "why", q + ".why")
            if kind == "class":
                need(_digits(r.get("why", "")) == 0, q + ".why", "'为什么'写原理，不能有数字（证据放 appendix.evidence）")
                need("who" not in r, q, "职业专题不写 who：整篇都是这个职业")
            else:
                need(bool(r.get("who")), q, "整队版要写 who")
        tip = seg.get("tip")
        if tip:
            need(tip.get("kind") in TIP_KINDS, p + ".tip.kind", f"{'/'.join(TIP_KINDS)}")
            length(tip.get("text"), "note", p + ".tip.text")
    for i, d in enumerate(data.get("debuffs") or []):
        p = f"debuffs[{i}]"
        need(bool(d.get("name")), p, "name 必填")
        tags(d.get("tags"), p + ".tags")
        length(d.get("handling"), "handling", p + ".handling")
    for i, ap in enumerate((data.get("appendix") or {}).get("evidence") or []):
        need(ap.get("strength") in STRENGTH, f"appendix.evidence[{i}].strength", "强/中/弱")
    # 正文（附录以外）不出现工具术语
    body = {k: v for k, v in data.items() if k not in ("appendix", "meta")}
    for path, text in _strings(body):
        for w in BANNED:
            if w in text:
                errs.append(f"{path}：正文里不要出现 '{w}'（证据和工具术语放 appendix）")
    return errs


def _strings(obj: Any, path: str = "") -> Iterable[Tuple[str, str]]:
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("id", "mechanic_id", "class", "kind", "type"):
                continue
            yield from _strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")


# ---------------------------------------------------------------- 图标
def _spell_ids(data: Dict[str, Any]) -> List[int]:
    ids = set()

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k in ("id", "mechanic_id"):
                if isinstance(o.get(k), int):
                    ids.add(o[k])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk({k: v for k, v in data.items() if k != "appendix"})
    return sorted(ids)


def _fetch_icon(name: str) -> Optional[str]:
    path = CACHE_DIR / "icons" / f"{name}.jpg"
    if not path.exists():
        url = f"https://wow.zamimg.com/images/wow/icons/large/{name}.jpg"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def load_icons(data: Dict[str, Any], lang: str = "zh") -> Dict[int, str]:
    """技能 ID -> 内嵌的图标（data URI），拿不到的不出现（用动作类型的 emoji 代替）。"""
    from .wowhead import spells
    out: Dict[int, str] = {}
    for gid, info in spells(_spell_ids(data), lang=lang).items():
        if info.get("icon"):
            uri = _fetch_icon(info["icon"])
            if uri:
                out[gid] = uri
    return out


# ---------------------------------------------------------------- HTML
def e(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _spell(obj: Dict[str, Any], icons: Dict[int, str], size: str = "") -> str:
    gid = obj.get("id")
    emoji, group = ACTIONS.get(obj.get("type"), ("•", "muted"))
    img = (f'<img class="ic{size}" src="{icons[gid]}" alt="">' if gid in icons
           else f'<span class="ic{size} ic-emoji">{emoji}</span>')
    name = f'<span class="sp-name">{e(obj.get("spell"))}</span>'
    inner = img + name
    if gid:
        inner = f'<a class="sp" href="https://www.wowhead.com/cn/spell={gid}" data-wowhead="spell={gid}&domain=cn">{inner}</a>'
    else:
        inner = f'<span class="sp">{inner}</span>'
    pill = f'<span class="pill a-{group}">{e(obj.get("type"))}</span>' if obj.get("type") else ""
    return inner + pill


def _mech(name: str, gid: Optional[int], icons: Dict[int, str]) -> str:
    img = f'<img class="ic" src="{icons[gid]}" alt="">' if gid in icons else ""
    label = f"{img}<span class=\"sp-name\">{e(name)}</span>"
    if gid:
        return f'<a class="sp mech" href="https://www.wowhead.com/cn/spell={gid}" data-wowhead="spell={gid}&domain=cn">{label}</a>'
    return f'<span class="sp mech">{label}</span>'


def _tags(lst: Optional[List[str]]) -> str:
    out = []
    for t in lst or []:
        emoji, group = TAGS.get(t, ("", "muted"))
        out.append(f'<span class="tag t-{group}">{emoji} {e(t)}</span>')
    return f'<span class="tags">{"".join(out)}</span>' if out else ""


def _dots(n: int) -> str:
    n = max(0, min(3, int(n or 0)))
    label = {3: "每场都用", 2: "多数场用", 1: "只见过一场"}.get(n, "")
    return f'<span class="dots" title="{label}">' + "".join(
        f'<i class="{"on" if i < n else ""}"></i>' for i in range(3)) + "</span>"


CSS = r"""
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--sub:#5b6474;--line:#e3e6eb;--soft:#f0f2f5;--accent:#3FC7EB;
--hero1:#141a26;--hero2:#232c3f;--heroink:#f3f5f8;
--warn:#b45309;--warn-bg:#fff4e5;--magic:#2563eb;--magic-bg:#e8f0ff;--poison:#15803d;--poison-bg:#e7f6ec;
--disease:#7c6a12;--disease-bg:#f6f1d9;--curse:#7e22ce;--curse-bg:#f3e8ff;--bleed:#b91c1c;--bleed-bg:#fde8e8;
--cc:#0e7490;--cc-bg:#e0f5f9;--muted:#4b5563;--muted-bg:#eceef1;
--a-reflect:#7c3aed;--a-immune:#b7791f;--a-defense:#2563eb;--a-cleanse:#0d9488;--a-external:#db2777;
--a-move:#16a34a;--a-heal:#059669;--a-control:#ea580c;--strong:#15803d;--mid:#b7791f;--weak:#9ca3af}
@media (prefers-color-scheme: dark){:root:not(.light){--bg:#0f131a;--card:#171c25;--ink:#e8ebf0;--sub:#9aa3b2;
--line:#283041;--soft:#1e2430;--warn-bg:#3a2a12;--magic-bg:#15254a;--poison-bg:#123321;--disease-bg:#33301a;
--curse-bg:#2c1a40;--bleed-bg:#3b1717;--cc-bg:#0f3038;--muted-bg:#262c37;--warn:#f59e0b;--magic:#7aa7ff;
--poison:#4ade80;--disease:#d4bf4a;--curse:#c084fc;--bleed:#f87171;--cc:#5fd3e6;--muted:#a3abb8}}
*{box-sizing:border-box}html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,"PingFang SC","Hiragino Sans GB",
"Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px 48px}
a{color:inherit;text-decoration:none}
.hero{background:linear-gradient(135deg,var(--hero1),var(--hero2));color:var(--heroink);padding:36px 0 30px;
border-bottom:4px solid var(--accent);margin-bottom:28px}
.hero h1{margin:0 0 6px;font-size:30px;letter-spacing:.5px}
.hero h1 .cls{color:var(--accent)}
.hero .wrap{padding-bottom:0}
.route table,.dbt table,.tbx table{table-layout:fixed}
.hero .summary{margin:14px 0 0;font-size:16px;color:#d5dbe5;max-width:760px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.chip{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:999px;padding:3px 12px;
font-size:13px;color:#e6eaf0}.chip b{color:#fff;font-weight:600;margin-right:6px}
h2{font-size:20px;margin:34px 0 14px;display:flex;align-items:center;gap:10px}
h2 .n{font-size:13px;color:var(--sub);font-weight:400}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px}
.hl{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.hl .card{padding:18px 18px 16px;position:relative;overflow:hidden;break-inside:avoid}
.hl .card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--accent)}
.hl .no{font-size:12px;color:var(--sub);letter-spacing:1px}
.hl .sig{font-size:14px;color:var(--sub);margin-top:8px}
.hl .act{font-size:19px;font-weight:650;margin:6px 0 8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.hl .note{font-size:14px;color:var(--ink)}
.hl .where{position:absolute;right:14px;top:14px;font-size:12px;color:var(--sub);background:var(--soft);
border-radius:999px;padding:1px 10px}
.ic{width:22px;height:22px;border-radius:5px;vertical-align:-5px;margin-right:6px;box-shadow:0 0 0 1px rgba(0,0,0,.35)}
.ic-lg{width:34px;height:34px;border-radius:7px;vertical-align:-10px;margin-right:8px;box-shadow:0 0 0 1px rgba(0,0,0,.35)}
.ic-emoji{display:inline-flex;align-items:center;justify-content:center;box-shadow:none;background:var(--soft);font-size:13px}
.ic-lg.ic-emoji{font-size:18px}
.sp{display:inline-flex;align-items:center;white-space:nowrap}.sp-name{font-weight:600}
.mech .sp-name{font-weight:600}
.pill{display:inline-block;font-size:11px;font-weight:600;border-radius:6px;padding:1px 7px;margin-left:8px;
color:#fff;vertical-align:1px}
.a-reflect{background:var(--a-reflect)}.a-immune{background:var(--a-immune)}.a-defense{background:var(--a-defense)}
.a-cleanse{background:var(--a-cleanse)}.a-external{background:var(--a-external)}.a-move{background:var(--a-move)}
.a-heal{background:var(--a-heal)}.a-control{background:var(--a-control)}.a-muted{background:var(--muted)}
.tags{display:inline-flex;flex-wrap:wrap;gap:4px;margin-left:6px;vertical-align:1px}
.tag{font-size:11.5px;border-radius:6px;padding:0 6px;white-space:nowrap}
.t-warn{color:var(--warn);background:var(--warn-bg)}.t-magic{color:var(--magic);background:var(--magic-bg)}
.t-poison{color:var(--poison);background:var(--poison-bg)}.t-disease{color:var(--disease);background:var(--disease-bg)}
.t-curse{color:var(--curse);background:var(--curse-bg)}.t-bleed{color:var(--bleed);background:var(--bleed-bg)}
.t-cc{color:var(--cc);background:var(--cc-bg)}.t-muted{color:var(--muted);background:var(--muted-bg)}
table{width:100%;border-collapse:collapse}
th{font-size:12px;font-weight:600;color:var(--sub);text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);
background:var(--soft)}
td{padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:0}
.tbl{overflow:hidden;break-inside:avoid}
.tbl th:first-child{border-top-left-radius:14px}.tbl th:last-child{border-top-right-radius:14px}
.muted{color:var(--sub)}.why{color:var(--sub)}
.dots{display:inline-flex;gap:4px}.dots i{width:9px;height:9px;border-radius:50%;background:var(--line);display:block}
.dots i.on{background:var(--accent)}
.spec{font-size:11.5px;color:var(--sub);background:var(--soft);border-radius:6px;padding:0 6px;margin-left:6px}
.route{position:relative;padding-left:34px}
.route:before{content:"";position:absolute;left:13px;top:8px;bottom:8px;width:2px;background:var(--line)}
.seg{position:relative;margin-bottom:18px;break-inside:avoid}
.seg .node{position:absolute;left:-34px;top:2px;width:28px;height:28px;border-radius:50%;display:flex;
align-items:center;justify-content:center;font-size:13px;font-weight:700;background:var(--card);
border:2px solid var(--line);color:var(--sub)}
.seg.boss .node{background:var(--accent);border-color:var(--accent);color:#0b1220}
.seg h3{margin:2px 0 10px;font-size:16.5px;display:flex;align-items:center;gap:8px}
.seg h3 .k{font-size:11.5px;font-weight:500;color:var(--sub);border:1px solid var(--line);border-radius:999px;padding:0 8px}
.callout{margin-top:8px;padding:9px 14px;border-radius:10px;font-size:14px;background:var(--soft);
border-left:3px solid var(--accent)}
.callout.warn{border-left-color:var(--warn);background:var(--warn-bg)}
.yes{color:var(--poison);font-weight:600}.no{color:var(--sub)}
.list{margin:0;padding:6px 0}.list li{list-style:none;padding:10px 16px;border-bottom:1px solid var(--line)}
.list li:last-child{border-bottom:0}.list b{margin-right:6px}
details{margin-top:12px}summary{cursor:pointer;font-weight:600;padding:12px 16px;list-style:none}
summary::-webkit-details-marker{display:none}summary:before{content:"▸ ";color:var(--sub)}
details[open] summary:before{content:"▾ "}
.app{padding:0 16px 14px;font-size:13.5px}.app h4{margin:16px 0 6px;font-size:13.5px}
.app td,.app th{padding:7px 10px;font-size:13px}
.app code{font-size:12px;background:var(--soft);padding:1px 5px;border-radius:4px}
.st{font-size:11.5px;font-weight:700;border-radius:6px;padding:0 7px;color:#fff}
.st-强{background:var(--strong)}.st-中{background:var(--mid)}.st-弱{background:var(--weak)}
.foot{margin-top:30px;font-size:12px;color:var(--sub);text-align:center}
@media (max-width:640px){.wrap{padding:0 14px 32px}.hero h1{font-size:24px}td,th{padding:9px 8px}
.route{padding-left:28px}.seg .node{left:-28px;width:24px;height:24px}.tbl{overflow-x:auto}}
html.export .hero{padding-top:28px}html.export details summary:before{content:""}
@media print{.hl{grid-template-columns:repeat(3,1fr)}.hl .card{padding:14px}body{background:#fff}.wrap{max-width:none}.hero{margin-bottom:18px}h2{break-after:avoid}}
"""


def render_html(data: Dict[str, Any], icons: Optional[Dict[int, str]] = None, tooltips: bool = True) -> str:
    icons = icons or {}
    kind = data.get("kind")
    accent = CLASS_COLORS.get(data.get("class") or "", "#e2b33c")
    title = e(data.get("title"))
    if kind == "class" and data.get("class_name") and data["class_name"] in data.get("title", ""):
        title = title.replace(e(data["class_name"]), f'<span class="cls">{e(data["class_name"])}</span>', 1)
    chips = "".join(f'<span class="chip"><b>{e(m.get("label"))}</b>{e(m.get("value"))}</span>'
                    for m in data.get("meta") or [])
    out = [f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(data.get("title"))}</title>'
           f'<style>{CSS}:root{{--accent:{accent}}}</style>']
    if tooltips:
        out.append('<script>const whTooltips={colorLinks:false,iconizeLinks:false,renameLinks:false};</script>'
                   '<script src="https://wow.zamimg.com/js/tooltips.js" async></script>')
    out.append('</head><body>')
    out.append(f'<header class="hero"><div class="wrap"><h1>{title}</h1><div class="chips">{chips}</div>'
               + (f'<p class="summary">{e(data.get("summary"))}</p>' if data.get("summary") else "")
               + '</div></header><main class="wrap">')

    # ⭐
    hl = data.get("highlights") or []
    if hl:
        cards = []
        for i, h in enumerate(hl, 1):
            who = f'{e(h.get("who"))}：' if h.get("who") else ""
            cards.append(
                f'<div class="card"><div class="no">第 {i} 招</div>'
                + (f'<span class="where">{e(h.get("where"))}</span>' if h.get("where") else "")
                + f'<div class="sig">{who}看到 <b>{e(h.get("signal"))}</b></div>'
                f'<div class="act">→ {_spell(h["action"], icons, "-lg")}</div>'
                f'<div class="note">{e(h.get("note"))}</div></div>')
        out.append(f'<h2>⭐ {"必会的几招" if kind == "class" else "先学这几条"}</h2><div class="hl">{"".join(cards)}</div>')

    # 🧰
    tb = data.get("toolbox") or []
    if tb:
        rows = "".join(
            f'<tr><td>{_spell(t, icons)}' + (f'<span class="spec">{e(t.get("spec"))}</span>' if t.get("spec") else "")
            + f'</td><td>{e(t.get("handles"))}</td><td class="muted">{e(t.get("timing"))}</td><td>{_dots(t.get("usage"))}</td></tr>'
            for t in tb)
        label = e(data.get("class_name") or "")
        out.append(f'<h2>🧰 {label}工具箱 <span class="n">带哪些技能、留给什么</span></h2>'
                   f'<div class="card tbl tbx"><table><colgroup><col style="width:31%"><col style="width:36%"><col style="width:21%"><col style="width:12%"></colgroup><thead><tr><th>技能</th><th>用来处理</th><th>时机</th><th>常用度</th>'
                   f'</tr></thead><tbody>{rows}</tbody></table></div>')

    # 🗺️
    route = data.get("route") or []
    if route:
        segs = []
        boss_no = 0
        team = kind == "team"
        for seg in route:
            boss = seg.get("kind") == "boss"
            boss_no += boss
            node = str(seg.get("number") or boss_no) if boss else "·"
            widths = ([30, 17, 11, 22, 20] if team else [31, 19, 27, 23])
            cols = "<colgroup>" + "".join(f'<col style="width:{w}%">' for w in widths) + "</colgroup>"
            head = "".join(["<th>机制</th><th>信号</th>", "<th>谁</th>" if team else "", "<th>按什么</th><th>为什么</th>"])
            body = []
            for r in seg.get("rows") or []:
                body.append(
                    f'<tr><td>{_mech(r.get("mechanic"), r.get("mechanic_id"), icons)}{_tags(r.get("tags"))}</td>'
                    f'<td>{e(r.get("signal"))}</td>' + (f'<td><b>{e(r.get("who"))}</b></td>' if team else "")
                    + f'<td>{_spell(r["action"], icons)}</td><td class="why">{e(r.get("why"))}</td></tr>')
            tip = seg.get("tip")
            tip_html = ""
            if tip:
                emoji, _label = TIP_KINDS.get(tip.get("kind"), ("💡", ""))
                tip_html = f'<div class="callout {"warn" if tip.get("kind") == "warn" else ""}">{emoji} {e(tip.get("text"))}</div>'
            segs.append(
                f'<section class="seg {"boss" if boss else "trash"}"><div class="node">{e(node)}</div>'
                f'<h3>{"👹" if boss else "👾"} {e(seg.get("name"))}<span class="k">{"首领" if boss else "小怪段"}</span></h3>'
                f'<div class="card tbl"><table>{cols}<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
                f'{tip_html}</section>')
        out.append(f'<h2>🗺️ 按副本流程 <span class="n">从开场到尾王</span></h2><div class="route">{"".join(segs)}</div>')

    # 🩹
    db = data.get("debuffs") or []
    if db:
        rows = "".join(
            f'<tr><td>{_mech(d.get("name"), d.get("id"), icons)}{_tags(d.get("tags"))}</td>'
            + (f'<td><span class="yes">✅ {e(d.get("self"))}</span></td>' if d.get("self") else '<td class="no">❌ 不能</td>')
            + f'<td class="muted">{e(d.get("handling"))}</td></tr>' for d in db)
        out.append(f'<h2>🩹 常中的减益</h2><div class="card tbl dbt"><table><colgroup><col style="width:34%"><col style="width:33%"><col style="width:33%"></colgroup><thead><tr><th>减益</th><th>自己能解吗</th>'
                   f'<th>一般怎么处理</th></tr></thead><tbody>{rows}</tbody></table></div>')

    for key, icon, label in (("dont", "⚠️", "别这样做"), ("unclear", "❓", "还没看清的")):
        items = data.get(key) or []
        if items:
            lis = []
            for it in items:
                if isinstance(it, dict):
                    lis.append(f'<li><b>{e(it.get("title"))}</b>{e(it.get("text"))}</li>')
                else:
                    lis.append(f"<li>{e(it)}</li>")
            out.append(f'<h2>{icon} {label}</h2><div class="card"><ul class="list">{"".join(lis)}</ul></div>')

    # 📎
    ap = data.get("appendix") or {}
    if ap:
        parts = []
        if ap.get("runs"):
            rows = "".join(f'<tr><td><code>{e(r.get("code"))}#{e(r.get("fight"))}</code></td><td>{e(r.get("level"))}</td>'
                           f'<td>{e(r.get("result"))}</td><td>{e(r.get("players"))}</td><td>{e(r.get("team"))}</td></tr>'
                           for r in ap["runs"])
            parts.append('<h4>对照记录</h4><table><thead><tr><th>记录</th><th>层数</th><th>结果</th><th>玩家</th><th>队伍</th>'
                         f'</tr></thead><tbody>{rows}</tbody></table>')
            if ap.get("runs_note"):
                parts.append(f'<p class="muted">{e(ap["runs_note"])}</p>')
        if ap.get("evidence"):
            rows = "".join(f'<tr><td>{e(x.get("mechanic"))}</td><td>{e(x.get("response"))}</td><td>{e(x.get("evidence"))}</td>'
                           f'<td><span class="st st-{e(x.get("strength"))}">{e(x.get("strength"))}</span></td></tr>'
                           for x in ap["evidence"])
            parts.append('<h4>证据明细</h4><table><thead><tr><th>机制</th><th>应对</th><th>证据</th><th>强度</th></tr></thead>'
                         f'<tbody>{rows}</tbody></table>')
        if ap.get("verify"):
            parts.append("<h4>怎么核实</h4><ul>" + "".join(f"<li><code>{e(v)}</code></li>" for v in ap["verify"]) + "</ul>")
        if ap.get("notes"):
            parts.append(f'<h4>数据口径</h4><p class="muted">{e(ap["notes"])}</p>')
        out.append(f'<details class="card" id="appendix"><summary>📎 附录：对照记录、证据明细、核实方法</summary>'
                   f'<div class="app">{"".join(parts)}</div></details>')
    out.append(f'<div class="foot">wcl-raider · mplus-tactics · {e(data.get("date") or "")}</div></main></body></html>')
    return "".join(out)


# ---------------------------------------------------------------- Markdown（对话里贴、存档用）
def render_md(data: Dict[str, Any]) -> str:
    kind = data.get("kind")
    lines = [f"# {data.get('title')}", ""]
    meta = " · ".join(f"{m.get('label')} {m.get('value')}" for m in data.get("meta") or [])
    if meta:
        lines.append(f"> {meta}")
    if data.get("summary"):
        lines.append(f"> {data['summary']}")
    lines += ["", "## ⭐ " + ("必会的几招" if kind == "class" else "先学这几条"), ""]
    for i, h in enumerate(data.get("highlights") or [], 1):
        who = f"{h['who']}：" if h.get("who") else ""
        lines.append(f"{i}. **{who}{h.get('signal')} → {h['action'].get('spell')}**　{h.get('note', '')}")
    if data.get("toolbox"):
        lines += ["", f"## 🧰 {data.get('class_name', '')}工具箱", "", "| 技能 | 用来处理 | 时机 | 常用度 |", "|---|---|---|---|"]
        for t in data["toolbox"]:
            dots = "●" * int(t.get("usage") or 0) + "○" * (3 - int(t.get("usage") or 0))
            spec = f"（{t['spec']}）" if t.get("spec") else ""
            lines.append(f"| {ACTIONS.get(t.get('type'), ('', ''))[0]} {t.get('spell')}{spec} | {t.get('handles', '')} | "
                         f"{t.get('timing', '')} | {dots} |")
    lines += ["", "## 🗺️ 按副本流程"]
    for seg in data.get("route") or []:
        lines += ["", f"### {'👹' if seg.get('kind') == 'boss' else '👾'} {seg.get('name')}", ""]
        team = kind == "team"
        lines.append("| 机制 | 信号 | " + ("谁 | " if team else "") + "按什么 | 为什么 |")
        lines.append("|---|---|" + ("---|" if team else "") + "---|---|")
        for r in seg.get("rows") or []:
            tg = " ".join(f"`{TAGS.get(t, ('', ''))[0]}{t}`" for t in r.get("tags") or [])
            lines.append(f"| {r.get('mechanic')} {tg} | {r.get('signal', '')} | " + (f"{r.get('who', '')} | " if team else "")
                         + f"{ACTIONS.get(r['action'].get('type'), ('', ''))[0]} {r['action'].get('spell')} | {r.get('why', '')} |")
        if seg.get("tip"):
            lines += ["", f"> {TIP_KINDS.get(seg['tip'].get('kind'), ('💡', ''))[0]} {seg['tip'].get('text')}"]
    if data.get("debuffs"):
        lines += ["", "## 🩹 常中的减益", "", "| 减益 | 自己能解吗 | 一般怎么处理 |", "|---|---|---|"]
        for d in data["debuffs"]:
            tg = " ".join(f"`{TAGS.get(t, ('', ''))[0]}{t}`" for t in d.get("tags") or [])
            lines.append(f"| {d.get('name')} {tg} | {'✅ ' + d['self'] if d.get('self') else '❌'} | {d.get('handling', '')} |")
    for key, label in (("dont", "## ⚠️ 别这样做"), ("unclear", "## ❓ 还没看清的")):
        if data.get(key):
            lines += ["", label]
            for it in data[key]:
                lines.append(f"- **{it.get('title')}**：{it.get('text')}" if isinstance(it, dict) else f"- {it}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 命令
def cmd_render(path: str, out: Optional[str] = None, pdf: Optional[str] = None, png: Optional[str] = None,
               md: Optional[str] = None, force: bool = False, lang: str = "zh") -> str:
    src = Path(path)
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WCLError(f"读不了报告 JSON：{exc}") from None
    errs = validate(data)
    if errs and not force:
        raise WCLError("报告没通过检查（改 JSON 后重跑；确实需要时加 --force）：\n- " + "\n- ".join(errs))
    icons = load_icons(data, lang)
    html_path = Path(out) if out else src.with_suffix(".html")
    html_path.write_text(render_html(data, icons), encoding="utf-8")
    lines = [f"HTML：{html_path.resolve()}（图标 {len(icons)} 个已内嵌；联网时鼠标悬停技能名会显示 Wowhead 说明）"]
    if errs:
        lines.append("警告（--force 忽略了）：\n- " + "\n- ".join(errs))
    if md:
        Path(md).write_text(render_md(data), encoding="utf-8")
        lines.append(f"Markdown：{Path(md).resolve()}")
    if pdf or png:
        from .export import export
        for kind, target in export(html_path, pdf=pdf, png=png):
            lines.append(f"{kind}：{Path(target).resolve()}")
    return "\n".join(lines)
