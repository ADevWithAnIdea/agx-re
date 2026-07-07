#!/bin/sh
# EXP-0024 driver — runs on the A18 device under ~/cleanroom_work/exp0024.
# Builds gvar (graphics) + cvar2 (compute) + iotrace (arm64e), captures registered GPU BOs
# for three change-one-parameter matrices, and diffs on-device:
#   G-3: USC shader-entry pointer  (pad / vsz / fsz sweep; code BO 0x10000000000 + USC 0x130000)
#   G-7: PPP present/emission grammar (state-group on/off; VDM 0x18000 + FF pool 0x58000)
#   G-8: CDM +0x00 config word + threadgroup-memory-size field (tgmem/config kernels; all BOs)
# CLEAN-ROOM: DATA-TRACE + OWN-SHADER. Pulls back text + trimmed hexdumps only.
set -e
cd "$(dirname "$0")"

echo "=== build (arm64e; macOS 26 requires arch-match for the DYLD interposer) ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o gvar  gvar.m
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o cvar2 cvar2.m
echo built

DYL=./iotrace.dylib
BIG=0x80000     # covers code BO 0x10000 fully
SMALL=0x8000

rm -rf caps ana; mkdir -p caps ana

grun(){ cap="$1"; label="$2"; shift 2; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_MAX_MAP="$cap" IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./gvar "$@" --dump > "caps/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E 'MAGIC|status=|FAIL' caps/$label.out | tr '\n' ' ')"; }
crun(){ cap="$1"; label="$2"; shift 2; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_MAX_MAP="$cap" IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./cvar2 "$@" --dump > "caps/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E 'staticThreadgroup|status=|FAIL|UNKNOWN' caps/$label.out | tr '\n' ' ')"; }

echo "=== G-3: USC shader-entry (pad / vsz / fsz VA-shift sweep) ==="
grun $BIG g3_base -- --pad 0 --vsz 0 --fsz 0
grun $BIG g3_base2 -- --pad 0 --vsz 0 --fsz 0        # determinism
grun $BIG g3_pad1 -- --pad 1
grun $BIG g3_pad2 -- --pad 2
grun $BIG g3_pad3 -- --pad 3
grun $BIG g3_pad4 -- --pad 4
grun $BIG g3_vsz2 -- --vsz 2
grun $BIG g3_vsz4 -- --vsz 4
grun $BIG g3_vsz8 -- --vsz 8
grun $BIG g3_fsz2 -- --fsz 2
grun $BIG g3_fsz4 -- --fsz 4
grun $BIG g3_fsz8 -- --fsz 8

echo "=== G-7: PPP present/emission grammar (state-group on/off) ==="
grun $SMALL g7_base --
grun $SMALL g7_depth -- --depth --dcmp less
grun $SMALL g7_depthonly -- --depth --dcmp always --dwrite 0
grun $SMALL g7_stencil -- --stencil --scmp less --spass replace
grun $SMALL g7_ds -- --depth --dcmp less --stencil --scmp less --spass replace
grun $SMALL g7_blend -- --blend
grun $SMALL g7_blend_depth -- --blend --depth --dcmp less
grun $SMALL g7_cullback -- --cull back
grun $SMALL g7_all -- --depth --dcmp less --stencil --scmp less --spass replace --blend --cull back

echo "=== G-8: CDM config word + threadgroup-memory-size ==="
crun $SMALL c8_add3 -- --kernel add3
crun $SMALL c8_heavy -- --kernel heavy
crun $SMALL c8_atom -- --kernel atom
crun $SMALL c8_barr -- --kernel barr
crun $SMALL c8_simd -- --kernel simd
# dynamic tg-mem size sweep (same kernel, only setThreadgroupMemoryLength changes)
crun $BIG c8_dyn256   -- --kernel tgdyn --tgmem 256
crun $BIG c8_dyn1k    -- --kernel tgdyn --tgmem 1024
crun $BIG c8_dyn4k    -- --kernel tgdyn --tgmem 4096
crun $BIG c8_dyn16k   -- --kernel tgdyn --tgmem 16384
crun $BIG c8_dyn32k   -- --kernel tgdyn --tgmem 32768
# static tg-mem size sweep (compile-time array size)
crun $BIG c8_st64   -- --kernel tgs64
crun $BIG c8_st256  -- --kernel tgs256
crun $BIG c8_st1024 -- --kernel tgs1024
crun $BIG c8_st4096 -- --kernel tgs4096
crun $BIG c8_st8192 -- --kernel tgs8192

