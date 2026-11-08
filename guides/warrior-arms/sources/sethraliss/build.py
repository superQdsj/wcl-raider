import json,re,sys
S,out=sys.argv[1:3]
s=open(S+'/arms.src.html').read()
ic=json.load(open(S+'/icons.json')); ts=json.load(open(S+'/tstring.json'))['string']
s=s.replace('{{TSTRING}}',ts)
miss=set()
def f(m):
    k=m.group(1)
    if k not in ic: miss.add(k); return ''
    return ic[k]
s=re.sub(r'\{\{(\d+)\}\}',f,s)
assert not miss, miss
open(out,'w').write(s); print(len(s))
