#!/usr/bin/env python3
"""EXP-0231: generated device-memory transfer between GPR tiers."""

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
spec = importlib.util.spec_from_file_location("exp0231_isadb", PINNED)
ISADB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ISADB)
assert Path(ISADB._DB_JSON).resolve() == (PINNED.parent / "db.json").resolve()
S.isadb = ISADB

B.EXP = EXP
B.HERE = HERE
B.CARRIER = "carrier231.metal"

SOURCES = (0, 11, 16, 63, 64, 95)
DESTINATIONS = (1, 10, 17, 62, 65, 94)
GAPS = (0, 1, 4, 16)

R_STORE_INDEX = 14
R_LOAD_INDEX = 15
R_FILL = 13
STORE_INDEX_VALUE = 4
LOAD_INDEX_VALUE = 7
STORE_IDX_OFF = 199
LOAD_IDX_OFF = 793
SCRATCH_BYTE = 3200
assert S.store_byte_offset(STORE_INDEX_VALUE, STORE_IDX_OFF) == SCRATCH_BYTE
assert S.load_byte_offset(LOAD_INDEX_VALUE, LOAD_IDX_OFF, 3) == SCRATCH_BYTE

OBS = {
    "pre_source": 1000,
    "pre_destination": 1001,
    "pre_source_alias": 1002,
    "pre_destination_alias": 1003,
    "post_forward": 1010,
    "post_source": 1011,
    "post_destination": 1012,
    "post_source_alias": 1013,
    "post_destination_alias": 1014,
    "post_store_index": 1015,
    "post_load_index": 1016,
    "post_sentinel": 1020,
}

DEST_POISON = P.codeword(120)
DEST_ALIAS_POISON = P.codeword(117)
FILL_VALUES = tuple(v for v in range(80, 110) if v not in P.UNSAFE_IMM7)


def build_cases(include_hazard=False):
    out = [{
        "i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
        "kind": "s0_slot", "slot": slot, "expect_match": True,
        "predicted_bucket": "measure", "expect_sentinel": False,
    } for slot in range(8)]
    for gap in GAPS:
        for source in SOURCES:
            for destination in DESTINATIONS:
                out.append({
                    "i": len(out),
                    "name": "m_g%02d_s%02d_d%02d" % (gap, source, destination),
                    "arm": "M", "kind": "memory_transfer", "gap": gap,
                    "source": source, "destination": destination,
                    "oracle_mode": "exact", "expect_match": True,
                    "predicted_bucket": "exact",
                })
    for name, source, destination, mode in (
            ("ctl_wrong_store", 64, 65, "wrong_store"),
            ("ctl_wrong_load", 95, 94, "wrong_load")):
        out.append({
            "i": len(out), "name": name, "arm": "CTL",
            "kind": "memory_transfer", "gap": 0, "source": source,
            "destination": destination, "oracle_mode": mode,
            "expect_match": False, "predicted_bucket": "refute",
        })
    return out


def pack_word(bits):
    return list(struct.pack("<I", bits & 0xFFFFFFFF))


def generated_load(pg, base, index_reg, idx_off, destination, value, salt):
    """Emit a load and model its known value without the old r63 oracle cap."""
    previous = pg.rbits(destination)
    S.device_load(pg.E, index_reg, idx_off, 3, pg.slots[base], destination,
                  salt=salt, offnatural=False, ld_format=17,
                  extmode=2 * destination, addr_mode=0x44)
    pg.set_reg(destination, value)
    pg._pending = (destination, previous)


def generated_store(pg, base, index_reg, idx_off, source, value, salt,
                    addr_mode=S.DS_ADDRMODE_ALU):
    """Emit an exact scalar store, including r64..r95 source descriptors."""
    idx = pg.rbits(index_reg)
    S.device_store(pg.E, index_reg, idx_off, pg.slots[base], source,
                   salt=salt, offnatural=False, st_format=17,
                   extmode=2 * source, addr_mode=addr_mode)
    off = None if idx is None else S.store_byte_offset(idx, idx_off)
    pg.writes.append((base, off, pack_word(value), salt))
    pg._pending = None
    pg.set_reg(index_reg, 0)


def observe_forwarded_load(pg, source, idx_off, expected, tag):
    generated_store(pg, "out", R_STORE_INDEX, idx_off, source, expected, tag,
                    addr_mode=S.DS_ADDRMODE_LOADFWD)


def observe_register(pg, source, idx_off, tag):
    generated_store(pg, "out", R_STORE_INDEX, idx_off, source,
                    pg.rbits(source), tag)


