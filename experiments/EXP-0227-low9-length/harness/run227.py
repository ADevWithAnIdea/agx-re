#!/usr/bin/env python3
"""EXP-0227: generated G17P low-nibble-9 instruction-length probe.

The disputed instruction is generated from fields.  A staircase of independent
two-byte mov-immediate markers follows it at relative offsets 4, 6, 8, and 10;
a final marker at offset 12 proves that streams of any expected float-family
length have resynchronised before the state dump.  Which markers execute is a
direct observation of how many bytes the hardware consumed.
"""

import importlib.util
import struct
import sys
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
EXP_ROOT = EXP.parent
HERE = Path(__file__).resolve().parent
BASE_HARNESS = EXP_ROOT / "EXP-0223-isel-canonical" / "harness"
sys.path.insert(0, str(BASE_HARNESS))
import run223_pilot as B  # noqa: E402


C, P, R, S = B.C, B.P, B.R, B.S
ORIG_CASES = B.ORIG_CASES
ORIG_BUILD = B.ORIG_BUILD
BASE_SCORE = R.score

# Use this experiment's immutable decoder snapshot for assembly and Gate A.
PINNED_DECODER = EXP / "work" / "frozen" / "isadb.py"
_spec = importlib.util.spec_from_file_location("exp0227_isadb", PINNED_DECODER)
EXP227_ISADB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(EXP227_ISADB)
assert Path(EXP227_ISADB._DB_JSON).resolve() == \
    (PINNED_DECODER.parent / "db.json").resolve()
S.isadb = EXP227_ISADB

# Re-home the reusable runner so its carrier, frozen tools, work products,
# metadata hashes, and raw paths all belong to EXP-0227.
R.EXP = EXP
R.HERE = HERE
R.CARRIER = "carrier227.metal"
R.FUNC = "k"


STAIR = ((3, 91), (4, 92), (5, 93))
POST = (11, 94)
CANDIDATE_UNKNOWN_REGS = (0, 1, 2, 5)


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0227 PRE_REGISTRATION", note)


def emit_low9_prefix(pg, byte2):
    """Generate `09 01 <byte2> 05` without copying a donor instruction."""
    if not (0 <= byte2 <= 255):
        raise ValueError("byte2 must fit in one byte")
    pg.E.emit("falu_compact4", {
        "dst": fv(0, "known low-nibble-9 destination nibble"),
        "src": fv(0x01, "fixed source descriptor for the geometry probe"),
        "opsel": fv(byte2 & 0x07, "candidate low three-bit form selector"),
        "opmode": fv(byte2 >> 3, "remaining byte+2 mode bits"),
        "operand": fv(0x05, "fixed operand descriptor for the geometry probe"),
    })
    pg._pending = None
    # Length is the only axis under test.  Do not claim arithmetic or lifecycle
    # semantics for this candidate: retain the complete readback, but mark every
    # plausibly named low register unknown until a later marker overwrites it.
    for reg in CANDIDATE_UNKNOWN_REGS:
        pg.set_reg(reg, None)


def emit_staircase(pg, first_reg, first_value, model_first_value=None):
    markers = [(first_reg, first_value)] + list(STAIR)
    for reg, value in markers:
        pg.movi(reg, value)
    if model_first_value is not None:
        pg.set_reg(first_reg, model_first_value)
    pg.movi(*POST)
    return markers + [POST]


def add_case(out, name, arm, byte2, first_reg, first_value,
             model_first_value=None, expected_length=4,
             predicted_bucket="measure"):
    out.append({
        "i": len(out),
        "name": name,
        "arm": arm,
        "kind": "low9_length",
        "expect_match": arm != "CTL",
        "predicted_bucket": predicted_bucket,
        "byte2": byte2,
        "first_reg": first_reg,
        "first_value": first_value,
        "model_first_value": model_first_value,
        "expected_length": expected_length,
    })


def build_cases(include_hazard=False):
    out = [case for case in ORIG_CASES(False) if case["arm"] == "S0"]
    add_case(out, "h1_b20_r0_imm55", "H1", 0x20, 0, 85)
    add_case(out, "h1_b20_r0_imm33", "H1", 0x20, 0, 51)
    add_case(out, "h1_b20_r6_imm57", "H1", 0x20, 6, 87)
    add_case(out, "p1_known_b21_r0_imm55", "P1", 0x21, 0, 85)
    add_case(out, "ctl_wrong_r0_model33", "CTL", 0x20, 0, 85,
             model_first_value=51, predicted_bucket="refute")
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = B.fresh(case, slots)
    emit_low9_prefix(pg, case["byte2"])
    case["marker_values"] = emit_staircase(
        pg, case["first_reg"], case["first_value"],
        model_first_value=case.get("model_first_value"))
    pg.dump()
    return pg, pg.finish(carrier_len)


def _dump_u32(pg, res, slots, reg):
    surf = res.get("surf", {}).get(slots["out"])
    off = pg.dump_byte(reg)
    if surf is None or off + 4 > len(surf):
        return None
    return struct.unpack("<I", surf[off:off + 4])[0]


def score227(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] != "low9_length":
        return rec

    marker_offsets = (4, 6, 8, 10)
    marker_values = case["marker_values"][:-1]
    post_reg, post_value = case["marker_values"][-1]
    observed = {str(reg): _dump_u32(pg, res, slots, reg)
                for reg, _ in case["marker_values"]}
    hits = [observed[str(reg)] == value for reg, value in marker_values]
    post_hit = observed[str(post_reg)] == post_value

    candidates = []
    for length in (4, 6, 8, 10, 12):
        predicted = [offset >= length for offset in marker_offsets]
        if hits == predicted and post_hit:
            candidates.append(length)

    body = prog[pg.body_start:pg.body_end]
    probe = {
        "candidate_offset": pg.body_start,
        "candidate_bytes": body[:4].hex(),
        "following_10_bytes": body[4:14].hex(),
        "marker_relative_offsets": list(marker_offsets),
        "marker_values": [[reg, value] for reg, value in marker_values],
        "post_marker": [post_reg, post_value, 12],
        "observed_u32": observed,
        "marker_hits": hits,
        "post_marker_hit": post_hit,
        "inferred_length_candidates": candidates,
        "expected_length": case["expected_length"],
    }
    if case["arm"] == "CTL":
        probe["control_detected"] = bool(not rec.get("match") and
                                         rec.get("bucket_ok"))
        probe["length_gate_ok"] = (candidates == [case["expected_length"]] and
                                   probe["control_detected"])
    else:
        probe["length_gate_ok"] = (candidates == [case["expected_length"]])
    rec["length_probe"] = probe
    return rec


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    R.score = score227
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
