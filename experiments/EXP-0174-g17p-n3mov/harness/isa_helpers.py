#!/usr/bin/env python3
"""EXP-0174 program construction — the `n3_mov` GPR-to-GPR move question.

Every scaffolding instruction is built through `tools/agx-isa`'s own READ-ONLY
`isadb.assemble(mnemonic, fields)`. The instruction UNDER TEST is built from
FOUR RAW BYTES that this module computes from the descriptor's own field
geometry — **no byte of it is copied from a compiled shader** — which is the
form the acceptance gate asks for.

LINEAGE (our own code, this repository, cited per CODEX.md):
  EXP-0154/harness/isa_helpers.py -> EXP-0161 -> EXP-0168/harness/isa_helpers.py
The seed-table idea, the PRE/POST sentinel construction, the poisoned read-back,
the tail-poison region and `build_program` are EXP-0168's; `mov_imm`,
`falu2i_raw`, `device_store`, `store_word` and `stop` are the same wrappers.

WHAT IS DIFFERENT HERE, AND WHY EACH DIFFERENCE EXISTS
------------------------------------------------------
1. **NO `device_load` ANYWHERE.** DEF-0169-1 (EXP-0169): `device_load` on G17P is
   ASYNCHRONOUS; with no wait a program landed 0,0,0,0,2,5,8,8 of 8 seed
   registers depending only on filler length. Every register in this experiment
   is seeded with `mov_imm` / `falu2i` immediates.

2. **The read-back index register is a PARAMETER, and the experiment runs two
   variants.** EXP-0168 fixed `R_IDX = 15` and `store_word()` emits
   `mov_imm(R_IDX, 0)` immediately before EVERY store — including the store that
   reads `data_reg = 15`. In that program r15 is zeroed one instruction before it
   is read, so r15 MUST read 0 whether or not it is writable. EXP-0168 reported
   that as the hardware fact "a write whose 4-bit destination nibble is 15 is
   discarded". Here `R_IDX` is a parameter: variant `idx15` is blind at slot 15,
   variant `idx7` is blind at slot 7, and the union of the two observes all 16.
   The two variants are also this experiment's two carriers, differing exactly in
   the dimension `dst` controls (the register plan), per FIELD-SWEEP-PROTOCOL.

3. **`extmode` is a parameter.** `db.json` records the ALU-forwarded store data
   source as `extmode = 2*R` **or** `2*R|0xC0`. EXP-0168 used `2*R`, which is
   `0x00` for `data_reg = 0`, and its committed baseline shows slot 0 reading 0
   against a seed of 10. Calibration measures both encodings before anything is
   frozen.

4. **Self-restoring pads after the instruction under test.** An unknown byte+2 /
   byte+3 combination may select a LONGER instruction (`reg_move_cb` byte+2
   0x0f/0x26 does exactly that, EXP-0168 §2). Padding with
   `mov_imm(R_PAD, SEED_I[R_PAD])` — a write of a register's OWN seed — absorbs
   an over-consumption of up to `PAD_BYTES` while being a no-op with respect to
   the register dump. The pad register is a parameter and differs between the
   two variants, so no single slot is masked in both.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def _find_isadb():
    """The agx-isa snapshot this experiment is PINNED to.

    `work/frozen/` holds the EXACT `db.json` / `isadb.py` the hardware ran
    against, sha256-checked in CAPTURE_CONTRACT.json.

    FAIL-CLOSED. The dispatch is explicit: a harness must FAIL when its pinned
    toolchain is absent, not quietly resolve something else. The neo's SHARED
    `~/agxre/tools/agx-isa/db.json` is STALE (1036 fields vs this repo's 1062;
    `falu2.srcA_class`/`srcB_class` there were replaced by `mod_lo` here), and a
    path-search fallback silently resolved it for another experiment on
    2026-08-30. So there is exactly ONE candidate directory and no fallback.
    """
    cand = EXP / "work" / "frozen"
    if (cand / "isadb.py").exists() and (cand / "db.json").exists():
        return cand
    raise RuntimeError(
        "PINNED TOOLCHAIN MISSING: %s must contain isadb.py and db.json. "
        "Run `harness/sync.sh pin` (repo host) / `harness/pin_check.py` (neo). "
        "There is deliberately NO path-search fallback -- see _find_isadb()."
        % cand)


ISA_DIR = _find_isadb()
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

N_REGS = 16
POISON = 0xDEADBEEF
SENT_PRE = 0x5A            # written to MEMORY before the tested block
SENT_POST = 111            # mov_imm-able POST sentinel (< 128)
PAD_BYTES = 8              # self-restoring padding after the block under test

# Distinct, NON-ZERO integer seeds, all inside mov_imm's HW-VALIDATED 0..127
# range (EXP-0128: imm >= 128 does not write the register at all; imm7 == 12
# does not tokenize under the current length rule, so 12 is avoided).
# Every value is distinct, so "which register did this value come from?" is
# uniquely decodable -- that IS the oracle for a move.
# No seed is 0: EXP-0168 defect #1 -- a zero seed cannot be told from "the
# instruction wrote zero" or from "the instruction did nothing".
SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 121}
assert len(set(SEED_I.values())) == N_REGS
assert 0 not in SEED_I.values()
assert 12 not in SEED_I.values()

# Output word layout (32-bit words). `device_store` idx_off unit is 4 WORDS
# (16 bytes) — db.json device_store semantics, EXP-0082/EXP-0090/EXP-0119.
STORE_STRIDE_WORDS = 4
W_REG0 = 0                                   # r0..r15 -> words 0,4,...,60
W_PRE = N_REGS * STORE_STRIDE_WORDS          # 64
W_POST = W_PRE + STORE_STRIDE_WORDS          # 68
W_SPARE = W_POST + STORE_STRIDE_WORDS        # 72 (unused, kept for layout parity)
W_TAIL = W_SPARE + STORE_STRIDE_WORDS        # 76 first word NEVER stored to
N_TAIL_WORDS = 28
OUT_WORDS = W_TAIL + N_TAIL_WORDS            # 104 words read back


class Plan(object):
    """A register plan = one CARRIER. `idx` is destroyed by the read-back path
    and is therefore the ONE slot this variant cannot observe; `pad` is the
    register the post-block padding rewrites with its own seed, so a write the
    instruction under test makes to `pad` could be masked. The two frozen
    variants choose disjoint (idx, pad) pairs so no slot is blind in both."""

    def __init__(self, name, idx, sent, pre, pad, extmode_or=0x00):
        self.name = name
        self.idx = idx
        self.sent = sent
        self.pre = pre
        self.pad = pad
        self.extmode_or = extmode_or
        if len({idx, sent, pre}) != 3:
            raise ValueError("idx/sent/pre must be distinct")

    @property
    def blind(self):
        return {self.idx}

    @property
    def masked(self):
        return {self.pad}

    def as_dict(self):
        return {"name": self.name, "idx": self.idx, "sent": self.sent,
                "pre": self.pre, "pad": self.pad,
                "extmode_or": self.extmode_or,
                "blind_slots": sorted(self.blind),
                "pad_masked_slots": sorted(self.masked)}


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", f32(x)))[0]


# --------------------------------------------------------------------------
# Scaffolding instructions, all assembled by tools/agx-isa itself.
# --------------------------------------------------------------------------
def mov_imm(dst, imm8):
    if not (0 <= imm8 <= 127):
        raise ValueError("mov_imm imm8 must be 0..127 (EXP-0128/EXP-0140)")
    if imm8 == 12:
        raise ValueError("mov_imm imm7 == 12 does not tokenize (EXP-0140)")
    return isadb.assemble("mov_imm", {"dst": dst, "imm7": imm8 & 0x7F,
                                      "imm_top": 0})


def falu2i_raw(dst, srcA_reg7, k, opflags4=0, ctrl_lo=0, mods=0xC0,
               srcA_size=1, imm_flag=None, opsel=4):
    """6B falu2i (float op with a packed minifloat immediate). `mods=0xC0` is
    EXP-0101's HW-VALIDATED requirement. Reused verbatim from EXP-0168."""
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