def seed_register(pg, reg, codeword_number, observe_off, tag):
    value = P.codeword(codeword_number)
    generated_load(pg, "imem", R_LOAD_INDEX, P.CODEWORD_BASE + codeword_number,
                   reg, value, tag + "_load")
    observe_forwarded_load(pg, reg, observe_off, value, tag + "_fwd")
    return value


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

    source = case["source"]
    destination = case["destination"]
    source_alias = source % 64
    destination_alias = destination % 64
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(R_STORE_INDEX, 0)
    pg.movi(R_LOAD_INDEX, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=R_STORE_INDEX, tag="sentinel")

    if source_alias != source:
        seed_register(pg, source_alias, source_alias, OBS["pre_source_alias"],
                      "seed_source_alias")
    if destination_alias != destination:
        seed_register(pg, destination_alias, 117,
                      OBS["pre_destination_alias"], "seed_destination_alias")
    source_value = seed_register(pg, source, source, OBS["pre_source"],
                                 "seed_source")
    seed_register(pg, destination, 120, OBS["pre_destination"],
                  "seed_destination")

    # Low-register aliases are the register itself. Record the same pre-state
    # through a second independent store so all cases have identical channels.
    if source_alias == source:
        observe_register(pg, source_alias, OBS["pre_source_alias"],
                         "pre_source_alias")
    if destination_alias == destination:
        observe_register(pg, destination_alias, OBS["pre_destination_alias"],
                         "pre_destination_alias")

    pg.movi(R_STORE_INDEX, STORE_INDEX_VALUE)
    pg.movi(R_LOAD_INDEX, LOAD_INDEX_VALUE)
    pg.body_start = pg.E.off

    store_oracle = source_value
    if case["oracle_mode"] == "wrong_store":
        store_oracle ^= 0xFFFFFFFF
    generated_store(pg, "mem", R_STORE_INDEX, STORE_IDX_OFF, source,
                    store_oracle, "transfer_store")

    for n in range(case["gap"]):
        pg.movi(R_FILL, FILL_VALUES[n])

    before_destination = pg.rbits(destination)
    S.device_load(pg.E, R_LOAD_INDEX, LOAD_IDX_OFF, 3, slots["mem"], destination,
                  salt="transfer_load", offnatural=False, ld_format=17,
                  extmode=2 * destination, addr_mode=0x44)
    load_oracle = source_value
    if case["oracle_mode"] == "wrong_load":
        load_oracle ^= 0xFFFFFFFF
    pg.set_reg(destination, load_oracle)
    pg._pending = (destination, before_destination)
    pg.body_end = pg.E.off

    observe_forwarded_load(pg, destination, OBS["post_forward"], load_oracle,
                           "post_forward")
    observe_register(pg, source, OBS["post_source"], "post_source")
    observe_register(pg, destination, OBS["post_destination"],
                     "post_destination")
    observe_register(pg, source_alias, OBS["post_source_alias"],
                     "post_source_alias")
    observe_register(pg, destination_alias, OBS["post_destination_alias"],
                     "post_destination_alias")
    observe_register(pg, R_STORE_INDEX, OBS["post_store_index"],
                     "post_store_index")
    observe_register(pg, R_LOAD_INDEX, OBS["post_load_index"],
                     "post_load_index")
    observe_register(pg, P.R_SENT, OBS["post_sentinel"], "post_sentinel")
    return pg, pg.finish(carrier_len)


def read_word(res, slot, byte_off):
    surf = res.get("surf", {}).get(slot)
    if surf is None or byte_off + 4 > len(surf):
        return None
    return struct.unpack("<I", surf[byte_off:byte_off + 4])[0]


def score231(case, pg, prog, rows, bad, alias, res, base_state, oracle,
             slots, dispatched_ok):
    rec = BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                     oracle, slots, dispatched_ok)
    if case["kind"] != "memory_transfer":
        return rec
    out_slot = slots["out"]
    observed = {name: read_word(res, out_slot, S.store_byte_offset(0, off))
                for name, off in OBS.items()}
    observed["scratch"] = read_word(res, slots["mem"], SCRATCH_BYTE)
    source = case["source"]
    destination = case["destination"]
    source_value = P.codeword(source)
    initial_scratch = struct.unpack("<I", P.mem_bytes()[SCRATCH_BYTE:
                                                       SCRATCH_BYTE + 4])[0]
    models = {
        "exact": {"scratch": source_value, "destination": source_value},
        "stale_destination": {"scratch": source_value,
                              "destination": DEST_POISON},
        "zero": {"scratch": 0, "destination": 0},
        "source_mod64": {"scratch": P.codeword(source % 64),
                         "destination": P.codeword(source % 64)},
        "store_absent": {"scratch": initial_scratch,
                         "destination": initial_scratch},
    }
    matching = [name for name, model in models.items()
                if observed["scratch"] == model["scratch"]
                and observed["post_forward"] == model["destination"]
                and observed["post_destination"] == model["destination"]]
    rec["transfer_probe"] = {
        "source": source, "destination": destination,
        "source_tier": "low" if source < 16 else ("mid" if source < 64 else "high"),
        "destination_tier": "low" if destination < 16 else
                            ("mid" if destination < 64 else "high"),
        "gap": case["gap"], "oracle_mode": case["oracle_mode"],
        "scratch_byte": SCRATCH_BYTE, "observed": observed,
        "models": models, "matching_models": sorted(matching),
        "semantic_decidable": bool(
            rec.get("status") == "OK"
            and observed["pre_source"] == source_value
            and observed["pre_destination"] == DEST_POISON
            and observed["post_source"] == source_value
            and observed["post_store_index"] == 0
            and observed["post_load_index"] == LOAD_INDEX_VALUE
            and observed["post_sentinel"] == P.SENT_IMM),
    }
    return rec


def main():
    B.C = sys.modules[__name__]
    B.score = score231
    return B.main()


if __name__ == "__main__":
    raise SystemExit(main())
