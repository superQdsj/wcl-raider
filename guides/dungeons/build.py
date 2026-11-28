#!/usr/bin/env python3
"""Build one multi-spec dungeon page from data.

    python3 guides/dungeons/build.py saitalisi          # check + build
    python3 guides/dungeons/build.py saitalisi --check  # check only

Inputs (guides/dungeons/<slug>/):
  dungeon.json     shared layer: bosses, abilities, numbers, each mechanic with its source
  specs/*.json     one file per DPS spec: cooldown plan, what to press, trick, don'ts, log links
  evidence/        sources the `src` fields point at (wowhead.json, diag-bN.md, <spec>-guide.md)
Output: guides/dungeons/<slug>/<slug>.html (spec blocks are all in the page; the picker shows/hides them).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUIDES = HERE.parent
ROOT = GUIDES.parent
ICONS = GUIDES / "icons"
sys.path.insert(0, str(GUIDES / "tools"))
from icons import inject_icons  # noqa: E402

# Specs the site knows about; shown greyed out in the picker until a specs/<id>.json exists.
SPEC_CATALOG = [
    ("ret", "惩戒骑", "#f48cba", "spell_holy_auraoflight"),
    ("arms", "武器战", "#c69b6d", "ability_warrior_savageblow"),
    ("rogue", "敏锐贼", "#fff468", "ability_stealth"),
    ("ele", "元素萨", "#0070dd", "spell_nature_lightning"),
    ("dh", "噬灭 DH", "#a330c9", "classicon_demonhunter_void"),
    ("bm", "兽王猎", "#aad372", "ability_hunter_bestialdiscipline"),
]
NONE_COLOR = "#62cfc3"
DDIR = HERE

# ---------------------------------------------------------------- checks
BANNED = [
    (r"\d+\s*/\s*\d+\s*场", "统计句式「N/N 场」"),
    (r"场均", "统计词「场均」"),
    (r"Δt", "统计符号 Δt"),
    (r"%\s*HP|\bHP\b", "用 HP 百分比写伤害"),
    (r"中位", "统计词「中位」"),
    (r"\d(\.\d+)?\s*[MK]\b", "用 M/K 写数字，改成「万」"),
    (r"[一二三四五六七八九两几]成血", "「几成血」，写绝对值"),
]
LIMITS = {"talent": 50, "what": 48, "cap": 30, "note": 50, "all": 70, "plan": 24, "do": 44, "step": 50, "caption": 70, "summary": 100, "dont": 60}


class Checker:
    def __init__(self, ddir: Path):
        self.ddir = ddir
        self.errors: list[str] = []
        ev = ddir / "evidence"
        wh = ev / "wowhead.json"
        self.wowhead = json.loads(wh.read_text(encoding="utf-8")) if wh.is_file() else {}
        self.ev = ev
        self._lines: dict[str, list[str]] = {}

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def src(self, where: str, srcs) -> None:
        if not srcs:
            self.err(where, "缺少 src（机制和建议都要写出处）")
            return
        for s in srcs:
            if s == "user":
                continue
            if s.startswith("talents-"):
                if not (self.ev / f"{s}.json").is_file():
                    self.err(where, f"{s} 找不到 evidence/{s}.json")
                continue
            if s == "trash-route" or re.fullmatch(r"diag(-[a-z]+)?-trash", s):
                if not (self.ev / f"{s}.md").is_file():
                    self.err(where, f"{s} 找不到 evidence/{s}.md")
                continue
            if s.startswith("mdt:"):
                if f'["id"] = {s[4:]},' not in self._mdt():
                    self.err(where, f"{s} 不在 evidence/mdt.lua")
                continue
            if s.startswith("wowhead:"):
                if s[8:] not in self.wowhead:
                    self.err(where, f"{s} 不在 evidence/wowhead.json")
            elif re.fullmatch(r"diag(-[a-z]+)?-b\d", s):
                if not (self.ev / f"{s}.md").is_file():
                    self.err(where, f"{s} 找不到 evidence/{s}.md")
            elif m := re.fullmatch(r"([a-z]+-guide):L(\d+)", s):
                lines = self._lines.setdefault(m[1], self._read(m[1]))
                n = int(m[2])
                if not (1 <= n <= len(lines)) or not lines[n - 1].strip():
                    self.err(where, f"{s} 指向空行或越界")
            else:
                self.err(where, f"看不懂的 src：{s}")

    def _mdt(self) -> str:
        if not hasattr(self, "_mdt_text"):
            p = self.ev / "mdt.lua"
            self._mdt_text = p.read_text(encoding="utf-8") if p.is_file() else ""
        return self._mdt_text

    def _read(self, name: str) -> list[str]:
        p = self.ev / f"{name}.md"
        return p.read_text(encoding="utf-8").splitlines() if p.is_file() else []

    def text(self, where: str, s: str, kind: str) -> None:
        if not s:
            return
        plain = s.replace("**", "")
        lim = LIMITS[kind]
        if len(plain) > lim:
            self.err(where, f"太长 {len(plain)}/{lim} 字：{plain[:30]}…")
        for pat, why in BANNED:
            if re.search(pat, plain):
                self.err(where, f"{why}：{plain[:40]}")


def check(d: dict, specs: list[dict], ck: Checker) -> None:
    for b in d["bosses"]:
        bw = b["id"]
        ck.src(f"{bw}.summary", b.get("src"))
        ck.text(f"{bw}.summary", b.get("summary", "") + b.get("summary_em", ""), "summary")
        ids = {a["id"] for a in b["abilities"]}
        loop = b.get("loop")
        if loop:
            if loop.get("sub_src"):
                ck.src(f"{bw}.loop.sub", loop["sub_src"])
            for seg in loop["segments"]:
                for aid in seg.get("abilities", []):
                    if aid not in ids:
                        ck.err(f"{bw}.loop", f"段落里的技能 {aid} 不在 abilities")
            if loop.get("layout") in ("aligned", "grouped"):
                listed = [a for s in loop["segments"] for a in s.get("abilities", [])]
                if sorted(listed) != sorted(ids):
                    ck.err(f"{bw}.loop", "aligned/grouped 时每个技能必须恰好出现在一个段落里")
        for a in b["abilities"]:
            w = f"{bw}.{a['name']}"
            ck.src(w, a.get("src"))
            ck.text(w, a.get("what", ""), "what")
            if a.get("num"):
                ck.src(w + ".num", [a.get("num_src")] if a.get("num_src") else None)
                ck.text(w + ".cap", a.get("cap", ""), "cap")
            for k in ("note", "all"):
                if a.get(k):
                    ck.src(f"{w}.{k}", a[k].get("src"))
                    ck.text(f"{w}.{k}", a[k]["text"], k)
    trash = {t["id"]: t for t in d.get("trash", [])}
    if d.get("trash_legend"):
        ck.src("trash_legend", d["trash_legend"].get("src"))
    for tr in trash.values():
        tw = tr["id"]
        ck.src(f"{tw}.summary", tr.get("src"))
        ck.text(f"{tw}.summary", tr.get("summary", "") + tr.get("summary_em", ""), "summary")
        if tr.get("quiet"):
            ck.src(f"{tw}.quiet", tr["quiet"].get("src"))
        if sn := tr.get("seen"):
            ck.src(f"{tw}.seen", sn.get("src"))
            if sn["from"] not in trash:
                ck.err(f"{tw}.seen", f"from 指向不存在的小怪段 {sn['from']}")
        for m in tr["mobs"]:
            ck.src(f"{tw}.{m['name']}", m.get("src"))
            for a in m["skills"]:
                w = f"{tw}.{m['name']}.{a['name']}"
                ck.src(w, a.get("src"))
                ck.text(w, a.get("what", ""), "what")
                if a.get("type") not in (None, "kick", "bar", "unstoppable"):
                    ck.err(w, f"type 只能是 kick / bar / unstoppable：{a.get('type')}")
                if a.get("num"):
                    ck.src(w + ".num", [a.get("num_src")] if a.get("num_src") else None)
                    ck.text(w + ".cap", a.get("cap", ""), "cap")
                for k in ("note", "all"):
                    if a.get(k):
                        ck.src(f"{w}.{k}", a[k].get("src"))
                        ck.text(f"{w}.{k}", a[k]["text"], k)
    route = d.get("route") or [b["id"] for b in d["bosses"]]
    known = {b["id"] for b in d["bosses"]} | set(trash)
    for r in route:
        if r not in known:
            ck.err("route", f"{r} 既不是首领也不是小怪段")
    bosses = {b["id"]: b for b in d["bosses"]}
    for sp in specs:
        if tl := sp.get("talents"):
            w0 = f"{sp['spec']}.talents"
            ck.src(w0, tl.get("src"))
            if not (ck.ddir / tl["string_from"]).is_file():
                ck.err(w0, f"找不到天赋串文件 {tl['string_from']}")
            for k in tl.get("keys", []):
                ck.src(f"{w0}.{k['name']}", k.get("src"))
                ck.text(f"{w0}.{k['name']}", k["text"], "talent")
                for x in k.get("where", []):
                    if x not in known:
                        ck.err(f"{w0}.{k['name']}", f"where 指向不存在的段落 {x}")
    for sp in specs:
        for tid, st in sp.get("trash", {}).items():
            w0 = f"{sp['spec']}.{tid}"
            if tid not in trash:
                ck.err(w0, "副本里没有这个小怪段")
                continue
            ids = {str(a["id"]) for m in trash[tid]["mobs"] for a in m["skills"]}
            for i, p in enumerate(st.get("plan", [])):
                ck.src(f"{w0}.plan{i+1}", p.get("src"))
                ck.text(f"{w0}.plan{i+1}", p["text"], "plan")
            for aid, items in st.get("do", {}).items():
                if aid not in ids:
                    ck.err(f"{w0}.do", f"技能 {aid} 不在这一段的小怪技能里")
                for it in items:
                    ck.src(f"{w0}.do.{aid}", it.get("src"))
                    ck.text(f"{w0}.do.{aid}", it["text"], "do")
    for sp in specs:
        sid = sp["spec"]
        ck.src(f"{sid}.kit", sp.get("kit_src"))
        for bid, sb in sp.get("bosses", {}).items():
            w0 = f"{sid}.{bid}"
            if bid not in bosses:
                ck.err(w0, "副本里没有这个首领")
                continue
            ids = {str(a["id"]) for a in bosses[bid]["abilities"]}
            for i, p in enumerate(sb.get("plan", [])):
                ck.src(f"{w0}.plan{i+1}", p.get("src"))
                ck.text(f"{w0}.plan{i+1}", p["text"], "plan")
            for aid, items in sb.get("do", {}).items():
                if aid not in ids:
                    ck.err(f"{w0}.do", f"技能 {aid} 不在这个首领的 abilities")
                for it in items:
                    ck.src(f"{w0}.do.{aid}", it.get("src"))
                    ck.text(f"{w0}.do.{aid}", it["text"], "do")
            if tr := sb.get("trick"):
                ck.src(f"{w0}.trick", tr.get("src"))
                for st in tr["steps"]:
                    ck.text(f"{w0}.trick", st["text"], "step")
                ck.text(f"{w0}.trick.caption", tr.get("chart", {}).get("caption", ""), "caption")
            for dn in sb.get("donts", []):
                ck.src(f"{w0}.dont", dn.get("src"))
                ck.text(f"{w0}.dont", dn["text"], "dont")


# ---------------------------------------------------------------- render helpers
def t(s: str) -> str:
    """Escape, then allow **bold**."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(s, quote=False))


