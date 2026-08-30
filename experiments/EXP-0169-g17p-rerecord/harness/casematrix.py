#!/usr/bin/env python3
"""EXP-0169 case matrix (rule frozen at pre-registration; the RESOLVED matrix
sha256 is recorded in raw/<run>/00_env.json before the first gated dispatch).

An ARM is (instruction under test, carrier, seed provenance). Each arm names
either

  mode='lift'  -- a contiguous ALU block lifted BYTE-FOR-BYTE out of the
                  compiled form of our own MSL (kernels/probes.metal), with
                  exactly ONE db.json field mutated per case; or
  mode='synth' -- the instruction ASSEMBLED from db.json's own field rules
                  (the stronger evidence level: an independently generated
                  encoding executed on hardware); or
  mode='store' -- like 'synth' but the instruction under test is the probe
                  device_store, placed AFTER the register dump so that
                  wherever it lands is visible against the poison; or
  mode='nat'   -- spliced IN PLACE inside its own compiled kernel, which then
                  runs unmodified and is read through its own output. Used
                  where the field's effect is only observable through machinery
                  a synthesized straight-line program does not have (icmp_pred
                  sets a predicate that only a divergent block consumes).

WHICH KERNEL SUPPLIES WHICH ANCHOR IS NOT HARD-CODED. Arms name a target
mnemonic and `anchors.py`'s tokenization decides; `resolve_arms()` picks the
first liftable occurrence in the frozen kernel order. That keeps the contract
robust against the compiler choosing a different length/form than we guessed,
and a miss is reported as a miss rather than silently mutating the wrong bytes.

Coverage per field (FIELD-SWEEP-PROTOCOL section 3.3):
  width <= 8  -> ALL 2^w values, densely;
  width  > 8  -> each constituent byte swept 0..255.
Byte-wise sweeps still yield PER-FIELD attribution under EXP-0164's
collect_raw.py, because it partitions records by "the instruction word with
the field's bits cleared" and only counts movement WITHIN a partition.

Every (arm, carrier) additionally carries a pre-registered FALSIFIER and a
LIVENESS LADDER. Both are logged with a leading-underscore `field`, so
EXP-0164's collect_raw.py files them as pseudo-records and they never
contaminate field attribution. If a ladder step fails to move, that arm has no
demonstrated detection power and its inert readings are reported as
`untested`, never as `hardware-run` and never as "the field is inert".

CLEAN-ROOM: block bytes come from the compiled form of our own MSL; field
geometry comes from our own tools/agx-isa/db.json.
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
INS = dict((i["mnemonic"], i) for i in DB["instructions"])

# Frozen kernel search order for anchor resolution.
KERNEL_ORDER = [
    "k_fadd", "k_fmul", "k_fchain",
    "k_faddi", "k_fimmchain",
    "k_funi", "k_funichain",
    "k_hadd", "k_hmul", "k_hchain", "k_hsat", "k_hfma", "k_hfma_abs",
    "k_hfma_satabs",
    "k_bfadd", "k_bfmul", "k_bfchain",
    "k_popcount", "k_clz", "k_reverse", "k_ctz", "k_bitchain",
    "k_cvt_f2i", "k_cvt_i2f", "k_cvt_chain",
    "k_cmp", "k_cmp_chain",
    "k_sr",
]

# Instructions that may NOT appear inside a lifted block: they touch memory,
# control flow, or the carrier's binding table, so they would not survive being
# moved into a synthesized program. (EXP-0154 NON_LIFTABLE, minus `get_sr`:
# a special-register read names no buffer binding, and with grid=1/tg=1 every
# SR this harness reaches is deterministic. That relaxation is recorded here
# because it is a deliberate departure from EXP-0154.)
NON_LIFTABLE = {"device_load", "device_store", "stop", "jmp_exec_any",
                "jmp_exec_none", "if_push", "if_pop", "else_pop", "while_push",
                "pop_exec", "uniform_store", "threadgroup_load",
                "threadgroup_store", "wait", "spill_frame_marker",
                "frame_prologue", "link_save_restore", "device_atomic",
                "icmp_pred", "jump", "jump_cond", "ret", "pop_reconverge"}

# --------------------------------------------------------------------------
# Carriers. Two carriers identical in the dimension a field controls are ONE
# carrier, so each differs from the others in a dimension some withheld field
# is known or suspected to control.
# --------------------------------------------------------------------------
CARRIERS = {
    # id        (metal file,           function, seed kind, out words, why)
    "C1_alu":  ("carrier_dag.metal", "k", "alu",  H.OUT_WORDS,
                "operands produced by mov_imm/falu2i (ALU-sourced); float seeds "
                "have ZERO low halves"),
    "C2_load": ("carrier_dag.metal", "k", "load", H.OUT_WORDS,
                "operands produced by device_load (LOAD-sourced) with NON-ZERO "
                "low halves: the provenance dimension EXP-0158 found falu2.mod_hi "
                "depends on, and the only way a b16 source read is a different "
                "NON-ZERO value instead of 0.0"),
    "C3_uni":  ("carrier_uni.metal", "k", "alu",  H.OUT_WORDS,
                "also preloads the UNIFORM register file and has a different "
                "buffer signature: required for falu2_uni.uni_mode and "
                "falu2.srcB_class==1, and reg_move's read-back is documented to "
                "vary with the kernel's buffer signature (EXP-0087)"),
    "C4_store": ("carrier_dag.metal", "k", "alu", H.OUT_WORDS_BIG,
                 "same program shape as C1 but an 8256-word read-back, so a "
                 "device_store idx_off/base_slot sweep that lands in range is "
                 "seen as a store and not misread as a fault"),
}

# seed `kind` passed to isa_helpers.seed_instrs, per arm data type
KIND_FOR = {"alu_int": "int", "alu_float": "float", "load": "load"}


class Arm(object):
    def __init__(self, name, instr, mode, carrier, datatype, before=0, after=0,
                 prefer=(), note=""):
        self.name = name
        self.instr = instr
        self.mode = mode
        self.carrier = carrier
        self.datatype = datatype          # 'int' | 'float' (C1/C3 seed flavour)
        self.before = before
        self.after = after
        self.prefer = list(prefer)
        self.note = note

    @property
    def kind(self):
        """isa_helpers seed kind for this (carrier, datatype). The NATIVE
        carrier runs the probe kernel's own program, so it has no seed table of
        ours; `datatype` is carried only for bookkeeping."""
        if self.carrier not in CARRIERS:
            return self.datatype
        if CARRIERS[self.carrier][2] == "load":
            return "load"
        return self.datatype

    def key(self):
        return "%s@%s" % (self.name, self.carrier)


def _alu_arms():
    """LIFT arms: every withheld ALU descriptor, on >= 2 structurally different
    carriers."""
    spec = [
        # name         instr             datatype  before after  prefer
        ("FALU2",      "falu2",          "float",  0, 0, ("k_fadd", "k_fchain", "k_fmul")),
        ("FALU2I",     "falu2i",         "float",  0, 0, ("k_faddi", "k_fimmchain")),
        ("HALF_ALU",   "half_alu",       "float",  0, 0, ("k_hadd", "k_hchain", "k_hmul")),
        ("HALF_EXT8",  "half_alu_ext8",  "float",  0, 0, ("k_hfma", "k_hsat")),
        ("HALF_FMA12", "half_alu_fma12", "float",  0, 0, ("k_hfma_abs", "k_hfma_satabs")),
        ("BF_ALU",     "bf_alu",         "float",  0, 0, ("k_bfadd", "k_bfchain", "k_bfmul")),
        ("IUNARY",     "iunary",         "int",    0, 0, ("k_cvt_f2i", "k_cvt_chain", "k_cvt_i2f")),
        ("IBITCOUNT",  "ibitcount",      "int",    0, 0, ("k_popcount", "k_bitchain", "k_clz")),
        ("GET_SR",     "get_sr",         "int",    0, 0, ("k_sr",)),
    ]
    out = []
    for (nm, ins, dt, b, a, pref) in spec:
        for car in ("C1_alu", "C2_load"):
            out.append(Arm(nm, ins, "lift", car, dt, b, a, pref))
    # falu2 also on the uniform carrier: srcB_class==1 reads the NON-GPR file,
    # which only exists there.
    out.append(Arm("FALU2", "falu2", "lift", "C3_uni", "float", 0, 0,
                   ("k_fadd", "k_fchain", "k_fmul")))
    # falu2_uni exists ONLY on the uniform carrier.
    out.append(Arm("FALU2UNI", "falu2_uni", "lift", "C3_uni", "float", 0, 0,
                   ("k_funi", "k_funichain")))
    return out


def _regmove_arms():
    out = []
    for nm, ins in (("RM_C0", "reg_move_c0"), ("RM_C1", "reg_move_c1"),
                    ("RM_C2VAR", "reg_move_c2var"), ("RM_C9", "reg_move_c9"),
                    ("RM_CB", "reg_move_cb")):
        for car in ("C1_alu", "C3_uni"):
            out.append(Arm(nm, ins, "synth", car, "int", note=(
                "reg_move's read-back is documented to depend on the kernel's "
                "buffer signature (EXP-0087), so the two carriers differ in "
                "exactly that dimension")))
    return out


ARMS = (_alu_arms() + _regmove_arms()
        + [Arm("DSTORE", "device_store", "store", "C4_store", "int"),
           Arm("DSTORE", "device_store", "store", "C1_alu", "int"),
           Arm("ICMP", "icmp_pred", "nat", "NAT_kcmp", "int", note=(
               "icmp_pred sets a per-lane predicate that only a divergent block "
               "consumes, so it is spliced IN PLACE in its own compiled kernel "
               "(EXP-0139's NAT carrier style) rather than lifted"))])

# SYNTH base encodings: the unmutated instruction each synth arm mutates.
# Values are the dominant corpus forms recorded in db.json's own semantics
# notes (EXP-0087/EXP-0140), not values copied from any Apple artefact.
SYNTH_BASE = {
    "reg_move_c0":     dict(dst=3, src=0x00, form=0x20, opdesc=0x00),
    "reg_move_c1":     dict(dst=3, src=0x00, form=0x21, opdesc=0x0C),
    "reg_move_c2var":  dict(dst=3, src=0x00, form=0x22, opdesc=0x00),
    "reg_move_c9":     dict(dst=3, src=0x00, form=0x29, opdesc=0x04),
    "reg_move_cb":     dict(dst=3, src=0x00, form=0x0B, opdesc=0x00),
}

# The probe device_store the DSTORE arm mutates: it carries r0 (a known seed)
# and, unmutated, lands on the first free probe word.
DSTORE_BASE = dict(index_reg=H.R_IDX, idx_off=H.W_PROBE // H.STORE_STRIDE_WORDS,
                   base_slot=H.SLOT_OUT, data_reg=0)

# Fields another experiment owns the verdict for (coordinator directive
# 2026-08-30). They are still SWEPT here -- "which register slot changed" is
# this experiment's primary detection instrument, and dropping the sweep would
# cost us the ladder -- but analysis/verdicts.py emits NO verdict for them.
#   * the field NAME `dst`, on every descriptor            -> EXP-0168
#   * `get_sr.form`, one of the "one-field-away" rows      -> EXP-0172
# Matched as a bare field name OR as "<mnemonic>.<field>".
FOREIGN_FIELDS = {"dst", "get_sr.form"}


def is_foreign(mnemonic, field):
    return field in FOREIGN_FIELDS or ("%s.%s" % (mnemonic, field)) in FOREIGN_FIELDS


# --------------------------------------------------------------------------
# Bit surgery.
# --------------------------------------------------------------------------
def set_field(blk, tgt, start, width, value):
    """`blk` with the db field [start, start+width) of the instruction at byte
    offset `tgt` set to `value`. Bit numbering is LSB-first across the
    instruction's bytes, exactly as tools/agx-isa/db.json defines it."""
    b = bytearray(blk)
    for i in range(width):
        bit = start + i
        byi = tgt + (bit >> 3)
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
        if blk[tgt + (bit >> 3)] >> (bit & 7) & 1:
            v |= 1 << i
    return v


