import sys, subprocess, json
sys.path.insert(0,'../../../tools/agx-isa')
import isadb
hx = sys.argv[1] if len(sys.argv)>1 else None
b = bytes.fromhex(hx)
off=0
while off < len(b):
    try:
        L = isadb.instr_length(b, off)
    except Exception as e:
        print("%04x  LENFAIL %s" % (off, e)); break
    if not L: print("%04x  LEN0 %s"%(off,b[off:off+8].hex())); break
    chunk = b[off:off+L]
    try:
        d, _L = isadb.decode_one(b, off)
    except Exception as e:
        d = None
    m = d['mnemonic'] if d else '?'
    f = d.get('fields') if d else {}
    print("%04x  %-20s %-34s %s" % (off, m, chunk.hex(), json.dumps(f) if f else ''))
    off += L
