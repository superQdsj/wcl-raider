"""Read-only cache replay and existing offline tests; no live API requests."""
import contextlib
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
ARCHIVAL = '--archival' in sys.argv
if ARCHIVAL:
    OUTPUT = OUTPUT / 'archival-replay'
    OUTPUT.mkdir(exist_ok=True)
HISTORY = Path('/private/tmp/claude-501/-Users-xialiqun--t3-projects-wcl-raider/'
               'dab802e1-9e0d-4b16-b516-87152cf78dfd/scratchpad/review-round2')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / '.claude/skills/mplus-review/scripts'))
from wclr import api
from wclr.cli import main


def fingerprint():
    paths = [ROOT / 'README.md', ROOT / '.env.example', ROOT / '.gitignore']
    paths += list((ROOT / '.claude').rglob('*'))
    paths += list((ROOT / 'tests').glob('*.py'))
    paths += [ROOT / 'tests/corpus.md']
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)
            if path.is_file() and '__pycache__' not in path.parts}


def blocked_network(*args, **kwargs):
    raise api.WCLError('CACHE_ONLY: uncached request blocked; no network performed')


original_cache_get = api._cache_get


def archival_cache_get(path, ttl):
    return original_cache_get(path, float('inf'))


def execute(label, args, expected=0):
    stdout, stderr = io.StringIO(), io.StringIO()
    started = time.monotonic()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            exit_code = main(args)
        except SystemExit as error:
            exit_code = error.code
        except Exception as error:
            import traceback
            traceback.print_exc()
            exit_code = 99
    text, errors = stdout.getvalue(), stderr.getvalue()
    (OUTPUT / f'{label}.stdout.md').write_text(text, encoding='utf-8')
    (OUTPUT / f'{label}.stderr.log').write_text(errors, encoding='utf-8')
    cache_miss = 'CACHE_ONLY:' in errors or 'CACHE_ONLY:' in text
    status = 'CACHE_MISS' if cache_miss else ('PASS' if exit_code == expected else 'FAIL')
    result = dict(label=label, argv=args, expected_exit=expected, exit_code=exit_code,
                  status=status, elapsed_seconds=round(time.monotonic() - started, 3),
                  stdout_chars=len(text), truncation_notice='已截断' in text)
    print(f'{status}: {label}', flush=True)
    return result


def report_url(code, fight):
    return f'https://www.warcraftlogs.com/reports/{code}#fight={fight}'


before = fingerprint()
environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
unit = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                      cwd=ROOT, env=environment, capture_output=True, text=True)
(OUTPUT / 'unittest.stdout.log').write_text(unit.stdout, encoding='utf-8')
(OUTPUT / 'unittest.stderr.log').write_text(unit.stderr, encoding='utf-8')
print(f'UNITTEST: exit {unit.returncode}', flush=True)
historical = []
for name in ('sol-feedback.md', 'sol-dryrun.md', 'sol-judgments.json'):
    source = HISTORY / name
    if source.exists():
        (OUTPUT / f'historical-{name}').write_bytes(source.read_bytes())
        historical.append(name)

cases = []
samples = [('cn24', 'JpHdnbhYD8ZFWvma', 1),
           ('eu11', 'QkyF9vA2hC7qJzGY', 15),
           ('eu12', 'QkyF9vA2hC7qJzGY', 3)]
for label, code, fight in samples:
    url = report_url(code, fight)
    for command in ('runs', 'overview', 'pulls', 'deaths', 'interrupts', 'damage', 'compare', 'score'):
        cases.append((f'{label}-{command}', [command, url], 0))
    cases.append((f'{label}-deaths-full', ['deaths', url, '--detail', '100', '--max-chars', '0'], 0))

