#!/usr/bin/env python3
"""EXP-0171 FROZEN case matrix (G17P).

The sweep plan is BYTE-dense and FIELD-decomposed:

  * every case mutates exactly ONE BYTE of the instruction under test, densely
    over 0..255, with every other byte at its compiler-emitted anchor value;
  * db FIELDS are recovered OFFLINE by the A5 decomposition (EXP-0166): a
    field's sub-values are the swept byte values whose OTHER bits in that byte
    equal the anchor's.

Why bytes and not fields: `isadb.assemble()` ORs the match constant before the
field values and an OR cannot clear a bit, so 53 fields in db.json were silently
under-swept when driven through it (EXP-0166 DEF-0166-1, fixed at 4b16d0b4;
`irotate.b2` reached 32 of 256 encodings while reporting 256). Splicing raw
bytes cannot under-cover, and `analysis/coverage.py` proves it by counting
DISTINCT `bytes` strings rather than trusting the dispatched-value count.

THE THREE CARRIER STYLES, and why they are structurally different:

  NAT   -- the compiled probe kernel itself, ONE byte spliced IN PLACE. The
           instruction under test keeps its own operand provenance (values
           LOADED from device buffers) and, decisively, ITS OWN CONSUMER: the
           compiler's own `device_store` into `out[]`. This is the
           STORE-CONSUMED observable EXP-0166 sect 2.1 prescribes.
  SYNTH -- the whole `_agc.main` replaced by a program we assembled from
           tools/agx-isa's field rules: mov_imm seeds -> PRE sentinel -> the
           instruction under test lifted BYTE-FOR-BYTE -> a 16-register dump ->
           POST sentinel -> stop. The observable is the REGISTER FILE. This is
           EXP-0154's carrier, reproduced here so the two are compared inside
           one experiment rather than across two.
  FRAME -- SYNTH plus a two-instruction framing probe (6B falu2i then 2B
           mov_imm) placed IMMEDIATELY AFTER the instruction under test. If a
           swept trailing byte were a LENGTH or framing bit, the decoder would
           resume mid-instruction and both markers would be lost. A `tail`/`z*`
           inertness verdict is only admissible from a carrier that could have
           seen that.

NAT vs SYNTH differ in exactly the dimension `ilogic.outmod` is hypothesised to
control (db.json types its value 128 as "output/store"): whether the result is
consumed by a memory op or read out of the GPR file afterwards. NAT across five
different boolean kernels additionally differs in the dimension `lut_a_free` is
hypothesised to control (which LUT2 function is selected).

Ladder rule (binding, FIELD-SWEEP-PROTOCOL sect 7 / EXP-0164): every
(arm, carrier) sweeps at least one byte ALREADY established live on G17P before
any inertness verdict from that carrier is admitted. A carrier that cannot show
its ladder is discarded, not reported as evidence of inertness.

CLEAN-ROOM: pure planning over our own db.json and our own compiled anchors.
"""
import hashlib
import json

# --------------------------------------------------------------------------
# Probe-kernel table: element type of buffer 0/1/2/3 and how many elements of
# `out` the kernel writes at grid=8. Used to build the HOST ORACLE.
#   0 = out (read back, poisoned)  1 = a  2 = b  3 = c  4 = sent (read back)
# `op` is the host-computable semantics, or None where the result is not
# exactly host-computable (estimates, and float/half/bfloat rounding) -- those
# arms are declared BASELINE-COMPARATOR arms in PRE_REGISTRATION.md sect 5.
# --------------------------------------------------------------------------
KERNELS = {
    "k_and":       {"t": "uint",   "n_out": 8,  "op": "and"},
    "k_or":        {"t": "uint",   "n_out": 8,  "op": "or"},
    "k_xor":       {"t": "uint",   "n_out": 8,  "op": "xor"},
    "k_andn":      {"t": "uint",   "n_out": 8,  "op": "andn"},
    "k_nand":      {"t": "uint",   "n_out": 8,  "op": "nand"},
    "k_and_sel":   {"t": "uint",   "n_out": 8,  "op": "and_sel"},
    "k_and_if":    {"t": "uint",   "n_out": 8,  "op": "and_sel"},
    "k_popcnt":    {"t": "uint",   "n_out": 8,  "op": "popcnt"},
    "k_clz":       {"t": "uint",   "n_out": 8,  "op": "clz"},
    "k_bfe":       {"t": "uint",   "n_out": 8,  "op": "bfe_u"},
    "k_bfe_s":     {"t": "uint",   "n_out": 8,  "op": "bfe_s"},
    "k_u32add":    {"t": "uint",   "n_out": 8,  "op": "add"},
    "k_rsqrt":     {"t": "float",  "n_out": 8,  "op": None},
    "k_rsqrt_fast": {"t": "float", "n_out": 8,  "op": None},
    "k_recip_fast": {"t": "float", "n_out": 8,  "op": None},
    "k_half2":     {"t": "half",   "n_out": 16, "op": None},
    "k_cmpsel":    {"t": "uint",   "n_out": 8,  "op": None},
    "k_bfadd":     {"t": "bfloat", "n_out": 8,  "op": None},
    "k_bfmul":     {"t": "bfloat", "n_out": 8,  "op": None},
    "k_bffma":     {"t": "bfloat", "n_out": 8,  "op": None},
}

