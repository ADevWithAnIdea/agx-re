#!/bin/sh
# RT-11 red-team 2nd-pass driver. Runs on the A18 device under ~/cleanroom_work/rt11.
# Confirms RT-2a/RT-4 corrections + hunts remaining holes. change-one-param + byte-diff.
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib
rm -rf caps analysis hex; mkdir -p caps analysis hex

CAP=0x800
rund(){ # rund LABEL BIN -- args...    (draw record cap 0x800)
  label="$1"; bin="$2"; shift 2; [ "$1" = "--" ] && shift
  d="caps/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./$bin "$@" --dump > "caps/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E '^(CONFIG|SUBMIT|PIXEL|PIPELINE_FAIL)' caps/$label.out | head -2 | tr '\n' ' ')"
}
runbig(){ # like rund but larger map cap (arg buffer / tiler heap)
  label="$1"; bin="$2"; shift 2; [ "$1" = "--" ] && shift
  d="caps/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=0x2000 IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./$bin "$@" --dump > "caps/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E '^(CONFIG|SUBMIT|PIXEL|PIPELINE_FAIL)' caps/$label.out | head -2 | tr '\n' ' ')"
}

echo "===== PHASE 1: indexed VDM record shift (0x18000) ====="
rund i_ni      idx11 --
rund i_ni2     idx11 --
rund i_ni_inst idx11 -- --inst 7
rund i_ni_bi   idx11 -- --inst 7 --baseinst 5
rund i_ni_st   idx11 -- --start 2
rund i_u16     idx11 -- --indexed --itype u16
rund i_u32     idx11 -- --indexed --itype u32
rund i_u16_i3  idx11 -- --indexed --itype u16 --inst 3
rund i_u32_i3  idx11 -- --indexed --itype u32 --inst 3
rund i_u16_bv  idx11 -- --indexed --itype u16 --basevert 9
rund i_u16_bi  idx11 -- --indexed --itype u16 --baseinst 5
rund i_u16_off idx11 -- --indexed --itype u16 --idxoff 4
rund i_u16_ic9 idx11 -- --indexed --itype u16 --icount 9
rund i_combo   idx11 -- --indexed --itype u32 --inst 4 --basevert 3 --baseinst 6 --icount 9

echo "===== PHASE 2: USC sampler stride (arg buffer 0x10000248000) ====="
runbig s_t1s0 smp11 -- --tex 1 --smp 0
runbig s_t1s1 smp11 -- --tex 1 --smp 1
runbig s_t1s2 smp11 -- --tex 1 --smp 2
runbig s_t1s5 smp11 -- --tex 1 --smp 5
runbig s_t1s8 smp11 -- --tex 1 --smp 8
runbig s_t2s0 smp11 -- --tex 2 --smp 0
runbig s_t5s0 smp11 -- --tex 5 --smp 0
runbig s_t8s0 smp11 -- --tex 8 --smp 0
runbig s_t2s5 smp11 -- --tex 2 --smp 5
runbig s_t8s8 smp11 -- --tex 8 --smp 8
runbig s_t3s2 smp11 -- --tex 3 --smp 2

echo "===== PHASE 3: sample positions userspace @+0x40 (default vs custom) ====="
runbig sp2_def sp11 -- --samples 2 --mode default
runbig sp2_cus sp11 -- --samples 2 --mode custom
runbig sp4_def sp11 -- --samples 4 --mode default
runbig sp4_cus sp11 -- --samples 4 --mode custom

echo "===== PHASE 4: MRT feasibility + tiler-heap stride (0x10000018200) ====="
runbig m_1_8   mrt11 -- --mrt 1 --fmt bgra8
runbig m_4_8   mrt11 -- --mrt 4 --fmt bgra8
runbig m_8_8   mrt11 -- --mrt 8 --fmt bgra8
runbig m_1_32f mrt11 -- --mrt 1 --fmt rgba32f
runbig m_4_32f mrt11 -- --mrt 4 --fmt rgba32f
runbig m_8_32f mrt11 -- --mrt 8 --fmt rgba32f
runbig m_8_16f mrt11 -- --mrt 8 --fmt rgba16f

echo "===== PHASE 5: threadgroup-memory (32KiB) budget (shader BO tgmem field) ====="
rund tg_m256   cdm11 -- --gx 64 --tgx 32 --tgmem 256
rund tg_m16k   cdm11 -- --gx 64 --tgx 32 --tgmem 16384
rund tg_m32k   cdm11 -- --gx 64 --tgx 32 --tgmem 32768
# over-budget attempts (expect reject or clamp)
cdm11_over(){ ./cdm11 --gx 64 --tgx 32 --tgmem $1 > caps/tgover_$1.out 2>&1 || true;
  echo "  [tgover $1] $(grep -E 'SUBMIT|PIPELINE_FAIL|PSO' caps/tgover_$1.out | tr '\n' ' ')"; }