eu12 = report_url('QkyF9vA2hC7qJzGY', 3)
for command, suffix, options in [
    ('interrupts', 'pull8', ['--pull', '8', '--max-chars', '0']),
    ('damage', 'ability270003', ['--ability', '270003', '--max-chars', '0']),
    ('damage', 'blade-storm', ['--ability', '剑刃风暴', '--max-chars', '0']),
    ('damage', 'ability270928', ['--ability', '270928', '--max-chars', '0']),
    ('player', 'Nikey', ['Nikey', '--max-chars', '0']),
    ('player', 'Ysavia', ['Ysavia', '--max-chars', '0']),
    ('player', 'Xervdh', ['Xervdh', '--max-chars', '0']),
    ('player', 'ability', ['Nikey', '--ability', '193455', '--max-chars', '0']),
    ('player', 'Hell-ability108271', ['Hêll', '--ability', '108271', '--max-chars', '0']),
    ('events', 'pull8-enemy', ['--pull', '8', '--type', 'enemy-casts', '--max-chars', '0']),
    ('events', 'pull8-interrupts', ['--pull', '8', '--type', 'interrupts', '--max-chars', '0']),
    ('events', 'frontal', ['--from', '0:56', '--to', '1:10', '--type', 'all', '--ability', '270003', '--max-chars', '0']),
    ('events', 'disease', ['--from', '11:59', '--to', '12:10', '--type', 'all', '--ability', '267763', '--max-chars', '0']),
    ('score', 'no-compare', ['--no-compare', '--max-chars', '0']),
    ('spec', 'Nikey', ['Nikey', '--max-chars', '0']),
]:
    cases.append((f'eu12-{command}-{suffix}', [command, eu12] + options, 0))
judgments = OUTPUT / 'historical-sol-judgments.json'
if judgments.exists():
    cases.append(('eu12-score-judgments', ['score', eu12, '--judgments', str(judgments), '--max-chars', '0'], 0))
for label, code, fight, expected in [
    ('us2', 'tgC7LXH1PJyRpKfj', 1, 0),
    ('eu5', 'QkyF9vA2hC7qJzGY', 29, 0),
    ('kr9', '2D6YH98bdKkqAMz1', 5, 0),
    ('tw5', 'AhMVrbJgZxPWq7nQ', 1, 0),
    ('cn2', 'nQcvWw29qgzkFNyd', 1, 0),
    ('abandoned', 'yWF7rmM2BTtzP41Q', 12, 0),
    ('raid', '1WGqgPTy62FRwDnZ', 1, 2),
]:
    cases.append((f'{label}-overview', ['overview', report_url(code, fight)], expected))
cases += [
    ('cli-help', ['--help'], 0),
    ('invalid-report', ['overview', 'not-a-report'], 2),
    ('invalid-pull', ['interrupts', eu12, '--pull', '0'], 2),
    ('invalid-max-chars', ['deaths', eu12, '--max-chars', '-1'], 2),
    ('invalid-window', ['deaths', eu12, '--window', 'nan'], 2),
    ('missing-fight', ['overview', eu12, '--fight', '99999'], 2),
    ('missing-player', ['player', eu12, 'NonexistentPlayerForVerification'], 2),
    ('missing-pull', ['interrupts', eu12, '--pull', '99999'], 2),
]
cache_policy = (patch.object(api, '_cache_get', side_effect=archival_cache_get)
                if ARCHIVAL else contextlib.nullcontext())
with patch.object(api.Client, '_post', side_effect=blocked_network), \
        patch('urllib.request.urlopen', side_effect=blocked_network), cache_policy:
    results = [execute(*case) for case in cases]
after = fingerprint()
summary = dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               python=sys.version, scope='existing tests and cache-only replay; no optimization',
               network='blocked at Client._post and urllib.request.urlopen; zero actual requests',
               cache_policy='archival: ignore TTL in test harness only' if ARCHIVAL else 'production TTL',
               unit_exit_code=unit.returncode, historical_artifacts=historical,
               protected_files_unchanged=before == after, fingerprints_before=before,
               fingerprints_after=after, cases=results)
(OUTPUT / 'results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: sum(case['status'] == key for case in results)
                  for key in ('PASS', 'FAIL', 'CACHE_MISS')}, ensure_ascii=False))
print(f'PROTECTED_FILES_UNCHANGED: {before == after}')
