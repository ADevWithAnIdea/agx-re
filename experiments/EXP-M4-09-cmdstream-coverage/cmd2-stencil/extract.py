#!/usr/bin/env python3
"""Extract & decode the front (+0x3c) and back (+0x44) stencil words from each
capture's 0x58000 BO. CLEAN-ROOM: DATA only."""
import glob, os, re

HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')

def load58000(capdir):
    files = glob.glob(os.path.join(capdir, 'bo_sigusr1_*_va58000_*.hex'))
    if not files:
        return None
    data = bytearray()
    with open(files[0]) as f:
        for line in f:
            m = HEXLINE.match(line)
            if not m:
                continue
            off = int(m.group(1), 16)
            b = bytes.fromhex(m.group(2).replace(' ', ''))
            if len(data) < off + len(b):
                data.extend(b'\x00' * (off + len(b) - len(data)))
            data[off:off+len(b)] = b
    return bytes(data)

def w32(data, off):
    return int.from_bytes(data[off:off+4], 'little')

def decode(word):
    return {
        'wmask':  word & 0xff,
        'rmask':  (word >> 8) & 0xff,
        'pass':   (word >> 16) & 7,
        'zfail':  (word >> 19) & 7,
        'sfail':  (word >> 22) & 7,
        'cmp':    (word >> 25) & 7,
        'high':   word >> 28,
    }

OPNAME = ['keep','zero','replace','incrclamp','decrclamp','invert','incrwrap','decrwrap']
OPS = OPNAME

def rowfmt(label, word):
    d = decode(word)
    return (f"  {label:16s} +0x3c=0x{word:08x}  "
            f"wm={d['wmask']:#04x} rm={d['rmask']:#04x} "
            f"pass={d['pass']} zfail={d['zfail']} sfail={d['sfail']} cmp={d['cmp']} hi={d['high']}")

def main():
    print("### FRONT-FACE stencil word (+0x3c) per capture\n")
    # reference
    for tag in ['s_ref']:
        data = load58000(f'caps/{tag}')
        if data is None:
            print(f"  {tag}: NO 58000 BO"); continue
        print(rowfmt(tag, w32(data, 0x3c)))
    print()

    for field in ['spass', 'szfail', 'sfail']:
        print(f"--- {field} sweep (front +0x3c) ---")
        for op in OPS:
            tag = f'{field}_{op}'
            data = load58000(f'caps/{tag}')
            if data is None:
                print(f"  {tag:16s} NO 58000 BO (packet absent/disabled)"); continue
            word = w32(data, 0x3c)
            d = decode(word)
            # map field name -> decoded key
            key = {'spass':'pass','szfail':'zfail','sfail':'sfail'}[field]
            print(rowfmt(tag, word) + f"   <== {field}={op} -> {key}-field={d[key]}")
        print()

    print("### BACK-FACE check")
    for tag in ['s_ref', 'sback']:
        data = load58000(f'caps/{tag}')
        if data is None:
            print(f"  {tag}: NO 58000 BO"); continue
        wf = w32(data, 0x3c); wb = w32(data, 0x44)
        df = decode(wf); db = decode(wb)
        print(f"  {tag:8s} front +0x3c=0x{wf:08x} (pass={df['pass']} zfail={df['zfail']} sfail={df['sfail']} cmp={df['cmp']} wm={df['wmask']:#04x} rm={df['rmask']:#04x})")
        print(f"  {tag:8s} back  +0x44=0x{wb:08x} (pass={db['pass']} zfail={db['zfail']} sfail={db['sfail']} cmp={db['cmp']} wm={db['wmask']:#04x} rm={db['rmask']:#04x})")

if __name__ == '__main__':
    main()
