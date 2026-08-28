#!/usr/bin/env python3
"""Re-derive every carrier kernel's own compiled length fresh (compiled
WITH --no-fast-math, matching what tools/agxtest always passes), rather
than trusting the constants hardcoded in casematrix.py. Run before every
capture (also exercised by verify.py --preflight indirectly via file
presence, but this script is the actual re-derivation and must be run by
hand / by the orchestrator before trusting the CARRIER_LEN constants).

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

EXPECT = {
    "carrier.metal": CM.CARRIER_LEN,
    "loadfwd_carrier.metal": CM.LOADFWD_CARRIER_LEN,
    "carrier_buf1.metal": CM.BUF1_CARRIER_LEN,
    "carrier_buf2.metal": CM.BUF2_CARRIER_LEN,
    "carrier_buf3.metal": CM.BUF3_CARRIER_LEN,
}


def main():
    bin_dir = HERE / "work" / "baseline_bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(HERE / "harness" / "build.sh"), str(bin_dir)], check=True, cwd=HERE)
    ok = True
    for kernel, expect_len in EXPECT.items():
        out = bin_dir / ("%s_check.bin" % kernel)
        subprocess.run([str(bin_dir / "shdump"), "-o", str(out), "--no-fast-math",
                         str(HERE / "kernels" / kernel), "-f", "k"], check=True, cwd=HERE)
        hexstr = subprocess.run(
            [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
             str(out), "--extract-hex"], check=True, capture_output=True, text=True, cwd=HERE
        ).stdout.strip()
        b = bytes.fromhex(hexstr)
        print("%s: _agc.main length (compiled --no-fast-math) = %d (expect %d)" %
              (kernel, len(b), expect_len))
        if len(b) != expect_len:
            ok = False
            print("  DRIFT: casematrix.py says %d, real compile says %d" % (expect_len, len(b)))
    if not ok:
        raise SystemExit("baseline: FAIL (carrier length drift -- pre-capture stop)")
    print("baseline: PASS (all %d carrier lengths confirmed fresh)" % len(EXPECT))


if __name__ == "__main__":
    main()
