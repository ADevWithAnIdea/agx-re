cd ~/cleanroom_work/EXP-M5-17
SH=~/cleanroom_work/tools/shdump/shdump
$SH -o lodsel.bin --render --vertex v_main --fragment f_lodsel kernels/rtex2.metal >/dev/null 2>&1
T="--tex0-mip 255,0,0,255:0,0,255,255"   # mip level0=RED, level1=BLUE
echo "baseline (a=level(0)=RED):"
python3 splice.py lodsel.bin kernels/rtex2.metal v_main f_lodsel fragment "" $T
echo "op0 @+78 (66+12) LOD imm 0x00->0x40 (level0->level1):"
python3 splice.py lodsel.bin kernels/rtex2.metal v_main f_lodsel fragment "78=40" $T
echo "op0 @+78 LOD imm 0x00->0x80 (level2, only 2 levels -> clamps to level1=BLUE):"
python3 splice.py lodsel.bin kernels/rtex2.metal v_main f_lodsel fragment "78=80" $T
