#!/usr/bin/env python3
"""EXP-0180 case matrix. The RULE is frozen at pre-registration; the RESOLVED matrix's
sha256 is written into raw/<run>/00_env.json and must be identical in both gated runs.

An ARM is (instruction under test, base instance, mode). A CARRIER is (shader, seed table,
operand magnitudes, tail slack, second consumer). Two carriers identical in the dimension a
field controls are ONE carrier (FIELD-SWEEP-PROTOCOL section 3 rule 5), so C_HI and C_LO
differ in FIVE dimensions: buffer signature + uniform preload, seed permutation, operand
magnitude (result > 1.0 vs < 1.0, the only way `saturate` is observable), tail slack (the
framing dimension `srcB_desc` controls), and a second consumer of the block's source
half-registers (the ordering dimension `opflags` publication controls).

Field GEOMETRY always comes from the PINNED db.json -- mutations are `set_field` over
db.json's own start/width, never hand-computed offsets -- so every verdict keys cleanly to
the current db. Only byte0's high nibble is reached outside that model, and that is
hypothesis H0 (DEF-0180-1), tested by its own arm.

CLEAN-ROOM: block bytes are either lifted byte-for-byte from the compiled form of our own
MSL or generated from db.json's own field rules. No Apple binary is inspected.
"""
from __future__ import print_function

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

DB = json.loads((H.ISA_DIR / "db.json").read_text())
INS = {i["mnemonic"]: i for i in DB["instructions"]}

# The 16 distinct fields this experiment rules on (25 row-claims). Everything else swept
# here is an instrument, and no verdict is emitted for it.
TARGET_FIELDS = {
    "half_alu_ext8": ["dst", "opsel", "opflags", "srcA", "srcB_desc", "b5", "rsv6",
                      "b7_lo", "saturate", "b7_mid", "op_valid_marker"],
    "half_alu_fma12": ["dst", "opsel", "opflags", "srcA", "ext"],
}

# --------------------------------------------------------------------------
# Carriers
# --------------------------------------------------------------------------
CARRIERS = {
    "C_HI": {"source": "carrier_dag.metal", "function": "k", "seeds": "A",
             "slack": False, "consumer": False,
             "why": "buffers out/float/int; SEED_A; LARGE operand lanes so the result "
                    "magnitude exceeds 1.0 -- the only carrier on which `saturate` can be "
                    "observed at all; post-dump IMMEDIATELY after the block, so an "
                    "over-consuming length desyncs and that is visible"},
    "C_LO": {"source": "carrier_uni.metal", "function": "k", "seeds": "B",
             "slack": True, "consumer": True,
             "why": "different buffer signature + UNIFORM preload (EXP-0087's read-back "
                    "dimension); SEED_B is a different permutation so a given descriptor "
                    "selects a different value; SMALL operand lanes so the result magnitude "
                    "is below 1.0 and `saturate` must be a no-op; 8 bytes of register-neutral "
                    "tail slack so an over-consuming length is survivable and readable; and a "
                    "SECOND CONSUMER of the block's source half-registers, so an `opflags` "
                    "release/last-use/publication bit with no effect on the block's own "
                    "result can still change a downstream read"},
}

# --------------------------------------------------------------------------
# Generated base instances.
#
# byte+4 carries the LENGTH selector in its low two bits (DEF-0180-2), so it is chosen to
# keep the intended length: `& 3 == 1` -> 8 bytes (half_alu_ext8), `& 3 == 3` -> 12 bytes
# (half_alu_fma12). Bit 7 is set, matching the compiled instances, and is a documented
# don't-care in the descriptor (EXP-0169 raw: 129..155 mirrors 1..27).
#
# Operand descriptors name SEEDED registers only, and never the destination -- the exact
# two things EXP-0169's lifted anchors got wrong (DEF-0180-A: registers 64/65, never seeded;
# and even descriptors reading zero low halves). `opflags = 0` so arithmetic, not
# release-on-read, is the signal; the opflags sweep then exposes the release bits by which
# register goes to zero.
# --------------------------------------------------------------------------
DST_REG = 1        # db.json pins byte0 in `match`, so a db-expressible encoding writes r1.
                   # r1 is a destination ONLY here: no base instance names it as a source.

