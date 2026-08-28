#!/usr/bin/env python3
"""Re-derive kernels/carrier_dag.metal's own facts (compiled WITH
--no-fast-math, matching what tools/agxtest always passes) fresh, rather
than trusting the constants hardcoded in families.py. Run before every
capture. Verbatim architecture from EXP-0090/EXP-0101/EXP-0112's own
baseline.py.

No GPU dispatch here -- compile + static disassemble only.
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402
sys.path.insert(0, str(HERE))
import families as F  # noqa: E402


def compiled_main(bin_dir, kernel_path):
    out = bin_dir / (kernel_path.stem + "_check.bin")
    subprocess.run([str(bin_dir / "shdump"), "-o", str(out), "--no-fast-math",
                     str(kernel_path), "-f", "k"], check=True, cwd=HERE)
    hexstr = subprocess.run(
        [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
         str(out), "--extract-hex"], check=True, capture_output=True, text=True, cwd=HERE
    ).stdout.strip()
    return bytes.fromhex(hexstr)


def slots_used(b):
    off = 0
    loads, stores = [], []
    while off < len(b):
        chunk = b[off:off + 16]
        recs, _ = isadb.disassemble(chunk)
        m = recs[0] if recs else None
        if m and m.get("length"):
            if m["mnemonic"] == "device_load":
                loads.append(m["fields"]["base_slot"])
            elif m["mnemonic"] == "device_store":
                stores.append(m["fields"]["base_slot"])
            off += m["length"]
        else:
            off += 2
    return loads, stores


def main():
    bin_dir = HERE / "work" / "baseline_bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(HERE / "harness" / "build.sh"), str(bin_dir)], check=True, cwd=HERE)

    b_dag = compiled_main(bin_dir, HERE / "kernels" / "carrier_dag.metal")
    print("carrier_dag.metal _agc.main length (--no-fast-math):", len(b_dag))
    assert len(b_dag) >= F.DAG_CARRIER_LEN, (
        "carrier_dag.metal compiled shorter (%d) than DAG_CARRIER_LEN (%d) -- "
        "every generated program must fit" % (len(b_dag), F.DAG_CARRIER_LEN))
    loads, stores = slots_used(b_dag)
    print("carrier_dag device_load base_slot values (in order):", loads, "device_store:", stores)
    assert set(loads) == {F.SLOT_MEM, F.SLOT_IMEM}, "carrier_dag load slots drifted: %r" % (loads,)
    assert set(stores) == {F.SLOT_OUT}, "carrier_dag store slots drifted: %r" % (stores,)
    assert loads[0] == F.SLOT_MEM, "carrier_dag: expected the FIRST compiled load to be SLOT_MEM=%d, got %r" % (
        F.SLOT_MEM, loads[0])
    assert loads[-1] == F.SLOT_IMEM, "carrier_dag: expected the LAST compiled load to be SLOT_IMEM=%d, got %r" % (
        F.SLOT_IMEM, loads[-1])

    print("baseline: PASS (carrier_dag.metal length and base_slot mapping confirmed fresh)")


if __name__ == "__main__":
    main()
