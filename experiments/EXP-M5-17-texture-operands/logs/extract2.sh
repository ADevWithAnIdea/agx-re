cd ~/cleanroom_work/EXP-M5-17
SH=~/cleanroom_work/tools/shdump/shdump
AP=~/cleanroom_work/tools/shdump/agxparse.py
for F in f_coord f_texslot f_sampslot f_lodsel f_readsel; do
  $SH -o "$F.bin" --render --vertex v_main --fragment "$F" kernels/rtex2.metal >/dev/null 2>&1
  HEX=$(python3 $AP "$F.bin" --stage fragment --extract-hex 2>/dev/null | tr -d '[:space:]')
  echo "$F $HEX"
done