# half-register descriptors: odd = a HIGH half, even = a LOW half. SEED_A's low halves are
# large (|.| ~ 4..5) and SEED_B's include small ones (|.| < 1.1), which is how the two
# carriers get their result-magnitude difference.
BASE = {
    # arm        carrier   b1   b2(opflags<<3|opsel)  b3   b4    b5    b6    b7
    ("E8_ADD",  "C_HI"): (0x0D, 0x04, 0x11, 0x89, 0x15, 0x00, 0xC0),
    ("E8_ADD",  "C_LO"): (0x0C, 0x04, 0x10, 0x89, 0x14, 0x00, 0xC0),
    ("E8_FMA",  "C_HI"): (0x0D, 0x06, 0x11, 0x89, 0x15, 0x00, 0xC0),
    ("E8_FMA",  "C_LO"): (0x0C, 0x06, 0x10, 0x89, 0x14, 0x00, 0xC0),
}
# half_alu_fma12: 12 bytes, byte+4 & 3 == 3. Bytes +6..+11 keep the values our own
# k_hfma_abs compiled to, so the generated form differs from the compiled one ONLY in the
# operand descriptors.
BASE12 = {
    ("F12_FMA", "C_HI"): (0x0D, 0x06, 0x11, 0x93, 0x15, 0x00, 0x00, 0x00, 0x80, 0x01, 0x00),
    ("F12_FMA", "C_LO"): (0x0C, 0x06, 0x10, 0x93, 0x14, 0x00, 0x00, 0x00, 0x80, 0x01, 0x00),
}

ARMS = [
    ("E8_ADD",  "half_alu_ext8",  "generated",    ("C_HI", "C_LO")),
    ("E8_FMA",  "half_alu_ext8",  "generated",    ("C_HI", "C_LO")),
    ("F12_FMA", "half_alu_fma12", "generated",    ("C_HI", "C_LO")),
    ("E8_LIFT", "half_alu_ext8",  "lift-control", ("C_HI",)),
    ("F12_LIFT", "half_alu_fma12", "lift-control", ("C_HI",)),
    ("LEN",     "half_alu_ext8",  "probe",        ("C_HI",)),
    ("DSTNIB",  "half_alu_ext8",  "probe",        ("C_HI", "C_LO")),
]

LIFT_PREFER = {"E8_LIFT": ("k_hfma", "k_hsat"), "F12_LIFT": ("k_hfma_abs", "k_hfma_satabs")}


def base_block(arm, carrier):
    if (arm, carrier) in BASE:
        return H.halfop(DST_REG, *BASE[(arm, carrier)])
    if (arm, carrier) in BASE12:
        b = BASE12[(arm, carrier)]
        return bytes([H.byte0_dst(DST_REG)] + [x & 0xFF for x in b])
    return None


# --------------------------------------------------------------------------
# Bit surgery over db.json's OWN geometry.
# --------------------------------------------------------------------------
def set_field(blk, tgt, start, width, value):
    b = bytearray(blk)
    for i in range(width):
        bit = start + i
        byi = tgt + (bit >> 3)
        if byi >= len(b):
            raise IndexError("field bit %d lies outside the %d-byte block" % (bit, len(b)))
        mask = 1 << (bit & 7)
        if (value >> i) & 1:
            b[byi] |= mask
        else:
            b[byi] &= 0xFF ^ mask
    return bytes(b)


def get_field(blk, tgt, start, width):
    v = 0
    for i in range(width):
        bit = start + i
        v |= ((blk[tgt + (bit >> 3)] >> (bit & 7)) & 1) << i
    return v


def set_byte(blk, tgt, byte_index, value):
    b = bytearray(blk)
    b[tgt + byte_index] = value & 0xFF
    return bytes(b)


