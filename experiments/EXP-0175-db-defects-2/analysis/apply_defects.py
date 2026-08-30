#!/usr/bin/env python3
"""EXP-0175 — apply the re-derived defects to a copy of `tools/agx-isa/db.json`.

Every change here is gated on its own re-derivation script having printed
CONFIRMED (see RESULTS.md). Nothing is applied on the strength of EXP-0171's
RESULTS.md alone.

    python3 analysis/apply_defects.py --into <tree>/db.json [--only NAME ...]

Change sets:

  def1        DEF-0171-1  ilogic byte0 == (dst<<4)|0x0b : the 8-bit byte0 match is
                          replaced by a 4-bit low-nibble match plus a modelled
                          `dst` field. HARDWARE-PROVEN, 15/15 observable regs,
                          both gated runs (analysis/rederive_def1.py).
  def3        DEF-0171-3  ibfe.sign_ext is NOT the sign control (semantics only).
  def4        DEF-0171-4  outmod bit7 is a SOURCE-READ control, not an
                          output/store flag (enum + semantics, 3 descriptors).
  def5        DEF-0171-5  fspecial_est.subop gains the emitted value 0x0f.
  def2        DEF-0171-2  bf_{add,mul,fma}_dst.fmt gains the emitted value 0x00,
                          and the descriptors record that G17P's own bfloat ALU
                          does not tokenize because the LENGTH RULE (isadb.py,
                          not db.json) has no entry for byte0 0x31.
  fold        EXP-0173    the 25 zero-free-bit "fields" are folded into `match`:
                          they have exactly one legal value, so they are not
                          fields. Their names/semantics are preserved in a
                          `match_notes` block on the descriptor.
  merge       (H2)        the full ilogic == b_alu10_lof == b_alu10_loe merge.
                          OPT-IN ONLY -- see RESULTS.md.

CLEAN-ROOM: pure edit of our own machine-readable database.
"""
import argparse, collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))


def load(path):
    return json.loads(open(path, encoding="utf-8").read())


def save(db, path):
    # json.dumps(indent=1) reproduces the repository's db.json byte-for-byte
    open(path, "w", encoding="utf-8").write(json.dumps(db, indent=1))


def byname(db):
    return {i["mnemonic"]: i for i in db["instructions"]}


def field(instr, name):
    for f in instr["fields"]:
        if f["name"] == name:
            return f
    raise KeyError("%s.%s" % (instr["mnemonic"], name))


# ---------------------------------------------------------------- def1 --------
D1_SEM = (
    " ⚠ BYTE0 IS `(dst << 4) | 0x0b` -- DEF-0171-1, HARDWARE-PROVEN (EXP-0171, "
    "G17P; independently re-derived from that experiment's raw in EXP-0175). The "
    "pre-2026-08-30 descriptor pinned byte0 to the full 8-bit value 0x0b, so it "
    "described DESTINATION r0 ONLY and an emitter following it could never write "
    "`ilogic` anywhere else; every other destination fell through to b_alu10_lof / "
    "b_alu10_loe, whose low-nibble match is accompanied by a modelled `dst`. "
    "MEASURED: a dense byte0 sweep in a 16-GPR-dump carrier puts the AND result "
    "(93 & 107 = 73) in register `byte0 >> 4` for EVERY value whose low nibble is "
    "0xb -- 15 of 15 observable destinations, 0 misses, in BOTH gated runs. "
    "(r15 is unobservable in that carrier by construction: it is the harness's own "
    "store-index register, re-seeded before each dump.) `dst` is now modelled and "
    "the match is the low nibble. "
    "UNMODELLED DEGREE OF FREEDOM, recorded not folded (EXP-0175): byte0 BIT 3 is a "
    "DON'T-CARE on this datapath. The same sweep shows low nibble 0x3 reproduces the "
    "identical 16-register result for 15 of 16 destinations -- `0x23 03 1f 01 ...` "
    "gives a byte-identical register state to the anchor `0x2b 03 1f 01 ...`. Bit 3 "
    "is NOT folded into the match because byte0 low-nibble 3 is a populated, "
    "separately HW-validated group (n3_mov / mov_zext16 / n3_addr_prep) and this "
    "observation was made only at byte+2 == 0x1f; what bit 3 selects is UNKNOWN."
)
D1_PROV = (
    " DEF-0171-1 byte0 = (dst<<4)|0x0b: HW-VALIDATED (EXP-0171, G17P, dense byte0 "
    "sweep on the SYNTH 16-register-dump carrier, 15/15 observable destinations, "
    "0 misses, cross-run agreement 1.0000); re-derived from the committed raw in "
    "EXP-0175 (analysis/rederive_def1.py, analysis/def1_rederived.json)."
)


