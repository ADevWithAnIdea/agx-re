#!/usr/bin/env python3
# extract_new_hex.py -- EXP-0040. Pull the extracted _agc.main hex of the NEW
# objective-2 kernel families (RT / tensor / MPP matrix / bfloat / imageblock-tile)
# out of the EXP-O2C / EXP-O2D raw dumps into individual hex/ files, so the byte0
# census can tokenize them alongside the reused EXP-0036 corpus.
#
# CLEAN-ROOM: every byte is the compiled form of MSL WE WROTE (OWN-SHADER),
# extracted by tools/shdump in EXP-O2C / EXP-O2D. No Apple binary involved.
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(HERE, 'hex')
os.makedirs(OUT, exist_ok=True)

HEXRE = re.compile(r'^[0-9a-fA-F]{8,}$')

def sanitize(s):
    return re.sub(r'[^0-9a-zA-Z]+', '_', s).strip('_')

def emit(name, hexstr):
    hexstr = hexstr.strip()
    if not HEXRE.match(hexstr):
        return False
    with open(os.path.join(OUT, name + '.hex'), 'w') as f:
        f.write(hexstr + '\n')
    return True

count = 0

# ---- EXP-O2C mains.txt: "<group> <name> <hex>" (RT + tensor + MPP) ----
p = os.path.join(EXP, 'EXP-O2C-rt-tensor-tail', 'raw', 'mains.txt')
for line in open(p):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    parts = line.split()
    if len(parts) < 3:
        continue
    group, name, hx = parts[0], parts[1], parts[-1]
    # bucket prefix so the census category function can classify
    if group in ('tensor',):
        pref = 'tensor_'
    elif group in ('mpp',):
        pref = 'mpp_'
    elif group in ('rtpay', 'rtprim', 'rtfrag'):
        pref = 'rt_'
    else:
        pref = group + '_'
    fn = pref + sanitize(name)
    count += emit(fn, hx)

# ---- EXP-O2D mains.txt: "<group> <name> MAIN|CPROG <hex>" (bfloat) ----
p = os.path.join(EXP, 'EXP-O2D-compute-frag-tail', 'raw', 'mains.txt')
seen = {}
for line in open(p):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    parts = line.split()
    if len(parts) < 4 or parts[2] != 'MAIN':
        continue                       # skip CPROG (constant program, not instructions)
    name, hx = parts[1], parts[-1]
    # bfaddu file lists both a 62B and 64B variant per name; keep the first (deduped)
    if name in seen:
        name = name + '_b'
    seen[name] = 1
    count += emit('bf_' + sanitize(name), hx)

# ---- EXP-O2D tile_mains.txt: "<name> <hex> len=NNB" (imageblock tile shaders) ----
p = os.path.join(EXP, 'EXP-O2D-compute-frag-tail', 'raw', 'tile_mains.txt')
for line in open(p):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    parts = line.split()
    if len(parts) < 2:
        continue
    name = parts[0]
    hx = next((t for t in parts[1:] if HEXRE.match(t)), None)
    if hx:
        count += emit('tile_' + sanitize(name), hx)

print(f'wrote {count} new-family hex files to {OUT}')
for f in sorted(os.listdir(OUT)):
    b = open(os.path.join(OUT, f)).read().strip()
    print(f'  {f:28s} {len(bytes.fromhex(b)):6d}B')