def field_cases(mnemonic, only=None):
    """Coverage rule (FIELD-SWEEP-PROTOCOL 3.3), frozen:
       width <= 8 -> ALL 2^w values, dense;
       width  > 8 -> every constituent byte swept 0..255.
    `half_alu_fma12.ext` is width 64 (encodable range 2^64): 8 bytes x 256 = 2048 values,
    coverage ~0.0%. PRE-REGISTERED as unable to reach `hardware-run` whatever the outcome."""
    out = []
    for f in INS[mnemonic]["fields"]:
        if only is not None and f["name"] not in only:
            continue
        w = f["width"]
        if w <= 8:
            out.append((f["name"], "field", (f["start"], w, list(range(1 << w)))))
        else:
            lo, hi = f["start"] // 8, (f["start"] + w - 1) // 8
            for bi in range(lo, hi + 1):
                out.append((f["name"], "byte", (bi, list(range(256)))))
    return out


# --------------------------------------------------------------------------
# Liveness ladder + the four pre-registered falsifiers.
#
# NOTE what is NOT here: `byte0 -> 0x00`. EXP-0169 used it as its falsifier for this family,
# and DEF-0180-1 shows it only RELOCATES the destination -- it cannot null the op. Sixteen
# rows were held on a ladder step that was never a ladder step. It is retained ONLY inside
# the DSTNIB arm, where relocation is the thing being measured.
# --------------------------------------------------------------------------
def ladder(arm, blk, tgt, spec, carrier):
    """Mutations pre-registered to MOVE the observation on this carrier. A carrier that
    fails a ladder step has no demonstrated detection power in that dimension, and its
    inert readings prove nothing (`iter_at.loc` at one sample; `get_sr` at grid=1)."""
    F = {f["name"]: f for f in spec["fields"]}
    out = []

    def bump(name, alt, why):
        f = F.get(name)
        if f is None:
            return
        cur = get_field(blk, tgt, f["start"], f["width"])
        v = alt if alt != cur else (alt + 1) % (1 << f["width"])
        out.append(("L_" + name, set_field(blk, tgt, f["start"], f["width"], v), v, why))

    # L1 -- point the byte+1 descriptor at a differently-seeded half-register. Under
    #       DEF-0180-1 this is a SOURCE, so the result must change.
    bump("dst", 0x13, "byte+1 -> h19 (a different seeded high half) must move")
    # L2 -- srcA at a differently-seeded half-register.
    bump("srcA", 0x19, "srcA -> h25 (a different seeded high half) must move")
    # L3 -- operation select: hadd vs hmul. The seeds are chosen so a+b != a*b.
    bump("opsel", H.OPSEL_HMUL, "opsel -> hmul must move (a+b != a*b for these seeds)")
    # L4 -- the third operand descriptor.
    bump("b5", 0x19, "b5 -> h25 must move")
    # L5 -- byte+4 held at the SAME length class (&3 unchanged) but a different register,
    #       so this step tests the OPERAND half of byte+4 without changing the length.
    # L6 -- half_alu_fma12 has no `b5`/`srcB_desc`: db.json swallows bytes +4..+11 into one
    #       64-bit `ext` (DEF-0180-3). Reach the third-operand byte (+5) and one tail byte
    #       (+9) directly, keeping byte+4 -- and so the LENGTH class -- untouched.
    if "ext" in F and len(blk) >= tgt + 12:
        out.append(("L_ext_b5", set_byte(blk, tgt, 5, 0x19), 0x19,
                    "byte+5 (inside `ext`) -> h25 must move: it is the third operand in the "
                    "compiled fma-abs instance"))
        out.append(("L_ext_b9", set_byte(blk, tgt, 9, 0x00), 0x00,
                    "byte+9 (inside `ext`) 0x80 -> 0x00 must move IF bytes +8..+11 are part "
                    "of the instruction at all (H2). If it does not move, that is evidence "
                    "FOR the over-consumption, not against detection power"))
    f = F.get("srcB_desc")
    if f is not None:
        cur = get_field(blk, tgt, f["start"], f["width"])
        v = (cur + 4) & 0xFF                      # same (v & 3), different register
        out.append(("L_srcB_desc_samelen", set_field(blk, tgt, f["start"], 8, v), v,
                    "byte+4 +4 keeps (v & 3) and so the LENGTH, but names a different "
                    "half-register: isolates the operand half of an overloaded byte"))
    return out


