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


GUIDE_DIRECTORY = Path(__file__).resolve().parents[1] / 'guides/warrior-arms'
sys.path.insert(0, str(GUIDE_DIRECTORY))
import build as warrior_build
from guides import GUIDES
from talents import decode, encode, selections
sys.path.pop(0)


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


class WarriorGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = warrior_build.read(warrior_build.SOURCE / 'arms-tree.json')
        cls.tooltips = warrior_build.read(warrior_build.SOURCE / 'spells.json')
        cls.style = (warrior_build.SOURCE / 'design.css').read_text() + warrior_build.EXTRA_CSS

    def test_all_twenty_four_import_strings_round_trip(self):
        for name in warrior_build.DUNGEONS:
            directory = warrior_build.SOURCE / name
            selected = warrior_build.read(directory / 'selected.json')
            self.assertEqual(len(selected), 3)
            self.assertEqual(len({row['url'] for row in selected}), 3)
            for row in selected:
                with self.subTest(dungeon=name, player=row['player']):
                    record = warrior_build.read(directory / row['file'])
                    self.assertEqual(record['player']['spec'], 'Arms')
                    self.assertEqual(record['player']['cls'], 'Warrior')
                    chosen = selections(record['combatant'])
                    self.assertIn(123390, {talent['id'] for talent in chosen.values()})
                    encoded = encode(self.tree, chosen)
                    self.assertEqual(set(decode(self.tree, encoded)), set(chosen))
                    self.assertEqual(len(decode(self.tree, encoded)), len(chosen))

    def test_invalid_import_data_is_rejected(self):
        with self.assertRaises(ValueError):
            decode(self.tree, 'A')
        with self.assertRaises(ValueError):
            encode(dict(self.tree, specId=72), {})
        with self.assertRaises(ValueError):
            encode(self.tree, {-1: {'id': -1, 'rank': 1}})
        with self.assertRaises(ValueError):
            encode(self.tree, {90326: {'id': 112183, 'rank': 9}})

    def test_guides_follow_skill_format(self):
        self.assertTrue(GUIDES)
        self.assertLessEqual(set(GUIDES), set(warrior_build.DUNGEONS))
        for name, guide in GUIDES.items():
            with self.subTest(dungeon=name):
                page = warrior_build.render_guide(name, guide, self.style, self.tooltips, self.tree)
                parser = GuideParser()
                parser.feed(page)
                self.assertEqual(parser.chapters, [f'chapter-{index}' for index in range(1, 8)])
                self.assertEqual(len(parser.references), 3)
                self.assertEqual(page.count('<article class="mo">'), 4)
                self.assertIn('class="tl-card"', page)
                self.assertIn('class="tl-scroll"', page)
                self.assertIn('class="band boss"', page)
                self.assertIn('class="mk up', page)
                self.assertIn('class="mk dn', page)
                self.assertNotRegex(page, r'class="stem"></span><img class="ic')
                self.assertIn('class="combo"', page)
                self.assertEqual(page.count('<li>'), len(guide['combo']['steps']))
                self.assertNotIn('class="bars"', page)
                self.assertIn('fonts.googleapis.com/css2?family=Noto+Serif+SC', page)
                self.assertNotIn('planline', page)
                self.assertNotIn('flow-step', page)
                self.assertNotIn('chapter-nav', page)
                self.assertGreaterEqual(len(parser.images), 35)
                self.assertTrue(all(image.startswith('data:image/jpeg;base64,') for image in parser.images))
                self.assertNotRegex(page, r'\{\{(?:I:|T:|TALENT)')
                self.assertIn('id="copy-btn"', page)
                self.assertIn('role="status"', page)
                self.assertNotIn('三名都这样打', page)
                self.assertNotIn('日志里', page)
                imported = re.search(r'<code id="talent-code">([^<]+)</code>', page).group(1)
                self.assertTrue(decode(self.tree, imported))
                for stage in guide['route']:
                    self.assertTrue(stage['rows'])
                    for row in stage['rows']:
                        self.assertTrue(all(row[key] for key in ['mechanic', 'signal', 'skills', 'why']))
                        self.assertLessEqual(len(row['signal']), 20)
                        self.assertLessEqual(len(row['why']), 60)
                self.assertLessEqual(sum(bool(stage['note']) for stage in guide['route']), 1)

    def test_duplicate_names_resolve_to_the_actual_dungeon_spell(self):
        mapping = warrior_build.read(warrior_build.SOURCE / '毒牙祭坛/mechanics.json')
        self.assertEqual(warrior_build.mechanic_id('毒伤', mapping, self.tooltips), 1289416)
        self.assertEqual(warrior_build.mechanic_id('毒伤', mapping, self.tooltips, debuff=True), 1307571)
        mapping = warrior_build.read(warrior_build.SOURCE / '塞塔里斯神庙/mechanics.json')
        self.assertEqual(warrior_build.mechanic_id('阵风', mapping, self.tooltips), 1288457)

    def test_mechanic_specific_safety_guards(self):
        eye = next(row for row in GUIDES['红玉新生法池']['debuffs'] if row[0] == '风暴之眼')
        self.assertEqual(eye[2], '离开即消失')
        self.assertIn('冰霜地雷', str(GUIDES['红玉新生法池']['debuffs']))

    def test_ruby_pools_uses_the_recorded_warrior_techniques(self):
        guide = GUIDES['红玉新生法池']
        rows = {(row['mechanic'], tuple(row['skills'])) for stage in guide['route'] for row in stage['rows']}
        self.assertIn(('火热冲击', (355, 23920)), rows)
        self.assertIn(('雷霆冲击', (355, 23920)), rows)
        self.assertIn(('冰霜过载', (384110,)), rows)
        self.assertIn(('暴风骤雨之盾', (384110,)), rows)
        self.assertIn(('燃焰弹幕', (46968, 107570)), rows)
        leaps = [row['mechanic'] for stage in guide['route'] for row in stage['rows'] if 6544 in row['skills']]
        self.assertEqual(set(leaps), {'燃尽'})
        page = warrior_build.render_guide('红玉新生法池', guide, self.style, self.tooltips, self.tree)
        imported = re.search(r'<code id="talent-code">([^<]+)</code>', page).group(1)
        nodes = {node['id']: node for group in ['classNodes', 'specNodes', 'heroNodes', 'subTreeNodes'] for node in self.tree[group]}
        entries = {entry['id']: entry.get('spellId') for node in nodes.values() for entry in node['entries']}
        spells = {entries.get(entry) for _, entry in decode(self.tree, imported).values()}
        self.assertIn(384110, spells)
        self.assertIn('<span class="plus">+</span>', page)
        self.assertIn('class="who"', page)

    def test_original_design_is_not_overridden(self):
        self.assertNotRegex(warrior_build.EXTRA_CSS, r'\.(?:lede|row|mo|finding|tool|wrap|tbl-wrap)\b')
        original = (GUIDE_DIRECTORY.parent / 'rogue/sources/rogue.src.html').read_text()
        original_css = re.search(r'<style>(.*?)</style>', original, re.S).group(1)
        original_css = re.sub(r'/\*.*?\*/', '', original_css, flags=re.S)
        self.assertEqual(original_css.strip(), (warrior_build.SOURCE / 'design.css').read_text().strip())

    def test_offline_build_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with patch('urllib.request.urlopen', side_effect=AssertionError('Offline rebuild must not access the network')):
                with contextlib.redirect_stdout(io.StringIO()):
                    first = warrior_build.build(output)
                    original = {path.name: path.read_bytes() for path in output.glob('*.html')}
                    second = warrior_build.build(output)
            self.assertEqual(len(first), len(GUIDES))
            self.assertEqual(first, second)
            self.assertEqual(len(original), len(GUIDES) + 1)
            self.assertEqual(original, {path.name: path.read_bytes() for path in output.glob('*.html')})


if __name__ == '__main__':
    unittest.main()
