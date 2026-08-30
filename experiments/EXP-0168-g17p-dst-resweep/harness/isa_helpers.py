#!/usr/bin/env python3
"""EXP-0168 program construction (G17P `dst` re-sweep + 12 one-field-away).

Every scaffolding instruction is built through `tools/agx-isa`'s own READ-ONLY
`isadb.assemble(mnemonic, fields)`. The instruction UNDER TEST is either

  * lifted byte-for-byte out of the compiled form of OUR OWN MSL
    (`kernels/probes.metal`) and then mutated in ONE field  -- carrier STYLE-S
    ("SYNTH+LIFTED", the EXP-0154 shape), or
  * mutated IN PLACE inside the compiled form of our own MSL and that whole
    kernel dispatched with real inputs                      -- carrier STYLE-P
    ("IN-PLACE"), used for control-flow and memory instructions whose branch
    targets and buffer bindings do not survive being moved.

Structure (not results) reused, and cited, from EXP-0154 `harness/isa_helpers.py`
(same project, same rules): `mov_imm`, `falu2i_raw`, `device_store`,
`store_word`, `stop`, `build_program`, `assert_round_trip`, the seed tables and
the PRE/POST sentinel construction.

WHAT IS NEW HERE, AND WHY
-------------------------
1. **The observable is WHICH REGISTER SLOT CHANGED, not what one word holds.**
   `dst` is a destination-register selector: the only dimension it controls is
   the identity of the written register. A read-back of one word is blind to it
   by construction. Every STYLE-S program therefore dumps all 16 GPRs and the
   verdict is a function of the *set of moved slots*.

2. **A high-register read-back probe.** `dst` fields wider than 4 bits reach
   past r15, outside the dump window. `probe_instrs(v)` appends a
   `falu2i(dst=R_PROBE, srcA=v, +0.0)` that copies register `v` (7-bit, r0..r127)
   into a dumped slot, so the sweep is not silently truncated at r15.

3. **A tail poison region.** `W_TAIL..OUT_WORDS` is never the target of any
   store this module emits. If a dispatch reports STATUS OK and the tail is no
   longer `0xDEADBEEF`, something wrote out of bounds; if the WHOLE buffer is
   still poison, the program never ran. EXP-0160 saw 25 dispatches report
   STATUS OK and write nothing at all, with no `InnocentVictim` string; against a
   zero-initialised buffer those would have been 25 confident `silent_zero`s.
   Such a case is `validity != "valid"` here and is re-run, never recorded as a
   silent zero.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def _find_isadb():
    """The agx-isa snapshot this experiment is pinned to.

    `work/frozen/` holds the EXACT `db.json` / `isadb.py` the hardware ran
    against, sha256-checked in CAPTURE_CONTRACT.json. It is preferred because
    the repo host's `tools/agx-isa/db.json` DRIFTS while sibling experiments
    extend the ISA (EXP-0165 owns it right now), which would silently re-key our
    verdicts against a descriptor the hardware never saw.
    """
    for cand in (EXP / "work" / "frozen",
                 EXP / "tools" / "agx-isa",                     # on the neo
                 Path.home() / "agxre" / "EXP-0168" / "tools" / "agx-isa",
                 EXP.parents[1] / "tools" / "agx-isa",          # on the repo host
                 Path.home() / "agxre" / "tools" / "agx-isa"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    raise RuntimeError("cannot locate tools/agx-isa")


ISA_DIR = _find_isadb()
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

# --------------------------------------------------------------------------
# Register plan.
# --------------------------------------------------------------------------
R_IDX = 15          # device_store index register; re-seeded to 0 before EVERY
                    # store so a release-on-read of r15 cannot move later stores
R_SENT = 12         # POST-sentinel register, written AFTER the tested block
R_PRE = 13          # scratch used to materialize the PRE sentinel
R_PROBE = 11        # high-register read-back probe destination
N_REGS = 16

# Distinct integer seeds, all inside mov_imm's HW-VALIDATED 0..127 range
# (EXP-0128: imm >= 128 does not write the register at all; imm7 == 12 does not
# tokenize under the current length rule, so it is avoided). Chosen so that
# a+b, a-b, a*b, min/max and "which register is this?" are uniquely decodable.
# NO SEED MAY BE 0. `SEED_I[15]` was 0, and the prefreeze diagnostic
# raw/prefreeze/diag_byte0.json measured that the reg_move forms 0x00/0x01/0x03
# WRITE ZERO. A dst sweep therefore could not distinguish "dst=15 wrote 0 into
# r15" from "dst=15 did nothing" -- the same class of by-construction blindness
# as EXP-0140's co-varying oracle, in MY OWN seed table. 121 is distinct from
# every other seed and inside mov_imm's HW-VALIDATED 0..127 range.
SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 121}

# Distinct float seeds. Every value is an EXACT fixed point of the falu2i
# minifloat immediate encoder (asserted at import time below).
# r14 MUST stay +0.0 -- it is the `+0.0` source every falu2i seed adds to.
# r15 was also 0.0 and is not required to be, so it is given a distinct exact
# minifloat value for the same reason SEED_I[15] changed. For kind="float" arms
# dst=14 remains undecidable when the instruction writes +0.0; that is a
# recorded limit of the float carrier, and the int carrier covers r14.
SEED_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
          8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0, 13: 0.75,
          14: 0.0, 15: 2.5}

SENT_PRE = 0x5A5A5A5A     # written to memory BEFORE the tested block
SENT_POST = 111           # mov_imm-able POST sentinel (< 128)
POISON = 0xDEADBEEF

# Output word layout (32-bit words). device_store's idx_off unit is 4 WORDS
# (EXP-0090/EXP-0119).
STORE_STRIDE_WORDS = 4
W_REG0 = 0                                  # r0..r15 -> words 0,4,...,60
W_PRE = 16 * STORE_STRIDE_WORDS             # 64
W_POST = W_PRE + STORE_STRIDE_WORDS         # 68
W_PROBE = W_POST + STORE_STRIDE_WORDS       # 72  high-register probe result
W_TAIL = W_PROBE + STORE_STRIDE_WORDS       # 76  first word NEVER stored to
N_TAIL_WORDS = 28
OUT_WORDS = W_TAIL + N_TAIL_WORDS           # 104 words read back


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


# --------------------------------------------------------------------------
# Scaffolding instructions (all assembled by tools/agx-isa itself).
# --------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031 for 0..127. imm >= 128 sets
    `imm_top`, which EXP-0140 showed selects a DIFFERENT, LONGER instruction
    that does not write the register -- hard-rejected in scaffolding (it is a
    sweep TARGET, never a building block)."""
    if not (0 <= imm8 <= 127):
        raise ValueError("mov_imm imm8 must be 0..127 (EXP-0128/EXP-0140)")
    return isadb.assemble("mov_imm", {"dst": dst, "imm7": imm8 & 0x7F,
                                      "imm_top": 0})


