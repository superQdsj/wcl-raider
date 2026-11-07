import json,re,sys,base64
S,out=sys.argv[1],sys.argv[2]
s=open(S+'/rogue.src.html').read()
ic=json.load(open(S+'/icons.json'))
s=re.sub(r'\{\{I:(\d+)\}\}',lambda m:ic[m.group(1)],s)
s=re.sub(r'\{\{T:(\d+)\}\}',lambda m:'data:image/jpeg;base64,'+base64.b64encode(open(f'{S}/ticons/{m.group(1)}.jpg','rb').read()).decode(),s)
s=s.replace('{{TALENT}}',json.load(open(S+'/tstring.json'))['string'])
assert '{{' not in s
open(out,'w').write(s); print(len(s))
