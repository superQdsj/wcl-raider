"""check.py 篇幅与精炼度门禁回归测试（离线）。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "guides" / "tools"))

import check  # noqa: E402


class CheckConcisenessTests(unittest.TestCase):
    def test_duya_sample_has_zero_errors_and_warnings(self):
        sample_dir = ROOT / "guides" / "rogue" / "sources" / "duya-sample"
        fails, warns = check.check_page(sample_dir / "sample.html", sample_dir, published=False)
        self.assertEqual(fails, [])
        self.assertEqual(warns, [])

    def test_flags_verbose_why_rhythm_average_and_crammed_title(self):
        sample_dir = ROOT / "guides" / "rogue" / "sources" / "duya-sample"
        sample_html = sample_dir / "sample.html"
        long_rhythm = "节奏说明" * 35  # 140 chars > 130
        long_why = "详细边界推演" * 16  # 96 chars > 80
        long_step_why = "复杂步骤说明" * 20  # 120 chars > 110
        body = f"""<body>
<section id="route">
  <article class="stop trash" id="s1">
    <div class="rhythm"><span class="lbl">节奏</span>{long_rhythm}</div>
    <div class="rows">
      <div class="row must">
        <div class="mech"><div><div class="n"><span class="badge-must">必做</span>甲 / 乙 / 丙 / 丁</div></div></div>
        <div class="why">{long_why}</div>
      </div>
      <div class="row step">
        <div class="mech"><div><div class="n">步骤一</div></div></div>
        <div class="why">{long_step_why}</div>
      </div>
    </div>
  </article>
</section>
</body>"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            (src / "body.part").write_text(body, encoding="utf-8")
            (src / "NOTES.md").write_text(
                "## 重建 build.py\n## 删掉的低样本\n## 天赋 enc.py\n## 补查 wcl.py\n",
                encoding="utf-8",
            )
            _, warns = check.check_page(sample_html, src, published=False)

        joined = "\n".join(warns)
        self.assertIn("Verbose .rhythm (140 chars > 130)", joined)
        self.assertIn("Overly crammed row title '甲 / 乙 / 丙 / 丁'", joined)
        self.assertIn("Verbose .why in '甲 / 乙 / 丙 / 丁' (96 chars > 80)", joined)
        self.assertIn("Verbose .why in '步骤一' (120 chars > 110)", joined)
        self.assertIn("High average .why length across #route (108.0 chars > 48", joined)


if __name__ == "__main__":
    unittest.main()