def device_store(index_reg, idx_off, data_reg, base_slot=0, extmode_or=0x00):
    """14B device_store, ALU-forwarded form.

    `extmode` names the data source. db.json: `extmode = 2*R` **or**
    `2*R|0xC0`, "proven over three registers" (EXP-0090/0101/0141). `extmode_or`
    selects which of the two this program uses; it is a calibrated parameter
    here because `2*R` is `0x00` for R == 0 and EXP-0168's committed baseline
    shows slot 0 reading 0 against a non-zero seed."""
    return isadb.assemble("device_store", {
        "space": 0, "addr_mode": 0x54,
        "extmode": ((data_reg << 1) | extmode_or) & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": 0x21, "reserved7": 0,
        "st_format": 0x11, "st_format_ext": 0,
        "idx_off": (idx_off) & 0x7FF, "st_desc_hi": 0x24,
        "elem_size": 0x11, "reserved13": 0,
    })


def store_word(plan, word_idx, data_reg):
    """Store r[data_reg] at absolute output WORD index `word_idx`.

    The index register is re-zeroed immediately before every store so that a
    write the block under test made to it cannot relocate the dump. The price is
    that r[plan.idx] itself is destroyed by this path, which is why there are two
    variants with different `idx`."""
    if word_idx % STORE_STRIDE_WORDS:
        raise ValueError("word_idx must be a multiple of %d" % STORE_STRIDE_WORDS)
    return (mov_imm(plan.idx, 0)
            + device_store(plan.idx, word_idx // STORE_STRIDE_WORDS, data_reg,
                           extmode_or=plan.extmode_or))


