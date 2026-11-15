import json,re,sys
sys.path.insert(0,sys.argv[1])
from timeline import build
W=sys.argv[1]; out=sys.argv[2]
s=open(W+'/src.html').read().replace('{{TIMELINE}}',build())
s=s.replace('{{TALENT}}',json.load(open(W+'/tal.json'))['Ptz']['string'])
ic=json.load(open(W+'/icons.json'))
s=re.sub(r'\{\{I:(\d+)\}\}',lambda m:ic[m.group(1)],s)
assert '{{' not in s, re.findall(r'\{\{[^}]*\}\}',s)[:5]
open(out,'w').write(s); print(len(s))

# Icons live in guides/icons/; the page links to them instead of embedding base64.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.abspath(__file__).split("/guides/")[0], "guides", "tools"))
from icons import externalize
print("icons:", externalize(out))
