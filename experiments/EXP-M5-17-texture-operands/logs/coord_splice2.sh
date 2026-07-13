cd ~/cleanroom_work/EXP-M5-17
T="--tex0-2x2 255,0,0,255:0,0,255,255"   # row0=RED(uvA=0.25), row1=BLUE(uvB=0.75)
echo "baseline (a=uvA=RED):"
python3 splice.py coord.bin kernels/rtex2.metal v_main f_coord fragment "" $T
echo "op0 +3 only (113=04):"
python3 splice.py coord.bin kernels/rtex2.metal v_main f_coord fragment "113=04" $T
echo "op0 +7 only (117=49):"
python3 splice.py coord.bin kernels/rtex2.metal v_main f_coord fragment "117=49" $T
echo "op0 +3 AND +7 (113=04,117=49) -> op1's coord (uvB):"
python3 splice.py coord.bin kernels/rtex2.metal v_main f_coord fragment "113=04,117=49" $T
echo "op0 full operand region ->op1 (112=..):  bytes +6..+7 = 60 49, +3=04"
python3 splice.py coord.bin kernels/rtex2.metal v_main f_coord fragment "113=04,116=6049" $T
