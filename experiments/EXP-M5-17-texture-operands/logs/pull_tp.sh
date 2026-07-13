ls -la ~/cleanroom_work/EXP-M5-17/census_new_tp.txt 2>&1
grep -E "fully-named|desync-regions|named=" ~/cleanroom_work/EXP-M5-17/census_new_tp.txt 2>&1 | head
