"""render（报告 JSON → HTML/Markdown）的校验与排版；离线，不取图标。"""
import copy
import json
import unittest
from pathlib import Path

import support  # noqa: F401  (把 scripts 目录加进 sys.path)
from wclr import report as R

EXAMPLES = Path(__file__).resolve().parents[1] / '.claude' / 'skills' / 'mplus-tactics' / 'references'


def load(name):
    return json.loads((EXAMPLES / name).read_text(encoding='utf-8'))


class ReportTests(unittest.TestCase):
    def test_examples_pass(self):
        for name in ('example-class.json', 'example-team.json'):
            self.assertEqual(R.validate(load(name)), [], name)

    def test_rules(self):
        d = load('example-class.json')
        bad = copy.deepcopy(d)
        bad['route'][0]['rows'][0]['why'] = '5 次里 3 次有效'
        bad['route'][0]['rows'][0]['tags'] = ['魔法', '随便']
        bad['route'][0]['rows'][0]['action']['type'] = '神秘'
        bad['highlights'][0]['note'] = '免疫 ×8，伴随 4.9 倍'
        bad['toolbox'][0]['usage'] = 5
        errs = '\n'.join(R.validate(bad))
        for frag in ('不能有数字', "标签 '随便'", "type '神秘'", "'×'", "'伴随'", '常用度'):
            self.assertIn(frag, errs)
        team = load('example-team.json')
        del team['route'][0]['rows'][0]['who']
        self.assertTrue(any('who' in x for x in R.validate(team)))

    def test_appendix_and_meta_may_hold_evidence(self):
        d = load('example-class.json')
        d['appendix']['evidence'][0]['evidence'] = '伴随 ×9（4.9 倍）'
        d['meta'][0]['value'] = '奥术 ×2'
        self.assertEqual(R.validate(d), [])

    def test_render_html(self):
        d = load('example-class.json')
        html = R.render_html(d, icons={342245: 'data:image/jpeg;base64,AAAA'}, tooltips=False)
        self.assertTrue(html.startswith('<!doctype html>'))
        self.assertIn('--accent:#3FC7EB', html)
        self.assertIn('<span class="cls">法师</span>', html)
        self.assertIn('spell=342245', html)
        self.assertIn('data:image/jpeg;base64,AAAA', html)
        self.assertIn('首领 1 · 拉维', html)
        self.assertIn('<details', html)
        self.assertNotIn('tooltips.js', html)
        self.assertNotIn('<th>谁</th>', html)
        team = R.render_html(load('example-team.json'), tooltips=False)
        self.assertIn('<th>谁</th>', team)

    def test_render_md(self):
        md = R.render_md(load('example-class.json'))
        self.assertIn('## ⭐ 必会的几招', md)
        self.assertIn('| 机制 | 信号 | 按什么 | 为什么 |', md)
        self.assertIn('●●○', md)


if __name__ == '__main__':
    unittest.main()
