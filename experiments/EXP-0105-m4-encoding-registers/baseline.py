#!/usr/bin/env python3
"""Re-derive kernels/carrier.metal's own facts (compiled WITH --no-fast-math,
matching what tools/agxtest always passes) fresh, rather than trusting the
constant hardcoded in casematrix.py. Run before every capture (also
exercised by verify.py --preflight indirectly via file presence, but this
script is the actual re-derivation and must be run by hand / by the
orchestrator before trusting CARRIER_LEN).

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
    print("baseline: PASS (CARRIER_LEN=%d confirmed fresh)" % CM.CARRIER_LEN)


if __name__ == "__main__":
    main()
