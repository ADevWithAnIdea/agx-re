#!/usr/bin/env python3
"""EXP-0206 CENSUS -- PRE-FREEZE CALIBRATION. **NO VERDICT MAY CITE THIS FILE.**

Runs on the neo. Compiles every carrier with our own `shdump`, carves EVERY
symbol region of the shader `__text` section, locates every target instruction in
the regions its target declares (`region_select`) by BOTH methods (signature scan
and pinned-tokenizer walk), and reports per occurrence the compiled value of the
target field and of the occurrence's DIMENSION field.

It answers, before any device time is spent:

  * does each carrier emit the instruction at all (compiler inlining / folding)?
  * is the DIMENSION actually spanned -- in particular, does any carrier emit an
    `if_push` with `scope_kind == 0x1a`, the loop-iteration region kind EXP-0184
    could not reach and named as its own limitation?
  * for `stop`: does CODE FOLLOW the terminator (a mid-program stop, where a
    termination-dimension positive control is available) or not (the final stop,
    where EXP-0003/EXP-0010 already showed the whole word to be inert)?
  * do the two location methods agree, and where do they not?

Output: raw/prefreeze/census.json  (calibration evidence, retained, never cited)

CLEAN-ROOM: OWN-SHADER. Only our own compiled MSL is inspected.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(HERE))

import carriers206 as C          # noqa: E402
import locate206 as L            # noqa: E402
import targets206 as T           # noqa: E402

BIN = EXP / "work" / "bin"
WORK = EXP / "work"


def select_regions(regions, how):
    code = L.code_regions(regions)
    if how == "main":
        return [n for n in code if n == "_agc.main"]
    if how == "callee":
        return [n for n in code if not n.startswith("_agc.main")]
    return code


def main():
    out = {"carriers": {}, "targets": {}}
    creg = {}
    for name, spec in C.CARRIERS.items():
        rec = {"func": spec["func"], "metal": spec["metal"], "doc": spec["doc"]}
        try:
            arch, regions = L.compile_carrier(
                BIN, EXP / spec["metal"], spec["func"], WORK / "arch")
            creg[name] = regions
            rr = {}
            for rn, r in regions.items():
                entry = {"abs": r["abs"], "len": r["len"]}
                if rn in L.code_regions(regions):
                    recs, gaps = L.walk_resync(r["bytes"])
                    entry.update(walk_instrs=len(recs), gaps=gaps,
                                 mnemonics=sorted({x["mnemonic"] for x in recs}))
                rr[rn] = entry
            rec["regions"] = rr
        except Exception as e:                                  # noqa: BLE001
            rec["error"] = str(e)[:400]
        out["carriers"][name] = rec

    for t in T.TARGETS:
        mn = t.get("from_mnemonic", t["mnemonic"])
        entry = {"mnemonic": mn, "field": t["field"],
                 "dimension": t["dimension"],
                 "region_select": t["region_select"], "occurrences": {}}
        for cname in t["carriers"]:
            regions = creg.get(cname)
            if regions is None:
                entry["occurrences"][cname] = {"error": "carrier did not compile"}
                continue
            per = {}
            for rn in select_regions(regions, t["region_select"]):
                main_b = regions[rn]["bytes"]
                occ = L.occurrences(main_b, mn)
                rows = []
                for off in occ["accepted"]:
                    length = L.DESC[mn]["length"]
                    raw = bytes(main_b[off:off + length])
                    row = {"off": off, "len": length, "bytes": raw.hex()}
                    if t.get("from_mnemonic") is None:
                        try:
                            row["compiled_field"] = L.get_field(raw, mn, t["field"])
                        except KeyError:
                            row["compiled_field"] = None
                    dimf = t.get("occ_dimension_field")
                    if dimf:
                        try:
                            row["dim"] = L.get_field(raw, mn, dimf)
                        except KeyError:
                            row["dim"] = None
                    if mn == "stop":
                        fc, rest = L.follows_code(main_b, off, length)
                        row["follows_code"] = fc
                        row["bytes_after"] = rest
                    rows.append(row)
                per[rn] = {"agreed": rows,
                           "accepted_offsets": occ["accepted"],
                           "resync_accepted": occ["resync_accepted"],
                           "signature_only": occ["signature_only"],
                           "signature_inside_decoded": occ["signature_inside_decoded"],
                           "walk_only": occ["walk_only"],
                           "gaps": occ["gaps"],
                           "walk_covered_bytes": occ["walk_covered_bytes"],
                           "region_len": occ["main_len"]}
            entry["occurrences"][cname] = per
        out["targets"][t["key"]] = entry

    d = EXP / "raw" / "prefreeze"
    d.mkdir(parents=True, exist_ok=True)
    (d / "census.json").write_text(json.dumps(out, indent=1, sort_keys=True))

    print("== carriers ==")
    for n, r in sorted(out["carriers"].items()):
        if "error" in r:
            print("  %-12s ERROR %s" % (n, r["error"]))
            continue
        print("  %-12s %s" % (n, "  ".join(
            "%s[%d]" % (rn, rr["len"]) for rn, rr in sorted(r["regions"].items()))))
    print("== targets ==")
    for k, e in out["targets"].items():
        print("  -- %s (%s, regions=%s)" % (k, e["mnemonic"], e["region_select"]))
        for c, per in sorted(e["occurrences"].items()):
            if "error" in per:
                print("     %-12s %s" % (c, per["error"]))
                continue
            for rn, o in sorted(per.items()):
                dims = sorted({r.get("dim") for r in o["agreed"]}) \
                    if T.BY_KEY[k].get("occ_dimension_field") else []
                cf = sorted({r.get("compiled_field") for r in o["agreed"]})
                extra = ""
                if e["mnemonic"] == "stop":
                    extra = " follows_code=%s" % sorted(
                        {r.get("follows_code") for r in o["agreed"]})
                print("     %-12s %-22s n=%-3d dim=%-16s compiled=%-16s "
                      "resync=%s inside=%d gaps=%d%s"
                      % (c, rn[:22], len(o["agreed"]), dims, cf,
                         o["resync_accepted"],
                         len(o["signature_inside_decoded"]), len(o["gaps"]), extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
