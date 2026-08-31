#!/usr/bin/env python3
"""EXP-0221 case matrix.

EXP-0220 left three named blockers on the recipe dashboard, and this file is the
matrix that attacks them:

  device_store   `generated-no-donor`, held back by ONE class a compiler selects
                 -- THE THREADGROUP ADDRESS SPACE -- plus `extmode >= 128` and
                 nine fields that were SAMPLED rather than swept densely.
  device_load    `generated-no-donor`; four fields (`addr_mode`, `access_desc`,
                 `reserved7`, `reserved13`) have no emitter-grade label, and
                 EXP-0220 held `ld_format`, the index GPR, `space`, `elem_size`,
                 `base_slot`, `dst_lo`, `dst_ext9` and `ldform_hi11` at one value.
  stop           `generated-no-donor`; `stop.reserved` is a 24-bit field sampled
                 at 73 of 16,777,216 values and labelled `untested`.

Every case is a COMPLETE GENERATED PROGRAM with a host oracle, a full
architectural state dump (r0..r23), and a pre-registered Gate C bucket.

Case order here is the CANONICAL order; run221.py also dispatches shuffled.
"""

import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synth221 as S      # noqa: E402
import prog221 as P       # noqa: E402

RA, RB, RD = 1, 2, 0
R_JUNK = 13
CASE_OFF = 600                        # store under test   -> out byte 9600
PROBE_OFF = 700
TRIP_OFF = 650                        # arm S post-stop tripwire -> out byte 10400
JA, JB = 40, 77
INLINE_ONE = 24

# EXP-0141 / EXP-0092: index_reg values that FAULT (and 112, nondeterministic).
IDXREG_HAZARD = [96, 97, 100, 111, 112, 120, 127]

# ---------------------------------------------------------------------------
# EXP-0141's M4 ACCEPTED SETS, frozen in work/frozen/e141_m4_accepted_sets.json
# and used here as the PRE-REGISTERED CROSS-TARGET PREDICTION for G17P.  A
# cross-target fact may not be asserted (CLAUDE.md), but it is a perfectly good
# falsifiable hypothesis, and stating it turns a dense sweep from `measure` into
# a Gate C test with a refuter: any value where G17P disagrees with M4 is a
# first-class result.
E141 = {}


def _load_e141():
    import json
    p = HERE.parent / "work" / "frozen" / "e141_m4_accepted_sets.json"
    d = json.load(open(p))
    for k, v in d.items():
        E141[k] = set(v.get("accepted_all_runs_ok") or [])
    return E141


_load_e141()


def m4_accepts(key, v):
    s = E141.get(key)
    return None if not s else (v in s)


# ---------------------------------------------------------------------------
# THREADGROUP CONFIGURATION -- filled in by the DISCLOSED PRE-FREEZE PILOT
# (work/pilot), never by reading a compiled threadgroup access.  If the pilot
# found no working configuration the file is absent and the dense threadgroup
# arms are simply not built; the discovery arm still runs.
TGCFG = None


def _load_tgcfg():
    global TGCFG
    import json
    p = HERE.parent / "work" / "frozen" / "tg_config.json"
    if p.exists():
        TGCFG = json.load(open(p))
    return TGCFG


_load_tgcfg()


# ---------------------------------------------------------------------------
def alu_operand(pg, dst, k, salt):
    pg.falu2(dst, "fmul", R_JUNK, srcB_class=2, mod_hi=0xC, opflags=0b000,
             salt=salt + "z")
    pg.falu2(dst, "fadd", dst, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=k,
             srcB_neg=1, mod_hi=0xC, opflags=0b000, salt=salt + "v")
    return dst


def gap(pg, R=11, salt="gap"):
    """One independent ALU instruction.  EXP-0220 D11/D12: a load result is not
    architecturally visible to the VERY NEXT instruction, so every arm that
    consumes a loaded value in a following store or ALU op puts one of these in
    between."""
    pg.falu2(R, "fmul", R_JUNK, srcB_class=2, mod_hi=0xC, opflags=0b000, salt=salt)


def _new(slots, salt, offnatural=True, seed_high=True):
    pg = P.Prog(slots, salt, offnatural=offnatural)
    pg.prologue(seed_high=seed_high)
    return pg


# ---------------------------------------------------------------------------
# controls
# ---------------------------------------------------------------------------
def b_ctl_norun(c, slots, clen):
    return P.Prog(slots, c["name"])


def b_ctl_baseline(c, slots, clen):
    return _new(slots, c["name"])