def mov_imm_raw(dst, byte1):
    """The same 2 bytes with byte+1 taken VERBATIM, so `imm_top` can be swept.
    Only the mov_imm arm uses this."""
    return bytes([0x0C | ((dst & 0xF) << 4), byte1 & 0xFF])


def falu2i_raw(dst, srcA_reg7, k, opflags4=0, ctrl_lo=0, mods=0xC0,
               srcA_size=1, imm_flag=None, opsel=4):
    """6B falu2i (float op with a packed minifloat immediate). Defaults are the
    anchor values of our own compiled `a[t]+3.0f`; `mods=0xC0` is EXP-0101's
    HW-VALIDATED requirement. srcA_reg7 reaches r0..r127."""
    b1, sign = isadb.imm_encode(k)
    if imm_flag is None:
        imm_flag = b1 & 1
    return isadb.assemble("falu2i", {
        "dst": dst, "imm_flag": imm_flag & 1, "imm_mant": (b1 >> 1) & 0x7,
        "imm_exp": (b1 >> 4) & 0xF, "opsel": opsel, "imm_sign": sign,
        "opflags": opflags4 & 0xF, "srcA_size": srcA_size,
        "srcA_reg": srcA_reg7 & 0x3F, "srcA_reg_top": (srcA_reg7 >> 6) & 1,
        "ctrl_lo": ctrl_lo & 0x7F, "mods": mods & 0xFF,
    })


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                 space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                 st_format_ext=0, st_desc_hi=0x24, elem_size=0x11,
                 reserved7=0, reserved13=0):
    """14B device_store, ALU-forwarded form. `extmode = 2*data_reg` is EXP-0090
    finding_5 (HW-VALIDATED for data_reg < 64); `idx_off` unit is 4 WORDS."""
    if extmode is None:
        extmode = (data_reg << 1) & 0xFF
    return isadb.assemble("device_store", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "st_format": st_format, "st_format_ext": st_format_ext,
        "idx_off": idx_off & 0x7FF, "st_desc_hi": st_desc_hi,
        "elem_size": elem_size & 0xFF, "reserved13": reserved13,
    })


