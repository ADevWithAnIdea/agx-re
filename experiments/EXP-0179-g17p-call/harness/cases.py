#!/usr/bin/env python3
"""EXP-0179 case matrix. The single authoritative definition of what is
dispatched; `harness/run.py` executes exactly what `build_cases()` returns and
`CAPTURE_CONTRACT.json` records its sha256.

FIELD-SWEEP-PROTOCOL section 3 coverage: every field under test is 8 bits wide,
so every arm sweeps ALL 256 values densely on BOTH carriers. Nothing is sampled.

The two carriers differ in **execution-mask stack depth** at the call, which is
the dimension H4 says these fields control (`call` shares the `0f 05` leader with
`if_push`, whose own descriptor calls byte+2 the mask BANK and byte+3 the SCOPE
KIND -- and `call` carries 0x1a at byte+3, the value `if_push` names as a
loop-iteration scope). Two carriers differing only in the register plan would be
one carrier (the EXP-0163 lesson).

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte dispatched is generated from the
pinned descriptor geometry; nothing is copied from a compiled shader.
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
import isadb             # noqa: E402


def _field_geom(mnemonic, field):
    for i in isadb.DB:
        if i["mnemonic"] == mnemonic:
            for f in i["fields"]:
                if f["name"] == field:
                    return f["start"], f["width"]
    raise KeyError("%s.%s not in the pinned db.json" % (mnemonic, field))


def load_addendum():
    """The FOUR calibrated parameters, frozen by the pre-freeze phase and written
    to `work/addendum.json`. FAIL-CLOSED: an underspecified frozen contract is an
    automatic STOP (SUBAGENT_BRIEF), so there is no default."""
    p = EXP / "work" / "addendum.json"
    if not p.exists():
        raise RuntimeError(
            "FROZEN ADDENDUM MISSING: %s. Run harness/calib.py first; its four "
            "outputs (extmode_or, marker, reconverge, region_len) are the ONLY "
            "parameters calibration may decide, and they must be frozen before "
            "any gated case is dispatched." % p)
    a = json.loads(p.read_text())
    for k in ("extmode_or", "marker", "reconverge", "region_len", "jumpover_ok"):
        if k not in a:
            raise RuntimeError("addendum missing key %r" % k)
    return a


# The two gated carriers.
# AMENDMENT-01: C2 is `if_push(scope=0x56, scope_kind=0x1a)` deep. The frozen
# C2 (`scope_kind=0x01`) was MEASURED DEAD in run01 and is retained, not reused.
CARRIERS = {
    "C1_flat":   {"plan": "idx15", "nested": False},
    "C2_nested": {"plan": "idx7",  "nested": True},
}
AMENDMENT_01 = {"nested_scope": 0x56, "nested_kind": 0x1a}
# Arm G additionally crosses plan x nesting so that all 16 register slots are
# genuinely observed (each plan is blind at a different slot).
GEN_CARRIERS = {
    "C1_flat":     {"plan": "idx15", "nested": False},
    "C1b_flat":    {"plan": "idx7",  "nested": False},
    "C2_nested":   {"plan": "idx7",  "nested": True},
    "C2b_nested":  {"plan": "idx15", "nested": True},
}

FIELDS = [
    ("B3", "call", "b3"),
    ("B5", "call", "b5"),
    ("B6", "call", "b6"),
    ("TL", "call", "tail"),
    ("R",  "ret",  "scoreboard"),
]

BASE_CALL = {"call_b3": 0x1a, "call_b5": 0x00, "call_b6": 0x56, "call_tail": 0x00}
BASE_RET = {"ret_linkmode": 0x02, "ret_scoreboard": 0x00}

GEN_GAPS = list(range(0, 96, 2))          # 48 distinct generated displacements
TARGET_DELTAS = [-8, -6, -4, -2, 0, 2, 4, 6, 8]
ORDER_FILLERS = [0, 1, 2, 3, 4, 6, 8, 10, 12, 16, 20, 24]
ORDER_SB = [0x00, 0x02, 0x04, 0x06, 0x20, 0x22, 0x24, 0x26,
            0x2A, 0x40, 0x80, 0xA2, 0xC0, 0xE2, 0xFE, 0xFF]


def _case(arm, carrier, cfg, addendum, **kw):
    """One case. Every row carries the dispatch standard's required keys."""
    c = {
        "arm": arm,
        "carrier": carrier,
        "plan": cfg["plan"],
        "nested": cfg["nested"],
        "marker": addendum["marker"],
        "reconverge": addendum["reconverge"],
        "instr": kw.pop("instr", "call"),
        "field": kw.pop("field", None),
        "value": kw.pop("value", None),
        "start": kw.pop("start", None),
        "width": kw.pop("width", None),
        "encodable_range": kw.pop("encodable_range", None),
        "expect_called": kw.pop("expect_called", True),
        "expect_returned": kw.pop("expect_returned", True),
        "expect_rung": kw.pop("expect_rung", None),
        "falsifier": kw.pop("falsifier", False),
        "hang_candidate": kw.pop("hang_candidate", False),
        "note": kw.pop("note", ""),
        "build": {},
    }
    build = dict(BASE_CALL)
    build.update(BASE_RET)
    build.update({"nested": cfg["nested"], "marker": addendum["marker"],
                  "reconverge": addendum["reconverge"]})
    build.update(AMENDMENT_01)
    build.update(kw)
    c["build"] = build
    return c


