#!/usr/bin/env python3
"""Re-derive kernels/carrier.metal's own facts (compiled WITH --no-fast-math,
matching what tools/agxtest always passes) fresh, rather than trusting the
constants hardcoded in casematrix.py. Run before every capture (also
exercised by verify.py --preflight indirectly via file presence, but this
script is the actual re-derivation and must be run by hand / by the
orchestrator before trusting CARRIER_LEN/SLOT_OUT/SLOT_MEM).

No GPU dispatch here -- compile + static disassemble only.
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402


def main():
    bin_dir = HERE / "work" / "baseline_bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(HERE / "harness" / "build.sh"), str(bin_dir)], check=True, cwd=HERE)
    out = bin_dir / "carrier_check.bin"
    subprocess.run([str(bin_dir / "shdump"), "-o", str(out), "--no-fast-math",
                     str(HERE / "kernels" / "carrier.metal"), "-f", "k"], check=True, cwd=HERE)
    hexstr = subprocess.run(
        [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
         str(out), "--extract-hex"], check=True, capture_output=True, text=True, cwd=HERE
    ).stdout.strip()
    b = bytes.fromhex(hexstr)
    print("_agc.main length (compiled --no-fast-math):", len(b))
    assert len(b) == CM.CARRIER_LEN, "CARRIER_LEN drifted: casematrix.py says %d, real compile says %d" % (
        CM.CARRIER_LEN, len(b))

    off = 0
    found = {"device_load": set(), "device_store": set()}
    while off < len(b):
        chunk = b[off:off + 14]
        recs, _ = isadb.disassemble(chunk)
        m = recs[0]
        if m.get("length"):
            if m["mnemonic"] in found:
                found[m["mnemonic"]].add(m["fields"]["base_slot"])
            off += m["length"]
        else:
            off += 2
    print("device_load base_slot values seen:", found["device_load"])
    print("device_store base_slot values seen:", found["device_store"])
    assert found["device_load"] == {CM.SLOT_MEM}, "load base_slot drifted from SLOT_MEM=%d: %r" % (
        CM.SLOT_MEM, found["device_load"])
    assert found["device_store"] == {CM.SLOT_OUT}, "store base_slot drifted from SLOT_OUT=%d: %r" % (
        CM.SLOT_OUT, found["device_store"])
    print("baseline: PASS (CARRIER_LEN=%d, SLOT_MEM(load)=%d, SLOT_OUT(store)=%d all confirmed fresh)" % (
        CM.CARRIER_LEN, CM.SLOT_MEM, CM.SLOT_OUT))


if __name__ == "__main__":
    main()
