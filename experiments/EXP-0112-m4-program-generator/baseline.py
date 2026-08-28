#!/usr/bin/env python3
"""Re-derive kernels/carrier_dag.metal and kernels/carrier_cf.metal's own
facts (compiled WITH --no-fast-math, matching what tools/agxtest always
passes) fresh, rather than trusting the constants hardcoded in
generator.py/cf.py. Run before every capture. Verbatim architecture from
EXP-0101/EXP-0090's own baseline.py (same method; two carriers instead of
one since this experiment's CF family needs a materially different buffer
shape from its DAG family).

No GPU dispatch here -- compile + static disassemble only.
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402
sys.path.insert(0, str(HERE))
import generator as G   # noqa: E402
import cf as CF          # noqa: E402


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
    """Returns (loads, stores) as ORDER-PRESERVING lists of base_slot
    values, one entry per device_load/device_store instruction in the
    kernel's own compiled instruction stream, in program order. Order
    matters: a real bug in this experiment's own CF family (see cf.py's
    docstring) was caused by trusting a SEPARATE, simplified probe
    kernel's base_slot assignment instead of the actual carrier kernel's
    own -- the compiler does not merely assign base_slot by buffer
    declaration order, so returning only a set (this function's earlier
    shape) hid that the FIRST vs SECOND load's slot value matters and
    cannot be inferred from a differently-shaped stand-in kernel."""
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
    assert len(b_dag) >= G.DAG_CARRIER_LEN, (
        "carrier_dag.metal compiled shorter (%d) than DAG_CARRIER_LEN (%d) -- "
        "every generated program must fit" % (len(b_dag), G.DAG_CARRIER_LEN))
    loads, stores = slots_used(b_dag)
    print("carrier_dag device_load base_slot values (in order):", loads, "device_store:", stores)
    assert set(loads) == {G.SLOT_MEM, G.SLOT_IMEM}, "carrier_dag load slots drifted: %r" % (loads,)
    assert set(stores) == {G.SLOT_OUT}, "carrier_dag store slots drifted: %r" % (stores,)
    # carrier_dag.metal's own source reads ALL mem[] (float) accesses before
    # ANY imem[] (int) access -- the FIRST load in the compiled stream must
    # therefore be SLOT_MEM, matching generator.py's own load-node builder
    # (which always targets SLOT_MEM) and families.py's IADD_ANCHOR (which
    # always targets SLOT_IMEM) -- this positional check is exactly the
    # class of assumption the CF base_slot bug (see cf.py) got wrong by NOT
    # checking.
    assert loads[0] == G.SLOT_MEM, "carrier_dag: expected the FIRST compiled load to be SLOT_MEM=%d, got %r" % (
        G.SLOT_MEM, loads[0])
    assert loads[-1] == G.SLOT_IMEM, "carrier_dag: expected the LAST compiled load to be SLOT_IMEM=%d, got %r" % (
        G.SLOT_IMEM, loads[-1])

    b_cf = compiled_main(bin_dir, HERE / "kernels" / "carrier_cf.metal")
    print("carrier_cf.metal _agc.main length (--no-fast-math):", len(b_cf))
    assert len(b_cf) == CF.CARRIER_LEN, (
        "carrier_cf.metal length drifted: expected %d, got %d" % (CF.CARRIER_LEN, len(b_cf)))
    loads, stores = slots_used(b_cf)
    print("carrier_cf device_load base_slot values (in order):", loads, "device_store:", stores)
    assert set(loads) == {CF.SLOT_A, CF.SLOT_N}, "carrier_cf load slots drifted: %r" % (loads,)
    assert set(stores) == {CF.SLOT_OUT}, "carrier_cf store slots drifted: %r" % (stores,)
    # carrier_cf.metal's own source reads a[tid] (SLOT_A) strictly before
    # n[tid] (SLOT_N) -- order-checked explicitly (see the loud comment
    # above); this is the exact assertion that would have caught the
    # swapped-base_slot bug documented in cf.py's own module docstring
    # before it ever reached a GPU dispatch.
    assert loads[0] == CF.SLOT_A, "carrier_cf: expected the FIRST compiled load to be SLOT_A=%d, got %r" % (
        CF.SLOT_A, loads[0])
    assert loads[1] == CF.SLOT_N, "carrier_cf: expected the SECOND compiled load to be SLOT_N=%d, got %r" % (
        CF.SLOT_N, loads[1])

    print("baseline: PASS (all carrier lengths and base_slot mappings confirmed fresh)")


if __name__ == "__main__":
    main()