def falsifiers(arm, blk, tgt, spec, carrier):
    """Pre-registered to FAIL, i.e. each MUST produce a visible difference. If one does
    not, the instrument is void for that arm and its rows are reported `NO-DETECTION-POWER`,
    never `inert`."""
    F = {f["name"]: f for f in spec["fields"]}
    out = []
    if "opsel" in F:
        out.append(("F1_opsel_hadd",
                    set_field(blk, tgt, F["opsel"]["start"], F["opsel"]["width"], H.OPSEL_HADD),
                    H.OPSEL_HADD, "opsel -> hadd must change an fma result"))
    if "srcA" in F:
        out.append(("F2_srcA_zerolane",
                    set_field(blk, tgt, F["srcA"]["start"], 8, 2 * H.R_ZERO),
                    2 * H.R_ZERO, "srcA -> r14's low half (the one lane that IS 0.0) must move"))
    out.append(("F3_dstnib_r7", bytes([(7 << 4) | H.FAMILY_LOW_NIBBLE]) + blk[tgt + 1:],
                7, "byte0 high nibble -> 7 must move the write to r7 (H0/DEF-0180-1). "
                   "This is NOT a null-the-op falsifier -- EXP-0169 used it as one and it "
                   "cannot be one."))
    return out


# --------------------------------------------------------------------------
# The two probe arms.
# --------------------------------------------------------------------------
LEN_B2 = (0x04, 0x06)                       # opflags=0, opsel = hadd / hfma
LEN_B4 = (0x00, 0x01, 0x02, 0x03, 0x89, 0x93)


def len_cases(base):
    """H2/H3. The instruction's bytes +6.. ARE the four-marker chain, so the number of
    markers that survive reads the HARDWARE's length: 4 -> 6B, 3 -> 8B, 2 -> 10B, 1 -> 12B,
    0 -> 14B. F4 (the chain with no instruction in front of it) is the instrument's zero
    point and runs first."""
    head = bytearray(base[:6])
    out = [("__falsifier_F4_zero_point", None, None, H.marker_chain(),
            "the marker chain alone must set r8..r11 to 101..104")]
    for b2 in LEN_B2:
        for b4 in range(256):
            h = bytearray(head)
            h[2], h[4] = b2, b4
            out.append(("len_b4", "b4", b4, bytes(h) + H.marker_chain(),
                        "byte+2=0x%02x" % b2))
    for b4 in LEN_B4:
        for b2 in range(256):
            h = bytearray(head)
            h[2], h[4] = b2, b4
            out.append(("len_b2", "b2", b2, bytes(h) + H.marker_chain(),
                        "byte+4=0x%02x" % b4))
    return out


def dstnib_cases(base):
    """H0 / DEF-0180-1: byte0 = n<<4 for n = 0..15. Prediction: the result lands in the LOW
    16 bits of GPR n, leaving GPR n's HIGH 16 bits unchanged. Refuter: it lands somewhere
    fixed, or the whole register is overwritten."""
    return [("dst_nibble", n, bytes([H.byte0_dst(n)]) + base[1:],
             "H0: destination GPR = byte0 bits 4..7") for n in range(16)]


