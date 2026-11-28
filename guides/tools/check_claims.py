#!/usr/bin/env python3
"""v3 攻略稿的机械闸门：落盘 diag 输出、按结构化证据核对稿件、脚本拼接 guide.md。

子命令（仅用标准库）：
  dump     依次跑 diag.py boss 1-4 + trash，输出落盘到 <src>/diag/（每份首行是命令原文）
  inspect  跑一次 diag.py inspect 并落盘到 <src>/diag/inspect-*.txt，同时打印到 stdout
  check    逐条 PASS/FAIL 核对 boss1-4.md、trash.md（以及 claims.json），有 FAIL 则退出码 1
  merge    把 boss1-4.md + trash.md 拼成 guide.md（不经模型改写）
  mechanics  从 diag/*.txt 的「① 机制速览」抽出副本机制卡骨架（新副本的阶段 0 用）

典型用法：
  python3 guides/tools/check_claims.py dump    guides/v3/sethraliss/drafts/hunter-beastmastery
  python3 guides/tools/check_claims.py inspect guides/v3/sethraliss/drafts/hunter-beastmastery --boss 2 --ability 1293048 --only-bare
  python3 guides/tools/check_claims.py check   guides/v3/sethraliss/drafts/hunter-beastmastery --banned guides/tools/mechanics/sethraliss.banned.txt
  python3 guides/tools/check_claims.py merge   guides/v3/sethraliss/drafts/hunter-beastmastery --spec-name 兽王猎

目录约定：guides/v3/<dungeon>/drafts/<spec>/，副本名和专精名都由路径推断。
职业配置：drafts/<spec> → guides/tools/classes/<CLASS_JSON[spec]>.json（v2 的旧目录 guides/<slug>/sources/... 仍然可用）。
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
DIAG = TOOLS / 'diag.py'

SECTIONS = ['boss1', 'boss2', 'boss3', 'boss4', 'trash']
LIMITS = {'boss': 2200, 'trash': 3200}          # 可见字符（链接只计标签文字）
RULES = {'boss': (3, 5), 'trash': (5, 7)}
EVIDENCE = {'boss': (2, 2), 'trash': (2, 3)}
# 标签覆盖：(说明, 匹配的关键词, 缺失时 FAIL 还是 WARN)
TAGS = {
    'boss': [('不交', ('不交',), 'FAIL'), ('必交', ('必交',), 'FAIL'),
             ('贪输出/交互', ('贪输出', '交互'), 'WARN'), ('避坑', ('避坑',), 'FAIL')],
    'trash': [('必交', ('必交',), 'FAIL'), ('免疫/清除', ('免疫', '清除', '秒消'), 'FAIL'),
              ('驱散/功能牌', ('驱散', '功能', '位移'), 'WARN'),
              ('控断/群控', ('控断', '打断', '群控'), 'FAIL'), ('避坑', ('避坑',), 'FAIL')],
}
NEEDS_BARE = ('必交', '不交')                    # 这两类结论必须来自纯裸吃样本
NEEDS_LINK = ('免疫', '清除', '打断', '驱散')    # 这几类结论必须附原始事件链接

URL_RE = re.compile(r'https://(?:www\.|cn\.)?warcraftlogs\.com/reports/[A-Za-z0-9]+[^\s)\]>]*')
LABELED_RE = re.compile(r'\[(r\d{2})@[^\]]*\]\((' + URL_RE.pattern + r')\)')
RULE_RE = re.compile(r'^(\d+)\.\s+\*\*((?:【[^】]+】)+)', re.M)
NUM_PATTERNS = [re.compile(p) for p in (
    r'(?:\d+|—)%→\d+%',             # 起手→剩血
    r'\d+(?:\.\d+)?[KM](?![A-Za-z])',  # 伤害量
    r'\d+/\d+',                      # 分子/分母
)]


# ---------------------------------------------------------------- 工具函数

def rel(p):
    p = Path(p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


# v3 草稿目录用英文全称，职业配置文件沿用 v2 的旧名（v2 工具也在用）。
CLASS_JSON = {
    'rogue-subtlety': 'rogue-sub',
    'paladin-retribution': 'paladin-ret',
    'hunter-beastmastery': 'hunter-bm',
}


def guess_dungeon(src):
    """guides/v3/<dungeon>/drafts/<spec> → <dungeon>；旧目录 sources/<dungeon>-v3 → <dungeon>。"""
    src = Path(src).resolve()
    if src.parent.name == 'drafts':
        return src.parent.parent.name
    return re.sub(r'-v\d+$', '', src.name)


def guess_class_json(src):
    parts = Path(src).resolve().parts
    slug = None
    if 'drafts' in parts and parts.index('drafts') + 1 < len(parts):
        slug = parts[parts.index('drafts') + 1]
        slug = CLASS_JSON.get(slug, slug)
    elif 'sources' in parts:
        slug = parts[parts.index('sources') - 1]
    if slug:
        cand = TOOLS / 'classes' / f'{slug}.json'
        if cand.exists():
            return cand
    sys.exit(f'无法从 {src} 推断职业配置，请用 --class-json 指定')


def diag_dir(args):
    return Path(args.diag_dir) if args.diag_dir else Path(args.src) / 'diag'


def run_diag(argv, out):
    """跑 diag.py，stdout+stderr 落盘，首行写命令原文。返回 (退出码, 文本)。"""
    shown = ['python3', rel(DIAG)] + argv
    proc = subprocess.run([sys.executable, str(DIAG)] + argv, cwd=ROOT,
                          capture_output=True, text=True)
    text = f'$ {shlex.join(shown)}\n' + proc.stdout + (proc.stderr or '')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    return proc.returncode, text


def visible(text):
    """链接只保留方括号里的标签，用于字数统计与数字抽取。"""
    return re.sub(r'\]\([^)]*\)', ']', text)


def has_number(text, num):
    return re.search(r'(?<![\d.])' + re.escape(str(num)) + r'(?![\d.])', text) is not None


def has_pct(text, num):
    return re.search(r'(?<![\d.])' + re.escape(str(num)) + r'%', text) is not None


def parse_tables(text):
    """解析 inspect 明细表：返回 (行列表[dict], 表头声明的总条数)。"""
    rows, total, header = [], None, None
    m = re.search(r'共\s*(\d+)\s*条', text)
    if m:
        total = int(m.group(1))
    for line in text.splitlines():
        if not line.startswith('|'):
            header = None if not line.strip() else header
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if '起手→剩血' in cells:
            header = cells
        elif header and cells and cells[0].startswith('[r'):
            rows.append(dict(zip(header, cells)))
    return rows, total


def remaining(row):
    m = re.search(r'→(\d+)%', row.get('起手→剩血', ''))
    return int(m.group(1)) if m else None


def filter_rows(rows, where):
    out = []
    for r in rows:
        hp = remaining(r)
        if 'cover' in where and r.get('减伤/其他覆盖') != where['cover']:
            continue
        if 'status' in where and not r.get('状态', '').startswith(where['status']):
            continue
        if 'remaining_lt' in where and (hp is None or hp >= where['remaining_lt']):
            continue
        if 'remaining_ge' in where and (hp is None or hp < where['remaining_ge']):
            continue
        out.append(r)
    return out


class Report:
    def __init__(self, quiet=False):
        self.items, self.quiet = [], quiet

    def add(self, status, where, msg):
        self.items.append((status, where, msg))
        if not (self.quiet and status == 'PASS'):
            print(f'{status:4} {where}: {msg}')

    def ok(self, cond, where, msg_pass, msg_fail, level='FAIL'):
        self.add('PASS' if cond else level, where, msg_pass if cond else msg_fail)
        return cond

    def summary(self):
        n = {k: sum(1 for s, _, _ in self.items if s == k) for k in ('PASS', 'FAIL', 'WARN', 'INFO')}
        print(f'\n合计：PASS {n["PASS"]} / FAIL {n["FAIL"]} / WARN {n["WARN"]} / INFO {n["INFO"]}')
        return n['FAIL']


# ---------------------------------------------------------------- dump / inspect

def cmd_dump(args):
    src, out = Path(args.src), diag_dir(args)
    runs = src / 'runs.json'
    cls = Path(args.class_json) if args.class_json else guess_class_json(src)
    base = ['--runs', rel(runs), '--class', rel(cls)] + ([] if args.wowhead else ['--no-wowhead'])
    jobs = [(f'boss{i}', ['boss'] + base + ['--boss', str(i)]) for i in range(1, 5)]
    jobs.append(('trash', ['trash'] + base))
    only = set(args.only.split(',')) if args.only else None
    jobs = [j for j in jobs if not only or j[0] in only]

    def work(job):
        name, argv = job
        code, text = run_diag(argv, out / f'{name}.txt')
        return name, code, len(text)

    bad = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for name, code, size in ex.map(work, jobs):
            bad += code != 0
            print(f'{"PASS" if code == 0 else "FAIL"} {name}: {rel(out / (name + ".txt"))}（{size} 字符，退出码 {code}）')
    return 1 if bad else 0


def cmd_inspect(args):
    src = Path(args.src)
    cls = Path(args.class_json) if args.class_json else guess_class_json(src)
    argv = ['inspect', '--runs', rel(src / 'runs.json'), '--class', rel(cls)]
    scope = 'trash' if args.trash else f'boss{args.boss}'
    argv += ['--trash'] if args.trash else ['--boss', str(args.boss)]
    argv += ['--ability', args.ability]
    suffix = ''
    if args.only_hit:
        argv.append('--only-hit')
        suffix += '-hit'
    if args.only_bare:
        argv.append('--only-bare')
        suffix += '-bare'
    if args.limit is not None:
        argv += ['--limit', str(args.limit)]
        suffix += f'-l{args.limit}'
    key = re.sub(r'[^\w]+', '_', args.ability).strip('_')
    out = diag_dir(args) / f'inspect-{scope}-{key}{suffix}.txt'
    code, text = run_diag(argv, out)
    sys.stdout.write(text)
    print(f'\n[已落盘] {rel(out)}')
    return code


# ---------------------------------------------------------------- check

def load_runs(src):
    try:
        data = json.loads((Path(src) / 'runs.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {r['tag']: (r['code'], str(r['fid'])) for r in data.get('runs', [])}


def load_diag(ddir):
    files = {}
    for p in sorted(Path(ddir).glob('*.txt')) if Path(ddir).is_dir() else []:
        files[p.name] = p.read_text(encoding='utf-8')
    return files


def split_rules(text):
    """返回 {序号: (标签串, 该条全文)}。"""
    out, ms = {}, list(RULE_RE.finditer(text))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        body = text[m.start():end]
        body = body.split('\n- *实测背书')[0]
        out[int(m.group(1))] = (m.group(2), body)
    return out


def check_format(rep, name, text, kind, banned):
    where = f'{name}.md'
    lines = [l for l in text.splitlines() if l.strip()]
    rep.ok(lines and re.match(r'#{1,2} ', lines[0]), where, '标题行', '首行不是 "#"/"##" 标题')
    rep.ok(any(l.startswith('> **一句话流程**') for l in lines), where, '一句话流程', '缺 "> **一句话流程**"')
    n_vis, cap = len(visible(text)), LIMITS[kind]
    rep.ok(n_vis <= cap, where, f'可见字符 {n_vis} ≤ {cap}', f'可见字符 {n_vis} > 上限 {cap}')
    rules = split_rules(text)
    lo, hi = RULES[kind]
    rep.ok(lo <= len(rules) <= hi, where, f'口诀 {len(rules)} 条', f'口诀 {len(rules)} 条，应为 {lo}–{hi}')
    tags = ''.join(t for t, _ in rules.values())
    for label, keys, level in TAGS[kind]:
        rep.ok(any(k in tags for k in keys), where, f'标签覆盖【{label}】', f'缺标签【{label}】', level)
    ev = [l for l in lines if l.startswith('- *实测背书')]
    lo, hi = EVIDENCE[kind]
    rep.ok(lo <= len(ev) <= hi, where, f'实测背书 {len(ev)} 行', f'实测背书 {len(ev)} 行，应为 {lo}–{hi}')
    for i, l in enumerate(ev, 1):
        rep.ok(URL_RE.search(l), where, f'背书 {i} 含链接', f'背书 {i} 没有 WCL 链接')
    bad = re.search(r'第\s*\d+\s*轮', text) or any(l.startswith('|') for l in lines)
    rep.ok(not bad, where, '无固定轮次时间表', '出现「第 N 轮」或表格，疑似固定时间表')
    for phrase in banned:
        hit = re.search(phrase, text)
        rep.ok(not hit, where, f'无禁用说法 /{phrase}/',
               f'出现禁用说法 /{phrase}/：…{text[max(0, hit.start() - 20):hit.end() + 20] if hit else ""}…')


def check_links(rep, name, text, runs, diag_links, have_diag):
    where = f'{name}.md'
    urls = URL_RE.findall(text)
    if not urls:
        rep.add('FAIL', where, '全文没有 WCL 链接')
        return
    codes = {c for c, _ in runs.values()}
    foreign = [u for u in urls if re.search(r'/reports/([A-Za-z0-9]+)', u).group(1) not in codes]
    rep.ok(not foreign, where, f'{len(urls)} 条链接的报告都在 runs.json',
           f'{len(foreign)} 条链接的报告不在 runs.json：{foreign[:3]}')
    mislabeled = []
    for tag, url in LABELED_RE.findall(text):
        code = re.search(r'/reports/([A-Za-z0-9]+)', url).group(1)
        fid = (re.search(r'fight=(\d+)', url) or [None, None])[1]
        if tag in runs and runs[tag] != (code, fid):
            mislabeled.append(f'{tag}→{code}#fight={fid}')
    rep.ok(not mislabeled, where, '链接标签 rNN 与 runs.json 一致', f'标签与报告不符：{mislabeled[:5]}')
    if not have_diag:
        rep.add('FAIL', where, 'diag 目录为空，无法逐字核对链接')
        return
    missing = [u for u in urls if u not in diag_links]
    rep.ok(not missing, where, f'{len(urls)} 条链接逐字出现在 diag 输出',
           f'{len(missing)}/{len(urls)} 条链接不在 diag 输出：' + '；'.join(missing[:4]) + ('…' if len(missing) > 4 else ''))


def check_numbers(rep, name, text, blob, strict, show):
    toks = []
    vis = visible(text)
    for pat in NUM_PATTERNS:
        toks += pat.findall(vis)
    toks = list(dict.fromkeys(toks))
    if not toks:
        return
    miss = [t for t in toks if t not in blob]
    msg = f'数字原文命中 {len(toks) - len(miss)}/{len(toks)}'
    if miss:
        msg += '；未命中（可能是写手自行汇总）：' + '、'.join(miss[:show]) + ('…' if len(miss) > show else '')
    rep.add('FAIL' if strict and miss else 'INFO', f'{name}.md', msg)


def check_claims(rep, claims, mds, files):
    for name in SECTIONS:
        if name not in mds:
            continue
        rules = split_rules(mds[name])
        items = claims.get(name, [])
        covered = {c.get('rule') for c in items}
        for no in rules:
            rep.ok(no in covered, f'{name}.md#{no}', '有结构化证据', '口诀没有对应的 claims 条目')
        for i, c in enumerate(items):
            check_claim(rep, f'claims.{name}[{i}]', c, rules, mds[name], files)


def check_claim(rep, where, c, rules, md, files):
    no, typ = c.get('rule'), c.get('type', '')
    if not rep.ok(no in rules, where, f'对应第 {no} 条', f'md 里没有第 {no} 条口诀'):
        return
    tags, body = rules[no]
    rep.ok(typ and typ in tags, where, f'类型「{typ}」与标签 {tags} 一致', f'类型「{typ}」不在标签 {tags} 中')
    src = c.get('source')
    if not rep.ok(src in files, where, f'来源 {src}', f'来源文件 {src} 不在 diag/'):
        return
    text = files[src]
    head = text.splitlines()[0][2:] if text.startswith('$ ') else ''
    if c.get('command'):
        rep.ok(c['command'].strip() == head, where, '命令原文与落盘首行一致', f'命令不符：落盘为 `{head}`')
    for ab in c.get('ability', []):
        rep.ok(has_number(text, ab), where, f'技能 {ab} 出现在来源', f'技能 {ab} 不在来源中')
    where_ = c.get('where', {})
    bare = '--only-bare' in head or where_.get('cover') == '纯裸吃'
    if any(k in typ for k in NEEDS_BARE):
        rep.ok(bare, where, '基于纯裸吃样本', '必交/不交须基于纯裸吃样本（--only-bare 或 where.cover=纯裸吃）')
        rep.ok('m' in c and 'min_hp' in c, where, '有分母与最低血线', '必交/不交须给 m（分母）和 min_hp（最低剩血）')
    if any(k in typ for k in NEEDS_LINK):
        rep.ok(c.get('links'), where, '附事件链接', f'「{typ}」须附原始事件链接')

    rows, total = parse_tables(text)
    sel = filter_rows(rows, where_) if rows else []
    truncated = bool(rows) and total is not None and len(rows) < total
    if 'm' in c:
        base = filter_rows(rows, {k: v for k, v in where_.items() if k in ('cover', 'status')}) if rows else []
        if rows and not truncated:
            rep.ok(len(base) == c['m'], where, f'分母 m={c["m"]} 与明细表一致', f'分母 m={c["m"]}，明细表为 {len(base)}')
        else:
            rep.ok(has_number(text, c['m']), where, f'分母 m={c["m"]} 在来源原文中',
                   f'分母 m={c["m"]} 在来源中找不到' + ('（明细表被 --limit 截断）' if truncated else ''))
    if 'n' in c:
        if rows and not truncated and where_:
            rep.ok(len(sel) == c['n'], where, f'分子 n={c["n"]} 与明细表筛选一致', f'分子 n={c["n"]}，按 where 筛得 {len(sel)}')
        else:
            rep.ok(has_number(text, c['n']), where, f'分子 n={c["n"]} 在来源原文中', f'分子 n={c["n"]} 在来源中找不到')
    if 'min_hp' in c:
        hps = [h for h in (remaining(r) for r in (sel if where_ else rows)) if h is not None]
        if hps and not truncated:
            rep.ok(min(hps) == c['min_hp'], where, f'最低剩血 {c["min_hp"]}% 与明细表一致', f'最低剩血写 {c["min_hp"]}%，明细表为 {min(hps)}%')
        else:
            rep.ok(has_pct(text, c['min_hp']), where, f'最低剩血 {c["min_hp"]}% 在来源原文中', f'最低剩血 {c["min_hp"]}% 在来源中找不到')
    # 与 md 一致：数字写进了这条口诀或背书
    for key in ('n', 'm'):
        if key in c:
            rep.ok(has_number(md, c[key]), where, f'{key}={c[key]} 出现在稿件', f'{key}={c[key]} 没写进稿件')
    if 'min_hp' in c:
        rep.ok(has_pct(md, c['min_hp']), where, f'最低剩血 {c["min_hp"]}% 出现在稿件', f'最低剩血 {c["min_hp"]}% 没写进稿件')
    for u in c.get('links', []):
        rep.ok(u in md and u in text, where, '链接在稿件与来源中', f'链接不在稿件或来源中：{u}')
    for q in c.get('quote', []):
        rep.ok(q in text, where, f'原文片段「{q}」在来源', f'原文片段「{q}」不在来源')


def cmd_check(args):
    src = Path(args.src)
    rep = Report(args.quiet)
    runs = load_runs(src)
    rep.ok(bool(runs), 'runs.json', f'{len(runs)} 场样本', '读不到 runs.json')
    files = load_diag(diag_dir(args))
    rep.ok(bool(files), 'diag/', f'{len(files)} 份落盘输出', f'{rel(diag_dir(args))} 下没有 *.txt')
    blob = '\n'.join(files.values())
    diag_links = set(URL_RE.findall(blob))
    banned = []
    for f in args.banned or []:
        banned += [l.strip() for l in Path(f).read_text(encoding='utf-8').splitlines()
                   if l.strip() and not l.startswith('#')]
    mds = {}
    for name in SECTIONS:
        p = src / f'{name}.md'
        if not rep.ok(p.exists(), f'{name}.md', '存在', '缺失'):
            continue
        mds[name] = p.read_text(encoding='utf-8')
        kind = 'trash' if name == 'trash' else 'boss'
        check_format(rep, name, mds[name], kind, banned)
        check_links(rep, name, mds[name], runs, diag_links, bool(files))
        check_numbers(rep, name, mds[name], blob, args.strict_numbers, args.show)
    cpath = Path(args.claims) if args.claims else src / 'claims.json'
    if cpath.exists():
        try:
            claims = json.loads(cpath.read_text(encoding='utf-8'))
        except ValueError as e:
            rep.add('FAIL', 'claims.json', f'JSON 解析失败：{e}')
        else:
            check_claims(rep, claims, mds, files)
    else:
        rep.add('WARN' if args.allow_no_claims else 'FAIL', 'claims.json', f'{rel(cpath)} 不存在，跳过逐条证据核对')
    return 1 if rep.summary() else 0


# ---------------------------------------------------------------- merge

def cmd_merge(args):
    src = Path(args.src)
    parts = []
    for name in SECTIONS:
        p = src / f'{name}.md'
        if not p.exists():
            sys.exit(f'缺 {rel(p)}')
        part = p.read_text(encoding='utf-8').strip()
        parts.append('#' + part if re.match(r'# ', part) else part)   # 分节统一为二级标题
    if args.header:
        header = Path(args.header).read_text(encoding='utf-8').strip()
    else:
        if not args.spec_name:
            sys.exit('请给 --spec-name（如 兽王猎），或用 --header 指定页眉文件')
        data = json.loads((src / 'runs.json').read_text(encoding='utf-8'))
        lv = sorted({r['level'] for r in data['runs']})
        lv_s = '/'.join(f'+{x}' for x in lv)
        n, spec = len(data['runs']), args.spec_name
        full = data.get('class', '')
        who = f'{spec}（{full}）' if full and full != spec else spec
        header = (f'# {data["dungeon"]}（{spec} · {lv_s} 限时 {n} 场实战口诀）\n\n'
                  f'> 基于 {n} 场 {lv_s} 限时顶分{who}WCL 日志（`runs.json`）逐事件诊断与交叉证伪整理，'
                  f'按条件触发而非固定轮次给牌；全本共含 **老 1 ~ 老 4 + 全本小怪** 五块实战口诀。'
                  f'样本仅含限时成功局，「不交也稳」的结论不代表失败局。')
    text = header + '\n\n---\n\n' + '\n\n---\n\n'.join(parts) + '\n'
    out = Path(args.out) if args.out else src / 'guide.md'
    if args.diff:
        old = out.read_text(encoding='utf-8') if out.exists() else ''
        same = old == text
        if not same and old:
            same_body = old.split('\n\n---\n\n', 1)[-1] == text.split('\n\n---\n\n', 1)[-1]
            print(f'与 {rel(out)} {"仅页眉不同" if same_body else "正文不同"}')
        else:
            print(f'与 {rel(out)} {"逐字一致" if same else "不同"}')
        return 0 if same else 1
    out.write_text(text, encoding='utf-8')
    print(f'已写入 {rel(out)}（{len(text)} 字符）')
    return 0


# ---------------------------------------------------------------- main

# ---------------------------------------------------------------------------
# mechanics：从 diag ① 抽副本机制卡骨架（只含日志统计，去掉本专精相关的血量占比）

BOSS_MECH = re.compile(
    r'^\s*- \*\*(?P<name>.+?)\*\*（(?P<caster>.+?), ID:(?P<ids>[\d/]+)）：(?P<shape>[^|]+?)\s*\|'
    r'\s*周期 (?P<period>[^|]+?)\s*\|\s*(?P<dmg>[^|]+?)\s*\|\s*共(?P<waves>\d+)波（中(?P<hit>\d+) / 免疫(?P<imm>\d+) / 躲避未中(?P<miss>\d+)）')
TRASH_MECH = re.compile(
    r'^\s*- \*\*(?P<mob>.+?) · (?P<skill>.+?)\*\*（ID:(?P<ids>[\d/]+)，(?P<kind>.+?)）：(?P<dmg>[^|]+?)\s*\|'
    r'\s*中(?P<hit>\d+) / 免疫(?P<imm>\d+) / 未中(?P<miss>\d+)（覆盖(?P<cov>\d+)/(?P<n>\d+)场）')


def neutral_damage(text):
    """去掉占本专精血量的百分比，只留绝对值。"""
    t = text.strip()
    m = re.search(r'全队命中中位 ([\d.]+[KM]?)', t)
    if t.startswith('本专精0掉血') and m:
        return f'样本专精未中招；全队命中中位 {m.group(1)}'
    if t.startswith('本专精0直接承伤'):
        return '样本专精未直接承伤'
    t = re.sub(r'\s*\(\d+%HP\)', '', t)
    t = re.sub(r'\s*≈\d+%本专精HP', '', t)
    t = t.replace('纯裸吃中位', '裸吃中位')
    t = re.sub(r'\((\d+)跳合\)', r'（\1 跳合计）', t)
    return t


def section_one(text):
    m = re.search(r'^## ①.*?$(.*?)^## ②', text, re.S | re.M)
    return m.group(1) if m else ''


def boss_title(text, fallback):
    first = text.splitlines()[1] if text.startswith('$ ') else text.splitlines()[0]
    for line in text.splitlines()[:3]:
        if line.startswith('# '):
            first = line
            break
    parts = [x.strip() for x in first.lstrip('# ').split('·')]
    name = parts[1] if len(parts) > 1 else fallback
    return re.sub(r'（encounter \d+）', '', name).strip()


def mdt_note(info):
    """MDT 一个技能的打断 / 驱散 / 施法者吃控，写成一格。"""
    import mdt  # noqa: E402（同目录）
    if not info:
        return 'MDT 无此技能'
    parts = ['可打断' if info['interruptible'] else '不可打断']
    if info['dispel']:
        parts.append('驱散：' + '、'.join(sorted(info['dispel'])))
    cc = info['cc']
    if cc is None:
        parts.append('吃控：MDT 无数据')
    else:
        hard = [c for c in cc if c in mdt.HARD_CC]
        parts.append('吃控：' + mdt.cc_zh(set(hard)) if hard else '不吃硬控')
    return '；'.join(parts)


def load_mdt(path):
    import mdt  # noqa: E402
    return mdt.by_spell(mdt.parse(Path(path)))


LOG_MIN_CASTS = 20   # 至少这么多次施放才敢用"0 读条 0 打断"推翻 MDT 的可打断


def log_interrupt_stats(src):
    """从样本日志统计每个敌方技能：施放次数、读条次数、被友方打断次数。只走 diag 的整场查询（命中缓存）。"""
    import diag  # noqa: E402（同目录）
    from collections import Counter
    client = diag.Client(api_version='auto', refresh=False)
    _meta, samples = diag.load_samples(Path(src) / 'runs.json')
    casts, begins, kicked = Counter(), Counter(), Counter()
    for smp in samples:
        run = diag.load_run(client, f"{smp.code}#fight={smp.fid}")
        for e in diag.full_events(run, 'Casts', hostility='Enemies'):
            sid = e.get('abilityGameID')
            if e.get('type') == 'cast':
                casts[sid] += 1
            elif e.get('type') == 'begincast':
                begins[sid] += 1
        for e in diag.full_events(run, 'Interrupts'):
            kicked[e.get('extraAbilityGameID')] += 1
    return {'casts': casts, 'begins': begins, 'kicked': kicked, 'n': len(samples)}


def _mmss(ms):
    s = int(round(ms / 1000))
    return f'{s // 60}:{s % 60:02d}'


def _median(vals):
    import statistics
    return statistics.median(vals) if vals else None


SEG_NAMES = ['老 1 之前', '老 1 → 老 2', '老 2 → 老 3', '老 3 → 老 4', '老 4 之后']


def log_flow(src, boss_ids):
    """从样本日志推出每个首领的流程事实和小怪分段。boss_ids: {'1': {技能 ID, ...}, ...}。
    只用战斗列表、敌方施法（整场查询，命中缓存）和敌方死亡（整场查询）。"""
    import diag  # noqa: E402
    from collections import Counter, defaultdict
    client = diag.Client(api_version='auto', refresh=False)
    _meta, samples = diag.load_samples(Path(src) / 'runs.json')
    n = len(samples)
    boss = {b: {'dur': [], 'units': defaultdict(list), 'bosses': set(), 'death': defaultdict(list),
                'first': defaultdict(list)} for b in boss_ids}
    seg_runs, seg_cnt = defaultdict(Counter), defaultdict(lambda: defaultdict(list))
    for smp in samples:
        run = diag.load_run(client, f"{smp.code}#fight={smp.fid}")
        casts = diag.full_events(run, 'Casts', hostility='Enemies')
        deaths = diag.full_events(run, 'Deaths', hostility='Enemies')
        for b, ids in boss_ids.items():
            pulls = diag.find_boss_pulls(run, b)
            if not pulls:
                continue
            p = ([x for x in pulls if x.kill] or pulls)[-1]
            rec = boss[b]
            rec['dur'].append(p.dur)
            rec['bosses'] |= set(p.boss_names)
            for name, cnt in p.mobs:
                rec['units'][name].append(cnt)
            seen = {}
            for e in deaths:
                ts = float(e.get('timestamp') or 0)
                if p.start <= ts <= p.end + 1000:
                    nm = run.actor_name(e.get('targetID'))
                    seen.setdefault(nm, ts - p.start)
            for nm, off in seen.items():
                rec['death'][nm].append(off)
            first = {}
            for e in casts:
                sid = e.get('abilityGameID')
                ts = float(e.get('timestamp') or 0)
                if sid in ids and p.start <= ts <= p.end and e.get('type') in ('cast', 'begincast'):
                    first.setdefault(sid, (ts - p.start, (e.get('ability') or {}).get('name') or str(sid)))
            for sid, (off, nm) in first.items():
                rec['first'][(sid, nm)].append(off)
        kills = []
        for p in sorted((x for x in run.pulls if x.is_boss and x.kill), key=lambda x: x.end):
            if p.encounter_id not in [k for _, k in kills]:
                kills.append((p.end, p.encounter_id))
        seen_seg = defaultdict(set)
        for p in run.pulls:
            if p.is_boss:
                continue
            seg = sum(1 for end, _ in kills if end <= p.start)
            for name, cnt in p.mobs:
                seen_seg[seg].add(name)
                seg_cnt[seg][name].append(cnt)
        for seg, names in seen_seg.items():
            for nm in names:
                seg_runs[seg][nm] += 1

    half = n / 2
    out = {}
    for b, rec in boss.items():
        if not rec['dur']:
            continue
        lines = [f"中位时长 {_mmss(_median(rec['dur']))}（{len(rec['dur'])}/{n} 场）"]
        units = [(nm, len(v), _median(v)) for nm, v in rec['units'].items() if len(v) >= half]
        units.sort(key=lambda x: (x[0] not in rec['bosses'], -x[2]))
        if units:
            lines.append('同场敌方单位（每场中位数量）：' + '、'.join(
                f"{nm}{'（首领）' if nm in rec['bosses'] else ''} ×{cnt:g}" for nm, _r, cnt in units))
        order = sorted(((nm, _median(v)) for nm, v in rec['death'].items()
                        if len(v) >= half and (nm in rec['bosses'] or _median(rec['units'].get(nm, [9])) <= 3)),
                       key=lambda x: x[1])
        if len(order) >= 2:
            lines.append('击杀顺序（中位首次死亡时刻）：' + ' → '.join(f'{nm} +{_mmss(off)}' for nm, off in order[:8]))
        first = sorted(((nm, _median(v)) for (sid, nm), v in rec['first'].items() if len(v) >= half),
                       key=lambda x: x[1])
        if first:
            lines.append('开怪后首次施放（中位）：' + ' → '.join(f'{nm} +{_mmss(off)}' for nm, off in first[:8]))
        out[b] = lines
    segs = []
    for seg in sorted(seg_runs):
        mobs = [(nm, r, _median(seg_cnt[seg][nm])) for nm, r in seg_runs[seg].most_common() if r >= half]
        if mobs:
            label = SEG_NAMES[seg] if seg < len(SEG_NAMES) else f'段 {seg}'
            segs.append(f'{label}：' + '、'.join(f'{nm} ×{c:g}（{r}/{n} 场）' for nm, r, c in mobs))
    out['trash'] = segs
    return out


def mdt_cell(table, ids, logs=None):
    """MDT 标记 + 日志核对；冲突时以日志为准，并写明证据。"""
    id_list = [int(i) for i in ids.split('/')]
    hits = [table[i] for i in id_list if i in table] if table is not None else []
    n_cast = n_begin = n_kick = 0
    if logs:
        n_cast = sum(logs['casts'][i] for i in id_list)
        n_begin = sum(logs['begins'][i] for i in id_list)
        n_kick = sum(logs['kicked'][i] for i in id_list)
    if table is None and not logs:
        return '<待补>'
    if not hits:
        if n_kick:
            return f'可打断（日志：被打断 {n_kick} 次；MDT 无此技能）'
        return 'MDT 无此技能'
    merged = {'interruptible': any(h['interruptible'] for h in hits),
              'dispel': set().union(*[h['dispel'] for h in hits]),
              'cc': None if all(h['cc'] is None for h in hits)
              else set().union(*[h['cc'] for h in hits if h['cc'] is not None])}
    note = mdt_note(merged) + '（MDT）'
    if logs and merged['interruptible'] and n_kick == 0 and n_begin == 0 and n_cast + n_begin >= LOG_MIN_CASTS:
        note = note.replace('可打断', '不可打断', 1)
        note += f'；以日志为准：{n_cast} 次施放、0 次读条、0 次被打断，MDT 标可打断'
    elif logs and not merged['interruptible'] and n_kick:
        note = note.replace('不可打断', '可打断', 1)
        note += f'；以日志为准：被打断 {n_kick} 次，MDT 标不可打断'
    elif logs and n_kick:
        note += f'；日志被打断 {n_kick} 次'
    return note


def cmd_mechanics(args):
    src = Path(args.src)
    files = load_diag(diag_dir(args))
    if not files:
        print(f'FAIL {rel(diag_dir(args))} 下没有 diag 输出，先跑 dump', file=sys.stderr)
        return 1
    dungeon = guess_dungeon(src)
    out = Path(args.out) if args.out else TOOLS / 'mechanics' / f'{dungeon}.draft.md'
    mdt_path = Path(args.mdt) if args.mdt else TOOLS / 'mechanics' / f'{dungeon}.mdt.lua'
    mdt_table = load_mdt(mdt_path) if mdt_path.is_file() else None
    logs = None
    if not args.no_log and (src / 'runs.json').is_file():
        try:
            logs = log_interrupt_stats(src)
        except Exception as exc:  # 联网失败也能出草稿，只是不做日志核对
            print(f'WARN 日志核对跳过：{exc}', file=sys.stderr)
    flow = {}
    if logs is not None:
        boss_ids = {}
        for i in range(1, 5):
            text = files.get(f'boss{i}.txt')
            if text:
                ids = set()
                for raw in section_one(text).splitlines():
                    m = BOSS_MECH.match(raw)
                    if m:
                        ids |= {int(x) for x in m.group('ids').split('/')}
                boss_ids[str(i)] = ids
        try:
            flow = log_flow(src, boss_ids)
        except Exception as exc:
            print(f'WARN 流程推导跳过：{exc}', file=sys.stderr)
    if out.exists() and not args.force:
        print(f'FAIL {rel(out)} 已存在，加 --force 覆盖', file=sys.stderr)
        return 1
    try:
        n_runs = len(load_runs(src))
    except Exception:
        n_runs = '?'
    lines = [
        f'# {dungeon} · 共享机制源（草稿，待用户确认）', '',
        f'> 由 `check_claims.py mechanics` 从 `{rel(src)}/diag/` 的「① 机制速览」自动抽取，样本 {n_runs} 场。',
        '> 只有日志能统计出来的部分：技能、ID、施放者、目标形态、周期、伤害绝对值、命中/躲避次数。',
        '> 伤害是样本专精承受的数值，换专精会有出入；已去掉占本专精血量的百分比。',
        '> 「打断 / 驱散 / 吃控」来自 MDT 快照 `<dungeon>.mdt.lua`，并用样本日志核对能否打断：冲突时以日志为准，格内写明证据。MDT 没数据 ≠ 免控。',
        '> 流程（时长、同场单位、击杀顺序、首次施放、小怪分段）由样本日志推出；场地、走位、开门条件这类日志看不出来的不写。',
        '> 用户只需挑错：数据和印象不符的地方指出来，以日志为准核对后修正。',
        '> 用户确认后改名为 `<dungeon>.md`，删掉本段，并写变更记录。', '',
    ]
    unparsed = 0
    for name in SECTIONS:
        text = files.get(f'{name}.txt')
        if text is None:
            lines += [f'## {name}', '', '（缺少 diag 输出）', '']
            continue
        body = section_one(text)
        if name == 'trash':
            segs = flow.get('trash') or []
            lines += ['## 全本小怪', '']
            if segs:
                lines += [f'- 小怪分段（日志，段 = 开打时已击杀的首领数，只列一半以上场次出现的怪）：']
                lines += [f'  - {x}' for x in segs]
                lines.append('')
            lines += [
                      '| 怪物 | 技能 | ID | 类型 | 伤害 | 中 / 免疫 / 未中 | 出现场次 | 打断 / 驱散 / 吃控 |',
                      '|---|---|---|---|---|---|---|---|']
            for raw in body.splitlines():
                m = TRASH_MECH.match(raw)
                if not m:
                    unparsed += raw.strip().startswith('- **')
                    continue
                g = m.groupdict()
                lines.append(f"| {g['mob']} | {g['skill']} | {g['ids']} | {g['kind']} | {neutral_damage(g['dmg'])} "
                             f"| {g['hit']} / {g['imm']} / {g['miss']} | {g['cov']}/{g['n']} | {mdt_cell(mdt_table, g['ids'], logs)} |")
        else:
            title = boss_title(text, name)
            lines += [f'## 老 {name[-1]}：{title}', '']
            for x in flow.get(name[-1]) or []:
                lines.append(f'- {x}')
            if flow.get(name[-1]):
                lines.append('')
            lines += [
                      '| 技能 | 施放者 | ID | 目标形态 | 周期 | 伤害 | 共 / 中 / 免疫 / 躲避未中 | 打断 / 驱散 / 吃控 |',
                      '|---|---|---|---|---|---|---|---|']
            for raw in body.splitlines():
                m = BOSS_MECH.match(raw)
                if not m:
                    unparsed += raw.strip().startswith('- **') or raw.strip().startswith('  - **')
                    continue
                g = m.groupdict()
                skill = re.sub(r'^\[小怪:[^\]]+\]\s*', '', g['name'])
                lines.append(f"| {skill} | {g['caster']} | {g['ids']} | {g['shape'].strip()} | {g['period'].strip()} "
                             f"| {neutral_damage(g['dmg'])} | {g['waves']} / {g['hit']} / {g['imm']} / {g['miss']} | {mdt_cell(mdt_table, g['ids'], logs)} |")
        lines.append('')
    lines += ['## 变更记录', '', '- <日期> 由 check_claims.py mechanics 生成草稿。']
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'PASS 写出 {rel(out)}' + (f'（{unparsed} 行 ① 条目没能解析，请人工核对 diag 原文）' if unparsed else ''))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('src', help='guides/v3/<dungeon>/drafts/<spec> 目录（含 runs.json 与 *.md）')
        p.add_argument('--diag-dir', help='diag 落盘目录，默认 <src>/diag')
        return p

    p = common(sub.add_parser('dump', help='落盘 boss1-4 + trash 诊断（默认串行）'))
    p.add_argument('--class-json')
    p.add_argument('--wowhead', action='store_true', help='带 Wowhead 说明（默认 --no-wowhead）')
    p.add_argument('--jobs', type=int, default=1,
                   help='同时跑几节（默认 1：各节共用整场查询，串行时后几节全命中缓存；并发高还会触发 WCL 的 IP 限流）')
    p.add_argument('--only', help='只跑部分，如 boss2,trash')

    p = common(sub.add_parser('inspect', help='跑 diag inspect 并落盘'))
    p.add_argument('--class-json')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--boss')
    g.add_argument('--trash', action='store_true')
    p.add_argument('--ability', required=True)
    p.add_argument('--only-hit', action='store_true')
    p.add_argument('--only-bare', action='store_true')
    p.add_argument('--limit', type=int)

    p = common(sub.add_parser('check', help='机械闸门：逐条 PASS/FAIL'))
    p.add_argument('--claims', help='claims.json 路径，默认 <src>/claims.json')
    p.add_argument('--banned', action='append', help='禁用说法文件（每行一个正则，# 开头为注释），可重复')
    p.add_argument('--strict-numbers', action='store_true', help='稿件里的数字原文在 diag 中找不到也算 FAIL')
    p.add_argument('--allow-no-claims', action='store_true', help='没有 claims.json 时只记 WARN（用于旧稿抽检）')
    p.add_argument('--show', type=int, default=8, help='每份稿件最多列出几个未命中数字')
    p.add_argument('--quiet', action='store_true', help='不打印 PASS 行')

    p = common(sub.add_parser('merge', help='拼接 guide.md'))
    p.add_argument('--spec-name', help='页眉里的专精中文名，如 兽王猎')
    p.add_argument('--header', help='页眉文件（覆盖自动生成）')
    p.add_argument('--out', help='输出路径，默认 <src>/guide.md')
    p.add_argument('--diff', action='store_true', help='只比较不写入，一致则退出码 0')

    p = common(sub.add_parser('mechanics', help='从 diag ① 抽副本机制卡骨架'))
    p.add_argument('--out', help='输出路径，默认 guides/tools/mechanics/<dungeon>.draft.md')
    p.add_argument('--force', action='store_true', help='覆盖已存在的输出')
    p.add_argument('--no-log', action='store_true', help='不用样本日志核对 MDT（离线时用）')
    p.add_argument('--mdt', help='MDT 快照，默认 guides/tools/mechanics/<dungeon>.mdt.lua（不存在就留 <待补>）')

    args = ap.parse_args(argv)
    return {'dump': cmd_dump, 'inspect': cmd_inspect, 'check': cmd_check, 'merge': cmd_merge,
            'mechanics': cmd_mechanics}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
