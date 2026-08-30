#!/usr/bin/env python3
"""EXP-0182 -- derive the low-nibble-2 byte+2 op-select -> length map from db.json,
and compare it against what `instr_length` actually returns at every destination nibble.

This is the GENERAL form of the `hminmax` defect. The low-nibble-2 family (integer /
half compare, min/max, select, carry) puts the DESTINATION register in byte0's high
nibble -- every descriptor's own `match` says so (`[0,4,2]`, never `[0,8,v]`). Its
length is selected by the byte+2 OP-SELECT. `instr_length` dispatches on the op-select
for a list of values and then falls back to FULL-BYTE per-destination rules
(`if b0 == 0x02 / 0x12 / 0x22 / 0x32`), so any op-select missing from that list gets a
length that depends on which register the instruction writes.

Output: for each byte+2 in 0..0x3f, the length db.json implies (when unambiguous) and
the length `instr_length` returns at each of the 16 destination nibbles.

Usage: python3 analysis/opsel_length_map.py [--tree DIR]
CLEAN-ROOM: pure analysis over our own db.json.
"""
import collections, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(os.path.dirname(HERE), "..", ".."))


def load(tree):
    spec = importlib.util.spec_from_file_location(
        "isadb_om_%x" % (abs(hash(tree)) & 0xffffffff), os.path.join(tree, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def main():
    tree = os.path.join(REPO, "tools", "agx-isa")
    if "--tree" in sys.argv:
        tree = sys.argv[sys.argv.index("--tree") + 1]
    m = load(tree)
    # db.json: which lengths does a given byte+2 admit, for low-nibble-2 descriptors
    # that pin at least one bit of byte+2 (the unpinned n2_op6/8/10 catch-alls are the
    # residue descriptors and are excluded -- they admit every op-select by construction).
    admits = collections.defaultdict(set)
    for d in m.DB:
        lo = [v for (s, w, v) in d["match"] if s == 0 and w == 4 and v == 2]
        full = [v for (s, w, v) in d["match"] if s == 0 and w == 8]
        if not lo or full:
            continue
        cons = [(s - 16, w, v) for (s, w, v) in d["match"] if s >= 16 and s + w <= 24]
        if not cons:
            continue                       # residue catch-all (n2_op6/8/10)
        for b2 in range(256):
            if all(((b2 >> st) & ((1 << w) - 1)) == v for st, w, v in cons):
                admits[b2].add((d["length"], d["mnemonic"]))

    rows = {}
    for b2 in range(0x40):
        lens = {L for L, _ in admits.get(b2, ())}
        got = {}
        for n in range(16):
            # Probe: byte0 = dst<<4 | 2, byte+2 = op-select. byte+1 is a source
            # descriptor, NOT a length selector, but an all-zero byte+1 trips the
            # unrelated 2-byte `X2 00` compact rules and the R9 trailing-word tables,
            # so two probes are used and an op-select counts as destination-dependent
            # only when BOTH agree that it is (byte+1 = 0x01 and 0x05).
            vals = []
            for b1 in (0x01, 0x05):
                buf = bytes([(n << 4) | 0x02, b1, b2] + [0x00] * 13)
                try:
                    vals.append(m.instr_length(buf, 0))
                except Exception as e:
                    vals.append("ERR:%s" % type(e).__name__)
            got["%x" % n] = vals[0] if vals[0] == vals[1] else vals
        # a cell whose two probes disagree is PROBE-SENSITIVE (the `_R9_SIGS` 2-byte
        # trailing-word table keys on (byte0, byte+1) and fires for some pairs); it is
        # reported but never counted as a destination dependence.
        scal = {k: v for k, v in got.items() if not isinstance(v, list)}
        distinct = sorted({str(v) for v in scal.values()})
        rows["0x%02x" % b2] = {
            "db_json_admits": sorted("%d:%s" % (L, mn) for L, mn in admits.get(b2, ())),
            "db_json_unambiguous_length": (list(lens)[0] if len(lens) == 1 else None),
            "instr_length_by_dst_nibble": got,
            "dst_dependent": len(distinct) > 1,
            "distinct_lengths": distinct,
            "probe_sensitive_nibbles": sorted(k for k, v in got.items() if isinstance(v, list)),
            "nibbles_disagreeing_with_db_json": sorted(
                k for k, v in scal.items()
                if len(lens) == 1 and v != list(lens)[0]),
        }
    bad = {k: v for k, v in rows.items() if v["dst_dependent"]}
    mism = {k: v for k, v in rows.items() if v["nibbles_disagreeing_with_db_json"]}
    json.dump({"_meta": {"tree": os.path.relpath(os.path.abspath(tree), REPO)},
               "summary": {"op_selects_whose_length_depends_on_the_DESTINATION": sorted(bad),
                           "n_dst_dependent": len(bad),
                           "op_selects_where_db_json_is_unambiguous_and_code_disagrees":
                               {k: rows[k]["nibbles_disagreeing_with_db_json"] for k in sorted(mism)},
                           "n_mismatch": len(mism)},
               "rows": rows}, sys.stdout, indent=1)
    print()


main()
