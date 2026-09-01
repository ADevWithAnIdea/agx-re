#!/usr/bin/env python3
"""EXP-0229: generated marker probe for 10/12-byte SIMD forms."""

import importlib.util
import struct
import sys
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
EXP_ROOT = EXP.parent
HERE = Path(__file__).resolve().parent
BASE = EXP_ROOT / "EXP-0227-low9-length" / "harness"
sys.path.insert(0, str(BASE))
import run227 as B  # noqa: E402


C, P, R, S = B.C, B.P, B.R, B.S
ORIG_CASES, ORIG_BUILD = B.ORIG_CASES, B.ORIG_BUILD
BASE_SCORE = B.BASE_SCORE

PINNED = EXP / "work" / "frozen" / "isadb.py"
_spec = importlib.util.spec_from_file_location("exp0229_isadb", PINNED)
EXP229_ISADB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(EXP229_ISADB)
assert Path(EXP229_ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = EXP229_ISADB

R.EXP = EXP
R.HERE = HERE
R.CARRIER = "carrier229.metal"
R.FUNC = "k"

MARKERS = ((6, None), (7, 88), (8, 89))
POST = (11, 94)
KNOWN_MODES = (0, 1, 4, 5, 6, 8, 16, 20, 21)


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0229 PRE_REGISTRATION", note)


def add_case(out, name, arm, direction, mode, rsv9, first_value,
             model_first_value=None):
    out.append({
        "i": len(out), "name": name, "arm": arm,
        "kind": "simd_length", "expect_match": arm == "N10",
        "predicted_bucket": "measure" if arm != "CTL" else "refute",
        "direction": direction, "mode": mode, "rsv9": rsv9,
        "first_value": first_value, "model_first_value": model_first_value,
        "expected_length": 12 if mode == 6 else 10,
    })


def build_cases(include_hazard=False):
    out = [case for case in ORIG_CASES(False) if case["arm"] == "S0"]
    for direction in (0, 1):
        for mode in KNOWN_MODES:
            rsvs = (0x11, 0x91) if mode == 6 else (0x00,)
            for rsv9 in rsvs:
                arm = "M12" if mode == 6 else "M10"
                add_case(out, "%s_d%d_mode%02x_b%02x" %
                         (arm.lower(), direction, mode, rsv9), arm,
                         direction, mode, rsv9, 51)
    for rsv9 in (0x11, 0x91):
        add_case(out, "m12_repeat_d1_mode06_b%02x" % rsv9, "M12",
                 1, 6, rsv9, 87)
    add_case(out, "ctl_wrong_marker", "CTL", 0, 4, 0x00, 87,
             model_first_value=51)
    return out


def emit_prefix(pg, case):
    pg.E.emit("simd_shuffle", {
        "dir": fv(case["direction"], "direction cross-check"),
        "mode": fv(case["mode"], "named SIMD mode length discriminator"),
        "cache": fv(1, "G17P-valid SIMD cache point"),
        "dst": fv(0, "normalized destination"),
        "src": fv(2, "normalized source"),
        "srctype": fv(0, "u32 source type"),
        "lane": fv(2, "asymmetric lane/second-source selector"),
        "rtype": fv(0, "u32 result type"),
        "dsthi": fv(0x14, "known SIMD destination descriptor"),
        "rsv9": fv(case["rsv9"], "candidate ten/twelve-byte selector"),
    })
    pg._pending = None
    # Length is the only claim. Mark the generated source/destination unknown,
    # while retaining r15's known index value so the full-state dump remains
    # addressable and auditable.
    for reg in (0, 2):
        pg.set_reg(reg, None)


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = B.B.fresh(case, slots)
    emit_prefix(pg, case)
    marker_values = []
    for reg, fixed in MARKERS:
        value = case["first_value"] if fixed is None else fixed
        pg.movi(reg, value)
        marker_values.append((reg, value))
    if case.get("model_first_value") is not None:
        pg.set_reg(MARKERS[0][0], case["model_first_value"])
    pg.movi(*POST)
    marker_values.append(POST)
    case["marker_values"] = marker_values
    pg.dump()
    return pg, pg.finish(carrier_len)


def _dump_u32(pg, res, slots, reg):
    surf = res.get("surf", {}).get(slots["out"])
    off = pg.dump_byte(reg)
    if surf is None or off + 4 > len(surf):
        return None
    return struct.unpack("<I", surf[off:off + 4])[0]


def score229(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] != "simd_length":
        return rec

    marker_offsets = (10, 12, 14)
    marker_values = case["marker_values"][:-1]
    post_reg, post_value = case["marker_values"][-1]
    observed = {str(reg): _dump_u32(pg, res, slots, reg)
                for reg, _ in case["marker_values"]}
    hits = [observed[str(reg)] == value for reg, value in marker_values]
    post_hit = observed[str(post_reg)] == post_value
    candidates = []
    for length in (10, 12, 14, 16):
        if hits == [offset >= length for offset in marker_offsets] and post_hit:
            candidates.append(length)
    body = prog[pg.body_start:pg.body_end]
    probe = {
        "candidate_offset": pg.body_start,
        "candidate_bytes": body[:10].hex(),
        "following_8_bytes": body[10:18].hex(),
        "marker_relative_offsets": list(marker_offsets),
        "marker_values": [[reg, value] for reg, value in marker_values],
        "post_marker": [post_reg, post_value, 16],
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
        probe["length_gate_ok"] = candidates == [case["expected_length"]]
    rec["length_probe"] = probe
    return rec


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    R.score = score229
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