# --------------------------------------------------------------------------
# THE ARM TABLE.
#
# `t` = target bytes: the bytes containing the BLOCKING fields (dense 0..255).
# `l` = ladder bytes: bytes whose liveness on G17P is already committed in
#       tools/agx-isa/validation.json at `hardware-run`, swept dense so the
#       carrier's detection power is a MEASUREMENT, not an assumption.
# `wide` = (field, [byte offsets]) needing the FIELD-SWEEP-PROTOCOL sect 3.3
#       set for w > 8, written across all of the field's bytes at once.
# `xplant` = cross-kernel transplant positive controls (ILOGIC only).
#
# `verdict_fields` names EXACTLY the fields this arm may emit a verdict for.
# Anything not listed is swept as an instrument and gets NO verdict -- in
# particular every `.dst` field, which is EXP-0168's, and every field already
# at emitter grade, which is only being confirmed.
# --------------------------------------------------------------------------
ARMS = [
    # ---- rank 1: THE PRIMARY TARGET -----------------------------------
    {"arm": "ILOGIC", "rank": 1, "instr": "ilogic", "kind": "int",
     "verdict_fields": ["lut_a_free", "z6", "outmod", "z8", "z9"],
     "carriers": [
         {"c": "NAT",   "probe": "k_and",     "t": [4, 6, 7, 8, 9], "l": [1, 3, 5]},
         {"c": "SYNTH", "probe": "k_and",     "t": [4, 6, 7, 8, 9], "l": [1, 3, 5]},
         {"c": "FRAME", "probe": "k_and",     "t": [4, 6, 7, 8, 9], "l": [1, 3, 5]},
         # the LUT dimension -- four more store-consumed carriers whose only
         # difference from k_and is WHICH boolean function the LUT selects.
         {"c": "NAT",   "probe": "k_or",      "t": [4, 7], "l": [1]},
         {"c": "NAT",   "probe": "k_xor",     "t": [4, 7], "l": [1]},
         {"c": "NAT",   "probe": "k_andn",    "t": [4, 7], "l": [1]},
         {"c": "NAT",   "probe": "k_nand",    "t": [4, 7], "l": [1]},
         # the PREDICATE-CONSUMED pole. db.json claims byte+7 bit7 is CLEAR on
         # the "dec2" predicate-consumed forms; if either of these kernels
         # yields such an anchor, that is a third consumer dimension.
         {"c": "NAT",   "probe": "k_and_sel", "t": [7], "l": [1]},
         {"c": "NAT",   "probe": "k_and_if",  "t": [7], "l": [1]},
     ],
     "wide": [],
     "xplant": ["k_and", "k_or", "k_xor", "k_andn", "k_nand"],
     "xplant_bytes": [2, 4, 5]},

    # ---- rank 2: `tail`, ONE field from closing ibitcount --------------
    {"arm": "IBITCOUNT", "rank": 2, "instr": "ibitcount", "kind": "int",
     "verdict_fields": ["tail"],
     "carriers": [
         {"c": "NAT",   "probe": "k_popcnt", "t": [7], "l": [3, 5, 6]},
         {"c": "NAT",   "probe": "k_clz",    "t": [7], "l": [3, 5, 6]},
         {"c": "SYNTH", "probe": "k_popcnt", "t": [7], "l": [3, 5, 6]},
         {"c": "FRAME", "probe": "k_popcnt", "t": [7], "l": [3, 5, 6]},
     ],
     "wide": [], "xplant": [], "xplant_bytes": []},

    # ---- rank 3: `tail` (w=32), ONE field from closing bf_fma_dst ------
    {"arm": "BF_FMA_DST", "rank": 3, "instr": "bf_fma_dst", "kind": "float",
     "verdict_fields": ["tail"],
     "carriers": [
         {"c": "NAT",   "probe": "k_bffma", "t": [6, 7, 8, 9], "l": [3, 4, 5]},
         {"c": "SYNTH", "probe": "k_bffma", "t": [6, 7, 8, 9], "l": [3, 4, 5]},
         {"c": "FRAME", "probe": "k_bffma", "t": [6, 7, 8, 9], "l": [3, 4, 5]},
     ],
     "wide": [("tail", [6, 7, 8, 9])], "xplant": [], "xplant_bytes": []},

    # ---- rank 4: `srcA` + `subop`, TWO fields from closing fspecial_est -
    # EXP-0161 could not promote either because BOTH its carriers were the
    # PRECISE forms, where the Newton-Raphson refinement that follows corrects
    # the estimate whatever the estimate was. SYNTH lifts the estimate ALONE
    # with nothing after it -- that is the dimension the fields control.
    {"arm": "FSPECIAL_EST", "rank": 4, "instr": "fspecial_est", "kind": "float",
     "verdict_fields": ["srcA", "subop"],
     "carriers": [
         {"c": "SYNTH", "probe": "k_rsqrt", "t": [1, 3], "l": [4, 5]},
         {"c": "FRAME", "probe": "k_rsqrt", "t": [1, 3], "l": [4, 5]},
         {"c": "NAT",   "probe": "k_rsqrt", "t": [1, 3], "l": [4, 5]},
         {"c": "NAT",   "probe": "k_recip_fast", "t": [1, 3], "l": [4, 5]},
         {"c": "NAT",   "probe": "k_rsqrt_fast", "t": [1, 3], "l": [4, 5]},
     ],
     "wide": [], "xplant": [], "xplant_bytes": []},

    # ---- rank 5: `srcA` + `b2_fmt`, TWO fields from closing iadd2 -------
    {"arm": "IADD2", "rank": 5, "instr": "iadd2", "kind": "int",
     "verdict_fields": ["srcA", "b2_fmt"],
     "carriers": [
         {"c": "NAT",   "probe": "k_u32add", "t": [2, 7], "l": [3, 5]},
         {"c": "SYNTH", "probe": "k_u32add", "t": [2, 7], "l": [3, 5]},
         {"c": "FRAME", "probe": "k_u32add", "t": [2, 7], "l": [3, 5]},
     ],
     "wide": [], "xplant": [], "xplant_bytes": []},

    # ---- rank 6: `srcA`+`srcB`+`tail`, THREE from closing bf_alu --------
    {"arm": "BF_ALU", "rank": 6, "instr": "bf_alu", "kind": "float",
     "verdict_fields": ["srcA", "srcB", "tail"],
     "carriers": [
         {"c": "NAT",   "probe": "k_bfadd", "t": [3, 4, 5, 6, 7], "l": [2]},
         {"c": "NAT",   "probe": "k_bfmul", "t": [3, 4, 5, 6, 7], "l": [2]},
         {"c": "SYNTH", "probe": "k_bfadd", "t": [3, 4, 5, 6, 7], "l": [2]},
         {"c": "FRAME", "probe": "k_bfadd", "t": [3, 4, 5, 6, 7], "l": [2]},
     ],
     "wide": [("tail", [5, 6, 7])], "xplant": [], "xplant_bytes": []},

    # ---- rank 7: `srcA`, and a carrier PAIR that differs in exactly the
    # dimension `sign_ext` controls (k_bfe unsigned vs k_bfe_s signed) -------
    {"arm": "IBFE", "rank": 7, "instr": "ibfe", "kind": "int",
     "verdict_fields": ["srcA", "sign_ext", "b2_bit0"],
     "carriers": [
         {"c": "NAT",   "probe": "k_bfe",   "t": [2, 6, 8], "l": [3, 10]},
         {"c": "NAT",   "probe": "k_bfe_s", "t": [2, 6, 8], "l": [3, 10]},
         {"c": "SYNTH", "probe": "k_bfe",   "t": [2, 6, 8], "l": [3, 10]},
     ],
     "wide": [], "xplant": [], "xplant_bytes": []},
]