def set_byte(blk, tgt, byte_index, value):
    b = bytearray(blk)
    b[tgt + byte_index] = value & 0xFF
    return bytes(b)


def field_cases(mnemonic):
    """(field_name, how, param) sweep descriptors for one instruction:
    dense over the whole encodable range for w <= 8, byte-wise for w > 8."""
    out = []
    for f in INS[mnemonic]["fields"]:
        w = f["width"]
        if w <= 8:
            out.append((f["name"], "field",
                        (f["start"], w, list(range(1 << w)))))
        else:
            lo = f["start"] // 8
            hi = (f["start"] + w - 1) // 8
            for bi in range(lo, hi + 1):
                out.append((f["name"], "byte", (bi, list(range(256)))))
    return out


# --------------------------------------------------------------------------
# Anchor resolution.
# --------------------------------------------------------------------------
def resolve_arms(anchor_report):
    """For every LIFT/NAT arm find the first occurrence of its mnemonic, in the
    frozen kernel order, whose widened window is liftable. Returns
    (resolved, misses); a miss is reported, never patched around."""
    resolved, misses = {}, []
    for arm in ARMS:
        if arm.mode not in ("lift", "nat"):
            continue
        k = (arm.name, arm.instr, arm.mode)
        if k in resolved:
            continue
        order = [x for x in arm.prefer if x in anchor_report] + \
                [x for x in KERNEL_ORDER
                 if x in anchor_report and x not in arm.prefer]
        hit = None
        for fn in order:
            rep = anchor_report[fn]
            if "tokens" not in rep:
                continue
            toks = rep["tokens"]
            for i, t in enumerate(toks):
                if t["mn"] != arm.instr or t.get("len") is None:
                    continue
                lo_i = max(0, i - arm.before)
                hi_i = min(len(toks) - 1, i + arm.after)
                win = toks[lo_i:hi_i + 1]
                # NATIVE mode does not LIFT anything -- it splices the mutated
                # instruction back into the very kernel it came from -- so the
                # liftability constraint does not apply (and would reject the
                # target itself: `icmp_pred` is in NON_LIFTABLE precisely
                # because it cannot be moved out of its own program).
                if arm.mode != "nat" and any(x["mn"] in NON_LIFTABLE for x in win):
                    continue
                if any(x.get("len") is None for x in win):
                    continue
                start = win[0]["off"]
                end = win[-1]["off"] + win[-1]["len"]
                hit = {"probe": fn, "block_lo": start, "block_hi": end,
                       "tgt": t["off"] - start, "occurrence": i,
                       "ilen": t["len"]}
                break
            if hit:
                break
        if hit:
            resolved[k] = hit
        else:
            misses.append({"arm": arm.name, "instr": arm.instr,
                           "mode": arm.mode,
                           "why": "no liftable occurrence in any probe kernel"})
    return resolved, misses


