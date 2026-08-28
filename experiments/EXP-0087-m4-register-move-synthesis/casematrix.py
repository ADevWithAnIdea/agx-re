#!/usr/bin/env python3
"""EXP-0087 frozen splice matrix + observation codec (single source of truth).

run.py builds every case from CASES below; verify.py re-derives and checks
the contract against it; analysis.py decodes observations with the same
codec. The matrix is frozen BEFORE any GPU dispatch of a spliced variant.

Carrier: kernels/synth_move.metal function `k` (see baseline.py FROZEN).
Sixteen thread-invariant loads `in[K]` (K=0..15) are each marshaled through
their own compact 4-byte move (byte0 low-nibble 0xb family) into a distinct
GPR, then four vectorized device_stores write them out unchanged:
baseline out[K] == in[K] for every K, with IN_PATTERN[K] = 1000.0 + K.

Two probe sites (see baseline.py):
  probe_src -- the FIRST move (`cb080108`: dst=12 usrc=8), which feeds
               out[0] via the first vector store. Every field of THIS
               instruction except dst is swept (byte+2 family, op_desc,
               src/usrc). dst is held at 12 throughout the src-side sweep so
               a case's effect is legible purely from out[0] (and any
               cross-talk elsewhere).
  probe_dst -- the LAST move (`3b260108`: dst=3 usrc=0x26), which
               (unmodified) feeds out[15] via the fourth vector store and is
               the ONLY instruction after it in program order -- so
               retargeting its `dst` field is unambiguous: nothing later can
               overwrite whatever register it is redirected to write, and
               out[15] itself goes stale (nothing else writes r3).

Every case changes exactly ONE field family relative to either probe's
ORIGINAL bytes (one-changed-field-per-case discipline). Every case is
independently re-assembled from scratch with tools/agx-isa's `assemble()`
(mnemonic chosen by the target byte+2 family) wherever the DB has a
matching descriptor; the two exploratory byte+2 values outside every known
family (0x0F, 0xFF) are constructed directly as raw bytes (struct-packed),
clearly labeled MOVE-05, since no descriptor claims them.

Items:
  CTRL      paired controls: re-splice a probe with its OWN original bytes
            (mechanical null result -- proves the splice pipeline changes
            nothing when nothing is changed).
  MOVE-01   byte+2 FAMILY sweep on probe_src (dst=12,src=8,op_desc=8 fixed):
            every high-nibble value documented as "observed" by each of the
            five DB descriptors reg_move_c0/c1/c9/cb/c2var.
            H-ZERO (frozen): any byte+2 whose LOW NIBBLE != 1 does not read
            the intended uniform slot; it silently yields exactly 0 in the
            destination register, with no other observable side effect.
  MOVE-02   op_desc (byte+3) SINGLE-BIT sweep on probe_src (dst=12,src=8,
            byte+2=0x01 -- the one WORKING family from MOVE-01 -- fixed):
            each of the 8 bits of op_desc flipped one at a time from the
            known-good value 0x08. No single frozen hypothesis is stated
            (pilot probing already showed a non-monotonic bit pattern: bit0
            harmless, bit1/bit3 break the read to zero, bit2 CORRUPTS a
            DIFFERENT output slot, bits 4-7 harmless) -- this item is
            explicitly exploratory per-bit, predictions recorded per case.
  MOVE-03   src/usrc sweep on probe_src (dst=12, byte+2=0x01, op_desc=0x08
            fixed): sibling values already used by other moves in this same
            program (predicted: out[0] takes that sibling's tagged value --
            H-SRC), values below our program's own uniform-slot range
            (explore), values above the observed range including the
            src_flag/GPR-mode bit (explore).
  MOVE-04   dst sweep on probe_dst (src=0x26, byte+2=0x01, op_desc=0x08
            fixed): dst retargeted across all four register quads. Frozen
            from pilot probing (informal, pre-registration-exempt hardware
            exploration per the Rosenzweig extrapolate-then-test method) --
            H-DST: out[quad(new_dst)] takes in[15]'s tagged value; out[15]
            (no longer written by anything) reads exactly 0.
  MOVE-05   byte+2 values OUTSIDE every documented family (0x0F, 0x FF):
            exploratory; no assembler descriptor claims these, so they are
            constructed as raw bytes. Frozen prediction: FAULT
            (CMDBUF_ERROR), by analogy with the piloted 0xFF case.

Note on provenance of the frozen predictions: this matrix was informed by
informal, non-recorded pilot splicing on this same local M4 (the standard
"extrapolate, then test" RE method CLAUDE.md endorses) BEFORE this
pre-registration was written. The pilot session is not itself evidence --
only the two gated captures below (run01/run02) are. Where the pilot did not
reach a case (none, in this matrix) or where its result is not a single
predictable point value, the prediction is honestly recorded as "explore".
"""
import struct, sys
from pathlib import Path

