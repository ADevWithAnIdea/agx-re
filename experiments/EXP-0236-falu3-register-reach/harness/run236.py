#!/usr/bin/env python3
"""EXP-0236: materialized canonical falu3 per-role register reach on G17P."""

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
spec = importlib.util.spec_from_file_location("exp0236_isadb", PINNED)
ISADB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ISADB)
assert Path(ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = ISADB
B.EXP = EXP
B.HERE = HERE
B.CARRIER = "carrier236.metal"

SPARSE_REGS = (0, 15, 16, 18, 19, 20, 23, 24, 31, 32, 47,
               48, 63, 64, 79, 80, 95, 96, 111, 112, 127)

OBS = {
    "pre_target": 1200,
    "pre_destination": 1201,
    "pre_alias16": 1202,
    "pre_alias32": 1203,
    "pre_alias64": 1204,
    "pre_other_a": 1205,
    "pre_other_b": 1206,
    "post_destination": 1210,
    "post_target": 1211,
    "post_alias16": 1212,
    "post_alias32": 1213,
    "post_alias64": 1214,
    "post_other_a": 1215,
    "post_other_b": 1216,
}


def build_cases(include_hazard=False, full=False):
    out = [{
        "i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
        "kind": "s0_slot", "slot": slot, "expect_match": True,
        "predicted_bucket": "measure", "expect_sentinel": False,
    } for slot in range(8)]
    regs = range(128) if full else SPARSE_REGS
    for role, arm in (("src_a", "A"), ("src_b", "B"), ("src_c", "C")):
        for reg in regs:
            out.append({
                "i": len(out), "name": "%s_r%03d" % (arm.lower(), reg),
                "arm": arm, "kind": "falu3_reach", "role": role,
                "register": reg, "expect_match": True,
                "predicted_bucket": "exact", "oracle_mode": "exact",
                "oracle_model": "exact" if reg < 64 else "mod64",
            })
    for reg in range(16):
        out.append({
            "i": len(out), "name": "d_r%02d" % reg, "arm": "D",
            "kind": "falu3_reach", "role": "destination", "register": reg,
            "expect_match": True, "predicted_bucket": "exact",
            "oracle_mode": "exact", "oracle_model": "exact",
        })
    for name, role, reg in (("ctl_wrong_a", "src_a", 63),
                            ("ctl_wrong_d", "destination", 15)):
        out.append({
            "i": len(out), "name": name, "arm": "CTL",
            "kind": "falu3_reach", "role": role, "register": reg,
            "expect_match": False, "predicted_bucket": "refute",
            "oracle_mode": "wrong", "oracle_model": "exact",
        })
    return out


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0236 PRE_REGISTRATION", note)


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


def generated_load_float(pg, load_index, store_index, reg, word, out_off, tag):
    value = P.fbits(P.MEM[word])
    previous = pg.rbits(reg)
    S.device_load(pg.E, load_index, word, 3, pg.slots["mem"], reg,
                  salt=tag + "_load", offnatural=False, ld_format=17,
                  extmode=2 * reg, addr_mode=0x44)
    pg.set_reg(reg, value)
    pg._pending = (reg, previous)
    # The accepting store is intentional: it performs the load's first handoff
    # and leaves a materialized, retained data GPR before falu3 executes.
    generated_store(pg, store_index, reg, out_off, value, tag + "_materialize",
                    addr_mode=S.DS_ADDRMODE_LOADFWD)
    return value


def observe(pg, store_index, reg, out_off, tag):
    generated_store(pg, store_index, reg, out_off, pg.rbits(reg), tag)


def seed_map(pg, load_index, store_index, seeds):
    for n, (reg, word) in enumerate(seeds.items()):
        generated_load_float(pg, load_index, store_index, reg, word,
                             1400 + n, "seed_r%02d" % reg)


def fma_bits(a_bits, b_bits, c_bits):
    a, b, c = S.bits_f32(a_bits), S.bits_f32(b_bits), S.bits_f32(c_bits)
    return P.fbits(S.f32(a * b + c))


def emit_fma(pg, destination, src_a, src_b, src_c):
    pg.E.emit("falu3", {
        "dst": fv(destination, "four-bit destination GPR"),
        "srcA": fv((src_a << 1) | 1, "source-A register descriptor"),
        "op": fv(0x06, "retained-source FP32 FMA"),
        "srcB": fv((src_b << 1) | 1, "source-B register descriptor"),
        "ctrl_len": fv(0x01, "canonical eight-byte retained-C control"),
        "srcC": fv(src_c << 1, "source-C register descriptor"),
        "ctrl": fv(0x02, "canonical FMA control"),
        "srcmods": fv(0xc0, "canonical ordinary/materialized-source mode"),
    })
    pg._pending = None


def source_program(case, slots, carrier_len):
    reg = case["register"]
    alias16, alias32, alias64 = reg % 16, reg % 32, reg % 64
    relevant = {alias16, alias32, alias64}
    if reg < 96:
        relevant.add(reg)
    destination, other_a, other_b = choose_low(relevant, 3)
    relevant.update((destination, other_a, other_b))
    store_index, load_index = choose_indices(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")

    seeds = {alias16: 116, alias32: 117, alias64: 118}
    if reg < 96:
        seeds[reg] = 119
    seeds[destination] = 120
    seeds[other_a] = 121
    seeds[other_b] = 122
    seed_map(pg, load_index, store_index, seeds)

    if reg < 96:
        observe(pg, store_index, reg, OBS["pre_target"], "pre_target")
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")
    observe(pg, store_index, alias16, OBS["pre_alias16"], "pre_alias16")
    observe(pg, store_index, alias32, OBS["pre_alias32"], "pre_alias32")
    observe(pg, store_index, alias64, OBS["pre_alias64"], "pre_alias64")
    observe(pg, store_index, other_a, OBS["pre_other_a"], "pre_other_a")
    observe(pg, store_index, other_b, OBS["pre_other_b"], "pre_other_b")

    before = dict(pg.reg)
    models = {}
    for model, effective in (("exact", reg if reg < 96 else None),
                             ("mod16", alias16), ("mod32", alias32),
                             ("mod64", alias64)):
        if effective is None or before.get(effective) is None:
            models[model] = None
            continue
        vals = {"src_a": before[other_a], "src_b": before[other_b],
                "src_c": before[other_b]}
        if case["role"] == "src_a":
            vals.update(src_a=before[effective], src_b=before[other_a],
                        src_c=before[other_b])
        elif case["role"] == "src_b":
            vals.update(src_a=before[other_a], src_b=before[effective],
                        src_c=before[other_b])
        else:
            vals.update(src_a=before[other_a], src_b=before[other_b],
                        src_c=before[effective])
        result = fma_bits(vals["src_a"], vals["src_b"], vals["src_c"])
        models[model] = {
            "post_destination": result,
            "post_target": before.get(reg),
            "post_alias16": before[alias16],
            "post_alias32": before[alias32],
            "post_alias64": before[alias64],
            "post_other_a": before[other_a],
            "post_other_b": before[other_b],
        }

    oracle_model = case["oracle_model"]
    predicted_state = dict(models[oracle_model])
    predicted_result = predicted_state["post_destination"]
    if case["oracle_mode"] == "wrong":
        predicted_result ^= 0x00800000
        predicted_state["post_destination"] = predicted_result

    if case["role"] == "src_a":
        src_a, src_b, src_c = reg, other_a, other_b
    elif case["role"] == "src_b":
        src_a, src_b, src_c = other_a, reg, other_b
    else:
        src_a, src_b, src_c = other_a, other_b, reg
    pg.body_start = pg.E.off
    emit_fma(pg, destination, src_a, src_b, src_c)
    pg.body_end = pg.E.off
    pg.set_reg(destination, predicted_result)

    observe(pg, store_index, destination, OBS["post_destination"], "post_destination")
    if reg < 96:
        observe(pg, store_index, reg, OBS["post_target"], "post_target")
    observe(pg, store_index, alias16, OBS["post_alias16"], "post_alias16")
    observe(pg, store_index, alias32, OBS["post_alias32"], "post_alias32")
    observe(pg, store_index, alias64, OBS["post_alias64"], "post_alias64")
    observe(pg, store_index, other_a, OBS["post_other_a"], "post_other_a")
    observe(pg, store_index, other_b, OBS["post_other_b"], "post_other_b")
    pg.probe_expected = {
        "oracle_model": oracle_model, "candidate_states": models,
        "destination": destination, "other_a": other_a, "other_b": other_b,
    }
    return pg, pg.finish(carrier_len)


def destination_program(case, slots, carrier_len):
    destination = case["register"]
    src_a, src_b, src_c = choose_low({destination}, 3)
    relevant = {destination, src_a, src_b, src_c}
    store_index, load_index = choose_indices(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")
    seeds = {destination: 119, src_a: 120, src_b: 121, src_c: 122}
    seed_map(pg, load_index, store_index, seeds)
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")
    observe(pg, store_index, src_a, OBS["pre_alias16"], "pre_source_a")
    observe(pg, store_index, src_b, OBS["pre_alias32"], "pre_source_b")
    observe(pg, store_index, src_c, OBS["pre_alias64"], "pre_source_c")
    result = fma_bits(pg.rbits(src_a), pg.rbits(src_b), pg.rbits(src_c))
    predicted = result if case["oracle_mode"] == "exact" else result ^ 0x00800000
    pg.body_start = pg.E.off
    emit_fma(pg, destination, src_a, src_b, src_c)
    pg.body_end = pg.E.off
    pg.set_reg(destination, predicted)
    observe(pg, store_index, destination, OBS["post_destination"], "post_destination")
    observe(pg, store_index, src_a, OBS["post_alias16"], "post_source_a")
    observe(pg, store_index, src_b, OBS["post_alias32"], "post_source_b")
    observe(pg, store_index, src_c, OBS["post_alias64"], "post_source_c")
    pg.probe_expected = {"oracle_model": "exact", "candidate_states": {},
                         "destination": destination}
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


def score236(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] != "falu3_reach":
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
    rec["falu3_reach_probe"] = probe
    return rec


def main():
    B.C = sys.modules[__name__]
    B.score = score236
    return B.main()


if __name__ == "__main__":
    raise SystemExit(main())
