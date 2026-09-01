#!/usr/bin/env python3
"""EXP-0234: canonical isel10 per-role register reach on G17P."""

import importlib.util
import struct
import sys
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import base_run221 as B  # noqa: E402


S, P = B.S, B.P
BASE_SCORE = B.score
PINNED = EXP / "work" / "frozen" / "isadb.py"
spec = importlib.util.spec_from_file_location("exp0234_isadb", PINNED)
ISADB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ISADB)
assert Path(ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = ISADB
B.EXP = EXP
B.HERE = HERE
B.CARRIER = "carrier234.metal"

OBS = {
    "pre_target": 1000,
    "pre_destination": 1001,
    "pre_alias16": 1002,
    "pre_alias32": 1003,
    "pre_alias64": 1004,
    "post_destination": 1010,
    "post_target": 1011,
    "post_alias16": 1012,
    "post_alias32": 1013,
    "post_alias64": 1014,
    "post_source0": 1015,
    "post_source1": 1016,
}


def build_cases(include_hazard=False):
    out = [{
        "i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
        "kind": "s0_slot", "slot": slot, "expect_match": True,
        "predicted_bucket": "measure", "expect_sentinel": False,
    } for slot in range(8)]
    for role, arm in (("cmp_a", "A"), ("cmp_b", "B"),
                      ("sel_true", "T"), ("sel_false", "F")):
        for reg in range(96):
            out.append({
                "i": len(out), "name": "%s_r%02d" % (arm.lower(), reg),
                "arm": arm, "kind": "isel_reach", "role": role,
                "register": reg, "expect_match": True,
                "predicted_bucket": "exact", "oracle_mode": "exact",
            })
    for reg in range(16):
        out.append({
            "i": len(out), "name": "d_r%02d" % reg, "arm": "D",
            "kind": "isel_reach", "role": "destination", "register": reg,
            "expect_match": True, "predicted_bucket": "exact",
            "oracle_mode": "exact",
        })
    for name, role, reg in (("ctl_wrong_t", "sel_true", 95),
                            ("ctl_wrong_d", "destination", 15)):
        out.append({
            "i": len(out), "name": name, "arm": "CTL",
            "kind": "isel_reach", "role": role, "register": reg,
            "expect_match": False, "predicted_bucket": "refute",
            "oracle_mode": "wrong",
        })
    if include_hazard:
        for role, short in (("cmp_a", "a"), ("cmp_b", "b"),
                            ("sel_true", "t"), ("sel_false", "f")):
            for suffix, reg, expected_status in (
                    ("ctl_pre96", 95, "exact"), ("r96", 96, "fault"),
                    ("ctl_mid96", 95, "exact"), ("r127", 127, "fault"),
                    ("ctl_post127", 95, "exact")):
                out.append({
                    "i": len(out), "name": "h_%s_%s" % (short, suffix),
                    "arm": "H", "kind": "isel_reach", "role": role,
                    "register": reg, "expect_match": expected_status == "exact",
                    "predicted_bucket": ("exact" if expected_status == "exact"
                                         else "corrupt"),
                    "oracle_mode": "exact", "expected_status": expected_status,
                    "hazard": expected_status != "exact",
                })
    return out


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0234 PRE_REGISTRATION", note)


def pack_word(bits):
    return list(struct.pack("<I", bits & 0xFFFFFFFF))


def choose_indices(excluded):
    # r12 remains the independent sentinel carrier. At most one of r13..r15
    # can occur in a case's target/alias set because those aliases share the
    # same residue modulo 16, leaving two independent index registers.
    available = [r for r in (13, 14, 15) if r not in excluded]
    if len(available) < 2:
        raise AssertionError((excluded, available))
    return available[0], available[1]


def generated_load(pg, load_index, store_index, reg, codeword_number, out_off, tag):
    value = P.codeword(codeword_number)
    previous = pg.rbits(reg)
    S.device_load(pg.E, load_index, P.CODEWORD_BASE + codeword_number, 3,
                  pg.slots["imem"], reg, salt=tag + "_load", offnatural=False,
                  ld_format=17, extmode=2 * reg, addr_mode=0x44)
    pg.set_reg(reg, value)
    pg._pending = (reg, previous)
    generated_store(pg, store_index, reg, out_off, value, tag + "_fwd",
                    addr_mode=S.DS_ADDRMODE_LOADFWD)
    return value


def generated_store(pg, store_index, reg, out_off, value, tag,
                    addr_mode=S.DS_ADDRMODE_ALU):
    idx = pg.rbits(store_index)
    S.device_store(pg.E, store_index, out_off, pg.slots["out"], reg,
                   salt=tag, offnatural=False, st_format=17,
                   extmode=2 * reg, addr_mode=addr_mode)
    off = None if idx is None else S.store_byte_offset(idx, out_off)
    pg.writes.append(("out", off, pack_word(value), tag))
    pg._pending = None
    pg.set_reg(store_index, 0)


def observe(pg, store_index, reg, out_off, tag):
    generated_store(pg, store_index, reg, out_off, pg.rbits(reg), tag)


def emit_isel(pg, destination, cmp_a, cmp_b, sel_true, sel_false, predicted):
    pg.E.emit("isel10", {
        "dst": fv(destination, "four-bit destination GPR"),
        "cmpA": fv((cmp_a << 1) | 1, "32-bit compare-A descriptor"),
        "opsel": fv(0, "retain compare sources"),
        "cmpB": fv((cmp_b << 1) | 1, "32-bit compare-B descriptor"),
        "cmp_mode": fv(0x06, "integer equality mode and retain true source"),
        "selTrue": fv(sel_true << 1, "32-bit true-value descriptor"),
        "cc": fv(0, "integer equality condition"),
        "flags": fv(0xC0, "canonical dependency-accepting flags"),
        "selFalse_file": fv(0, "GPR false source and retain it"),
        "selFalse": fv(sel_false << 1, "32-bit false-value descriptor"),
    })
    pg._pending = None
    pg.set_reg(destination, predicted)


def seed_map(pg, load_index, store_index, seeds):
    for n, (reg, codeword_number) in enumerate(seeds.items()):
        generated_load(pg, load_index, store_index, reg, codeword_number,
                       1100 + n, "seed_r%02d" % reg)


def choose_low(excluded, count):
    out = [r for r in range(12) if r not in excluded]
    if len(out) < count:
        raise AssertionError((excluded, out, count))
    return out[:count]


def source_program(case, slots, carrier_len):
    reg = case["register"]
    alias16, alias32, alias64 = reg % 16, reg % 32, reg % 64
    relevant = {alias16, alias32, alias64}
    if reg < 96:
        relevant.add(reg)
    destination, q0, q1, q2 = choose_low(relevant, 4)
    relevant.update((destination, q0, q1, q2))
    store_index, load_index = choose_indices(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")

    seeds = {}
    seeds[alias16] = 116
    seeds[alias32] = 117
    seeds[alias64] = 118
    if reg < 96:
        seeds[reg] = reg
    seeds[destination] = 120
    role = case["role"]
    if role == "cmp_a":
        cmp_a, cmp_b, sel_true, sel_false = reg, q0, q1, q2
        seeds[q0], seeds[q1], seeds[q2] = reg, 121, 122
    elif role == "cmp_b":
        cmp_a, cmp_b, sel_true, sel_false = q0, reg, q1, q2
        seeds[q0], seeds[q1], seeds[q2] = reg, 121, 122
    elif role == "sel_true":
        cmp_a, cmp_b, sel_true, sel_false = q0, q1, reg, q2
        seeds[q0], seeds[q1], seeds[q2] = 121, 121, 122
    elif role == "sel_false":
        cmp_a, cmp_b, sel_true, sel_false = q0, q1, q2, reg
        seeds[q0], seeds[q1], seeds[q2] = 121, 122, 123
    else:
        raise AssertionError(role)
    seed_map(pg, load_index, store_index, seeds)

    if reg < 96:
        observe(pg, store_index, reg, OBS["pre_target"], "pre_target")
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")
    observe(pg, store_index, alias16, OBS["pre_alias16"], "pre_alias16")
    observe(pg, store_index, alias32, OBS["pre_alias32"], "pre_alias32")
    observe(pg, store_index, alias64, OBS["pre_alias64"], "pre_alias64")

    def candidate_result(value):
        av = value if role == "cmp_a" else pg.rbits(cmp_a)
        bv = value if role == "cmp_b" else pg.rbits(cmp_b)
        tv = value if role == "sel_true" else pg.rbits(sel_true)
        fval = value if role == "sel_false" else pg.rbits(sel_false)
        if None in (av, bv, tv, fval):
            return None
        return tv if av == bv else fval

    candidate_results = {
        "exact": candidate_result(pg.rbits(reg)),
        "mod16": candidate_result(pg.rbits(alias16)),
        "mod32": candidate_result(pg.rbits(alias32)),
        "mod64": candidate_result(pg.rbits(alias64)),
        "zero": candidate_result(0),
    }
    exact = candidate_results["exact"]
    predicted = (0 if exact is None else
                 (exact if case["oracle_mode"] == "exact" else exact ^ 0xFFFFFFFF))
    pg.body_start = pg.E.off
    emit_isel(pg, destination, cmp_a, cmp_b, sel_true, sel_false, predicted)
    pg.body_end = pg.E.off

    observe(pg, store_index, destination, OBS["post_destination"], "post_destination")
    if reg < 96:
        observe(pg, store_index, reg, OBS["post_target"], "post_target")
    observe(pg, store_index, alias16, OBS["post_alias16"], "post_alias16")
    observe(pg, store_index, alias32, OBS["post_alias32"], "post_alias32")
    observe(pg, store_index, alias64, OBS["post_alias64"], "post_alias64")
    pg.probe_expected = {
        "exact_result": exact,
        "candidate_results": candidate_results,
        "destination": destination,
    }
    return pg, pg.finish(carrier_len)


def destination_program(case, slots, carrier_len):
    destination = case["register"]
    aliases = {destination}
    cmp_a, cmp_b, sel_true, sel_false = choose_low({destination}, 4)
    relevant = aliases | {cmp_a, cmp_b, sel_true, sel_false}
    store_index, load_index = choose_indices(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")

    seeds = {}
    seeds[destination] = 120
    seeds[cmp_a] = 121
    seeds[cmp_b] = 121
    seeds[sel_true] = 122
    seeds[sel_false] = 123
    seed_map(pg, load_index, store_index, seeds)
    for name, reg in (("pre_target", destination),
                      ("pre_alias16", destination % 16),
                      ("pre_alias32", destination % 32),
                      ("pre_alias64", destination % 64)):
        observe(pg, store_index, reg, OBS[name], name)
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")

    result = pg.rbits(sel_true)
    predicted = result if case["oracle_mode"] == "exact" else result ^ 0xFFFFFFFF
    pg.body_start = pg.E.off
    emit_isel(pg, destination, cmp_a, cmp_b, sel_true, sel_false, predicted)
    pg.body_end = pg.E.off

    for name, reg in (("post_destination", destination),
                      ("post_alias16", destination % 16),
                      ("post_alias32", destination % 32),
                      ("post_alias64", destination % 64),
                      ("post_source0", cmp_a), ("post_source1", cmp_b)):
        observe(pg, store_index, reg, OBS[name], name)
    pg.probe_expected = {"exact_result": result, "destination": destination}
    return pg, pg.finish(carrier_len)


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        pg = P.Prog({"out": 0, "mem": 1, "imem": 2}, case["name"],
                    offnatural=False)
        pg.movi(P.R_IDX, 0)
        pg.movi(P.R_SENT, P.SENT_IMM)
        S.device_store(pg.E, P.R_IDX, 10, case["slot"], P.R_SENT,
                       salt=case["name"], offnatural=False)
        pg.body_start = pg.E.off
        pg.body_end = pg.E.off
        return pg, pg.finish(carrier_len)
    if case["role"] == "destination":
        return destination_program(case, slots, carrier_len)
    return source_program(case, slots, carrier_len)


def read_word(res, slot, idx_off):
    surf = res.get("surf", {}).get(slot)
    off = S.store_byte_offset(0, idx_off)
    if surf is None or off + 4 > len(surf):
        return None
    return struct.unpack("<I", surf[off:off + 4])[0]


def score234(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] != "isel_reach":
        return rec
    observed = {name: read_word(res, slots["out"], off)
                for name, off in OBS.items()}
    expected = pg.probe_expected
    probe = {
        "role": case["role"], "register": case["register"],
        "oracle_mode": case["oracle_mode"], "observed": observed,
        "expected": expected,
        "semantic_decidable": bool(
            rec.get("status") == "OK"
            and observed["post_destination"] is not None
            and rec.get("sentinel_ok")),
    }
    if case["role"] != "destination":
        candidates = expected.get("candidate_results", {})
        got = observed["post_destination"]
        probe["candidate_results"] = candidates
        probe["matching_models"] = sorted(k for k, v in candidates.items() if got == v)
    rec["isel_reach_probe"] = probe
    return rec


def main():
    B.C = sys.modules[__name__]
    B.score = score234
    return B.main()


if __name__ == "__main__":
    raise SystemExit(main())
