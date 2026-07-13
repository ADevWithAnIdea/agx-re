cd ~/cleanroom_work/EXP-M5-17
TEX="--tex0-2x2 255,0,0,255:0,0,255,255"   # row0=RED(uvA), row1=BLUE(uvB)
echo "baseline (no splice):"
python3 splice.py coord.bin kernels/rtex2.metal v_main f_coord fragment "" $TEX
echo "op0 @+117 (110+7) coord 0x29->0x49:"
python3 splice.py coord.bin kernels/rtex2.metal v_main f_coord fragment "117=49" $TEX
echo "op1 @+139 (132+7) coord 0x49->0x29:"
python3 splice.py coord.bin kernels/rtex2.metal v_main f_coord fragment "139=29" $TEX
