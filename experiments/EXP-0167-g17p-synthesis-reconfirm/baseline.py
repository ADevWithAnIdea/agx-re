#!/usr/bin/env python3
"""EXP-0158 carrier baseline (G17P): re-derive our own carrier kernels'
compiled length and base_slot ORDER fresh before every capture, on THIS
target, never trusted from a constant.  Compile + static disassemble only --
no GPU dispatch.

Adapted from EXP-0112's baseline.py (our own code).  The ORDER check is kept:
EXP-0112 documented a real hardware failure caused by inferring base_slot from
a structurally different stand-in kernel.  Re-running it here matters twice
over, because the carrier is compiled by the A18's own toolchain and neither
its length nor its slot order may be assumed to match the M4's.
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import generator as G   # noqa: E402
import cf as CF         # noqa: E402
import synth as S       # noqa: E402
isadb = S.isadb         # the PINNED snapshot, not the live tools/agx-isa copy


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
    assert len(b_dag) >= G.DAG_CARRIER_LEN, (
        "carrier_dag.metal compiled shorter (%d) than DAG_CARRIER_LEN (%d)"
        % (len(b_dag), G.DAG_CARRIER_LEN))
    loads, stores = slots_used(b_dag)
    print("carrier_dag device_load base_slot (in order):", loads, "store:", stores)
    assert set(loads) == {G.SLOT_MEM, G.SLOT_IMEM}, "carrier_dag load slots drifted: %r" % (loads,)
    assert set(stores) == {G.SLOT_OUT}, "carrier_dag store slots drifted: %r" % (stores,)
    assert loads[0] == G.SLOT_MEM, "carrier_dag first load slot != SLOT_MEM: %r" % (loads[0],)
    assert loads[-1] == G.SLOT_IMEM, "carrier_dag last load slot != SLOT_IMEM: %r" % (loads[-1],)

    b_cf = compiled_main(bin_dir, HERE / "kernels" / "carrier_cf.metal")
    print("carrier_cf.metal _agc.main length (--no-fast-math):", len(b_cf))
    assert len(b_cf) == CF.CARRIER_LEN, (
        "carrier_cf.metal length drifted: expected %d, got %d.  If this fires on "
        "G17P it is a REAL FINDING (the A18 toolchain lays the carrier out "
        "differently), not a nuisance -- record it, do not silently retune."
        % (CF.CARRIER_LEN, len(b_cf)))
    loads, stores = slots_used(b_cf)
    print("carrier_cf device_load base_slot (in order):", loads, "store:", stores)
    assert set(loads) == {CF.SLOT_A, CF.SLOT_N}, "carrier_cf load slots drifted: %r" % (loads,)
    assert set(stores) == {CF.SLOT_OUT}, "carrier_cf store slots drifted: %r" % (stores,)
    assert loads[0] == CF.SLOT_A, "carrier_cf first load slot != SLOT_A: %r" % (loads[0],)
    assert loads[1] == CF.SLOT_N, "carrier_cf second load slot != SLOT_N: %r" % (loads[1],)

    print("baseline: PASS (carrier lengths and base_slot order confirmed fresh)")


if __name__ == "__main__":
    main()