def ic(spell: int, cls: str = "ic", dim: bool = False) -> str:
    c = cls + (" dim" if dim else "")
    return f'<img class="{c}" src="{{{{I:{spell}}}}}" alt="" data-tip="{spell}">'


SKULL = ('<svg class="skull" viewBox="0 0 24 24" role="img" aria-label="减员点"><path fill="currentColor" '
         'd="M12 2C6.9 2 3 5.7 3 10.4c0 2.6 1.2 4.6 3 5.9V19c0 .8.7 1.5 1.5 1.5H9v-2h1.5v2h3v-2H15v2h1.5c.8 0 1.5-.7 '
         '1.5-1.5v-2.7c1.8-1.3 3-3.3 3-5.9C21 5.7 17.1 2 12 2Zm-3.5 12a2.3 2.3 0 1 1 0-4.6 2.3 2.3 0 0 1 0 4.6Zm7 0a2.3 '
         '2.3 0 1 1 0-4.6 2.3 2.3 0 0 1 0 4.6Zm-3.5 3.2-1.3-2.4h2.6L12 17.2Z"/></svg>')


SCHOOLS = {"物理": "physical", "自然": "nature", "暗影": "shadow", "火焰": "fire", "冰霜": "frost", "奥术": "arcane", "神圣": "holy"}
EN_SCHOOLS = {"Physical": "物理", "Nature": "自然", "Shadow": "暗影", "Fire": "火焰", "Frost": "冰霜", "Arcane": "奥术", "Holy": "神圣"}
WOWHEAD: dict = {}