# --------------------------------------------------------------------------
# Matrix construction
# --------------------------------------------------------------------------
def build_cases(anchor_report):
    cases, misses = [], []
    for (arm, instr, mode, carriers) in ARMS:
        spec = INS[instr]
        for carrier in carriers:
            base = dict(arm=arm, carrier=carrier, instr=instr, mode=mode)
            if mode == "lift-control":
                hit = _resolve_lift(arm, instr, anchor_report)
                if hit is None:
                    misses.append({"arm": arm, "instr": instr,
                                   "why": "no liftable occurrence in any authored probe kernel"})
                    continue
                blk, tgt = hit["bytes"], 0
                base.update(probe=hit["probe"], instance="EXP-0169 anchor, base UNCHANGED",
                            anchor=blk.hex())
            elif mode == "probe":
                blk = base_block("E8_FMA", carrier if carrier in ("C_HI", "C_LO") else "C_HI")
                tgt = 0
                base.update(probe=None, instance="probe on the E8_FMA generated base",
                            anchor=blk.hex())
            else:
                blk = base_block(arm, carrier)
                tgt = 0
                base.update(probe=None,
                            instance="generated from db.json field geometry; byte0 high "
                                     "nibble = dst r%d" % DST_REG,
                            anchor=blk.hex())

            if arm == "LEN":
                for rec in len_cases(blk):
                    c = dict(base)
                    if rec[1] is None:
                        c.update(field=rec[0], value=0, bytes=rec[3].hex(),
                                 predict="markers 101..104 all land", foreign=True)
                    else:
                        c.update(field="__" + rec[0], value=rec[2], bytes=rec[3].hex(),
                                 predict="hw_len from marker survival", note=rec[4],
                                 foreign=True)
                    cases.append(c)
                continue
            if arm == "DSTNIB":
                for (fname, n, by, why) in dstnib_cases(blk):
                    c = dict(base)
                    c.update(field="__" + fname, value=n, bytes=by.hex(),
                             predict="result in r%d low half" % n, note=why, foreign=True)
                    cases.append(c)
                continue

            # (1) falsifiers first, so a void instrument is visible before any sweep
            for (nm, by, v, why) in falsifiers(arm, blk, tgt, spec, carrier):
                c = dict(base)
                c.update(field="__falsifier_" + nm, value=v, bytes=by.hex(),
                         predict="must_move", note=why, foreign=True)
                cases.append(c)
            # (2) liveness ladder
            for (nm, by, v, why) in ladder(arm, blk, tgt, spec, carrier):
                c = dict(base)
                c.update(field="__ladder_" + nm, value=v, bytes=by.hex(),
                         predict="must_move", note=why, foreign=True)
                cases.append(c)
            # (3) the field sweeps -- ONLY this experiment's 16 target fields
            for (name, how, param) in field_cases(instr, only=TARGET_FIELDS[instr]):
                if how == "field":
                    start, w, vals = param
                    for v in vals:
                        c = dict(base)
                        c.update(field=name, value=v, fstart=start, fwidth=w,
                                 bytes=set_field(blk, tgt, start, w, v).hex(),
                                 byte_index=None, predict="", foreign=False)
                        cases.append(c)
                else:
                    bi, vals = param
                    for v in vals:
                        c = dict(base)
                        c.update(field=name, value=v, byte_index=bi,
                                 fstart=None, fwidth=None,
                                 bytes=set_byte(blk, tgt, bi, v).hex(),
                                 predict="", foreign=False)
                        cases.append(c)
    for i, c in enumerate(cases):
        c["idx"] = i
    return cases, misses


def _resolve_lift(arm, instr, rep):
    for fn in LIFT_PREFER[arm]:
        r = rep.get(fn)
        if not r or "tokens" not in r:
            continue
        main = bytes.fromhex(r["main_hex"])
        for t in r["tokens"]:
            if t["mn"] == instr and t.get("len"):
                return {"probe": fn, "off": t["off"], "len": t["len"],
                        "bytes": main[t["off"]:t["off"] + t["len"]]}
    return None


def matrix_sha256(cases):
    blob = json.dumps([[c["arm"], c["carrier"], c["field"], c["value"], c["bytes"]]
                       for c in cases], sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def main():
    rep_path = EXP / "work" / "anchors" / "anchor_report.json"
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    cs, misses = build_cases(rep)
    from collections import Counter
    print("cases:", len(cs))
    print("matrix_sha256:", matrix_sha256(cs))
    for k, n in sorted(Counter("%s@%s" % (c["arm"], c["carrier"]) for c in cs).items()):
        print("   %-18s %6d" % (k, n))
    print("distinct encodings:", len({c["bytes"] for c in cs}))
    if misses:
        print("\nUNRESOLVED ARMS (reported, not patched around):")
        for m in misses:
            print("   " + json.dumps(m, sort_keys=True))


if __name__ == "__main__":
    main()