echo "=== on-device diffs ==="
D(){ python3 bodiff.py "caps/$1" "caps/$2" > "ana/diff_$2.txt" 2>&1 || true; }
# G-3 determinism + correlation
D g3_base g3_base2
for v in g3_pad1 g3_pad2 g3_pad3 g3_pad4 g3_vsz2 g3_vsz4 g3_vsz8 g3_fsz2 g3_fsz4 g3_fsz8; do D g3_base $v; done
python3 bodiff.py caps/g3_base caps/g3_pad1 --va 0x10000130000 > ana/usc_pad1.txt 2>&1 || true
python3 bodiff.py caps/g3_base caps/g3_pad2 --va 0x10000130000 > ana/usc_pad2.txt 2>&1 || true
python3 bodiff.py caps/g3_base caps/g3_vsz4 --va 0x10000130000 > ana/usc_vsz4.txt 2>&1 || true
python3 bodiff.py caps/g3_base caps/g3_fsz4 --va 0x10000130000 > ana/usc_fsz4.txt 2>&1 || true
for v in g3_pad1 g3_pad2 g3_pad3 g3_pad4 g3_vsz2 g3_vsz4 g3_vsz8 g3_fsz2 g3_fsz4 g3_fsz8; do
  python3 magloc.py --corr caps/g3_base caps/$v > ana/corr_$v.txt 2>&1 || true
done
python3 magloc.py caps/g3_base caps/g3_pad1 caps/g3_pad2 caps/g3_vsz4 caps/g3_fsz4 > ana/magloc.txt 2>&1 || true

# G-7 VDM header + FF pool present-mask
for v in g7_depth g7_depthonly g7_stencil g7_ds g7_blend g7_blend_depth g7_cullback g7_all; do
  python3 bodiff.py caps/g7_base caps/$v --va 0x18000 --maxlen 0x100 > ana/vdm_$v.txt 2>&1 || true
  python3 bodiff.py caps/g7_base caps/$v --va 0x58000 --maxlen 0x120 >> ana/vdm_$v.txt 2>&1 || true
done

# G-8 config word (launch desc 0x100000b0000 +0x00) + tg-mem hunt (all BOs)
for v in c8_heavy c8_atom c8_barr c8_simd; do D c8_add3 $v; done
# dynamic tg-mem: diff across sizes over ALL BOs to find where the size lands
python3 bodiff.py caps/c8_dyn256 caps/c8_dyn1k  > ana/tgdyn_256_1k.txt 2>&1 || true
python3 bodiff.py caps/c8_dyn256 caps/c8_dyn4k  > ana/tgdyn_256_4k.txt 2>&1 || true
python3 bodiff.py caps/c8_dyn256 caps/c8_dyn16k > ana/tgdyn_256_16k.txt 2>&1 || true
python3 bodiff.py caps/c8_dyn256 caps/c8_dyn32k > ana/tgdyn_256_32k.txt 2>&1 || true
python3 bodiff.py caps/c8_st64 caps/c8_st1024   > ana/tgstat_64_1k.txt 2>&1 || true
python3 bodiff.py caps/c8_st64 caps/c8_st8192   > ana/tgstat_64_32k.txt 2>&1 || true
python3 bodiff.py caps/c8_add3 caps/c8_st1024   > ana/tgstat_add3_1k.txt 2>&1 || true

# curated hexdumps
mkdir -p hex
kb(){ f=$(ls caps/$1/bo_sigusr1_*_va$2_*.hex 2>/dev/null | head -1); [ -n "$f" ] && head -n "${4:-200}" "$f" > "hex/$3.hex" 2>/dev/null || true; }
kb g3_base 10000130000 g3_usc_base
kb g3_base 10000000000 g3_code_base 400
kb g3_pad1 10000130000 g3_usc_pad1
kb g3_pad2 10000130000 g3_usc_pad2
kb g3_vsz4 10000130000 g3_usc_vsz4
kb g3_fsz4 10000130000 g3_usc_fsz4
kb g7_base 18000 g7_vdm_base
kb g7_ds   18000 g7_vdm_ds
kb g7_all  18000 g7_vdm_all
kb g7_base 58000 g7_ff_base
kb g7_all  58000 g7_ff_all
kb c8_add3 100000b0000 c8_cdm_add3
kb c8_heavy 100000b0000 c8_cdm_heavy
kb c8_dyn256 100000b0000 c8_cdm_dyn256
kb c8_dyn32k 100000b0000 c8_cdm_dyn32k
kb c8_st64 100000b0000 c8_cdm_st64
kb c8_st8192 100000b0000 c8_cdm_st8192
kb c8_dyn32k 100000e0000 c8_arg_dyn32k
kb c8_dyn32k 10000080000 c8_ctl_dyn32k

echo "=== selector histogram (sanity) ==="
{ echo "== g3_base =="; grep -cE '^CALL' caps/g3_base.trace; echo "== c8_add3 =="; grep -cE '^CALL' caps/c8_add3.trace; } > ana/selhist.txt 2>&1 || true
echo "=== done. caps=$(ls -d caps/*/ 2>/dev/null | wc -l) ana=$(ls ana 2>/dev/null | wc -l) ==="
