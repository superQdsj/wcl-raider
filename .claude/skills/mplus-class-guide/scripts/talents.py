ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
GROUPS = ('classNodes', 'specNodes', 'heroNodes', 'subTreeNodes')


def selections(combatant):
    selected = {}
    for talent in combatant['combatantInfo']['talentTree']:
        node_id = talent['nodeID']
        if node_id in selected:
            selected[node_id]['rank'] += talent['rank']
        else:
            selected[node_id] = dict(talent)
    return selected


def encode(tree, selected):
    nodes = {node['id']: node for group in GROUPS for node in tree[group]}
    if selected.keys() - nodes.keys():
        raise ValueError('Unknown selected talent node')
    bits = []

    def append(width, value):
        if not 0 <= value < 2 ** width:
            raise ValueError('Talent value exceeds serialization width')
        bits.extend((value >> offset) & 1 for offset in range(width))

    append(8, 2)
    append(16, tree['specId'])
    for _ in range(16):
        append(8, 0)
    for node_id in tree['fullNodeOrder']:
        talent = selected.get(node_id)
        append(1, int(talent is not None))
        if talent is None:
            continue
        node = nodes[node_id]
        append(1, int(not node.get('freeNode')))
        if node.get('freeNode'):
            continue
        rank = talent['rank']
        maximum = node.get('maxRanks', 1)
        if not 1 <= rank <= maximum:
            raise ValueError(f'Invalid talent rank: {node_id}: {rank}/{maximum}')
        append(1, int(rank != maximum))
        if rank != maximum:
            append(6, rank)
        choice = node['type'] in ('choice', 'subtree')
        append(1, int(choice))
        if choice:
            append(2, [entry['id'] for entry in node['entries']].index(talent['id']))
        elif node['type'] != 'tiered' and node['entries'][0]['id'] != talent['id']:
            raise ValueError('Entry ID does not match talent node')
    bits.extend([0] * (-len(bits) % 6))
    encoded = ''.join(ALPHABET[sum(bits[start + offset] << offset for offset in range(6))] for start in range(0, len(bits), 6))
    decoded = decode(tree, encoded)
    expected = {node_id: (talent['rank'], None if nodes[node_id]['type'] == 'tiered' else talent['id']) for node_id, talent in selected.items()}
    if decoded != expected:
        raise ValueError('Talent import string does not round-trip to WCL selections')
    return encoded


def decode(tree, encoded):
    nodes = {node['id']: node for group in GROUPS for node in tree[group]}
    bits = [((ALPHABET.index(character) >> offset) & 1) for character in encoded for offset in range(6)]
    position = 0

    def read(width):
        nonlocal position
        if position + width > len(bits):
            raise ValueError('Truncated talent import string')
        value = sum(bits[position + offset] << offset for offset in range(width))
        position += width
        return value

    if read(8) != 2 or read(16) != tree['specId']:
        raise ValueError('Wrong serialization version or specialization')
    for _ in range(16):
        read(8)
    selected = {}
    for node_id in tree['fullNodeOrder']:
        if not read(1):
            continue
        node = nodes[node_id]
        if not read(1):
            selected[node_id] = (node.get('maxRanks', 1), node['entries'][0]['id'])
            continue
        rank = read(6) if read(1) else node.get('maxRanks', 1)
        index = read(2) if read(1) else 0
        if index >= len(node['entries']):
            raise ValueError('Unknown talent choice')
        selected[node_id] = (rank, None if node['type'] == 'tiered' else node['entries'][index]['id'])
    if len(bits) - position > 5 or any(bits[position:]):
        raise ValueError('Unexpected trailing talent data')
    return selected