cdm11_over 32769
cdm11_over 49152
cdm11_over 65536

echo "===== PHASE 6: CDM effective threadgroup mapping (0x100000b0000) ====="
rund c_tg1   cdm11 -- --gx 256 --tgx 1
rund c_tg2   cdm11 -- --gx 256 --tgx 2
rund c_tg4   cdm11 -- --gx 256 --tgx 4
rund c_tg8   cdm11 -- --gx 256 --tgx 8
rund c_tg10  cdm11 -- --gx 256 --tgx 10
rund c_tg16  cdm11 -- --gx 256 --tgx 16
rund c_tg25  cdm11 -- --gx 256 --tgx 25
rund c_tg32  cdm11 -- --gx 256 --tgx 32
rund c_tg48  cdm11 -- --gx 256 --tgx 48
rund c_tg64  cdm11 -- --gx 256 --tgx 64
rund c_tg111 cdm11 -- --gx 512 --tgx 100
rund c_tg2d  cdm11 -- --gx 64 --gy 64 --tgx 3 --tgy 5
rund c_tg111_1 cdm11 -- --gx 64 --gy 64 --gz 8 --tgx 1 --tgy 1 --tgz 1

echo "===== PHASE 7: state-packet regression (0x58000 / 0x18000 / 0x68000) ====="
rund st_base  state11 --
rund st_dless state11 -- --depth --dcmp less
rund st_dgt   state11 -- --depth --dcmp greater
rund st_sten  state11 -- --depth --stencil --sref 3
rund st_cullb state11 -- --cull back
rund st_clamp state11 -- --clip clamp
rund st_blend state11 -- --blend
rund st_ml    state11 -- --mlcolor
rund st_1024  state11 -- --w 1024 --h 1024
rund st_777   state11 -- --w 777 --h 333
rund st_occ   state11 -- --occlusion
runbig st_ts  state11 -- --timestamp

echo "===== DIFFS ====="
D(){ python3 bodiff.py "caps/$1" "caps/$2" --va "$3" --maxlen "${4:-0x120}" > "analysis/$5.txt" 2>&1 || true; }
# indexed shift
D i_ni i_ni2 0x18000 0x120 vdm_determinism
D i_ni i_u16 0x18000 0x120 vdm_ni_to_u16
D i_u16 i_u32 0x18000 0x120 vdm_u16_to_u32
D i_u16 i_u16_i3 0x18000 0x120 vdm_idx_inst
D i_u16 i_u16_bv 0x18000 0x120 vdm_idx_basevert
D i_u16 i_u16_off 0x18000 0x120 vdm_idx_offset
D i_u16 i_u16_ic9 0x18000 0x120 vdm_idx_count
D i_ni i_ni_inst 0x18000 0x120 vdm_ni_inst
D i_ni i_ni_bi 0x18000 0x120 vdm_ni_baseinst
# state regression
D st_base st_dless 0x58000 0x100 st_depth_less
D st_base st_dgt 0x58000 0x100 st_depth_greater
D st_base st_sten 0x58000 0x100 st_stencil
D st_base st_cullb 0x58000 0x100 st_cull
D st_base st_clamp 0x58000 0x100 st_clip
D st_dless st_dgt 0x58000 0x100 st_depth_cmp

echo "===== SAMPLE-POSITION full-BO diffs (find the client BO) ====="
for pair in "sp2_def sp2_cus" "sp4_def sp4_cus"; do
  set -- $pair
  python3 bodiff.py "caps/$1" "caps/$2" --maxlen 0x400 > "analysis/allbo_$2.txt" 2>&1 || true
done

echo "===== SAMPLE-POSITION kernel-route falsification (trace CALL-structure diff) ====="
# Any positions routed via an ioctl would change the CALL sequence (selectors / struct
# sizes). Compare address-free CALL structure default vs custom; also count IN.struct
# payload bytes to see if custom pushes any EXTRA struct data to the kernel.
for pair in "sp2_def sp2_cus" "sp4_def sp4_cus"; do
  set -- $pair
  sed -nE 's/^CALL seq=[0-9]+ (fn=[^ ]+ )conn=[0-9a-f]+ (class=[^ ]+ sel=[0-9]+\([^)]*\) inScalarCnt=[0-9]+ inStructCnt=[0-9]+).*/\1\2/p' "caps/$1.trace" > "analysis/callstruct_$1.txt" 2>/dev/null || true
  sed -nE 's/^CALL seq=[0-9]+ (fn=[^ ]+ )conn=[0-9a-f]+ (class=[^ ]+ sel=[0-9]+\([^)]*\) inScalarCnt=[0-9]+ inStructCnt=[0-9]+).*/\1\2/p' "caps/$2.trace" > "analysis/callstruct_$2.txt" 2>/dev/null || true
  diff "analysis/callstruct_$1.txt" "analysis/callstruct_$2.txt" > "analysis/tracediff_$2.txt" 2>&1 || true
  in1=$(grep -c 'IN.struct' "caps/$1.trace" 2>/dev/null || echo 0)
  in2=$(grep -c 'IN.struct' "caps/$2.trace" 2>/dev/null || echo 0)
  echo "  $2: CALL-structure diff = $(grep -c '^[<>]' analysis/tracediff_$2.txt) lines; IN.struct count def=$in1 cus=$in2"