def store_word(word_idx, data_reg, base_slot=0):
    """Store r[data_reg] at absolute output WORD index `word_idx`, re-seeding the
    index register first so a release-on-read of r15 cannot relocate the store."""
    if word_idx % STORE_STRIDE_WORDS:
        raise ValueError("word_idx must be a multiple of %d" % STORE_STRIDE_WORDS)
    return (mov_imm(R_IDX, 0)
            + device_store(R_IDX, word_idx // STORE_STRIDE_WORDS, base_slot,
                           data_reg=data_reg))


def stop(reserved=0):
    return isadb.assemble("stop", {"reserved": reserved & 0xFFFFFF})


def build_program(instrs, carrier_len, pad_dst=14):
    """Pad to the carrier's `_agc.main` length with 2-byte writes to a register
    whose seed is already 0/0.0, so padding cannot perturb the dump."""
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d exceeds carrier %d"
                         % (len(body), carrier_len))
    rem = carrier_len - len(body)
    if rem % 2:
        raise ValueError("odd padding remainder %d" % rem)
    out = body + mov_imm(pad_dst, 0) * (rem // 2)
    assert len(out) == carrier_len
    return out


def assert_round_trip(buf):
    recs, leftover = isadb.disassemble(buf)
    if leftover:
        raise AssertionError("round-trip: %d leftover bytes" % len(leftover))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = buf[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s)"
                                 % (off, r["mnemonic"]))
        off += r["length"]
    return recs


def round_trips(buf):
    """True iff `buf` re-tokenizes exactly. A MUTATED instruction is often
    deliberately undecodable by OUR disassembler -- that is a recorded property
    of the case (`rt_ok`), never a build error: the hardware, not
    `tools/agx-isa`, is the authority on what the bytes mean."""
    try:
        assert_round_trip(buf)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# The synthesized program (carrier STYLE-S).
# --------------------------------------------------------------------------
def seed_instrs(kind):
    """Seed r0..r15 with distinct, decodable values."""
    if kind == "int":
        return [mov_imm(r, SEED_I[r]) for r in range(N_REGS)]
    if kind == "float":
        out = [mov_imm(14, 0)]                  # r14 = 0.0f, the +0 source
        for r in range(N_REGS):
            if r == 14:
                continue
            out.append(falu2i_raw(r, 14, SEED_F[r]))
        return out
    raise ValueError(kind)


def seed_high(regs, kind):
    """Additionally seed a set of registers ABOVE r15, for `dst` sweeps that
    reach past the dump window. `mov_imm`'s dst nibble stops at r15, so the
    high seeds are written with falu2i (7-bit dst is not available on falu2i
    either -- its dst is the same 4-bit nibble -- so a high register is seeded
    by falu2i's SOURCE side instead: we cannot write it, and the sweep therefore
    reads whatever the carrier left there. That is recorded, not hidden: for
    v > 15 the oracle is STRUCTURAL (did the probe slot change?) rather than
    value-exact."""
    return []


def pre_sentinel_instrs(kind):
    """Write SENT_PRE into memory BEFORE the tested block, then RESTORE the
    scratch register's seed so the seed table the block sees is intact."""
    out = [mov_imm(R_PRE, SENT_PRE & 0x7F), store_word(W_PRE, R_PRE)]
    if kind == "int":
        out.append(mov_imm(R_PRE, SEED_I[R_PRE]))
    else:
        out.append(falu2i_raw(R_PRE, 14, SEED_F[R_PRE]))
    return out


def probe_instrs(high_reg):
    """Copy register `high_reg` (0..127) into R_PROBE and store it, so a `dst`
    value outside the 16-register dump window is still observable. Uses falu2i
    `+0.0`, whose srcA is 7 bits."""
    if high_reg is None:
        return []
    return [falu2i_raw(R_PROBE, high_reg, 0.0), store_word(W_PROBE, R_PROBE)]


