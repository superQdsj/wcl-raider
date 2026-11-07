import contextlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.claude/skills/mplus-class-guide/scripts'
sys.path.insert(0, str(SCRIPTS))
import build as guide_build
from guidelib import ASSETS, tree_for
from talents import decode, encode, selections
sys.path.pop(0)

# 每个有 profile.py 的职业目录都按同一套规则检查
SPECS = sorted(path.parent.name for path in (ROOT / 'guides').glob('*/profile.py'))


class GuideParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chapters = []
        self.references = []
        self.images = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'section':
            self.chapters.append(attributes.get('id'))
        if tag == 'a' and '/reports/' in attributes.get('href', ''):
            self.references.append(attributes['href'])
        if tag == 'img':
            self.images.append(attributes.get('src'))


class ClassGuideTests(unittest.TestCase):
    def specs(self):
        """依次切换到每个职业目录，产出 (目录名, GUIDES, 天赋树, 样式)。"""
        for spec in SPECS:
            guides = guide_build.configure(spec)
            tree = tree_for(guide_build.P.SPEC_ID)
            style = guide_build.page_style()
            with self.subTest(spec=spec):
                try:
                    yield spec, guides, tree, style
                except GeneratorExit:  # 循环体里断言失败时生成器被关闭，不要再报成第二个错误
                    return

    def test_every_collected_import_string_round_trips(self):
        for spec, _, tree, _ in self.specs():
            runs = guide_build.DB.execute('SELECT dungeon, player_name, combatant FROM run').fetchall()
            self.assertTrue(runs)
            for run in runs:
                chosen = selections(json.loads(run['combatant']))
                self.assertIn(guide_build.P.HERO_ENTRY, {talent['id'] for talent in chosen.values()}, run['player_name'])
                encoded = encode(tree, chosen)
                self.assertEqual(len(decode(tree, encoded)), len(chosen))

    def test_invalid_import_data_is_rejected(self):
        guide_build.configure('warrior-arms')
        tree = tree_for(guide_build.P.SPEC_ID)
        with self.assertRaises(ValueError):
            decode(tree, 'A')
        with self.assertRaises(ValueError):  # 别的专精的字符串不能用本专精的树解开
            decode(dict(tree, specId=72), encode(tree, {}))
        with self.assertRaises(ValueError):
            encode(tree, {-1: {'id': -1, 'rank': 1}})
        with self.assertRaises(ValueError):
            encode(tree, {90326: {'id': 112183, 'rank': 9}})

    def test_guides_follow_skill_format(self):
        for spec, guides, tree, style in self.specs():
            for name, guide in guides.items():
                page = guide_build.render_guide(name, guide, style, tree)
                parser = GuideParser()
                parser.feed(page)
                self.assertEqual(parser.chapters, [f'chapter-{index}' for index in range(1, 8)])
                self.assertEqual(len(parser.references), 3)
                self.assertEqual(page.count('<article class="mo">'), 4)
                for marker in ['class="tl-card"', 'class="band boss"', 'class="mk up', 'class="mk dn', 'class="combo"',
                               'fonts.googleapis.com/css2?family=Noto+Serif+SC', 'id="copy-btn"', 'role="status"']:
                    self.assertIn(marker, page)
                self.assertNotRegex(page, r'class="stem"></span><img class="ic')
                self.assertEqual(page.count('<li>'), len(guide['combo']['steps']))
                self.assertGreaterEqual(len(parser.images), 35)
                self.assertTrue(all(image.startswith('data:image/jpeg;base64,') for image in parser.images))
                for banned in ['三名都这样打', '日志里', 'f2d24b', '242,210,75']:  # 证据类文字、盗贼金
                    self.assertNotIn(banned, page)
                imported = re.search(r'<code id="talent-code">([^<]+)</code>', page).group(1)
                self.assertTrue(decode(tree, imported))
                self.assertEqual(len(set(guide['moments'])), 4)
                for stage in guide['route']:
                    self.assertTrue(stage['rows'])
                    self.assertTrue(stage['note'], stage['name'])          # 每段一条提醒，讲取舍
                    self.assertLessEqual(len(stage['note']), 40, stage['note'])
                    self.assertNotRegex(stage['note'], r'仍需|仍要|别等|可尝试', stage['note'])
                    for row in stage['rows']:
                        self.assertTrue(all(row[key] for key in ['mechanic', 'signal', 'skills', 'why']))
                        self.assertLessEqual(len(row['signal']), 20)
                        self.assertLessEqual(len(row['why']), 60)
                        # writing.md「简练」：不打补丁、不用含糊兜底
                        self.assertNotRegex(row['why'], r'仍需|仍要|别等|可尝试|确认', row['why'])
                        for skill in row['skills']:
                            self.assertIn(skill, guide_build.P.SKILLS, f'{skill} 不在 profile.SKILLS 里')

    def test_timeline_groups_big_cooldowns_and_labels_answered_mechanics(self):
        guide_build.configure('warrior-arms')
        tooltips = {'118038': {'name': '剑在人在'}, '97462': {'name': '集结呐喊'}}
        guide = {'timeline_skills': [118038, 97462], 'route': [{'rows': [
            {'mechanic': '甲', 'skills': [118038]}, {'mechanic': '乙', 'skills': [97462]}, {'mechanic': '丙', 'skills': [1]}]}]}

        def use(gid, ts, before=(), active=(), removed=()):
            return {'gid': gid, 'ts': ts, 'time': guide_build.clock(ts), 'before': [[-1.0, g, '读条'] for g in before],
                    'active': list(active), 'applied_after': [], 'hits': {}, 'removed': [[g, 5, False] for g in removed], 'blocked': []}
        record = {'abilities': {'118038': {'name': '剑在人在'}, '97462': {'name': '集结呐喊'}, '900': {'name': '甲'},
                                '901': {'name': '乙'}, '902': {'name': '丙'}}, 'uses': [
            use(118038, 60000, before=[900], active=[902]),     # 甲 是正文写明的应对；丙 只是路线里有
            use(97462, 65000, before=[901]),                    # 5 秒后接集结 → 同一个点，乙 也是写明的应对
            use(118038, 300000, active=[902]),                  # 只伴随 丙
            use(1, 400000, before=[900]),                       # 不是大冷却，不上时间线
        ]}
        markers = guide_build.timeline_markers(guide, record, tooltips)
        self.assertEqual([(label, ids) for _, label, ids, _ in markers], [('甲 + 乙', [118038, 97462]), ('丙', [118038])])
        renamed = guide_build.timeline_markers(dict(guide, timeline_labels={'5:00': None, '1:00': '开怪'}), record, tooltips)
        self.assertEqual([label for _, label, _, _ in renamed], ['开怪'])

    def test_duplicate_mechanic_names_prefer_described_and_debuff_versions(self):
        # 同名机制：按出现次数排序，跳过没有说明的；减益表优先带减益文字的那个版本；显式 ID 覆盖
        tooltips = {'1': {'description': ''}, '2': {'description': '伤害', 'aura': ''}, '3': {'description': '持续', 'aura': '每秒'}}
        mapping = {'毒伤': [1, 2, 3]}
        self.assertEqual(guide_build.mechanic_id('毒伤', mapping, tooltips), 2)
        self.assertEqual(guide_build.mechanic_id('毒伤', mapping, tooltips, debuff=True), 3)
        self.assertEqual(guide_build.mechanic_id('毒伤', mapping, tooltips, explicit=3), 3)

    def test_ruby_pools_uses_the_recorded_warrior_techniques(self):
        guides = guide_build.configure('warrior-arms')
        guide = guides['红玉新生法池']
        eye = next(row for row in guide['debuffs'] if row[0] == '风暴之眼')
        self.assertEqual(eye[2], '离开即消失')
        rows = {(row['mechanic'], tuple(row['skills'])) for stage in guide['route'] for row in stage['rows']}
        for expected in [('火热冲击', (355, 23920)), ('雷霆冲击', (355, 23920)), ('冰霜过载', (384110,)),
                         ('暴风骤雨之盾', (384110,)), ('燃焰弹幕', (46968, 107570))]:
            self.assertIn(expected, rows)
        leaps = [row['mechanic'] for stage in guide['route'] for row in stage['rows'] if 6544 in row['skills']]
        self.assertEqual(set(leaps), {'燃尽'})
        tree = tree_for(guide_build.P.SPEC_ID)
        page = guide_build.render_guide('红玉新生法池', guide, guide_build.page_style(), tree)
        imported = re.search(r'<code id="talent-code">([^<]+)</code>', page).group(1)
        entries = {entry['id']: entry.get('spellId') for group in ['classNodes', 'specNodes', 'heroNodes', 'subTreeNodes']
                   for node in tree[group] for entry in node['entries']}
        self.assertIn(384110, {entries.get(entry) for _, entry in decode(tree, imported).values()})
        self.assertIn('<span class="plus">+</span>', page)
        self.assertIn('class="who"', page)

    def test_original_design_is_not_overridden(self):
        self.assertNotRegex(guide_build.EXTRA_CSS, r'\.(?:lede|row|mo|finding|tool|wrap|tbl-wrap)\b')
        original = (ROOT / 'guides/rogue/sources/rogue.src.html').read_text()
        original_css = re.sub(r'/\*.*?\*/', '', re.search(r'<style>(.*?)</style>', original, re.S).group(1), flags=re.S)
        self.assertEqual(original_css.strip(), (ASSETS / 'design.css').read_text().strip())

    def test_offline_build_is_reproducible(self):
        for spec, guides, _, _ in self.specs():
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)
                with patch('urllib.request.urlopen', side_effect=AssertionError('Offline rebuild must not access the network')):
                    with contextlib.redirect_stdout(io.StringIO()):
                        first = guide_build.build(spec, output)
                        original = {path.name: path.read_bytes() for path in output.glob('*.html')}
                        second = guide_build.build(spec, output)
                self.assertEqual(len(first), len(guides))
                self.assertEqual(first, second)
                self.assertEqual(len(original), len(guides) + 1)
                self.assertEqual(original, {path.name: path.read_bytes() for path in output.glob('*.html')})


if __name__ == '__main__':
    unittest.main()
