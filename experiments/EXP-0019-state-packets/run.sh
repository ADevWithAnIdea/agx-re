#!/bin/sh
# EXP-0019 driver — runs on the A18 device under ~/cleanroom_work/exp0019.
# Builds the parametric STATE-PACKET draw harness (svar) + iotrace, captures the
# registered GPU BOs for a change-one-STATE-parameter matrix, and diffs the 0x58000
# fixed-function state pool / 0x18000 VDM / 0x10000130000 USC program on-device.
# Pulls back text + a few curated hexdumps only. CLEAN-ROOM: DATA-TRACE + OWN-SHADER.
set -e
cd "$(dirname "$0")"

echo "=== build ==="
# NOTE: macOS 26 requires the DYLD-inserted interposer to match the process arch.
# The Metal process resolves to arm64e, so BOTH must be built -arch arm64e or the
# captures silently fail ("incompatible architecture ... need arm64e").
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o svar svar.m
echo "built"

DYL=./iotrace.dylib
SMALL=0x4000     # per-BO dump cap for state diffs (fields are all < 0x800)
BIG=0x40000      # larger cap for shader-entry decode (0x10000000000 code BO)

rm -rf caps analysis; mkdir -p caps analysis

run() {  # run CAP LABEL -- <svar args...>
  cap="$1"; label="$2"; shift 2; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_MAX_MAP="$cap" IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./svar "$@" --dump > "caps/$label.stdout" 2>&1 || true
  st=$(grep -E '^(PIPELINE_FAIL|SHADER_FAIL|ARGERR)' "caps/$label.stdout" || true)
  echo "  [$label] ${st:-ok}"
}

# ===== baseline / determinism =====
run $SMALL base   --
run $SMALL base2  --

# ===== Task 1a: DEPTH compare func (all 8) + depth write =====
for f in never less equal lequal greater nequal gequal always; do
  run $SMALL dcmp_$f -- --depth --dcmp $f --dwrite 1
done
run $SMALL dwr_off -- --depth --dcmp always --dwrite 0

# ===== Task 1b: STENCIL =====
run $SMALL st_ref -- --stencil
for f in never less equal lequal greater nequal gequal always; do
  run $SMALL scmp_$f -- --stencil --scmp $f
done
for op in keep zero replace incrclamp decrclamp invert incrwrap decrwrap; do
  run $SMALL spass_$op -- --stencil --spass $op
done
run $SMALL sfail_replace -- --stencil --sfail replace
run $SMALL sfail_invert  -- --stencil --sfail invert
run $SMALL szfail_replace -- --stencil --szfail replace
run $SMALL szfail_invert  -- --stencil --szfail invert
run $SMALL sref_5    -- --stencil --sref 5
run $SMALL sread_0f  -- --stencil --sread 0x0f
run $SMALL swrite_0f -- --stencil --swrite 0x0f
run $SMALL sback     -- --stencil --sback

# ===== Task 2: BLEND =====
run $SMALL bl_ref -- --blend
for f in zero one srccolor 1-srccolor srcalpha 1-srcalpha dstcolor 1-dstcolor \
         dstalpha 1-dstalpha srcalphasat blendcolor 1-blendcolor blendalpha 1-blendalpha; do
  run $SMALL srgb_$f -- --blend --srgb $f
done
run $SMALL drgb_zero     -- --blend --drgb zero
run $SMALL drgb_one      -- --blend --drgb one
run $SMALL drgb_dstcolor -- --blend --drgb dstcolor
run $SMALL salpha_zero -- --blend --salpha zero
run $SMALL salpha_one  -- --blend --salpha one
run $SMALL dalpha_zero -- --blend --dalpha zero
run $SMALL dalpha_one  -- --blend --dalpha one
for op in add sub revsub min max; do
  run $SMALL brgbop_$op -- --blend --brgbop $op
done
for op in add sub revsub min max; do
  run $SMALL balphaop_$op -- --blend --balphaop $op
done
for m in 0 1 2 4 8; do
  run $SMALL wmask_$m -- --blend --wmask $m
done
# dual-source (capability): FS emits index(1); factor codes should appear in the packet
run $SMALL dref -- --dualsrc
run $SMALL dual_src1color   -- --dualsrc --srgb src1color
run $SMALL dual_1src1color  -- --dualsrc --srgb 1-src1color
run $SMALL dual_src1alpha   -- --dualsrc --srgb src1alpha
run $SMALL dual_1src1alpha  -- --dualsrc --srgb 1-src1alpha

# ===== Task 3: RASTERIZER =====
run $SMALL cull_front -- --cull front
run $SMALL cull_back  -- --cull back
run $SMALL front_ccw  -- --front ccw
run $SMALL fill_lines -- --fill lines
# depth-related raster (paired with dcmp_always = --depth --dcmp always --dwrite 1)
run $SMALL clip_clamp -- --depth --dcmp always --dwrite 1 --clip clamp
run $SMALL dbias_zero -- --depth --dcmp always --dwrite 1 --dbias 0
run $SMALL dbias_c    -- --depth --dcmp always --dwrite 1 --dbias 1
run $SMALL dbias_s    -- --depth --dcmp always --dwrite 1 --dslope 1
run $SMALL dbias_k    -- --depth --dcmp always --dwrite 1 --dclamp 1
run $SMALL dbias_all  -- --depth --dcmp always --dwrite 1 --dbias 2 --dslope 3 --dclamp 0.5