def dump_instrs(store_regs=None):
    """Store every register, then the POST sentinel."""
    regs = list(range(N_REGS)) if store_regs is None else list(store_regs)
    out = []
    for r in regs:
        out.append(store_word(W_REG0 + r * STORE_STRIDE_WORDS, r))
    out.append(mov_imm(R_SENT, SENT_POST))
    out.append(store_word(W_POST, R_SENT))
    return out


def synth_program(kind, block_bytes, carrier_len, high_probe=None,
                  tail_bytes=b"", pre_block=b""):
    """seeds -> PRE sentinel -> [pre_block] -> [block under test] ->
    [high-register probe] -> 16-register dump -> POST sentinel -> [tail] -> stop.

    `pre_block` and `tail_bytes` let one arm place extra AUTHORED instructions
    around the block (the mov_imm consumption-witness arm, the falu_acc
    second-consumer arm, the mid-program-stop arm) without a second builder.
    """
    instrs = seed_instrs(kind)
    instrs += pre_sentinel_instrs(kind)
    if pre_block:
        instrs.append(pre_block)
    instrs.append(block_bytes)
    instrs += probe_instrs(high_probe)
    instrs += dump_instrs()
    if tail_bytes:
        instrs.append(tail_bytes)
    instrs.append(stop())
    return build_program(instrs, carrier_len)


def synth_program_midstop(kind, stop_bytes, carrier_len):
    """seeds -> PRE sentinel -> [stop under test] -> 16-register dump ->
    POST sentinel -> stop.

    The stop under test sits BEFORE the dump. If it terminates (the documented
    behaviour) the dump never runs and the whole register window stays POISON;
    if some 24-bit body made it not terminate, the dump appears. That is the
    only carrier in which `stop.reserved` can express what it controls."""
    instrs = seed_instrs(kind)
    instrs += pre_sentinel_instrs(kind)
    instrs.append(stop_bytes)
    instrs += dump_instrs()
    instrs.append(stop())
    return build_program(instrs, carrier_len)


SENT_WITNESS = 77         # mov_imm-able post-stop witness (< 128)


def synth_program_terminalstop(kind, stop_bytes, carrier_len):
    """seeds -> PRE sentinel -> 16-register dump -> POST sentinel ->
    [stop under test] -> POST-STOP WITNESS -> stop.

    The stop under test is the program's REAL terminator: every word the
    observable depends on has already been stored, so the register dump is
    present in EVERY case and the field cannot express itself through the dump
    at all. What it can express is whether anything AFTER it executes -- so a
    witness write into `W_PROBE` follows it. Terminates (documented behaviour)
    -> word 72 stays POISON. Fails to terminate -> word 72 == SENT_WITNESS.

    WHY THIS FUNCTION EXISTS. Until the prefreeze smoke caught it, STOP/terminal
    fell through to `synth_program()`, which places the block under test in the
    BODY -- byte-for-byte the same program shape as `synth_program_midstop()`.
    The two arms produced identical observations on hardware (whole dump poison,
    POST poison) because they were ONE CARRIER. That is exactly the R2 violation
    this experiment was built to expose in EXP-0155, occurring in my own harness.
    """
    instrs = seed_instrs(kind)
    instrs += pre_sentinel_instrs(kind)
    instrs += dump_instrs()
    instrs.append(stop_bytes)
    instrs.append(mov_imm(R_PROBE, SENT_WITNESS))
    instrs.append(store_word(W_PROBE, R_PROBE))
    instrs.append(stop())
    return build_program(instrs, carrier_len)


def expected_pre():
    return SENT_PRE & 0x7F


def seed_regs(kind):
    """The host-known register table the program installs before the block.
    This is the GPU-independent half of every oracle."""
    if kind == "int":
        return [SEED_I[r] for r in range(N_REGS)]
    return [struct.unpack("<I", struct.pack("<f", f32(SEED_F[r])))[0]
            for r in range(N_REGS)]


# Sanity: every float seed must be an EXACT minifloat fixed point.
for _r, _v in SEED_F.items():
    if f32(imm_value(_v)) != f32(_v):
        raise AssertionError("SEED_F[%d]=%r is not an exact minifloat fixed point"
                             % (_r, _v))
