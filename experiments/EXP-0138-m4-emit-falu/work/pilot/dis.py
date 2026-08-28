import sys
sys.path.insert(0,'/Users/user/asahi_re/public/agx-re/tools/agx-isa')
sys.path.insert(0,'/Users/user/asahi_re/public/agx-re/tools/shdump')
import isadb, agxparse
for path in sys.argv[1:]:
    buf=open(path,'rb').read()
    _,pieces=agxparse.extract_agx(buf)
    m=pieces["_agc.main"]
    print("=== %s  len=%d" % (path, len(m)))
    recs,left=isadb.disassemble(m)
    off=0
    for r in recs:
        print("  +%03x %-18s %s  %s" % (off, r['mnemonic'], m[off:off+r['length']].hex(), r['fields']))
        off+=r['length']
    if left: print("  LEFTOVER", left.hex())