def schools(spell: int) -> list[str]:
    """Damage schools straight from the Wowhead tooltip text; nothing inferred."""
    w = WOWHEAD.get(str(spell)) or {}
    text = (w.get("desc") or "") + " " + (w.get("aura") or "")
    found = re.findall(r"点(物理|自然|暗影|火焰|冰霜|奥术|神圣)伤害", text)
    found += [EN_SCHOOLS[x] for x in re.findall(r"\d+ (Physical|Nature|Shadow|Fire|Frost|Arcane|Holy) damage", text)]
    return list(dict.fromkeys(found))


MDT_FLAGS: dict = {}
DEBUFFS = {"流血": "bleed", "中毒": "poison", "疾病": "disease", "诅咒": "curse", "魔法": "magic"}
MDT_DEBUFF = {"poison": "中毒", "disease": "疾病", "curse": "诅咒", "magic": "魔法"}


def load_mdt_flags(text: str) -> dict:
    """spell id -> set of MDT flags (interruptible, poison, magic, curse, disease)."""
    out = {}
    for m in re.finditer(r"\[(\d{4,8})\] = \{([^{}]*)\}", text):
        flags = set(re.findall(r'\["(\w+)"\] = true', m.group(2)))
        if flags:
            out[int(m.group(1))] = flags
    return out


def debuffs(spell: int) -> list[str]:
    """Debuff kinds from official text only: Wowhead dispel type, MDT dispel flags, and 流血 in the tooltip."""
    w = WOWHEAD.get(str(spell)) or {}
    found = []
    text = (w.get("desc") or "") + " " + (w.get("aura") or "")
    if "流血" in text:
        found.append("流血")
    if w.get("dispel") in DEBUFFS:
        found.append(w["dispel"])
    found += [MDT_DEBUFF[f] for f in MDT_FLAGS.get(spell, ()) if f in MDT_DEBUFF]
    return list(dict.fromkeys(found))


def school_tags(spell: int) -> str:
    deb = "".join(f'<span class="dbf d-{DEBUFFS[x]}">{x}</span>' for x in debuffs(spell))
    return deb + "".join(f'<span class="sch s-{SCHOOLS[x]}">{x}</span>' for x in schools(spell))


def npc(display_id: int) -> str:
    return f"../../icons/npc-{display_id}.png"


def zoom_face(display_id: int, name: str) -> str:
    """Small round portrait; hovering shows the full-body model render."""
    n = html.escape(name)
    return (f'<button type="button" class="face zoom" data-zoom="{n}" aria-label="查看{n}大图">'
            f'<img src="{npc(display_id)}" alt=""></button>')


def ensure_npc(display_id: int) -> None:
    p = ICONS / f"npc-{display_id}.png"
    if p.is_file():
        return
    url = f"https://wow.zamimg.com/modelviewer/live/webthumbs/npc/{display_id % 256}/{display_id}.png"
    with urllib.request.urlopen(url, timeout=30) as r:
        p.write_bytes(r.read())
    print(f"  fetched portrait {display_id}")


def ensure_copy(src: Path, name: str) -> str:
    dst = ICONS / name
    if not dst.is_file():
        shutil.copyfile(src, dst)
    return f"../../icons/{name}"


def ticks(items, total: float) -> str:
    out = []
    for i, (pos, label) in enumerate(items):
        cls = "l" if i == 0 else ("r" if i == len(items) - 1 and pos >= total else "")
        out.append(f'<span class="{cls}" style="left:{pos / total * 100:.2f}%">{html.escape(label)}</span>')
    return f'<div class="ticks" aria-hidden="true">{"".join(out)}</div>'