def apply_def1(db):
    ilog = byname(db)["ilogic"]
    assert ilog["match"] == [[0, 8, 11], [17, 7, 15]], ilog["match"]
    ilog["match"] = [[0, 4, 11], [17, 7, 15]]
    assert not any(f["name"] == "dst" for f in ilog["fields"])
    ilog["fields"].insert(0, {"name": "dst", "start": 4, "width": 4, "type": "reg"})
    ilog["semantics"] += D1_SEM
    ilog["provenance"] += D1_PROV
    # the two aliases now overlap ilogic only outside byte+2 hi-nibble 1; say so.
    for m in ("b_alu10_lof", "b_alu10_loe"):
        d = byname(db)[m]
        d["semantics"] += (
            " ⚠ SAME INSTRUCTION AS `ilogic` AT opsel_hi == 1 (DEF-0171-1, EXP-0171, "
            "HW-VALIDATED G17P): `ilogic`'s byte0 is `(dst << 4) | 0x0b` and its field "
            "layout is byte-for-byte this one (byte+1 srcA/src_reg, byte+2 op_base/"
            "opsel_hi, byte+3 srcB/srcA, byte+4/+5 lut/mod, byte+6 z6, byte+7 outmod, "
            "byte+8/+9 tail). Since EXP-0175 `ilogic` matches byte+2 hi-nibble 1 for ALL "
            "destinations, so those bytes now decode as `ilogic`; this descriptor covers "
            "the OTHER opsel_hi values. NOTE FOR LABEL AUDITORS: EXP-0171 swept only "
            "opsel_hi == 1 and reported the same cases under both key sets, so this "
            "descriptor's `hardware-run` rows are ALIASES of the ilogic sweep and no "
            "evidence in that experiment exercises opsel_hi in {2,3,4,6,8,12}.")
    return ["ilogic.match 8-bit byte0 -> low-nibble + dst field",
            "b_alu10_lof/loe semantics: alias note"]


# ---------------------------------------------------------------- def3 --------
D3 = (
    " ⚠ `sign_ext` (byte+6 bit 1) IS NOT THE SIGN CONTROL -- DEF-0171-3 "
    "(EXP-0171, G17P; re-derived in EXP-0175). It is DENSE-INERT over both its "
    "sub-values in BOTH compiler anchors -- the unsigned `extract_bits` form "
    "(a7 00 56 04 02 00 10 00 f0 11 61 00) and the SIGNED one "
    "(a7 00 56 02 03 00 12 00 f0 10 61 00) -- on three carriers x two gated runs, "
    "while byte+6 AS A WHOLE moves 254 of its 256 values on every one of those "
    "carriers, so the instrument demonstrably has detection power. db.json's earlier "
    "'signed sets sign_ext' was a CORRELATION ACROSS TWO COMPILER FORMS, not a "
    "control. The two anchors differ in byte+3 (0x04->0x02), byte+4 (0x02->0x03), "
    "byte+6 (0x10->0x12) and byte+9 `srcC_flags` (0x11->0x10); the attribution of "
    "signedness to srcC_flags bit 0 is INFERRED -- byte+9 was not swept. The field "
    "keeps its name only so its validation.json evidence row survives; treat its role "
    "as UNKNOWN. LABEL NOTE (EXP-0175): `b2_bit0`'s promotion from proven inertness "
    "rests on carriers of which only ONE STYLE has any detection power on byte+2 -- "
    "the SYNTH carrier moves 0 of 256 there -- so it is single-style evidence."
)


