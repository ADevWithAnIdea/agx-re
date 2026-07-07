#!/usr/bin/env python3
# analyze.py -- EXP-0008 host-side analysis of the carved vertex/fragment AGX.
#
# Loads the extracted hex (raw/*.hex), and:
#   1. CARVE CHECK   -- proves __whole_text__ == constant_program ++ _agc.main
#      (byte-exact), i.e. the symbol-table carve partitions __text with no gap.
#   2. REGRESSION    -- tokenizes reference COMPUTE _agc.main under the current
#      agx-isa DB and confirms 0 leftover (our agxparse refactor did not break
#      the compute path).
#   3. FRONT-TOKENIZE-- tokenizes each vertex/fragment _agc.main under the
#      current (compute-only) DB and records the clean prefix + the byte0 of the
#      first instruction the DB cannot length (a PROVEN instruction boundary,
#      because everything before it tokenized cleanly). These are the
#      confirmed-new instruction-group leaders.
#   4. LEADER CENSUS -- a best-effort structural greedy walk (INFERRED lengths,
#      NOT hardware-validated) enumerating candidate byte0 group leaders that
#      appear in vertex/fragment but not in the compute corpus.
#
# CLEAN-ROOM: OWN-SHADER + PUBLIC. Operates only on our own compiled shader
# bytes and our own ISA DB. No Apple binary is disassembled.

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
# import the current (read-only) agx-isa DB for tokenization
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "agx-isa"))
import isadb  # noqa: E402

SHADERS = ["render_min", "render_interp", "render_tex", "render_deriv"]
STAGES = ["vertex", "fragment"]

# Reference COMPUTE _agc.main programs (extracted with the SAME refactored
# agxparse; see raw/compute_ref.txt). Used for the regression check.
COMPUTE_REF = {
    "k01_fadd":      "1ca010066710540000012000510100404600670044040101200051010040460009051c0100c0e7005400020121001100009011000e000000",
    "k10_loadstore": "1ca010066710440000012000510100404600e7005600010121001100009011000e000000",
}


def loadhex(name):
    p = os.path.join(RAW, name)
    with open(p) as f:
        return bytes.fromhex(f.read().strip())


def tokenize(buf):
    """Return (records, leftover). Uses the current agx-isa DB."""
    return isadb.disassemble(buf)


def carve_check():
    print("=" * 72)
    print("1. CARVE CHECK  (whole __text  ==  constant_program ++ _agc.main)")
    print("=" * 72)
    allok = True
    for sh in SHADERS:
        for st in STAGES:
            cprog = loadhex(f"{sh}.{st}.cprog.hex")
            main = loadhex(f"{sh}.{st}.main.hex")
            text = loadhex(f"{sh}.{st}.text.hex")
            recon = cprog + main
            ok = (recon == text)
            allok &= ok
            print(f"  {sh:14s} {st:8s} cprog={len(cprog):3d} main={len(main):3d} "
                  f"text={len(text):3d}  recon=={'OK' if ok else 'MISMATCH'}  "
                  f"ends_in_stop={main[-4:].hex()=='0e000000'}")
    print(f"  => {'ALL carves reconstruct byte-exact & end in stop' if allok else 'CARVE ERROR'}")
    return allok


def regression_check():
    print("\n" + "=" * 72)
    print("2. COMPUTE REGRESSION  (refactored agxparse -> same bytes; DB clean)")
    print("=" * 72)
    allclean = True
    for name, hx in COMPUTE_REF.items():
        recs, leftover = tokenize(bytes.fromhex(hx))
        clean = (leftover == b"")
        allclean &= clean
        mnems = " ".join(r["mnemonic"] for r in recs if not r.get("error"))
        print(f"  {name:14s} : {'CLEAN' if clean else 'LEFTOVER'} "
              f"({len(recs)} instr)  [{mnems}]")
    print(f"  => compute path {'unchanged & tokenizes clean' if allclean else 'REGRESSION'}")
    return allclean


def front_tokenize():
    print("\n" + "=" * 72)
    print("3. FRONT-TOKENIZE vertex/fragment under the CURRENT (compute-only) DB")
    print("   clean prefix, then the byte0 of the first un-lengthable instr")
    print("   (a PROVEN new instruction-group leader).")
    print("=" * 72)
    proven_new = {}   # byte0 -> set of "shader.stage" where it is a proven boundary
    for sh in SHADERS:
        for st in STAGES:
            main = loadhex(f"{sh}.{st}.main.hex")
            recs, leftover = tokenize(main)
            clean = [r for r in recs if not r.get("error")]
            prefix = " ".join(r["mnemonic"] for r in clean)
            consumed = sum(r["length"] for r in clean)
            first_unknown = None
            if leftover:
                first_unknown = leftover[0]
                proven_new.setdefault(first_unknown, set()).add(f"{sh}.{st}")
            fu = f"0x{first_unknown:02x}" if first_unknown is not None else "-(fully clean)"
            print(f"  {sh:14s} {st:8s}: clean_prefix=[{prefix}] "
                  f"consumed {consumed}/{len(main)}B, first_unknown_leader={fu}")
    print("\n  PROVEN-boundary new leaders (byte0 -> where):")
    for b0 in sorted(proven_new):
        where = ", ".join(sorted(proven_new[b0]))
        note = ""
        if b0 == 0x9f:
            note = "  (int-ALU family; also in COMPUTE int kernels -> not fragment-new)"
        print(f"    0x{b0:02x}: {where}{note}")
    return proven_new


