#!/usr/bin/env python3
"""Re-derive kernels/carrier.metal's/lit17_unpack.metal's/lit17_cvt.metal's
own compiled facts FRESH, rather than trusting the constants hardcoded in
casematrix.py/build_h2_cachebyte's own anchor arguments. Run before every
capture (also exercised by verify.py --preflight indirectly via file
presence, but this script is the actual re-derivation).

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


def compile_extract(bin_dir, metal_path):
    out = bin_dir / (Path(metal_path).stem + "_check.bin")
    subprocess.run([str(bin_dir / "shdump"), "-o", str(out), "--no-fast-math",
                     str(metal_path), "-f", "k"], check=True, cwd=HERE)
    hexstr = subprocess.run(
        [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
         str(out), "--extract-hex"], check=True, capture_output=True, text=True, cwd=HERE
    ).stdout.strip()
    return bytes.fromhex(hexstr)


def main():
    bin_dir = HERE / "work" / "baseline_bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(HERE / "harness" / "build.sh"), str(bin_dir)], check=True, cwd=HERE)

    b = compile_extract(bin_dir, HERE / "kernels" / "carrier.metal")
    print("carrier.metal _agc.main length (compiled --no-fast-math):", len(b))
    assert len(b) == CM.CARRIER_LEN, "CARRIER_LEN drifted: casematrix.py says %d, real compile says %d" % (
        CM.CARRIER_LEN, len(b))

    # Re-verify the H2_CACHEBYTE MODE B anchors (offsets/bytes hardcoded in
    # casematrix.build_h2) against a FRESH compile -- these are reused
    # verbatim from EXP-0089 and must still tokenize identically at this
    # pinned revision/toolchain.
    anchors = [
        ("lit17_unpack.metal", 0x12, "1704560401000eaa", 0x1a, "1704540001001cca"),
        ("lit17_cvt.metal", 0x12, "a707560003048e60", 0x1a, "a70754020304ac20"),
    ]
    for fname, c1_off, c1_hex, c2_off, c2_hex in anchors:
        buf = compile_extract(bin_dir, HERE / "kernels" / fname)
        print("%s _agc.main length: %d" % (fname, len(buf)))
        got1 = buf[c1_off:c1_off + len(c1_hex) // 2].hex()
        got2 = buf[c2_off:c2_off + len(c2_hex) // 2].hex()
        assert got1 == c1_hex, "%s c1 anchor drifted @0x%x: casematrix says %s, fresh compile says %s" % (
            fname, c1_off, c1_hex, got1)
        assert got2 == c2_hex, "%s c2 anchor drifted @0x%x: casematrix says %s, fresh compile says %s" % (
            fname, c2_off, c2_hex, got2)
        # also confirm both anchor instructions round-trip cleanly through isadb
        for off, hexbytes in ((c1_off, c1_hex), (c2_off, c2_hex)):
            rec = isadb.decode_one(bytes.fromhex(hexbytes), 0)[0]
            assert isadb.assemble(rec["mnemonic"], rec["fields"]).hex() == hexbytes, (
                "%s anchor @0x%x does not round-trip" % (fname, off))
        print("  %s: c1/c2 anchors byte-identical to casematrix.py's hardcoded values, round-trip OK" % fname)

    print("baseline: PASS (CARRIER_LEN=%d confirmed fresh; both MODE B kernels' anchors "
          "confirmed byte-identical to EXP-0089's recorded values, fresh compile)" % CM.CARRIER_LEN)


if __name__ == "__main__":
    main()
