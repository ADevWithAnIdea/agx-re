#!/usr/bin/env python3
"""EXP-0200 GATE A -- the caller-to-actual-byte ledger, verified from raw.

  python3 analysis/ledger200.py raw/<run> [raw/<run> ...]

GATE A (RE_EXPERIMENT_PROCESS_CORRECTIONS section 3) requires, per dispatched
case: the requested field value, the complete requested bytes, the complete
ACTUAL bytes from the final dispatched program, an independently decoded value
from those actual bytes, a program hash plus instruction offset, and the
descriptor/harness revisions -- and then, BEFORE any hardware conclusion:

    requested field value == value decoded from actual dispatched bytes

A symmetric assemble/disassemble round trip is NOT this gate. This gate is what
would have caught DEF-0166 -- a requested bit the assembler could not clear
never appears in the actual-byte ledger -- and it is the instrument for the
aliasing hazard where `match`-pinned bits make nominally different values
assemble to identical bytes, so the oracle describes a program that never ran.

TWO RUN SHAPES ARE VERIFIED, DIFFERENTLY, AND THE DIFFERENCE IS REPORTED.

* **Target 2** (`run200.py`) writes `requested_bytes`, `actual_bytes` sliced
  back out of the dispatched blob, `program_sha256`, `instr_offset`, `db_rev`
  and `harness_rev` on every case. Full Gate A. The check is
  `actual_bytes == requested_bytes` per case, plus the distinct-encoding counts.

* **Target 1** is EXP-0187's frozen harness honoured unchanged, and it predates
  Gate A: it records the mutated instruction bytes but not a slice of the
  dispatched blob. This script therefore verifies the STRONGEST claim that raw
  can support -- that the recorded bytes, re-decoded at the field's own span
  from the PINNED descriptor, yield exactly the requested value, and that the
  distinct-encoding count equals the distinct-value count -- and REPORTS the
  residual gap explicitly as `ledger_grade: reconstructed` rather than
  pretending to `dispatched-slice`. Per corrections section 9 that is a bounded
  auditability status, not a retraction.

Nothing here decides a verdict. It prints what the raw supports.
"""
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import locate200 as L            # noqa: E402


def load(run_dir):
    out = []
    for ln in (Path(run_dir) / "sweep.jsonl").read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def decode_span(hexbytes, mnemonic, field):
    """The independently decoded value: re-read the field out of the recorded
    bytes using the PINNED descriptor's own (start, width), never the value the
    caller asked for."""
    try:
        start, width = L.field_span(mnemonic, field)
    except KeyError:
        return None
    raw = bytes.fromhex(hexbytes)
    return (int.from_bytes(raw, "little") >> start) & ((1 << width) - 1)


def report(run_dir):
    recs = [r for r in load(run_dir)
            if r.get("outcome") not in ("carrier_ready", "carrier_start_failed")
            and r.get("role") != "baseline"]
    if not recs:
        print("  no dispatched cases")
        return {}
    has_actual = any("actual_bytes" in r for r in recs)
    grade = "dispatched-slice" if has_actual else "reconstructed"
    by_arm = collections.defaultdict(list)
    for r in recs:
        by_arm[(r.get("carrier"), r.get("arm"), r.get("instr"),
                r.get("field"))].append(r)
    tot = {"cases": 0, "ledger_ok": 0, "ledger_bad": 0, "decode_ok": 0,
           "decode_bad": 0, "decode_na": 0}
    lines = []
    for key, rs in sorted(by_arm.items(), key=lambda kv: str(kv[0])):
        carrier, arm, instr, field = key
        vals = {r.get("value") for r in rs}
        encs = {r.get("actual_bytes") or r.get("bytes") for r in rs}
        lbad, dok, dbad, dna = 0, 0, 0, 0
        for r in rs:
            tot["cases"] += 1
            if has_actual:
                ok = bool(r.get("ledger_ok")) and \
                    r.get("actual_bytes") == r.get("requested_bytes")
                tot["ledger_ok" if ok else "ledger_bad"] += 1
                lbad += 0 if ok else 1
            if field and not field.startswith("_"):
                got = decode_span(r.get("actual_bytes") or r.get("bytes") or "",
                                  instr, field)
                if got is None:
                    dna += 1
                    tot["decode_na"] += 1
                elif got == r.get("value"):
                    dok += 1
                    tot["decode_ok"] += 1
                else:
                    dbad += 1
                    tot["decode_bad"] += 1
            else:
                dna += 1
                tot["decode_na"] += 1
        alias = len(vals) - len(encs)
        lines.append({"carrier": carrier, "arm": arm, "instr": instr,
                      "field": field, "cases": len(rs),
                      "distinct_requested_values": len(vals),
                      "distinct_actual_encodings": len(encs),
                      "match_bit_collisions": max(0, alias),
                      "ledger_mismatches": lbad,
                      "decoded_equals_requested": dok,
                      "decoded_differs": dbad, "decode_not_applicable": dna})
    bad = [l for l in lines
           if l["ledger_mismatches"] or l["decoded_differs"]
           or l["match_bit_collisions"]]
    print("  ledger_grade=%s  arms=%d cases=%d" % (grade, len(lines), tot["cases"]))
    print("  requested==actual: %d ok / %d bad%s"
          % (tot["ledger_ok"], tot["ledger_bad"],
             "   (not recorded by this harness; see docstring)"
             if not has_actual else ""))
    print("  decoded-from-bytes == requested value: %d ok / %d differ / %d n/a "
          "(fieldless `_instruction` rows have no span to decode)"
          % (tot["decode_ok"], tot["decode_bad"], tot["decode_na"]))
    if bad:
        print("  ARMS WITH A LEDGER PROBLEM:")
        for l in bad:
            print("   ", json.dumps(l, sort_keys=True))
    else:
        print("  no ledger mismatch, no decode disagreement, no match-bit "
              "collision in any arm")
    return {"run": str(run_dir), "ledger_grade": grade, "totals": tot,
            "arms": lines, "problem_arms": bad}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    out = []
    for d in sys.argv[1:]:
        print("=== %s" % d)
        out.append(report(d))
    p = EXP / "analysis" / "ledger.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote", p)
    return 1 if any(r.get("problem_arms") for r in out) else 0


if __name__ == "__main__":
    sys.exit(main())