def b_ctl_move(c, slots, clen):
    pg = _new(slots, c["name"])
    pg.load_f(RA, c["ja"])
    pg.load_f(RB, JB)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, load_sourced=True, opflags=0b010)
    return pg


def b_f2_falsifier(c, slots, clen):
    """Pre-registered to FAIL: the program computes fadd, the oracle fmul."""
    pg = _new(slots, c["name"])
    pg.load_f(RA, JA)
    pg.load_f(RB, JB)
    pg.falu2(RD, "fadd", RA, srcB_reg=RB, load_sourced=True, opflags=0b010,
             predict=False)
    a, b = pg.rbits(RA), pg.rbits(RB)
    pg.set_reg(RD, P.fbits(S.bits_f32(a) * S.bits_f32(b)))
    return pg


def b_ds_falsifier(c, slots, clen):
    pg = _new(slots, c["name"])
    pg.load_f(RA, JA)
    gap(pg)
    pg.load_f(RB, JB)
    gap(pg, 10, "g2")
    wrong = pg.rbits(RB)
    pg.store_predicted(RA, CASE_OFF, struct.pack("<I", wrong), tag="under_test")
    return pg


def b_s0_slot(c, slots, clen):
    pg = P.Prog({"out": 0, "mem": 1, "imem": 2}, c["name"])
    pg.movi(P.R_IDX, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    S.device_store(pg.E, P.R_IDX, 10, c["slot"], P.R_SENT,
                   salt=c["name"], offnatural=False)
    pg.writes.append(("probe", None, None, "slot%d" % c["slot"]))
    return pg


# ---------------------------------------------------------------------------
# arm S -- stop.reserved, with a POST-STOP TRIPWIRE
# ---------------------------------------------------------------------------
def b_stop(c, slots, clen):
    """The whole program is the standard skeleton; the only thing under test is
    the 24-bit body of the terminating `stop`.

    DETECTION POWER (Gate B).  `stop` has no destination and no observable of
    its own, so an inertness verdict on its body needs something that WOULD be
    observable if the instruction stopped stopping.  `finish()` emits a
    `device_store` of the sentinel register AFTER the `stop`; the scorer reads
    that out word directly and records `tripwire_written`.  The paired control
    `ctl_tripwire_pre` puts the identical store immediately BEFORE the `stop`
    and must write -- an arm whose tripwire cannot fire proves nothing."""
    pg = _new(slots, c["name"])
    pg.load_f(RA, JA)
    gap(pg)
    pg.falu2(RD, "fadd", RA, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=INLINE_ONE,
             srcB_neg=1, opflags=0b000)
    return pg


# ---------------------------------------------------------------------------
# arm L -- device_load fields, dense
# ---------------------------------------------------------------------------
def b_l_field(c, slots, clen):
    """One generated device_load with ONE descriptor field driven to the swept
    value, everything else at a documented working value.  The oracle is the
    complete 24-register state, so a load that writes the WRONG register, writes
    NOTHING, or writes extra registers is all separately visible."""
    f, v = c["field"], c["value"]
    pg = _new(slots, c["name"])
    kw = {f: v}
    pg.load_f(RD, JA, predict=c["predict"], **kw)
    gap(pg)
    return pg


def b_l_extmode(c, slots, clen):
    """extmode names the DESTINATION register (EXP-0101 H1: extmode = 2*R).
    Every register the sweep can name carries a unique codeword before the load,
    so `which register received it` is answered by the state dump rather than
    assumed."""
    v = c["value"]
    pg = _new(slots, c["name"])
    for r in c["seed_regs"]:
        pg.load_f(r, 200 + r, salt="lseed%d" % r)
    gap(pg)
    pg.load_f(RD, JA, predict=False, extmode=v)
    gap(pg, 10, "g2")
    R = (v >> 1) & 0x7F
    if c["predict"] and R < 24:
        off = S.load_byte_offset(0, JA, 3)
        pg.set_reg(R, struct.unpack("<I", P.mem_bytes()[off:off + 4])[0])
    return pg


def b_l_ldformat(c, slots, clen):
    """ld_format selects the ELEMENT SHAPE.  db.json's enum says element n lands
    in register R+n; that is a stated HYPOTHESIS here, with the state dump as
    its refuter."""
    v = c["value"]
    pg = _new(slots, c["name"])
    pg.load_f(RD, JA, predict=False, ld_format=v)
    gap(pg)
    shape = c.get("shape")
    if shape:
        width, n = shape
        src = P.mem_bytes()
        for k in range(n):
            off = S.load_byte_offset(0, JA + (k if n > 1 else 0), 3) + (4 * k if n > 1 else 0)
            word = struct.unpack("<I", src[off:off + 4])[0]
            if n == 1 and width < 4:
                prev = pg.rbits(RD + k)
                word = word & ((1 << (8 * width)) - 1)
                if prev is not None:
                    word |= prev & ~((1 << (8 * width)) - 1)
            pg.set_reg(RD + k, word)
    return pg


def b_l_indexreg(c, slots, clen):
    """index_reg sweep.  The named register is seeded with a KNOWN index, so the
    predicted load ADDRESS -- not merely `something was written` -- is the
    oracle."""
    ir = c["value"]
    pg = _new(slots, c["name"])
    idxval = c["idxval"]
    if (ir & 0x7F) < 16:
        pg.movi(ir & 0x7F, idxval)
    else:
        pg.load_i(ir & 0x7F, idxval, salt="iseed%d" % ir)
        gap(pg)
    pg.load_f(RD, c["idx_off"], predict=False, index_reg=ir)
    gap(pg, 10, "g2")
    if c["predict"]:
        off = S.load_byte_offset(idxval, c["idx_off"], 3)
        src = P.mem_bytes()
        pg.set_reg(RD, struct.unpack("<I", src[off:off + 4])[0]
                   if off + 4 <= len(src) else None)
    pg.movi(P.R_IDX, 0)
    return pg


def b_l_baseslot(c, slots, clen):
    """base_slot selects the BOUND BUFFER.  Prediction: the slot->buffer map arm
    S0 measured, plus the hypothesis that bit 7 is IGNORED (as EXP-0141 found
    for index_reg), i.e. v and v|0x80 behave identically."""
    v = c["value"]
    pg = _new(slots, c["name"])
    pg.load_f(RD, JA, predict=False, slot=v)
    gap(pg)
    base = c.get("expect_base")
    if base is not None:
        src = P.mem_bytes() if base == "mem" else (
            P.imem_bytes() if base == "imem" else P.poison_bytes())
        off = S.load_byte_offset(0, JA, 3)
        pg.set_reg(RD, struct.unpack("<I", src[off:off + 4])[0])
    return pg


# ---------------------------------------------------------------------------
# arm D -- device_store fields, dense
# ---------------------------------------------------------------------------
def _ds_seed(pg):
    """ALU-computed store data (EXP-0141: `addr_mode` bit1 is inert for this
    data-source class, which is the class a compiler selects for a computed
    value)."""
    pg.load_f(RA, JA)
    pg.falu2(RA, "fmul", RA, srcB_class=S.SRCB_CLASS_NONGPR, inline_k=INLINE_ONE,
             srcB_neg=1, load_sourced=True, opflags=0b010, salt="aluify")
    return RA


def b_d_field(c, slots, clen):
    f, v = c["field"], c["value"]
    pg = _new(slots, c["name"])
    R = _ds_seed(pg)
    pg.store(R, CASE_OFF, tag="under_test", predict=c["predict"], **{f: v})
    return pg


def b_d_extmode(c, slots, clen):
    """extmode names the SOURCE register.  MODEL, pre-registered from EXP-0220's
    own committed run01 observations at 126..200:
        even v, v/2 <= 95   -> the store writes r(v/2) at the target address
        odd  v              -> it writes r((v-1)/2)'s word TWO BYTES LOW
    Every register r0..r95 carries a unique codeword, so the model is refutable
    by the value that lands, not merely by whether something landed."""
    v = c["value"]
    pg = _new(slots, c["name"])
    R = _ds_seed(pg)
    for r in c["seed_regs"]:
        pg.load_f(r, 200 + r, salt="dseed%d" % r)
    gap(pg)
    if c["predict"]:
        src = (v >> 1) & 0x7F
        bits = pg.rbits(src)
        if v & 1:
            pg.store_predicted(R, CASE_OFF, [], extmode=v, tag="under_test")
            if bits is not None:
                off = S.store_byte_offset(0, CASE_OFF) - 2
                pg.writes.append(("out", off, list(struct.pack("<I", bits)),
                                  "under_test_shifted"))
        else:
            pg.store(R, CASE_OFF, extmode=v, tag="under_test")
    else:
        pg.store_predicted(R, CASE_OFF, [], extmode=v, tag="under_test")
    return pg


def b_d_indexreg(c, slots, clen):
    ir = c["value"]
    pg = _new(slots, c["name"])
    R = _ds_seed(pg)
    idxval = c["idxval"]
    if (ir & 0x7F) < 16:
        pg.movi(ir & 0x7F, idxval)
    else:
        pg.load_i(ir & 0x7F, idxval, salt="dis%d" % ir)
        gap(pg)
    pg.store(R, CASE_OFF, index_reg=ir, tag="under_test", predict=c["predict"])
    pg.movi(P.R_IDX, 0)
    return pg


def b_d_stformat(c, slots, clen):
    """st_format dense.  R..R+3 all carry distinct codewords and NOTHING is
    predicted for the undocumented codes: the 16 bytes at the target address are
    recorded verbatim (`target16`), so the element shape of every accepted code
    is DERIVED from data rather than assumed."""
    v = c["value"]
    pg = _new(slots, c["name"])
    for k in range(4):
        pg.load_f(RA + k, JA + k, salt="sf%d" % k)
    gap(pg)
    if c["predict"]:
        pg.store(RA, CASE_OFF, st_format=v, tag="under_test")
    else:
        pg.store_predicted(RA, CASE_OFF, [], st_format=v, tag="under_test")
    return pg


def b_d_space(c, slots, clen):
    v = c["value"]
    pg = _new(slots, c["name"])
    R = _ds_seed(pg)
    if v & 0x02:
        pg.store_predicted(R, CASE_OFF, [], space=v, tag="under_test")
    else:
        pg.store(R, CASE_OFF, space=v, tag="under_test")
    return pg


# ---------------------------------------------------------------------------
# arm T -- THE THREADGROUP ADDRESS SPACE
#
# THE ONE GAP THAT KEPT `device_store` AT `generated-no-donor` IN EXP-0220.
#
# What the DISCLOSED PRE-FREEZE PILOT (work/pilot, stages 1 and 4..9) measured,
# folded in here BEFORE this matrix was frozen -- and what it did NOT settle:
#
#  * With a static threadgroup tile declared by the carrier, a generated
#    `device_store` carrying `space` bit 1 DOES NOT FAULT, over all 256 `space`
#    values.  EXP-0220's four faults came from a carrier with no tile.  That is
#    what arm D2 re-measures here on BOTH carriers.
#  * A codeword stored by a generated threadgroup `device_store` at store
#    `idx_off = k` is read back by a generated threadgroup `device_load` at load
#    `idx_off = 4k`, AND AT NO OTHER LOAD OFFSET.  Five of five 4x pairs
#    delivered it and six of six non-4x pairs did not (pilot stage 6).  This is
#    the store-unit-16-bytes / load-unit-4-bytes asymmetry EXP-0100 measured on
#    M4 by splicing compiler-emitted threadgroup accesses; here it is measured
#    on G17P from bytes we generated, which is a different and stronger claim.
#    Arm T3 is that law as a PRE-REGISTERED BOOLEAN PREDICTION.
#  * The round trip is NOT reproducible across program shapes.  It fires inside
#    a 16-entry load bank and not for a single load with the identical
#    descriptor; which bank slot fires moves with the OTHER loads' `elem_size`
#    and with the destination registers; a dense single-reader store sweep
#    (stage 9, 3,336 cases) returned ZERO round trips at descriptors that had
#    just worked.  THE PILOT THEREFORE DOES NOT YIELD A RECIPE, and this
#    experiment does not claim one.  Arm T4 records the shape dependence rather
#    than papering over it.
BANK_REGS = [16, 17, 18, 19, 20, 21, 22, 23, 3, 4, 5, 6, 7, 8, 9, 10]
TG_SLOT_HIT = 5                      # the bank slot the pilot saw deliver


def _tg_prologue(pg, cw):
    pg.load_i(RB, P.CODEWORD_BASE + cw, salt="cw")
    gap(pg)


def _tg_tail(pg):
    gap(pg, 12, "tgg")
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.movi(P.R_IDX, 0)


def b_tg_probe(c, slots, clen):
    """ONE generated store config x a BANK of generated load configs.

    The circularity this breaks: a threadgroup store can only be observed
    through a threadgroup load whose own descriptor is equally unknown, so
    neither side can be swept while the other sits at a value nobody has
    measured.  Sixteen load configurations inside one program make each dispatch
    a 1 x 16 slice of that grid.  Nothing is predicted byte-wise; the
    measurement is WHICH bank register came back holding the codeword, and the
    codeword is chosen so an UNINITIALISED tile cannot supply it by accident."""
    pg = _new(slots, c["name"], seed_high=False)
    _tg_prologue(pg, c["cw"])
    if c["store_present"]:
        pg.tg_store(RB, c["tg_off"], c["store_cfg"])
    for k, cfg in enumerate(c["bank"]):
        pg.tg_load(BANK_REGS[k], c["load_off"], cfg)
    _tg_tail(pg)
    return pg


def b_tg_ctl_device(c, slots, clen):
    """Gate B detection power for arm T, on the DEVICE side where the answer is
    known: the identical program shape stores the codeword to a device buffer and
    reads it back into every bank register with DEVICE-space loads.  All sixteen
    must come back holding it.  If they do not, arm T's negative results say
    nothing about threadgroup space and the arm is `carrier-undecidable`.

    The prediction is written EXPLICITLY rather than left to `load_f`'s memory
    model: that model reads the PRE-DISPATCH buffer image and therefore cannot
    see this program's own store, which is what made the same control read
    `wrong_value` in the pilot while the hardware was perfectly correct."""
    pg = _new(slots, c["name"], seed_high=False)
    _tg_prologue(pg, c["cw"])
    pg.store(RB, c["tg_off"], base="mem", tag="ctl_store")
    for k in range(len(c["bank"])):
        pg.load_f(BANK_REGS[k], c["tg_off"] * 4, base="mem", predict=False,
                  salt="ctlload%d" % k)
    _tg_tail(pg)
    for k in range(len(c["bank"])):
        pg.set_reg(BANK_REGS[k], P.codeword(c["cw"]))
    return pg


def b_tg_addrlaw(c, slots, clen):
    """THE PRE-REGISTERED ADDRESS LAW.

    Prediction, frozen before this matrix ran: the codeword appears in bank slot
    %d iff `load_idx_off == 4 * store_idx_off`.  Both directions are dispatched,
    so the rule can be wrong in either -- a 4x pair that fails to deliver and a
    non-4x pair that delivers are both refutations.""" % TG_SLOT_HIT
    pg = _new(slots, c["name"], seed_high=False)
    _tg_prologue(pg, c["cw"])
    pg.tg_store(RB, c["store_off"], c["store_cfg"])
    for k, cfg in enumerate(c["bank"]):
        pg.tg_load(BANK_REGS[k], c["load_off"], cfg)
    _tg_tail(pg)
    return pg


def b_tg_shape(c, slots, clen):
    """The program-shape dependence itself, as a measurement.

    variants: `bank` (the shape that fires), `single` (one load with the
    identical descriptor), `uniform` (sixteen loads all carrying the bank's
    firing descriptor), `dist` (N independent ALU instructions between the store
    and the loads)."""
    pg = _new(slots, c["name"], seed_high=False)
    _tg_prologue(pg, c["cw"])
    pg.tg_store(RB, c["tg_off"], c["store_cfg"])
    for k in range(c.get("dist", 0)):
        gap(pg, 11, "d%d" % k)
    v = c["variant"]
    if v == "single":
        pg.tg_load(BANK_REGS[TG_SLOT_HIT], c["load_off"], c["bank"][TG_SLOT_HIT])
    elif v == "uniform":
        for k in range(16):
            pg.tg_load(BANK_REGS[k], c["load_off"], c["bank"][TG_SLOT_HIT])
    else:
        for k, cfg in enumerate(c["bank"]):
            pg.tg_load(BANK_REGS[k], c["load_off"], cfg)
    _tg_tail(pg)
    return pg


BUILDERS = {
    "ctl_norun": b_ctl_norun, "ctl_baseline": b_ctl_baseline,
    "ctl_move": b_ctl_move, "f2_falsifier": b_f2_falsifier,
    "ds_falsifier": b_ds_falsifier, "s0_slot": b_s0_slot,
    "stop": b_stop,
    "l_field": b_l_field, "l_extmode": b_l_extmode, "l_ldformat": b_l_ldformat,
    "l_indexreg": b_l_indexreg, "l_baseslot": b_l_baseslot,
    "d_field": b_d_field, "d_extmode": b_d_extmode, "d_indexreg": b_d_indexreg,
    "d_stformat": b_d_stformat, "d_space": b_d_space,
    "tg_probe": b_tg_probe, "tg_ctl_device": b_tg_ctl_device,
    "tg_addrlaw": b_tg_addrlaw, "tg_shape": b_tg_shape,
}

NO_SENTINEL = {"s0_slot", "ctl_norun"}
NO_DUMP = {"s0_slot", "ctl_norun"}


def _c(kind, name, arm, **kw):
    d = {"kind": kind, "name": name, "arm": arm, "expect_match": True,
         "hazard": False, "expect_sentinel": kind not in NO_SENTINEL,
         "predicted_bucket": "exact", "predict": True,
         "expect_codeword": None, "cw": None,
         "stop_reserved": None, "tripwire_off": None,
         "tripwire_before_stop": False}
    d.update(kw)
    return d


# ---------------------------------------------------------------------------
# the threadgroup discovery grid
# ---------------------------------------------------------------------------
def tg_load_bank():
    """16 candidate threadgroup-LOAD descriptors.

    They are built from the documented STRUCTURE, not from any compiled
    threadgroup access: `space` bit 1 is what EXP-0141's exact device rule
    (`v & 0x03 == 0x00` for a load) leaves as the non-device selector, and
    db.json's `access_desc` enum names 0 `threadgroup/other` against 32
    `device/global (bit5)`.  `elem_size` cannot be derived at all, so four
    candidates spanning the device code space and the low codes are carried."""
    bank = []
    for sp in (0x02, 0x06):
        for ad in (0x00, 0x20):
            for es in (0x46, 0x08, 0x00, 0x40):
                bank.append({"space": sp, "access_desc": ad, "elem_size": es,
                             "ld_format": 17, "base_slot": 0})
    return bank


def tg_store_grid():
    """Store configurations for the discovery arm."""
    out = []
    for sp in range(256):
        out.append({"space": sp, "access_desc": 0x00, "elem_size": 0x11,
                    "st_format": 17, "base_slot": 0, "addr_mode": 0x54})
    for es in range(256):
        out.append({"space": 0x02, "access_desc": 0x00, "elem_size": es,
                    "st_format": 17, "base_slot": 0, "addr_mode": 0x54})
    for ad in range(256):
        out.append({"space": 0x02, "access_desc": ad, "elem_size": 0x11,
                    "st_format": 17, "base_slot": 0, "addr_mode": 0x54})
    for bs in (0, 1, 2, 3, 4, 8, 16, 32, 64, 128, 255):
        out.append({"space": 0x02, "access_desc": 0x00, "elem_size": 0x11,
                    "st_format": 17, "base_slot": bs, "addr_mode": 0x54})
    for sf in (17, 1, 33, 25, 29, 23, 3, 0):
        out.append({"space": 0x02, "access_desc": 0x00, "elem_size": 0x11,
                    "st_format": sf, "base_slot": 0, "addr_mode": 0x54})
    for am in (0x54, 0x56, 0x00, 0x64, 0x04):
        out.append({"space": 0x02, "access_desc": 0x00, "elem_size": 0x11,
                    "st_format": 17, "base_slot": 0, "addr_mode": am})
    return out


def _stop_values():
    v = set()
    v |= {0, 1, 2, 3, 0xFFFFFF, 0xFFFFFE, 0x7FFFFF, 0x800000, 0x5A5A5A,
          0xA5A5A5, 0x555555, 0xAAAAAA}
    v |= {1 << b for b in range(24)}
    v |= {0xFFFFFF ^ (1 << b) for b in range(24)}
    v |= set(range(256))                       # body byte 0 dense, bytes 1/2 = 0
    v |= {0x5A5A00 | b for b in range(256)}    # body byte 0 dense, bytes 1/2 = 0x5A
    v |= {b << 8 for b in range(256)}          # body byte 1 dense
    v |= {b << 16 for b in range(256)}         # body byte 2 dense
    for n in range(128):                       # deterministic pseudorandom tail
        v.add(zlib.crc32(("stop|%d" % n).encode()) & 0xFFFFFF)
    return sorted(v)


def build_cases(include_hazard=False, arms=None):
    cs = []

    # ---- S0: base_slot by hardware probe (must run first) -----------------
    for s in range(0, 8):
        cs.append(_c("s0_slot", "s0_slot%02d" % s, "S0", slot=s,
                     predicted_bucket="measure"))

    # ---- controls ---------------------------------------------------------
    cs.append(_c("ctl_norun", "ctl_norun", "CTL"))
    cs.append(_c("ctl_baseline", "ctl_baseline", "CTL"))
    for ja in (40, 41, 300):
        cs.append(_c("ctl_move", "ctl_move_j%d" % ja, "CTL", ja=ja))
    cs.append(_c("f2_falsifier", "ctl_falsifier_falu2", "CTL", expect_match=False,
                 predicted_bucket="refute"))
    cs.append(_c("ds_falsifier", "ctl_falsifier_store", "CTL", expect_match=False,
                 predicted_bucket="refute"))
    # Gate B for arm S: the identical tripwire store placed BEFORE the stop
    # must write.  If it does not, no `stop` conclusion in arm S is supported.
    cs.append(_c("stop", "ctl_tripwire_pre", "CTL", stop_reserved=0,
                 tripwire_off=TRIP_OFF, tripwire_before_stop=True))
    cs.append(_c("stop", "ctl_tripwire_post", "CTL", stop_reserved=0,
                 tripwire_off=TRIP_OFF))

    # ---- arm T: THE THREADGROUP ADDRESS SPACE -----------------------------
    bank = tg_load_bank()
    S_TG = {"space": 0x02, "access_desc": 0x00, "elem_size": 0x11,
            "st_format": 17, "base_slot": 16, "addr_mode": 0x54}
    # T0 first: without detection power nothing else in arm T means anything.
    for n in range(4):
        cs.append(_c("tg_ctl_device", "tg_ctl_device%02d" % n,
                     "T0-detection-power", bank=bank, tg_off=64 + n, cw=n,
                     predicted_bucket="exact", expect_codeword=True))
    for n, sc in enumerate(tg_store_grid()):
        cs.append(_c("tg_probe", "tg_probe%04d" % n, "T1-tg-discovery",
                     store_cfg=sc, bank=bank, tg_off=0, load_off=0, cw=n % 100,
                     store_present=True, predicted_bucket="measure",
                     expect_codeword=None))
    for n in range(8):
        cs.append(_c("tg_probe", "tg_nostore%02d" % n, "T2-tg-negative-control",
                     store_cfg=S_TG, bank=bank, tg_off=0, load_off=0, cw=n,
                     store_present=False, predicted_bucket="measure",
                     expect_codeword=False))
    for so in (0, 1, 2, 4, 8, 16, 32, 64):
        for lo in (0, 1, 2, 4, 8, 16, 32, 64, 128, 256):
            cs.append(_c("tg_addrlaw", "tg_addr_s%03d_l%03d" % (so, lo),
                         "T3-tg-address-law", store_cfg=S_TG, bank=bank,
                         store_off=so, load_off=lo, cw=(so * 7 + lo) % 100,
                         predicted_bucket="measure",
                         expect_codeword=(lo == 4 * so)))
    for v in ("bank", "single", "uniform"):
        for d in (0, 1, 2, 4, 8, 16, 32):
            cs.append(_c("tg_shape", "tg_shape_%s_d%02d" % (v, d),
                         "T4-tg-shape", variant=v, dist=d, store_cfg=S_TG,
                         bank=bank, tg_off=0, load_off=0, cw=(d * 3) % 100,
                         predicted_bucket="measure", expect_codeword=None))

    # ---- arm L: device_load, dense ----------------------------------------
    for f, dom in (("access_desc", 256), ("addr_mode", 256), ("reserved7", 256),
                   ("reserved13", 256), ("space", 256), ("elem_size", 256),
                   ("ldform_hi11", 64), ("dst_ext9", 128), ("dst_lo", 4)):
        key = "device_load." + f
        for v in range(dom):
            ok = m4_accepts(key, v)
            cs.append(_c("l_field", "l_%s_%03d" % (f, v), "L1-%s" % f,
                         field=f, value=v, predict=True,
                         predicted_bucket="exact" if ok else "corrupt"))
    SEEDS_L = list(range(16, 24))
    for v in range(256):
        R = (v >> 1) & 0x7F
        ok = (v % 2 == 0) and R < 24
        cs.append(_c("l_extmode", "l_extmode%03d" % v, "L2-extmode",
                     value=v, seed_regs=SEEDS_L, predict=ok,
                     predicted_bucket="exact" if ok else "measure"))
    SHAPES = {17: (4, 1), 1: (2, 1), 33: (1, 1), 25: (4, 2), 29: (4, 3),
              23: (4, 4), 7: (2, 4)}
    for v in range(64):
        sh = SHAPES.get(v)
        acc = m4_accepts("device_load.ld_format", v)
        cs.append(_c("l_ldformat", "l_ldformat%02d" % v, "L3-ld_format",
                     value=v, shape=sh,
                     predicted_bucket="exact" if sh else
                     ("measure" if acc else "corrupt")))
    for v in range(256):
        base = v & 0x7F
        hz = base in IDXREG_HAZARD
        iv = (7 + base) % 64
        if iv == 12:
            iv = 13
        ok = (base < 96) and not hz
        cs.append(_c("l_indexreg", "l_indexreg%03d" % v, "L4-index_reg",
                     value=v, idxval=iv, idx_off=JA, predict=ok, hazard=hz,
                     predicted_bucket="exact" if ok else "corrupt"))
    for v in range(256):
        base = v & 0x7F
        eb = {0: "out", 1: "mem", 2: "imem"}.get(base)
        cs.append(_c("l_baseslot", "l_baseslot%03d" % v, "L5-base_slot",
                     value=v, expect_base=eb,
                     predicted_bucket="exact" if eb else "measure"))

    # ---- arm D: device_store, dense ---------------------------------------
    for f, dom, key in (("access_desc", 256, "device_store.access_desc"),
                        ("addr_mode", 256, "device_store.addr_mode"),
                        ("reserved7", 256, "device_store.reserved7"),
                        ("reserved13", 256, "device_store.reserved13"),
                        ("elem_size", 256, "device_store.elem_size"),
                        ("st_format_ext", 128, "device_store.st_format_ext"),
                        ("st_desc_hi", 64, "device_store.st_desc_hi")):
        for v in range(dom):
            ok = m4_accepts(key, v)
            cs.append(_c("d_field", "d_%s_%03d" % (f, v), "D1-%s" % f,
                         field=f, value=v, predict=True,
                         predicted_bucket="exact" if ok else "corrupt"))
    for v in range(256):
        ok = m4_accepts("device_store.space", v)
        cs.append(_c("d_space", "d_space%03d" % v, "D2-space", value=v,
                     predicted_bucket="exact" if ok else "measure"))
    SEEDS_D = list(range(24, 96))
    for v in range(256):
        R = (v >> 1) & 0x7F
        pred = R <= 95 and v < 252
        cs.append(_c("d_extmode", "d_extmode%03d" % v, "D3-extmode", value=v,
                     seed_regs=SEEDS_D, predict=pred, hazard=(v >= 252),
                     predicted_bucket="exact" if pred else "measure"))
    for v in range(256):
        base = v & 0x7F
        hz = base in IDXREG_HAZARD
        iv = (7 + base) % 64
        if iv == 12:
            iv = 13
        ok = (base < 96) and not hz
        cs.append(_c("d_indexreg", "d_indexreg%03d" % v, "D4-index_reg",
                     value=v, idxval=iv, predict=ok, hazard=hz,
                     predicted_bucket="exact" if ok else "corrupt"))
    for v in range(256):
        sh = P.ST_FORMAT_SHAPE.get(v)
        acc = m4_accepts("device_store.st_format", v)
        cs.append(_c("d_stformat", "d_stformat%03d" % v, "D5-st_format",
                     value=v, predict=bool(sh),
                     predicted_bucket="exact" if sh else "measure"))

    # ---- arm S: stop.reserved ---------------------------------------------
    for v in _stop_values():
        cf = (v & 0xFF) in (0x0F, 0x8F)
        cs.append(_c("stop", "stop_%06x" % v, "S1-stop.reserved",
                     stop_reserved=v, tripwire_off=TRIP_OFF, hazard=cf,
                     predicted_bucket="corrupt" if cf else "exact"))

    if not include_hazard:
        cs = [c for c in cs if not c["hazard"]]
    if arms:
        want = set(arms)
        cs = [c for c in cs if c["arm"].split("-")[0] in want or c["arm"] in want]
    for i, c in enumerate(cs):
        c["i"] = i
    return cs


def build_program_for(case, slots, carrier_len):
    pg = BUILDERS[case["kind"]](case, slots, carrier_len)
    if case["kind"] not in NO_DUMP:
        pg.dump()
    prog = pg.finish(carrier_len, stop_reserved=case.get("stop_reserved"),
                     tripwire_off=case.get("tripwire_off"),
                     tripwire_before_stop=case.get("tripwire_before_stop", False))
    return pg, prog


if __name__ == "__main__":
    import collections
    cs = build_cases(include_hazard=True)
    print("total cases (with hazards):", len(cs))
    for arm, n in sorted(collections.Counter(c["arm"] for c in cs).items()):
        print("  %-26s %5d" % (arm, n))
    print("without hazards:", len(build_cases(include_hazard=False)))
