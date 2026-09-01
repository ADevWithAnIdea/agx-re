#!/usr/bin/env python3
"""EXP-0230: dense generated n3_mov source-register reach probe."""

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
spec = importlib.util.spec_from_file_location("exp0230_isadb", PINNED)
ISADB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ISADB)
assert Path(ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = ISADB

B.EXP = EXP
B.HERE = HERE
B.CARRIER = "carrier230.metal"

OBS = {
    "pre_dst": 1000,
    "pre_src": 1001,
    "pre_mod64": 1002,
    "post_dst": 1010,
    "post_src": 1011,
    "post_mod64": 1012,
    "low_base": 1020,
    "post_sentinel": 1040,
}


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0230 PRE_REGISTRATION", note)


def replace_half(word, half, value):
    shift = 16 * half
    return ((word & ~(0xFFFF << shift)) | ((value & 0xFFFF) << shift)) & 0xFFFFFFFF


def seed_value(reg, index_reg):
    return 0 if reg == index_reg else P.codeword(reg)


def source_value(model, source, index_reg):
    if model == "full96_zero_oob":
        return seed_value(source, index_reg) if source < 96 else 0
    if model == "mod64":
        return seed_value(source % 64, index_reg)
    if model == "low64_zero_high":
        return seed_value(source, index_reg) if source < 64 else 0
    if model == "mod96":
        return seed_value(source % 96, index_reg)
    raise AssertionError(model)


def expected_destination(model, source, source_half, destination_half, destination,
                         index_reg):
    src = source_value(model, source, index_reg)
    before = seed_value(destination, index_reg)
    return replace_half(before, destination_half, (src >> (16 * source_half)) & 0xFFFF)


def add_case(out, name, source, source_half, index_reg, control=False):
    destination = 3 if source == 2 else 2
    destination_half = 0
    out.append({
        "i": len(out), "name": name, "arm": "CTL" if control else "R1",
        "kind": "n3_reach", "source": source, "source_half": source_half,
        "destination": destination, "destination_half": destination_half,
        "index_reg": index_reg, "expect_match": not control,
        "predicted_bucket": "refute" if control else "exact",
        "oracle_source": 2 if control else source,
    })


def build_cases(include_hazard=False):
    out = [{
        "i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
        "kind": "s0_slot", "slot": slot, "expect_match": True,
        "predicted_bucket": "measure", "expect_sentinel": False,
    } for slot in range(8)]
    for index_reg in (14, 15):
        for source in range(128):
            for source_half in (0, 1):
                add_case(out, "r1_i%02d_s%03d_h%d" %
                         (index_reg, source, source_half), source, source_half,
                         index_reg)
    add_case(out, "ctl_wrong_source_i14", 1, 0, 14, control=True)
    add_case(out, "ctl_wrong_source_i15", 1, 1, 15, control=True)
    return out


def exact_store(pg, slots, index_reg, data_reg, idx_off, tag):
    """Store one exact architectural register through EXP-0221's G17P path."""
    S.device_store(pg.E, index_reg, idx_off, slots["out"], data_reg,
                   salt=tag, offnatural=False, extmode=2 * data_reg,
                   addr_mode=S.DS_ADDRMODE_ALU)
    bits = pg.rbits(data_reg)
    payload = None if bits is None else list(struct.pack("<I", bits))
    pg.writes.append(("out", S.store_byte_offset(0, idx_off), payload, tag))
    pg._pending = None
    pg.set_reg(index_reg, 0)


def emit_move(pg, case):
    source = case["source"]
    source_half = case["source_half"]
    destination = case["destination"]
    destination_half = case["destination_half"]
    pg.E.emit("n3_mov", {
        "dst": fv(destination, "four-bit destination r0..r15"),
        "srcA_reg": fv((source << 1) | source_half,
                        "dense eight-bit source/half descriptor"),
        "subform": fv(0x01, "canonical non-releasing half move"),
        "companion": fv(destination_half, "destination-half selector"),
    })
    model_source = case["oracle_source"]
    src = source_value("full96_zero_oob", model_source, case["index_reg"])
    before = pg.rbits(destination)
    value = (src >> (16 * source_half)) & 0xFFFF
    pg.set_reg(destination, replace_half(before, destination_half, value))
    pg._pending = None


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

    index_reg = case["index_reg"]
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(index_reg, 0)

    # Independent pre-body sentinel, then overwrite its register as part of the
    # ordinary all-register seed wave. The memory witness remains intact.
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=index_reg, tag="sentinel")

    for reg in range(96):
        if reg == index_reg:
            continue
        pg.load_i(reg, P.CODEWORD_BASE + reg, index_reg=index_reg,
                  salt="seed_r%02d" % reg)
    for n in range(64):
        pg.movi(index_reg, 0)

    destination = case["destination"]
    source = case["source"]
    exact_store(pg, slots, index_reg, destination, OBS["pre_dst"], "pre_dst")
    if source < 96:
        exact_store(pg, slots, index_reg, source, OBS["pre_src"], "pre_src")
    exact_store(pg, slots, index_reg, source % 64, OBS["pre_mod64"], "pre_mod64")

    pg.body_start = pg.E.off
    emit_move(pg, case)
    pg.body_end = pg.E.off

    exact_store(pg, slots, index_reg, destination, OBS["post_dst"], "post_dst")
    if source < 96:
        exact_store(pg, slots, index_reg, source, OBS["post_src"], "post_src")
    exact_store(pg, slots, index_reg, source % 64, OBS["post_mod64"], "post_mod64")
    for reg in range(16):
        exact_store(pg, slots, index_reg, reg, OBS["low_base"] + reg,
                    "low_r%02d" % reg)

    # End-of-body witness after every observation store. Destination has already
    # been snapshotted, so it is safe to reuse as the sentinel carrier.
    pg.movi(destination, 86)
    exact_store(pg, slots, index_reg, destination, OBS["post_sentinel"],
                "post_sentinel")
    return pg, pg.finish(carrier_len)