def stop(reserved=0):
    return isadb.assemble("stop", {"reserved": reserved & 0xFFFFFF})


def nop_pad(plan):
    """A write of a register's OWN seed: a genuine no-op with respect to the
    register dump, unlike `mov_imm(R, 0)`."""
    return mov_imm(plan.pad, SEED_I[plan.pad])


def build_program(plan, instrs, carrier_len):
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d exceeds carrier %d"
                         % (len(body), carrier_len))
    rem = carrier_len - len(body)
    if rem % 2:
        raise ValueError("odd padding remainder %d" % rem)
    out = body + nop_pad(plan) * (rem // 2)
    assert len(out) == carrier_len
    return out


# --------------------------------------------------------------------------
# THE INSTRUCTION UNDER TEST — built from the descriptor's own geometry.
# --------------------------------------------------------------------------
def n3_bytes(dst, srcA_reg, srcA_uni, subform, companion):
    """The four bytes of a low-nibble-3 compact instruction.

    Built by placing each value at the bit position `db.json` declares for it
    (`dst` @4 w4, `srcA_reg` @8 w7, `srcA_uni` @15 w1, `subform` @16 w8,
    `companion` @24 w8) over the descriptor's own `match` (byte0 low nibble == 3).
    NOTHING is copied from a compiled shader. `isadb.assemble` is used where the
    resulting bytes are inside a declared descriptor and is cross-checked against
    this construction by `assert_geometry()`."""
    if not (0 <= dst <= 15 and 0 <= srcA_reg <= 127 and 0 <= srcA_uni <= 1
            and 0 <= subform <= 255 and 0 <= companion <= 255):
        raise ValueError("n3 field out of range")
    return bytes([(dst << 4) | 0x3,
                  (srcA_uni << 7) | srcA_reg,
                  subform, companion])


def assert_geometry():
    """Cross-check `n3_bytes` against `isadb.assemble` on the declared
    descriptor, so the hand-placed geometry cannot silently disagree with
    db.json. Only checked where the value set stays inside `n3_mov`'s match
    (byte+3 low 3 bits != 1 keeps it out of the `mov_zext16` split-out)."""
    for dst in (0, 5, 15):
        for src in (0, 1, 64, 127):
            for uni in (0, 1):
                for sub in (0, 0x20, 0xFF):
                    for comp in (0x00, 0x02, 0xFE):
                        want = isadb.assemble("n3_mov", {
                            "dst": dst, "srcA_reg": src, "srcA_uni": uni,
                            "subform": sub, "companion": comp})
                        got = n3_bytes(dst, src, uni, sub, comp)
                        if want != got:
                            raise AssertionError(
                                "geometry mismatch %s != %s" % (want.hex(), got.hex()))
    return True


def round_trips(buf):
    """True iff `buf` re-tokenizes exactly. Recorded as a property of the case
    (`rt_ok`), NEVER as a gate: FIELD-SWEEP-PROTOCOL 3(b) — a round trip is not
    an emitter gate, and EXP-0170 proved the repo's own suite passes against an
    assembler that cannot clear a bit."""
    try:
        recs, leftover = isadb.disassemble(buf)
        if leftover:
            return False
        off = 0
        for r in recs:
            if isadb.assemble(r["mnemonic"], r["fields"]) != buf[off:off + r["length"]]:
                return False
            off += r["length"]
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# The synthesized program.
# --------------------------------------------------------------------------
def seed_instrs(plan, wide=None):
    """Seed r0..r15 with the distinct integer table. `wide`, if given, is
    (reg, float_k): that register is then overwritten with the exact IEEE-754
    bit pattern of `float_k` via falu2i, giving one source whose value has bits
    ABOVE bit 15 set — so a 16-bit copy and a 32-bit copy are distinguishable."""
    out = [mov_imm(r, SEED_I[r]) for r in range(N_REGS)]
    if wide is not None:
        wreg, wk = wide
        # r14's seed (3) is a denormal, so denormal + k == k exactly, with or
        # without flush-to-zero. The result is host-computable with no GPU input.
        out.append(falu2i_raw(wreg, 14, wk))
    return out


def seed_state(plan, wide=None):
    """The host-known register table the program installs before the block.
    The GPU-independent half of every oracle."""
    st = [SEED_I[r] for r in range(N_REGS)]
    if wide is not None:
        wreg, wk = wide
        st[wreg] = f32_bits(wk)
    return st


def pre_sentinel_instrs(plan):
    """Write SENT_PRE to MEMORY before the tested block, then restore the
    scratch register's seed so the block sees an intact seed table."""
    return [mov_imm(plan.pre, SENT_PRE),
            store_word(plan, W_PRE, plan.pre),
            mov_imm(plan.pre, SEED_I[plan.pre])]


def dump_instrs(plan):
    """Store every register, then the POST sentinel.

    The POST sentinel is materialized AFTER the block by `mov_imm`, a path the
    instruction under test cannot influence, which is FIELD-SWEEP-PROTOCOL 7.2's
    "integrity sentinel written through an independent path". r[plan.sent] is
    stored BEFORE it is overwritten, so its own dumped value is still true."""
    out = [store_word(plan, W_REG0 + r * STORE_STRIDE_WORDS, r)
           for r in range(N_REGS)]
    out.append(mov_imm(plan.sent, SENT_POST))
    out.append(store_word(plan, W_POST, plan.sent))
    return out


def synth_program(plan, block_bytes, carrier_len, wide=None, pre_block=b"",
                  n_pads=None):
    """seeds -> PRE sentinel -> [pre_block] -> [BLOCK UNDER TEST] -> pads ->
    16-register dump -> POST sentinel -> stop."""
    if n_pads is None:
        n_pads = PAD_BYTES // 2
    instrs = seed_instrs(plan, wide)
    instrs += pre_sentinel_instrs(plan)
    if pre_block:
        instrs.append(pre_block)
    instrs.append(block_bytes)
    instrs += [nop_pad(plan)] * n_pads
    instrs += dump_instrs(plan)
    instrs.append(stop())
    return build_program(plan, instrs, carrier_len)


PLANS = {
    # Blind at slot 15, pad-masked at slot 13.
    "idx15": Plan("idx15", idx=15, sent=12, pre=11, pad=13),
    # Blind at slot 7, pad-masked at slot 6.  Disjoint from idx15 in BOTH.
    "idx7":  Plan("idx7",  idx=7,  sent=12, pre=11, pad=6),
}