def render_bar(loop: dict) -> str:
    segs = []
    for s in loop["segments"]:
        tone = s.get("tone", "mech")
        if sp := s.get("split"):
            a = sp["at"] * 100
            inner = (f'<span class="t-{tone}" style="flex:0 0 {a:.1f}%">{html.escape(s["label"])}</span>'
                     f'<span class="t-{sp.get("tone", "cast")}" style="flex:1">{html.escape(sp["label"])}</span>')
        elif "fill" in s:
            f = s["fill"] * 100
            inner = (f'<span class="t-{tone}" style="flex:0 0 {f:.1f}%;overflow:visible">{html.escape(s["label"])}</span>'
                     f'<span class="t-calm" style="flex:1"></span>')
        else:
            inner = f'<span class="t-{tone}" style="flex:1">{html.escape(s["label"])}</span>'
        segs.append(f'<div class="seg" style="flex:{s["w"]} 1 0">{inner}</div>')
    total = sum(s["w"] for s in loop["segments"])
    return f'<div class="bar" aria-hidden="true">{"".join(segs)}</div>' + ticks(loop.get("ticks", []), total)


def render_mine(sid: str, items: list[dict]) -> str:
    rows = []
    for it in items:
        kind = it.get("kind", "do")
        icon = ic(it["icon"], "ic sm", dim=(kind == "skip")) if it.get("icon") else '<span class="dot"></span>'
        label = f'<b>{html.escape(it["label"])}</b>：' if it.get("label") else ""
        rows.append(f'<div class="do {kind}">{icon}<span>{label}{t(it["text"])}</span></div>')
    return f'<div class="mine" data-for="{sid}">{"".join(rows)}</div>'


def mob_refs(d: dict, here: str) -> dict:
    """Trash skill name → (spell id, card anchor), so text can point back at the mob that casts it.
    Names shared by several mobs resolve to the current trash section first."""
    refs = {}
    for tr in sorted(d.get("trash", []), key=lambda x: x["id"] != here):
        for i, m in enumerate(tr["mobs"]):
            for a in m["skills"]:
                refs.setdefault(a["name"], (a["id"], f'{tr["id"]}-m{i}'))
    return refs


def xref(s: str, refs: dict, skip: str = "") -> str:
    """t(), plus every mob-skill name becomes a small icon+name link to its mob card (tooltip names the mob)."""
    out = t(s)
    names = sorted((n for n in refs if n != skip), key=len, reverse=True)
    if not names:
        return out

    def link(mt):
        sid, anchor = refs[mt.group(0)]
        return (f'<a class="xref" href="#{anchor}" data-tip="{sid}"><img src="{{{{I:{sid}}}}}" alt="">'
                f'{mt.group(0)}</a>')
    return re.sub("|".join(map(re.escape, names)), link, out)


def render_mine_table(sid: str, items: list[dict], refs: dict | None = None, skip: str = "") -> str:
    tx = (lambda s: xref(s, refs, skip)) if refs else t
    rows = []
    for it in items:
        kind = it.get("kind", "do")
        icon = ic(it["icon"], "ic sm", dim=(kind == "skip")) if it.get("icon") else ""
        if it.get("label"):
            rows.append(f'<div class="mt-r {kind}"><span class="mt-k">{icon}<b>{html.escape(it["label"])}</b></span>'
                        f'<span class="mt-v">{tx(it["text"])}</span></div>')
        else:
            rows.append(f'<div class="mt-r {kind} wide"><span class="mt-v">{tx(it["text"])}</span></div>')
    return f'<div class="mtab" data-for="{sid}">{"".join(rows)}</div>'


def render_step(a: dict, specs: list[dict], bid: str, first: bool) -> str:
    skull = " " + SKULL if a.get("lethal") else ""
    parts = [f'<div class="name">{ic(a["id"])}<div><b>{html.escape(a["name"])}{skull}</b>{school_tags(a["id"])}'
             f'<small>{t(a["what"])}</small></div></div>']
    if a.get("num"):
        parts.append(f'<div class="num">{html.escape(a["num"])}<i>万</i></div><div class="cap">{t(a.get("cap", ""))}</div>')
    if n := a.get("note"):
        nic = ic(n["icon"], "ic xs") if n.get("icon") else ""
        parts.append(f'<div class="note">{nic}<span>{t(n["text"])}</span></div>')
    if al := a.get("all"):
        parts.append(f'<div class="all">{t(al["text"])}</div>')
    for sp in specs:
        items = sp.get("bosses", {}).get(bid, {}).get("do", {}).get(str(a["id"]))
        if items:
            parts.append(render_mine(sp["spec"], items))
    cls = "step" + (" hot" if a.get("lethal") else "") + (" first" if first else "")
    return f'<div class="{cls}">{"".join(parts)}</div>'


def steps_grid(abilities: list[dict], specs, bid: str, cols: str | None = None) -> str:
    n = len(abilities)
    ncol = 2 if n == 4 else min(n, 3)
    style = f' style="grid-template-columns:{cols}"' if cols else f' style="--n:{ncol}"'
    cells = [render_step(a, specs, bid, i % ncol == 0 if not cols else i == 0) for i, a in enumerate(abilities)]
    return f'<div class="steps"{style}>{"".join(cells)}</div>'


def render_fight(b: dict, specs) -> str:
    by_id = {a["id"]: a for a in b["abilities"]}
    loop = b.get("loop")
    out = ['<div class="loop">']
    if loop:
        out.append(f'<h3 class="sec-h">{html.escape(loop["title"])}</h3>')
        if loop.get("sub"):
            out.append(f'<p class="sub">{t(loop["sub"])}</p>')
        out.append(render_bar(loop))
        layout = loop.get("layout")
        if layout == "aligned":
            cols = " ".join(f'{s["w"]}fr' for s in loop["segments"])
            abil = [by_id[x] for s in loop["segments"] for x in s["abilities"]]
            out.append(steps_grid(abil, specs, b["id"], cols))
        elif layout == "grouped":
            for s in loop["segments"]:
                tone = s.get("tone", "mech")
                out.append(f'<div class="group-h"><i class="t-{tone}"></i>{html.escape(s["label"])}</div>')
                out.append(steps_grid([by_id[x] for x in s["abilities"]], specs, b["id"]))
        else:
            out.append(steps_grid(b["abilities"], specs, b["id"]))
    else:
        out.append('<h3 class="sec-h">要处理的东西</h3><p class="sub">上面是机制，虚线下面是你要按的。</p>')
        out.append(steps_grid(b["abilities"], specs, b["id"]))
    out.append("</div>")
    return "".join(out)