sys.dont_write_bytecode = True
_ISA_TOOLS = Path(__file__).resolve().parents[2] / "tools" / "agx-isa"
if str(_ISA_TOOLS) not in sys.path:
    sys.path.insert(0, str(_ISA_TOOLS))

IN_PATTERN = [1000.0 + k for k in range(16)]   # in[K], K=0..15


def fill_in():
    return b"".join(struct.pack("<f", v) for v in IN_PATTERN)


def f32_hex(v):
    return struct.pack("<f", v).hex()


# ---------------------------------------------------------------------------
# byte+2 candidate families (every "observed" high nibble from each of the
# five DB descriptors reg_move_c0/c1/c9/cb/c2var; source: tools/agx-isa/db.json)
# ---------------------------------------------------------------------------
C0_HI = (0x0, 0x2, 0x6)                                   # -> 0x00,0x20,0x60
C1_HI = (0x0, 0x2, 0x6, 0xa, 0xc, 0xe)                     # -> 0x01,0x21,...
C9_HI = (0x0, 0x2, 0x4, 0x6, 0x8, 0xc)                     # -> 0x09,0x29,...
CB_HI = (0x0, 0x1, 0x2, 0x3)                               # -> 0x0b,0x1b,0x2b,0x3b
C2VAR_LO = (0x2, 0x3, 0x4, 0x6, 0xa)                        # -> 0x22,0x23,0x24,0x26,0x2a

FAMILY_MNEM = {0x0: "reg_move_c0", 0x1: "reg_move_c1", 0x9: "reg_move_c9", 0xb: "reg_move_cb"}


def byte2_for(lo, hi):
    return (hi << 4) | lo


def move01_byte2_list():
    vals = [byte2_for(0x0, h) for h in C0_HI]
    vals += [byte2_for(0x1, h) for h in C1_HI]
    vals += [byte2_for(0x9, h) for h in C9_HI]
    vals += [byte2_for(0xb, h) for h in CB_HI]
    vals += [(0x2 << 4) | lo for lo in C2VAR_LO]
    return vals


def assemble_move(byte2, dst, src, op_desc):
    """Build the 4-byte compact move via tools/agx-isa's own assembler where
    a descriptor exists for this byte+2 value; otherwise raw bytes (MOVE-05
    only). Returns (hex, mnemonic_or_None)."""
    import isadb
    lo = byte2 & 0xF
    hi = (byte2 >> 4) & 0xF
    if lo in (0x0, 0x1, 0x9) :
        mnem = FAMILY_MNEM[lo]
        b = isadb.assemble(mnem, {"dst": dst, "src_reg": src & 0x7F, "src_flag": (src >> 7) & 1,
                                  "src_class": hi, "op_desc": op_desc})
        return b.hex(), mnem
    if lo == 0xb:
        mnem = "reg_move_cb"
        b = isadb.assemble(mnem, {"dst": dst, "src": src & 0xFF, "form": byte2, "b3": op_desc})
        return b.hex(), mnem
    if hi == 0x2 and lo not in (0x0, 0x1, 0x9, 0xb):
        mnem = "reg_move_c2var"
        b = isadb.assemble(mnem, {"dst": dst, "src_reg": src & 0x7F, "src_flag": (src >> 7) & 1,
                                  "subform": lo, "op_desc": op_desc})
        return b.hex(), mnem
    # no descriptor covers this byte+2 -- raw construction (MOVE-05 only)
    raw = bytes([0x0B | (dst << 4), src & 0xFF, byte2, op_desc])
    return raw.hex(), None


def assemble_uniform_mov(dst, usrc):
    import isadb
    return isadb.assemble("uniform_mov", {"dst": dst, "usrc": usrc}).hex()


# ---------------------------------------------------------------------------
# THE FROZEN CASE LIST
# ---------------------------------------------------------------------------
CASES = []


def _add(name, item, probe, dst, src, byte2, op_desc, pred, note):
    hexval, mnem = assemble_move(byte2, dst, src, op_desc)
    CASES.append({"name": name, "item": item, "probe": probe, "dst": dst, "src": src,
                  "byte2": byte2, "op_desc": op_desc, "hex": hexval, "assembled_as": mnem,
                  "pred": pred, "note": note})


# CTRL: identity re-splice of both probes (paired controls / null result).
_add("ctrl_src_identity", "CTRL", "src", 12, 8, 0x01, 0x08,
     {"out0": "unchanged"}, "re-splice probe_src with its own original bytes")
