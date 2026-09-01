#!/usr/bin/env python3
"""EXP-0239: canonical cvt_i2f register reach and lifecycle on G17P."""

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
spec = importlib.util.spec_from_file_location("exp0239_isadb", PINNED)
ISADB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ISADB)
assert Path(ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = ISADB
B.EXP = EXP
B.HERE = HERE
B.CARRIER = "carrier239.metal"

ALIAS_REGS = (0, 15, 16, 31, 32, 47, 48, 63)
OBS = {
    "pre_target": 1200,
    "pre_destination": 1201,
    "pre_alias16": 1202,
    "pre_alias32": 1203,
    "pre_alias64": 1204,
    "post_target": 1210,
    "post_destination": 1211,
    "post_alias16": 1212,
    "post_alias32": 1213,
    "post_alias64": 1214,
}


def build_cases(include_hazard=False, full=False):
    del full
    out = [{
        "i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
        "kind": "s0_slot", "slot": slot, "expect_match": True,
        "predicted_bucket": "measure", "expect_sentinel": False,
    } for slot in range(8)]
    for code in range(256):
        out.append({
            "i": len(out), "name": "s_v%03d" % code, "arm": "S",
            "kind": "cvt_i2f_reach", "role": "source", "code": code,
            "register": code >> 2, "expect_match": True,
            "predicted_bucket": "exact", "oracle_mode": "exact",
        })
    for code in range(192):
        out.append({
            "i": len(out), "name": "d_v%03d" % code, "arm": "D",
            "kind": "cvt_i2f_reach", "role": "destination", "code": code,
            "register": code >> 1, "expect_match": True,
            "predicted_bucket": "exact", "oracle_mode": "exact",
        })
    for reg in ALIAS_REGS:
        out.append({
            "i": len(out), "name": "l_r%02d" % reg, "arm": "L",
            "kind": "cvt_i2f_reach", "role": "alias", "code": reg,
            "register": reg, "expect_match": True,
            "predicted_bucket": "exact", "oracle_mode": "exact",
        })
    for name, role, code in (("ctl_wrong_s", "source", 252),
                             ("ctl_wrong_d", "destination", 190)):
        out.append({
            "i": len(out), "name": name, "arm": "CTL",
            "kind": "cvt_i2f_reach", "role": role, "code": code,
            "register": code >> (2 if role == "source" else 1),
            "expect_match": False, "predicted_bucket": "refute",
            "oracle_mode": "wrong",
        })
    if include_hazard:
        out.append({
            "i": len(out), "name": "d_invalid_192", "arm": "X",
            "kind": "cvt_i2f_boundary", "role": "destination_invalid",
            "code": 192, "register": 96, "expect_match": False,
            "predicted_bucket": "corrupt", "oracle_mode": "fault",
        })
    return out


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0239 PRE_REGISTRATION", note)


def pack_word(bits):
    return list(struct.pack("<I", bits & 0xFFFFFFFF))


def choose_scaffold(excluded):
    available = [r for r in (15, 14, 13, 12, 11, 10, 9, 8, 7, 6)
                 if r not in excluded]
    if len(available) < 3:
        raise AssertionError((excluded, available))
    return available[0], available[1], available[2]


def choose_low(excluded):
    for reg in range(16):
        if reg not in excluded:
            return reg
    raise AssertionError(excluded)


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


def generated_load_int(pg, load_index, store_index, reg, word, out_off, tag):
    value = P.IMEM[word] & 0xFFFFFFFF
    previous = pg.rbits(reg)
    S.device_load(pg.E, load_index, word, 3, pg.slots["imem"], reg,
                  salt=tag + "_load", offnatural=False, ld_format=17,
                  extmode=2 * reg, addr_mode=0x44)
    pg.set_reg(reg, value)
    pg._pending = (reg, previous)
    generated_store(pg, store_index, reg, out_off, value, tag + "_materialize",
                    addr_mode=S.DS_ADDRMODE_LOADFWD)
    return value


def observe(pg, store_index, reg, out_off, tag):
    generated_store(pg, store_index, reg, out_off, pg.rbits(reg), tag)


def seed_word(reg):
    # IMEM[j]=j below 900. These distinct small positive I32 values convert exactly.
    return 257 + reg


def seed_map(pg, load_index, store_index, regs):
    for n, reg in enumerate(sorted(regs)):
        generated_load_int(pg, load_index, store_index, reg, seed_word(reg),
                           1400 + n, "seed_r%02d" % reg)


def i32_to_f32_bits(bits):
    value = bits if bits < 0x80000000 else bits - 0x100000000
    return P.fbits(float(value))


def emit_cvt_i2f(pg, destination_code, source_code):
    pg.E.emit("cvt_i2f", {
        "mode": fv(0x56, "canonical materialized-source mode"),
        "dst": fv(destination_code, "destination descriptor byte"),
        "src_class": fv(0x02, "canonical signed-I32 source class"),
        "src": fv(source_code, "source descriptor byte"),
        "cvtop": fv(0xac, "canonical 32-bit integer-to-float conversion"),
        "signflag": fv(0x60, "canonical signed source and FP32 destination"),
    })
    pg._pending = None


def setup(case, source, destination, slots):
    relevant = {source, destination, source % 16, source % 32, source % 64,
                destination % 16, destination % 32, destination % 64}
    store_index, load_index, sentinel_reg = choose_scaffold(relevant)
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(sentinel_reg, P.SENT_IMM)
    pg.store(sentinel_reg, P.SENT_OFF, index_reg=store_index, tag="sentinel")
    return pg, store_index, load_index


def reach_program(case, slots, carrier_len):
    role, target = case["role"], case["register"]
    if role == "source":
        source = target
        destination = choose_low({source, source % 16, source % 32, source % 64})
        source_code, destination_code = case["code"], destination << 1
    elif role == "destination":
        destination = target
        source = choose_low({destination, destination % 16, destination % 32,
                             destination % 64})
        source_code, destination_code = source << 2, case["code"]
    elif role == "alias":
        source = destination = target
        source_code, destination_code = source << 2, destination << 1
    else:
        raise AssertionError(role)

    pg, store_index, load_index = setup(case, source, destination, slots)
    aliases = {target, target % 16, target % 32, target % 64, source, destination}
    seed_map(pg, load_index, store_index, aliases)

    observe(pg, store_index, target, OBS["pre_target"], "pre_target")
    observe(pg, store_index, destination, OBS["pre_destination"], "pre_destination")
    observe(pg, store_index, target % 16, OBS["pre_alias16"], "pre_alias16")
    observe(pg, store_index, target % 32, OBS["pre_alias32"], "pre_alias32")
    observe(pg, store_index, target % 64, OBS["pre_alias64"], "pre_alias64")

    before = dict(pg.reg)
    result = i32_to_f32_bits(before[source])
    predicted = result if case["oracle_mode"] == "exact" else result ^ 0x00000001
    pg.body_start = pg.E.off
    emit_cvt_i2f(pg, destination_code, source_code)
    pg.body_end = pg.E.off
    pg.set_reg(source, 0)
    pg.set_reg(destination, predicted)

    observe(pg, store_index, target, OBS["post_target"], "post_target")
    observe(pg, store_index, destination, OBS["post_destination"], "post_destination")
    observe(pg, store_index, target % 16, OBS["post_alias16"], "post_alias16")
    observe(pg, store_index, target % 32, OBS["post_alias32"], "post_alias32")
    observe(pg, store_index, target % 64, OBS["post_alias64"], "post_alias64")
    pg.probe_expected = {
        "role": role, "register": target, "code": case["code"],
        "source": source, "destination": destination,
        "result": result, "source_post": pg.rbits(source),
    }
    return pg, pg.finish(carrier_len)


def boundary_program(case, slots, carrier_len):
    source = 0
    pg, store_index, load_index = setup(case, source, 1, slots)
    seed_map(pg, load_index, store_index, {source})
    observe(pg, store_index, source, OBS["pre_target"], "pre_source")
    pg.body_start = pg.E.off
    emit_cvt_i2f(pg, case["code"], source << 2)
    pg.body_end = pg.E.off
    pg.probe_expected = {
        "role": case["role"], "register": case["register"],
        "code": case["code"], "source": source,
        "expected_status": "CMDBUF_ERROR/ErrorHang",
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
    if case["kind"] == "cvt_i2f_boundary":
        return boundary_program(case, slots, carrier_len)
    return reach_program(case, slots, carrier_len)


def read_word(res, slot, idx_off):
    surf = res.get("surf", {}).get(slot)
    off = S.store_byte_offset(0, idx_off)
    if surf is None or off + 4 > len(surf):
        return None
    return struct.unpack("<I", surf[off:off + 4])[0]


def score239(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] == "cvt_i2f_boundary":
        rec["cvt_i2f_boundary_probe"] = {
            **pg.probe_expected,
            "errorhang": bool(rec.get("status") == "CMDBUF_ERROR"
                              and "ErrorHang" in rec.get("error", "")),
        }
        return rec
    if case["kind"] != "cvt_i2f_reach":
        return rec
    observed = {name: read_word(res, slots["out"], off)
                for name, off in OBS.items()}
    rec["cvt_i2f_reach_probe"] = {
        **pg.probe_expected,
        "oracle_mode": case["oracle_mode"],
        "observed": observed,
        "semantic_decidable": bool(rec.get("status") == "OK"
                                    and observed["post_destination"] is not None
                                    and rec.get("sentinel_ok")),
    }
    return rec


def main():
    B.C = sys.modules[__name__]
    B.score = score239
    return B.main()


if __name__ == "__main__":
    raise SystemExit(main())
