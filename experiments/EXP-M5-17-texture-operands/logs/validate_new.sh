cd ~/cleanroom_work/EXP-M5-17
# census wrapper that points at our isolated copy
cat > census_new.py <<'PY'
import sys, os
sys.path.insert(0, os.path.expanduser("~/cleanroom_work/EXP-M5-17/isa_copy"))
# load the census_fork module source but force our isadb dir
import importlib.util
spec = importlib.util.spec_from_file_location("cf", os.path.expanduser("~/cleanroom_work/EXP-M5-05/census_fork.py"))
# monkeypatch _find_isadb before exec
cf = importlib.util.module_from_spec(spec)
cf._find_isadb = lambda: os.path.expanduser("~/cleanroom_work/EXP-M5-17/isa_copy")
spec.loader.exec_module(cf)
cf.main()
PY
echo "=== NEW roundtrip ==="
cd ~/cleanroom_work/EXP-M5-17/isa_copy && python3 roundtrip_test.py 2>&1 | tail -3
cd ~/cleanroom_work/EXP-M5-17
echo "=== NEW own census ==="
python3 census_new.py ~/cleanroom_work/EXP-M5-02/hex --out census_new_own 2>&1 | tail -1
grep -E "fully-named|desync-regions|named=|cleanly" census_new_own.txt | head
echo "=== NEW tp census ==="
python3 census_new.py ~/cleanroom_work/EXP-M5-03/tp_hex --out census_new_tp 2>&1 | tail -1
grep -E "fully-named|desync-regions|named=|cleanly" census_new_tp.txt | head