# Explicitly OUT of scope, and why -- naming them is part of the result.
OUT_OF_SCOPE = {
    "*.dst": "EXP-0168 owns the field name `dst` everywhere. `dst` bytes ARE "
             "swept here as LADDER bytes (which register slot changed is the "
             "detection instrument) but NO verdict is emitted for any `.dst` "
             "field, in any arm.",
    "packed_half2_hi": "dropped from the frozen matrix: 3 blocking fields, one "
                       "of them a 16-bit `mods`, and half-precision rounding "
                       "leaves no exact host oracle. A 4th and 5th closure "
                       "candidate is not worth a weaker instrument.",
    "icmp_pred": "EXP-0169 is concurrently building the divergent-block "
                 "carrier (`NAT_kcmp`) this instruction needs for `cond`. Two "
                 "experiments on one instrument buys no extra coverage.",
    "funary": "6 blocking fields, and `funary.op` overlaps a set `match` bit "
              "(DEF-0166-1), so its descriptor needs repair before a sweep "
              "means anything.",
    "falu2.srcA_class / srcB_class": "1- and 2-bit fields sharing byte+5 with "
                                     "three emitter-grade fields; the A5 "
                                     "decomposition yields 2 and 4 sub-values, "
                                     "too thin to defend as a closure.",
}

