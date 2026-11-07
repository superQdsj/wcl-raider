import json,re,sys,base64
N,out=sys.argv[1],sys.argv[2]
head=open(N+'/head.part').read()
rep=[('<title>潜行者 · 毒牙祭坛</title>','<title>潜行者 · 纳洛拉克的洞穴</title>'),
 ('/* 布局：一张贼的作战卡。顶部斗篷时间轴 → 必会时刻 → 闪避新发现 → 按路线逐段 → 工具箱 → 减益 → 来源。单一暗色主题（毒林夜色），潜行者金为唯一强调色。 */',
  '/* 布局：一张贼的作战卡。顶部斗篷时间轴 → 必会时刻 → 回响重击专题 → 按路线逐段 → 工具箱 → 减益 → 天赋。单一暗色主题（冰原熊穴夜色），潜行者金为唯一强调色。 */'),
 ('--bg:#0d1210; --panel:#141b18; --panel-2:#1a231f; --line:#27322d;','--bg:#0d1114; --panel:#141a1e; --panel-2:#1a2227; --line:#273139;'),
 ('--ink:#ebe7da; --mute:#97a39b; --faint:#5f6c65;','--ink:#e9e8e1; --mute:#98a3a8; --faint:#5e6b72;'),
 ('--venom:#86c97c;','--venom:#8fd0dc;'),
 ('rgba(134,201,124,.07)','rgba(143,208,220,.08)'),
 ('rgba(134,201,124,.16)','rgba(143,208,220,.15)'),
 ('rgba(134,201,124,.35)','rgba(143,208,220,.35)'),
 ('.bar .on{background:var(--gold)}','.bar .on{background:var(--gold)}\n.bar .on.dim{background:#c9ad3c}\n.bar .zero{width:100%;background:transparent;color:var(--gold);justify-content:flex-start;padding-left:10px;border:1px dashed var(--gold-dim)}'),
]
for a,b in rep:
    assert a in head,a; head=head.replace(a,b)
tail=open(N+'/tail.part').read().split('</footer>',1)[1]
s=head+open(N+'/body.part').read()+tail
ic=json.load(open(N+'/icons.json'))
s=re.sub(r'\{\{I:(\d+)\}\}',lambda m:ic[m.group(1)],s)
s=re.sub(r'\{\{T:(\d+)\}\}',lambda m:'data:image/jpeg;base64,'+base64.b64encode(open(f'{N}/ticons/{m.group(1)}.jpg','rb').read()).decode(),s)
s=s.replace('{{TALENT}}',json.load(open(N+'/tstring.json'))['string'])
assert '{{' not in s
open(N+'/src.html','w').write(head+open(N+'/body.part').read()+tail)
open(out,'w').write(s); print(len(s))
