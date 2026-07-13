cd ~/cleanroom_work/EXP-M5-17
SH=~/cleanroom_work/tools/shdump/shdump
AP=~/cleanroom_work/tools/shdump/agxparse.py
for F in f_coordA f_coordB f_tex0 f_tex1 f_samp0 f_samp1 f_lod0 f_lod1 f_lod2 f_lodreg f_bias f_read0 f_read1; do
  $SH -o "$F.bin" --render --vertex v_main --fragment "$F" kernels/rtex.metal >/dev/null 2>&1
  HEX=$(python3 $AP "$F.bin" --stage fragment --extract-hex 2>/dev/null | tr -d '[:space:]')
  echo "$F $HEX"
done
