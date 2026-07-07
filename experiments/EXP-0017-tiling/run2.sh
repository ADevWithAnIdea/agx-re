#!/bin/sh
# EXP-0017 run2 — focused compression-trigger sweep, entropy test, and mip packing.
set -u
cd "$(dirname "$0")"
clang -fobjc-arc -framework Metal -framework Foundation -o texprobe texprobe.m || exit 1
DYL=./iotrace.dylib
mkdir -p caps analysis

cap() { label="$1"; fmt="$2"; W="$3"; H="$4"; shift 4
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./texprobe --fmt "$fmt" --w "$W" --h "$H" "$@" --dump \
    > "caps/$label.stdout" 2>&1 || true
  echo "  cap $label $fmt ${W}x${H} $*"
}

echo "=== F: compression trigger — ShaderRead-only (no ShaderWrite), size sweep ==="
for S in 4 8 16 32 64 128; do cap F_read_$S rgba8unorm $S $S --usage read --nowrite; done
# ShaderWrite (rw) large — expect NO compression flags
cap F_rw_256 rgba8unorm 256 256 --usage rw --nowrite
cap F_rw_512 rgba8unorm 512 512 --usage rw --nowrite
# render-target tiny (already known on) as control
cap F_rt_4 rgba8unorm 4 4 --render --usage rt
# extract just the descriptor line for each
for S in 4 8 16 32 64 128; do
  echo "F_read_$S:"; python3 twiddle.py caps/F_read_$S --fmt rgba8unorm --w $S --h $S 2>&1 | sed -n '2p'
done > analysis/F_trigger.txt
echo "F_rw_256:"  >> analysis/F_trigger.txt; python3 twiddle.py caps/F_rw_256 --fmt rgba8unorm --w 256 --h 256 2>&1 | sed -n '2p' >> analysis/F_trigger.txt
echo "F_rw_512:"  >> analysis/F_trigger.txt; python3 twiddle.py caps/F_rw_512 --fmt rgba8unorm --w 512 --h 512 2>&1 | sed -n '2p' >> analysis/F_trigger.txt
echo "F_rt_4:"    >> analysis/F_trigger.txt; python3 twiddle.py caps/F_rt_4   --fmt rgba8unorm --w 4   --h 4   2>&1 | sed -n '2p' >> analysis/F_trigger.txt
cat analysis/F_trigger.txt

echo "=== G: entropy — noise vs gradient render at 64x64, aux bytes ==="
cap G_grad_64  rgba8unorm 64 64 --render --usage rt
cap G_noise_64 rgba8unorm 64 64 --render --usage rt --noise
python3 - <<'PY' > analysis/G_entropy.txt 2>&1
import glob,sys,os
sys.path.insert(0,'.')
from twiddle import load, find_descriptor
for lbl,dd in [('gradient','caps/G_grad_64'),('noise','caps/G_noise_64')]:
    bos=[load(p) for p in glob.glob(dd+'/*.hex')]
    desc=find_descriptor(bos,64,64); db,doff,w=desc
    base=(w[2]|((w[3]&0xfff)<<32))<<4; sec=(w[4]|((w[5]&0xfff)<<32))<<4
    bo=min([b for b in bos if b['gpu_va']<=base<b['gpu_va']+b['size']],key=lambda b:base-b['gpu_va'])
    d=bo['data']; bo0=base-bo['gpu_va']; so=sec-bo['gpu_va']
    aux=d[so:so+128]
    from collections import Counter
    print(f"== {lbl} == base=0x{base:x} sec=0x{sec:x} (main size=0x{sec-base:x}) aux 128B histogram:")
    print("  aux bytes:", aux.hex())
    print("  aux value counts:", dict(Counter(aux)))
    print("  main first 64B:", d[bo0:bo0+64].hex())
PY
cat analysis/G_entropy.txt

echo "=== H: mip packing — write every level, find offsets ==="
cap H_mip_128 r32uint 128 128 --mips 8
python3 mipmap.py caps/H_mip_128 --w 128 --h 128 > analysis/H_mip_128.txt 2>&1
cat analysis/H_mip_128.txt
cap H_mip_96 r32uint 96 96 --mips 4
python3 mipmap.py caps/H_mip_96 --w 96 --h 96 > analysis/H_mip_96.txt 2>&1
cat analysis/H_mip_96.txt

echo "=== I: split compressibility (block spatial mapping) ==="
cap I_split_64 rgba8unorm 64 64 --render --usage rt --split
python3 - <<'PY' > analysis/I_split.txt 2>&1
import glob,sys; sys.path.insert(0,'.')
from twiddle import load, find_descriptor
bos=[load(p) for p in glob.glob('caps/I_split_64/*.hex')]
db,doff,w=find_descriptor(bos,64,64)
base=(w[2]|((w[3]&0xfff)<<32))<<4; sec=(w[4]|((w[5]&0xfff)<<32))<<4
bo=min([b for b in bos if b['gpu_va']<=base<b['gpu_va']+b['size']],key=lambda b:base-b['gpu_va'])
d=bo['data']; so=sec-bo['gpu_va']; aux=d[so:so+128]
print("aux 128B (left x<32 const=0x03, right noise=0x7f):")
for o in range(0,128,32): print(f"  +{o:04x}:", aux[o:o+32].hex())
print("=> four 32B runs = four 32x32 super-tiles (Morton); 1 aux byte per 8x4 block")
PY
cat analysis/I_split.txt

echo "=== J: r8 16x16 clean (bpp=1 Morton) ==="
cap J_r8_16 r8uint 16 16
python3 twiddle.py caps/J_r8_16 --fmt r8uint --w 16 --h 16 --grid 8 > analysis/J_r8_16.txt 2>&1
sed -n '/element_index =/p' analysis/J_r8_16.txt

echo "=== K: linear bytesPerRow decode (word3 stride field) ==="
: > analysis/K_linear_stride.txt
for WW in 32 64 128 200; do
  cap K_lin_$WW r32uint $WW 16 --linear
  bpr=$(grep -o 'bpr=0x[0-9a-f]*' caps/K_lin_$WW.stdout | head -1)
  w3=$(python3 twiddle.py caps/K_lin_$WW --fmt r32uint --w $WW --h 16 2>&1 | grep -o 'w3=[0-9a-f]*' | head -1)
  echo "W=$WW $bpr $w3  => stride F=word3>>14; bpr=(F+1)*16" >> analysis/K_linear_stride.txt
done
cat analysis/K_linear_stride.txt

echo "=== done run2 ==="
