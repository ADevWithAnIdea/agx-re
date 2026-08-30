#!/usr/bin/env python3
"""EXP-0168 case matrix (the GENERATOR is frozen at pre-registration; its
sha256 and the sha256 of the case list it produces from the frozen anchor report
are both recorded in CAPTURE_CONTRACT.json before the first gated run).

WHAT THIS EXPERIMENT IS REPAIRING, AND THE THREE RULES THAT FOLLOW
-----------------------------------------------------------------
EXP-0164 withdrew 122 fields to `untested`. Every one of this experiment's
targets was withheld for one of three reasons, and each reason dictates a
different fix:

  INERT-SINGLE   the field moved nothing, on ONE carrier. Almost always the
                 carrier could not express what the field controls. Fix: a
                 SECOND carrier that differs in that dimension, plus a liveness
                 ladder proving the carrier could have seen a difference.
  UNSTABLE       the field moved, but not reproducibly across the two runs the
                 audit compared. Fix: more measured runs -- and, for two of
                 them, a re-scoring, because the audit compared a run that never
                 dispatched the value (see analysis/rescore_0144.py).
  UNVERIFIABLE   no per-value record under raw/ can be attributed to the field.
                 Fix: re-record in this schema. An auditability gap, not a
                 refutation.

RULE 1 -- THE OBSERVABLE MUST NOT CO-VARY WITH THE FIELD.
EXP-0140's `uniform_mov.dst` sweep built its read-back as
`device_store(..., data_reg=D)` where D is the very dst being swept
(EXP-0140/harness/cases.py:92-100). Field and observable moved together, so a
CORRECT hardware result is a constant observed vector by construction and
"0 observations moved" was the passing outcome. Here the store list is IDENTICAL
in every case -- all 16 GPRs, always -- and the verdict is a function of WHICH
SLOT changed.

RULE 2 -- TWO CARRIERS IDENTICAL IN THE CONTROLLED DIMENSION ARE ONE CARRIER.
`iter_at.loc` read inert on every EXP-0155 arm and moves 128/256 at
rasterSampleCount=4 (EXP-0163): both its "independent" carriers were samples=1.
Every arm below names its `dim` and the arms that pair must differ in it.

RULE 3 -- PROVE DETECTION POWER FIRST.
Every arm carries LADDER cases that mutate a KNOWN-LIVE control of the same
instruction, with the citation that makes it known-live. An arm whose ladder
does not produce >=2 distinct observed digests is DISCARDED and its inertness is
not evidence.

Plus two mechanical requirements the audit named:
  * BYTE-MATES. For a sub-byte field, the complementary bits of the same byte
    are swept separately with the field pinned at its anchor. If the complement
    moves the same observable, attribution is ambiguous and RESULTS.md says so.
  * FALSIFIERS. Every arm has at least one case pre-registered to FAIL.

CLEAN-ROOM: block bytes come from the compiled form of our own MSL; field
geometry comes from our own `tools/agx-isa/db.json` snapshot; scaffolding is
assembled by our own `isadb.assemble`.
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


# ---------------------------------------------------------------------------
# bit surgery
# ---------------------------------------------------------------------------
def set_field(blk, tgt, start, width, value):
    """`blk` with the db field [start, start+width) of the instruction at byte
    offset `tgt` set to `value`. Bit numbering is LSB-first across the
    instruction's bytes, exactly as db.json defines it. Only the field's own
    bits are touched -- that is what makes the byte-mate control meaningful."""
    b = bytearray(blk)
    for i in range(width):
        bit = start + i
        byi = tgt + (bit >> 3)
        if byi >= len(b):
            raise IndexError("field bit %d past end of block" % bit)
        mask = 1 << (bit & 7)
        if (value >> i) & 1:
            b[byi] |= mask
        else:
            b[byi] &= ~mask & 0xFF
    return bytes(b)


def get_field(blk, tgt, start, width):
    v = 0
    for i in range(width):
        bit = start + i
        byi = tgt + (bit >> 3)
        if (blk[byi] >> (bit & 7)) & 1:
            v |= 1 << i
    return v


def set_byte(blk, tgt, byte_index, value):
    b = bytearray(blk)
    b[tgt + byte_index] = value & 0xFF
    return bytes(b)


def complement_bits(blk, tgt, start, width, value):
    """Set every OTHER bit of the byte(s) the field lives in, leaving the field
    itself alone. The byte-mate control."""
    b = bytearray(blk)
    lo_byte = start >> 3
    hi_byte = (start + width - 1) >> 3
    fieldbits = set(range(start, start + width))
    k = 0
    for byi in range(lo_byte, hi_byte + 1):
        for bit in range(byi * 8, byi * 8 + 8):
            if bit in fieldbits:
                continue
            mask = 1 << (bit & 7)
            if (value >> k) & 1:
                b[tgt + byi] |= mask
            else:
                b[tgt + byi] &= ~mask & 0xFF
            k += 1
    return bytes(b)


def field_geom(mnemonic, field):
    d = INS[mnemonic]
    for f in d["fields"]:
        if f["name"] == field:
            return f["start"], f["width"]
    raise KeyError("%s.%s not in db.json" % (mnemonic, field))


def coverage(width):
    """FIELD-SWEEP-PROTOCOL 3.3: dense for w<=8; boundaries + all powers of two
    + >=16 asymmetric interior samples above that."""
    if width <= 8:
        return list(range(1 << width))
    mx = (1 << width) - 1
    vals = {0, 1, 2, mx - 1, mx}
    for i in range(width):
        vals.add(1 << i)
        vals.add(mx ^ (1 << i))
    for k in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59):
        vals.add((k * 2654435761) & mx)
    return sorted(vals)


# ---------------------------------------------------------------------------
# THE ARM TABLE
# ---------------------------------------------------------------------------
# Each arm:
#   id      arm identifier, appears in every record
#   style   "S" synth+lifted | "P" in-place
#   probe   kernel in kernels/probes.metal supplying the anchor. May be a LIST
#           of candidates, tried in order: which kernel the Apple compiler
#           chooses to emit a given instruction from is not under our control,
#           so an arm that names one kernel can silently lose itself. An arm
#           that finds NO candidate is recorded `arm_not_run` with the reason,
#           never silently dropped.
#   mn      mnemonic under test
#   occ     which occurrence of `mn` inside that kernel
#   kind    seed table for STYLE-S ("int" / "float")
#   dim     THE DIMENSION THIS CARRIER VARIES -- rule 2 is checked against this
#   why     one line: why this carrier can express the field
#   fields  [(field name, "field"|"byte", start-or-byte-index, width)]
#   ladder  (field name, [values], citation) -- the known-live control
#   cross   [(name, "field"|"byte", a, b, [values])] -- a SECOND dimension the
#           swept field is crossed with. This is what EXP-0140 never did: it
#           swept `dst` at ONE byte+2 form and fanned the verdict out to five
#           descriptors that behave differently.
#   before  extra instructions before the block (STYLE-S only), by name
#   after   extra instructions after the block (STYLE-S only), by name
#   probe_reg  register the high-register read-back probe should copy, or None
#   falsifier_byte0  override for the pre-registered-to-fail case. The DEFAULT
#           falsifier forces byte0 = 0x00, which is not this instruction. That
#           is confounded whenever byte0 carries BOTH the match-pinned opcode
#           bits AND a field under test: for `uniform_mov`, byte0 = opcode
#           nibble (bits 0..3, pinned to 0xb) | dst (bits 4..7), so byte0 = 0x00
#           ALSO sets dst = 0 -- and the anchor's own dst is 0. The prefreeze
#           smoke measured that falsifier producing a digest IDENTICAL to the
#           baseline, and raw/prefreeze/diag_byte0.json shows why: low nibble
#           0x0 is a DIFFERENT but structurally parallel instruction that writes
#           the SAME destination register from the SAME dst bits. Low nibbles
#           0x5 and 0xd are the only ones inert-with-the-program-completing at
#           BOTH form 0x00 and form 0x01, so 0x55 (lo=0x5, dst=5, seed 65 != 0)
#           is a falsifier that provably fires.
#           GENERAL RULE, for FIELD-SWEEP-PROTOCOL: a falsifier that clobbers a
#           byte carrying both the opcode and a field under test is confounded
#           with that field's own values and must be chosen away from them.

ARMS = [
    # ================================================== the dst field name ===
    # The compact-move family is ONE 4-byte instruction (EXP-0087/EXP-0140):
    # byte0-hi = dst, byte+1 = src, byte+2 = form selector, byte+3 = op_desc.
    # EXP-0140 swept dst at ONE form (byte+2=0x01 / byte+3=0x08) and fanned the
    # single verdict out to all six descriptor names (verdicts.py:327). The
    # missing measurement is the dst x form CROSS-PRODUCT, which is this arm.
    dict(id="REGMOVE/dump", style="S",
         falsifier_byte0=0x55,
         probe=["k_uni_each", "k_uni_sum", "k_bitcast", "k_packnorm2"],
         mn="uniform_mov",
         occ=0, kind="int",
         dim="which register slot changed (16-GPR dump; store list FIXED)",
         why="EXP-0140's read-back store used data_reg=D, so field and "
             "observable co-varied and a correct result was a constant vector. "
             "Here the store list is identical in every case.",
         fields=[("dst", "field", None, None)],
         # THE CROSS-PRODUCT THAT WAS MISSING. byte+2 selects the form; the five
         # db.json descriptors are five values of it, and EXP-0140's own probe
         # showed they behave differently (c0/c2var silent_zero, c9/cb
         # wrong_value, c1 ok). All three of those still WRITE the destination,
         # so a 16-register dump makes `dst` live for every one of them.
         cross=[("form_b2", "byte", 2, 8,
                 [0x00, 0x01, 0x02, 0x09, 0x0B,      # the five descriptors
                  0x05, 0x11, 0x15, 0x21, 0x25, 0x31, 0x35,  # EXP-0140 movers
                  0x0F, 0x26])],                     # EXP-0113 nondeterministic
         ladder=("usrc", "byte", 1, 8,
                 "EXP-0101/EXP-0113 HW: the readback depends only on src_reg"),
         probe_reg=None),
    dict(id="REGMOVE/consumer", style="S",
         falsifier_byte0=0x55,
         probe=["k_uni_each", "k_uni_sum", "k_bitcast", "k_packnorm2"],
         mn="uniform_mov",
         occ=0, kind="int",
         dim="dst observed through a register-file DEPENDENCE, not a bulk dump",
         why="a second, structurally different observation path: a fixed "
             "consumer reads rC and only the coincidence dst==rC changes it. "
             "Its failure modes (forwarding, scoreboard) differ from a dump's.",
         fields=[("dst", "field", None, None)],
         ladder=("usrc", "byte", 1, 8, "EXP-0101/EXP-0113 HW"),
         probe_reg=None),
    dict(id="REGMOVE/consumer9", style="S",
         falsifier_byte0=0x55,
         probe=["k_uni_each", "k_uni_sum", "k_bitcast", "k_packnorm2"],
         mn="uniform_mov", occ=0, kind="int",
         dim="the same dependence path with the CONSUMER at a different index",
         why="if dst really selects the destination, the coincidence index at "
             "which the consumer's value changes must MOVE with the consumer, "
             "from 3 to 9. A single consumer index cannot show that.",
         fields=[("dst", "field", None, None)],
         ladder=("usrc", "byte", 1, 8, "EXP-0101/EXP-0113 HW"),
         probe_reg=None),
    dict(id="REGMOVE/form", style="S",
         falsifier_byte0=0x55,
         probe=["k_uni_each", "k_uni_sum", "k_bitcast", "k_packnorm2"],
         mn="uniform_mov",
         occ=0, kind="int",
         dim="the byte+2 FORM selector, swept at TWO dst values",
         why="EXP-0140 swept byte+2 at dst=3 only. Sweeping it at two dst "
             "values is what separates 'form' from 'form x dst'.",
         fields=[("form_b2", "byte", 2, 8), ("opdesc_b3", "byte", 3, 8)],
         ladder=("usrc", "byte", 1, 8, "EXP-0101/EXP-0113 HW"),
         probe_reg=None),

    dict(id="FALU2/dump", style="S",
         probe=["k_fadd", "k_copysign_rp", "k_sum_reuse", "k_sum"], mn="falu2",
         occ=0,
         kind="float",
         dim="which register slot receives a fully host-computable float sum",
         why="the value written is host-computable from the seed table, so the "
             "oracle does not depend on any GPU measurement at all.",
         fields=[("dst", "field", None, None)],
         ladder=("srcA_reg", "field", None, None,
                 "EXP-0020/EXP-0101 HW: srcA_reg selects the first operand"),
         probe_reg=None),
    dict(id="FALU2I/dump", style="S",
         probe=["k_faddi", "k_copysign_rp", "k_sum"], mn="falu2i", occ=0,
         kind="float",
         dim="same slot question with an IMMEDIATE srcB (no second GPR read)",
         why="differs from FALU2 in the source-operand class, so a dst verdict "
             "that held only when both sources were GPRs would separate here.",
         fields=[("dst", "field", None, None)],
         ladder=("srcA_reg", "field", None, None, "EXP-0020/EXP-0101 HW"),
         probe_reg=None),

    dict(id="GETSR/dump", style="S",
         probe=["k_getsr", "k_fadd", "k_sum"], mn="get_sr", occ=0,
         kind="int",
         dim="which slot receives a special register whose value is host-known",
         why="dispatched at tg=8 with sr_sel = threads_per_threadgroup, so the "
             "expected value is 8 -- a number that appears in no seed.",
         fields=[("dst", "field", None, None), ("dst_hi", "field", None, None),
                 ("form", "field", None, None)],
         ladder=("sr_sel", "field", None, None,
                 "EXP-0031 HW: SR# = byte1, splice-proven on dispatched kernels"),
         probe_reg="dst_hi"),

    dict(id="CVTF2I/standalone", style="S", probe="k_f2i", mn="cvt_f2i", occ=0,
         kind="float",
         dim="convert result NOT consumed by a following ALU op",
         why="every EXP-0144 carrier for this op is standalone; this reproduces "
             "that configuration on G17P as the control half of the pair.",
         fields=[("dst", "byte", 3, 8), ("b9", "byte", 9, 8)],
         ladder=("src", "byte", 5, 8,
                 "EXP-M4-13 R9 own-MSL byte-diff: byte+5 = src reg (src<<2)"),
         probe_reg=None),
    dict(id="CVTF2I/consumed", style="S", probe="k_f2i_consumed", mn="cvt_f2i",
         occ=0, kind="float",
         dim="convert result IS consumed by a following ALU op",
         why="db.json says byte+2 of this family selects "
             "result-consumed-by-following-ALU vs standalone, and EXP-0144 "
             "never built a consuming carrier for cvt_f2i or cvt_f2h. This is "
             "the missing half of the dimension.",
         fields=[("dst", "byte", 3, 8), ("b9", "byte", 9, 8)],
         ladder=("src", "byte", 5, 8, "EXP-M4-13 R9"),
         probe_reg=None),

    dict(id="UNPACK/unorm", style="S", probe="k_unpack_unorm2",
         mn="unpack_convert", occ=0, kind="int",
         dim="unorm2x16 source format",
         why="format is the dimension the byte+3..+7 descriptor region encodes.",
         fields=[("dst", "byte", 3, 8)],
         ladder=("src", "byte", 5, 8, "EXP-0144 HW: byte+5 is a source register"),
         probe_reg=None),
    dict(id="UNPACK/snorm", style="S", probe="k_unpack_snorm2",
         mn="unpack_convert", occ=0, kind="int",
         dim="snorm2x16 source format (differs from UNPACK/unorm in FORMAT)",
         why="a second carrier that differs in the format dimension, not merely "
             "in the occurrence index.",
         fields=[("dst", "byte", 3, 8)],
         ladder=("src", "byte", 5, 8, "EXP-0144 HW"),
         probe_reg=None),
    dict(id="UNPACK/consumed", style="S", probe="k_unpack_consumed",
         mn="unpack_convert", occ=0, kind="int",
         dim="unpack result consumed by a following ALU op",
         why="third carrier, differing in consumption rather than format.",
         fields=[("dst", "byte", 3, 8)],
         ladder=("src", "byte", 5, 8, "EXP-0144 HW"),
         probe_reg=None),

    # ============================================ the 12 one-field-away ======
    dict(id="FALU_ACC/lastuse", style="S", probe=["k_sum", "k_sum_reuse"],
         mn="falu_acc", occ=0,
         kind="float",
         dim="the accumulate's sources are NEVER read again",
         why="db.json calls byte+2 bit5 a source-cache/LAST-USE hint. RT-1a-FIX "
             "tested it by checking the reduction RESULT, which a cache hint "
             "cannot change. The dimension is whether the SOURCE survives, so "
             "the observable must be the source register, not the sum.",
         fields=[("cache", "field", None, None)],
         cross=[("srcB", "field", None, None,
                 [0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 26, 0x80, 0xC0])],
         ladder=("srcB", "field", None, None,
                 "EXP-0025 HW: byte+3 is the srcB register descriptor"),
         probe_reg=None),
    dict(id="FALU_ACC/reuse", style="S", probe=["k_sum_reuse", "k_sum"],
         mn="falu_acc", occ=0, kind="float",
         dim="every accumulate source IS read a second time afterwards",
         why="the paired carrier: it differs from FALU_ACC/lastuse in exactly "
             "the dimension a last-use hint would control.",
         fields=[("cache", "field", None, None)],
         cross=[("srcB", "field", None, None,
                 [0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 26, 0x80, 0xC0])],
         ladder=("srcB", "field", None, None, "EXP-0025 HW"),
         probe_reg=None),
    dict(id="FALU_ACC/reread", style="S", probe=["k_sum", "k_sum_reuse"],
         mn="falu_acc", occ=0,
         kind="float",
         dim="an AUTHORED second consumer re-reads srcB after the accumulate",
         why="third carrier: the re-read is a synthesized falu2i we control, so "
             "the re-read is guaranteed to happen and to be observable, rather "
             "than depending on what the compiler chose to schedule.",
         fields=[("cache", "field", None, None)],
         cross=[("srcB", "field", None, None,
                 [0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 26, 0x80, 0xC0])],
         ladder=("srcB", "field", None, None, "EXP-0025 HW"),
         after="reread_srcB", probe_reg=None),

    dict(id="SHIFTMOVE/gpr", style="S", probe=["k_rot_var", "k_shl_var"],
         mn="shift_amt_move",
         occ=0, kind="int",
         dim="the staged shift amount comes from a per-thread GPR",
         why="src_flag selects WHICH FILE the amount comes from (EXP-0140: bit7 "
             "selects immediate-vs-uniform-file). A carrier that never varies "
             "the source index cannot separate the two files.",
         fields=[("src_flag", "field", None, None)],
         # THE JOINT SWEEP. If flag=0 reads the GPR file, the staged amount
         # tracks our distinct per-register seeds; if flag=1 reads the
         # uniform/immediate file it does not. TWO PROFILES over the index is
         # the movement signal, and a carrier holding src_reg fixed is blind to
         # it however many times it is run.
         cross=[("src_reg", "field", None, None,
                 [0, 1, 2, 3, 5, 7, 8, 11, 13, 15, 16, 31, 63])],
         ladder=("src_reg", "field", None, None,
                 "EXP-0101/EXP-0113 HW: readback depends only on src_reg"),
         probe_reg=None),
    dict(id="SHIFTMOVE/uni", style="S", probe=["k_rot_uni"],
         mn="shift_amt_move",
         occ=0, kind="int",
         dim="the staged shift amount is THREAD-INVARIANT (uniform/immediate)",
         why="the paired carrier, differing in exactly the file the flag "
             "selects.",
         fields=[("src_flag", "field", None, None)],
         cross=[("src_reg", "field", None, None,
                 [0, 1, 2, 3, 5, 7, 8, 11, 13, 15, 16, 31, 63])],
         ladder=("src_reg", "field", None, None, "EXP-0101/EXP-0113 HW"),
         probe_reg=None),

    dict(id="COPYSIGN/lowpress", style="S", probe="k_copysign", mn="copysign",
         occ=0, kind="float",
         dim="two live float registers (EXP-0138's configuration, reproduced)",
         why="control half. EXP-0138 swept byte+3 over 256 values here and "
             "nothing moved -- but its carrier held only TWO live floats, so a "
             "register-selector byte had a two-outcome observable space.",
         fields=[("operands", "field", None, None)],
         ladder=("b1", "byte", 1, 8,
                 "EXP-0138 HW: byte+1 moved 240/256 silent-zero, 8 -> -5.0, "
                 "8 -> +5.0 -- a live operand field db.json pins as a match "
                 "constant"),
         probe_reg=None),
    dict(id="COPYSIGN/highpress", style="S", probe="k_copysign_rp",
         mn="copysign", occ=0, kind="float",
         dim="16 live, distinctly-seeded float registers",
         why="the paired carrier: it differs in the SIZE OF THE OBSERVABLE "
             "OPERAND SPACE, which is the dimension a register-descriptor byte "
             "controls. With 16 distinct seeds and a 16-register dump, a "
             "register selector has 16 resolvable outcomes instead of 2.",
         fields=[("operands", "field", None, None)],
         ladder=("b1", "byte", 1, 8, "EXP-0138 HW"),
         probe_reg=None),

    dict(id="CVTF2H/standalone", style="S", probe="k_f2h_standalone",
         mn="cvt_f2h", occ=0, kind="float",
         dim="convert result NOT consumed by a following ALU op",
         why="reproduces EXP-0144's configuration as the control half.",
         fields=[("op", "byte", 2, 8)],
         ladder=("src", "byte", 3, 8,
                 "EXP-0144 HW byte_scans: 8 values of byte+2 redirect the "
                 "SOURCE, so the source byte is demonstrably live here"),
         probe_reg=None),
    dict(id="CVTF2H/consumed", style="S", probe="k_f2h_consumed", mn="cvt_f2h",
         occ=0, kind="float",
         dim="convert result IS consumed by a following half-ALU op",
         why="the missing half. EXP-0144 built no consuming carrier for this "
             "op, and its byte+2 finding (62 of 256 values turn the fp16 "
             "convert into a BFLOAT16 convert) has never been tested against a "
             "consumer.",
         fields=[("op", "byte", 2, 8)],
         ladder=("src", "byte", 3, 8, "EXP-0144 HW"),
         probe_reg=None),

    dict(id="PACK/unorm2", style="S", probe="k_pack_unorm2", mn="pack_convert",
         occ=0, kind="float", dim="unorm2x16 destination format",
         why="b7 sits inside the format-conversion descriptor, so FORMAT is the "
             "dimension it most plausibly interacts with.",
         fields=[("b7", "byte", 7, 8)],
         ladder=("src_lane0", "byte", 5, 8,
                 "EXP-0144 HW: byte+5 is a real source register (reg<<2)"),
         probe_reg=None),
    dict(id="PACK/snorm2", style="S", probe="k_pack_snorm2", mn="pack_convert",
         occ=0, kind="float", dim="snorm2x16 destination format",
         why="second carrier differing in FORMAT, not in occurrence index. "
             "EXP-0144's 'two carriers' for this field were arms F and W over "
             "the same compiled c_pack program.",
         fields=[("b7", "byte", 7, 8)],
         ladder=("src_lane0", "byte", 5, 8, "EXP-0144 HW"),
         probe_reg=None),
    dict(id="PACK/unorm4", style="S", probe="k_pack_unorm4", mn="pack_convert",
         occ=0, kind="float", dim="unorm 8-bit-lane destination format",
         why="third format, and the one whose lane count differs.",
         fields=[("b7", "byte", 7, 8)],
         ladder=("src_lane0", "byte", 5, 8, "EXP-0144 HW"),
         probe_reg=None),

    # mov_imm and stop are SYNTHESIZED outright, not lifted: they are
    # scaffolding this experiment already builds from db.json's own field rules,
    # which is the strongest evidence level in CODEX.md section 3 (an
    # independently generated encoding executed on hardware).
    dict(id="MOVIMM/padded", style="S", probe=None, mn="mov_imm", occ=0,
         kind="int",
         dim="the following instruction is INERT PADDING",
         why="if imm_top selects a longer instruction, a padded form loses only "
             "padding and the destination register keeps its seed.",
         fields=[("imm_top", "field", None, None), ("byte1", "byte", 1, 8)],
         cross=[("dst", "field", None, None, [2, 7, 13])],
         ladder=("imm7", "field", None, None,
                 "EXP-0031 HW: out = the byte+1 literal, splice-proven"),
         probe_reg=None),
    dict(id="MOVIMM/unpadded", style="S", probe=None, mn="mov_imm", occ=0,
         kind="int",
         dim="the following instruction is a LOAD-BEARING witness write",
         why="the paired carrier, differing in exactly the dimension "
             "'is the next instruction consumed'. EXP-0140 reached this "
             "conclusion from TWO records at one immediate and one dst.",
         fields=[("imm_top", "field", None, None), ("byte1", "byte", 1, 8)],
         cross=[("dst", "field", None, None, [2, 7, 13])],
         ladder=("imm7", "field", None, None, "EXP-0031 HW"),
         probe_reg=None),

    dict(id="STOP/terminal", style="S", probe=None, mn="stop", occ=0,
         kind="int", dim="stop at the END of the program",
         why="control half: everything before it must have executed, so the "
             "full register dump plus both sentinels are the observable.",
         fields=[("reserved", "field", None, None), ("b1", "byte", 1, 8),
                 ("b2", "byte", 2, 8), ("b3", "byte", 3, 8)],
         ladder=None,
         probe_reg=None),
    dict(id="STOP/midprogram", style="S", probe=None, mn="stop", occ=0,
         kind="int", dim="stop BEFORE the register dump",
         why="the only carrier in which the field can express what a program-end "
             "token controls. If it terminates, the dump never runs and the "
             "window stays 0xDEADBEEF; if some body value made it not "
             "terminate, the dump appears. A terminal-stop carrier is blind to "
             "that by construction.",
         fields=[("reserved", "field", None, None), ("b1", "byte", 1, 8),
                 ("b2", "byte", 2, 8), ("b3", "byte", 3, 8)],
         ladder=None,
         probe_reg=None),

    # ======================================================= STYLE-P arms ====
    dict(id="IFPUSH/flat", style="P", probe="k_if_flat", mn="if_push", occ=0,
         kind=None, dim="ONE non-nested scope (the blind negative control)",
         why="with a single live scope there is no second mask bank for a wrong "
             "bank to collide with. Kept explicitly as the control, because "
             "EXP-0140's carrier was this shape.",
         fields=[("scope", "field", None, None)],
         ladder=("scope_kind", "field", None, None,
                 "EXP-0140 HW: scope_kind moved 178 cases to wrong_value plus "
                 "1 hang, 6 distinct observed vectors, on the same carrier"),
         probe_reg=None),
    dict(id="IFPUSH/nest3.outer", style="P", probe="k_if_nest3", mn="if_push",
         occ=0, kind=None, dim="THREE nesting levels; the OUTER push",
         why="db.json says scope ping-pongs 0x54/0x56 with nesting parity. "
             "EXP-0140's carrier had both live pushes at 0x54, so the model was "
             "never instantiated. Three levels instantiate it.",
         fields=[("scope", "field", None, None)],
         ladder=("scope_kind", "field", None, None, "EXP-0140 HW"),
         probe_reg=None),
    dict(id="IFPUSH/nest3.inner", style="P", probe="k_if_nest3", mn="if_push",
         occ=2, kind=None, dim="THREE nesting levels; the INNERMOST push",
         why="forcing the inner push to the outer's bank is the direct test of "
             "the bank model, and it is only possible when an outer mask exists "
             "to destroy.",
         fields=[("scope", "field", None, None)],
         ladder=("scope_kind", "field", None, None, "EXP-0140 HW"),
         probe_reg=None),
    dict(id="IFPUSH/loop", style="P", probe="k_if_loop", mn="if_push", occ=0,
         kind=None, dim="a scope_kind 0x1a LOOP scope nested inside a 0x01 guard",
         why="the two scope KINDS nested, which neither the flat nor the pure "
             "nest carrier produces.",
         fields=[("scope", "field", None, None)],
         ladder=("scope_kind", "field", None, None, "EXP-0140 HW"),
         probe_reg=None),

    dict(id="ATOMIC/lowreg", style="P", probe="k_atomic_lo", mn="atomic_mem",
         occ=0, kind=None, dim="the atomic operand is in a LOW register",
         why="control half: EXP-0141 tested exactly one operand register "
             "(index 3) and its own range note says 0x01/0x41/0x81/0xC1 all "
             "select index 3.",
         fields=[("addr_desc_hi", "field", None, None)],
         # the register-extension hypothesis is only testable ACROSS register
         # numbers, and EXP-0141 tested exactly one (index 3)
         cross=[("oper_reg_hi", "field", None, None,
                 [0, 1, 3, 7, 15, 31, 32, 47, 63])],
         ladder=("oper_reg_hi", "field", None, None,
                 "EXP-0141: the operand register field selects the value added"),
         probe_reg=None),
    dict(id="ATOMIC/highreg", style="P", probe="k_atomic_hi", mn="atomic_mem",
         occ=0, kind=None, dim="the atomic operand is in a HIGH register",
         why="addr_desc_hi sits immediately above the 7-bit operand-register "
             "field, so the register NUMBER is the dimension it would extend -- "
             "and that is untestable at a low index. 24 simultaneously live "
             "named scalars force a high allocation.",
         fields=[("addr_desc_hi", "field", None, None)],
         cross=[("oper_reg_hi", "field", None, None,
                 [0, 1, 3, 7, 15, 31, 32, 47, 63])],
         ladder=("oper_reg_hi", "field", None, None, "EXP-0141"),
         probe_reg=None),
    dict(id="ATOMIC/minop", style="P", probe="k_atomic_min", mn="atomic_mem",
         occ=0, kind=None, dim="a different atomic OPERATION (min, not add)",
         why="third carrier, differing in the op selector rather than the "
             "register, so an addr_desc_hi effect that is op-specific separates.",
         fields=[("addr_desc_hi", "field", None, None)],
         cross=[("oper_reg_hi", "field", None, None,
                 [0, 1, 3, 7, 15, 31, 32, 47, 63])],
         ladder=("oper_reg_hi", "field", None, None, "EXP-0141"),
         probe_reg=None),
]

# Arms deliberately NOT opened, with the reason. Reporting what was not reached
# is part of the deliverable.
NOT_RUN = {
    "matrix_mac.dst":
        "needs a simdgroup-matrix carrier over a full 32-lane simdgroup with "
        "fragment-register readback. It is one of TWELVE withheld fields on "
        "matrix_mac, so repairing dst alone cannot recover the instruction, and "
        "the arm is not worth the device time against this experiment's other "
        "targets. Reported as NOT ATTEMPTED, not as inert.",
    "iter_at.grp":
        "handled in the RENDER arm, and constrained by a db.json defect: the "
        "descriptor declares `grp` as 8 bits at start=0 while its own match "
        "constant [0,7,47] pins bits 0..6, so only bit 7 is free and every "
        "other value is a DIFFERENT instruction. It is also a hang minefield "
        "(EXP-0155 and EXP-0163 both tripped the 2-hang stop rule; no run has "
        "ever swept past ~25 of 256 values).",
    "frag_color_pack.dst": "RENDER arm.",
    "pixel_order.kind": "RENDER arm.",
    "vtx_out_pos.dst / vtx_out_pos.slot": "RENDER arm (vertex stage).",
}


# ---------------------------------------------------------------------------
# case generation
# ---------------------------------------------------------------------------
def _geom(arm, spec):
    """(byte_index_or_None, start, width) for one field spec."""
    name, how, a, b = spec[0], spec[1], spec[2], spec[3]
    if how == "field":
        st, w = field_geom(arm["mn"], name)
        return None, st, w
    return a, a * 8, b


def build_cases(anchor_report):
    """The frozen case list. `anchor_report` is work/anchors/anchor_report.json."""
    cases = []
    idx = 0

    def add(**kw):
        nonlocal idx
        kw["idx"] = idx
        idx += 1
        cases.append(kw)

    for arm in ARMS:
        aid = arm["id"]
        mn = arm["mn"]
        probe = arm.get("probe")

        # --- locate the anchor -------------------------------------------
        blk = None
        tgt = 0
        block_lo = block_hi = None
        if probe is not None:
            cands = probe if isinstance(probe, (list, tuple)) else [probe]
            chosen = None
            tried = []
            for cand in cands:
                rep = anchor_report.get(cand)
                if rep is None or "error" in rep:
                    tried.append("%s:no-compile" % cand)
                    continue
                hits = [t for t in rep["tokens"]
                        if t["mn"] == mn and t.get("len")]
                if len(hits) <= arm["occ"]:
                    tried.append("%s:%d-occurrence(s)" % (cand, len(hits)))
                    continue
                chosen = (cand, rep, hits[arm["occ"]])
                break
            if chosen is None:
                add(arm=aid, role="arm_not_run", instr=mn, field="-", value=-1,
                    bytes="", probe=cands[0], style=arm["style"],
                    dim=arm["dim"], kind=arm.get("kind"),
                    byte_index=None, fstart=None, fwidth=None,
                    cross_field=None, cross_value=None,
                    note="no candidate kernel supplied a %s occurrence %d: %s"
                         % (mn, arm["occ"], "; ".join(tried)))
                continue
            probe, rep, t = chosen
            main = bytes.fromhex(rep["main_hex"])
            if arm["style"] == "S":
                block_lo, block_hi = t["off"], t["off"] + t["len"]
                blk = main[block_lo:block_hi]
                tgt = 0
            else:
                blk = main
                tgt = t["off"]
                block_lo, block_hi = 0, len(main)
        else:
            # fully SYNTHESIZED anchors (mov_imm, stop)
            if mn == "mov_imm":
                blk = H.mov_imm(7, 33)
            elif mn == "stop":
                blk = H.stop(0)
            else:
                raise RuntimeError("no anchor source for %s" % mn)
            tgt = 0
            block_lo, block_hi = 0, len(blk)

        common = dict(arm=aid, instr=mn, probe=probe, style=arm["style"],
                      dim=arm["dim"], kind=arm.get("kind"), occ=arm["occ"],
                      block_lo=block_lo, block_hi=block_hi, tgt=tgt,
                      anchor=blk.hex(), after=arm.get("after"),
                      probe_reg=arm.get("probe_reg"))

        # --- baseline ------------------------------------------------------
        add(role="baseline", field="-", value=-1, bytes=blk.hex(),
            byte_index=None, fstart=None, fwidth=None,
            cross_field=None, cross_value=None,
            note="unmutated anchor; every later case is a delta against it",
            **common)

        # --- liveness ladder (rule 3) --------------------------------------
        lad = arm.get("ladder")
        if lad:
            lname, lhow = lad[0], lad[1]
            try:
                lbi, lst, lw = _geom(arm, lad)
            except KeyError:
                lbi = lst = lw = None
            if lst is not None:
                lvals = coverage(lw) if lw <= 4 else \
                    [0, 1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 255]
                lvals = [v for v in lvals if v < (1 << lw)]
                for v in lvals:
                    try:
                        mb = set_field(blk, tgt, lst, lw, v)
                    except IndexError:
                        continue
                    add(role="ladder", field=lname, value=v, bytes=mb.hex(),
                        byte_index=lbi, fstart=lst, fwidth=lw,
                        cross_field=None, cross_value=None,
                        note="LIVENESS LADDER on a known-live control: %s"
                             % lad[-1],
                        **common)

        # --- the CROSS dimension (rule: a verdict at one form is a verdict
        #     about one form) -------------------------------------------------
        cross = arm.get("cross") or []
        cross_pts = [(None, None, None, None, None)]
        if cross:
            cross_pts = []
            for cspec in cross:
                cname = cspec[0]
                try:
                    cbi, cst, cw = _geom(arm, cspec[:4])
                except KeyError:
                    continue
                for cv in cspec[4]:
                    if cv >= (1 << cw):
                        continue
                    cross_pts.append((cname, cbi, cst, cw, cv))
            if not cross_pts:
                cross_pts = [(None, None, None, None, None)]

        # --- the fields under test -----------------------------------------
        for spec in arm["fields"]:
            fname = spec[0]
            try:
                bi, st, w = _geom(arm, spec)
            except KeyError:
                add(role="arm_not_run", field=fname, value=-1, bytes=blk.hex(),
                    byte_index=None, fstart=None, fwidth=None,
                    cross_field=None, cross_value=None,
                    note="%s.%s is not in the pinned db.json snapshot"
                         % (mn, fname), **common)
                continue
            for (cname, cbi, cst, cw, cv) in cross_pts:
                if cname is not None and (cst, cw) == (st, w):
                    continue        # never cross a field with itself
                base_blk = blk
                cnote = ""
                if cname is not None:
                    try:
                        base_blk = set_field(blk, tgt, cst, cw, cv)
                    except IndexError:
                        continue
                    cnote = ("crossed with %s=0x%02x -- a verdict at ONE value "
                             "of %s is a verdict about that value only "
                             "(EXP-0140 fanned a single-form dst verdict out to "
                             "five descriptors)" % (cname, cv, cname))
                for v in coverage(w):
                    try:
                        mb = set_field(base_blk, tgt, st, w, v)
                    except IndexError:
                        continue
                    add(role="sweep", field=fname, value=v, bytes=mb.hex(),
                        byte_index=bi, fstart=st, fwidth=w,
                        cross_field=cname, cross_value=cv, note=cnote, **common)

            # --- byte-mate control (only meaningful for a sub-byte field) --
            if w < 8:
                nfree = ((st + w - 1) // 8 - st // 8 + 1) * 8 - w
                anchor_v = get_field(blk, tgt, st, w)
                for v in coverage(min(nfree, 8)):
                    try:
                        mb = complement_bits(blk, tgt, st, w, v)
                    except IndexError:
                        continue
                    add(role="bytemate", field=fname + "@bytemate", value=v,
                        bytes=mb.hex(), byte_index=bi, fstart=st, fwidth=w,
                        cross_field=None, cross_value=None,
                        note="BYTE-MATE CONTROL: %s is HELD at its anchor "
                             "value %d and only the OTHER bits of its byte(s) "
                             "move. Two readings, and RESULTS.md must say which "
                             "applies: (a) where the neighbouring bits are a "
                             "match-pinned opcode nibble, movement here is "
                             "EXPECTED and merely proves the splice really is "
                             "sub-byte; (b) where they are another live field, "
                             "movement here means movement credited to %s "
                             "could have come from the byte-mate instead, and "
                             "the attribution is ambiguous."
                             % (fname, anchor_v, fname),
                        **common)

        # --- falsifier (rule: at least one case pre-registered to FAIL) ----
        fv = arm.get("falsifier_byte0", 0x00)
        add(role="falsifier", field="_byte0", value=fv,
            bytes=set_byte(blk, tgt, 0, fv).hex(), byte_index=0,
            fstart=0, fwidth=8,
            cross_field=None, cross_value=None,
            note="PRE-REGISTERED TO FAIL: byte0 forced to 0x%02x is not this "
                 "instruction. If it scores `ok`, this arm's sweep proves "
                 "nothing and is reported as such rather than promoted.%s"
                 % (fv, "" if fv == 0x00 else
                    " Chosen away from 0x00 because byte0 here carries the "
                    "pinned opcode nibble AND the swept dst field, so 0x00 is "
                    "confounded with dst=0 -- measured identical to the "
                    "baseline in the prefreeze smoke "
                    "(raw/prefreeze/diag_byte0.json)."),
            **common)

    return cases


def matrix_sha256(cases):
    blob = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def main():
    rep_path = EXP / "work" / "anchors" / "anchor_report.json"
    if not rep_path.exists():
        raise SystemExit("run harness/anchors.py first (%s missing)" % rep_path)
    rep = json.loads(rep_path.read_text())
    cases = build_cases(rep)
    from collections import Counter
    print("cases:", len(cases))
    print("by role:", json.dumps(dict(Counter(c["role"] for c in cases)),
                                 sort_keys=True))
    print("by arm:")
    for a, n in sorted(Counter(c["arm"] for c in cases).items()):
        print("   %-24s %d" % (a, n))
    print("matrix sha256:", matrix_sha256(cases))
    outp = EXP / "work" / "casematrix.json"
    outp.write_text(json.dumps(cases, sort_keys=True))
    print("wrote", outp)


if __name__ == "__main__":
    main()
