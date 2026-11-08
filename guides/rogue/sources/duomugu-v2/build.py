"""Offline rebuild: python3 build.py [out.html]  (default: ../../2026-11-08-夺目谷-潜行者.html)
Inputs: src.html (page), timeline.py (cloak lanes), tstring.json (from enc.py), icons.json (spell id -> data URI)."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
from timeline import build

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '../../2026-11-08-夺目谷-潜行者.html')
s = open(os.path.join(H, 'src.html'), encoding='utf-8').read().replace('{{TIMELINE}}', build())
s = s.replace('{{TALENT}}', json.load(open(os.path.join(H, 'tstring.json')))['string'])
ic = json.load(open(os.path.join(H, 'icons.json')))
s = re.sub(r'\{\{I:(\d+)\}\}', lambda m: ic[m.group(1)], s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}', s)[:5]
open(out, 'w', encoding='utf-8').write(s)
print(out, len(s))