def apply_def3(db):
    byname(db)["ibfe"]["semantics"] += D3
    return ["ibfe semantics: sign_ext is not the sign control"]


# ---------------------------------------------------------------- def4 --------
D4 = (
    " ⚠ byte+7 BIT 7 IS A SOURCE-READ CONTROL, NOT AN OUTPUT/STORE FLAG -- "
    "DEF-0171-4 (EXP-0171, G17P, HW-VALIDATED; re-derived in EXP-0175). With bit 7 "
    "CLEAR the LUT still evaluates and the destination register is still written: "
    "the read-back buffer is un-poisoned and both integrity sentinels are intact on "
    "all 128 such values, and the DISCRIMINATOR is `nand` -- k_and/k_or/k_xor/k_andn "
    "write 0x00000000 but k_nand writes 0xFFFFFFFF, which is ~(0 & 0). A flag that "
    "zeroed the OUTPUT would give 0 for nand too. It is BOTH SOURCES that read as "
    "zero. Reproduced on five independent store-consumed carriers, both gated runs, "
    "and in a fresh-process adversarial re-run (20/20, 5 reps each). The effect is "
    "visible ONLY when the result is consumed by an adjacent memory operation: on a "
    "16-register-dump carrier the same 256 values are inert, which is why EXP-0154 "
    "read the field as inert on G17P. ALTERNATIVE NOT EXCLUDED: a writeback/publish "
    "control whose absence is invisible when the consumer is far away. ACTIONABLE "
    "RULE FOR AN EMITTER (target-independent either way): clearing byte+7 bit 7 on a "
    "logic op whose result is consumed by a memory operation LOSES THE OPERANDS."
)


def apply_def4(db):
    n = byname(db)
    ilog = n["ilogic"]
    f = field(ilog, "outmod")
    assert f.get("enum") == {"128": "output/store"}, f.get("enum")
    f["enum"] = {"128": "sources-read-enable (NOT an output/store flag -- DEF-0171-4)"}
    ilog["semantics"] += D4
    for m in ("b_alu10_lof", "b_alu10_loe"):
        d = n[m]
        f = field(d, "outmod")
        f["enum"] = {"128": "sources-read-enable (NOT an output/store flag -- DEF-0171-4)"}
        d["semantics"] += D4
    return ["ilogic/b_alu10_lof/b_alu10_loe outmod: enum + semantics corrected"]


# ---------------------------------------------------------------- def5 --------
def apply_def5(db):
    fe = byname(db)["fspecial_est"]
    f = field(fe, "subop")
    assert f["enum"] == {"9": "rcp_estimate", "11": "rsqrt_estimate",
                         "13": "sqrt_estimate"}, f["enum"]
    f["enum"]["15"] = "rsqrt_estimate (G17P precise lowering) -- DEF-0171-5"
    fe["semantics"] += (
        " SUBOP 0x0F OBSERVED AND ENCODABLE (DEF-0171-5, EXP-0171 G17P; re-derived in "
        "EXP-0175): our own precise `rsqrt` lowers on G17P to `09 83 25 0f 00 c2`, i.e. "
        "byte+3 == 0x0f, a value the pre-2026-08-30 enum did not list. The descriptor's "
        "own match ([24,1,1] and [27,1,1] and [28,4,0]) leaves exactly two free bits, so "
        "the legal subop set is {0x09, 0x0b, 0x0d, 0x0f} -- 0x0f is not an anomaly, it is "
        "the fourth member. WHAT 0x0f COMPUTES IS NOT ESTABLISHED: EXP-0171's accept-set "
        "for this field is the singleton {0x0f}, which shows every other value breaks that "
        "carrier, not that a sub-op map was measured. RANGE CAVEAT for label auditors: "
        "validation.json records `256 of 256 sub-values` for this field, but only 4 of "
        "those 256 byte values are legal encodings of this instruction.")
    return ["fspecial_est.subop: enum gains 0x0f"]