def render_plan(sid: str, plan: list[dict]) -> str:
    slots = []
    for p in plan:
        use = p["use"]
        big = "".join(ic(u, "big") for u in use)
        if len(use) > 1:
            big = f'<span class="duo">{big}</span>'
        tgt = ""
        if on := p.get("on"):
            if "spell" in on:
                tgt = f'<i class="to"></i>{ic(on["spell"], "tgt")}'
            elif "npc" in on:
                tgt = f'<i class="to"></i><span class="tgt face"><img src="{npc(on["npc"])}" alt=""></span>'
        slots.append(f'<div class="slot"><div class="icons">{big}{tgt}</div>'
                     f'<div><b>{html.escape(p["name"])}</b><span class="t">{t(p["text"])}</span></div></div>')
    return f'<div class="plan" data-for="{sid}" aria-label="这场大招怎么分">{"".join(slots)}</div>'


def render_chart(ch: dict) -> str:
    sc = ch["scale"]
    rows = []
    for r in ch["rows"]:
        inner = []
        for s in r.get("segs", []):
            left, width = s["from"] / sc * 100, (s["to"] - s["from"]) / sc * 100
            inner.append(f'<div class="bseg g-{s["tone"]}" style="left:{left:.2f}%;width:{width:.2f}%">{html.escape(s.get("text", ""))}</div>')
        for m in r.get("marks", []):
            inner.append(f'<div class="mark" style="left:{m["at"] / sc * 100:.2f}%"><span>{html.escape(m["text"])}</span></div>')
        cls = "track marks" if r.get("marks") and not r.get("segs") else "track"
        rows.append(f'<div class="row"><span>{html.escape(r["label"])}</span><div class="{cls}">{"".join(inner)}</div></div>')
    axis = f'<div class="axis"><i></i>{ticks(ch.get("ticks", []), sc)}</div>'
    cap = f'<p>{t(ch["caption"])}</p>' if ch.get("caption") else ""
    return f'<figure class="gantt">{"".join(rows)}{axis}{cap}</figure>'


def render_trick(sid: str, tr: dict) -> str:
    steps = "".join(f'<li><span>{ic(s["icon"], "ic xs") if s.get("icon") else ""}{t(s["text"])}</span></li>' for s in tr["steps"])
    chart = render_chart(tr["chart"]) if tr.get("chart") else ""
    return (f'<div class="trick" data-for="{sid}"><div><h3 class="sec-h">{html.escape(tr["title"])}</h3>'
            f'<p class="sub">{t(tr.get("sub", ""))}</p><ol>{steps}</ol></div>{chart}</div>')


def render_donts(sid: str, donts: list[dict]) -> str:
    items = []
    for dn in donts:
        if dn.get("seq"):
            icons = '<span class="seq">' + "›".join(ic(i, "ic sm") for i in dn["icons"]) + "</span>"
        else:
            icons = f'<span class="x">{ic(dn["icons"][0])}</span>'
        items.append(f'<div class="dont">{icons}<p><b>{html.escape(dn["title"])}</b>{t(dn["text"])}</p></div>')
    return f'<div class="donts" data-for="{sid}"><h3 class="sec-h">别这样做</h3>{"".join(items)}</div>'


def render_evidence(sid: str, ev: list[dict]) -> str:
    lis = "".join(f'<li>{html.escape(e["text"])}：<a href="{html.escape(e["url"])}" target="_blank" rel="noopener">{html.escape(e["label"])}</a></li>' for e in ev)
    return f'<details class="src" data-for="{sid}"><summary>看日志依据（{len(ev)} 条）</summary><ul>{lis}</ul></details>'


TYPE_CHIP = {"kick": ("打断", "k-kick"), "bar": ("钢条", "k-bar"), "unstoppable": ("免控", "k-stop")}


def render_mob(m: dict, specs, tid: str, idx: int, refs: dict) -> str:
    rows = []
    for a in m["skills"]:
        chip = ""
        if a.get("type"):
            label, cls = TYPE_CHIP[a["type"]]
            chip = f'<span class="mtype {cls}">{label}</span>'
        skull = " " + SKULL if a.get("lethal") else ""
        num = (f'<span class="mnum">{html.escape(a["num"])}<i>万</i></span>' if a.get("num") else "")
        cap = f'<span class="mcap">{t(a.get("cap", ""))}</span>' if a.get("num") else ""
        mine = ""
        for sp in specs:
            items = sp.get("trash", {}).get(tid, {}).get("do", {}).get(str(a["id"]))
            if items:
                mine += render_mine_table(sp["spec"], items, refs, a["name"])
        extra = ""
        if n := a.get("note"):
            extra += f'<div class="note"><span>{xref(n["text"], refs, a["name"])}</span></div>'
        if al := a.get("all"):
            extra += f'<div class="all">{xref(al["text"], refs, a["name"])}</div>'
        rows.append(
            f'<div class="mskill{" hot" if a.get("lethal") else ""}">'
            f'<div class="mrow">{ic(a["id"], "ic sm")}<b class="mname">{html.escape(a["name"])}{skull}</b>{num}'
            f'<p class="mmeta">{t(a["what"])}{chip}{school_tags(a["id"])}</p>{cap}</div>{extra}{mine}</div>')
    return (f'<article class="mob" id="{tid}-m{idx}"><div class="mob-head">{zoom_face(m["portrait"], m["name"])}'
            f'<h3>{html.escape(m["name"])}</h3></div>{"".join(rows)}</article>')