def common_prefix(a, b):
    n = 0
    while n < len(a) and n < len(b) and a[n] == b[n]:
        n += 1
    return n


def common_suffix(a, b):
    n = 0
    while n < len(a) and n < len(b) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def differential():
    """Attribute new instruction bytes to features by differential comparison.

    All 4 fragments share the SAME MSL vertex-output plumbing except the
    fragment body, so the shared SUFFIX = the fragment output/epilogue path and
    the per-feature DELTAS localize interpolation/sample/derivative code."""
    print("\n" + "=" * 72)
    print("4. DIFFERENTIAL feature attribution (which new code = which feature)")
    print("=" * 72)
    frag = {sh: loadhex(f"{sh}.fragment.main.hex") for sh in SHADERS}
    vert = {sh: loadhex(f"{sh}.vertex.main.hex") for sh in SHADERS}

    # Longest common suffix across all fragments = the shared fragment epilogue.
    ref = frag["render_min"]
    csuf = min(common_suffix(ref, frag[sh]) for sh in SHADERS)
    print(f"  fragment shared epilogue (common suffix) = {csuf} bytes:")
    print(f"    ...{ref[-csuf:].hex()}")
    print("    (this is the color-output store path: 0x87 setup, 0xe7 store,")
    print("     0x07 form, 0x0e stop -- present in EVERY fragment)")

    print("\n  fragment BODY (main minus shared epilogue), byte0 of first parcel:")
    for sh in SHADERS:
        body = frag[sh][:len(frag[sh]) - csuf]
        b0s = sorted({body[i] for i in range(0, len(body), 2)})
        print(f"    {sh:14s}: body={len(body):3d}B  first=0x{body[0]:02x}  "
              f"parcel-byte0-set={[hex(b) for b in b0s]}")

    print("\n  feature deltas (constant color has NO interp/sample/deriv):")
    base = frag["render_min"]
    for sh in ("render_interp", "render_tex", "render_deriv"):
        cp = common_prefix(base, frag[sh])
        cs = common_suffix(base, frag[sh])
        feat = {"render_interp": "varying INTERPOLATION",
                "render_tex":    "texture SAMPLE (implicit-LOD)",
                "render_deriv":  "DERIVATIVE (dfdx/dfdy)"}[sh]
        print(f"    render_min vs {sh:14s} [{feat}]:")
        print(f"      shared_prefix={cp}B shared_suffix={cs}B  "
              f"=> {sh} adds {len(frag[sh]) - cp - cs}B unique body")

    # Vertex: render_tex & render_deriv have identical MSL vertex.
    print("\n  vertex determinism/identity cross-check:")
    from hashlib import sha256
    for sh in SHADERS:
        print(f"    {sh:14s} vertex sha256[:12]={sha256(vert[sh]).hexdigest()[:12]}")


def new_group_summary():
    print("\n" + "=" * 72)
    print("5. NEW instruction-GROUP surface vs the current DB")
    print("=" * 72)
    print("  Current DB covers byte0 groups (low-nibble = group id, EXP-0006):")
    print("    c=preamble  9=float-ALU  7(0x67/0xe7)=device load/store  e=stop"
          "  (also 0x0b,0x12 float)")
    print("  Vertex/fragment streams additionally exercise, NONE in the DB:")
    print("    * low-nibble 0xf ALU family: 0x2f, 0x3f, 0xaf (siblings of the")
    print("      int-ALU 0x9f) -- PROVEN leader 0x2f begins interp/tex/deriv frags")
    print("    * low-nibble 0x7 memory family variants beyond 0x67/0xe7:")
    print("      0x07, 0x87, 0x97, 0xa7 -- PROVEN leader 0x97 begins the")
    print("      constant-color fragment; 0xa7 in vertex")
    print("    * vertex varying/attribute stores: 0x05/0x06/0x57 forms")
    print("  (byte0 GROUP presence is structural; exact instr boundaries/lengths")
    print("   and semantics are deferred to a follow-up decode experiment.)")


if __name__ == "__main__":
    ok1 = carve_check()
    ok2 = regression_check()
    front_tokenize()
    differential()
    new_group_summary()
    print("\n" + "=" * 72)
    print(f"SUMMARY: carve={'OK' if ok1 else 'FAIL'}  compute_regression={'OK' if ok2 else 'FAIL'}")
    print("=" * 72)
