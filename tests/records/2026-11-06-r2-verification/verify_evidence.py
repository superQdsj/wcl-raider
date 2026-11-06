"""Check saved outputs; reproducing a known issue does not mean it is fixed."""
import hashlib
import json
from pathlib import Path
import re


OUTPUT = Path(__file__).resolve().parent
REPLAY = OUTPUT / 'archival-replay'
ROOT = OUTPUT.parents[2]
results = []


def text(name):
    return (REPLAY / f'{name}.stdout.md').read_text(encoding='utf-8')


def check(label, observed, kind, evidence):
    results.append(dict(label=label, observed=bool(observed), kind=kind, evidence=evidence))


score = text('eu12-score-judgments')
judgments = json.loads((REPLAY / 'historical-sol-judgments.json').read_text(encoding='utf-8'))
deaths = text('eu12-deaths-full')
pulls = text('eu12-pulls')
interrupts = text('eu12-interrupts')
damage = text('eu12-damage')
detail = text('eu12-damage-ability270928')
check('eu12-all-16-deaths-expanded',
      len(re.findall(r'^### #\d+ ', deaths, re.MULTILINE)) == 16 and '已截断' not in deaths,
      'functional_check', 'eu12-deaths-full.stdout.md')
check('default-deaths-truncation-explicit', '输出已截断' in text('eu12-deaths'),
      'functional_check', 'eu12-deaths.stdout.md')
check('eu11-timeout-not-abandoned', '超时完成' in text('eu11-overview'),
      'functional_check', 'eu11-overview.stdout.md')
check('eu11-inferred-five-second-penalty', '10 × 5 秒' in text('eu11-overview'),
      'functional_check', 'eu11-overview.stdout.md')
check('eu12-inferred-fifteen-second-penalty', '16 × 15 秒' in text('eu12-overview'),
      'functional_check', 'eu12-overview.stdout.md')
check('cn24-inferred-fifteen-second-penalty', '3 × 15 秒' in text('cn24-overview'),
      'functional_check', 'cn24-overview.stdout.md')
check('R2-S1-role-exclusion-still-perfect-score',
      all('tank' not in entry.get('roles', []) for entry in judgments['avoidable'])
      and '| Xervdh(恶魔猎手-复仇) | 坦克 | 10.0 | 10.0 | 10.0 | 10.0 | N/A | 10.0 |' in score,
      'known_issue_reproduced', 'historical-sol-judgments.json; eu12-score-judgments.stdout.md')
check('R2-S2-unqualified-cooldown-inference-retained',
      '就一定不在冷却' in (ROOT / '.claude/skills/mplus-review/references/playbook.md').read_text(),
      'known_document_issue_confirmed', '.claude/skills/mplus-review/references/playbook.md')
check('R2-S3-effective-trash-progress-between-boss-attempts',
      re.search(r'^\| 9 \|.*5\.6%', pulls, re.MULTILINE)
      and re.search(r'^\| 10 \|.*6\.7%', pulls, re.MULTILINE),
      'known_issue_supporting_evidence', 'eu12-pulls.stdout.md')
check('R2-S4-unknown-death-still-deducted',
      judgments['deaths']['10']['cause'] == 'unknown'
      and 'Ysavia**（有效权重 65%）：生存：#10 12:06 未能核实 −1.5' in score,
      'known_issue_reproduced', 'historical-sol-judgments.json; eu12-score-judgments.stdout.md')
check('R2-S5-team-median-and-unmatched-success-ratio-still-scored',
      '非治疗中位数 9.0' in score and '4/7（<75% −0.5）' in score,
      'known_issue_reproduced', 'eu12-score-judgments.stdout.md')
check('R2-S6-unnormalized-candidates-retained', '【未归一化' in score,
      'known_issue_supporting_evidence', 'eu12-score-judgments.stdout.md; candidates are not proof of avoidability')
check('R2-S7-incomplete-usage-review-still-nine',
      judgments['usage']['Hêll']['misses'] == []
      and 'Hêll(萨满祭司-增强) | 输出 | 10.0 | 10.0 | 10.0 | 8.6 | 9.0 | 9.6' in score,
      'known_issue_reproduced', 'historical-sol-judgments.json; eu12-score-judgments.stdout.md')
check('R2-S7-global-and-critical-window-differ',
      '| 关键打断 | 9.2 |' in score and '打断 2（40%），读完 3（60%）' in text('eu12-interrupts-pull8'),
      'known_issue_supporting_evidence', 'eu12-score-judgments.stdout.md; eu12-interrupts-pull8.stdout.md')
check('R2-S8-raw-zero-percentile-still-scored',
      '同层同专精百分位 0（样本 100+ 人）' in score
      and '| Nikey(猎人-野兽控制) | 输出 | 0.0 | 8.1 | 6.7 | 5.0 | 9.0 | 4.9 |' in score,
      'known_issue_reproduced', 'eu12-score-judgments.stdout.md; this check does not establish personal execution quality')
check('R2-S9-dispel-units-not-aligned', '| 暗影束缚(269935) | 10 | 28 | 2 |' in interrupts,
      'known_issue_reproduced', 'eu12-interrupts.stdout.md')
check('R2-S9-damage-summary-and-detail-differ',
      '| 剑刃风暴(270928)' in damage and '| 15/0 |' in damage
      and '| Hêll(萨满祭司-增强) | 10 | 0 |' in detail and 'Hêll81%/9' in damage,
      'known_issue_reproduced', 'eu12-damage.stdout.md; eu12-damage-ability270928.stdout.md')
summary = json.loads((REPLAY / 'results.json').read_text())
unchanged = all((ROOT / name).is_file()
                and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
                for name, digest in summary['fingerprints_before'].items())
check('protected-implementation-documents-tests-unchanged', unchanged,
      'scope_check', 'archival-replay/results.json fingerprints_before')
(OUTPUT / 'evidence-checks.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
for result in results:
    print(f"{'CONFIRMED' if result['observed'] else 'NOT_CONFIRMED'}: {result['label']} ({result['kind']})")
raise SystemExit(0 if all(result['observed'] for result in results) else 1)