def read_word(rec, pg, res, slots, idx_off):
    surf = res.get("surf", {}).get(slots["out"])
    off = S.store_byte_offset(0, idx_off)
    if surf is None or off + 4 > len(surf):
        return None
    return struct.unpack("<I", surf[off:off + 4])[0]


def score230(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] != "n3_reach":
        return rec
    observed = {name: read_word(rec, pg, res, slots, off)
                for name, off in OBS.items() if name != "low_base"}
    observed["low"] = [read_word(rec, pg, res, slots, OBS["low_base"] + r)
                       for r in range(16)]
    rec["reach_probe"] = {
        "source": case["source"],
        "source_half": case["source_half"],
        "destination": case["destination"],
        "destination_half": case["destination_half"],
        "index_reg": case["index_reg"],
        "observed": observed,
        "expected_post_dst": {
            model: expected_destination(model, case["source"],
                                        case["source_half"],
                                        case["destination_half"],
                                        case["destination"],
                                        case["index_reg"])
            for model in ("full96_zero_oob", "mod64", "low64_zero_high", "mod96")
        },
    }
    rp = rec["reach_probe"]
    got = observed["post_dst"]
    rp["matching_models"] = sorted(
        model for model, want in rp["expected_post_dst"].items() if got == want)
    if case["source"] < 96:
        rp["seed_expected"] = seed_value(case["source"], case["index_reg"])
        rp["seed_ok"] = observed["pre_src"] == rp["seed_expected"]
    else:
        rp["seed_expected"] = None
        rp["seed_ok"] = True
    rp["post_sentinel_ok"] = observed["post_sentinel"] == 86
    rp["semantic_decidable"] = bool(
        rec.get("status") == "OK" and rp["seed_ok"] and rp["post_sentinel_ok"])
    return rec


def main():
    B.C = sys.modules[__name__]
    B.score = score230
    return B.main()


if __name__ == "__main__":
    raise SystemExit(main())
