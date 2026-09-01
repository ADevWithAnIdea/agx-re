#!/usr/bin/env python3
"""Formal cross-run gate for EXP-0237 canonical fspecial reach."""

import json
import struct
import sys
from collections import Counter
from pathlib import Path


ALIAS_REGS = {0, 15, 16, 31, 32, 47, 48, 63}


def load(path):
    rows = [json.loads(line) for line in open(Path(path) / "sweep.jsonl")]
    return {row["name"]: row for row in rows
            if row.get("kind") == "fspecial_reach"}


def fbits(value):
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: formal237.py RUN01 RUN02")
    a, b = load(argv[1]), load(argv[2])
    names = sorted(set(a) | set(b))
    main_names = [n for n in names if not n.startswith("ctl_")]
    controls = [n for n in names if n.startswith("ctl_")]
    missing = [n for n in names if n not in a or n not in b]
    counts = Counter()
    source_codes, destination_codes, alias_regs = set(), set(), set()
    failures = {key: [] for key in (
        "byte_disagreements", "observation_disagreements", "undecidable",
        "semantic", "gate_a", "donor", "descriptor", "source_value",
        "source_release", "destination_value", "alias_publication")}

    for name in main_names + controls:
        if name not in a or name not in b:
            continue
        ra, rb = a[name], b[name]
        pa = ra.get("fspecial_reach_probe", {})
        pb = rb.get("fspecial_reach_probe", {})
        role, code, reg = pa.get("role"), pa.get("code"), pa.get("register")
        if name in main_names:
            counts[role] += 1
            if role == "source":
                source_codes.add(code)
            elif role == "destination":
                destination_codes.add(code)
            elif role == "alias":
                alias_regs.add(reg)
        for rec in (ra, rb):
            ga, body = rec.get("gate_a", {}), rec.get("under_test", [])
            if not rec.get("dispatched_bytes_verified") or ga.get("n_bad") != 0 \
                    or ga.get("n_alias") != 0 or len(body) != 1 \
                    or body[0].get("mnemonic") != "fspecial" \
                    or len(bytes.fromhex(body[0].get("bytes", ""))) != 10:
                failures["gate_a"].append("%s:%s" % (name, rec.get("run")))
            ledger = rec.get("ledger", {})
            if rec.get("donor_fields") or ledger.get("COPIED") or ledger.get("CARRIER"):
                failures["donor"].append("%s:%s" % (name, rec.get("run")))
            if body:
                decoded = body[0].get("decoded_actual", {})
                if role == "source" and decoded.get("src") != code:
                    failures["descriptor"].append("%s:%s" % (name, rec.get("run")))
                elif role == "destination" and decoded.get("dst") != code:
                    failures["descriptor"].append("%s:%s" % (name, rec.get("run")))
                elif role == "alias" and (decoded.get("src") != reg << 2
                                           or decoded.get("dst") != reg << 1):
                    failures["descriptor"].append("%s:%s" % (name, rec.get("run")))
        if ra.get("prog_sha256") != rb.get("prog_sha256") \
                or ra.get("under_test") != rb.get("under_test"):
            failures["byte_disagreements"].append(name)
        if pa.get("observed") != pb.get("observed"):
            failures["observation_disagreements"].append(name)
        if name in main_names:
            for rec, probe in ((ra, pa), (rb, pb)):
                obs = probe.get("observed", {})
                if not probe.get("semantic_decidable"):
                    failures["undecidable"].append(name)
                if not rec.get("match") or not rec.get("bucket_ok"):
                    failures["semantic"].append(name)
                if role == "source":
                    if obs.get("post_destination") != fbits(reg + 1):
                        failures["source_value"].append(name)
                    if obs.get("post_target") != 0:
                        failures["source_release"].append(name)
                elif role == "destination":
                    if obs.get("post_target") != probe.get("result"):
                        failures["destination_value"].append(name)
                elif role == "alias":
                    if obs.get("post_target") != fbits(reg + 1):
                        failures["alias_publication"].append(name)

    control_fired = [n for n in controls if n in a and n in b
                     and not a[n].get("match") and not b[n].get("match")
                     and a[n].get("bucket_ok") and b[n].get("bucket_ok")]
    expected_counts = {"source": 256, "destination": 192, "alias": 8}
    coverage_ok = (source_codes == set(range(256))
                   and destination_codes == set(range(192))
                   and alias_regs == ALIAS_REGS)
    result = {
        "runs": [argv[1], argv[2]], "expected_counts": expected_counts,
        "seen_counts": dict(counts), "source_codes": len(source_codes),
        "destination_codes": len(destination_codes),
        "alias_regs": sorted(alias_regs), "coverage_ok": coverage_ok,
        "controls_seen": len(controls), "control_fired": control_fired,
        "missing_cross_run": missing,
        **{key: sorted(set(value)) for key, value in failures.items()},
    }
    result["pass"] = bool(dict(counts) == expected_counts and coverage_ok
                          and len(controls) == 2 and len(control_fired) == 2
                          and not missing
                          and all(not value for value in failures.values()))
    out = Path(__file__).with_name("formal_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({
        "pass": result["pass"], "seen_counts": result["seen_counts"],
        "source_codes": len(source_codes), "destination_codes": len(destination_codes),
        "controls_seen": len(controls), "controls_fired": len(control_fired),
        **{key: len(set(value)) for key, value in failures.items()},
        "missing": len(missing),
    }, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
