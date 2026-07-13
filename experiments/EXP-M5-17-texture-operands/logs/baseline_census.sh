cd ~/cleanroom_work/EXP-M5-17
mkdir -p census_base
C=~/cleanroom_work/EXP-M5-05/census_fork.py
echo "=== BASELINE own ==="
python3 $C ~/cleanroom_work/EXP-M5-02/hex --out census_base/own_base 2>&1 | tail -2
grep -E "fully-named|desync-regions|named=|cleanly|BYTE COV|undecoded" census_base/own_base.txt | head
echo "=== BASELINE tp ==="
python3 $C ~/cleanroom_work/EXP-M5-03/tp_hex --out census_base/tp_base 2>&1 | tail -2
grep -E "fully-named|desync-regions|named=|cleanly|BYTE COV|undecoded" census_base/tp_base.txt | head
echo "=== BASELINE roundtrip ==="
cd ~/cleanroom_work/tools/agx-isa-m5 && python3 roundtrip_test.py 2>&1 | tail -5
