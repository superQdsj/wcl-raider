"""Encode a WCL combatantInfo talentTree into an in-game import string, then decode it back to verify.
usage: python3 enc.py <player>   (reads talents_raw.json + ../../../rogue/sources/dl/talents.json, writes tstring.json)"""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__))
A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
spec = [x for x in json.load(open(os.path.join(H, '../../../rogue/sources/dl/talents.json'))) if x.get('specId') == 1480][0]
nodes = {}
for k in ['classNodes', 'specNodes', 'heroNodes', 'subTreeNodes']:
    for n in spec[k]:
        nodes[n['id']] = n


def encode(tree):
    w = {}
    for t in tree:
        if t['nodeID'] in w:
            w[t['nodeID']]['rank'] += t['rank']
        else:
            w[t['nodeID']] = dict(t)
    bits = []
    def add(n, v):
        bits.extend((v >> i) & 1 for i in range(n))
    add(8, 2); add(16, 1480)
    for _ in range(16):
        add(8, 0)
    for nid in spec['fullNodeOrder']:
        if nid not in w:
            add(1, 0); continue
        n, t = nodes[nid], w[nid]
        add(1, 1)
        if n.get('freeNode'):
            add(1, 0); continue
        add(1, 1)
        mx = n.get('maxRanks', 1)
        add(1, int(t['rank'] != mx))
        if t['rank'] != mx:
            add(6, t['rank'])
        choice = n['type'] in ('choice', 'subtree')
        add(1, int(choice))
        if choice:
            add(2, [e.get('id') for e in n['entries']].index(t['id']))
    while len(bits) % 6:
        bits.append(0)
    return ''.join(A[sum(bits[i + j] << j for j in range(6))] for i in range(0, len(bits), 6)), w


def decode(st):
    bits = []
    for ch in st:
        v = A.index(ch); bits += [(v >> i) & 1 for i in range(6)]
    pos = [0]
    def rd(n):
        v = sum(bits[pos[0] + i] << i for i in range(n)); pos[0] += n; return v
    assert rd(8) == 2 and rd(16) == 1480
    [rd(8) for _ in range(16)]
    out = {}
    for nid in spec['fullNodeOrder']:
        if not rd(1):
            continue
        n = nodes[nid]
        if not rd(1):
            out[nid] = ('granted', None); continue
        r = rd(6) if rd(1) else n.get('maxRanks', 1)
        idx = rd(2) if rd(1) else 0
        out[nid] = (r, n['entries'][idx]['id'])
    return out


if __name__ == '__main__':
    who = sys.argv[1] if len(sys.argv) > 1 else 'r3_Chandemon'
    tree = json.load(open(os.path.join(H, 'talents_raw.json')))[who]['talentTree']
    st, w = encode(tree)
    back = decode(st)
    # verify: every WCL node comes back with the same entry and rank (free nodes come back as granted)
    bad = []
    for nid, t in w.items():
        b = back.get(nid)
        if b is None:
            bad.append((nid, 'missing'))
        elif b[0] != 'granted' and (b[0] != t['rank'] or (nodes[nid]['type'] != 'tiered' and b[1] != t['id'])):
            bad.append((nid, t, b))
    extra = set(back) - set(w)
    print(st); print('nodes', len(w), 'decoded', len(back), 'mismatch', bad, 'extra', extra)
    assert not bad and not extra
    names = []
    for nid, t in w.items():
        n = nodes[nid]; e = [x for x in n['entries'] if x.get('id') == t['id']]
        names.append(e[0]['name'] if e else n['name'])
    json.dump({'player': who, 'string': st, 'talents': sorted(names)}, open(os.path.join(H, 'tstring.json'), 'w'), ensure_ascii=False, indent=1)
