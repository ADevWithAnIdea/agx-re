cd ~/cleanroom_work/EXP-M5-17
SH=~/cleanroom_work/tools/shdump/shdump
$SH -o texslot.bin --render --vertex v_main --fragment f_texslot kernels/rtex2.metal >/dev/null 2>&1
# tex0 solid RED (slot0), tex1 solid GREEN (slot1)
T="--tex-fill 255,0,0,255 --tex1-fill 0,255,0,255"
echo "baseline (expect a=tex0=RED):"
python3 splice.py texslot.bin kernels/rtex2.metal v_main f_texslot fragment "" $T
echo "op0 @+72 (66+6) texslot 0x60->0x68 (slot0->1):"
python3 splice.py texslot.bin kernels/rtex2.metal v_main f_texslot fragment "72=68" $T
echo "op1 @+94 (88+6) texslot 0x68->0x60 (slot1->0):"
python3 splice.py texslot.bin kernels/rtex2.metal v_main f_texslot fragment "94=60" $T
