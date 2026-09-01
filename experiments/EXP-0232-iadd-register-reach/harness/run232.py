#!/usr/bin/env python3
"""EXP-0232: canonical iadd2 per-role register reach on G17P."""

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
spec = importlib.util.spec_from_file_location("exp0232_isadb", PINNED)
ISADB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ISADB)
assert Path(ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = ISADB
B.EXP = EXP
B.HERE = HERE
B.CARRIER = "carrier232.metal"

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
    for reg in range(32):
        out.append({
            "i": len(out), "name": "a_r%02d" % reg, "arm": "A",
            "kind": "iadd_reach", "role": "source_a", "register": reg,
            "expect_match": True, "predicted_bucket": "exact",
            "oracle_mode": "exact",
        })
    for reg in range(64):
        out.append({
            "i": len(out), "name": "b_r%02d" % reg, "arm": "B",
            "kind": "iadd_reach", "role": "source_b", "register": reg,
            "expect_match": True, "predicted_bucket": "exact",
            "oracle_mode": "exact",
        })
    for reg in range(95):
        out.append({
            "i": len(out), "name": "d_r%02d" % reg, "arm": "D",
            "kind": "iadd_reach", "role": "destination", "register": reg,
            "expect_match": True, "predicted_bucket": "exact",
            "oracle_mode": "exact",
        })
    for name, role, reg in (("ctl_wrong_a", "source_a", 31),
                            ("ctl_wrong_d", "destination", 94)):
        out.append({
            "i": len(out), "name": name, "arm": "CTL",
            "kind": "iadd_reach", "role": role, "register": reg,
            "expect_match": False, "predicted_bucket": "refute",
            "oracle_mode": "wrong",
        })
    return out


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0232 PRE_REGISTRATION", note)


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


def emit_iadd(pg, destination, source_a, source_b, predicted):
    pg.E.emit("iadd2", {
        "addsub": fv(1, "canonical add"),
        "lenbit": fv(1, "canonical ten-byte form"),
        "srcB_reg_hi": fv(0, "canonical register form"),
        "b2_bit0": fv(0, "canonical 32-bit point"),
        "store_en": fv(1, "publish destination"),
        "b2_fmt": fv(0x15, "canonical 32-bit format"),
        "dst": fv((destination << 1) | 1, "32-bit destination descriptor"),
        "opmode": fv(2, "canonical register mode"),
        "srcB_imm": fv(source_b << 2, "second source reg<<2"),
        "srcB_imm_hi": fv(0, "canonical register form"),
        "srcB_ext": fv(source_a << 2, "first source reg<<2"),
        "srcA": fv(0xA8, "canonical operand control"),
        "opc_tail": fv(0x11, "retain both sources"),
        "opc_tail2": fv(0x05, "canonical tail"),
    })
    pg._pending = None
    pg.set_reg(destination, predicted)


def seed_map(pg, load_index, store_index, seeds):
    for n, (reg, codeword_number) in enumerate(seeds.items()):
        generated_load(pg, load_index, store_index, reg, codeword_number,
                       1100 + n, "seed_r%02d" % reg)


def source_program(case, slots, carrier_len):
    reg = case["register"]
    alias16, alias32 = reg % 16, reg % 32
    relevant = {reg, alias16, alias32}
    zero_reg = next(r for r in range(8) if r not in relevant)
    destination = next(r for r in range(8, 12) if r not in relevant)
    relevant.update((zero_reg, destination))
    store_index, load_index = choose_indices(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")

    seeds = {}
    seeds[alias16] = 116
    seeds[alias32] = 117
    seeds[reg] = reg
    seeds[destination] = 120
    seed_map(pg, load_index, store_index, seeds)
    pg.movi(zero_reg, 0)

    observe(pg, store_index, reg, OBS["pre_target"], "pre_target")
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")
    observe(pg, store_index, alias16, OBS["pre_alias16"], "pre_alias16")
    observe(pg, store_index, alias32, OBS["pre_alias32"], "pre_alias32")
    observe(pg, store_index, reg, OBS["pre_alias64"], "pre_alias64")

    exact = pg.rbits(reg)
    predicted = exact if case["oracle_mode"] == "exact" else exact ^ 0xFFFFFFFF
    pg.body_start = pg.E.off
    if case["role"] == "source_a":
        emit_iadd(pg, destination, reg, zero_reg, predicted)
    else:
        emit_iadd(pg, destination, zero_reg, reg, predicted)
    pg.body_end = pg.E.off

    observe(pg, store_index, destination, OBS["post_destination"], "post_destination")
    observe(pg, store_index, reg, OBS["post_target"], "post_target")
    observe(pg, store_index, alias16, OBS["post_alias16"], "post_alias16")
    observe(pg, store_index, alias32, OBS["post_alias32"], "post_alias32")
    observe(pg, store_index, reg, OBS["post_alias64"], "post_alias64")
    pg.probe_expected = {
        "exact_result": exact,
        "alias16_result": pg.rbits(alias16),
        "alias32_result": pg.rbits(alias32),
        "destination": destination,
    }
    return pg, pg.finish(carrier_len)


def destination_program(case, slots, carrier_len):
    destination = case["register"]
    aliases = {destination % 16, destination % 32, destination % 64}
    relevant = aliases | {destination, 0, 1}
    store_index, load_index = choose_indices(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")

    seeds = {}
    seeds[destination % 16] = 116
    seeds[destination % 32] = 117
    seeds[destination % 64] = 118
    seeds[0] = 0
    seeds[1] = 1
    if destination not in (0, 1):
        seeds[destination] = 120
    seed_map(pg, load_index, store_index, seeds)
    for name, reg in (("pre_target", destination),
                      ("pre_alias16", destination % 16),
                      ("pre_alias32", destination % 32),
                      ("pre_alias64", destination % 64)):
        observe(pg, store_index, reg, OBS[name], name)
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")

    result = (pg.rbits(0) + pg.rbits(1)) & 0xFFFFFFFF
    predicted = result if case["oracle_mode"] == "exact" else result ^ 0xFFFFFFFF
    pg.body_start = pg.E.off
    emit_iadd(pg, destination, 0, 1, predicted)
    pg.body_end = pg.E.off

    for name, reg in (("post_destination", destination),
                      ("post_alias16", destination % 16),
                      ("post_alias32", destination % 32),
                      ("post_alias64", destination % 64),
                      ("post_source0", 0), ("post_source1", 1)):
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


def score232(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] != "iadd_reach":
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
    if case["role"].startswith("source"):
        candidates = {
            "exact": observed["pre_target"],
            "mod16": observed["pre_alias16"],
            "mod32": observed["pre_alias32"],
            "zero": 0,
        }
        got = observed["post_destination"]
        probe["candidate_results"] = candidates
        probe["matching_models"] = sorted(k for k, v in candidates.items() if got == v)
    rec["iadd_reach_probe"] = probe
    return rec


def main():
    B.C = sys.modules[__name__]
    B.score = score232
    return B.main()


if __name__ == "__main__":
    raise SystemExit(main())
