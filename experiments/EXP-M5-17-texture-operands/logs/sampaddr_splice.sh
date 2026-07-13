cd ~/cleanroom_work/EXP-M5-17
T="--tex0-2x2 255,0,0,255:0,0,255,255 --samp0 nearest:clamp --samp1 nearest:repeat"
echo "baseline (a=s0=clamp=BLUE):"
python3 splice.py sampaddr.bin kernels/rtex2.metal v_main f_sampaddr fragment "" $T
echo "op0 @+67 (62+5) samp-slot 0x00->0x01 (samp0->samp1=repeat -> row0=RED):"
python3 splice.py sampaddr.bin kernels/rtex2.metal v_main f_sampaddr fragment "67=01" $T
echo "control: op0 @+68 (62+6) 0x60->0x68 (tex-slot bit; only 1 texture bound so tex1 unbound=black/undef):"
python3 splice.py sampaddr.bin kernels/rtex2.metal v_main f_sampaddr fragment "68=68" $T