# --------------------------------------------------------------------------
# Liveness ladder.
# --------------------------------------------------------------------------
# Per-instruction ladder overrides, where the generic heuristic below has no
# field to grab. Each entry is (field name, alternative value); the step is
# pre-registered to MOVE the observation.
LADDER_SPEC = {
    "device_store": [("idx_off", (H.W_PROBE // H.STORE_STRIDE_WORDS) + 1),
                     ("extmode", 2 * 7)],
    "get_sr":       [("sr_sel", None)],
}

# EXP-0140's HW-VALIDATED moving reg_move construction: byte+1 = 0x80|85,
# byte+2 = 0x01, byte+3 = 0x08 writes 85 into the destination. Used ONLY as a
# ladder step, to prove the carrier can see a reg_move write at all before any
# inert reading on the c0/c2var/c9/cb forms is believed. It deliberately leaves
# the arm's own descriptor -- that is what makes it a detection-power proof
# rather than a case.
REGMOVE_KNOWN_MOVE = (0x80 | 85, 0x01, 0x08)


def ladder_steps(arm, blk, tgt, spec):
    """Pre-registered mutations that MUST move the observation on this carrier.
    A carrier that fails a ladder step has no demonstrated detection power for
    that dimension and its inert readings prove nothing (the `iter_at.loc`
    failure mode: every arm was samples=1, where centroid and sample are the
    same point)."""
    fields = {f["name"]: f for f in spec["fields"]}
    out = []

    def bump(name, alt):
        f = fields.get(name)
        if f is None:
            return
        cur = get_field(blk, tgt, f["start"], f["width"])
        v = alt if alt != cur else (alt + 1) % (1 << f["width"])
        out.append(("L_%s" % name, set_field(blk, tgt, f["start"],
                                             f["width"], v), v,
                    "field %s %d -> %d must move" % (name, cur, v)))

    # L1 destination-slot: which register slot changed is the detection oracle
    #     the audit's `uniform_mov.dst` "16 values, 0 moved" was blind to.
    bump("dst", 5)
    # L2 source selection: point the operand at a differently-seeded register.
    for n in ("srcA_reg", "srcA", "src", "src_reg", "a_reg"):
        if n in fields:
            bump(n, 7)
            break
    # L3 operation select: fadd vs fmul (the seeds are chosen so a+b != a*b).
    for n in ("opsel", "op", "form", "cmpmode"):
        if n in fields:
            bump(n, 5)
            break
    # L4 operand WIDTH: only has detection power where the seed's low half is
    #    non-zero, i.e. on C2_load. Recorded on every carrier so the difference
    #    between the carriers is itself in the raw.
    for n in ("srcA_size", "srcB_size"):
        bump(n, 0)
    # L5 per-instruction overrides, where the heuristic above found nothing.
    for (n, alt) in LADDER_SPEC.get(arm.instr, ()):
        f = fields.get(n)
        if f is None:
            continue
        cur = get_field(blk, tgt, f["start"], f["width"])
        v = (cur + 1) % (1 << f["width"]) if alt is None else alt
        if v == cur:
            v = (cur + 1) % (1 << f["width"])
        out.append(("L_%s" % n, set_field(blk, tgt, f["start"], f["width"], v),
                    v, "field %s %d -> %d must move" % (n, cur, v)))
    # L6 reg_move only: EXP-0140's known-moving construction, to prove the
    #    carrier can observe a reg_move write BEFORE any inert reading on the
    #    c0/c2var/c9/cb forms is believed.
    if arm.instr.startswith("reg_move"):
        src, form, opd = REGMOVE_KNOWN_MOVE
        nb = bytearray(blk)
        nb[tgt + 1], nb[tgt + 2], nb[tgt + 3] = src, form, opd
        out.append(("L_known_move", bytes(nb), opd,
                    "EXP-0140 HW-VALIDATED: byte+1=0x%02x byte+2=0x%02x "
                    "byte+3=0x%02x writes 85 to the destination; if this does "
                    "not move, the carrier cannot see a reg_move write at all"
                    % (src, form, opd)))
    return out


# --------------------------------------------------------------------------
# Matrix construction.
# --------------------------------------------------------------------------
def build_cases(anchor_report):
    """The full ordered case list. Deterministic: this list IS the matrix whose
    sha256 goes into CAPTURE_CONTRACT.json / raw/<run>/00_env.json."""
    resolved, misses = resolve_arms(anchor_report)
    cases = []
    for arm in ARMS:
        spec = INS[arm.instr]
        ilen = spec["length"]
        base = dict(arm=arm.name, carrier=arm.carrier, instr=arm.instr,
                    mode=arm.mode, kind=arm.kind, note=arm.note)

        if arm.mode in ("lift", "nat"):
            r = resolved.get((arm.name, arm.instr, arm.mode))
            if r is None:
                continue
            main = bytes.fromhex(anchor_report[r["probe"]]["main_hex"])
            blk = main[r["block_lo"]:r["block_hi"]]
            tgt = r["tgt"]
            base.update(probe=r["probe"], block_lo=r["block_lo"],
                        block_hi=r["block_hi"], tgt=tgt,
                        anchor=blk[tgt:tgt + ilen].hex())
        elif arm.mode == "synth":
            p = SYNTH_BASE[arm.instr]
            blk = H.regmove(p["dst"], p["src"], p["form"], p["opdesc"])
            tgt = 0
            base.update(probe=None, block_lo=None, block_hi=None, tgt=0,
                        anchor=blk.hex())
        else:                                     # 'store'
            blk = H.device_store(**DSTORE_BASE)
            tgt = 0
            base.update(probe=None, block_lo=None, block_hi=None, tgt=0,
                        anchor=blk.hex())

        # (1) pre-registered falsifier, first, so a broken arm is visible early
        c = dict(base)
        c.update(field="__falsifier_byte0", value=0,
                 bytes=set_byte(blk, tgt, 0, 0x00).hex(), predict="not_ok")
        cases.append(c)

        # (2) liveness ladder
        for (nm, nb, v, why) in ladder_steps(arm, blk, tgt, spec):
            c = dict(base)
            c.update(field="__ladder_" + nm, value=v, bytes=nb.hex(),
                     predict="move", note=why)
            cases.append(c)

        # (3) the field sweeps
        for (name, how, param) in field_cases(arm.instr):
            if how == "field":
                start, w, vals = param
                for v in vals:
                    c = dict(base)
                    c.update(field=name, value=v,
                             bytes=set_field(blk, tgt, start, w, v).hex(),
                             fstart=start, fwidth=w, predict="",
                             foreign=is_foreign(arm.instr, name))
                    cases.append(c)
            else:
                bi, vals = param
                for v in vals:
                    c = dict(base)
                    c.update(field=name, value=v,
                             bytes=set_byte(blk, tgt, bi, v).hex(),
                             byte_index=bi, predict="",
                             foreign=is_foreign(arm.instr, name))
                    cases.append(c)

        # (4) the crossings that make the PUBLISHED falu2 semantics auditable
        #     at value level rather than assumed.
        cases += _falu2_crossings(base, blk, tgt, arm, spec)

    for i, c in enumerate(cases):
        c["idx"] = i
    return cases, resolved, misses


def _falu2_crossings(base, blk, tgt, arm, spec):
    """EXP-0138 established the source-class model and the inline 8-bit
    minifloat immediate; EXP-0158 found `mod_hi` operand-provenance-dependent
    and the immediate's sign negative at srcB_neg==0. None of that is auditable
    at value level in committed raw. These crossings make it so.

    Logged under real db field names (so collect_raw.py attributes them) with a
    `cross` tag naming the held-constant dimension."""
    out = []
    F = {f["name"]: f for f in spec["fields"]}
    if arm.instr == "falu2":
        # (a) srcB source-class 1 x srcB_reg 0..127 x srcB_neg {0,1}
        #     64..127 is the claimed inline minifloat; 0..63 the uniform file.
        if all(k in F for k in ("srcB_class", "srcB_reg", "srcB_neg")):
            for neg in (0, 1):
                for v in range(128):
                    nb = set_field(blk, tgt, F["srcB_class"]["start"],
                                   F["srcB_class"]["width"], 1)
                    nb = set_field(nb, tgt, F["srcB_neg"]["start"], 1, neg)
                    nb = set_field(nb, tgt, F["srcB_reg"]["start"],
                                   F["srcB_reg"]["width"], v & 0x3F)
                    # srcB_reg is 6 bits in db.json; the claimed 7th bit that
                    # carries the immediate is srcB_reg_top (bit 31).
                    nb = set_field(nb, tgt, F["srcB_reg_top"]["start"], 1,
                                   (v >> 6) & 1)
                    c = dict(base)
                    c.update(field="srcB_reg", value=v, bytes=nb.hex(),
                             fstart=F["srcB_reg"]["start"],
                             fwidth=F["srcB_reg"]["width"],
                             cross="srcB_class=1,srcB_neg=%d" % neg,
                             predict="", foreign=False,
                             note=("EXP-0138 inline-minifloat claim: v>=64 is an "
                                   "8-bit immediate, v<64 a uniform-file index; "
                                   "EXP-0158 claims the sign is NEGATIVE at "
                                   "srcB_neg=0"))
                    out.append(c)
        # (b) mod_hi x opsel {fadd,fmul}. Provenance (ALU vs LOAD) is the
        #     carrier axis, so this crossing plus the two carriers is the
        #     2-D test EXP-0158's claim needs.
        if "mod_hi" in F and "opsel" in F:
            for op in (4, 5):
                for v in range(1 << F["mod_hi"]["width"]):
                    nb = set_field(blk, tgt, F["opsel"]["start"],
                                   F["opsel"]["width"], op)
                    nb = set_field(nb, tgt, F["mod_hi"]["start"],
                                   F["mod_hi"]["width"], v)
                    c = dict(base)
                    c.update(field="mod_hi", value=v, bytes=nb.hex(),
                             fstart=F["mod_hi"]["start"],
                             fwidth=F["mod_hi"]["width"],
                             cross="opsel=%d" % op, predict="", foreign=False,
                             note="EXP-0158: mod_hi is operand-provenance-dependent")
                    out.append(c)
        # (c) reg_top x reg in {3,67} x the matching release flag in {0,1}
        #     -- the exact crossing EXP-0099's INERT claim was made on.
        for topf, regf, relbit in (("srcA_reg_top", "srcA_reg", 19),
                                   ("srcB_reg_top", "srcB_reg", 20)):
            if topf not in F or regf not in F:
                continue
            for rel in (0, 1):
                for reg in (3, 67):
                    for top in (0, 1):
                        nb = set_field(blk, tgt, F[regf]["start"],
                                       F[regf]["width"], reg & 0x3F)
                        nb = set_field(nb, tgt, F[topf]["start"], 1, top)
                        nb = set_field(nb, tgt, relbit, 1, rel)
                        c = dict(base)
                        c.update(field=topf, value=top, bytes=nb.hex(),
                                 fstart=F[topf]["start"], fwidth=1,
                                 cross="%s=%d,opflags_bit%d=%d"
                                       % (regf, reg, relbit, rel),
                                 predict="", foreign=False,
                                 note=("EXP-0099 claimed INERT for both "
                                       "addressing and retention on exactly "
                                       "this crossing"))
                        out.append(c)
    if arm.instr == "falu2i":
        # The whole 8-bit packed immediate space, with a host-side oracle
        # (isadb.imm_decode) per value: exp x mant x sign.
        if all(k in F for k in ("imm_exp", "imm_mant", "imm_sign", "imm_flag")):
            for sign in (0, 1):
                for e in range(16):
                    for m in range(8):
                        for fl in (0, 1):
                            nb = set_field(blk, tgt, F["imm_sign"]["start"], 1, sign)
                            nb = set_field(nb, tgt, F["imm_exp"]["start"], 4, e)
                            nb = set_field(nb, tgt, F["imm_mant"]["start"], 3, m)
                            nb = set_field(nb, tgt, F["imm_flag"]["start"], 1, fl)
                            c = dict(base)
                            c.update(field="imm_exp", value=e, bytes=nb.hex(),
                                     fstart=F["imm_exp"]["start"], fwidth=4,
                                     cross="mant=%d,sign=%d,flag=%d" % (m, sign, fl),
                                     predict="", foreign=False,
                                     note="full packed-immediate space, host oracle "
                                          "= isadb.imm_decode")
                            out.append(c)
    return out


def matrix_sha256(cases):
    blob = json.dumps([[c["arm"], c["carrier"], c["field"], c["value"],
                        c["bytes"]] for c in cases],
                      sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def main():
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cs, resolved, misses = build_cases(rep)
    from collections import Counter
    print("cases:", len(cs))
    print("matrix_sha256:", matrix_sha256(cs))
    for a, n in sorted(Counter("%s@%s" % (c["arm"], c["carrier"])
                               for c in cs).items()):
        print("   %-22s %6d" % (a, n))
    if misses:
        print("\nUNRESOLVED ARMS (reported, not patched around):")
        for m in misses:
            print("   %s" % json.dumps(m, sort_keys=True))


if __name__ == "__main__":
    main()
