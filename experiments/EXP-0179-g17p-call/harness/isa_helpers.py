#!/usr/bin/env python3
"""EXP-0179 program construction -- the CALL / RETURN question.

Every instruction in every program built here -- the seeds, the sentinels, the
read-back, the ladder, the callee, the `call` itself and the `ret` itself -- is
assembled through the PINNED `tools/agx-isa` snapshot's own
`isadb.assemble(mnemonic, fields)`, i.e. from the bit geometry `db.json`
declares. **No byte of any of them is copied out of a compiled shader.** That is
the form the acceptance gate asks for and the form EXP-0174 used to close the
`nir_op_mov` blocker.

LINEAGE (our own code, this repository, cited per CODEX.md):
  EXP-0154/harness/isa_helpers.py -> EXP-0161 -> EXP-0168 -> EXP-0174 -> HERE.
The seed table, the PRE/POST sentinel construction, the poisoned read-back, the
tail-poison region, `build_program`, `mov_imm`, `falu2i_raw`, `device_store`,
`store_word`, `stop` and the Plan/blind/pad-masked bookkeeping are EXP-0174's,
unchanged in spirit.

WHAT IS NEW HERE, AND WHY
-------------------------
1. **A CALL FRAME LAYOUT.** `synth_call_program()` lays out
   `seeds | PRE | [if_push] | CALL | [pop] | POST-MARK | dump | stop | gap |
    LADDER | CALLEE | ret | stop | pad`
   and COMPUTES the call displacement from the layout, so the offset is derived
   rather than copied. Everything after the first `stop` is unreachable by
   fall-through and is entered ONLY by the call.

2. **A LANDING LADDER.** Four 2-byte `mov_imm` rungs immediately before the
   callee, each writing a distinct non-seed value to a distinct register. Control
   entering at rung j executes rungs j..3, so the LOWEST rung that fired
   localises the branch target to 2 bytes over an 8-byte window. This turns a
   mis-targeted call from a hazard into a measurement, which is what makes the
   offset ladder (arm T) safe to run.

3. **A MEMORY BREADCRUMB INSIDE THE CALLEE.** The callee stores its own constant
   to `W_CALLEE` in the poisoned output buffer BEFORE it returns, so "the callee
   ran but never came back" is distinguishable from "the call never happened"
   even when the caller-side dump never executes.

4. **RULE 3(a) IS STRUCTURAL, NOT CAREFUL.** Neither `call` nor `ret` declares a
   single register-typed field, so no swept value can name the read-back index
   register, any store's data register, the sentinel registers, or the callee
   register. The observable CANNOT co-vary with the field under test.

5. **NO `device_load` ON ANY VERDICT PATH.** DEF-0169-1: `device_load` on G17P is
   ASYNCHRONOUS and fabricates movement. It appears in exactly one arm (`O/order`)
   where its asynchrony is deliberately the instrument, behind a pre-declined
   promotion condition.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def _find_isadb():
    """The agx-isa snapshot this experiment is PINNED to.

    FAIL-CLOSED, exactly one candidate, NO path-search fallback. The neo's
    SHARED `~/agxre/tools/agx-isa/db.json` is stale and a path-search fallback
    silently resolved it for another experiment on 2026-08-30.
    """
    cand = EXP / "work" / "frozen"
    if (cand / "isadb.py").exists() and (cand / "db.json").exists():
        return cand
    raise RuntimeError(
        "PINNED TOOLCHAIN MISSING: %s must contain isadb.py and db.json. "
        "There is deliberately NO path-search fallback -- see _find_isadb()." % cand)


ISA_DIR = _find_isadb()
sys.path.insert(0, str(ISA_DIR))
import isadb  # noqa: E402  (read-only use)

N_REGS = 16
POISON = 0xDEADBEEF
SENT_PRE = 0x5A            # written to MEMORY before the call
SENT_POST = 111            # mov_imm-able POST sentinel (< 128)
CALLEE_CONST = 15          # what the callee writes into R_CALLEE
POSTCALL = 17              # what the caller writes AFTER the call returns
LADDER_V = (5, 7, 9, 11)   # the four landing-ladder rung values
LADDER_R = (0, 1, 2, 3)    # the registers they are written to
INNER_CONST = 20           # arm N: what the DEPTH-2 callee writes into R_INNER
INNER_POST = 22            # arm N: written by callee1 AFTER the inner call returns
R_INNER = 4                # not blind or pad-masked in either plan
R_INNER_POST = 5
R_LOAD = 8                 # arm O only: the device_load destination
SLOT_OUT, SLOT_MEM, SLOT_IMEM = 0, 1, 2   # base_slot == the Metal buffer index
PAD_BYTES = 0              # the call carrier does its own layout; no blanket pad

# Seed table: distinct, NON-ZERO, inside mov_imm's HW-VALIDATED 0..127 range
# (EXP-0128: imm >= 128 does not write the register at all; imm7 == 12 does not
# tokenize under the current length rule). Reused verbatim from EXP-0174.
SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 121}
assert len(set(SEED_I.values())) == N_REGS
assert 0 not in SEED_I.values() and 12 not in SEED_I.values()
# every marker value must be distinguishable from every seed and from each other
_MARKERS = set(LADDER_V) | {CALLEE_CONST, POSTCALL, SENT_POST,
            INNER_CONST, INNER_POST}
assert len(_MARKERS) == 9
assert not (_MARKERS & set(SEED_I.values()))
assert 12 not in _MARKERS and all(0 < v < 128 for v in _MARKERS)

# Output word layout (32-bit words). `device_store` idx_off unit is 4 WORDS
# (16 bytes) -- db.json device_store semantics, EXP-0082/EXP-0090/EXP-0119.
STORE_STRIDE_WORDS = 4
W_REG0 = 0                                   # r0..r15 -> words 0,4,...,60
W_PRE = N_REGS * STORE_STRIDE_WORDS          # 64
W_POST = W_PRE + STORE_STRIDE_WORDS          # 68
W_CALLEE = W_POST + STORE_STRIDE_WORDS       # 72  <- the callee's own breadcrumb
W_TAIL = W_CALLEE + STORE_STRIDE_WORDS       # 76  first word NEVER stored to
N_TAIL_WORDS = 28
OUT_WORDS = W_TAIL + N_TAIL_WORDS            # 104 words read back


class Plan(object):
    """A register plan. `idx` is destroyed by the read-back path and is the ONE
    slot this plan cannot observe; `pad` is rewritten by the trailing padding.
    The two frozen plans choose disjoint (idx, pad) pairs, so every one of the 16
    slots is genuinely observed in at least one carrier."""

    def __init__(self, name, idx, sent, pre, pad, callee=10, post=9,
                 extmode_or=0x00):
        self.name = name
        self.idx = idx
        self.sent = sent
        self.pre = pre
        self.pad = pad
        self.callee = callee
        self.post = post
        self.extmode_or = extmode_or
        roles = [idx, sent, pre, callee, post]
        if len(set(roles)) != len(roles):
            raise ValueError("idx/sent/pre/callee/post must be distinct")
        if callee in (idx, pad) or post in (idx, pad):
            raise ValueError("callee/post must not be blind or pad-masked")
        if set(LADDER_R) & {idx, pad, callee, post, sent, pre}:
            raise ValueError("ladder registers collide with a role register")

    @property
    def blind(self):
        return {self.idx}

    @property
    def masked(self):
        return {self.pad}

    def as_dict(self):
        return {"name": self.name, "idx": self.idx, "sent": self.sent,
                "pre": self.pre, "pad": self.pad, "callee": self.callee,
                "post": self.post, "extmode_or": self.extmode_or,
                "blind_slots": sorted(self.blind),
                "pad_masked_slots": sorted(self.masked)}


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", f32(x)))[0]


# --------------------------------------------------------------------------
# Scaffolding instructions, all assembled by the PINNED tools/agx-isa itself.
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
    """14B device_store, ALU-forwarded form. `extmode_or` selects between the two
    encodings db.json declares (`2*R` or `2*R|0xC0`); it is CALIBRATED."""
    return isadb.assemble("device_store", {
        "space": 0, "addr_mode": 0x54,
        "extmode": ((data_reg << 1) | extmode_or) & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": 0x21, "reserved7": 0,
        "st_format": 0x11, "st_format_ext": 0,
        "idx_off": idx_off & 0x7FF, "st_desc_hi": 0x24,
        "elem_size": 0x11, "reserved13": 0,
    })


def store_word(plan, word_idx, data_reg):
    """Store r[data_reg] at absolute output WORD index `word_idx` (16 bytes).

    The index register is re-zeroed immediately before every store so that a
    write the block under test made to it cannot relocate the dump. The price is
    that r[plan.idx] is destroyed by this path, which is why there are two plans.
    """
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


# --------------------------------------------------------------------------
# THE INSTRUCTIONS UNDER TEST -- generated, never copied.
# --------------------------------------------------------------------------
CALL_LEN = 14
RET_LEN = 4
OFF_WIDTH = 48                      # db.json: call.offset start=56 width=48


def call_bytes(offset, b3=0x1a, b5=0x00, b6=0x56, tail=0x00):
    """The 14 bytes of a direct CALL, assembled from the descriptor.

    `offset` is the SIGNED byte displacement; it is encoded here as
    two's complement over the field's declared 48-bit width. The DEFAULTS for
    b3/b5/b6/tail are the values the corpus shows -- they are the BASELINE of the
    sweeps, and every arm that is not sweeping a given field holds it at its
    baseline. Nothing is copied: the bytes are produced by isadb.assemble from
    db.json's own field geometry.
    """
    off = offset & ((1 << OFF_WIDTH) - 1)
    b = isadb.assemble("call", {"b3": b3 & 0xFF, "b5": b5 & 0xFF,
                                "b6": b6 & 0xFF, "offset": off,
                                "tail": tail & 0xFF})
    if len(b) != CALL_LEN:
        raise AssertionError("call length %d != %d" % (len(b), CALL_LEN))
    return b


def ret_bytes(linkmode=0x02, scoreboard=0x00):
    b = isadb.assemble("ret", {"linkmode": linkmode & 0xFF,
                               "scoreboard": scoreboard & 0xFF})
    if len(b) != RET_LEN:
        raise AssertionError("ret length %d != %d" % (len(b), RET_LEN))
    return b


def frame_marker_bytes():
    """`43 00 00 01` -- the 4-byte call-site / frame-setup marker the compiler
    emits before every out-of-line call (EXP-0035 byte-observation). Whether it
    is REQUIRED is a hypothesis this experiment tests (arm M), not an assumption.
    """
    return isadb.assemble("frame_marker",
                          {"srcA_reg": 0x00, "subform": 0x00, "companion": 0x01})


def if_push_bytes(scope=0x54, scope_kind=0x01):
    return isadb.assemble("if_push", {"scope": scope, "scope_kind": scope_kind})


def pop_reconverge_bytes(scope=0x04, scope_kind=0x02, reserved=0x0000):
    return isadb.assemble("pop_reconverge", {"scope": scope,
                                             "scope_kind": scope_kind,
                                             "reserved": reserved})


def jump_bytes(offset, branch_ctrl=0x54, link=0x00):
    off = offset & ((1 << 48) - 1)
    return isadb.assemble("jump", {"branch_ctrl": branch_ctrl, "offset": off,
                                   "link": link})


def assert_geometry():
    """Cross-check that every generated instruction re-decodes to the fields it
    was built from, on the PINNED descriptor. This checks the CONSTRUCTION, not
    the hardware; it is never cited as evidence that an encoding can be emitted
    (FIELD-SWEEP-PROTOCOL 3b). `rt_ok` per case is likewise recorded and unused.
    """
    checks = []
    for off in (0, 4, 100, -104, -552, 65536, -65536):
        for (b3, b5, b6, tl) in ((0x1a, 0x00, 0x56, 0x00),
                                 (0x00, 0xFF, 0x54, 0xFF),
                                 (0xFF, 0x7F, 0x00, 0x80)):
            b = call_bytes(off, b3, b5, b6, tl)
            recs, left = isadb.disassemble(b)
            if left or len(recs) != 1 or recs[0]["mnemonic"] != "call":
                raise AssertionError("call %d/%02x did not re-decode: %s"
                                     % (off, b3, b.hex()))
            f = recs[0]["fields"]
            got = f["offset"]
            if got >= (1 << (OFF_WIDTH - 1)):
                got -= (1 << OFF_WIDTH)
            if got != off or f["b3"] != b3 or f["b5"] != b5 or f["b6"] != b6 \
               or f["tail"] != tl:
                raise AssertionError("call field mismatch %s" % b.hex())
            checks.append(b.hex())
    for lm in (0x02, 0x04, 0x05, 0x12):
        for sb in (0x00, 0x22, 0xFF):
            b = ret_bytes(lm, sb)
            recs, left = isadb.disassemble(b)
            if left or recs[0]["mnemonic"] not in ("ret",):
                raise AssertionError("ret did not re-decode: %s" % b.hex())
    if len(frame_marker_bytes()) != 4:
        raise AssertionError("frame_marker length")
    if len(if_push_bytes()) != 4 or len(pop_reconverge_bytes()) != 6:
        raise AssertionError("if_push/pop_reconverge length")
    if len(jump_bytes(0)) != 10:
        raise AssertionError("jump length")
    return len(checks)


def round_trips(buf):
    """True iff `buf` re-tokenizes exactly. Recorded as a per-case property
    (`rt_ok`), NEVER as a gate: FIELD-SWEEP-PROTOCOL 3(b)."""
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
# The synthesized CALL program.
# --------------------------------------------------------------------------
def seed_instrs(plan):
    """Seed r0..r15 with the distinct integer table. mov_imm ONLY -- no
    device_load anywhere (DEF-0169-1)."""
    return [mov_imm(r, SEED_I[r]) for r in range(N_REGS)]


def seed_state():
    """The HOST-KNOWN register table the program installs. The GPU-independent
    half of every oracle in this experiment."""
    return [SEED_I[r] for r in range(N_REGS)]


def pre_sentinel_instrs(plan):
    return [mov_imm(plan.pre, SENT_PRE),
            store_word(plan, W_PRE, plan.pre),
            mov_imm(plan.pre, SEED_I[plan.pre])]


def dump_instrs(plan):
    """The FIXED read-back: 16 register stores in a fixed order, then the POST
    sentinel through an independent path. Byte-identical in every case of every
    arm -- no store operand is a function of any swept value."""
    out = [store_word(plan, W_REG0 + r * STORE_STRIDE_WORDS, r)
           for r in range(N_REGS)]
    out.append(mov_imm(plan.sent, SENT_POST))
    out.append(store_word(plan, W_POST, plan.sent))
    return out


def ladder_instrs():
    return [mov_imm(LADDER_R[j], LADDER_V[j]) for j in range(len(LADDER_R))]


def callee_instrs(plan, extra_regs=()):
    """The GENERATED callee body, WITHOUT its `ret` (the caller supplies that so
    the `ret` bytes can be swept).

    Returns (instrs, ret_rel_off): `ret_rel_off` is the byte offset of the `ret`
    relative to the callee entry, so arm F5 can target the bare `ret`.
    """
    out = [mov_imm(plan.callee, CALLEE_CONST),
           store_word(plan, W_CALLEE, plan.callee)]
    for (r, v) in extra_regs:
        out.append(mov_imm(r, v))
    return out, sum(len(x) for x in out)


def synth_call_program(plan, carrier_len,
                       call_b3=0x1a, call_b5=0x00, call_b6=0x56, call_tail=0x00,
                       ret_linkmode=0x02, ret_scoreboard=0x00,
                       nested=False, marker=False, reconverge=False,
                       gap=0, offset_delta=0, target="callee",
                       callee_extra=(), replace_call=None, replace_ret=None,
                       corrupt_call_byte=None, pre_call_extra=b"",
                       post_call_extra=b"",
                       depth2=False, depth2_marker=False, depth2_link=False,
                       depth2_pop=True,
                       order_load=False, order_filler=0,
                       nested_scope=0x56, nested_kind=0x1a):
    """Build the whole `_agc.main`.

    Layout:
        seeds | PRE | [marker] | [if_push] | CALL | [pop] | POSTMARK
              | dump | POST | stop | gap | LADDER | CALLEE | ret | stop | pad
                                                     ^-- entered ONLY by the call

    The displacement is COMPUTED from the layout:
        offset = CALLEE_AT - (CALL_AT + 4)
    and `offset_delta` perturbs it (arm T). `target` selects which address the
    call aims at: "callee" (the callee entry), "ret" (the bare `ret`, arm F5),
    or "ladder" (the first ladder rung).

    Returns (program_bytes, layout_dict).
    """
    prefix = seed_instrs(plan) + pre_sentinel_instrs(plan)
    if marker:
        prefix.append(frame_marker_bytes())
    if nested:
        # AMENDMENT-01 (2026-08-30, on measured evidence -- see PRE_REGISTRATION
        # section 13). The frozen C2 used if_push(scope=0x54, scope_kind=0x01) and
        # run01 measured that carrier DEAD: the PRE sentinel wrote and nothing
        # after it did, in every case. `raw/prefreeze/calib_20260830c_amend`
        # isolates it -- scope_kind 0x01 masks off the only lane of a one-thread
        # dispatch (both banks), while scope_kind 0x1a (the same value `call`
        # itself carries at byte+3) does not, in both banks. C2 is therefore
        # if_push(0x56, 0x1a): one mask level deeper, in the ALTERNATE bank to the
        # 0x54 the call pins, and alive.
        prefix.append(if_push_bytes(nested_scope, nested_kind))
    if pre_call_extra:
        prefix.append(pre_call_extra)
    P = sum(len(x) for x in prefix)

    suffix = []
    if nested and reconverge:
        suffix.append(pop_reconverge_bytes())
    elif reconverge:
        suffix.append(pop_reconverge_bytes())
    if post_call_extra:
        suffix.append(post_call_extra)
    suffix.append(mov_imm(plan.post, POSTCALL))
    suffix += dump_instrs(plan)
    suffix.append(stop())
    S = sum(len(x) for x in suffix)

    if gap % 2:
        raise ValueError("gap must be even")
    ladder = ladder_instrs()
    LAD = sum(len(x) for x in ladder)

    call_len = CALL_LEN if replace_call is None else len(replace_call)
    CALL_AT = P
    LADDER_AT = P + call_len + S + gap
    CALLEE_AT = LADDER_AT + LAD

    body, ret_rel = callee_instrs(plan, callee_extra)
    if order_load:
        # arm O ONLY: the callee issues an ASYNCHRONOUS device_load and then
        # `order_filler` 2-byte no-ops before returning. DEF-0169-1 makes the
        # filler length the instrument.
        body = body + [load_reg(plan, R_LOAD, 0)] \
                    + [nop_pad(plan)] * order_filler
        ret_rel = sum(len(x) for x in body)

    inner = []
    inner_layout = {}
    if depth2:
        # callee1 makes a further GENERATED call, with NO frame_prologue and NO
        # link_save_restore, to test whether the return address is a hardware
        # STACK or a single link register (H7). Hang-prone by construction.
        pre_inner = list(body)
        if depth2_marker:
            pre_inner.append(frame_marker_bytes())
        if depth2_link:
            pre_inner.append(isadb.assemble("link_save_restore",
                                            {"b3": 0x00, "dir_offset": 0x0000,
                                             "reserved7": 0x00}))
        CALL2_AT = CALLEE_AT + sum(len(x) for x in pre_inner)
        post_inner = []
        # AMENDMENT-02 (2026-08-30, on measured evidence). The FIRST arm-N pass
        # (`raw/MAPPING_g17p_20260830_run05N_hangtolerant`, retained) faulted on
        # all 6 cases in both runs -- and that was MY BUG, not a hardware fact
        # about nesting: this construction omitted the `pop_reconverge` after the
        # INNER call, and arm M had already MEASURED that a call without a
        # following pop faults. Arm M's own result predicted the failure. The
        # inner call now gets the same closing pop the outer one has, so arm N
        # tests the link-register question it was written to test instead of
        # re-measuring arm M.
        if depth2_pop:
            post_inner.append(pop_reconverge_bytes())
        if depth2_link:
            post_inner.append(isadb.assemble("link_save_restore",
                                             {"b3": 0x00, "dir_offset": 0x1FFF,
                                              "reserved7": 0x00}))
        post_inner.append(mov_imm(R_INNER_POST, INNER_POST))
        RET_AT = CALL2_AT + CALL_LEN + sum(len(x) for x in post_inner)
        CALLEE2_AT = RET_AT + RET_LEN + 4          # after ret1 and its stop
        off2 = CALLEE2_AT - (CALL2_AT + 4)
        call2 = call_bytes(off2, call_b3, call_b5, call_b6, call_tail)
        body = pre_inner + [call2] + post_inner
        inner = [mov_imm(R_INNER, INNER_CONST),
                 ret_bytes(ret_linkmode, ret_scoreboard), stop()]
        inner_layout = {"CALL2_AT": CALL2_AT, "CALLEE2_AT": CALLEE2_AT,
                        "offset2": off2, "call2_hex": call2.hex(),
                        "depth2_pop": depth2_pop}
    else:
        RET_AT = CALLEE_AT + ret_rel

    tgt = {"callee": CALLEE_AT, "ret": RET_AT, "ladder": LADDER_AT}[target]
    offset = tgt - (CALL_AT + 4) + offset_delta

    if replace_call is not None:
        call_blob = replace_call
    else:
        call_blob = call_bytes(offset, call_b3, call_b5, call_b6, call_tail)
        if corrupt_call_byte is not None:
            i, v = corrupt_call_byte
            ba = bytearray(call_blob)
            ba[i] = v
            call_blob = bytes(ba)

    ret_blob = (ret_bytes(ret_linkmode, ret_scoreboard)
                if replace_ret is None else replace_ret)

    instrs = list(prefix) + [call_blob] + list(suffix)
    instrs += [nop_pad(plan)] * (gap // 2)
    instrs += ladder
    instrs += body + [ret_blob, stop()] + inner

    used = sum(len(x) for x in instrs)
    if used > carrier_len:
        raise ValueError("program %d exceeds carrier region %d" % (used, carrier_len))
    rem = carrier_len - used
    if rem % 2:
        raise ValueError("odd padding remainder %d (carrier_len=%d)" % (rem, carrier_len))
    prog = b"".join(instrs) + nop_pad(plan) * (rem // 2)
    assert len(prog) == carrier_len

    layout = {"CALL_AT": CALL_AT, "LADDER_AT": LADDER_AT, "CALLEE_AT": CALLEE_AT,
              "RET_AT": RET_AT, "STOP_AT": P + call_len + S - 4,
              "offset": offset, "target": target, "gap": gap,
              "offset_delta": offset_delta, "used": used, "pad_bytes": rem,
              "call_hex": call_blob.hex(), "ret_hex": ret_blob.hex(),
              "nested": nested, "marker": marker, "reconverge": reconverge,
              "depth2": depth2, "order_load": order_load,
              "order_filler": order_filler}
    layout.update(inner_layout)
    return prog, layout


# --------------------------------------------------------------------------
# The HOST-COMPUTED oracle. No GPU measurement enters this.
# --------------------------------------------------------------------------
def expected_dump(plan, called=True, returned=True, rungs_from=None,
                  callee_extra=()):
    """The 16-register dump predicted on the HOST for a program in which the call
    behaved as `called`/`returned` and control entered the ladder at rung
    `rungs_from` (None = landed at or after the callee entry).

    NOTE the read-back path itself zeroes r[plan.idx] before every store, so slot
    `plan.idx` reads 0 by construction and is excluded from every verdict; the
    trailing padding rewrites r[plan.pad] with its own seed, so that slot is
    masked. Both are reported per case, never silently dropped.
    """
    st = seed_state()
    if called:
        if rungs_from is not None:
            for j in range(rungs_from, len(LADDER_R)):
                st[LADDER_R[j]] = LADDER_V[j]
        st[plan.callee] = CALLEE_CONST
        for (r, v) in callee_extra:
            st[r] = v
    if returned:
        st[plan.post] = POSTCALL
    st[plan.idx] = 0                     # destroyed by the read-back path
    st[plan.sent] = SEED_I[plan.sent]    # stored before it is overwritten
    return st


PLANS = {
    # blind at slot 15, pad-masked at slot 13
    "idx15": Plan("idx15", idx=15, sent=12, pre=11, pad=13),
    # blind at slot 7, pad-masked at slot 6 -- disjoint from idx15 in BOTH
    "idx7":  Plan("idx7",  idx=7,  sent=12, pre=11, pad=6),
}


# --------------------------------------------------------------------------
# arm O ONLY -- device_load. DEF-0169-1: `device_load` on G17P is ASYNCHRONOUS.
# It is FORBIDDEN on every verdict path in this experiment; arm `O/order` is the
# single exception, where that asynchrony IS the instrument. Recipe reused
# verbatim from EXP-0141 -> EXP-0169/harness/isa_helpers.device_load (our own
# code, this repository); defaults are the compiler-observed terminal
# scalar-32-bit shape EXP-0101 validated end to end, `extmode = 2*R` selecting
# the destination register R.
# --------------------------------------------------------------------------
def device_load(index_reg, base_slot, extmode, dst_lo=1, dst_ext9=1, idx_off=0,
                elem_code=3, space=0x10, addr_mode=0x44, access_desc=0x20,
                ld_format=0x11, ldform_hi11=0x10, reserved7=0, reserved13=0,
                elem_size=None):
    if elem_size is None:
        elem_size = 0x40 | ((elem_code & 0x7) << 1)
    return isadb.assemble("device_load", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "ld_format": ld_format & 0x3F, "dst_lo": dst_lo & 0x3,
        "dst_ext9": dst_ext9 & 0x7F, "idx_off": idx_off & 0x7FF,
        "ldform_hi11": ldform_hi11 & 0x3F, "elem_size": elem_size & 0xFF,
        "reserved13": reserved13 & 0xFF,
    })


def load_reg(plan, dst_reg, word_off, base_slot=SLOT_MEM):
    return (mov_imm(plan.idx, 0)
            + device_load(index_reg=plan.idx, base_slot=base_slot,
                          extmode=2 * dst_reg, idx_off=word_off))
