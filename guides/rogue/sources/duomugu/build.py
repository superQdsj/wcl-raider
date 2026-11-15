import json,re,sys,base64
D,out=sys.argv[1],sys.argv[2]
s=open(D+'/src.html').read()
ic=json.load(open(D+'/icons.json'))
s=re.sub(r'\{\{I:(\d+)\}\}',lambda m:ic[m.group(1)],s)
s=re.sub(r'\{\{T:(\d+)\}\}',lambda m:'data:image/jpeg;base64,'+base64.b64encode(open(f'{D}/ticons/{m.group(1)}.jpg','rb').read()).decode(),s)
s=s.replace('{{TALENT}}',json.load(open(D+'/tstring.json'))['string'])
assert '{{' not in s
open(out,'w').write(s); print(len(s))

# Icons live in guides/icons/; the page links to them instead of embedding base64.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.abspath(__file__).split("/guides/")[0], "guides", "tools"))
from icons import externalize
print("icons:", externalize(out))
