#!/usr/bin/env python3
"""EXP-0139 shared instruction-construction helpers.

PORTED VERBATIM from EXP-0128-m4-generator-envelope/isa_helpers.py (our own
prior tooling; reuse across experiments is explicitly encouraged by
experiments/SUBAGENT_BRIEF.md). The ONLY edits are (a) the REPO path (this
copy lives one directory deeper) and (b) the EXP-0139-specific builders
appended at the end of the file, each documented at its own definition.
Everything above that appended block is EXP-0128's text unchanged.

--- EXP-0128 original docstring follows ---

EXP-0128 shared instruction-construction helpers.

Every function builds ONE instruction's raw bytes via `tools/agx-isa`'s own,
READ-ONLY `isadb.assemble(mnemonic, fields)` -- never a hand-spliced byte
string. Field VALUES are either (a) HW-VALIDATED by a prior experiment and
cited, (b) HW-VALIDATED by THIS experiment's own pilot phase (PROGRESS.md
Milestones 1-2) and cited to it, or (c) a documented constant copied
VERBATIM from a prior HW-confirmed anchor, labelled at the point of use.

Reused verbatim from EXP-0112-m4-program-generator/isa_helpers.py (same
project, same rules, cited): `mov_imm`, `falu2i`, `falu2`, `device_load`,
`device_store` (ALU-forwarded, addr_mode=0x54), `iadd2_anchor`, `stop`,
`get_sr_tid`, `build_program`, `assert_round_trip`, `ELEM_SCALE`,
`load_byte_offset`, `store_byte_offset`, `DST_TOKEN_KNOWNGOOD`. Only the
NEW helpers this experiment's own pilot phase established are documented
in full below.

Register plan for this experiment's NEW families (documented in
PRE_REGISTRATION.md):
  IADD_REG family: uses r0 (fixed first operand, "srcA"), r_N for N in
    0..15 (second operand, "srcB", one case per N), and R_IDX in {14,15}
    (whichever of the two is not itself r0 or r_N) for `device_store`
    addressing. `dst` (result register) is chosen freely per case,
    including values >> 15 (this family's whole point is that dst is an
    INDEPENDENT 7-bit field, unconnected to which registers r0/r_N read).
  LOADSTORE_DIRECT family: addr_mode=0x56 store, byte offset conveyed by
    the DYNAMIC CONTENT of an index register (mov_imm-seeded), idx_off=0
    fixed on both load and store (PROGRESS.md Milestone 2 -- idx_off!=0
    was tested and fails).
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]   # EXP-0139: this file lives in harness/, one level deeper than EXP-0128's copy
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402  (read-only use: assemble/disassemble/imm_encode/imm_decode)

POOL = list(range(14))          # r0..r13 (reused DAG-style pool, not used by the NEW families directly)
R_UNWRITTEN = 14
R_IDX = 15


# ---------------------------------------------------------------------------
# float / bit helpers (verbatim from EXP-0112)
# ---------------------------------------------------------------------------
def imm_value(k):
    b1, sign = isadb.imm_encode(k)
    return isadb.imm_decode(b1, sign)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def bits_f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def i32(u):
    """Reinterpret an unsigned 32-bit pattern as Python's signed int32 --
    MUST be used for every IADD_REG oracle value, since
    harness/case_exec.py's decode_case decodes int-mode output words via
    `struct.unpack("<i", ...)` (signed), not `<I` (unsigned)."""
    return struct.unpack("<i", struct.pack("<I", u & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# single-instruction builders (verbatim from EXP-0112, cited)
# ---------------------------------------------------------------------------
def mov_imm(dst, imm8):
    """2B: d[dst] = imm8. HW-VALIDATED EXP-0031 for imm8 in 0..127. NOTE
    (this experiment's own pilot finding, PROGRESS.md Milestone 1a):
    `dst` is a HARD 4-bit field (db.json width=4) -- mov_imm can only
    directly seed r0..r15. **A SECOND, NEWLY-FOUND boundary this same
    pilot phase established**: `imm8` is only 7 bits LOAD-BEARING --
    values 0..127 read back exactly, but 128..255 silently read back as
    0 in an ordinary ALU context (HW-VALIDATED, 5-point sweep {50,127,
    128,200,255}, dense at the boundary). Combined with a SPECIFIC other
    construction (iadd2 register-mode's own N=0/self-read encoding, this
    experiment's own item (c) family) an imm8>=128 write was additionally
    observed to trigger a real GPU HANG (kIOGPUCommandBufferCallbackError
    Hang), not merely a silent zero -- see RESULTS.md "mov_imm boundary"
    for the full, disclosed finding. Every family in this experiment uses
    imm8 in 0..127 ONLY, specifically to stay clear of this boundary."""
    if not (0 <= imm8 <= 127):
        raise ValueError("mov_imm: imm8 must be 0..127 (this experiment's own "
                          "HW-VALIDATED safe range -- values >=128 are a disclosed "
                          "boundary hazard, see RESULTS.md)")
    # EXP-0139 NOTE: db.json now models this field as `imm7` (7 bits) +
    # `imm_top` (the inert 8th bit) following EXP-0128's own HW finding.
    # EXP-0128's copy of this helper predates that rename and passed `imm8`.
    return isadb.assemble("mov_imm", {"dst": dst, "imm7": imm8 & 0x7F, "imm_top": 0})


def falu2i(dst, op, srcA_reg, k, last_use_srcA, mods=0, ctrl_lo=0, srcA_size=1):
    opsel = {"fadd": 4, "fmul": 5}[op]
    b1, sign = isadb.imm_encode(k)
    imm_flag = b1 & 1
    imm_mant = (b1 >> 1) & 0x7
    imm_exp = (b1 >> 4) & 0xF
    return isadb.assemble("falu2i", {
        "dst": dst, "imm_flag": imm_flag, "imm_mant": imm_mant, "imm_exp": imm_exp,
        "opsel": opsel, "imm_sign": sign, "opflags": (1 if last_use_srcA else 0) & 0xF,
        "srcA_size": srcA_size, "srcA_reg": srcA_reg & 0x7F, "ctrl_lo": ctrl_lo, "mods": mods & 0xFF,
    })


ELEM_SCALE = {0: 16, 1: 1, 2: 2, 3: 4, 4: 8}  # EXP-0082 HW-VALIDATED


def elem_byte(code):
    return 0x40 | ((code & 0x7) << 1)


def load_byte_offset(idx, idx_off, code):
    idx_off = idx_off & 0x7FF
    scale = ELEM_SCALE[code]
    index_term = idx * scale
    if code in (1, 2):
        index_term = (index_term // 4) * 4
    return (index_term + idx_off * 4) & 0xFFFFFFFF


def store_byte_offset(idx, idx_off):
    return (idx * 4 + idx_off * 16) & 0xFFFFFFFF


DST_TOKEN_KNOWNGOOD = (1, 1)


def device_load(index_reg, idx_off, elem_code, base_slot, extmode,
                 dst_lo=1, dst_ext9=1, space=0x10, addr_mode=0x44,
                 access_desc=0x20, ld_format=0x11, ldform_hi11=0x10,
                 reserved7=0, reserved13=0):
    return isadb.assemble("device_load", {
        "space": space, "addr_mode": addr_mode, "extmode": extmode & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": access_desc, "reserved7": reserved7,
        "ld_format": ld_format, "dst_lo": dst_lo & 0x3, "dst_ext9": dst_ext9 & 0x7F,
        "idx_off": idx_off & 0x7FF, "ldform_hi11": ldform_hi11,
        "elem_size": elem_byte(elem_code), "reserved13": reserved13,
    })


def device_store(index_reg, idx_off, base_slot, data_reg, extmode=None,
                  space=0, addr_mode=0x54, access_desc=0x21, st_format=0x11,
                  st_format_ext=0, st_desc_hi=0x24, elem_size=0x11, reserved7=0, reserved13=0):
    """14B device_store, ALU-forwarded form (addr_mode=0x54). `extmode =
    2*data_reg` is EXP-0090's own HW-VALIDATED formula (finding_5)."""
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


def device_store_direct(index_reg, base_slot, idx_off=0, extmode=0):
    """14B device_store, DIRECT-FORWARD form (addr_mode=0x56). Forwards
    whatever the immediately preceding `device_load` loaded, bypassing the
    GPR file entirely -- EXP-0090 RESULTS.md finding_3 (`diagnostics/
    redecisive.py::finding_3_device_load_to_store_direct_forward_works`),
    HW-VALIDATED there for `idx_off=0`/`extmode=0` fixed on both sides.
    THIS EXPERIMENT'S OWN pilot phase (PROGRESS.md Milestone 2)
    GENERALIZES it, HW-VALIDATED: the byte address must be carried by the
    DYNAMIC CONTENT of `index_reg` (e.g. via `mov_imm`), with `idx_off`
    held at 0 on BOTH the load and this store -- `idx_off!=0` was tested
    and FAILS (silent zero). Load and store may use DIFFERENT index
    registers/values (independently addressed), and multiple load-store
    pairs CHAIN correctly (unlike this experiment's own iadd2 finding)."""
    return isadb.assemble("device_store", {
        "space": 0, "addr_mode": 0x56, "extmode": extmode & 0xFF,
        "base_slot": base_slot & 0xFF, "index_reg": index_reg & 0xFF,
        "access_desc": 0x21, "reserved7": 0,
        "st_format": 0x11, "st_format_ext": 0, "idx_off": idx_off & 0x7FF,
        "st_desc_hi": 0x24, "elem_size": 0x11, "reserved13": 0,
    })


IADD2_SRCA_R0_FIXED = 0xA8   # byte7 constant -- HW-VALIDATED (this experiment, PROGRESS.md
                             # Milestone 1): the register-mode form's FIRST operand is a
                             # FIXED read of r0, independent of `dst` -- NOT a "srcA=dst"
                             # implicit-accumulate form (both alternatives independently
                             # refuted, 3 constructions, see RESULTS.md SS "item c").


def iadd2_reg_r0_plus_rN(dst_reg, N, addsub=1, dst_size=0):
    """10B iadd2, REGISTER-mode form: `d[dst_reg] = r0 (+ or -) r_N`.
    HW-VALIDATED THIS EXPERIMENT (PROGRESS.md Milestone 1, RESULTS.md item
    c): `srcA` is the FIXED byte `IADD2_SRCA_R0_FIXED` (always reads r0,
    independent of `dst_reg`); `srcB`'s scattered field, for THIS specific
    tail shape (`opc_tail=0x17, opc_tail2=0x05` -- the compiler's own
    register-register tail, db.json's "reg-srcB tail = a8 17 05"), encodes
    the second operand as `srcB_imm = 4*N` with `srcB_reg_hi=0`/
    `srcB_ext=0` -- swept and matched N=0..15 (16/16, two independent
    process launches each during pilot, one gated run below). N>15 is
    OUT OF SCOPE (no HW-VALIDATED way in this experiment to seed r16+ for
    a clean ground-truth check -- see RESULTS.md "generation envelope").
    `dst_reg` is a fully independent 7-bit field (db.json/EXP-0020: iadd2's
    dst reaches the whole addressable GPR file) -- NOT required to be <=15,
    unlike r0/r_N which must be `mov_imm`-reachable to serve as this
    family's own ground-truth operands."""
    if not (0 <= N <= 15):
        raise ValueError("iadd2_reg_r0_plus_rN: N must be 0..15 (mov_imm-seedable range)")
    dst_field = (dst_reg << 1) | (dst_size & 1)
    return isadb.assemble("iadd2", {
        "addsub": addsub & 1, "lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0,
        "store_en": 1, "b2_fmt": 0x15, "dst": dst_field & 0xFF, "opmode": 2,
        "srcB_imm": (4 * N) & 0xFF, "srcB_imm_hi": 0, "srcB_ext": 0,
        "srcA": IADD2_SRCA_R0_FIXED, "opc_tail": 0x17, "opc_tail2": 5,
    })


def iadd2_reg_adversarial_wrong_reghi(dst_reg, N, reg_hi_bad):
    """Adversarial construction: the SAME shape as `iadd2_reg_r0_plus_rN`
    but with `srcB_reg_hi` forced to a NONZERO, wrong value (every
    HW-VALIDATED positive case above uses `srcB_reg_hi=0`) -- predicts a
    DIFFERENT (not r0+rN) result, i.e. `expect_match=False`, per this
    project's standing "deliberate single-rule violation" convention."""
    dst_field = (dst_reg << 1) & 0xFF
    return isadb.assemble("iadd2", {
        "addsub": 1, "lenbit": 1, "srcB_reg_hi": reg_hi_bad & 0x7F, "b2_bit0": 0,
        "store_en": 1, "b2_fmt": 0x15, "dst": dst_field, "opmode": 2,
        "srcB_imm": (4 * N) & 0xFF, "srcB_imm_hi": 0, "srcB_ext": 0,
        "srcA": IADD2_SRCA_R0_FIXED, "opc_tail": 0x17, "opc_tail2": 5,
    })


def get_sr_tid(dst=0):
    return isadb.assemble("get_sr", {"form": 1, "dst": dst, "sr_sel": 0xA0,
                                       "dp_width": 0x10, "dp_marker": 6, "dst_hi": 0})


def stop():
    return isadb.assemble("stop", {"reserved": 0})


# ---------------------------------------------------------------------------
# whole-program assembly (verbatim from EXP-0112)
# ---------------------------------------------------------------------------
def build_program(instrs, carrier_len, pad_dst=13):
    body = b"".join(instrs)
    if len(body) > carrier_len:
        raise ValueError("program body %d bytes exceeds carrier length %d" % (len(body), carrier_len))
    remainder = carrier_len - len(body)
    if remainder % 2:
        raise ValueError("odd padding remainder %d" % remainder)
    pad = mov_imm(pad_dst, 0) * (remainder // 2)
    out = body + pad
    assert len(out) == carrier_len
    return out


def assert_round_trip(hexbytes):
    recs, leftover = isadb.disassemble(hexbytes)
    if leftover:
        raise AssertionError("round-trip: %d leftover bytes: %s" % (len(leftover), leftover.hex()))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])
        want = hexbytes[off:off + r["length"]]
        if got != want:
            raise AssertionError("round-trip mismatch at +0x%x (%s): %s != %s" %
                                  (off, r["mnemonic"], got.hex(), want.hex()))
        off += r["length"]
    return recs
