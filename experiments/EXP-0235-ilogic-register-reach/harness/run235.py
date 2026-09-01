#!/usr/bin/env python3
"""EXP-0235: canonical ilogic per-role register reach on G17P."""

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
spec = importlib.util.spec_from_file_location("exp0235_isadb", PINNED)
ISADB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ISADB)
assert Path(ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = ISADB
B.EXP = EXP
B.HERE = HERE
B.CARRIER = "carrier235.metal"

SPARSE_REGS = (0, 23, 24, 31, 32, 47, 48, 63,
               64, 79, 80, 95, 96, 111, 112, 127)

OBS = {
    "pre_target": 1000,
    "pre_destination": 1001,
    "pre_alias16": 1002,
    "pre_alias32": 1003,
    "pre_alias64": 1004,
    "pre_other": 1005,
    "post_destination": 1010,
    "post_target": 1011,
    "post_alias16": 1012,
    "post_alias32": 1013,
    "post_alias64": 1014,
    "post_other": 1015,
}


def build_cases(include_hazard=False, full=False):
    out = [{
        "i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
        "kind": "s0_slot", "slot": slot, "expect_match": True,
        "predicted_bucket": "measure", "expect_sentinel": False,
    } for slot in range(8)]
    source_regs = range(128) if full else SPARSE_REGS
    for role, arm in (("semantic_a", "A"), ("semantic_b", "B")):
        for reg in source_regs:
            out.append({
                "i": len(out), "name": "%s_r%03d" % (arm.lower(), reg),
                "arm": arm, "kind": "ilogic_reach", "role": role,
                "register": reg, "expect_match": True,
                "predicted_bucket": "exact", "oracle_mode": "exact",
                "oracle_model": "exact" if reg < 64 else "mod64",
            })
    for reg in range(16):
        out.append({
            "i": len(out), "name": "d_r%02d" % reg, "arm": "D",
            "kind": "ilogic_reach", "role": "destination", "register": reg,
            "expect_match": True, "predicted_bucket": "exact",
            "oracle_mode": "exact", "oracle_model": "exact",
        })
    for name, role, reg in (("ctl_wrong_a", "semantic_a", 63),
                            ("ctl_wrong_d", "destination", 15)):
        out.append({
            "i": len(out), "name": name, "arm": "CTL",
            "kind": "ilogic_reach", "role": role, "register": reg,
            "expect_match": False, "predicted_bucket": "refute",
            "oracle_mode": "wrong", "oracle_model": "exact",
        })
    return out


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0235 PRE_REGISTRATION", note)


def pack_word(bits):
    return list(struct.pack("<I", bits & 0xFFFFFFFF))


def choose_indices(excluded):
    available = [r for r in (13, 14, 15) if r not in excluded]
    if len(available) < 2:
        raise AssertionError((excluded, available))
    return available[0], available[1]


def choose_low(excluded, count):
    available = [r for r in range(12) if r not in excluded]
    if len(available) < count:
        raise AssertionError((excluded, available, count))
    return available[:count]


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


def observe(pg, store_index, reg, out_off, tag):
    generated_store(pg, store_index, reg, out_off, pg.rbits(reg), tag)


def seed_map(pg, load_index, store_index, seeds):
    for n, (reg, codeword_number) in enumerate(seeds.items()):
        generated_load(pg, load_index, store_index, reg, codeword_number,
                       1100 + n, "seed_r%02d" % reg)


def emit_xor(pg, destination, semantic_a, semantic_b):
    # EXP-0226: semantic A occupies db srcB, semantic B occupies db srcA.
    pg.E.emit("ilogic", {
        "dst": fv(destination, "four-bit destination GPR"),
        "srcA": fv((semantic_b << 1) | 1, "semantic-B register descriptor"),
        "op_base": fv(0, "EXP-0226 XOR LUT base"),
        "srcB": fv((semantic_a << 1) | 1, "semantic-A register descriptor"),
        "lut_a_sel": fv(2, "EXP-0226 XOR LUT selector A"),
        "lut_a_free": fv(0, "canonical selector high bits"),
        "lut_a_z": fv(0, "canonical selector zero tail"),
        "lut_b": fv(8, "EXP-0226 XOR LUT selector B"),
        "z6": fv(0, "canonical tail"),
        "outmod": fv(0x80, "canonical source-read enable"),
        "z8": fv(0, "canonical tail"),
        "z9": fv(0, "canonical tail"),
    })
    pg._pending = None


def source_program(case, slots, carrier_len):
    reg = case["register"]
    alias16, alias32, alias64 = reg % 16, reg % 32, reg % 64
    relevant = {alias16, alias32, alias64}
    if reg < 96:
        relevant.add(reg)
    destination, other = choose_low(relevant, 2)
    relevant.update((destination, other))
    store_index, load_index = choose_indices(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")

    seeds = {alias16: 116, alias32: 117, alias64: 118}
    if reg < 96:
        seeds[reg] = reg
    seeds[destination] = 120
    seeds[other] = 121
    seed_map(pg, load_index, store_index, seeds)

    if reg < 96:
        observe(pg, store_index, reg, OBS["pre_target"], "pre_target")
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")
    observe(pg, store_index, alias16, OBS["pre_alias16"], "pre_alias16")
    observe(pg, store_index, alias32, OBS["pre_alias32"], "pre_alias32")
    observe(pg, store_index, alias64, OBS["pre_alias64"], "pre_alias64")
    observe(pg, store_index, other, OBS["pre_other"], "pre_other")

    before = dict(pg.reg)
    models = {}
    for model, effective in (("exact", reg if reg < 96 else None),
                             ("mod16", alias16), ("mod32", alias32),
                             ("mod64", alias64)):
        if effective is None or before.get(effective) is None:
            models[model] = None
            continue
        source_value = before[effective]
        result = source_value ^ before[other]
        state = {
            "post_destination": result,
            "post_target": (0 if reg < 96 and effective == reg else before.get(reg)),
            "post_alias16": 0 if effective == alias16 else before[alias16],
            "post_alias32": 0 if effective == alias32 else before[alias32],
            "post_alias64": 0 if effective == alias64 else before[alias64],
            "post_other": 0,
        }
        models[model] = state

    oracle_model = case["oracle_model"]
    predicted_state = models[oracle_model]
    if predicted_state is None:
        raise AssertionError((case, models))
    predicted_result = predicted_state["post_destination"]
    if case["oracle_mode"] == "wrong":
        predicted_result ^= 0xFFFFFFFF

    if case["role"] == "semantic_a":
        semantic_a, semantic_b = reg, other
    else:
        semantic_a, semantic_b = other, reg
    pg.body_start = pg.E.off
    emit_xor(pg, destination, semantic_a, semantic_b)
    pg.body_end = pg.E.off

    effective = reg if oracle_model == "exact" else alias64
    pg.set_reg(effective, 0)
    pg.set_reg(other, 0)
    pg.set_reg(destination, predicted_result)

    observe(pg, store_index, destination, OBS["post_destination"], "post_destination")
    if reg < 96:
        observe(pg, store_index, reg, OBS["post_target"], "post_target")
    observe(pg, store_index, alias16, OBS["post_alias16"], "post_alias16")
    observe(pg, store_index, alias32, OBS["post_alias32"], "post_alias32")
    observe(pg, store_index, alias64, OBS["post_alias64"], "post_alias64")
    observe(pg, store_index, other, OBS["post_other"], "post_other")
    pg.probe_expected = {
        "oracle_model": oracle_model,
        "candidate_states": models,
        "destination": destination,
        "other": other,
    }
    return pg, pg.finish(carrier_len)


def destination_program(case, slots, carrier_len):
    destination = case["register"]
    semantic_a, semantic_b = choose_low({destination}, 2)
    relevant = {destination, semantic_a, semantic_b}
    store_index, load_index = choose_indices(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")
    seeds = {destination: 120, semantic_a: 121, semantic_b: 122}
    seed_map(pg, load_index, store_index, seeds)
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")
    observe(pg, store_index, semantic_a, OBS["pre_alias16"], "pre_source_a")
    observe(pg, store_index, semantic_b, OBS["pre_alias32"], "pre_source_b")
    result = pg.rbits(semantic_a) ^ pg.rbits(semantic_b)
    predicted = result if case["oracle_mode"] == "exact" else result ^ 0xFFFFFFFF
    pg.body_start = pg.E.off
    emit_xor(pg, destination, semantic_a, semantic_b)
    pg.body_end = pg.E.off
    pg.set_reg(semantic_a, 0)
    pg.set_reg(semantic_b, 0)
    pg.set_reg(destination, predicted)
    observe(pg, store_index, destination, OBS["post_destination"], "post_destination")
    observe(pg, store_index, semantic_a, OBS["post_alias16"], "post_source_a")
    observe(pg, store_index, semantic_b, OBS["post_alias32"], "post_source_b")
    pg.probe_expected = {
        "oracle_model": "exact", "destination": destination,
        "other": semantic_b, "candidate_states": {},
    }
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


def score235(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] != "ilogic_reach":
        return rec
    observed = {name: read_word(res, slots["out"], off)
                for name, off in OBS.items()}
    expected = pg.probe_expected
    probe = {
        "role": case["role"], "register": case["register"],
        "oracle_mode": case["oracle_mode"],
        "oracle_model": case.get("oracle_model", "exact"),
        "observed": observed, "expected": expected,
        "semantic_decidable": bool(rec.get("status") == "OK"
                                    and observed["post_destination"] is not None
                                    and rec.get("sentinel_ok")),
    }
    matching = []
    for model, state in expected.get("candidate_states", {}).items():
        if state is None:
            continue
        if all(observed.get(k) == v for k, v in state.items()
               if v is not None and k in observed):
            matching.append(model)
    probe["matching_models"] = sorted(matching)
    rec["ilogic_reach_probe"] = probe
    return rec


def main():
    B.C = sys.modules[__name__]
    B.score = score235
    return B.main()


if __name__ == "__main__":
    raise SystemExit(main())