def render_trash(tr: dict, d: dict, specs) -> str:
    parts = [f'<section class="boss trash" id="{tr["id"]}"><div class="trash-head"><p class="kicker">小怪</p>'
             f'<h2>{html.escape(tr["title"])}</h2><p class="sum">{t(tr["summary"])}<em>{t(tr.get("summary_em", ""))}</em></p></div>']
    for sp in specs:
        if plan := sp.get("trash", {}).get(tr["id"], {}).get("plan"):
            parts.append(render_plan(sp["spec"], plan))
    if lg := d.get("trash_legend"):
        parts.append(f'<p class="legend"><span class="chip k-kick">打断</span><span class="chip k-bar">钢条</span><span class="chip k-stop">免控</span>{t(lg["text"])}</p>')
    parts.append('<div class="mobs">' + "".join(render_mob(m, specs, tr["id"], i, mob_refs(d, tr["id"])) for i, m in enumerate(tr["mobs"])) + "</div>")
    if sn := tr.get("seen"):
        src = {x["id"]: x for x in d.get("trash", [])}.get(sn["from"], {})
        faces = "".join(zoom_face(m["portrait"], m["name"]) for m in sn["mobs"])
        names = "、".join(m["name"] for m in sn["mobs"])
        parts.append(f'<p class="seen"><span class="pair">{faces}</span><span>{html.escape(names)}：上一段见过，'
                     f'打法同<a href="#{sn["from"]}">{html.escape(src.get("title", ""))}</a>。</span></p>')
    if q := tr.get("quiet"):
        parts.append(f'<p class="quiet">{t(q["text"])}</p>')
    for sp in specs:
        if ev := sp.get("trash", {}).get(tr["id"], {}).get("evidence"):
            parts.append(render_evidence(sp["spec"], ev))
    parts.append("</section>")
    return "".join(parts)


def render_talents(sp: dict, ddir: Path, titles: dict) -> str:
    tl = sp["talents"]
    ts = json.loads((ddir / tl["string_from"]).read_text(encoding="utf-8"))
    string = ts["string"]
    cards = []
    for k in tl.get("keys", []):
        where = "".join(f'<a href="#{w}">{html.escape(titles.get(w, w))}</a>' for w in k.get("where", []))
        cards.append(f'<div class="tal">{ic(k["id"])}<div><b>{html.escape(k["name"])}</b><p>{t(k["text"])}</p>'
                     f'<span class="where">{where}</span></div></div>')
    sid = sp["spec"]
    return (f'<section class="boss talents" id="talents-{sid}" data-for="{sid}"><div class="trash-head"><p class="kicker">天赋</p>'
            f'<h2>{html.escape(sp["name"])}天赋</h2><p class="sum">英雄天赋：{html.escape(tl["hero"])}。{t(tl.get("sub", ""))}</p></div>'
            f'<div class="tstring"><input id="ts-{sid}" readonly value="{html.escape(string)}" aria-label="天赋导入字符串">'
            f'<button type="button" class="copy" data-copy="ts-{sid}">复制</button></div>'
            f'<div class="tals">{"".join(cards)}</div></section>')


def render_boss(b: dict, specs) -> str:
    ports = b["portraits"]
    pcls = "portrait duo" if len(ports) > 1 else "portrait"
    pimgs = "".join(f'<img src="{npc(p)}" alt="">' for p in ports)
    head = (f'<div class="head"><div class="{pcls}" role="img" aria-label="{html.escape(b["name"])}">{pimgs}</div><div>'
            f'<p class="kicker">{html.escape(b["kicker"])}</p><h2>{html.escape(b["name"])}</h2>'
            f'<p class="sum">{t(b["summary"])}<em>{t(b.get("summary_em", ""))}</em></p></div></div>')
    parts = [f'<section class="boss" id="{b["id"]}">', head]
    for sp in specs:
        if plan := sp.get("bosses", {}).get(b["id"], {}).get("plan"):
            parts.append(render_plan(sp["spec"], plan))
    parts.append(render_fight(b, specs))
    for sp in specs:
        sb = sp.get("bosses", {}).get(b["id"], {})
        if sb.get("trick"):
            parts.append(render_trick(sp["spec"], sb["trick"]))
        if sb.get("donts"):
            parts.append(render_donts(sp["spec"], sb["donts"]))
        if sb.get("evidence"):
            parts.append(render_evidence(sp["spec"], sb["evidence"]))
    parts.append("</section>")
    return "".join(parts)


def clean_desc(desc: str) -> str:
    """Wowhead text → tooltip text: drop talent/spec prefixes and base-level numbers (ours are measured)."""
    s = re.sub(r"\s*\[[^\]]*\]", "", desc or "")
    s = re.sub(r"^天赋\s*", "", s.strip())
    s = re.split(r"\s+防护\s+", s)[0]
    s = re.sub(r"^(神圣|惩戒|防护)(, (神圣|惩戒|防护))*\s+", "", s)
    s = re.sub(r"\d{4,}点", "", s)
    return re.sub(r"\s+", " ", s).strip()