# ---------------------------------------------------------------- def2 --------
D2 = (
    " ⚠ G17P's OWN NATIVE BFLOAT ALU DOES NOT TOKENIZE -- DEF-0171-2 (EXP-0171; "
    "re-derived in EXP-0175). Our own bfloat add / mul / fma compile on G17P to "
    "`31 00 1c 00 11 00 c0 81` (8B), `31 00 1d 00 11 00 c0 81` (8B) and "
    "`31 00 1e 00 86 02 10 00 c0 81` (10B). All three raise `unknown instruction "
    "length (byte0=0x31)`. The blocker is the LENGTH RULE in isadb.py, NOT this "
    "descriptor set: the low-nibble-1 bfloat branch is gated on byte+1 in {0x02,0x04} "
    "and G17P emits byte+1 == 0x00. Given a length, these bytes are already claimed "
    "correctly and unambiguously -- bf_add_dst / bf_mul_dst / bf_fma_dst each match "
    "them with 12 match bits against bf_alu8_var's 4. The length rule is the "
    "length-rule owner's file and is REPORTED, NOT PATCHED here. Separately, "
    "`bf_alu`'s match demands byte0 == 0x11 -- a full 8-bit byte0, the same "
    "dst-nibble over-fit as DEF-0171-1 (0x31 is dst r3, 0x11 is dst r1) -- and "
    "byte+1 == 0x02, which G17P does not emit; the dst-parameterised siblings cover "
    "the general case, so that match is left alone rather than widened blind."
)


def apply_def2(db):
    n = byname(db)
    out = []
    for m in ("bf_add_dst", "bf_mul_dst", "bf_fma_dst"):
        f = field(n[m], "fmt")
        assert f["enum"] == {"2": "bf", "4": "bf2"}, (m, f["enum"])
        f["enum"]["0"] = "bf (G17P scalar form) -- DEF-0171-2"
        n[m]["semantics"] += D2
        out.append("%s.fmt: enum gains 0x00; DEF-0171-2 note" % m)
    n["bf_alu"]["semantics"] += D2
    out.append("bf_alu semantics: DEF-0171-2 note")
    return out


# ---------------------------------------------------------------- fold --------
def zero_free_rows(db):
    """Every field whose span is entirely covered by its own descriptor's match."""
    rows = []
    for i in db["instructions"]:
        covered = 0
        for (s, w, _v) in i.get("match", []):
            covered |= ((1 << w) - 1) << s
        for f in i.get("fields", []):
            span = ((1 << f["width"]) - 1) << f["start"]
            if span and not (span & ~covered):
                rows.append((i["mnemonic"], f["name"]))
    return rows


def apply_fold(db):
    """Delete the zero-free-bit fields; preserve their names + any enum/type in a
    `match_notes` block so no documentation is lost."""
    n = byname(db)
    folded = collections.defaultdict(list)
    for mn, fn in zero_free_rows(db):
        instr = n[mn]
        f = field(instr, fn)
        # the single legal value, read straight out of the match
        val = 0
        for (s, w, v) in instr["match"]:
            lo, hi = f["start"], f["start"] + f["width"]
            if s >= lo and s + w <= hi:
                val |= v << (s - lo)
        note = {"name": fn, "start": f["start"], "width": f["width"],
                "type": f["type"], "value": val}
        if f.get("enum"):
            note["enum"] = f["enum"]
        instr.setdefault("match_notes", []).append(note)
        instr["fields"].remove(f)
        folded[mn].append(fn)
    for mn in folded:
        n[mn]["semantics"] += (
            " FOLDED INTO `match` (EXP-0175, from EXP-0173's audit): %s had ZERO free "
            "bits -- every bit of the span is pinned by this descriptor's own `match`, "
            "so there is exactly one legal value and it is not a field an emitter "
            "chooses. The name, span and pinned value are preserved in `match_notes`. "
            "An emitter-grade label on such a row was a vacuous claim (DEF-0170-1)."
            % ", ".join("`%s`" % x for x in folded[mn]))
    return ["folded %d fields into match across %d descriptors"
            % (sum(len(v) for v in folded.values()), len(folded))], folded


