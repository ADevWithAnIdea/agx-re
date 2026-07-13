echo "=== census hex dirs on device ==="
find ~/cleanroom_work -maxdepth 4 -type d -name "hex" 2>/dev/null | head
echo "=== M5-02 / M5-03 census dirs ==="
ls -d ~/cleanroom_work/EXP-M5-0{2,3}* 2>/dev/null
find ~/cleanroom_work -maxdepth 3 -name "census*.py" 2>/dev/null | head
echo "=== count hex files in any corpus ==="
for d in $(find ~/cleanroom_work -maxdepth 4 -type d -name "hex" 2>/dev/null); do echo "$d: $(ls $d/*.hex 2>/dev/null | wc -l) hex"; done
echo "=== roundtrip in fork ==="
ls ~/cleanroom_work/tools/agx-isa-m5/
