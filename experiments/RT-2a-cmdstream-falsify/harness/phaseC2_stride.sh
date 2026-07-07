#!/bin/sh
# RT-2a Phase C2 — pin down texture/sampler descriptor STRIDE in arg buffer 0x10000248000.
# Doc claims: tex 32B, samp 8B, num_samp=(term-samp)/8.  Sweep counts, measure deltas.
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; CAP=0x1000
rm -rf capsC2; mkdir -p capsC2
ru(){ label="$1"; shift; d="capsC2/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./uvar "$@" --dump > "capsC2/$label.out" 2>&1 || true; }
# texture sweep (0 samp), sampler sweep (1 tex fixed)
ru t1s0 --ftex 1 --fsmp 0
ru t2s0 --ftex 2 --fsmp 0
ru t3s0 --ftex 3 --fsmp 0
ru t4s0 --ftex 4 --fsmp 0
ru t1s1 --ftex 1 --fsmp 1
ru t1s2 --ftex 1 --fsmp 2
ru t1s3 --ftex 1 --fsmp 3
ru t1s4 --ftex 1 --fsmp 4
ru t2s3 --ftex 2 --fsmp 3
echo "=== header ptrs + terminator per config (offsets within BO) ==="
for l in t1s0 t2s0 t3s0 t4s0 t1s1 t1s2 t1s3 t1s4 t2s3; do
  f=$(ls capsC2/$l/*va10000248000_*.hex 2>/dev/null|head -1)
  cfg=$(grep '^CONFIG' capsC2/$l.out|head -1|sed -E 's/.*(ftex=[0-9]+ fsmp=[0-9]+).*/\1/')
  printf "%-6s %-18s " "$l" "$cfg"
  [ -n "$f" ] && python3 - "$f" <<'PY'
import sys,re
base=0;data=bytearray()
for line in open(sys.argv[1]):
    if line.startswith('#'):
        m=re.search(r'gpu_va=0x([0-9a-f]+)',line);
        if m:base=int(m.group(1),16)
        continue
    m=re.match(r'^([0-9a-f]{8}):\s+(.*)$',line)
    if not m:continue
    o=int(m.group(1),16);b=bytes.fromhex(m.group(2).replace(' ',''))
    if len(data)<o+len(b):data.extend(b'\0'*(o+len(b)-len(data)))
    data[o:o+len(b)]=b
u64=lambda o:int.from_bytes(data[o:o+8],'little');u32=lambda o:int.from_bytes(data[o:o+4],'little')
lo,hi=base,base+0x8000;hdr=None
for o in range(0,0xf00,8):
    a,b=u64(o),u64(o+8)
    if lo<=a<hi and lo<=b<hi and (a>>32)==0x100 and b>=a: hdr=o;tp=a-base;sp=b-base;break
term=None
for o in range(0,0xf00,4):
    if u32(o)==0x60000000: term=o;break
if hdr is None: print("hdr=? term@%s"%(hex(term) if term else '?'));sys.exit()
print("hdr@%#x tex@%#x samp@%#x term@%#x | texbytes=%#x sampbytes=%#x"%(hdr,tp,sp,term,sp-tp,term-sp))
PY
done
echo DONE_PHASE_C2