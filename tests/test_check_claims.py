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


class MechanicsMdtTests(unittest.TestCase):
    LUA = '''
MDT.dungeonEnemies[dungeonIndex] = {
  [1] = {
    ["name"] = "Poisonous Viper";
    ["id"] = 134389;
    ["characteristics"] = {
      ["Taunt"] = true;
      ["Stun"] = true;
    };
    ["spells"] = {
      [1308148] = {
        ["interruptible"] = true;
        ["poison"] = true;
      };
    };
  };
  [2] = {
    ["name"] = "Agitated Nimbus";
    ["id"] = 135000;
    ["characteristics"] = {
      ["Taunt"] = true;
    };
    ["spells"] = {
      [1293475] = {
      };
    };
  };
};
'''

    def test_mdt_column(self):
        trash = ("# x · 全本小怪\n## ① 速览\n"
                 "- **剧毒蝰蛇 · 细胞毒素**（ID:1308148，DoT）：纯裸吃中位 607K (48%HP) | 中92 / 免疫0 / 未中262（覆盖15/15场）\n"
                 "- **暴怒云气 · 释放电荷**（ID:1293475，直伤）：纯裸吃中位 822K (64%HP) | 中113 / 免疫4 / 未中0（覆盖15/15场）\n"
                 "- **某怪 · 某技能**（ID:999999，直伤）：纯裸吃中位 1K (1%HP) | 中1 / 免疫0 / 未中0（覆盖1/15场）\n"
                 "## ② x\n")
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'x-v3'
            (src / 'diag').mkdir(parents=True)
            (src / 'diag' / 'trash.txt').write_text(trash, encoding='utf-8')
            lua = Path(d) / 'x.mdt.lua'
            lua.write_text(self.LUA, encoding='utf-8')
            out = Path(d) / 'draft.md'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cc.main(['mechanics', str(src), '--out', str(out), '--mdt', str(lua)]), 0)
            text = out.read_text(encoding='utf-8')
        self.assertIn('| 可打断；驱散：中毒；吃控：晕（MDT） |', text)
        self.assertIn('| 不可打断；不吃硬控（MDT） |', text)
        self.assertIn('| MDT 无此技能 |', text)


class MdtLogConflictTests(unittest.TestCase):
    from collections import Counter as _C
    TABLE = {1: {'interruptible': True, 'dispel': set(), 'cc': {'Stun'}},
             2: {'interruptible': False, 'dispel': set(), 'cc': None}}

    def logs(self, casts=0, begins=0, kicked=0, sid=1):
        C = self._C
        return {'casts': C({sid: casts}), 'begins': C({sid: begins}), 'kicked': C({sid: kicked}), 'n': 15}

    def test_log_overrides_mdt_interruptible(self):
        cell = cc.mdt_cell(self.TABLE, '1', self.logs(casts=354))
        self.assertTrue(cell.startswith('不可打断'))
        self.assertIn('以日志为准：354 次施放、0 次读条、0 次被打断', cell)

    def test_too_few_casts_keeps_mdt(self):
        self.assertTrue(cc.mdt_cell(self.TABLE, '1', self.logs(casts=5)).startswith('可打断'))

    def test_channel_that_got_kicked_keeps_interruptible(self):
        cell = cc.mdt_cell(self.TABLE, '1', self.logs(casts=40, kicked=3))
        self.assertTrue(cell.startswith('可打断'))

    def test_log_kicks_override_mdt_uninterruptible(self):
        cell = cc.mdt_cell(self.TABLE, '2', self.logs(kicked=4, sid=2))
        self.assertTrue(cell.startswith('可打断'))
        self.assertIn('MDT 标不可打断', cell)

    def test_missing_in_mdt_but_kicked(self):
        self.assertEqual(cc.mdt_cell(self.TABLE, '9', self.logs(kicked=2, sid=9)),
                         '可打断（日志：被打断 2 次；MDT 无此技能）')


class LogFlowTests(unittest.TestCase):
    def test_flow_from_fake_logs(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import diag

        def pull(enc, start, end, mobs, bosses=(), kill=True):
            return NS(encounter_id=enc, start=start, end=end, dur=end - start, kill=kill,
                      mobs=list(mobs), boss_names=list(bosses), is_boss=enc > 0)
        boss1 = pull(1, 100_000, 340_000, [('A', 1), ('B', 1), ('小怪', 2)], bosses=('A', 'B'))
        trash = [pull(0, 0, 50_000, [('游荡三叶虫', 4)]), pull(0, 400_000, 450_000, [('宝珠守望者', 2)])]
        names = {1: 'A', 2: 'B', 3: '小怪'}
        run = NS(pulls=trash + [boss1], actor_name=lambda i, inst=None: names.get(i, '?'))
        casts = [{'abilityGameID': 11, 'type': 'cast', 'timestamp': 105_000, 'ability': {'name': '阵风'}},
                 {'abilityGameID': 12, 'type': 'begincast', 'timestamp': 110_000, 'ability': {'name': '电闪雷鸣'}}]
        deaths = [{'targetID': 2, 'timestamp': 300_000}, {'targetID': 1, 'timestamp': 340_000}]
        samples = [NS(code='c%d' % i, fid=1) for i in range(3)]
        with mock.patch.object(diag, 'Client'), \
                mock.patch.object(diag, 'load_samples', return_value=({}, samples)), \
                mock.patch.object(diag, 'load_run', return_value=run), \
                mock.patch.object(diag, 'find_boss_pulls', return_value=[boss1]), \
                mock.patch.object(diag, 'full_events',
                                  side_effect=lambda r, kind, **k: casts if kind == 'Casts' else deaths):
            flow = cc.log_flow('x', {'1': {11, 12}})
        text = '\n'.join(flow['1'])
        self.assertIn('中位时长 4:00（3/3 场）', text)
        self.assertIn('击杀顺序（中位首次死亡时刻）：B +3:20 → A +4:00', text)
        self.assertIn('开怪后首次施放（中位）：阵风 +0:05 → 电闪雷鸣 +0:10', text)
        self.assertEqual(flow['trash'], ['老 1 之前：游荡三叶虫 ×4（3/3 场）', '老 1 → 老 2：宝珠守望者 ×2（3/3 场）'])
