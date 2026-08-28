#!/usr/bin/env python3
"""Re-derive every carrier kernel's own compiled facts FRESH, rather than
trusting the constants hardcoded in casematrix.py. Run before every
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
import isa_helpers as H  # noqa: E402


def compile_extract(bin_dir, metal_path, func="k"):
    out = bin_dir / (Path(metal_path).stem + "_" + func + "_check.bin")
    subprocess.run([str(bin_dir / "shdump"), "-o", str(out), "--no-fast-math",
                     "-f", func, str(metal_path)], check=True, cwd=HERE)
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

    b_dag = compile_extract(bin_dir, HERE / "kernels" / "carrier_dag.metal")
    print("carrier_dag.metal _agc.main length (compiled --no-fast-math):", len(b_dag))
    assert len(b_dag) >= CM.DAG_CARRIER_LEN, (
        "carrier_dag.metal compiled shorter (%d) than DAG_CARRIER_LEN (%d) -- "
        "every MODE A pressure program must fit" % (len(b_dag), CM.DAG_CARRIER_LEN))

    b_cf = compile_extract(bin_dir, HERE / "kernels" / "carrier_cf.metal")
    print("carrier_cf.metal _agc.main length (compiled --no-fast-math):", len(b_cf))
    assert len(b_cf) == CM.CF_CARRIER_LEN, "CF_CARRIER_LEN drifted: casematrix.py says %d, real compile says %d" % (
        CM.CF_CARRIER_LEN, len(b_cf))
    # re-confirm the reused EXP-0112/EXP-0090 skeleton is STILL byte-for-byte
    # what build_cf_topbit_program(srcA_reg_byte=0x41) produces, on THIS
    # pinned toolchain/revision (not merely trusted from EXP-0112's own
    # committed raw/).
    hexhex, out0, meta = H.build_cf_topbit_program(90.0, 10.0, 0x41)
    assert bytes.fromhex(hexhex) == b_cf, (
        "build_cf_topbit_program(0x41) (the untouched skeleton) no longer matches a "
        "fresh compile of carrier_cf.metal -- EXP-0112/EXP-0090's reused skeleton has drifted")
    print("  build_cf_topbit_program(0x41): byte-for-byte identical to fresh carrier_cf.metal compile")

    # Re-verify iunary_popcount.metal's k_popcount anchor (EXP-M4-14's own
    # literal bytes, reused verbatim) against a fresh compile -- must still
    # tokenize identically at this pinned revision/toolchain. Offset is
    # RELATIVE to _agc.main (agxtest.py's own --splice convention), NOT the
    # archive's absolute file offset -- see casematrix.py's own module
    # docstring bug #4 for why this distinction matters.
    b_pc = compile_extract(bin_dir, HERE / "kernels" / "iunary_popcount.metal", func="k_popcount")
    print("iunary_popcount.metal k_popcount _agc.main length:", len(b_pc))
    anchor_off, anchor_hex = 0x12, "2705560002005c04"
    got = b_pc[anchor_off:anchor_off + len(anchor_hex) // 2].hex()
    assert got == anchor_hex, (
        "iunary_popcount.metal k_popcount anchor drifted @0x%x: EXP-M4-14 says %s, fresh compile says %s"
        % (anchor_off, anchor_hex, got))
    rec = isadb.decode_one(bytes.fromhex(anchor_hex), 0)[0]
    assert isadb.assemble(rec["mnemonic"], rec["fields"]).hex() == anchor_hex, (
        "iunary_popcount.metal k_popcount anchor does not round-trip")
    print("  k_popcount anchor byte-identical to EXP-M4-14's own literal bytes, round-trip OK")

    print("baseline: PASS (CARRIER_LEN=%d, DAG_CARRIER_LEN<=%d, CF_CARRIER_LEN=%d all confirmed "
          "fresh; carrier_cf skeleton and iunary_popcount anchor confirmed byte-identical to their "
          "prior-experiment source)" % (CM.CARRIER_LEN, len(b_dag), CM.CF_CARRIER_LEN))


if __name__ == "__main__":
    main()
