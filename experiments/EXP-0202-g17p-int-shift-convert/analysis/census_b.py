#!/usr/bin/env python3
"""EXP-0202 AMENDMENT (v3) census -- identical to analysis/census.py except that
it also loads the v3 carriers (`harness/carriers202b.py`) and writes
`raw/prefreeze/census_b.json`. `analysis/census.py` is left untouched so the
run02 chain stays reproducible.

EXP-0202 pre-freeze census. RUNS ON THE NEO. NO VERDICT MAY CITE IT.

Compiles every authored carrier with the pinned `shdump`, locates every
occurrence of each target instruction by DESCRIPTOR SIGNATURE from the pinned
`db.json`, cross-checks each hit with the pinned tokenizer, and reports:

  * which carriers emit their target at all (a carrier that does not is DROPPED
    before the freeze and the drop is recorded -- that is data about which
    datapaths our own MSL can reach);
  * the COMPILED value of every target field, per occurrence. This is the
    cheapest and strongest dimension evidence there is: if the compiler itself
    emits both values of `shift_amt_move.src_flag`, or both of `ibitcount.cache`,
    the carrier set spans the dimension by DEMONSTRATION rather than assertion
    (EXP-0188 established `if_push.scope` exactly this way);
  * for `irotate`, the byte-diff across rotate amounts {1,5,7,13,19,31} that
    identifies WHICH byte of the 40-bit `operands` blob carries the immediate --
    which is what converts a "did it move" test into an EXACT per-value oracle;
  * for `cvt_f2i`, where the pinned tokenizer says the FOLLOWING instruction
    starts, so the 10-byte length model that makes `b9` a field at all is
    checked rather than assumed.

  python3 analysis/census.py            # writes raw/prefreeze/census.json

CLEAN-ROOM: OWN-SHADER. Only the compiled form of our own kernels is inspected.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import carriers202 as C      # noqa: E402
import carriers202b          # noqa: E402,F401  (adds the v3 carriers)
import locate202 as L        # noqa: E402

TARGETS = ["shift_amt_move", "irotate", "ibitcount", "iunary", "cvt_f2i"]
# The whole compact-move family that shares byte+1 = src_reg(7) + src_flag(1) at
# bit 15, plus `uniform_mov`, whose byte+1 is an EIGHT-bit uniform index with no
# flag at all. If the compiler ever sets bit 15 anywhere in this family, the
# source-class dimension is demonstrated rather than asserted -- and if it never
# does, that is the finding.
SRCFLAG_FAMILY = ["reg_move_c0", "reg_move_c1", "reg_move_c9", "reg_move_c2var",
                  "b_alu10_lo6", "b_alu10_lo7", "b_alu10_loe", "b_alu10_lof",
                  "shift_amt_move", "uniform_mov"]
FIELDS = {
    "shift_amt_move": ["dst", "src_reg", "src_flag", "kind", "op_desc"],
    "irotate": ["b2", "operands", "tail"],
    "ibitcount": ["fn_hi", "form", "cache", "dst", "op_enable", "src", "srcdesc", "tail"],
    "iunary": ["b1", "opsel", "dst", "op_enable", "src", "srcdesc", "tail"],
    "cvt_f2i": ["mode", "dst", "src_class", "src", "cvtop", "signflag", "dst_class", "b9"],
}
BIN = EXP / "work" / "bin"


def bits(raw, start, width):
    return (int.from_bytes(raw, "little") >> start) & ((1 << width) - 1)


def walk(main_bytes):
    """Sequential tokenizer walk from offset 0 -> the set of REAL instruction
    boundaries, plus the decoded stream.

    A signature scan alone finds byte patterns, not instructions: a window that
    starts in the MIDDLE of a longer instruction can satisfy a loose descriptor's
    match and decode cleanly. `iunary` is exactly that kind of descriptor (one
    match constraint: byte0 == 0x27), so without this every popcount's interior
    would be offered as an `iunary` arm. Two fields were withdrawn on 2026-08-30
    after their movement turned out to be a different instruction; this is the
    same failure one step earlier."""
    offs, stream, off, guard = set(), [], 0, 0
    n = len(main_bytes)
    while off < n and guard < 100000:
        guard += 1
        try:
            rec, length = L.isadb.decode_one(bytes(main_bytes), off)
        except Exception:                                       # noqa: BLE001
            off += 2
            continue
        if not length or length <= 0:
            off += 2
            continue
        offs.add(off)
        stream.append({"off": off, "mnemonic": rec.get("mnemonic"), "len": length})
        off += length
    return offs, stream


def main():
    out = {"carriers": {}, "drops": [], "compiled_field_values": {},
           "irotate_amount_bytediff": {}, "cvt_next_instruction": {}}
    for name in sorted(C.CARRIERS):
        spec = C.CARRIERS[name]
        rec = {"metal": spec["metal"], "func": spec["func"], "doc": spec["doc"]}
        try:
            arch, off, main_bytes = L.compile_carrier(
                BIN, EXP / spec["metal"], spec["func"], EXP / "work" / "arch")
        except Exception as e:                                  # noqa: BLE001
            rec["compile_error"] = str(e)[:400]
            out["carriers"][name] = rec
            out["drops"].append({"carrier": name, "why": "compile failed"})
            continue
        rec["main_len"] = len(main_bytes)
        boundaries, stream = walk(main_bytes)
        rec["n_instructions_walked"] = len(stream)
        rec["walk_covers_bytes"] = sum(x["len"] for x in stream)
        rec["occurrences"] = {}
        for mn in TARGETS:
            hits = L.find_occurrences(main_bytes, mn)
            keep = []
            for h in hits:
                tok = L.token_at(main_bytes, h["off"])
                h["token"] = tok
                # An occurrence counts only if the pinned tokenizer AGREES that
                # the bytes there are this instruction. `iunary` is a loose
                # byte0==0x27 catch-all whose signature `ibitcount` also
                # satisfies, so signature alone would mis-attribute every
                # popcount to `iunary`.
                h["at_boundary"] = h["off"] in boundaries
                h["tokenizer_agrees"] = (tok.get("mnemonic") == mn
                                         and h["off"] in boundaries)
                fv = {}
                raw = bytes(main_bytes[h["off"]:h["off"] + h["len"]])
                for f in FIELDS[mn]:
                    try:
                        s, w = L.field_span(mn, f)
                    except KeyError:
                        continue
                    fv[f] = bits(raw, s, w)
                h["field_values"] = fv
                keep.append(h)
            if keep:
                rec["occurrences"][mn] = keep
        out["carriers"][name] = rec

    # Which compiled values does our own compiler actually choose, per field?
    for mn, flds in FIELDS.items():
        for f in flds:
            key = "%s.%s" % (mn, f)
            seen = {}
            for name, rec in out["carriers"].items():
                for h in rec.get("occurrences", {}).get(mn, []):
                    if not h["tokenizer_agrees"]:
                        continue
                    v = h["field_values"].get(f)
                    if v is None:
                        continue
                    seen.setdefault(v, []).append("%s@%d" % (name, h["off"]))
            if seen:
                out["compiled_field_values"][key] = {
                    "distinct_values": sorted(seen),
                    "n_distinct": len(seen),
                    "where": {str(k): v[:6] for k, v in sorted(seen.items())}}

    # The source-class dimension, across the WHOLE compact-move family.
    fam = {}
    for name, rec in out["carriers"].items():
        if "main_len" not in rec:
            continue
        try:
            arch, off, mb = L.compile_carrier(
                BIN, EXP / C.CARRIERS[name]["metal"], C.CARRIERS[name]["func"],
                EXP / "work" / "arch")
        except Exception:                                       # noqa: BLE001
            continue
        bnd, _ = walk(mb)
        for mn in SRCFLAG_FAMILY:
            for h in L.find_occurrences(mb, mn):
                if h["off"] not in bnd:
                    continue
                if L.token_at(mb, h["off"]).get("mnemonic") != mn:
                    continue
                raw = bytes(mb[h["off"]:h["off"] + h["len"]])
                d = fam.setdefault(mn, {"n": 0, "src_flag": {}, "byte1": {},
                                        "examples": []})
                d["n"] += 1
                if mn != "uniform_mov":
                    sf = bits(raw, 15, 1)
                    d["src_flag"][str(sf)] = d["src_flag"].get(str(sf), 0) + 1
                b1 = bits(raw, 8, 8)
                d["byte1"][str(b1)] = d["byte1"].get(str(b1), 0) + 1
                if len(d["examples"]) < 8:
                    d["examples"].append({"carrier": name, "off": h["off"],
                                          "bytes": raw.hex()})
    out["srcflag_family_census"] = fam

    # irotate: which byte of `operands` moves with the immediate amount?
    amt = {}
    for name, k in (("rot_k1", 1), ("rot_k5", 5), ("rot_k7", 7),
                    ("rot_k13", 13), ("rot_k19", 19), ("rot_k31", 31)):
        rec = out["carriers"].get(name, {})
        hs = [h for h in rec.get("occurrences", {}).get("irotate", [])
              if h["tokenizer_agrees"]]
        if hs:
            amt[k] = hs[0]["bytes"]
    out["irotate_amount_bytediff"] = {
        "per_amount_bytes": amt,
        "bytes_that_vary": sorted({
            i for i in range(12)
            for a in amt.values() for b in amt.values()
            if len(a) == 24 and len(b) == 24 and a[2 * i:2 * i + 2] != b[2 * i:2 * i + 2]}),
    }

    # cvt_f2i: does the following instruction start at +10?
    for name, rec in out["carriers"].items():
        hs = [h for h in rec.get("occurrences", {}).get("cvt_f2i", [])
              if h["tokenizer_agrees"]]
        if not hs:
            continue
        try:
            arch, off, main_bytes = L.compile_carrier(
                BIN, EXP / C.CARRIERS[name]["metal"], C.CARRIERS[name]["func"],
                EXP / "work" / "arch")
        except Exception:                                       # noqa: BLE001
            continue
        h = hs[0]
        out["cvt_next_instruction"][name] = {
            "off": h["off"], "modelled_len": h["len"],
            "token_at_plus8": L.token_at(main_bytes, h["off"] + 8),
            "token_at_plus9": L.token_at(main_bytes, h["off"] + 9),
            "token_at_plus10": L.token_at(main_bytes, h["off"] + 10),
        }

    d = EXP / "raw" / "prefreeze"
    d.mkdir(parents=True, exist_ok=True)
    (d / "census_b.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("carriers=%d drops=%d" % (len(out["carriers"]), len(out["drops"])))
    for mn in TARGETS:
        n = sum(1 for r in out["carriers"].values()
                if any(h["tokenizer_agrees"] for h in r.get("occurrences", {}).get(mn, [])))
        print("  %-16s emitted (tokenizer-agreeing) by %d carriers" % (mn, n))
    for k, v in sorted(out["compiled_field_values"].items()):
        print("  compiled %-28s %d distinct: %s" % (k, v["n_distinct"],
                                                    v["distinct_values"][:12]))
    print("wrote", d / "census_b.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