# ===== Task 4: shader-entry / USC (big cap). NB: the "big" shaders in svar.m use a
# 1e-9 (non-zero) coefficient so the extra work survives the compiler's dead-code
# elimination -- otherwise VS/FS "big" collapse to the small shader and no shift shows.
run $BIG base_big -- --vshader small --fshader small
run $BIG vbig     -- --vshader big
run $BIG fbig     -- --fshader big

# ===== Task 1b (mask confirm): stencil read/write masks & ref with ACTIVE stencil.
# (A default stencil -- always/keep -- is emitted DISABLED, so masks don't appear;
#  an active compare+op is required to see the mask bytes.)
run $SMALL sa_ref  -- --stencil --scmp less --spass replace
run $SMALL sa_rd0f -- --stencil --scmp less --spass replace --sread 0x0f
run $SMALL sa_rd33 -- --stencil --scmp less --spass replace --sread 0x33
run $SMALL sa_wr0f -- --stencil --scmp less --spass replace --swrite 0x0f
run $SMALL sa_wr55 -- --stencil --scmp less --spass replace --swrite 0x55
run $SMALL sa_ref5 -- --stencil --scmp less --spass replace --sref 0x5a

echo "=== on-device diffs ==="
# helper: diff VARIANT vs REF across all paired BOs (noise floor is 0 for identical cfg)
d() { python3 bodiff.py "caps/$1" "caps/$2" --maxlen 0x800 > "analysis/diff_$2.txt" 2>&1 || true; }

d base base2
for f in never less equal lequal greater nequal gequal always; do d dcmp_never dcmp_$f; done
d dcmp_always dwr_off
for f in never less equal lequal greater nequal gequal always; do d st_ref scmp_$f; done
for op in keep zero replace incrclamp decrclamp invert incrwrap decrwrap; do d st_ref spass_$op; done
for v in sfail_replace sfail_invert szfail_replace szfail_invert sref_5 sread_0f swrite_0f sback; do d st_ref $v; done
for f in zero one srccolor 1-srccolor srcalpha 1-srcalpha dstcolor 1-dstcolor dstalpha 1-dstalpha srcalphasat blendcolor 1-blendcolor blendalpha 1-blendalpha; do d bl_ref srgb_$f; done
for v in drgb_zero drgb_one drgb_dstcolor salpha_zero salpha_one dalpha_zero dalpha_one; do d bl_ref $v; done
for op in add sub revsub min max; do d bl_ref brgbop_$op; d bl_ref balphaop_$op; done
for m in 0 1 2 4 8; do d bl_ref wmask_$m; done
for v in dual_src1color dual_1src1color dual_src1alpha dual_1src1alpha; do d dref $v; done
for v in cull_front cull_back front_ccw fill_lines; do d base $v; done
for v in clip_clamp dbias_c dbias_s dbias_k dbias_all; do d dcmp_always $v; done
d dbias_zero dbias_c   # cleaner bias isolation (ref calls setDepthBias 0,0,0)
d dbias_zero dbias_s
d dbias_zero dbias_k
# shader-entry
python3 bodiff.py caps/base_big caps/vbig --va 0x10000130000 > analysis/diff_vbig_usc.txt 2>&1 || true
python3 bodiff.py caps/base_big caps/fbig --va 0x10000130000 > analysis/diff_fbig_usc.txt 2>&1 || true
# active-stencil mask confirmation
for v in sa_rd0f sa_rd33 sa_wr0f sa_wr55 sa_ref5; do
  python3 bodiff.py caps/sa_ref caps/$v --va 0x58000 --maxlen 0x60 > analysis/diff_$v.txt 2>&1 || true
done
python3 shptr.py caps/base_big > analysis/shptr_base.txt 2>&1 || true
python3 shptr.py caps/vbig     > analysis/shptr_vbig.txt 2>&1 || true
python3 shptr.py caps/fbig     > analysis/shptr_fbig.txt 2>&1 || true
python3 bograph.py caps/base_big > analysis/graph_base.txt 2>&1 || true

# curated hexdumps of the key control BOs for the reference configs (text, trimmed)
mkdir -p hex
keep_bo() { # keep_bo CAP VA OUT
  f=$(ls caps/$1/bo_sigusr1_*_va$2_*.hex 2>/dev/null | head -1)
  [ -n "$f" ] && head -140 "$f" > "hex/$3.hex" 2>/dev/null || true
}
# depth+stencil reference pool
keep_bo st_ref 58000 stref_58000
keep_bo st_ref 18000 stref_18000
keep_bo st_ref 10000130000 stref_usc
keep_bo st_ref 10000110000 stref_attach
keep_bo st_ref 10000120000 stref_120000
# depth-only reference pool
keep_bo dcmp_always 58000 depth_58000
keep_bo dcmp_always 18000 depth_18000
# blend reference pool
keep_bo bl_ref 58000 blend_58000
keep_bo bl_ref 18000 blend_18000
keep_bo bl_ref 10000120000 blend_120000
# plain base pool + USC + VDM + shader code
keep_bo base 58000 base_58000
keep_bo base 18000 base_18000
keep_bo base 68000 base_68000
keep_bo base_big 10000130000 base_usc
keep_bo base_big 10000000000 base_code
keep_bo vbig    10000130000 vbig_usc
keep_bo fbig    10000130000 fbig_usc

# selector histogram (draw BO count sanity)
{ echo "== base =="; grep -cE '^CALL' caps/base.trace; \
  grep -oE 'sel=[0-9]+' caps/base.trace | sort | uniq -c | sort -rn; } > analysis/selhist.txt 2>&1 || true

echo "=== done; captures: $(ls caps | grep -c / 2>/dev/null || ls -d caps/*/ | wc -l) ==="
ls analysis | wc -l
