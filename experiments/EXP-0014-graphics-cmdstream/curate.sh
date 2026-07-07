#!/bin/sh
cd ~/cleanroom_work/exp0014
mkdir -p curated
# curated control-plane diffs (clean, key BOs only)
D=curated/key_diffs.txt
: > $D
CTRL_PARAM="0x18000 0x58000 0x68000 0x10000100000 0x10000110000 0x10000120000"
echo "### DRAW-PARAMETER DIFFS (VDM BO 0x18000) ###" >> $D
for l in prim_line prim_point prim_strip inst4 verts6 indexed; do
  echo "## $l vs base @0x18000 ##" >> $D
  python3 bodiff.py caps/base caps/$l --va 0x18000 --maxlen 0x100 2>/dev/null | grep "[+]0x0" >> $D
done
echo "" >> $D; echo "### VIEWPORT / RT-SIZE (BO 0x68000) ###" >> $D
for l in vp32 rt128; do
  echo "## $l vs base @0x68000 ##" >> $D
  python3 bodiff.py caps/base caps/$l --va 0x68000 --maxlen 0x920 2>/dev/null | grep "[+]0x09" >> $D
done
echo "" >> $D; echo "### CLEAR COLOR / PIXEL FORMAT (BO 0x10000110000) ###" >> $D
for l in clear fmt_rgba8; do
  echo "## $l vs base @0x10000110000 ##" >> $D
  python3 bodiff.py caps/base caps/$l --va 0x10000110000 --maxlen 0x700 2>/dev/null | grep "[+]0x0" >> $D
done
echo "" >> $D; echo "### FIXED-FUNCTION STATE (BO 0x58000) ###" >> $D
for l in blend depth prim_line prim_point; do
  echo "## $l vs base @0x58000 ##" >> $D
  python3 bodiff.py caps/base caps/$l --va 0x58000 --maxlen 0x80 2>/dev/null | grep "[+]0x0" >> $D
done
echo "" >> $D; echo "### RASTER/RT-SIZE side-effects in VDM (BO 0x18000 +0x0c) ###" >> $D
for l in depth rt128; do
  echo "## $l vs base @0x18000 ##" >> $D
  python3 bodiff.py caps/base caps/$l --va 0x18000 --maxlen 0x20 2>/dev/null | grep "[+]0x0" >> $D
done
echo "" >> $D; echo "### SHADER-CHANGE BO SET (vbig/fbig change ONLY code+USC) ###" >> $D
for l in vbig fbig; do
  echo "## $l vs base : BOs that differ ##" >> $D
  python3 bodiff.py caps/base caps/$l --maxlen 0x4000 2>/dev/null | grep -E "^=== gpu_va=0x[1-9a-f]" >> $D
done
# constant-program stub census (locate shader code)
echo "" >> $D; echo "### AGX constant-program stub (03000700 02000000) census, base ###" >> $D
for f in caps/base/bo_*.hex; do c=$(grep -oE "03000700 02000000" "$f" | wc -l | tr -d " "); [ "$c" != "0" ] && echo "$c  $(basename $f)" >> $D; done
# save key raw control BO hexdumps (base) into curated/
for va in 18000 58000 68000; do cp caps/base/bo_sigusr1_h0_va${va}_*.hex curated/base_lo_${va}.hex; done
cp caps/base/bo_sigusr1_h0_va10000110000_*.hex curated/base_3d_attachment_110000.hex
cp caps/base/bo_sigusr1_h0_va10000130000_*.hex curated/base_usc_130000.hex
cp caps/base/bo_sigusr1_h0_va10000100000_*.hex curated/base_vtxtable_100000.hex
# also the VDM 2nd-draw record (two)
python3 bodiff.py caps/base caps/two --va 0x18000 --maxlen 0x100 2>/dev/null > curated/vdm_two_second_draw.txt
# viewport raw (base 0x68000 region 0x900-0x930)
echo "wrote curated/"; ls -la curated
