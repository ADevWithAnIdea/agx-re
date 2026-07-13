#!/bin/sh
# occ_driver.sh — occupancy-tier correlation on M5. For each accumulator count N:
#   (1) emit the exact MSL, compile with shdump, read f0 (GPR footprint) from __GPU_METADATA
#   (2) run under iotrace with --dump, snapshot the CDM config BO 0x100000b0000, read +0x00
#       and report bit23 (occupancy tier).
# CLEAN-ROOM: own MSL/API; iotrace logs non-copyrightable BO bytes from our own process.
cd ~/cleanroom_work/EXP-M5-21 || exit 1
IT=~/cleanroom_work/tools/iotrace
SHDUMP=~/cleanroom_work/tools/shdump/shdump
tmo(){ t=$1; shift; perl -e 'alarm(shift); exec @ARGV' "$t" "$@"; }
clang -fobjc-arc -O0 -arch arm64e -framework Metal -framework Foundation occ_probe.m -o occ_probe 2>occ_build.err
if [ ! -x occ_probe ]; then echo "BUILD_FAIL"; cat occ_build.err; exit 1; fi
echo "N f0 config+0x00 bit23"
for N in "$@"; do
  # (1) emit + compile + f0
  ./occ_probe --acc $N --emit src_$N.metal >/dev/null 2>&1
  f0=$(python3 - "$N" <<'PY'
import sys,os,struct,importlib.util
N=sys.argv[1]; HERE=os.path.expanduser("~/cleanroom_work/EXP-M5-21")
TOOLS=os.path.expanduser("~/cleanroom_work/tools")
spec=importlib.util.spec_from_file_location("ap",os.path.join(TOOLS,"shdump","agxparse.py"));ap=importlib.util.module_from_spec(spec);spec.loader.exec_module(ap)
import subprocess
arch=os.path.join(HERE,"occ_%s.bin"%N)
subprocess.run([os.path.join(TOOLS,"shdump","shdump"),"-o",arch,"-f","k","--no-fast-math",os.path.join(HERE,"src_%s.metal"%N)],capture_output=True)
buf=open(arch,"rb").read()
def gpu(buf):
  for off,size,note in ap.iter_gpu_images(buf):
    try:mo=ap.MachO(buf,off)
    except ValueError:continue
    if mo.cputype==ap.APPLE_GPU_CPUTYPE:return mo
mo=gpu(buf);s=mo.find_section("__TEXT","__compute");nb=mo.base+s["offset"];nm=ap.MachO(buf,nb)
meta=None
for sec in nm.sections:
  if sec["seg"]=="__GPU_METADATA":o=nb+sec["offset"];meta=bytes(buf[o:o+sec["size"]])
def tf(b,t):
  so=struct.unpack_from('<i',b,t)[0];vt=t-so;nf=(struct.unpack_from('<H',b,vt)[0]-4)//2;f={}
  for i in range(nf):
    fo=struct.unpack_from('<H',b,vt+4+i*2)[0]
    if fo:f[i]=t+fo
  return f
root=struct.unpack_from('<I',meta,0)[0];rf=tf(meta,root);sub=rf[0]+struct.unpack_from('<I',meta,rf[0])[0];ff=tf(meta,sub)
print(struct.unpack_from('<I',meta,ff[0])[0])
os.remove(arch)
PY
)
  # (2) traced dispatch + config BO snapshot
  rm -rf m_occ_$N; mkdir -p m_occ_$N
  tmo 45 env IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=m_occ_$N IOTRACE_MAX_MAP=262144 \
    DYLD_INSERT_LIBRARIES=$IT/iotrace.dylib ./occ_probe --acc $N --grid 64 --tg 32 --dump >r_occ_$N.txt 2>&1
  # keep only the CDM config BO
  for f in m_occ_$N/bo_*; do [ -e "$f" ] || continue; case "$(basename "$f")" in *100000b0000*) : ;; *) rm -f "$f";; esac; done
  cfg="?"; bit23="?"
  BOF=$(ls m_occ_$N/*100000b0000* 2>/dev/null | head -1)
  if [ -n "$BOF" ]; then
    read cfg bit23 <<EOF
$(python3 - "$BOF" <<'PY'
import sys,re
data=bytearray()
for line in open(sys.argv[1]):
  if line.startswith('#'):continue
  m=re.match(r'^([0-9a-f]{8}):\s+(.*)',line)
  if not m:continue
  base=int(m.group(1),16);hexs=m.group(2).replace(' ','')
  b=bytes.fromhex(hexs[:len(hexs)-(len(hexs)%2)])
  if base+len(b)>len(data):data.extend(b'\x00'*(base+len(b)-len(data)))
  data[base:base+len(b)]=b
v=int.from_bytes(bytes(data[0:4]),'little')
print("0x%08x %d"%(v,(v>>23)&1))
PY
)
EOF
  fi
  echo "$N $f0 $cfg $bit23"
done
