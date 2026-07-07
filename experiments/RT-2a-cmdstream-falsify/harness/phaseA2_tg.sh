#!/bin/sh
# RT-2a Phase A2 — pin down the CDM threadgroup field under dispatchThreads vs
# dispatchThreadgroups (anomaly: dispatchThreads(16,tg8)->recorded tg16; tg(1,1,1)->(2,4,4)).
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; CAP=0x400
rm -rf capsA2; mkdir -p capsA2
run(){ label="$1"; shift; d="capsA2/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./cvar "$@" --dump > "capsA2/$label.out" 2>&1 || true
}
# dispatchThreads matrix (grid=threads)
run T_g64_t32  --kernel add3 --gx 64  --tgx 32
run T_g16_t8   --kernel add3 --gx 16  --tgx 8
run T_g16_t16  --kernel add3 --gx 16  --tgx 16
run T_g96_t32  --kernel add3 --gx 96  --tgx 32
run T_g100_t10 --kernel add3 --gx 100 --tgx 10
run T_g100_t25 --kernel add3 --gx 100 --tgx 25
run T_g357_t1  --kernel add3 --gx 3 --gy 5 --gz 7 --tgx 1 --tgy 1 --tgz 1
run T_g357_t357 --kernel add3 --gx 3 --gy 5 --gz 7 --tgx 3 --tgy 5 --tgz 7
run T_g6_10_14_t3_5_7 --kernel add3 --gx 6 --gy 10 --gz 14 --tgx 3 --tgy 5 --tgz 7
# dispatchThreadgroups matrix (grid=groups)
run G_g2_t8    --kernel add3 --groups --gx 2 --tgx 8
run G_g2_t32   --kernel add3 --groups --gx 2 --tgx 32
run G_g1_t357  --kernel add3 --groups --gx 1 --gy 1 --gz 1 --tgx 3 --tgy 5 --tgz 7
run G_g4_t7    --kernel add3 --groups --gx 4 --tgx 7
echo "=== CDM records ==="
for l in T_g64_t32 T_g16_t8 T_g16_t16 T_g96_t32 T_g100_t10 T_g100_t25 T_g357_t1 T_g357_t357 T_g6_10_14_t3_5_7 G_g2_t8 G_g2_t32 G_g1_t357 G_g4_t7; do
  f=$(ls capsA2/$l/*va100000b0000_*.hex 2>/dev/null|head -1)
  cfg=$(grep '^CONFIG' capsA2/$l.out|head -1|sed 's/CONFIG //')
  printf "%-18s %s\n" "$l" "$cfg"
  [ -n "$f" ] && python3 cdmread.py "$f" | sed 's/^/    /'
done
echo DONE_PHASE_A2