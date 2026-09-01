#!/usr/bin/env python3
"""Formal gate for EXP-0230 Amendment 02."""

import json
import sys
from pathlib import Path


MODELS = ("mod64", "direct96", "zero")


def load(path):
    return {r["name"]: r for r in map(json.loads, open(Path(path) / "sweep.jsonl"))
            if r.get("arm") in ("R2", "R2CTL")}


def half(word, high):
    return (word >> (16 * high)) & 0xFFFF


def replace_low(word, value):
    return (word & 0xFFFF0000) | (value & 0xFFFF)


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: formal230_r2.py RUN03 RUN04")
    a, b = load(argv[1]), load(argv[2])
    names = sorted(set(a) | set(b))
    main_names = [n for n in names if n.startswith("r2_i")]
    controls = [n for n in names if n.startswith("r2ctl_")]
    missing = [n for n in names if n not in a or n not in b]
    gate_a_fail = []
    donor_fail = []
    seed_fail = []
    cross_run_fail = []
    model_mismatch = {m: [] for m in MODELS}
    descriptor = {14: set(), 15: set()}
    for name in main_names:
        if name not in a or name not in b:
            continue
        ra, rb = a[name], b[name]
        pa, pb = ra.get("reach_probe", {}), rb.get("reach_probe", {})
        for rec, probe in ((ra, pa), (rb, pb)):
            plan = probe.get("index_reg")
            source = probe.get("source")
            hs = probe.get("source_half")
            descriptor[plan].add((source << 1) | hs)
            ga = rec.get("gate_a", {})
            if not rec.get("dispatched_bytes_verified") or ga.get("n_bad") or \
                    ga.get("n_alias") or len(rec.get("under_test", [])) != 1:
                gate_a_fail.append("%s:%s" % (name, rec.get("run")))
            led = rec.get("ledger", {})
            if rec.get("donor_fields") or led.get("COPIED") or led.get("CARRIER"):
                donor_fail.append("%s:%s" % (name, rec.get("run")))
            obs = probe.get("observed", {})
            want_src = 0x5A17C0DE ^ (source * 0x01010101)
            alias = source % 64
            want_alias = 0x5A17C0DE ^ (alias * 0x01010101)
            if obs.get("pre_src") != (want_src & 0xFFFFFFFF) or \
                    obs.get("pre_mod64") != (want_alias & 0xFFFFFFFF) or \
                    not probe.get("post_sentinel_ok"):
                seed_fail.append("%s:%s" % (name, rec.get("run")))
            before = obs.get("pre_dst")
            got = obs.get("post_dst")
            expected = {
                "mod64": replace_low(before, half(want_alias, hs)),
                "direct96": replace_low(before, half(want_src, hs)),
                "zero": replace_low(before, 0),
            }
            for model in MODELS:
                if got != expected[model]:
                    model_mismatch[model].append("%s:%s" % (name, rec.get("run")))
        if pa.get("observed") != pb.get("observed") or \
                ra.get("under_test") != rb.get("under_test") or \
                ra.get("prog_sha256") != rb.get("prog_sha256"):
            cross_run_fail.append(name)

    control_fired = [n for n in controls if n in a and n in b and
                     not a[n].get("match") and not b[n].get("match")]
    winners = sorted(m for m in MODELS if not model_mismatch[m])
    coverage = {str(k): len(v) for k, v in descriptor.items()}
    result = {
        "runs": argv[1:], "main_seen": len(main_names), "controls_seen": len(controls),
        "missing": missing, "gate_a_failures": gate_a_fail,
        "donor_failures": donor_fail, "seed_failures": seed_fail,
        "cross_run_failures": cross_run_fail,
        "descriptor_coverage": coverage,
        "model_mismatches": model_mismatch, "zero_mismatch_models": winners,
        "selected_model": winners[0] if len(winners) == 1 else None,
        "controls_fired": control_fired,
    }
    result["pass"] = bool(
        len(main_names) == 16 and len(controls) == 2 and not missing and
        not gate_a_fail and not donor_fail and not seed_fail and not cross_run_fail and
        coverage == {"14": 8, "15": 8} and winners == ["mod64"] and
        len(control_fired) == 2)
    out = Path(__file__).with_name("formal_r2_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in result.items()
                      if k != "model_mismatches"}, indent=1, sort_keys=True))
    print("model mismatch counts:", {k: len(v) for k, v in model_mismatch.items()})
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
