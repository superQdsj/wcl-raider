import json,sys
S=sys.argv[1]; st=sys.argv[2]
d=json.load(open('/private/tmp/claude-501/-Users-xialiqun--t3-worktrees-wcl-raider-t3-8300a0f4/6f568a29-46d7-4218-9a90-cb710d8ee564/scratchpad/dl/talents.json')); s=[x for x in d if x.get('specId')==261][0]
nodes={}
for k in ['classNodes','specNodes','heroNodes','subTreeNodes']:
    for n in s[k]: nodes[n['id']]=n
A='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
bits=[]
for ch in st:
    v=A.index(ch); bits+= [(v>>i)&1 for i in range(6)]
pos=0
def rd(n):
    global pos; v=sum(bits[pos+i]<<i for i in range(n)); pos+=n; return v
print('ver',rd(8),'spec',rd(16)); [rd(8) for _ in range(16)]
out=[]
for nid in s['fullNodeOrder']:
    if not rd(1): continue
    n=nodes.get(nid,{'name':'?%d'%nid})
    if not rd(1): out.append((n['name'],'granted')); continue
    r=rd(6) if rd(1) else n.get('maxRanks',1)
    idx=rd(2) if rd(1) else None
    out.append((n['name'],r,idx))
print(len(out),'leftover bits',len(bits)-pos, 'nonzero left', sum(bits[pos:]))
for o in out: print(o)