# FIELD-SWEEP-PROTOCOL sect 3.3 wide-field sample set.
INTERIOR = [0x03, 0x05, 0x0B, 0x17, 0x2D, 0x3B, 0x55, 0x6F,
            0x97, 0xA3, 0xC7, 0xDB, 0xE5, 0xF1, 0xF9, 0xFD]


def wide_values(width):
    """{0,1,2,max-1,max} + every power of two + 16 asymmetric interior."""
    mx = (1 << width) - 1
    vals = {0, 1, 2, mx - 1, mx}
    for i in range(width):
        vals.add(1 << i)
    for i, seed in enumerate(INTERIOR):
        v = 0
        for b in range(0, width, 8):
            v |= ((seed + 17 * i + 5 * (b // 8)) & 0xFF) << b
        vals.add(v & mx)
    return sorted(vals)


def _instr_occurrence(anc, mnemonic):
    """First token of `mnemonic` in this probe's compiled `_agc.main`."""
    for k, tok in enumerate(anc.get("tokens", [])):
        if tok["mn"] == mnemonic and tok.get("len"):
            return k, tok
    return None, None


def build_cases(anchors, ranks=None):
    """anchors: the `harness/anchors.py` report, {probe: {main_hex, tokens}}.

    Returns a deterministic, frozen-order list of case dicts. A missing anchor
    is NOT an error -- the (arm, carrier) is skipped and reported
    `not_anchored`, which is an honest bound rather than a half-swept arm."""
    cases = []
    idx = 0
    skipped = []
    for spec in sorted(ARMS, key=lambda s: s["rank"]):
        if ranks and spec["rank"] not in ranks:
            continue
        mn = spec["instr"]
        for car in spec["carriers"]:
            probe = car["probe"]
            anc = anchors.get(probe)
            if not anc or "tokens" not in anc:
                skipped.append((spec["arm"], car["c"], probe, "no_anchor_report"))
                continue
            ti, tok = _instr_occurrence(anc, mn)
            if tok is None:
                skipped.append((spec["arm"], car["c"], probe, "instr_absent"))
                continue
            ilen = tok["len"]
            base = bytes.fromhex(tok["bytes"])
            common = {"arm": spec["arm"], "rank": spec["rank"],
                      "instr": mn, "kind": spec["kind"], "carrier": car["c"],
                      "probe": probe, "instr_off": tok["off"],
                      "instr_len": ilen, "tok_index": ti,
                      "anchor_bytes": tok["bytes"]}

            # ---- falsifier: byte0 := 0x00. Pre-registered to FAIL. ----
            mb = bytearray(base); mb[0] = 0x00
            cases.append(dict(common, idx=idx, role="falsifier", field=None,
                              byte_index=0, value=0, mut=[[0, 0]],
                              bytes=mb.hex(),
                              predict="non-ok (byte0 is the opcode group)"))
            idx += 1

            # ---- ladder then target, both dense 0..255 ----
            for role, blist in (("ladder", car["l"]), ("target", car["t"])):
                for bi in blist:
                    if bi >= ilen:
                        skipped.append((spec["arm"], car["c"], probe,
                                        "byte%d_beyond_len%d" % (bi, ilen)))
                        continue
                    for v in range(256):
                        mb = bytearray(base); mb[bi] = v
                        cases.append(dict(common, idx=idx, role=role,
                                          field=None, byte_index=bi, value=v,
                                          mut=[[bi, v]], bytes=mb.hex(),
                                          predict=""))
                        idx += 1

            # ---- wide fields (w > 8), written across all their bytes ----
            for fname, blist in spec["wide"]:
                if max(blist) >= ilen:
                    continue
                width = 8 * len(blist)
                for v in wide_values(width):
                    mb = bytearray(base)
                    mut = []
                    for k, bi in enumerate(blist):
                        mb[bi] = (v >> (8 * k)) & 0xFF
                        mut.append([bi, mb[bi]])
                    cases.append(dict(common, idx=idx, role="wide",
                                      field=fname, byte_index=None, value=v,
                                      mut=mut, bytes=mb.hex(), predict=""))
                    idx += 1

        # ---- cross-kernel transplant positive controls (ILOGIC) ----
        # Splice the SELECTOR bytes of kernel Y's `ilogic` into kernel X's, in
        # X's own NAT carrier, and predict X's output becomes Y's FUNCTION.
        # This is the sect 3.5 positive control: it demands a specific,
        # host-computable, non-baseline answer, so it cannot pass by inertness.
        for src in spec["xplant"]:
            a_src = anchors.get(src)
            _, tok_s = _instr_occurrence(a_src, mn) if a_src else (None, None)
            if tok_s is None:
                continue
            for dstk in spec["xplant"]:
                if dstk == src:
                    continue
                a_dst = anchors.get(dstk)
                _, tok_d = _instr_occurrence(a_dst, mn) if a_dst else (None, None)
                if tok_d is None:
                    continue
                b_d = bytearray(bytes.fromhex(tok_d["bytes"]))
                b_s = bytes.fromhex(tok_s["bytes"])
                mut = []
                for bi in spec["xplant_bytes"]:
                    if bi < len(b_d) and bi < len(b_s):
                        b_d[bi] = b_s[bi]
                        mut.append([bi, b_s[bi]])
                if not mut:
                    continue
                cases.append(dict(
                    idx=idx, arm=spec["arm"], rank=spec["rank"], instr=mn,
                    kind=spec["kind"], carrier="NAT", probe=dstk,
                    instr_off=tok_d["off"], instr_len=tok_d["len"],
                    tok_index=_instr_occurrence(a_dst, mn)[0],
                    anchor_bytes=tok_d["bytes"], role="xplant",
                    field=None, byte_index=None, value=0, mut=mut,
                    bytes=b_d.hex(), xplant_from=src, xplant_to=dstk,
                    predict="out == host oracle of %s" % src))
                idx += 1
    return cases, skipped


def matrix_sha256(cases):
    h = hashlib.sha256()
    for c in cases:
        h.update(json.dumps(c, sort_keys=True).encode())
    return h.hexdigest()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    rep = json.loads(Path(sys.argv[1]).read_text())
    cs, sk = build_cases(rep)
    print("cases       :", len(cs))
    print("matrix_sha256:", matrix_sha256(cs))
    per = {}
    for c in cs:
        per.setdefault((c["rank"], c["arm"]), {}).setdefault(
            "%s:%s" % (c["carrier"], c["probe"]), 0)
        per[(c["rank"], c["arm"])]["%s:%s" % (c["carrier"], c["probe"])] += 1
    for k in sorted(per):
        print("  %d %-14s %s" % (k[0], k[1], json.dumps(per[k], sort_keys=True)))
    print("skipped:", json.dumps(sk))