# ---------------------------------------------------------------- merge -------
def apply_merge(db):
    """H2: collapse ilogic + b_alu10_lof + b_alu10_loe into one descriptor.
    OPT-IN. Changes the instruction count and orphans two whole validation.json
    blocks; measured in RESULTS.md, applied only if explicitly requested."""
    n = byname(db)
    ilog = n["ilogic"]
    ilog["match"] = [[0, 4, 11], [17, 3, 7]]
    ilog["fields"] = [f for f in ilog["fields"] if f["name"] != "op_base"]
    ilog["fields"].append({"name": "opsel_hi", "start": 20, "width": 4, "type": "enum",
                           "enum": {"1": "ilogic (LUT2)", "2": "0x2e", "3": "0x3e",
                                    "4": "0x4f", "6": "0x6e/0x6f", "8": "0x8f",
                                    "12": "0xcf"}})
    ilog["fields"].append({"name": "op_base", "start": 16, "width": 1, "type": "enum",
                           "enum": {"0": "xor-base", "1": "and/or-base"}})
    ilog["fields"].sort(key=lambda f: f["start"])
    db["instructions"] = [i for i in db["instructions"]
                          if i["mnemonic"] not in ("b_alu10_lof", "b_alu10_loe")]
    return ["MERGED ilogic + b_alu10_lof + b_alu10_loe into one descriptor"]



# ------------------------------------------------------------- def0174_1 -----
# DEF-0174-1 (EXP-0174, HW-VALIDATED G17P; re-derived in EXP-0175 by fitting the
# two competing models against each other on EXP-0174's own raw --
# analysis/rederive_def0174_1.py, 32/32 vs 3/32, both register plans, both runs).
N3_SRC_NOTE = (
    "byte+1 = `(S << 1) | hs` -- the ORDINARY AGX 8-bit operand descriptor, the same "
    "`(reg<<1)|size` shape every other operand byte in this database uses. "
    "S (bits 1..7) = the SOURCE GPR; hs (bit 0) = which 16-bit HALF of it is read "
    "(0 = low, 1 = high). ⚠ CORRECTED 2026-08-30, DEF-0174-1: the descriptor used to "
    "model this byte as `srcA_reg` = bits 0..6 plus `srcA_uni` = bit 7 with an enum "
    "{0: gpr, 1: uniform/hi} -- ONE BIT OFF. An emitter following that wrote S into "
    "bits 0..6, which the hardware reads as register S>>1 with half-select S&1: the "
    "WRONG REGISTER AND THE WRONG HALF, silently, with no fault. MEASURED (EXP-0174, "
    "dense byte+1 0..255 x 2 register plans x 2 gated runs, 100.000%% cross-run "
    "agreement): re-derived independently in EXP-0175 by scoring the two models "
    "against a host-computed 16-bit-granular oracle -- the corrected model fits "
    "32 of 32 host-known values in every plan and run; db.json's fits 3 of 32. "
    "The aliasing period is 64, reproduced 128 of 128 (byte+1 = v and v+128 give "
    "byte-identical 16-register dumps), which is why bit 7 -- register bit 6 -- reads "
    "as inert. NO UNIFORM FILE IS REACHABLE THROUGH THIS BYTE at any value. "
    "The 16-bit granularity is independently visible in the same data: the one seeded "
    "source with a non-zero high half (r9 = 0x40200000) is the single case where a "
    "whole-32-bit-register reading fails and the half-granular oracle succeeds.")

