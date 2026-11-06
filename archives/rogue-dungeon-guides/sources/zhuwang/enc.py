import json,sys
S=sys.argv[1]
d=json.load(open(S+'/dl/talents.json')); s=[x for x in d if x.get('specId')==261][0]
p=json.load(open(sys.argv[2]))['斗篷小王子']['combatantInfo']['talentTree']
nodes={}
for k in ['classNodes','specNodes','heroNodes','subTreeNodes']:
    for n in s[k]: nodes[n['id']]=(k,n)
w={}
for t in p:
    if t['nodeID'] in w: w[t['nodeID']]=dict(w[t['nodeID']],rank=w[t['nodeID']]['rank']+t['rank'])
    else: w[t['nodeID']]=dict(t)
w[99842]={'id':123370,'rank':1,'nodeID':99842}
print('free nodes',[(n['name'],nid in w, k) for nid,(k,n) in nodes.items() if n.get('freeNode')])
bits=[]
def add(n,v):
    for i in range(n): bits.append((v>>i)&1)
add(8,2); add(16,261)
th=s['treeHash']; print('hash',th)
for b in [0]*16: add(8,b)
rows=[]
for nid in s['fullNodeOrder']:
    if nid not in w: add(1,0); continue
    k,n=nodes[nid]; t=w[nid]
    add(1,1)
    free=bool(n.get('freeNode'))
    add(1,0 if free else 1)
    if free: rows.append((n['name'],'granted')); continue
    mx=n.get('maxRanks',1); partial=t['rank']!=mx
    add(1,int(partial))
    if partial: add(6,t['rank'])
    choice=n['type'] in ('choice','subtree')
    add(1,int(choice))
    idx=None
    if choice:
        idx=[e['id'] for e in n['entries']].index(t['id']); add(2,idx)
    else:
        assert n['type']=='tiered' or n['entries'][0]['id']==t['id'],(n['name'],t)
    rows.append((n['name'],t['rank'],mx,idx))
A='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
while len(bits)%6: bits.append(0)
out=''.join(A[sum(bits[i+j]<<j for j in range(6))] for i in range(0,len(bits),6))
print(out); print(len(rows))
json.dump({'string':out,'rows':rows},open(sys.argv[3],'w'),ensure_ascii=False)
