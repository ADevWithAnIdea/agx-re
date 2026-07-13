cd ~/cleanroom_work/EXP-M5-17
clang -fobjc-arc -framework Metal -framework Foundation -o agxrender2 kernels/agxrender2.m 2>&1 | head -20
echo "BUILD_RC=$?"
ls -la agxrender2 2>/dev/null
SH=~/cleanroom_work/tools/shdump/shdump
echo "=== compile f_coord (dual-sample) ==="
$SH -o coord.bin --render --vertex v_main --fragment f_coord kernels/rtex2.metal 2>&1 | tail -2
echo "=== render f_coord: 2x2 top=RED(255,0,0) bottom=BLUE(0,0,255); expect a=uvA=texel row0=RED ==="
./agxrender2 --archive coord.bin --source kernels/rtex2.metal --vertex v_main --fragment f_coord --tex0-2x2 255,0,0,255:0,0,255,255 2>&1 | grep -E "PIXEL|STATUS|PIPELINE_SOURCE|ERROR"