N3_SEM = (
    " ⚠ OPERAND BYTE CORRECTED -- DEF-0174-1 (EXP-0174, HW-VALIDATED G17P; re-derived "
    "in EXP-0175). " + N3_SRC_NOTE +
    " THE MOVE IS 16-BIT GRANULAR AND THE OTHER HALF OF THE DESTINATION IS PRESERVED, "
    "so a 32-bit copy is TWO instructions -- an ABI fact an implementer needs. "
    "EMITTER-READY ENCODING (EXP-0174, generated, not tokenized: 840 32-bit copies over "
    "all 240 ordered dst!=src pairs plus 1680 half-moves, ZERO bytes copied from any "
    "compiled shader, 0 failures against a host-computed 16-register prediction): "
    "byte0 = (dst << 4) | 0x3 ; byte+1 = (S << 1) | hs ; byte+2 with (v & 0x03) == 1 "
    "and (v & 0xC0) == 0 selects the MOVE, and byte+2 bit 3 releases the source half ; "
    "byte+3 with (v & 0x1E) == 0 makes the write happen, and byte+3 bit 0 is the "
    "DESTINATION half. Result: r[dst].half(hd) := r[S].half(hs). "
    "DEF-0174-2: byte+2 is an OP SELECTOR (narrow / move / xor / or), not a "
    "'source-class/size sub-form', and byte+3 is the destination-half select, not a "
    "'companion / second-operand descriptor' -- established over the complete "
    "256 x 256 cross-product (65,536 encodings, three runs, 100.000%% same-plan "
    "cross-run agreement). `mov_zext16` is the byte+2 & 0x07 == 0 NARROW member of "
    "this same instruction, not a separate opcode; in that sub-form byte+1 is "
    "HW-tested inert (EXP-0161), which is consistent with it being an operand byte "
    "the narrow does not read.")

FM_SEM = (
    " ⚠ OPERAND BYTE CORRECTED BY INFERENCE, NOT BY MEASUREMENT ON THIS DESCRIPTOR -- "
    "DEF-0174-1. " + N3_SRC_NOTE +
    " EVIDENCE STATUS FOR *THIS* DESCRIPTOR: `STRUCTURAL`/`INFERRED`. EXP-0174 swept "
    "`n3_mov`; it did NOT sweep `frame_marker`. This descriptor's byte+1 fields were "
    "copied from the same (wrong) model, so the correction is applied here for "
    "consistency -- but nothing has executed a `frame_marker` with a chosen source "
    "register. OPEN QUESTION, recorded not resolved (EXP-0175 DEF-0175-1): "
    "`frame_marker` matches byte0 == 0x43 exactly, while EXP-0174 measured "
    "byte0 = (dst << 4) | 0x3 for this whole group, which makes 0x43 simply "
    "`dst = r4`. Whether `frame_marker` is a distinct instruction at all is "
    "unresolved; the corpus cannot adjudicate it (identical clean/leftover either "
    "way) and it needs its own experiment.")


