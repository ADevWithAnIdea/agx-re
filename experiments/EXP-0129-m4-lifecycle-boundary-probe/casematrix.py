#!/usr/bin/env python3
"""EXP-0126 shared case matrix: the three remaining register-lifecycle
unknowns (H1 widened axes / H2 mechanism discrimination / H3 A18-vs-M4).
Single source of truth imported by run.py, verify.py, analysis.py.

Builds directly on the fully-settled arc (docs/isa/register-move-and-liveness.md,
EXP-0086/0089/0099/0113/0119) -- nothing here re-derives an already-closed
fact. See PRE_REGISTRATION.md for the frozen falsifier design each group
answers and PROGRESS.md for the pilot-phase evidence (every construction
below was smoke-tested on real M4 hardware in work/pilot_* before this file
was frozen; the pilot caught FOUR real bugs, documented at their fix sites
below and in PROGRESS.md: (1) a fragment-stage MODE-B splice target that
proved not observably live on the rendered-pixel path -- H1_FRAGMENT is
consequently NOT REACHED, disclosed rather than faked; (2) CF-boundary's
first transcription of the reused EXP-0112/cf.py skeleton had one wrong
opflags nibble, caught by a byte-exact round-trip diff against the
original before any hardware run; (3) device_load-sourced falu2i operands
require `mods=0xC0` (EXP-0101's own finding) -- an early pilot omitted it
and silently read zero; (4) agxtest.py's `--splice SYM@OFF=HEX` offset is
RELATIVE to the symbol region, not the archive's absolute file offset --
an early H3 pilot used the absolute offset and spliced garbage bytes past
the end of a 44-byte kernel, which is itself what surfaced the
grid-size-independent all-zero readback that first looked like (but was
not) a genuine hardware effect.

Case "modes":
  MODE A (the majority): a fully HAND-ASSEMBLED straight-line program (via
    isa_helpers.py's isadb.assemble()-based builders), spliced whole into a
    carrier kernel's `_agc.main` region at offset 0 (isa_helpers.build_program
    for carrier/carrier_dag; isa_helpers.build_cf_topbit_program for
    carrier_cf's reused skeleton). Full control over instruction order and
    every field; independent of compiler scheduling.
  MODE B (H3_MODEB only): byte-field splice into a REAL COMPILED kernel's
    specific instruction offset (kernels/iunary_popcount.metal, reused
    VERBATIM from EXP-M4-14's own corpus/halfint/iunary.metal -- our own
    MSL, recompiled fresh in this experiment's own tree). Used to replicate
    EXP-M4-14's own literal A18 test as closely as this experiment's
    tooling allows, varying dispatch shape (grid) as the ONE axis while
    holding the OPERAND-PROVENANCE axis fixed (device_load-sourced, exactly
    as the original A18 kernel computes o[i]=popcount(a[i])).

REGISTER-ADDRESSING SCOPE (repeated from EXP-0119/EXP-0099's own
isa_helpers.py -- READ IT): every family used here for hand construction
has an independently HW-VALIDATED register field (falu2/falu2i's
srcA_reg/srcB_reg, EXP-0099 H1; device_load's extmode=2*target_register
formula with dst_lo/dst_ext9=(1,1), EXP-0101 H1, re-validated by this
experiment's own pilot at PROGRESS.md Milestone 3; ibitcount's
dst=reg<<1/src=reg<<2, EXP-M4-14 direct hardware splice, re-confirmed this
experiment's own pilot; carrier_cf's loop+if/else skeleton, EXP-0112/
EXP-0090, byte-for-byte reused, re-confirmed byte-identical by this
experiment's own pilot AND independently HW-re-executed with a matching
oracle before any case here was frozen).

IMMEDIATE PALETTE (frozen; isa_helpers.imm_value -- same fixed points
EXP-0099/EXP-0119 already validated, re-confirmed here):
  V  = imm_value(30.0)  = 30.0   seed value for the primary test register
  K2 = imm_value(20.0)  = 20.0   later-reader's increment
Both independently confirmed exact round-trip fixed points (no rounding).

WORD-SLOT CONVENTION (device_store's idx_off unit = 4 words = 16 bytes,
HW-VALIDATED EXP-0090, re-confirmed EXP-0119/this experiment's pilot):
idx_off=0 -> word0, 1 -> word4, 2 -> word8, 3 -> word12.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only: assemble/disassemble/decode_one)
import isa_helpers as H  # noqa: E402

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
CARRIER_LEN = 170             # kernels/carrier.metal's _agc.main length, MODE A (EXP-0119)
DAG_CARRIER_LEN = 1536        # kernels/carrier_dag.metal, MODE A (EXP-0112, own pilot re-confirmed)
CF_CARRIER_LEN = H.CF_CARRIER_LEN   # 152, kernels/carrier_cf.metal (EXP-0112/EXP-0090)

KERNEL_IO = {
    "carrier":     {"out_buf": 0, "in_buf": 1, "in_pack": "f32",
                     "in_vals": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], "out_words": 16},
    "carrier_dag": {"out_buf": 0, "in_buf": 1, "in_pack": "f32",
                     "in_vals": [float(i) for i in range(40)], "out_words": 8,
                     "extra_bufs": {2: ("i32", [0] * 8)}},   # buffer(2)=imem, unused by our splice, still bound
    "carrier_cf":  {"out_buf": 0, "in_pack": None, "out_words": 4,
                     "extra_bufs": None},   # per-case float/int bufs (a_val/n_val), see case()
    "iunary_popcount": {"out_buf": 2, "in_buf": 0, "in_pack": "u32",
                         "in_vals": [15, 16, 65535, 0x40000001], "out_words": 4},
}

V = H.imm_value(30.0)
K2 = H.imm_value(20.0)
assert (V, K2) == (30.0, 20.0), "immediate palette drifted from its frozen fixed points"

R_IDX = H.R_IDX
R_UNW = H.R_UNWRITTEN


def modeA_program(instrs, carrier_len=CARRIER_LEN):
    body = [H.mov_imm(R_IDX, 0)] + list(instrs) + [H.stop()]
    prog = H.build_program(body, carrier_len)
    H.assert_round_trip(prog)
    return prog


def seed_r3():
    """r3 = V, via falu2i(srcA=UNWRITTEN, k=V) -- HW-VALIDATED path
    (EXP-0087 MOVE-04: unwritten reads exactly 0.0)."""
    return H.falu2i_raw(3, R_UNW, V, opflags4=0)


def reader(dst, k, srcA_reg=3, opflags4=0, mods=0):
    """A separate, later falu2i reading srcA_reg (default r3) again."""
    return H.falu2i_raw(dst, srcA_reg, k, opflags4=opflags4, mods=mods)


def store(dst_word_idx, data_reg):
    assert dst_word_idx % 4 == 0
    return H.device_store(R_IDX, dst_word_idx // 4, 0, data_reg=data_reg)


def case(name, group, kernel, splices, oracle, notes, grid=1, tg=1, extra_bufs=None):
    """One case record. `splices` is [(abs_offset_into_ARCHIVE_or_relative_
    into_agc.main, hex), ...] -- for MODE A carrier kernels this is always
    [(0, whole_program_hex)] (offset relative to _agc.main, i.e. 0 == the
    region's own start); harness/case_exec.py always passes offsets THROUGH
    to agxtest.py's `--splice _agc.main@OFF=HEX`, which is relative to the
    symbol region (see this file's own module docstring bug #4)."""
    return {"name": name, "group": group, "kernel": kernel, "grid": grid, "tg": tg,
            "splices": splices, "oracle": {str(k): v for k, v in oracle.items()},
            "notes": notes, "extra_bufs": extra_bufs}


# ===========================================================================
# H1 -- bits 15/31 in NEW, wider contexts
# ===========================================================================
def build_h1_cf():
    """H1_CF: bits 15/31 across a REAL loop+if/else control-flow boundary,
    reusing EXP-0112/EXP-0090's own HW-VALIDATED carrier_cf.metal skeleton
    byte-for-byte except the "arm_true" falu2i's srcA_reg field. TRUE-arm
    parameters (a=90,n=10 -> acc=105>100) select r2 (the field-varied
    instruction's OWN result) into the stored output -- an ADDRESSING probe
    (does field=0x01 vs the skeleton's natural 0x41 change what gets read?).
    FALSE-arm parameters (a=10,n=5 -> acc=17.5<=100) select r3 (the
    UNTOUCHED sibling instruction's result, itself ALSO a reader of the
    SAME register r1/acc, executed immediately after the field-varied one)
    -- a RETENTION probe (does varying the EARLIER instruction's field
    corrupt a LATER, independent reader of the same register, across the
    if/else reconvergence?) with ZERO extra instruction bytes (CF_CARRIER_LEN
    has no slack -- PROGRESS.md pilot finding). Own pilot (PROGRESS.md):
    all 4 combinations match their host oracle exactly; a positive control
    (srcA_reg low6 changed 1->6, reading the loop-counter register instead
    of acc) gives 0.0, proving the harness detects a real addressing change
    at this exact position."""
    cs = []
    for label, (a_val, n_val, arm) in {
        "true": (90.0, 10.0, "arm_true"), "false": (10.0, 5.0, "arm_false"),
    }.items():
        for tag, srcA_byte in (("base", 0x41), ("bit15clr", 0x01)):
            hexhex, out0, meta = H.build_cf_topbit_program(a_val, n_val, srcA_byte)
            bufs = {1: ("f32", [a_val] * 4), 2: ("i32", [int(n_val)] * 4)}
            cs.append(case("h1_cf_%s_%s" % (label, tag), "H1_CF", "carrier_cf",
                            [(0, hexhex)], {0: out0},
                            "CF skeleton, srcA_reg=0x%02x on the field-varied falu2i "
                            "(top-bit %s, low6=1=acc); %s arm selected (isel10); "
                            "meta=%r" % (srcA_byte, "SET" if srcA_byte & 0x40 else "clear", arm, meta),
                            extra_bufs=bufs))
    # positive control: TRUE-arm, but the varied instruction's LOW 6 bits
    # (not just the top bit) point at the loop-counter register (r6) instead
    # of acc (r1) -- proves the harness can detect a genuine addressing
    # change at this exact field, own pilot: RESULT 0.0 (PROGRESS.md).
    hexhex, _, meta = H.build_cf_topbit_program(90.0, 10.0, 0x46)
    cs.append(case("h1_cf_positive_control", "H1_CF", "carrier_cf",
                    [(0, hexhex)], {0: 0.0},
                    "positive control: srcA_reg low6 changed 1->6 (reads the loop-counter "
                    "register, not acc) -- must NOT match the true-arm oracle 210.0",
                    extra_bufs={1: ("f32", [90.0] * 4), 2: ("i32", [10] * 4)}))
    return cs


def build_h1_load():
    """H1_LOAD: bits 15/31 when the operand's PROVENANCE is a device_load
    (EXP-0101's bridge formula: extmode=2*target_register, dst_lo/dst_ext9=
    DST_TOKEN_KNOWNGOOD=(1,1)) rather than an ALU write. `falu2i` with a
    load-sourced operand additionally requires mods=0xC0 (EXP-0101
    HW-VALIDATED) -- own pilot (PROGRESS.md Milestone 3) caught this: a
    first attempt with the naive mods=0 default silently read zero for
    EVERY case regardless of field value, which would have been
    misreported as "corrupted" without the diagnostic that traced it to
    the missing mods bits."""
    cs = []
    LOADVAL = 42.0
    for X in (7, 71):
        for b in (0, 1):
            instrs = [H.device_load_fixed(R_IDX, 0, elem_code=3, base_slot=1,
                                            extmode=2 * 7, dst_lo=H.DST_TOKEN_KNOWNGOOD[0],
                                            dst_ext9=H.DST_TOKEN_KNOWNGOOD[1]),
                      H.falu2i_raw(0, X, K2, opflags4=b, mods=0xC0),
                      store(0, 0),
                      reader(1, K2, srcA_reg=7, mods=0xC0),
                      store(4, 1)]
            prog = modeA_program(instrs)
            own = LOADVAL + K2
            later = K2 if b else LOADVAL + K2
            cs.append(case("h1_load_X%d_b%d" % (X, b), "H1_LOAD", "carrier",
                            [(0, prog.hex())], {0: own, 4: later},
                            "device_load-sourced r7 (LOADVAL=42.0, EXP-0101 bridge formula, "
                            "mods=0xC0), falu2i srcA_reg=%d(bit15=%d), opflags bit0=%d; "
                            "word0=own(addressing), word4=later-read(retention)" % (X, X >> 6, b),
                            extra_bufs={1: ("f32", [LOADVAL, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])}))
    return cs


def build_h1_halfwidth():
    """H1_HALFWIDTH: bits 15/31 at srcA_size=0 (b16/half) instead of the
    established b32 context. Own pilot (PROGRESS.md): a b16-seeded register,
    read back IMMEDIATELY by a b16 store, correctly returns 30.0 -- but a
    SECOND b16 instruction reading that same register (regardless of field
    value OR retention bit) reads it as 0 in all 4 combinations. This is
    reported as an OBSERVED, UNINTERPRETED anomaly specific to the
    half-width construction (see RESULTS.md) -- NOT silently folded into a
    "bit15/31 is inert at b16 too" claim, though the narrow claim that
    varying the FIELD/RETENTION bit changes nothing at b16 either IS
    supported (all 4 combinations are byte-identical to each other)."""
    cs = []
    for X in (3, 67):
        for b in (0, 1):
            instrs = [H.falu2i_raw(3, R_UNW, V, opflags4=0, srcA_size=0),
                      H.falu2i_raw(0, X, K2, opflags4=b, srcA_size=0),
                      store(0, 0),
                      H.falu2i_raw(1, 3, K2, opflags4=0, srcA_size=0),
                      store(4, 1)]
            prog = modeA_program(instrs)
            cs.append(case("h1_halfwidth_X%d_b%d" % (X, b), "H1_HALFWIDTH", "carrier",
                            [(0, prog.hex())], {0: None, 4: None},   # EXPLORATORY -- see notes
                            "srcA_size=0 (b16) throughout; field=%d(bit15=%d) opflags bit0=%d. "
                            "EXPLORATORY: own pilot found word0=word4=20.0 in ALL 4 (X,b) "
                            "combinations (own-result reads v as 0 even in the b=0/retain case) "
                            "-- an anomaly independent of X and b, recorded not interpreted; the "
                            "narrow claim under test (does X or b change ANYTHING at b16) is "
                            "answered by cross-case comparison, not a fixed oracle." % (X, X >> 6, b)))
    return cs


def build_h1_pressure():
    """H1_PRESSURE: bits 15/31 under ~40 simultaneously-live registers
    (r16..r55, via 40 independent device_load_fixed instructions into
    carrier_dag.metal's 1536-byte MODE A budget), pushing the highest live
    register index to r55 -- near EXP-0112's own 64-alias boundary
    (device_load consumer register R aliases R mod 64 for R in [64,112]).
    Own pilot: all 4 (X,b) combinations match the established H1 pattern
    exactly (own=50.0 always, later=50.0/20.0 per b)."""
    cs = []
    n_pressure, start_reg = 40, 16
    pressure_loads = [H.device_load_fixed(R_IDX, i, elem_code=3, base_slot=1,
                                            extmode=2 * (start_reg + i),
                                            dst_lo=H.DST_TOKEN_KNOWNGOOD[0],
                                            dst_ext9=H.DST_TOKEN_KNOWNGOOD[1])
                       for i in range(n_pressure)]
    for X in (3, 67):
        for b in (0, 1):
            instrs = list(pressure_loads) + [seed_r3(), H.falu2i_raw(0, X, K2, opflags4=b),
                                               store(0, 0), reader(1, K2), store(4, 1)]
            prog = modeA_program(instrs, carrier_len=DAG_CARRIER_LEN)
            own = V + K2
            later = K2 if b else V + K2
            cs.append(case("h1_pressure_X%d_b%d" % (X, b), "H1_PRESSURE", "carrier_dag",
                            [(0, prog.hex())], {0: own, 4: later},
                            "40 live registers r16..r55 (device_load, EXP-0101 formula) before "
                            "the H1 probe; field=%d(bit15=%d) opflags bit0=%d" % (X, X >> 6, b)))
    return cs


# ===========================================================================
# H2 -- is bit 17 (and the literal-position siblings) one mechanism or
# several? Discriminating tests targeting ibitcount specifically (the
# family EXP-0119 found causally INERT to its own cache bit -- own+later
# corruption both unconditional).
# ===========================================================================
# ibitcount's db.json match table forces byte0(bits0-6)+fn_hi(bit7)+form
# bit1(bit9)+byte2 bits16,18-23 -- the ONLY fields NOT semantically
# committed (opcode/reg) AND not match-forced are: cache(byte2 bit17,
# already characterized), op_enable(byte4) bits OTHER than bit1 (bit1 is
# the established "must be set to compute" gate -- already shown inert for
# COMPUTATION at 0x02/0x03/0x06/0x07/0x0a by EXP-M4-14's own provenance
# note, but NEVER tested for RETENTION), srcdesc(byte6) bits OTHER than
# bit6 (bit6 "must be set for GPR read", same caveat), and tail(byte7,
# fully uncharacterized beyond the anchor's 0x04). This sweep targets
# exactly those free bits.
FREE_BITS = (
    ("op_enable", 0xFF & ~0x02, 0x02),   # anchor 0x02; bit1 held fixed (compute-enable)
    ("srcdesc",   0xFF & ~0x40, 0x5c),   # anchor 0x5c; bit6 held fixed (GPR-read-enable)
    ("tail",      0xFF,         0x04),   # anchor 0x04; fully free per db.json's own match table
)


def build_h2_bytesweep():
    """H2_BYTESWEEP: for each of ibitcount's three non-match-forced 'mod'
    bytes (op_enable, srcdesc, tail), flip each individually-free bit
    against the anchor and check BOTH own-result (must stay correct, per
    EXP-M4-14/EXP-0119) and later-read (EXP-0119 found this UNCONDITIONALLY
    corrupted regardless of `cache` -- this sweep asks whether ANY of these
    OTHER bits makes it conditional, which would relocate the real
    release-control bit rather than confirm it does not exist)."""
    cs = []
    for field, freemask, anchor in FREE_BITS:
        bit = 0
        while (1 << bit) < 256:
            mask = 1 << bit
            if freemask & mask:
                val = anchor ^ mask
                kwargs = {"cache_bit17": 1}
                kwargs[field] = val
                instrs = [seed_r3(), H.ibitcount_raw(2, 3, **kwargs), store(0, 2),
                          reader(1, K2), store(4, 1)]
                prog = modeA_program(instrs)
                cs.append(case("h2_bytesweep_%s_bit%d" % (field, bit), "H2_BYTESWEEP", "carrier",
                                [(0, prog.hex())],
                                {0: None, 4: None},   # EXPLORATORY: own-result popcount(30.0 bits)=6
                                                        # stored as raw int (denormal f32 ~8.4e-45);
                                                        # later-read predicted K2=20.0 UNLESS this bit
                                                        # is the real release control (then 50.0) --
                                                        # see analysis.py for the decode.
                                "%s=0x%02x (anchor 0x%02x ^ bit%d), cache=1(fresh); "
                                "word0=own(popcount(30.0 bits)=6, denormal f32), "
                                "word4=later-read" % (field, val, anchor, bit)))
            bit += 1
    return cs


def build_h2_interaction():
    """H2_INTERACTION: own pilot (PROGRESS.md) found srcdesc bit4 (anchor
    0x5c has bit4=1; flipping to 0x4c) turns ibitcount's later-read from
    UNCONDITIONALLY corrupted (EXP-0119's own finding, `cache`/bit17
    causally inert) into UNCONDITIONALLY retained -- own-result stays
    correct (popcount=6) either way, so this is NOT the same confounded
    "degrades the GPR read entirely" pattern the pilot also found at
    srcdesc bits 0/3 and tail bit2 (those break OWN-result too). This is a
    real, clean, bidirectional release-control bit for ibitcount, just at
    a DIFFERENT literal position than `cache`. This group asks the natural
    follow-up: with srcdesc bit4 CLEARED (0x4c, the "retains" setting),
    does `cache`/bit17 now regain the role it plays in falu2/unpack_convert
    -- or is it independently inert regardless?"""
    cs = []
    for cache in (1, 0):
        instrs = [seed_r3(), H.ibitcount_raw(2, 3, cache_bit17=cache, srcdesc=0x4c),
                  store(0, 2), reader(1, K2), store(4, 1)]
        prog = modeA_program(instrs)
        cs.append(case("h2_interaction_srcdesc4clr_cache%d" % cache, "H2_INTERACTION", "carrier",
                        [(0, prog.hex())], {0: H.bits_f32(6), 4: None},
                        "srcdesc=0x4c (bit4 cleared vs the 0x5c anchor -- the pilot's own "
                        "'retains' setting), cache=%d; word4 EXPLORATORY -- does cache regain "
                        "a role once srcdesc bit4 is cleared, or stay inert independently?"
                        % cache))
    return cs


def build_h2_laterwrite_distance():
    """H2_LATERWRITE (does a fresh rewrite restore ibitcount's UNCONDITIONAL
    later-read corruption, matching falu2's per-write-instance-suppression
    signature, EXP-0119 H4.2?) + H2_DISTANCE (does the corruption depend on
    the number of intervening instructions between producer and later
    reader, EXP-0089's CandB-style sweep, extended to ibitcount which
    EXP-0119 never distance-swept)."""
    cs = []
    K3 = H.imm_value(8.0)
    # LATERWRITE: corrupt (cache doesn't matter -- always releases), then either
    # go straight to the later reader, or rewrite r3 first.
    for tag, rewrite in (("norewrite", False), ("rewrite", True)):
        instrs = [seed_r3(), H.ibitcount_raw(2, 3, cache_bit17=1), store(0, 2)]
        if rewrite:
            instrs.append(H.falu2i_raw(3, R_UNW, K3, opflags4=0))
        instrs += [reader(1, K2), store(4, 1)]
        prog = modeA_program(instrs)
        expected_later = (K3 + K2) if rewrite else K2
        cs.append(case("h2_laterwrite_%s" % tag, "H2_LATERWRITE", "carrier",
                        [(0, prog.hex())], {4: expected_later},
                        "ibitcount always releases r3 (EXP-0119); does an ordinary rewrite "
                        "(r3=K3=8.0) before the later reader restore it? rewrite=%s" % rewrite))
    # DISTANCE: 0 (adjacent, store IS the only intervening instr -- already
    # ibitcount's own 'own-result' construction), 1 extra throwaway instr
    # ("near"), 4 extra throwaway instrs ("far") between the store and the
    # later reader.
    for tag, n_filler in (("adjacent", 0), ("near", 1), ("far", 4)):
        instrs = [seed_r3(), H.ibitcount_raw(2, 3, cache_bit17=1), store(0, 2)]
        instrs += [H.mov_imm(12, i & 0xFF) for i in range(n_filler)]   # throwaway, r12 unused elsewhere
        instrs += [reader(1, K2), store(4, 1)]
        prog = modeA_program(instrs)
        cs.append(case("h2_distance_%s" % tag, "H2_DISTANCE", "carrier",
                        [(0, prog.hex())], {4: K2},
                        "ibitcount's later-read corruption at distance=%d intervening "
                        "throwaway instructions (mov_imm r12, never read) between the store "
                        "and the later reader" % n_filler))
    return cs


# ===========================================================================
# H3 -- A18-vs-M4 ibitcount discrepancy: operand-provenance x dispatch-shape
# ===========================================================================
def build_h3_modeb():
    """H3_MODEB: EXP-M4-14's OWN literal anchor bytes
    (27 05 56/54 00 02 00 5c 04), spliced into a FRESH M4 compile of the
    SAME own-MSL corpus file (kernels/iunary_popcount.metal, verbatim from
    EXP-M4-14's corpus/halfint/iunary.metal), at BOTH grid=1 (matching
    EXP-0119's own single-lane construction) and grid=4 (matching
    EXP-M4-14's own real 4-element dispatch) -- the ONE axis EXP-0119 could
    not vary (hands-off A18) is dispatch shape; this experiment CAN vary it
    entirely on M4."""
    cs = []
    for grid in (1, 4):
        for cache_hex, tag in (("2705560002005c04", "fresh"), ("2705540002005c04", "stale")):
            oracle = {}
            full_popcounts = [4, 1, 16, 2]
            for lane in range(grid):
                # popcount is an INTEGER count stored raw (device_store word,
                # no float conversion) -- compare against the exact denormal
                # f32 bit-reinterpretation, matching EXP-0119's own H.bits_f32
                # convention (its own casematrix.py comment: "denormal, ~8.4e-45").
                oracle[str(lane)] = H.bits_f32(full_popcounts[lane])
            cs.append(case("h3_modeb_grid%d_%s" % (grid, tag), "H3_MODEB", "iunary_popcount",
                            [(0x12, cache_hex)], oracle,
                            "EXP-M4-14's own literal anchor bytes (%s), grid=%d/tg=%d, "
                            "real device_load-sourced input a[i]=[15,16,65535,0x40000001] "
                            "(EXP-M4-14's own values); oracle is per-lane popcount for the "
                            "lanes actually dispatched (grid=1 dispatches only lane 0 -- "
                            "lanes 1-3 are simply never executed, not corrupted, at grid=1)"
                            % (cache_hex, grid, grid), grid=grid, tg=grid))
    return cs


def build_h3_modea():
    """H3_MODEA: MODE A hand-built ibitcount, crossing operand-provenance
    (ALU-immediate-seeded r3, matching EXP-0119's own construction, vs
    device_load-sourced r7, EXP-0101 bridge formula) x dispatch shape
    (grid=1 vs grid=4, all lanes executing the IDENTICAL tid-independent
    hand-built program) x cache bit (0/1). Own-result is the own-pilot's
    decisive H3 discriminator (own pilot, PROGRESS.md): ALU-seeded is
    ALWAYS correct regardless of cache (matches EXP-0119); device_load-
    sourced BREAKS at cache=0 (matches EXP-M4-14) -- at grid=1, i.e. WITHOUT
    varying dispatch shape at all, ruling dispatch-shape out as the
    deciding axis for THIS family's own-result signature."""
    cs = []
    LOADVAL_BITS = 0x40000001   # same value/expected popcount(2) as EXP-M4-14's own 4th input
    expected_popcount_alu = 6   # popcount(30.0's f32 bits), EXP-0119's own established oracle
    expected_popcount_load = 2  # popcount(0x40000001)
    for source in ("alu", "load"):
        for grid in (1, 4):
            for cache in (1, 0):
                if source == "alu":
                    instrs = [seed_r3(), H.ibitcount_raw(2, 3, cache_bit17=cache), store(0, 2)]
                    expected_own = expected_popcount_alu
                    buf1 = ("f32", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
                else:
                    instrs = [H.device_load_fixed(R_IDX, 0, elem_code=3, base_slot=1,
                                                    extmode=2 * 7, dst_lo=H.DST_TOKEN_KNOWNGOOD[0],
                                                    dst_ext9=H.DST_TOKEN_KNOWNGOOD[1]),
                              H.ibitcount_raw(2, 7, cache_bit17=cache), store(0, 2)]
                    expected_own = expected_popcount_load if cache else 0
                    raw = struct.pack("<I", LOADVAL_BITS)
                    buf1 = ("raw", raw + b"\x00" * 28)
                prog = modeA_program(instrs)
                expected_own = H.bits_f32(expected_own)
                # NOTE: every lane runs the IDENTICAL tid-independent program (no per-lane
                # divergence in the hand-built instruction stream) and every lane's
                # device_store targets the SAME fixed word0 (index_reg=R_IDX, held at 0 by
                # the leading mov_imm -- never made tid-dependent here). At grid>1 this is a
                # deliberate concurrent same-address race, but because every racing lane
                # computes the IDENTICAL value (no per-lane divergent input), the race is
                # over WHICH write physically lands last, not WHAT value lands -- the
                # stored word is still predicted deterministic. This case answers "does
                # own-result correctness depend on operand-provenance x dispatch-shape",
                # not per-lane output separation (H3_MODEB covers real per-thread
                # addressing/divergent data).
                cs.append(case("h3_modea_%s_grid%d_cache%d" % (source, grid, cache), "H3_MODEA",
                                "carrier",
                                [(0, prog.hex())], {0: expected_own},
                                "operand-source=%s, grid=%d/tg=%d (all lanes execute the "
                                "IDENTICAL tid-independent hand-built program; word0 is "
                                "whichever lane's write physically lands last -- this "
                                "case answers 'does own-result correctness depend on "
                                "operand provenance x dispatch shape', not per-lane output "
                                "separation), cache=%d" % (source, grid, grid, cache),
                                grid=grid, tg=grid, extra_bufs={1: buf1}))
    return cs


def build_cases():
    groups = (build_h1_cf() + build_h1_load() + build_h1_halfwidth() + build_h1_pressure() +
              build_h2_bytesweep() + build_h2_interaction() + build_h2_laterwrite_distance() +
              build_h3_modeb() + build_h3_modea())
    for i, c in enumerate(groups):
        c["i"] = i
    return groups
