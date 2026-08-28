#!/usr/bin/env python3
"""EXP-0141 sweep matrix: every case in the capture, declared once.

Two case kinds, both HW-PROBE on the local M4:

* `synth`  -- a COMPLETE hand-assembled AGX program (tools/agx-isa
  `isadb.assemble()` only, never a captured byte string) spliced over
  `kernels/carrier.metal`'s compiled `_agc.main[0:170]`. This is the strongest
  evidence level in CODEX.md step 3: an independently generated encoding
  executed on hardware. Used for `device_load`, `device_store` and the
  synthesised `dev_scoreboard_fence`.
* `splice` -- a single-byte mutation at a located instruction inside one of our
  own compiled MSL carriers. Used where whole-program synthesis is not yet
  possible because the instruction's operand plumbing is exactly what is under
  test (`atomic_mem`, `atomic_tg`, `threadgroup_barrier`, `mem_fence`,
  `tg_addr_compute`).

Oracles are host-computed (`carriers.py`), never read off a GPU run.
Each arm carries at least one pre-registered falsifier (`expect_match=False`).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
import carriers as C  # noqa: E402

CARRIER_LEN = 170
SLOT_OUT, SLOT_MEM = 0, 1
V_LOAD = C.MEM_F32[1]              # -8.5, the word every synthesised load reads
K_SMALL = H.imm_value(1.5)         # 1.5 exactly (isadb minifloat fixed point)
ALU_ORACLE = {0: [V_LOAD + K_SMALL]}     # -7.0
ALU_SILENT = {0: [K_SMALL]}              # 1.5  == srcA read as 0 (silent zero)
FWD_ORACLE = {0: [V_LOAD]}               # -8.5, no ALU in the path
D_ALU = 8                                # falu2i dst (4-bit field -> r0..r15)
D_CAN = 10                               # canary register
CANARY_WORD = 4                          # out[4] (store idx_off unit is 16 B)
CANARY_VALUE = 8.0

# INTEGRITY CANARY (added by AMENDMENT 1, see PRE_REGISTRATION.md).
# Under concurrent sibling GPU experiments a command buffer can come back
# `STATUS OK` having produced NOTHING -- the pre-registered baseline itself
# read back a wrong value that way during the amendment's own smoke. So every
# synthesised program first writes a fixed sentinel through a path that does
# NOT involve the instruction under test:
#     mov_imm(idx, 0); falu2i(D_CAN = r{idx} + 8.0); store out[4] = D_CAN
# and only then runs the load/ALU/store under test. `out[4] == 8.0` therefore
# means "our shader really executed"; its absence means the run is INVALID and
# must be repeated, not recorded as a property of the swept value.
# `mods` must be 0 here, not EXP-0101's 0xC0: 0xC0 is required only when the
# falu2i operand is device_load-sourced, and it BREAKS this mov_imm-sourced
# seed (pilot, work/canary).


# ---------------------------------------------------------------------------
# synthesised program shapes
# ---------------------------------------------------------------------------
def _canary(idx):
    """Sentinel prologue: out[CANARY_WORD] = CANARY_VALUE, written before the
    instruction under test and independent of it."""
    return [H.mov_imm(idx, 0),
            H.falu2i_raw(D_CAN, idx, CANARY_VALUE, mods=0),
            H.device_store(idx, SLOT_OUT, data_reg=D_CAN, idx_off=1)]


def prog_alu(R=7, dst_lo=1, dst_ext9=1, extmode=None, ld=None, st=None,
             extra=None, D=D_ALU):
    """mov_imm(idx,0); device_load -> r{R}; falu2i(D = r{R} + 1.5);
    device_store(out[0] = D). out[0] == -7.0 iff the load landed in r{R}."""
    ld = dict(ld or {})
    st = dict(st or {})
    idx = H.pick_idx_reg(R, D, D_CAN)
    lkw = dict(index_reg=idx, base_slot=SLOT_MEM,
               extmode=2 * R if extmode is None else extmode,
               dst_lo=dst_lo, dst_ext9=dst_ext9, idx_off=1)
    lkw.update(ld)
    skw = dict(index_reg=idx, base_slot=SLOT_OUT, data_reg=D, idx_off=0)
    skw.update(st)
    if "extmode" in skw:
        skw.pop("data_reg", None)
    load = H.device_load(**lkw)
    store = H.device_store(**skw)
    body = _canary(idx) + [load] + list(extra or []) + \
           [H.falu2i_raw(D, R, 1.5), store]
    return H.build_program(body, CARRIER_LEN), load, store


def prog_fwd(R=7, dst_lo=1, dst_ext9=1, extmode=None, ld=None, st=None):
    """mov_imm(idx,0); device_load -> r{R}; device_store(out[0] = r{R}).
    No ALU in the path, so out[0] is the loaded word BIT-EXACT -- the shape used
    for ld_format / elem_size, where an ALU add would mangle the bit pattern.
    device_store.addr_mode 0x56 ('direct live load-result data') is required
    here; 0x54 silently stores 0 (this experiment's own pilot, arm S_am_fwd)."""
    ld = dict(ld or {})
    st = dict(st or {})
    st.setdefault("addr_mode", 0x56)
    idx = H.pick_idx_reg(R, R, D_CAN)
    lkw = dict(index_reg=idx, base_slot=SLOT_MEM,
               extmode=2 * R if extmode is None else extmode,
               dst_lo=dst_lo, dst_ext9=dst_ext9, idx_off=1)
    lkw.update(ld)
    skw = dict(index_reg=idx, base_slot=SLOT_OUT, data_reg=R, idx_off=0)
    skw.update(st)
    if "extmode" in skw:
        skw.pop("data_reg", None)
    load = H.device_load(**lkw)
    store = H.device_store(**skw)
    return H.build_program(_canary(idx) + [load, store], CARRIER_LEN), load, store


def _case(arm, carrier, instr, field, value, note="", oracle=None,
          expect_match=None, kind="synth", prog=None, splice=None, ibytes="",
          roundtrip=False):
    c = {"arm": arm, "carrier": carrier, "instr": instr, "field": field,
         "value": value, "note": note, "oracle": oracle,
         "expect_match": expect_match, "kind": kind, "ibytes": ibytes}
    if kind == "synth":
        # CODEX step 10 round trip. A sweep VALUE may legitimately retokenize
        # the instruction (e.g. device_load byte+1 == 0x01 is atomic_mem's own
        # match), so the result is RECORDED per case rather than asserted --
        # except on controls, where a round-trip failure is a build-time stop.
        try:
            H.assert_round_trip(prog)
            c["rt"] = True
        except AssertionError:
            c["rt"] = False
        if roundtrip and not c["rt"]:
            raise AssertionError("control case %s/%s failed round trip" % (arm, field))
        c["prog"] = prog.hex()
    else:
        c["splice"] = [[off, b.hex()] for off, b in splice]
    return c


# ---------------------------------------------------------------------------
# ARM builders -- device_load / device_store (synthesis)
# ---------------------------------------------------------------------------
def arm_load_field(field, values, base=None, kind="alu", R=7, note=""):
    """Sweep one device_load field over `values` in the ALU (or fwd) program."""
    arm = "L_%s%s" % (field, "" if kind == "alu" else "_fwd")
    mk = prog_alu if kind == "alu" else prog_fwd
    oracle = ALU_ORACLE if kind == "alu" else FWD_ORACLE
    cases = []
    for v in values:
        ld = dict(base or {})
        ld[field] = v
        prog, load, _ = mk(R=R, ld=ld)
        cases.append(_case(arm, "synth", "device_load", field, v, note,
                           oracle, None, "synth", prog, ibytes=load.hex()))
    return {"arm": arm, "carrier": "synth", "instr": "device_load",
            "field": field, "cases": cases,
            "doc": "device_load.%s swept over %d values in the synthesised %s "
                   "program (oracle %s)." % (field, len(values), kind,
                                             "-7.0" if kind == "alu" else "-8.5")}


def arm_store_field(field, values, kind="alu", note=""):
    arm = "S_%s%s" % (field, "" if kind == "alu" else "_fwd")
    mk = prog_alu if kind == "alu" else prog_fwd
    oracle = ALU_ORACLE if kind == "alu" else FWD_ORACLE
    cases = []
    for v in values:
        prog, _, store = mk(R=7, st={field: v})
        cases.append(_case(arm, "synth", "device_store", field, v, note,
                           oracle, None, "synth", prog, ibytes=store.hex()))
    return {"arm": arm, "carrier": "synth", "instr": "device_store",
            "field": field, "cases": cases,
            "doc": "device_store.%s swept over %d values in the synthesised %s "
                   "program." % (field, len(values), kind)}


def build_load_store_arms():
    arms = []

    # --- controls / falsifiers on the synthesis carrier -------------------
    ctl = []
    p, ld, _ = prog_alu(R=7)
    ctl.append(_case("CTRL", "synth", "device_load", "_baseline", 0,
                     "EXP-0101's HW-VALIDATED construction, unmutated.",
                     ALU_ORACLE, True, "synth", p, ibytes=ld.hex(), roundtrip=True))
    p, ld, _ = prog_alu(R=7, dst_lo=0, dst_ext9=0)
    ctl.append(_case("CTRL", "synth", "device_load", "_falsifier_dst00", 0,
                     "PRE-REGISTERED TO FAIL: EXP-0101 found (0,0) breaks the "
                     "load (silent zero -> out0 == 1.5, not -7.0).",
                     ALU_ORACLE, False, "synth", p, ibytes=ld.hex()))
    p, ld, _ = prog_alu(R=7, extmode=0)
    ctl.append(_case("CTRL", "synth", "device_load", "_falsifier_extmode0", 0,
                     "PRE-REGISTERED TO FAIL: extmode=0 targets r0 while the "
                     "consumer reads r7 (EXP-0099's ROUTE_LOAD shape).",
                     ALU_ORACLE, False, "synth", p, ibytes=ld.hex()))
    p, _, st = prog_fwd(R=7)
    ctl.append(_case("CTRL", "synth", "device_store", "_baseline_fwd", 0,
                     "load->store forward, addr_mode 0x56; bit-exact -8.5.",
                     FWD_ORACLE, True, "synth", p, ibytes=st.hex(), roundtrip=True))
    p, _, st = prog_fwd(R=7, st={"addr_mode": 0x54})
    ctl.append(_case("CTRL", "synth", "device_store", "_falsifier_fwd_am54", 0,
                     "PRE-REGISTERED TO FAIL: 0x54 selects the ALU-computed "
                     "data source, so a direct load-result store writes 0.",
                     FWD_ORACLE, False, "synth", p, ibytes=st.hex()))
    arms.append({"arm": "CTRL", "carrier": "synth", "instr": "device_load",
                 "field": "_controls", "cases": ctl,
                 "doc": "Baselines and pre-registered falsifiers for the "
                        "synthesis carrier."})

    # --- device_load.extmode : the destination-register selector ----------
    cases = []
    for v in range(256):
        R = v >> 1
        prog, load, _ = prog_alu(R=R, extmode=v)
        cases.append(_case("L_extmode", "synth", "device_load", "extmode", v,
                           "consumer srcA_reg = %d" % R, ALU_ORACLE, None,
                           "synth", prog, ibytes=load.hex()))
    arms.append({"arm": "L_extmode", "carrier": "synth", "instr": "device_load",
                 "field": "extmode", "cases": cases,
                 "doc": "extmode 0..255 DENSE, each paired with a consumer that "
                        "reads r(extmode>>1). Tests EXP-0101's extmode = 2*R rule "
                        "over the whole 8-bit field including odd values and the "
                        "aliasing/fault region above r63."})

    # --- device_load.dst_lo / dst_ext9 : THE headline ---------------------
    for R in (3, 7, 20, 33):
        cases = []
        for v in range(4):
            prog, load, _ = prog_alu(R=R, dst_lo=v, dst_ext9=1)
            cases.append(_case("L_dst_lo_R%d" % R, "synth", "device_load",
                               "dst_lo", v, "dst_ext9 held at 1, target r%d" % R,
                               ALU_ORACLE, None, "synth", prog, ibytes=load.hex()))
        arms.append({"arm": "L_dst_lo_R%d" % R, "carrier": "synth",
                     "instr": "device_load", "field": "dst_lo", "cases": cases,
                     "doc": "dst_lo 0..3 EXHAUSTIVE at target register %d." % R})
        cases = []
        for v in range(128):
            prog, load, _ = prog_alu(R=R, dst_lo=1, dst_ext9=v)
            cases.append(_case("L_dst_ext9_R%d" % R, "synth", "device_load",
                               "dst_ext9", v, "dst_lo held at 1, target r%d" % R,
                               ALU_ORACLE, None, "synth", prog, ibytes=load.hex()))
        arms.append({"arm": "L_dst_ext9_R%d" % R, "carrier": "synth",
                     "instr": "device_load", "field": "dst_ext9", "cases": cases,
                     "doc": "dst_ext9 0..127 EXHAUSTIVE at target register %d." % R})
    cases = []
    for lo in range(4):
        for e9 in range(128):
            prog, load, _ = prog_alu(R=7, dst_lo=lo, dst_ext9=e9)
            cases.append(_case("L_dst_pair", "synth", "device_load", "dst_pair",
                               (lo << 7) | e9, "dst_lo=%d dst_ext9=%d" % (lo, e9),
                               ALU_ORACLE, None, "synth", prog, ibytes=load.hex()))
    arms.append({"arm": "L_dst_pair", "carrier": "synth", "instr": "device_load",
                 "field": "dst_pair", "cases": cases,
                 "doc": "FULL 2-D (dst_lo, dst_ext9) product, all 512 encodable "
                        "combinations, target r7. Answers whether the pair is a "
                        "free token, a constrained set, or a function of R."})

    # --- remaining device_load fields -------------------------------------
    arms.append(arm_load_field("ld_format", range(64)))
    arms.append(arm_load_field("ld_format", range(64), kind="fwd"))
    arms.append(arm_load_field("ldform_hi11", range(64),
                               note="EXP-0082 hazard: 0x48/0x50 gave undecodable output"))
    arms.append(arm_load_field("ldform_hi11", range(64), kind="fwd"))
    for f in ("reserved7", "reserved13", "space", "addr_mode", "access_desc",
              "elem_size", "index_reg"):
        arms.append(arm_load_field(f, range(256)))
    arms.append(arm_load_field("base_slot", [0, 1, 2, 3, 4, 8, 16, 30, 31, 32,
                                             63, 64, 127, 128, 129, 255],
                               note="control only; EXP-0083 already exhaustive"))
    arms.append(arm_load_field("idx_off", [0, 1, 2, 3, 4, 7, 8, 15, 16, 31,
                                           1023, 1024, 2046, 2047],
                               note="control only; EXP-0082 already 0..2047 dense"))

    # --- device_store fields ---------------------------------------------
    for f, n in (("st_format", 256), ("st_format_ext", 128), ("st_desc_hi", 64),
                 ("reserved7", 256), ("reserved13", 256), ("addr_mode", 256),
                 ("space", 256), ("access_desc", 256), ("elem_size", 256),
                 ("extmode", 256)):
        arms.append(arm_store_field(f, range(n)))
    arms.append(arm_store_field("addr_mode", range(256), kind="fwd",
                                note="direct live load-result data source"))
    arms.append(arm_store_field("st_format", range(256), kind="fwd"))
    return arms


# ---------------------------------------------------------------------------
# synthesised dev_scoreboard_fence (no own-MSL carrier emits `80 02 00 xx`
# in any shape this experiment could compile, so it is SYNTHESISED into the
# validated load->ALU->store program instead; see RESULTS.md limitations)
# ---------------------------------------------------------------------------
import isadb  # noqa: E402  (read-only; isa_helpers already put tools/agx-isa on the path)

DSF_OFF = 2 + 6 + 14 + 14   # canary(2+6+14) + device_load(14): where `extra` lands


def build_dsf_arms():
    base = isadb.assemble("dev_scoreboard_fence", {"scope_flag": 0})
    assert len(base) == 4 and base[:3] == b"\x80\x02\x00", base.hex()
    arms = []
    p0, _, _ = prog_alu(R=7, extra=[base])
    ctl = [_case("F_dsf", "synth", "dev_scoreboard_fence", "_baseline", 0,
                 "synthesised `80 02 00 00` between the load and its consumer",
                 ALU_ORACLE, True, "synth", p0, ibytes=base.hex(), roundtrip=True)]
    for name, off in (("scope_flag", 3), ("b1", 1), ("b2", 2)):
        cases = list(ctl) if name == "scope_flag" else []
        for v in range(256):
            ins = bytearray(base); ins[off] = v
            prog = bytearray(p0)
            prog[DSF_OFF:DSF_OFF + 4] = ins
            cases.append(_case("F_dsf_%s" % name, "synth",
                               "dev_scoreboard_fence", name, v, "",
                               ALU_ORACLE, None, "synth", bytes(prog),
                               ibytes=bytes(ins).hex(), roundtrip=False))
        arms.append({"arm": "F_dsf_%s" % name, "carrier": "synth",
                     "instr": "dev_scoreboard_fence", "field": name,
                     "cases": cases,
                     "doc": "dev_scoreboard_fence byte+%d 0..255 DENSE, "
                            "synthesised into the validated load->ALU->store "
                            "program; oracle = the surrounding dataflow still "
                            "produces -7.0. NOTE: this carrier has no memory "
                            "ORDERING observable, so it bounds acceptance and "
                            "dataflow-inertness only." % off})
    return arms


# ---------------------------------------------------------------------------
# splice arms -- atomics / barriers / fences / tg_addr_compute
# ---------------------------------------------------------------------------
# Instruction sites located by disassembling OUR OWN compiled carriers with
# tools/agx-isa (analysis/locate.py re-derives every one of these fresh before
# each capture; they are asserted, never assumed).
SITES = {
    "atdev":    ("atomic_mem", 70, 14),
    "atdevimm": ("atomic_mem", 70, 14),
    "attg":     ("atomic_tg", 128, 12),
    "tgtile_bar": ("threadgroup_barrier", 428, 6),
    "tgtile_tga": ("tg_addr_compute", 422, 6),
    "devfence": ("mem_fence", 90, 6),
}
BYTE_FIELD = {
    "atomic_mem": {1: "form_byte1", 2: "amode", 3: "rsv3", 4: "base_slot",
                   5: "index_reg", 6: "addr_desc", 7: "ret_flag", 8: "ret_desc",
                   9: "idx_off", 10: "rsv10", 11: "rsv11",
                   12: "op_lsb|op|per_lane|op_msb", 13: "amode_hi"},
    "atomic_tg": {1: "form_byte1", 2: "amode", 3: "ret_desc", 4: "rsv4",
                  5: "op_desc", 6: "rsv6", 7: "xop_desc", 8: "data_desc",
                  9: "rsv9", 10: "rsv10lo|op", 11: "op|op_hi_rsv"},
    "threadgroup_barrier": {1: "sub", 2: "match_byte2", 3: "mem_scope",
                            4: "flags", 5: "b5"},
    "mem_fence": {1: "sub", 2: "match_byte2", 3: "match_byte3",
                  4: "memclass", 5: "b5"},
    "tg_addr_compute": {0: "byte0_hi_nibble", 1: "byte1_operand",
                        2: "byte2_lengthdisc", 3: "b3", 4: "b4", 5: "b5"},
}


def build_splice_arms(sites):
    """`sites` maps a site key -> (mnemonic, main-relative offset, length,
    original bytes) re-derived fresh by analysis/locate.py."""
    arms = []
    for key, (mnem, off, ln, orig) in sorted(sites.items()):
        carrier = key.split("_")[0]
        for boff, fname in sorted(BYTE_FIELD[mnem].items()):
            arm = "%s_%s_b%d" % (carrier, mnem, boff)
            cases = []
            # baseline (unmutated) first, then the dense byte sweep
            cases.append(_case(arm, carrier, mnem, fname, orig[boff],
                               "BASELINE (unmutated value)", None, True,
                               "splice", splice=[(off + boff, bytes([orig[boff]]))],
                               ibytes=orig.hex()))
            for v in range(256):
                mut = bytearray(orig); mut[boff] = v
                cases.append(_case(arm, carrier, mnem, fname, v, "",
                                   None, None, "splice",
                                   splice=[(off + boff, bytes([v]))],
                                   ibytes=bytes(mut).hex()))
            arms.append({"arm": arm, "carrier": carrier, "instr": mnem,
                         "field": fname, "cases": cases,
                         "doc": "%s byte+%d (%s) 0..255 DENSE, spliced in place "
                                "at _agc.main+0x%x of our own compiled %s "
                                "carrier." % (mnem, boff, fname, off, carrier)})
    return arms


def build_falsifier_arms(sites):
    """One pre-registered-to-FAIL case per splice carrier, so every carrier
    proves it can still see a real difference (FIELD-SWEEP-PROTOCOL 3.5)."""
    cases = []
    mnem, off, ln, orig = sites["tgtile_bar"]
    mut = bytearray(orig); mut[3] = 0x00
    cases.append(_case("CTRL_SPLICE", "tgtile", "threadgroup_barrier",
                       "_falsifier_barrier_off", 0,
                       "PRE-REGISTERED TO FAIL: EXP-0025 neutralised the "
                       "threadgroup fence by mem_scope 0x61->0x00 and 128/256 "
                       "lanes read stale zeros.", None, False, "splice",
                       splice=[(off + 3, b"\x00")], ibytes=bytes(mut).hex()))
    mnem, off, ln, orig = sites["atdev"]
    mut = bytearray(orig); mut[12] = 0x22          # op 17 = and
    cases.append(_case("CTRL_SPLICE", "atdev", "atomic_mem",
                       "_falsifier_op_and", 0x22,
                       "PRE-REGISTERED TO FAIL: op add(0x20)->and(0x22) turns "
                       "0+7 into 0&7 == 0 (EXP-0018 op enum). NOTE: xchg was "
                       "REJECTED as a falsifier during harness smoke -- with a "
                       "zero-initialised counter, add and xchg both yield 7, so "
                       "it could not detect the change.", None, False,
                       "splice", splice=[(off + 12, b"\x22")],
                       ibytes=bytes(mut).hex()))
    mnem, off, ln, orig = sites["attg"]
    mut = bytearray(orig); mut[10] = orig[10] ^ 0x40   # flip an op bit
    cases.append(_case("CTRL_SPLICE", "attg", "atomic_tg",
                       "_falsifier_op_bit", mut[10],
                       "PRE-REGISTERED TO FAIL: flipping an op-selector bit "
                       "must change the threadgroup reduction.", None, False,
                       "splice", splice=[(off + 10, bytes([mut[10]]))],
                       ibytes=bytes(mut).hex()))
    for key in ("atdev", "atdevimm", "attg", "tgtile_bar", "devfence"):
        mnem, off, ln, orig = sites[key]
        carrier = key.split("_")[0]
        cases.append(_case("CTRL_SPLICE", carrier, mnem, "_baseline", 0,
                           "unmutated carrier, host-computed oracle", None,
                           True, "splice", splice=[(off, bytes([orig[0]]))],
                           ibytes=orig.hex()))
    return [{"arm": "CTRL_SPLICE", "carrier": "multi", "instr": "-",
             "field": "_controls", "cases": cases,
             "doc": "Per-carrier baselines and pre-registered falsifiers."}]


def build_all(sites):
    return (build_load_store_arms() + build_dsf_arms()
            + build_falsifier_arms(sites) + build_splice_arms(sites))


# ---------------------------------------------------------------------------
# ADDENDUM MATRIX (runs 21/22) -- the `atomic_rmw` FORM
# ---------------------------------------------------------------------------
# The frozen main matrix sweeps `atomic_mem` (byte+1 == 0x01), because that is
# what BOTH of our own atomic carriers compile to. `atomic_rmw` differs from it
# only in byte+1 (0x11), and the main matrix's `atdev_atomic_mem_b1` arm shows
# 0x11 executes correctly in the same carrier with everything else unchanged --
# but that is evidence about byte+1, NOT a per-field sweep of the 0x11 form.
# Labelling atomic_rmw's 14 fields from atomic_mem's sweeps would be exactly
# the strength mismatch `docs/evidence-classification.md` exists to prevent, so
# this addendum re-runs the dense byte sweep with byte+1 PINNED to 0x11.
RMW_BYTE1 = 0x11


def build_rmw_arms(sites):
    mnem, off, ln, orig = sites["atdev"]
    pinned = bytearray(orig)
    pinned[1] = RMW_BYTE1
    arms = []
    ctl = [_case("CTRL_RMW", "atdev", "atomic_rmw", "_baseline", RMW_BYTE1,
                 "byte+1 pinned to 0x11 (the atomic_rmw form), everything else "
                 "as the compiler emitted it", None, True, "splice",
                 splice=[(off + 1, bytes([RMW_BYTE1]))], ibytes=bytes(pinned).hex())]
    mut = bytearray(pinned); mut[12] = 0x22
    ctl.append(_case("CTRL_RMW", "atdev", "atomic_rmw", "_falsifier_op_and", 0x22,
                     "PRE-REGISTERED TO FAIL: op add(0x20)->and(0x22) turns 0+7 "
                     "into 0&7 == 0.", None, False, "splice",
                     splice=[(off + 1, bytes([RMW_BYTE1])), (off + 12, b"\x22")],
                     ibytes=bytes(mut).hex()))
    arms.append({"arm": "CTRL_RMW", "carrier": "atdev", "instr": "atomic_rmw",
                 "field": "_controls", "cases": ctl,
                 "doc": "Baseline and falsifier for the pinned 0x11 form."})
    for boff, fname in sorted(BYTE_FIELD["atomic_mem"].items()):
        if boff == 1:
            continue
        arm = "atdev_atomic_rmw_b%d" % boff
        cases = []
        for v in range(256):
            mut = bytearray(pinned); mut[boff] = v
            cases.append(_case(arm, "atdev", "atomic_rmw", fname, v, "",
                               None, None, "splice",
                               splice=[(off + 1, bytes([RMW_BYTE1])),
                                       (off + boff, bytes([v]))],
                               ibytes=bytes(mut).hex()))
        arms.append({"arm": arm, "carrier": "atdev", "instr": "atomic_rmw",
                     "field": fname, "cases": cases,
                     "doc": "atomic_rmw (byte+1 pinned 0x11) byte+%d (%s) 0..255 "
                            "DENSE." % (boff, fname)})
    return arms


# The 21 ld_format codes that deliver the 32-bit scalar correctly, taken from
# run11's own L_ld_format arm (identical in the ALU and load-forward shapes).
# Used here as a COVARIATE, not as a hypothesis: the question below is whether
# the dst_lo/dst_ext9 rule is the same under each of them.
LDFMT_OK = [3, 7, 9, 13, 17, 19, 21, 23, 25, 27, 29, 31, 39, 49, 51, 53, 55,
            57, 59, 61, 63]


def build_dst_x_ldformat_arms():
    """H8: is the (dst_lo, dst_ext9) rule INDEPENDENT of ld_format?

    EXP-0101's operational advice was to copy the pair verbatim 'from a
    compiler-observed device_load of the same addr_mode/ld_format shape', which
    implies the rule is per-shape. The main matrix swept the pair at four target
    registers but at ONE ld_format (0x11). This arm re-runs the full 512-value
    2-D product under EVERY ld_format code that works, so 'it depends on the
    shape' is either killed or demonstrated.
    """
    arms = []
    for fmt in LDFMT_OK:
        arm = "L_dstpair_ldfmt%d" % fmt
        cases = []
        for lo in range(4):
            for e9 in range(128):
                prog, load, _ = prog_alu(R=7, dst_lo=lo, dst_ext9=e9,
                                         ld={"ld_format": fmt})
                cases.append(_case(arm, "synth", "device_load", "dst_pair",
                                   (lo << 7) | e9, "ld_format=%d" % fmt,
                                   ALU_ORACLE, None, "synth", prog,
                                   ibytes=load.hex()))
        arms.append({"arm": arm, "carrier": "synth", "instr": "device_load",
                     "field": "dst_pair", "cases": cases,
                     "doc": "Full 512-value (dst_lo, dst_ext9) product at "
                            "ld_format=%d, target r7." % fmt})
    return arms


def build_operand_pair_arms(sites):
    """H9: the atomic operand-register index is
    (byte+5 >> 7) | ((byte+6 & 0x3F) << 1).

    The main matrix moved ONE byte at a time and so only ever built indices
    0, 1 and 2; the multiplier on byte+6 is interpolated from two points. This
    arm pins byte+5 = 0x80 (the index-bit-0 value) and sweeps byte+6 densely, so
    index 3 -- which must make the atomic add a[3] = 3007 -- is constructed for
    the first time.
    """
    mnem, off, ln, orig = sites["atdev"]
    base = bytearray(orig)
    base[5] = 0x80
    cases = []
    for v in range(256):
        mut = bytearray(base); mut[6] = v
        cases.append(_case("atdev_operand_pair", "atdev", "atomic_mem",
                           "index_reg|addr_desc", v, "byte+5 pinned 0x80",
                           None, None, "splice",
                           splice=[(off + 5, b"\x80"), (off + 6, bytes([v]))],
                           ibytes=bytes(mut).hex()))
    return [{"arm": "atdev_operand_pair", "carrier": "atdev",
             "instr": "atomic_mem", "field": "index_reg|addr_desc",
             "cases": cases,
             "doc": "byte+5 pinned to 0x80, byte+6 swept 0..255 DENSE: builds "
                    "operand-register indices 1, 3, 5, ... for the first time."}]


def build_addendum_controls():
    """The addendum's synth carrier needs its own pre-registered baseline and
    falsifier, so the H8 arms are not the only thing that carrier ever runs."""
    p, ld, _ = prog_alu(R=7)
    ctl = [_case("CTRL_ADD", "synth", "device_load", "_baseline", 0,
                 "canonical construction, unmutated", ALU_ORACLE, True,
                 "synth", p, ibytes=ld.hex(), roundtrip=True)]
    p, ld, _ = prog_alu(R=7, dst_lo=0, dst_ext9=0)
    ctl.append(_case("CTRL_ADD", "synth", "device_load", "_falsifier_dst00", 0,
                     "PRE-REGISTERED TO FAIL: (0,0) silently zeroes the load.",
                     ALU_ORACLE, False, "synth", p, ibytes=ld.hex(),
                     roundtrip=True))
    p, ld, _ = prog_alu(R=7, ld={"ld_format": 0})
    ctl.append(_case("CTRL_ADD", "synth", "device_load",
                     "_falsifier_ldformat0", 0,
                     "PRE-REGISTERED TO FAIL: ld_format 0 is not in the "
                     "21-code accepted set found by run11.",
                     ALU_ORACLE, False, "synth", p, ibytes=ld.hex()))
    return [{"arm": "CTRL_ADD", "carrier": "synth", "instr": "device_load",
             "field": "_controls", "cases": ctl,
             "doc": "Addendum baseline + falsifiers on the synth carrier."}]


def build_store_extmode_arms():
    """H10: is `device_store.extmode` the SOURCE REGISTER, and what are bits 6/7?

    The main matrix swept it with the data in ONE register (r8) and found only
    {16, 208} accepted -- 16 = 2*8 as EXP-0090's formula predicts, and 208 =
    16 | 0xC0 unexplained. This arm repeats the dense sweep with the ALU result
    in r4 and r12 as well. If extmode >> 1 is the source register, the accepted
    set must MOVE to {8, 8|0xC0} and {24, 24|0xC0}; if it does not move, the
    formula is wrong for the store side and the r8 result was a coincidence of
    that one register.
    """
    arms = []
    for D in (4, 8, 12):
        arm = "S_extmode_D%d" % D
        cases = []
        for v in range(256):
            prog, _, store = prog_alu(R=7, D=D, st={"extmode": v})
            cases.append(_case(arm, "synth", "device_store", "extmode", v,
                               "ALU result in r%d" % D, ALU_ORACLE, None,
                               "synth", prog, ibytes=store.hex()))
        arms.append({"arm": arm, "carrier": "synth", "instr": "device_store",
                     "field": "extmode", "cases": cases,
                     "doc": "device_store.extmode 0..255 DENSE with the stored "
                            "value in r%d." % D})
    return arms


def build_addendum(sites):
    return (build_addendum_controls() + build_store_extmode_arms()
            + build_rmw_arms(sites)
            + build_operand_pair_arms(sites) + build_dst_x_ldformat_arms())