def apply_def0174_1(db):
    n = byname(db)
    out = []
    for m in ("n3_mov", "frame_marker"):
        d = n[m]
        f = field(d, "srcA_reg")
        assert (f["start"], f["width"]) == (8, 7), (m, f)
        u = field(d, "srcA_uni")
        assert (u["start"], u["width"]) == (15, 1), (m, u)
        f["width"] = 8
        f["note"] = N3_SRC_NOTE
        d["fields"].remove(u)
        d["semantics"] += (N3_SEM if m == "n3_mov" else FM_SEM)
        out.append("%s: srcA_reg 7->8 bits at byte+1; srcA_uni DELETED "
                   "(it was register bit 6, not a uniform selector)" % m)

    # mov_zext16 is explicitly NOT changed: its byte+1 is a different field and is
    # HW-tested inert. Record the relationship and the reason.
    z = n["mov_zext16"]
    z["semantics"] += (
        " RELATIONSHIP TO `n3_mov` (EXP-0174, G17P; recorded in EXP-0175): this is the "
        "NARROW member (byte+2 & 0x07 == 0) of the same low-nibble-3 instruction, not a "
        "separate opcode. DEF-0174-1 -- the one-bit-off operand byte -- applies to the "
        "MOVE sub-form and is corrected on `n3_mov` / `frame_marker`. It is deliberately "
        "NOT applied here: this descriptor's byte+1 is a single 8-bit `src_flag`, "
        "HW-TESTED INERT over all 256 values in two independent register forms "
        "(EXP-0161, re-derived EXP-0165), and EXP-0174 reconfirms `93 0a 00 01` leaves "
        "r5 untouched. An operand byte the narrow sub-form does not read is exactly what "
        "an inert byte+1 looks like; do not copy the move sub-form's operand model here "
        "without a sweep.")
    out.append("mov_zext16: relationship note; NO field change (byte+1 proven inert)")

    # DEF-0174-4: the standing 'no validated GPR-to-GPR move' note is now false.
    # CODEX section 8: preserve the earlier record, mark it SUPERSEDED, cite the corrector.
    c0 = n["reg_move_c0"]
    old = "AS OF 2026-08-28 NO VALIDATED GPR-TO-GPR MOVE EXISTS ON APPLE9"
    if old in c0["semantics"]:
        c0["semantics"] = c0["semantics"].replace(
            old, "[SUPERSEDED 2026-08-30 -- see the note at the end of this entry] " + old)
    c0["semantics"] += (
        " ⚠ SUPERSEDED (EXP-0174, G17P): a validated GPR-to-GPR move DOES exist on "
        "Apple9. `n3_mov` performs r[dst].half := r[S].half for arbitrary chosen "
        "registers -- 840 generated 32-bit copies over all 240 ordered dst!=src pairs "
        "and 1680 half-moves, 0 failures against a host-computed prediction, with zero "
        "bytes copied from any compiled shader. SEPARATELY AND MORE WEAKLY, EXP-0174 "
        "OBSERVED (did not sweep) that `2b (2S) 01 00` -- this family's own byte+2 == "
        "0x01 form, i.e. `reg_move_c1` -- writes r[S] into r2 for S in {0,1,3,5,8,10,14} "
        "where r[S] was written by `mov_imm`, in both register plans. That contradicts "
        "the 'UNIFORM-REGISTER-SOURCED ONLY' reading. EXP-0090's negative used sources "
        "written by falu2/falu2i and by `device_load`, and `device_load` on G17P is now "
        "known to be ASYNCHRONOUS (DEF-0169-1) -- a candidate explanation for at least "
        "that half of it. Status of the reg_move_c1 observation: OBSERVATION, NOT SWEPT; "
        "a follow-up experiment is required before it is emitted.")
    out.append("reg_move_c0: 'no validated GPR-to-GPR move' marked SUPERSEDED (DEF-0174-4)")

    # DEF-0174-3: pad_operand. The phrase 'NOT A STANDALONE HARDWARE OPCODE' is
    # CHECKED by validate_labels.py against emitter_role: data-word and must NOT be
    # removed. Record the contradicting observation alongside it.
    po = n["pad_operand"]
    po["semantics"] += (
        " ⚠ CONTRADICTING OBSERVATION, NOT A CORRECTED MODEL (EXP-0174, G17P; recorded "
        "in EXP-0175 without acting on it): the 4-byte sequence `X0 (2S) 00 01`, placed "
        "where the preceding instruction is a COMPLETED 2-byte `mov_imm`, WRITES r[S]'s "
        "value into r[X] -- verified for S in {0,1,3,5,8,10,14} and X = 2, in both "
        "register plans. 'Not a standalone opcode' does not predict an architectural "
        "effect. EXP-0174 did NOT sweep the low-nibble-0 group and cannot say whether "
        "those four bytes are one instruction or a 2-byte op plus its operand word, so "
        "the `emitter_role: data-word` classification and the phrase validate_labels.py "
        "checks are BOTH LEFT AS THEY ARE pending a dedicated experiment.")
    out.append("pad_operand: DEF-0174-3 observation recorded; classification unchanged")
    return out


CHANGES = ["def1", "def3", "def4", "def5", "def2", "def0174_1", "fold"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--into", required=True)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()
    db = load(a.into)
    want = a.only if a.only is not None else list(CHANGES)
    log, folded = [], {}
    for name in want:
        if name == "fold":
            msgs, folded = apply_fold(db)
        else:
            msgs = globals()["apply_" + name](db)
        log += msgs
    if a.merge:
        log += apply_merge(db)
    save(db, a.into)
    nf = sum(len(i.get("fields", [])) for i in db["instructions"])
    print("wrote %s : %d instructions, %d fields"
          % (a.into, len(db["instructions"]), nf))
    for m in log:
        print("  -", m)
    if folded:
        out = os.path.join(HERE, "folded_fields.json")
        json.dump(folded, open(out, "w"), indent=1)
        print("  folded rows -> %s" % out)
    return 0


sys.exit(main())
