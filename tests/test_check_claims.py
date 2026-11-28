"""check_claims.py 机械闸门的离线测试；合成稿件与 diag 输出，禁止网络。"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  （把 guides/tools 加进 sys.path）
import check_claims as cc

URL = 'https://www.warcraftlogs.com/reports/AbCdEf1234567890#fight=1&view=events&start=1000&end=7000'
FOREIGN = 'https://www.warcraftlogs.com/reports/ZzZzZz9999999999#fight=1&view=events&start=1000&end=7000'
LINK = f'[r01@0:01.0]({URL})'
HEAD = '| 样本@时间 | 玩家 | 技能键 | 状态 | 队中/deb | 伤害 | 起手→剩血 | 减伤/其他覆盖 | 就绪牌(*大牌) | ±2s叠伤 | 窗内抬血 |'
ROWS = [('hit', '100%→78%', '纯裸吃'), ('hit', '100%→85%', '纯裸吃'),
        ('dodged', '—→—', '纯裸吃'), ('hit', '100%→60%', '优胜劣汰')]

BOSS_TAGS = ['不交', '必交', '交互', '避坑']
TRASH_TAGS = ['不交', '必交', '免疫/清除', '驱散', '控断', '避坑']


def md(title, tags, n_ev):
    rules = [f'{i}. **【{t}】条件**：纯裸吃 2 次中 1 次跌破 80%，最低 78%（{LINK}）。'
             for i, t in enumerate(tags, 1)]
    ev = [f'- *实测背书 {i}*：样本 {LINK}。' for i in range(1, n_ev + 1)]
    return '\n\n'.join([f'## {title}', '> **一句话流程**：开怪→转火→收尾。',
                        '\n'.join(rules), '\n'.join(ev)]) + '\n'


def inspect_txt(scope):
    rows = '\n'.join(f'| {LINK} | 玩家 | 技能 | {s} | 5/5 | 100K | {hp} | {cov} | 优胜劣汰 | 无 | — |'
                     for s, hp, cov in ROWS)
    return (f'$ python3 guides/tools/diag.py inspect --{scope} --ability 111 --only-hit\n'
            f'# 双向反查明细：111（共 {len(ROWS)} 条，按最低剩血升序）\n{HEAD}\n|---|\n{rows}\n')


def claims_for(name, tags):
    out = []
    for i, t in enumerate(tags, 1):
        c = {'rule': i, 'type': t, 'source': f'inspect-{name}.txt', 'ability': ['111']}
        if t in ('不交', '必交'):
            c.update(where={'cover': '纯裸吃', 'status': 'hit'}, m=2, min_hp=78)
        if t == '必交':
            c['where'] = dict(c['where'], remaining_lt=80)
            c['n'] = 1
        if '免疫' in t or '驱散' in t:
            c['links'] = [URL]
        out.append(c)
    return out


class CheckClaimsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name)
        (self.src / 'runs.json').write_text(json.dumps({
            'dungeon': '测试副本', 'class': '测试专精',
            'runs': [{'tag': 'r01', 'code': 'AbCdEf1234567890', 'fid': 1, 'level': 20}]}), encoding='utf-8')
        diag = self.src / 'diag'
        diag.mkdir()
        claims = {}
        for name in cc.SECTIONS:
            tags = TRASH_TAGS if name == 'trash' else BOSS_TAGS
            (self.src / f'{name}.md').write_text(md(name, tags, 3 if name == 'trash' else 2), encoding='utf-8')
            (diag / f'inspect-{name}.txt').write_text(inspect_txt('trash' if name == 'trash' else 'boss 1'), encoding='utf-8')
            claims[name] = claims_for(name, tags)
        self.claims = claims
        self.write_claims()

    def tearDown(self):
        self.tmp.cleanup()

    def write_claims(self):
        (self.src / 'claims.json').write_text(json.dumps(self.claims, ensure_ascii=False), encoding='utf-8')

    def run_check(self, *extra):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cc.main(['check', str(self.src), *extra])
        return code, buf.getvalue()

    def test_clean_sample_passes(self):
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertFalse([l for l in out.splitlines() if l.startswith('FAIL')], out)

    def test_wrong_denominator_fails(self):
        self.claims['boss2'][1]['m'] = 3
        self.write_claims()
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('分母 m=3，明细表为 2', out)

    def test_wrong_min_hp_fails(self):
        self.claims['boss1'][0]['min_hp'] = 60   # 60% 那行不是纯裸吃，不能算进来
        self.write_claims()
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('明细表为 78%', out)

    def test_link_not_in_diag_or_runs_fails(self):
        p = self.src / 'boss3.md'
        p.write_text(p.read_text(encoding='utf-8').replace(URL, FOREIGN, 1), encoding='utf-8')
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('不在 runs.json', out)
        self.assertIn('不在 diag 输出', out)

    def test_uncovered_rule_and_bare_requirement(self):
        self.claims['boss4'] = [c for c in self.claims['boss4'] if c['rule'] != 4]
        self.claims['boss4'][1]['where'] = {'status': 'hit'}     # 必交但没限定纯裸吃
        self.write_claims()
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('boss4.md#4: 口诀没有对应的 claims 条目', out)
        self.assertIn('必交/不交须基于纯裸吃样本', out)

    def test_banned_phrase_and_length(self):
        p = self.src / 'trash.md'
        p.write_text(p.read_text(encoding='utf-8') + '\n搬球走廊' + '字' * 3300, encoding='utf-8')
        banned = self.src / 'banned.txt'
        banned.write_text('# 注释\n搬球\n', encoding='utf-8')
        code, out = self.run_check('--banned', str(banned))
        self.assertEqual(code, 1)
        self.assertIn('出现禁用说法 /搬球/', out)
        self.assertIn('上限 3200', out)

    def test_merge_joins_sections_verbatim(self):
        head = self.src / 'header.md'
        head.write_text('# 页眉\n\n> 说明', encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cc.main(['merge', str(self.src), '--header', str(head)]), 0)
            self.assertEqual(cc.main(['merge', str(self.src), '--header', str(head), '--diff']), 0)
        text = (self.src / 'guide.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('# 页眉\n\n> 说明\n\n---\n\n## boss1'))
        self.assertEqual(text.count('\n\n---\n\n'), 5)


if __name__ == '__main__':
    unittest.main()


class MechanicsDraftTests(unittest.TestCase):
    BOSS = (
        "# 塞塔里斯神庙 · 米利克萨（encounter 2125）· 猎人（野兽控制） 极简五维诊断\n"
        "## ① 机制速览（按敌方关键技能施放主键）\n"
        "- **毒蛇风暴**（米利克萨, ID:1293048）：全队AOE+DoT | 周期 ~98s | 纯裸吃中位 1.65M (156%HP)(9跳合) | 共43波（中38 / 免疫0 / 躲避未中5）\n"
        "- *（合波带入小怪威胁技）*：\n"
        "  - **[小怪:风暴飞蛇] 萦绕风暴**（风暴飞蛇, ID:1289589/1293133）：单点1人(最高3)+DoT | 周期 ~8.5s | 本专精0掉血（全队命中中位 941K ≈89%本专精HP） | 共75波（中1 / 免疫0 / 躲避未中74）\n"
        "## ② 手牌预算账\n"
    )
    TRASH = (
        "# 塞塔里斯神庙 · 全本小怪（非 Boss）\n"
        "## ① 高频致死 / 高伤小怪技速览\n"
        "- **暴怒云气 · 释放电荷**（ID:1293475，直伤）：纯裸吃中位 796K (68%HP) | 中109 / 免疫7 / 未中0（覆盖15/15场） | **2s内死2次**\n"
        "## ② 小怪手牌与控断预算账\n"
    )

    def test_draft_is_spec_neutral(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'saitalisi-v3'
            (src / 'diag').mkdir(parents=True)
            (src / 'diag' / 'boss2.txt').write_text(self.BOSS, encoding='utf-8')
            (src / 'diag' / 'trash.txt').write_text(self.TRASH, encoding='utf-8')
            out = Path(d) / 'draft.md'
            with contextlib.redirect_stdout(io.StringIO()):
                code = cc.main(['mechanics', str(src), '--out', str(out)])
            self.assertEqual(code, 0)
            text = out.read_text(encoding='utf-8')
        self.assertIn('## 老 2：米利克萨', text)
        self.assertIn('| 毒蛇风暴 | 米利克萨 | 1293048 | 全队AOE+DoT | ~98s | 裸吃中位 1.65M（9 跳合计） | 43 / 38 / 0 / 5 |', text)
        self.assertIn('| 萦绕风暴 | 风暴飞蛇 | 1289589/1293133 |', text)
        self.assertIn('样本专精未中招；全队命中中位 941K', text)
        self.assertIn('| 暴怒云气 | 释放电荷 | 1293475 | 直伤 | 裸吃中位 796K | 109 / 7 / 0 | 15/15 |', text)
        self.assertNotIn('%HP', text)
        self.assertNotIn('2s内死', text)

    def test_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'x-v3'
            (src / 'diag').mkdir(parents=True)
            (src / 'diag' / 'trash.txt').write_text(self.TRASH, encoding='utf-8')
            out = Path(d) / 'draft.md'
            out.write_text('keep', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cc.main(['mechanics', str(src), '--out', str(out)]), 1)
            self.assertEqual(out.read_text(encoding='utf-8'), 'keep')
