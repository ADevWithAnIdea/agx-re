cd ~/cleanroom_work/EXP-M5-17
SH=~/cleanroom_work/tools/shdump/shdump
AP=~/cleanroom_work/tools/shdump/agxparse.py
echo "=== device health: fresh compile+render f_coord ==="
$SH -o coord.bin --render --vertex v_main --fragment f_coord kernels/rtex2.metal >/dev/null 2>&1
./agxrender2 --archive coord.bin --source kernels/rtex2.metal --vertex v_main --fragment f_coord --tex0-2x2 255,0,0,255:0,0,255,255 2>&1 | grep -E "PIXEL|STATUS"
echo "=== slot-2 kernels ==="
for F in f_tex3 f_samp4; do
  $SH -o "$F.bin" --render --vertex v_main --fragment "$F" kernels/rtex_slots2.metal >/dev/null 2>&1
  HEX=$(python3 $AP "$F.bin" --stage fragment --extract-hex 2>/dev/null | tr -d '[:space:]')
  echo "$F $HEX"
done
