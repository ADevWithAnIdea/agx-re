#!/bin/sh
# EXP-O2G driver — runs on the A18 (G17P) device under ~/cleanroom_work/exp_o2g.
# Part 1: shader printf/os_log lowering (pf.m + shdump_log byte-diff + iotrace log-buffer race-dump).
# Part 2: mesh-draw-into-ICB (micb.m; captures the 0x70000600 mesh record inside the ICB, or reject).
# Part 3: compression x mipmap / NPOT (cmip.m + texdesc.py descriptor+allocation decode).
# Reuses read-only tools/iotrace (interposer) + tools/shdump (own-shader extractor; shdump_log.m is a
# local copy with MTLCompileOptions.enableLogging=YES). Text out only.
# Clean-room: OWN-SHADER + DATA-TRACE + HW-PROBE. No Apple binary disassembled. See ../CLAUDE.md.
set -u
cd "$(dirname "$0")"

echo "=== build ==="
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation || exit 1
clang -fobjc-arc -framework Metal -framework Foundation -o pf         pf.m         || exit 1
clang -fobjc-arc -framework Metal -framework Foundation -o micb       micb.m       || exit 1
clang -fobjc-arc -framework Metal -framework Foundation -o cmip       cmip.m       || exit 1
clang -fobjc-arc -framework Metal -framework Foundation -o shdump_log shdump_log.m || exit 1
echo built
DYL=./iotrace.dylib
rm -rf caps raw; mkdir -p caps raw raw/caps_curated

########################## PART 1: shader printf / os_log ##########################
echo "=== PART 1: shader printf (os_log via <metal_logging>; enableLogging=YES) ==="
# 1a. end-to-end decode (log handler prints the runtime-decoded strings)
./pf --grid 4 --tg 4 2>&1 | grep LOGHANDLER > raw/pf_decoded_strings.txt || true
# 1b. RACE capture: kernel logs then spins; SIGUSR1-spam snapshots the log buffer BEFORE the
#     completion drain consumes it. IOTRACE_DUMP_PERSIG=1 -> one dir per snapshot. The race is
#     probabilistic, so retry until a snapshot caught the marker (records mid-flight).
got=0
for attempt in 1 2 3 4 5 6 7 8; do
  rm -rf caps/pf_race
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=caps/pf_race IOTRACE_DUMP_PERSIG=1 \
    DYLD_INSERT_LIBRARIES=$DYL ./pf --grid 4 --tg 4 --bufsize 0x40000 --spin 400000000 --pings 250 --nohandler --dump \
    > raw/pf_race.out 2>&1 || true
  for dd in caps/pf_race/dump*/; do
    if grep -q "efcdab51" "$dd"/*va10000030000*.hex 2>/dev/null; then
      python3 pflog.py "$dd" > raw/part1_pflog_records.txt 2>&1
      cp "$dd"/*va10000030000*.hex raw/caps_curated/pf_logbuffer.hex 2>/dev/null
      got=1; break
    fi
  done
  [ "$got" = 1 ] && echo "  part1 race caught records on attempt $attempt" && break
done
[ "$got" = 0 ] && echo "  WARN: race did not catch log records (retry run.sh)"
# 1c. shader-side lowering: os_log emit is a call to a compiler helper; format-string-length
#     INdependent (id/offset reference, not inline byte copy). Discriminate with two format lengths.
./shdump_log -o pf_lenA.bin pf_lenA.metal 2>/dev/null
./shdump_log -o pf_lenB.bin pf_lenB.metal 2>/dev/null
python3 agxparse.py pf_lenA.bin --stage compute --extract-hex > pf_lenA.main.hex 2>/dev/null
python3 agxparse.py pf_lenB.bin --stage compute --extract-hex > pf_lenB.main.hex 2>/dev/null
{ echo "# os_log lowering — AGX image sections (note: l___air_impl_os_log helper subroutine)";
  python3 agxparse.py pf_lenB.bin 2>&1 | head -30; echo;
  echo "# format-length discriminator (same 1 arg): _agc.main size is IDENTICAL ->";
  echo "  lenA fmt \"A%u\" (3 ch):  $(tr -d '\n' < pf_lenA.main.hex | wc -c) hexchars";
  echo "  lenB fmt 40*A+%u (42 ch): $(tr -d '\n' < pf_lenB.main.hex | wc -c) hexchars";
  echo "# -> shader references the format string by id/offset (in AGX constant data), not inline copy";
  echo "# format-string image location (AGX vs AIR):"; python3 imgloc.py pf_lenB.bin;
} > raw/part1_shader_lowering.txt 2>&1

########################## PART 2: mesh-in-ICB ##########################
echo "=== PART 2: mesh-in-ICB ==="
./micb --icbn 1  > raw/micb_tg.out 2>&1 || true
./micb --threads > raw/micb_threads.out 2>&1 || true
./micb --icbn 2  > raw/micb_n2.out 2>&1 || true
rm -rf caps/micb caps/micb2
IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=caps/micb  DYLD_INSERT_LIBRARIES=$DYL ./micb --icbn 1 --dump > /dev/null 2>&1 || true
IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=caps/micb2 DYLD_INSERT_LIBRARIES=$DYL ./micb --icbn 2 --dump > /dev/null 2>&1 || true
{ echo "## mesh-in-ICB record scan (icbn=1): expect 0x70000600 (mesh), NOT 0x61c4 / 0x6404";
  python3 dumpscan.py caps/micb  --u32 0x70000600 0x000061c4 0x00006404;
  echo; echo "## icbn=2 record scan"; python3 dumpscan.py caps/micb2 --u32 0x70000600;
  echo; echo "## command-count word diff icbn1 vs icbn2 (VDM/tiler 0x18000)";
  python3 bodiff.py caps/micb caps/micb2 --va 0x18000 --maxlen 0x240 | head -8;
} > raw/part2_meshicb_records.txt 2>&1
sed -n '2,20p' caps/micb/*va18000*.hex > raw/caps_curated/meshicb_tiler_0x18000.hex 2>/dev/null

########################## PART 3: compression x mipmap / NPOT ##########################
echo "=== PART 3: compression x mipmap / NPOT ==="
capdesc() { # capdesc LABEL FMT BPP SPECS
  label=$1; fmt=$2; bpp=$3; specs=$4; d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL \
    ./cmip --fmt "$fmt" --usage rt --specs "$specs" --dump > "raw/$label.out" 2>&1 || true
  python3 texdesc.py "$d" --fmt "$fmt" --bpp "$bpp" --specs "$specs" > "raw/part3_$label.desc.txt" 2>&1
  echo "  $label done"
}
capdesc mips  rgba8unorm 4  "128x128x1,128x128x8,128x128x4,64x64x7,256x256x1"
capdesc npot1 rgba8unorm 4  "4x4x1,8x8x1,16x16x1,32x32x1,9x9x1,10x10x1,12x12x1,15x15x1"
capdesc npot2 rgba8unorm 4  "17x17x1,20x20x1,24x24x1,16x8x1,8x16x1,32x8x1,16x12x1,16x4x1"
capdesc npot3 rgba8unorm 4  "16x15x1,15x16x1,17x16x1,16x17x1,4x16x1,8x32x1,12x16x1,31x31x1"
capdesc fmt32 rgba32f    16 "2x2x1,4x4x1,8x8x1,16x16x1,17x17x1"
capdesc fmt16 rgba16f    8  "4x4x1,8x8x1,16x16x1"
capdesc fmt8  r8unorm    1  "8x8x1,16x16x1,32x32x1,64x64x1"

echo "=== done. see raw/ ==="; ls raw/
