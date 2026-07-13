cd ~/cleanroom_work/EXP-M5-17
clang -fobjc-arc -framework Metal -framework Foundation -o agxrender2 kernels/agxrender2.m 2>/dev/null
echo "BUILD=$?"
SH=~/cleanroom_work/tools/shdump/shdump
AP=~/cleanroom_work/tools/shdump/agxparse.py
$SH -o sampaddr.bin --render --vertex v_main --fragment f_sampaddr kernels/rtex2.metal >/dev/null 2>&1
HEX=$(python3 $AP sampaddr.bin --stage fragment --extract-hex 2>/dev/null | tr -d '[:space:]')
echo "f_sampaddr $HEX" > /tmp/sa.txt
cat /tmp/sa.txt
# s0=nearest:clamp, s1=nearest:repeat ; uvR=1.25 -> clamp gives row1(BLUE), repeat gives row0(RED)
T="--tex0-2x2 255,0,0,255:0,0,255,255 --samp0 nearest:clamp --samp1 nearest:repeat"
echo "baseline (a=s0=clamp -> row1=BLUE):"
python3 splice.py sampaddr.bin kernels/rtex2.metal v_main f_sampaddr fragment "" $T