def tip_data(page: str, d: dict, ddir: Path) -> dict:
    wh = json.loads((ddir / "evidence" / "wowhead.json").read_text(encoding="utf-8"))
    ours = {}
    for b in d["bosses"]:
        for a in b["abilities"]:
            ours[a["id"]] = (a, b["name"])
    for tr in d.get("trash", []):
        for m in tr["mobs"]:
            for a in m["skills"]:
                ours[a["id"]] = (a, m["name"])
    tips = {}
    for sid in sorted({int(x) for x in re.findall(r'data-tip="(\d+)"', page)}):
        w = wh.get(str(sid)) or {}
        if sid in ours:
            a, who = ours[sid]
            tip = {"n": a["name"], "w": who, "d": a["what"].replace("**", "")}
            if a.get("num"):
                tip["v"] = f'{a["num"]} 万，{a.get("cap", "")}'.rstrip("，")
            if a.get("type"):
                tip["k"] = TYPE_CHIP[a["type"]][0]
        elif w.get("name"):
            tip = {"n": w["name"], "d": clean_desc(w.get("desc") or w.get("aura") or "")}
        else:
            continue
        if sch := schools(sid):
            tip["s"] = "、".join(sch) + "伤害"
        if deb := debuffs(sid):
            tip["s"] = ("、".join(deb) + "效果" + ("，" + tip["s"] if tip.get("s") else ""))
        tips[str(sid)] = tip
    return tips


def render_page(d: dict, specs: list[dict], css: str) -> str:
    have = {s["spec"]: s for s in specs}
    banner = ensure_copy(ROOT / d["banner"], f"dungeon-{Path(d['banner']).name}")
    chips = []
    for sid, name, color, icon in SPEC_CATALOG:
        src = ensure_copy(ROOT / "site/img/icons" / f"{icon}.jpg", f"spec-{icon}.jpg")
        if sid in have:
            chips.append(f'<button class="spec" data-spec="{sid}" style="--c:{color}" aria-pressed="false"><img src="{src}" alt="">{name}</button>')
        else:
            chips.append(f'<button class="spec" style="--c:{color}" disabled><img src="{src}" alt="">{name} <small>制作中</small></button>')
    chips.append(f'<button class="spec none" data-spec="none" style="--c:{NONE_COLOR}" aria-pressed="false">只看副本机制</button>')
    kits = "".join(
        f'<div class="kit" data-for="{s["spec"]}">' + "".join(
            f'<span class="{"warn" if k.get("warn") else ""}">{ic(k["icon"], "ic xs")}<b>{html.escape(k["name"])}</b>{t(k["text"])}</span>'
            for k in s.get("kit", [])) + "</div>" for s in specs)
    bmap = {b["id"]: b for b in d["bosses"]}
    tmap = {x["id"]: x for x in d.get("trash", [])}
    route = d.get("route") or list(bmap)
    nav, sections = [], []
    for i, rid in enumerate(route):
        if rid in tmap:
            nav.append(f'<li class="gap has"><a class="tdot" href="#{rid}" aria-label="{html.escape(tmap[rid]["title"])}小怪"><span>小怪</span></a></li>')
            sections.append(render_trash(tmap[rid], d, specs))
            continue
        b = bmap[rid]
        if i and route[i - 1] not in tmap:
            nav.append('<li class="gap" aria-hidden="true"></li>')
        faces = "".join(f'<span class="face"><img src="{npc(p)}" alt=""></span>' for p in b["portraits"])
        if len(b["portraits"]) > 1:
            faces = f'<span class="pair">{faces}</span>'
        nav.append(f'<li><a href="#{b["id"]}">{faces}<span class="lbl">{html.escape(b["short"])}</span></a></li>')
        sections.append(render_boss(b, specs))
    titles = {x["id"]: x["title"] for x in tmap.values()} | {x["id"]: x["short"] for x in bmap.values()}
    for sp in specs:
        if sp.get("talents"):
            nav.append(f'<li class="gap has" data-for="{sp["spec"]}"><a class="tdot" href="#talents-{sp["spec"]}"><span>天赋</span></a></li>')
            sections.append(render_talents(sp, DDIR, titles))
    bosses = "".join(sections)
    colors = {s["spec"]: s["color"] for s in specs}
    colors["none"] = NONE_COLOR
    js = JS.replace("__COLORS__", json.dumps(colors))
    return f"""<!doctype html>
<html lang="zh-CN" data-spec="none">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{html.escape(d["name"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;900&display=swap">
<style>
{css}
</style>
</head>
<body>
<header class="banner" style="background-image:url({banner})"><div class="wrap"><h1>{html.escape(d["name"])}</h1><p>{t(d["intro"])}</p></div></header>
<div class="wrap">
<div class="specs" role="group" aria-label="选择专精">{"".join(chips)}</div>
<p class="pick-hint" data-hint>先选你的专精，页面会加上你这个专精每一步要按的技能。</p>
{kits}
</div>
<nav class="route" aria-label="路线"><div class="wrap"><ol>{"".join(nav)}</ol></div></nav>
<main class="wrap">
{bosses}
<p class="foot">数据来自 15 场 +23/+24 限时记录。</p>
</main>
<div class="tip" role="tooltip" id="tip" hidden></div>
<figure class="zoombox" id="zoombox" aria-hidden="true" hidden><img alt=""><figcaption></figcaption></figure>
<script type="application/json" id="tips">__TIPS__</script>
<script>{js}</script>
</body>
</html>
"""