_add("ctrl_dst_identity", "CTRL", "dst", 3, 0x26, 0x01, 0x08,
     {"out15": "unchanged"}, "re-splice probe_dst with its own original bytes")

# MOVE-01: byte+2 family sweep on probe_src (dst=12, src=8, op_desc=8 fixed).
for b2 in move01_byte2_list():
    if b2 == 0x01:
        continue   # identical to ctrl_src_identity; not duplicated
    _add("move01_b2_%02x" % b2, "MOVE-01", "src", 12, 8, b2, 0x08,
         {"out0": 0.0}, "byte+2 family sweep; H-ZERO predicts a silent zero read")

# MOVE-02: op_desc single-bit sweep on probe_src (dst=12, src=8, byte2=0x01).
_MOVE02_PRED = {0x09: 1000.0, 0x0a: 0.0, 0x0c: "corrupt_out8", 0x00: 0.0,
                0x18: 0.0, 0x28: 1000.0, 0x48: 1000.0, 0x88: 1000.0}
for bit in range(8):
    od = 0x08 ^ (1 << bit)
    _add("move02_bit%d_od%02x" % (bit, od), "MOVE-02", "src", 12, 8, 0x01, od,
         {"out0": _MOVE02_PRED[od]}, "op_desc single-bit flip from the working 0x08")

# MOVE-03: src/usrc sweep on probe_src (dst=12, byte2=0x01, op_desc=0x08).
_SIBLINGS = {1: 0x0a, 4: 0x10, 8: 0x18, 12: 0x20, 15: 0x26}
for k, usrc in _SIBLINGS.items():
    _add("move03_sibling_k%02d" % k, "MOVE-03", "src", 12, usrc, 0x01, 0x08,
         {"out0": IN_PATTERN[k]}, "steal a sibling move's usrc (H-SRC: reads in[%d])" % k)
for usrc in (0x00, 0x04):
    _add("move03_lorange_%02x" % usrc, "MOVE-03", "src", 12, usrc, 0x01, 0x08,
         {"out0": "explore"}, "uniform slot below our program's own allocated range")
for usrc in (0x7e, 0xfe):
    _add("move03_hirange_%02x" % usrc, "MOVE-03", "src", 12, usrc, 0x01, 0x08,
         {"out0": "explore"}, "uniform slot far above our program's own allocated range")
_add("move03_gprflag_88", "MOVE-03", "src", 12, 0x88, 0x01, 0x08,
     {"out0": "explore"}, "src_flag bit7 set: GPR-mode read of r8 before any of our own "
     "moves have executed")

# MOVE-04: dst sweep on probe_dst (src=0x26, byte2=0x01, op_desc=0x08).
# Frozen from pilot probing: out[quad(new_dst)] takes in[15] (1015.0); out[15]
# (no longer written) reads 0.0.
_MOVE04 = ((12, "out0", 1000.0 + 15), (8, "out4", 1000.0 + 15),
          (4, "out8", 1000.0 + 15), (0, "out12", 1000.0 + 15))
for dst, slot, val in _MOVE04:
    _add("move04_dst%02d" % dst, "MOVE-04", "dst", dst, 0x26, 0x01, 0x08,
         {slot: val, "out15": 0.0}, "retarget the last move's dst; nothing later can "
         "overwrite it")

# MOVE-05: byte+2 values outside every documented family (raw construction).
_add("move05_byte2_0f", "MOVE-05", "src", 12, 8, 0x0f, 0x08,
     {"status": "CMDBUF_ERROR"}, "undocumented low-nibble 0xF; exploratory, raw bytes")
_add("move05_byte2_ff", "MOVE-05", "src", 12, 8, 0xff, 0x08,
     {"status": "CMDBUF_ERROR"}, "undocumented byte+2=0xFF; exploratory, raw bytes")

TOTAL = len(CASES)
assert TOTAL == 49, "case count drifted: %d" % TOTAL


# ---------------------------------------------------------------------------
# decode helper: compare a captured 16-float output vector to baseline.
# ---------------------------------------------------------------------------
def decode_out(out_hex):
    """Parse the 16x float32 OUT hex string into a list of floats (or None
    entries on a short/garbled read)."""
    if not out_hex or len(out_hex) < 128:
        return None
    try:
        raw = bytes.fromhex(out_hex[:128])
    except ValueError:
        return None
    return list(struct.unpack("<16f", raw))


def diff_from_baseline(values):
    """Return {index: value} for every slot that differs from IN_PATTERN
    (bit-exact float compare; the carrier never computes, only moves data,
    so no tolerance is appropriate)."""
    if values is None:
        return None
    out = {}
    for i, v in enumerate(values):
        if struct.pack("<f", v) != struct.pack("<f", IN_PATTERN[i]):
            out[i] = v
    return out
