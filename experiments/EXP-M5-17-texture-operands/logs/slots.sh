cd ~/cleanroom_work/EXP-M5-17
# device health check first
echo "=== health: re-run confirmed tex-slot baseline ==="
python3 splice.py texslot.bin kernels/rtex2.metal v_main f_texslot fragment "" --tex-fill 255,0,0,255 --tex1-fill 0,255,0,255
SH=~/cleanroom_work/tools/shdump/shdump
AP=~/cleanroom_work/tools/shdump/agxparse.py
for F in f_tex02 f_tex03 f_samp02 f_samp03 f_coordAC f_coordABC; do
  $SH -o "$F.bin" --render --vertex v_main --fragment "$F" kernels/rtex_slots.metal >/dev/null 2>&1
  HEX=$(python3 $AP "$F.bin" --stage fragment --extract-hex 2>/dev/null | tr -d '[:space:]')
  echo "$F $HEX"
done