JS = """
(function(){
  var root=document.documentElement, btns=document.querySelectorAll('.spec[data-spec]'), colors=__COLORS__;
  var hint=document.querySelector('[data-hint]');
  function set(s, save){
    if(!colors[s]) s='none';
    root.dataset.spec=s;
    root.style.setProperty('--spec',colors[s]);
    btns.forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.spec===s));});
    if(hint) hint.hidden = s!=='none';
    if(save){try{localStorage.setItem('spec',s);}catch(e){}}
  }
  btns.forEach(function(b){b.addEventListener('click',function(){set(b.dataset.spec,true);});});
  var start=location.hash.slice(1);
  if(!colors[start]){try{start=localStorage.getItem('spec')||'none';}catch(e){start='none';}}
  set(start,false);
  var links={};
  document.querySelectorAll('.route a').forEach(function(a){links[a.getAttribute('href').slice(1)]=a;});
  var tips={}; try{tips=JSON.parse(document.getElementById('tips').textContent);}catch(e){}
  var tip=document.getElementById('tip'), cur=null;
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function show(el){
    var d=tips[el.dataset.tip]; if(!d){return;}
    cur=el;
    tip.innerHTML='<b>'+esc(d.n)+'</b>'+(d.k?'<span class="tk">'+esc(d.k)+'</span>':'')+(d.s?'<span class="ts">'+esc(d.s)+'</span>':'')+(d.w?'<small>'+esc(d.w)+'</small>':'')+
      (d.d?'<p>'+esc(d.d)+'</p>':'')+(d.v?'<p class="tv">'+esc(d.v)+'</p>':'');
    tip.hidden=false;
    var r=el.getBoundingClientRect(), tw=tip.offsetWidth, th=tip.offsetHeight;
    var x=Math.min(Math.max(8,r.left+r.width/2-tw/2), window.innerWidth-tw-8);
    var y=r.top-th-10; if(y<8){y=r.bottom+10;}
    tip.style.left=x+'px'; tip.style.top=y+'px';
  }
  function hide(){tip.hidden=true; cur=null;}
  document.querySelectorAll('[data-tip]').forEach(function(el){
    if(!tips[el.dataset.tip]) return;
    el.tabIndex=0; el.setAttribute('aria-label',tips[el.dataset.tip].n);
    el.addEventListener('mouseenter',function(){show(el);});
    el.addEventListener('mouseleave',hide);
    el.addEventListener('focus',function(){show(el);});
    el.addEventListener('blur',hide);
    el.addEventListener('click',function(ev){ev.stopPropagation(); cur===el?hide():show(el);});
  });
  document.addEventListener('click',hide);
  window.addEventListener('scroll',hide,{passive:true});
  var zb=document.getElementById('zoombox'), zcur=null;
  if(zb){
    var zi=zb.querySelector('img'), zc=zb.querySelector('figcaption');
    function zplace(b){
      var r=b.getBoundingClientRect(), w=zb.offsetWidth, h=zb.offsetHeight;
      var x=r.right+12; if(x+w>window.innerWidth-8){x=r.left-w-12;}
      x=Math.max(8,Math.min(x,window.innerWidth-w-8));
      var y=Math.max(8,Math.min(r.top+r.height/2-h/2,window.innerHeight-h-8));
      zb.style.left=x+'px'; zb.style.top=y+'px';
    }
    function zshow(b){
      hide(); zcur=b;
      zi.onload=function(){if(zcur===b){zplace(b);}};
      zi.src=b.querySelector('img').src; zc.textContent=b.dataset.zoom;
      zb.hidden=false; zplace(b);
    }
    function zhide(){zb.hidden=true; zcur=null;}
    document.querySelectorAll('.face.zoom').forEach(function(b){
      b.addEventListener('mouseenter',function(){zshow(b);});
      b.addEventListener('mouseleave',zhide);
      b.addEventListener('focus',function(){zshow(b);});
      b.addEventListener('blur',zhide);
      b.addEventListener('click',function(ev){ev.stopPropagation(); zcur===b?zhide():zshow(b);});
    });
    document.addEventListener('click',zhide);
    window.addEventListener('scroll',zhide,{passive:true});
  }
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){
      if(e.isIntersecting){Object.keys(links).forEach(function(k){links[k].setAttribute('aria-current',String(k===e.target.id));});}
    });},{rootMargin:'-40% 0px -55% 0px'});
    document.querySelectorAll('section.boss').forEach(function(s){io.observe(s);});
  }
})();
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--check", action="store_true", help="只检查不生成")
    a = ap.parse_args()
    global DDIR
    ddir = HERE / a.slug
    DDIR = ddir
    d = json.loads((ddir / "dungeon.json").read_text(encoding="utf-8"))
    specs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ddir / "specs").glob("*.json"))]
    order = [s[0] for s in SPEC_CATALOG]
    specs.sort(key=lambda s: order.index(s["spec"]) if s["spec"] in order else 99)
    WOWHEAD.update(json.loads((ddir / "evidence" / "wowhead.json").read_text(encoding="utf-8")))
    if (ddir / "evidence" / "mdt.lua").is_file():
        MDT_FLAGS.update(load_mdt_flags((ddir / "evidence" / "mdt.lua").read_text(encoding="utf-8")))
    ck = Checker(ddir)
    check(d, specs, ck)
    if ck.errors:
        print(f"检查没过（{len(ck.errors)} 处）：")
        for e in ck.errors:
            print("  -", e)
        return 1
    print("检查通过")
    if a.check:
        return 0
    for b in d["bosses"]:
        for p in b["portraits"]:
            ensure_npc(p)
    for tr in d.get("trash", []):
        for m in tr["mobs"] + tr.get("seen", {}).get("mobs", []):
            ensure_npc(m["portrait"])
    for sp in specs:
        for sb in list(sp.get("bosses", {}).values()) + list(sp.get("trash", {}).values()):
            for p in sb.get("plan", []):
                if "npc" in p.get("on", {}):
                    ensure_npc(p["on"]["npc"])
    css = (HERE / "_shared" / "page.css").read_text(encoding="utf-8")
    out = ddir / f"{a.slug}.html"
    page = render_page(d, specs, css)
    tips = json.dumps(tip_data(page, d, ddir), ensure_ascii=False).replace("</", "<\\/")
    page = page.replace("__TIPS__", tips)
    page, n, fetched = inject_icons(page, out)
    out.write_text(page, encoding="utf-8")
    print(f"写出 {out.relative_to(ROOT)}（图标 {n} 处，新下载 {fetched} 个）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
