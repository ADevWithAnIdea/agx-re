cd ~/cleanroom_work/EXP-M5-17
AP=~/cleanroom_work/tools/shdump/agxparse.py
ISA=~/cleanroom_work/tools/agx-isa-m5/agxisa.py
HEX=$(python3 $AP f_coord.bin --stage fragment --extract-hex 2>/dev/null | tr -d '[:space:]')
echo "FULL f_coord fragment hex:"
echo "$HEX"
echo "=== tokenize ==="
python3 $ISA tokenize "$HEX" 2>&1 | head -80
