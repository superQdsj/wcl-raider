#!/usr/bin/env python3
"""MDT（Mythic Dungeon Tools）副本数据：下载 + 解析，给 check_claims.py mechanics 填「打断 / 吃控 / 驱散」。

MDT 的 Midnight/<副本>.lua 是社区实测维护的怪物表：每只怪吃哪些控制（characteristics）、
每个技能是否可打断（interruptible）、驱散类型（magic / poison / curse / disease / enrage）。
只用正则读取，不执行 Lua。

快照放在 guides/tools/mechanics/<dungeon>.mdt.lua，当作固定版本：不要随手重新下载，
更新时单独做，并重建引用了 mdt:<NPC ID> 的副本页核对出处。
  python3 guides/tools/mdt.py --en "Temple of Sethraliss" --out guides/tools/mechanics/sethraliss.mdt.lua

已知局限：吃控数据不全（塞塔里斯 45 个怪只有 18 个有），没有数据 ≠ 免控；
个别标记和实战不符（细胞毒素标了可打断，日志里是瞬发），与日志冲突时以日志为准。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.request
from pathlib import Path

REPO = "Nnoggie/MythicDungeonTools"
CC_ZH = {"Stun": "晕", "Fear": "恐惧", "Disorient": "迷惑", "Incapacitate": "瘫痪", "Silence": "沉默",
         "Polymorph": "变形", "Root": "定身", "Slow": "减速", "Sap": "闷棍", "Imprison": "禁锢",
         "Taunt": "嘲讽", "Banish": "放逐", "Mind Control": "精神控制", "Knock": "击退"}
DISPEL_ZH = {"magic": "魔法", "poison": "中毒", "curse": "诅咒", "disease": "疾病", "enrage": "激怒", "bleed": "流血"}
HARD_CC = {"Stun", "Fear", "Disorient", "Incapacitate", "Polymorph", "Sap", "Imprison"}


def file_name(en: str) -> str:
    """'Temple of Sethraliss' -> 'TempleOfSethraliss'"""
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[\s'’:-]+", en) if w)


def download(en: str, out: Path) -> Path:
    branch = "master"
    try:
        branch = subprocess.run(["gh", "api", f"repos/{REPO}", "--jq", ".default_branch"],
                                capture_output=True, text=True, timeout=20).stdout.strip() or branch
    except (OSError, subprocess.SubprocessError):
        pass
    url = f"https://raw.githubusercontent.com/{REPO}/{branch}/Midnight/{file_name(en)}.lua"
    with urllib.request.urlopen(url, timeout=30) as r:
        out.write_bytes(r.read())
    return out


def parse(path: Path) -> list[dict]:
    """返回 [{name, cc: [...], spells: {id: {interruptible, dispel}}}]，同名怪可能出现多次（不同波次）。"""
    t = path.read_text(encoding="utf-8")
    mobs = []
    for m in re.finditer(r'\["name"\]\s*=\s*"([^"]+)"(.*?)(?=\["name"\]\s*=|\Z)', t, re.S):
        body = m.group(2)
        ch = re.search(r'\["characteristics"\]\s*=\s*\{(.*?)\}', body, re.S)
        cc = re.findall(r'\["([^"]+)"\]\s*=\s*true', ch.group(1)) if ch else None   # None = MDT 没记录，不等于免控
        spells = {}
        sp = re.search(r'\["spells"\]\s*=\s*\{(.*)', body, re.S)
        if sp:
            for s in re.finditer(r'\[(\d+)\]\s*=\s*\{([^{}]*)\}', sp.group(1)):
                sid = int(s.group(1))
                if sid < 1000:          # 小整数是刷怪点序号，不是技能
                    continue
                flags = set(re.findall(r'\["([^"]+)"\]\s*=\s*true', s.group(2)))
                spells[sid] = {"interruptible": "interruptible" in flags,
                               "dispel": [DISPEL_ZH[f] for f in flags if f in DISPEL_ZH]}
        mobs.append({"name": m.group(1), "cc": cc, "spells": spells})
    return mobs


def by_spell(mobs: list[dict]) -> dict[int, dict]:
    """技能 ID -> {mobs: [英文怪名], cc: 施法者吃控并集, interruptible, dispel}"""
    out = {}
    for mob in mobs:
        for sid, f in mob["spells"].items():
            o = out.setdefault(sid, {"mobs": [], "cc": None, "interruptible": False, "dispel": set()})
            if mob["name"] not in o["mobs"]:
                o["mobs"].append(mob["name"])
            if mob["cc"] is not None:
                o["cc"] = (o["cc"] or set()) | set(mob["cc"])
            o["interruptible"] |= f["interruptible"]
            o["dispel"] |= set(f["dispel"])
    return out


def cc_zh(cc) -> str:
    if cc is None:
        return "MDT 无数据"
    return "、".join(CC_ZH.get(c, c) for c in sorted(cc, key=lambda c: list(CC_ZH).index(c) if c in CC_ZH else 99)) or "免疫一切（MDT 标注为空）"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--en", required=True, help="副本英文名，如 \"Temple of Sethraliss\"")
    ap.add_argument("--out", required=True, help="保存路径，通常是 guides/tools/mechanics/<dungeon>.mdt.lua")
    ap.add_argument("--dump", action="store_true", help="打印解析结果")
    a = ap.parse_args()
    p = download(a.en, Path(a.out))
    mobs = parse(p)
    print(f"wrote {p}（{len(mobs)} 个怪物条目，{len(by_spell(mobs))} 个技能）")
    if a.dump:
        for m in mobs:
            print(json.dumps({"name": m["name"], "cc": m["cc"], "spells": m["spells"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