done

echo "===== CURATED HEX ====="
kb(){ f=$(ls caps/$1/*va${2}_*.hex 2>/dev/null | head -1); [ -n "$f" ] && sed -n "${3:-1p;/^00000040:/,/^00000100:/p}" "$f" > "hex/$4.hex" 2>/dev/null || echo "no $1 va$2"; }
# VDM records
kb i_ni    18000 '1p;/^00000040:/,/^00000100:/p' vdm_ni
kb i_u16   18000 '1p;/^00000040:/,/^00000100:/p' vdm_u16
kb i_u32   18000 '1p;/^00000040:/,/^00000100:/p' vdm_u32
kb i_u16_i3 18000 '1p;/^00000040:/,/^00000100:/p' vdm_u16_i3
kb i_u32_i3 18000 '1p;/^00000040:/,/^00000100:/p' vdm_u32_i3
kb i_combo  18000 '1p;/^00000040:/,/^00000100:/p' vdm_combo
# arg buffers for sampler stride
for l in s_t1s0 s_t1s1 s_t1s2 s_t1s5 s_t1s8 s_t2s0 s_t5s0 s_t8s0 s_t2s5 s_t8s8 s_t3s2; do
  kb $l 10000248000 '1p;/^00000480:/,/^00000700:/p' argbuf_$l
done
# sample-pattern BOs
kb sp4_def 100000e8000 '1p;/^00000040:/,/^000000a0:/p' sp4_def_e8
kb sp4_cus 100000e8000 '1p;/^00000040:/,/^000000a0:/p' sp4_cus_e8
kb sp2_def 100000e0000 '1p;/^00000040:/,/^00000080:/p' sp2_def_e0
kb sp2_cus 100000e0000 '1p;/^00000040:/,/^00000080:/p' sp2_cus_e0
# tiler heap for MRT stride
kb m_8_8   10000018200 '1p;/^00000000:/,/^00000120:/p' heap_mrt8_bgra8
kb m_8_32f 10000018200 '1p;/^00000000:/,/^00000120:/p' heap_mrt8_32f
# CDM records for effective-tg
for l in c_tg1 c_tg2 c_tg4 c_tg8 c_tg10 c_tg16 c_tg25 c_tg32 c_tg48 c_tg64 c_tg111 c_tg2d c_tg111_1; do
  kb $l 100000b0000 '1p;/^00000000:/,/^00000040:/p' cdm_$l
done
# shader BO tgmem field
for l in tg_m256 tg_m16k tg_m32k; do
  kb $l 10000090000 '1p;/^00000040:/,/^00000060:/p' tgmem_$l
done
# tile grid for size regression
for l in st_base st_1024 st_777; do
  f=$(ls caps/$l/*va68000_*.hex 2>/dev/null|head -1); [ -n "$f" ] && grep -E '^0000090[048]:' "$f" > hex/tilegrid_$l.txt 2>/dev/null || true
done

echo "===== CDM effective-tg summary ====="
{ echo "label  reqTG  effTG(+0x1c/+0x20/+0x24)  execWidth";
  for l in c_tg1 c_tg2 c_tg4 c_tg8 c_tg10 c_tg16 c_tg25 c_tg32 c_tg48 c_tg64 c_tg111 c_tg2d c_tg111_1; do
    req=$(grep '^CONFIG' caps/$l.out|sed -E 's/.*tg=\(([0-9,]+)\).*/\1/')
    f=$(ls caps/$l/*va100000b0000_*.hex 2>/dev/null|head -1)
    line=$(sed -n '/^00000010:/p' "$f" 2>/dev/null)   # +0x10 line has +0x1c..+0x24? print +0x10 and +0x20 rows
    row1=$(sed -n '/^00000010:/p' "$f" 2>/dev/null); row2=$(sed -n '/^00000020:/p' "$f" 2>/dev/null)
    printf "%-8s req=%-10s r10=[%s] r20=[%s]\n" "$l" "$req" "$row1" "$row2"
  done; } > analysis/cdm_efftg_summary.txt
cat analysis/cdm_efftg_summary.txt

echo "===== status summary ====="
grep -H -E 'SUBMIT done|PIPELINE_FAIL' caps/*.out | sed -E 's#caps/##' > analysis/status.txt
cat analysis/status.txt
echo DONE_RT11
