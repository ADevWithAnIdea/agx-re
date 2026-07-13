#!/bin/sh
cd ~/cleanroom_work/EXP-M5-10
IT=../tools/iotrace
P=scripts
: >progress_rt3.log
clang -fobjc-arc -O0 -arch arm64e -framework Metal -framework Foundation scripts/indir.m -o indir 2>build_indir3.err
[ -x indir ] || { echo "BUILD_FAIL indir"; cat build_indir3.err; } >>progress_rt3.log
runbin(){ BIN="$1";NAME="$2";shift 2; rm -rf u_$NAME; mkdir -p u_$NAME
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=u_$NAME DYLD_INSERT_LIBRARIES=$IT/iotrace.dylib \
    ./$BIN "$@" --dump >ru_$NAME.txt 2>&1
  find u_$NAME -type f -size +2000k -delete 2>/dev/null
  echo "$NAME $(grep -oE 'STATUS=[0-9]+|COMPILE_FAIL|PIPELINE_FAIL' ru_$NAME.txt | head -1)" >>progress_rt3.log
}
runbin indir in_mesh --mode mesh
runbin indir in_tess --mode tess
echo "MESHTESS_DONE" >>progress_rt3.log
{
echo "############ MESH: tiler stream va18000 scan for mesh-grid-dispatch record ############"
FM=$(ls u_in_mesh/bo_*va18000_*.hex 2>/dev/null)
echo "mesh STATUS: $(grep STATUS ru_in_mesh.txt)"
for O in 0x80 0x84 0x88 0x8c 0x90 0x94 0x98 0x9c 0xa0 0xa4 0xa8; do python3 $P/shex.py "$FM" $O 4; done
echo "--- search va18000 for 0x70000600 / 0x70000e00 (mesh opcode) ---"
python3 - "$FM" <<'PY'
import sys,re
d=bytearray()
for line in open(sys.argv[1]):
    m=re.match(r'^([0-9a-f]{8}): (.*)',line)
    if not m:continue
    b=int(m.group(1),16);by=bytes.fromhex(m.group(2).replace(' ',''))
    if b+len(by)>len(d):d.extend(b'\x00'*(b+len(by)-len(d)))
    d[b:b+len(by)]=by
for i in range(0,len(d)-4,4):
    w=int.from_bytes(d[i:i+4],'little')
    if (w&0xffff0000)==0x70000000 or (w>>24)==0x70: print("  +0x%04x: %08x"%(i,w))
PY
echo; echo "############ TESS: tiler stream va18000 scan for patch-dispatch record ############"
FT=$(ls u_in_tess/bo_*va18000_*.hex 2>/dev/null)
echo "tess STATUS: $(grep STATUS ru_in_tess.txt)"
python3 - "$FT" <<'PY'
import sys,re
d=bytearray()
for line in open(sys.argv[1]):
    m=re.match(r'^([0-9a-f]{8}): (.*)',line)
    if not m:continue
    b=int(m.group(1),16);by=bytes.fromhex(m.group(2).replace(' ',''))
    if b+len(by)>len(d):d.extend(b'\x00'*(b+len(by)-len(d)))
    d[b:b+len(by)]=by
# print non-zero words in 0x80..0x120
for i in range(0x80,0x120,4):
    w=int.from_bytes(d[i:i+4],'little')
    if w: print("  +0x%04x: %08x"%(i,w))
PY
echo; echo "############ MORTON: find r32u texture backing in u_tp192 and u_tp128 ############"
echo "--- tp192 ---"; python3 $P/morton_find.py u_tp192
echo "--- tp128 ---"; python3 $P/morton_find.py u_tp128
echo; echo "############ FF LENGTH WORD: VDM va18000+0x0c and pool va58000+0x14 (base vs depth vs stencil) ############"
for N in base d_on scmp1 cull_back; do
  echo "--- $N ---"
  python3 $P/shex.py m_$N/bo_*va18000_*.hex 0x0c 4
  python3 $P/shex.py m_$N/bo_*va58000_*.hex 0x14 4
done
} >rt3_analysis.txt 2>&1
echo "ALL_RT3_DONE" >>progress_rt3.log
