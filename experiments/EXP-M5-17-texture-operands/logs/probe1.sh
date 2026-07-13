set -e
cd ~/cleanroom_work/EXP-M5-17
T=tools=~/cleanroom_work/tools
SH=~/cleanroom_work/tools/shdump/shdump
AP=~/cleanroom_work/tools/shdump/agxparse.py
[ -x "$SH" ] || SH=~/cleanroom_work/tools/agxtest/shdump
echo "shdump=$SH"
echo "=== compile coordA ==="
$SH -o coordA.bin --render --vertex v_main --fragment f_coordA kernels/rtex.metal 2>&1 | tail -3
echo "=== agxparse help ==="
python3 $AP --help 2>&1 | head -30