def build_cases(addendum=None):
    a = addendum or load_addendum()
    cases = []

    # ---- arm G: the ACCEPTANCE-GATE arm. Fully generated calls at 48 distinct
    # displacements on each of the four plan x nesting combinations. Zero bytes
    # copied from any compiled shader.
    for cname, cfg in sorted(GEN_CARRIERS.items()):
        for g in GEN_GAPS:
            cases.append(_case("G", cname, cfg, a, field="offset",
                               value=g, start=56, width=48,
                               encodable_range=(1 << 48), gap=g,
                               note="generated call, displacement varied by gap"))

    # ---- arm T: the TARGET FORMULA, measured by generation rather than assumed.
    for cname, cfg in sorted(CARRIERS.items()):
        for d in TARGET_DELTAS:
            # a negative delta lands on the landing ladder; the expected rung is
            # host-computed from the layout, NOT read off the GPU.
            rung = None
            if d < 0:
                nrung = len(H.LADDER_R)
                early = -d
                if early % 2 == 0 and early <= 2 * nrung:
                    rung = nrung - early // 2
                else:
                    rung = "unmodelled"
            cases.append(_case("T", cname, cfg, a, field="offset", value=d,
                               start=56, width=48, encodable_range=(1 << 48),
                               offset_delta=d,
                               expect_rung=(rung if rung != "unmodelled" else None),
                               expect_called=(d <= 0),
                               falsifier=(d == -2),
                               hang_candidate=(d > 0),
                               note="target = call_addr + 4 + offset + delta"))
        cases.append(_case("T", cname, cfg, a, field="offset", value="target_ret",
                           start=56, width=48, encodable_range=(1 << 48),
                           target="ret", expect_called=False,
                           note="call aimed at the bare `ret`: does a callee with "
                                "no body still return?"))
        cases.append(_case("T", cname, cfg, a, field="offset", value="target_ladder",
                           start=56, width=48, encodable_range=(1 << 48),
                           target="ladder", expect_rung=0,
                           note="call aimed at ladder rung 0"))

    # ---- arm M: is the 0x43 frame marker / 0f 06 reconverge REQUIRED?
    for cname, cfg in sorted(CARRIERS.items()):
        for mk in (False, True):
            for rc in (False, True):
                cases.append(_case("M", cname, cfg, a, field="bracket",
                                   value="marker=%d,reconverge=%d" % (mk, rc),
                                   start=None, width=None, encodable_range=4,
                                   marker=mk, reconverge=rc,
                                   note="EXP-0035 observed both; whether either is "
                                        "REQUIRED has never been tested"))

    # ---- the five dense 8-bit field sweeps
    for (arm, mnem, field) in FIELDS:
        start, width = _field_geom(mnem, field)
        key = ("call_" + field) if mnem == "call" else ("ret_" + field)
        base = BASE_CALL.get(key, BASE_RET.get(key))
        for cname, cfg in sorted(CARRIERS.items()):
            for v in range(1 << width):
                cases.append(_case(arm, cname, cfg, a, instr=mnem, field=field,
                                   value=v, start=start, width=width,
                                   encodable_range=(1 << width),
                                   hang_candidate=(mnem == "call"),
                                   note=("baseline" if v == base else ""),
                                   **{key: v}))

    # ---- arm L: ret.linkmode control (already `hardware-run` from EXP-0156;
    # re-run at four values only, as a cross-experiment consistency control).
    ls, lw = _field_geom("ret", "linkmode")
    for cname, cfg in sorted(CARRIERS.items()):
        for v in (0x02, 0x04, 0x05, 0x12):
            cases.append(_case("L", cname, cfg, a, instr="ret", field="linkmode",
                               value=v, start=ls, width=lw, encodable_range=256,
                               ret_linkmode=v, hang_candidate=True,
                               note="control: EXP-0156 swept this densely on G17P"))

    # ---- arm F: the falsifiers, pre-registered to FAIL
    for cname, cfg in sorted(CARRIERS.items()):
        # F2 -- the call replaced by 2-byte no-ops
        cases.append(_case("F", cname, cfg, a, field="F2_no_call",
                           value="pads", start=None, width=None,
                           encodable_range=1,
                           replace_call=H.nop_pad(H.PLANS[cfg["plan"]]) * 7,
                           expect_called=False, falsifier=True,
                           note="F2: the callee's effect must vanish when the call "
                                "is replaced by no-ops"))
        # F3 -- corrupt the CALL/link signature byte (a `match` byte, on purpose)
        for v in (0x00, 0xFF):
            cases.append(_case("F", cname, cfg, a, field="F3_sig_byte4",
                               value=v, start=32, width=8, encodable_range=256,
                               corrupt_call_byte=(4, v), falsifier=True,
                               hang_candidate=True,
                               note="F3: byte+4 is pinned in `match`; breaking it "
                                    "must not behave like the baseline"))
        # F4 -- the callee's `ret` replaced by no-ops
        cases.append(_case("F", cname, cfg, a, field="F4_no_ret", value="pads",
                           start=None, width=None, encodable_range=1,
                           replace_ret=H.nop_pad(H.PLANS[cfg["plan"]]) * 2,
                           expect_returned=False, falsifier=True,
                           hang_candidate=True,
                           note="F4: with no `ret` the program must not return"))
        # F6 -- nested carrier with the pop removed (bounds an unbalanced stack)
        if cfg["nested"]:
            cases.append(_case("F", cname, cfg, a, field="F6_unbalanced",
                               value="no_pop", start=None, width=None,
                               encodable_range=1, reconverge=False,
                               falsifier=False, hang_candidate=True,
                               note="F6: recorded, not predicted"))

    # ---- arm N: depth-2 generated call with NO link save/restore (H7).
    # RUN LAST, own hang budget. A destroyed return address is exactly the
    # 'runs forever' failure FIELD-SWEEP-PROTOCOL 3(c) warns about.
    for cname, cfg in sorted(CARRIERS.items()):
        # AMENDMENT-02: `depth2_pop` is now a VARIABLE, and pop=False is retained
        # as the control that reproduces the first pass's fault -- so arm N's
        # result cannot be confused with arm M's.
        for (lk, mk, pop) in ((False, False, True), (False, True, True),
                              (True, False, True), (False, False, False)):
            cases.append(_case("N", cname, cfg, a, field="depth2",
                               value="link=%d,marker=%d,pop=%d" % (lk, mk, pop),
                               start=None, width=None, encodable_range=4,
                               depth2=True, depth2_link=lk, depth2_marker=mk,
                               depth2_pop=pop, hang_candidate=True,
                               note="H7: is the return address a HW stack or a "
                                    "single link register?"))

    # ---- arm O: the ordering observable for ret.scoreboard.
    # PROMOTION IS PRE-DECLINED unless the positive control fires AND the
    # filler-length threshold SHIFTS with the scoreboard value (PRE_REG section 9).
    ss, sw = _field_geom("ret", "scoreboard")
    for cname, cfg in sorted(CARRIERS.items()):
        for f in ORDER_FILLERS:
            for sb in ORDER_SB:
                cases.append(_case("O", cname, cfg, a, instr="ret",
                                   field="scoreboard", value=sb,
                                   start=ss, width=sw, encodable_range=256,
                                   ret_scoreboard=sb, order_load=True,
                                   order_filler=f,
                                   note="order grid filler=%d" % f))
    return cases


def matrix_sha256(cases):
    blob = json.dumps(cases, sort_keys=True, separators=(",", ":"),
                      default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def summarize(cases):
    per = {}
    for c in cases:
        k = "%s/%s" % (c["arm"], c["carrier"])
        per[k] = per.get(k, 0) + 1
    return per


if __name__ == "__main__":
    cs = build_cases()
    print(json.dumps({"n_cases": len(cs), "sha256": matrix_sha256(cs),
                      "arms": summarize(cs)}, indent=1, sort_keys=True))
