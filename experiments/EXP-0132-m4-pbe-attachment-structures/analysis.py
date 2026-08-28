#!/usr/bin/env python3
"""EXP-0132 analysis: derive the H1-H5 hypothesis verdicts from the two
officially gated runs, write analysis.json + a human-readable report.
Cross-run byte-exactness itself is verify.py's job (--captured); this script
assumes that gate already passed and interprets the (run01) data, cross-
checking against run02 only where a hypothesis needs it explicitly.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "harness"))
import run as R
import casematrix as CM

MRT_LOAD_BASE, MRT_STORE_BASE, MRT_STRIDE = 0x20, 0x220, 0x20


def load(run_id):
    p = HERE / "raw" / run_id / "03_results.jsonl"
    return {json.loads(l)["name"]: json.loads(l) for l in open(p)}


def merge_with_flake_fallback(cases_a, cases_b):
    """Analysis operates primarily on run_a. Where verify.py --captured
    tolerated a content_captured flake (present+size agree, but one run's
    read failed), fall back to whichever run actually captured the bytes --
    both runs are equally valid GPU observations of the same case; the flake
    is a harness read failure, not a hardware difference (verify.py already
    confirmed size/presence agree). Returns (merged, fallback_used_for)."""
    merged = {}
    fallback_used_for = []
    for name, a in cases_a.items():
        b = cases_b.get(name)
        m = json.loads(json.dumps(a))  # deep copy
        if b is not None:
            for role, na in m.get("named", {}).items():
                nb = b.get("named", {}).get(role, {})
                if na.get("present") and not na.get("content_captured") and nb.get("content_captured"):
                    m["named"][role] = nb
                    fallback_used_for.append((name, role))
        merged[name] = m
    return merged, fallback_used_for


def k_record(window_hex, base, k):
    if window_hex is None:
        return None
    off = (base + k * MRT_STRIDE) * 2
    seg = window_hex[off: off + MRT_STRIDE * 2]
    return seg if seg else None


def is_zero(hexstr):
    return hexstr is not None and set(hexstr) <= {"0"}


def struct_prefix(hexstr, n=8):
    """First n hex-bytes (2n hex chars) -- the type/dims prefix before the
    masked address subfield, for cross-case structural comparison."""
    return hexstr[: n * 2] if hexstr else None


def h1_depth_stencil(cases):
    out = {"hypothesis": "H1: depth/stencil reuse k=ncolor(/+1) of mrt-attachment-descriptors"}
    def mrt(name):
        return cases[name]["named"]["mrt-attachment-descriptors"]

    findings = []
    verdict = "SUPPORTED"

    # a1: baseline, ncolor=1, no depth/stencil -> only k=0 populated.
    a1 = mrt("a1-clear-store-draw")
    if not a1["present"]:
        verdict = "INCONCLUSIVE"; findings.append("a1 mrt-attachment-descriptors not present")
    else:
        w = a1.get("window_hex")
        k0l, k1l = k_record(w, MRT_LOAD_BASE, 0), k_record(w, MRT_LOAD_BASE, 1)
        findings.append({"case": "a1", "k0_load_nonzero": not is_zero(k0l),
                          "k1_load_zero": is_zero(k1l)})
        if is_zero(k0l) or not is_zero(k1l):
            verdict = "REFUTED"

    # g1: ncolor=1, depth only -> k=1 populated (LOAD+STORE), matches g1's
    # own doubly-corroborated prefix from EXP-0108 (62 88 00 f8 01 7c 00 08).
    g1 = mrt("g1-depth-write")
    g1_prefix = None
    if g1["present"]:
        w = g1.get("window_hex")
        k1l = k_record(w, MRT_LOAD_BASE, 1)
        g1_prefix = struct_prefix(k1l)
        findings.append({"case": "g1", "k1_load_nonzero": not is_zero(k1l),
                          "k1_load_prefix": g1_prefix,
                          "matches_exp0108_doubly_corroborated_prefix":
                              g1_prefix == "628800f8017c0008"})
        if is_zero(k1l):
            verdict = "REFUTED"

    # h1: ncolor=1, stencil only -> k=1 populated, distinct prefix from depth.
    h1 = mrt("h1-stencil-write")
    h1_prefix = None
    if h1["present"]:
        w = h1.get("window_hex")
        k1l = k_record(w, MRT_LOAD_BASE, 1)
        h1_prefix = struct_prefix(k1l)
        findings.append({"case": "h1", "k1_load_nonzero": not is_zero(k1l),
                          "k1_load_prefix": h1_prefix,
                          "distinct_from_depth": h1_prefix != g1_prefix})
        if is_zero(k1l) or h1_prefix == g1_prefix:
            verdict = "REFUTED"

    # i1: ncolor=1, depth+stencil -> k=1 depth (matches g1), k=2 stencil (matches h1's shape).
    i1 = mrt("i1-depth-stencil-write")
    if i1["present"]:
        w = i1.get("window_hex")
        k1l, k2l = k_record(w, MRT_LOAD_BASE, 1), k_record(w, MRT_LOAD_BASE, 2)
        p1, p2 = struct_prefix(k1l), struct_prefix(k2l)
        findings.append({"case": "i1", "k1_matches_g1_depth_prefix": p1 == g1_prefix,
                          "k2_matches_h1_stencil_prefix": p2 == h1_prefix})
        if p1 != g1_prefix or p2 != h1_prefix:
            verdict = "REFUTED"

    # i2: ncolor=2, depth+stencil -> k=2 depth (matches g1), k=3 stencil (matches h1).
    # This is the adversarial generalization test (EXP-0108 only tested ncolor=1).
    i2 = mrt("i2-mrt2-depth-stencil-write")
    if i2["present"]:
        w = i2.get("window_hex")
        k0l, k1l = k_record(w, MRT_LOAD_BASE, 0), k_record(w, MRT_LOAD_BASE, 1)
        k2l, k3l = k_record(w, MRT_LOAD_BASE, 2), k_record(w, MRT_LOAD_BASE, 3)
        p2, p3 = struct_prefix(k2l), struct_prefix(k3l)
        findings.append({
            "case": "i2 (ncolor=2, adversarial generalization)",
            "k0_k1_color_nonzero": not is_zero(k0l) and not is_zero(k1l),
            "k2_matches_g1_depth_prefix": p2 == g1_prefix,
            "k3_matches_h1_stencil_prefix": p3 == h1_prefix,
        })
        if is_zero(k0l) or is_zero(k1l) or p2 != g1_prefix or p3 != h1_prefix:
            verdict = "REFUTED"
    else:
        verdict = "INCONCLUSIVE" if verdict == "SUPPORTED" else verdict

    # g2: depth memoryless -> k=1 still populated but with poison address marker.
    g2 = mrt("g2-depth-memoryless-write")
    if g2["present"]:
        w = g2.get("window_hex")
        k1l = k_record(w, MRT_LOAD_BASE, 1)
        findings.append({"case": "g2 (depth memoryless)", "k1_load_nonzero": not is_zero(k1l),
                          "k1_load_hex": k1l})

    out["verdict"] = verdict
    out["findings"] = findings
    return out


def h2_array_mip(cases):
    out = {"hypothesis": "H2: array slice / mip level not encoded in the k=0 record "
                          "(except a coarse mipCount>1 flag)"}
    def k0(name, base=MRT_LOAD_BASE):
        n = cases[name]["named"]["mrt-attachment-descriptors"]
        return k_record(n.get("window_hex"), base, 0) if n["present"] else None

    slice_records = {name: k0(name) for name in
                      ("l1-array-slice0", "l2-array-slice1", "l3-array-slice-last")}
    slice_identical = len(set(slice_records.values())) == 1 and all(slice_records.values())

    level_records = {name: k0(name) for name in ("m1-mip-level0", "m2-mip-level-last")}
    level_identical = len(set(level_records.values())) == 1 and all(level_records.values())

    baseline = k0("a1-clear-store-draw")
    mip_case = k0("m1-mip-level0")
    bit26_delta = None
    if baseline and mip_case:
        # word1 = bytes 4..7 of the record (record-relative), i.e. hex chars [8:16]
        # record bytes are little-endian on the wire; reverse byte order
        # before treating the 4 bytes as a 32-bit integer for bit tests
        # (record hex chars [8:16] = record-relative bytes 4..7 = "word1").
        w1_base = int.from_bytes(bytes.fromhex(baseline[8:16]), "little")
        w1_mip = int.from_bytes(bytes.fromhex(mip_case[8:16]), "little")
        bit26_delta = {"baseline_word1_hex": format(w1_base, "08x"),
                        "mip_word1_hex": format(w1_mip, "08x"),
                        "bit26_set_in_mip": bool(w1_mip & (1 << 26)),
                        "bit26_set_in_baseline": bool(w1_base & (1 << 26))}

    verdict = "SUPPORTED" if (slice_identical and level_identical) else "REFUTED"
    out["verdict"] = verdict
    out["findings"] = {
        "slice_records_identical_across_slice0_1_last": slice_identical,
        "level_records_identical_across_level0_last": level_identical,
        "mipcount_gt1_bit26_flag": bit26_delta,
    }
    return out


def h3_boundary(cases):
    out = {"hypothesis": "H3: invalid slice/level is silently accepted (no reject/abort)"}
    l4 = cases.get("l4-array-slice-invalid")
    m3 = cases.get("m3-mip-level-invalid")
    findings = {}
    verdict = "SUPPORTED"
    for name, c in (("l4-array-slice-invalid", l4), ("m3-mip-level-invalid", m3)):
        if c is None:
            verdict = "INCONCLUSIVE"; continue
        findings[name] = {"status": c["status"], "cb_status": c["cb_status"], "rts": c["rts"]}
        if c["status"] not in ("OK",):
            verdict = "REFUTED (non-OK status -- see findings for exact behavior)"
    out["verdict"] = verdict
    out["findings"] = findings
    return out


def h4_resolve(cases):
    out = {"hypothesis": "H4: MSAA resolve target populates k=ncolor of BOTH LOAD and "
                          "STORE arrays; k<ncolor STORE (the MSAA attachment's own) is zero"}
    findings = []
    verdict = "SUPPORTED"
    for name in ("r1-msaa4-resolve-detail", "r2-msaa4-store-and-resolve"):
        c = cases.get(name)
        if c is None:
            verdict = "INCONCLUSIVE"; continue
        n = c["named"]["mrt-attachment-descriptors"]
        if not n["present"]:
            verdict = "INCONCLUSIVE"; continue
        w = n.get("window_hex")
        k0_load, k0_store = k_record(w, MRT_LOAD_BASE, 0), k_record(w, MRT_STORE_BASE, 0)
        k1_load, k1_store = k_record(w, MRT_LOAD_BASE, 1), k_record(w, MRT_STORE_BASE, 1)
        rec = {"case": name,
               "k0_load_nonzero_ms_color": not is_zero(k0_load),
               "k0_store_zero_ms_color_store_slot": is_zero(k0_store),
               "k1_load_nonzero_resolve": not is_zero(k1_load),
               "k1_store_nonzero_resolve": not is_zero(k1_store),
               "k0_load_type_nibble": k0_load[1] if k0_load else None,
               "k1_load_type_nibble": k1_load[1] if k1_load else None}
        findings.append(rec)
        if is_zero(k0_load) or not is_zero(k0_store) or is_zero(k1_load) or is_zero(k1_store):
            verdict = "REFUTED (see findings)"
    out["verdict"] = verdict
    out["findings"] = findings
    return out


def h5_slot_b(cases):
    out = {"hypothesis": "H5: attachment-slot-b never appears in this harness's matrix"}
    present_anywhere = []
    for name, c in cases.items():
        n = c["named"].get("attachment-slot-b", {"present": False})
        if n["present"]:
            present_anywhere.append(name)
    verdict = "SUPPORTED (non-reproduction)" if not present_anywhere else \
        "REFUTED (present in: %s)" % present_anywhere
    out["verdict"] = verdict
    out["findings"] = {"present_in_cases": present_anywhere}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    run_a, run_b = R.RUNS
    cases_a = load(run_a)
    cases_b = load(run_b)

    # verify.py --captured already proved the two runs are byte-exact on
    # every gated field except a bounded, explicitly tolerated
    # content_captured flake (present+size still agree in that case). The
    # hypothesis analysis below should not be crippled by that one flaked
    # read, so it operates on `merged`: run_a's data, with the specific
    # (case, role) pairs where run_a failed to capture content but run_b did
    # backfilled from run_b. Both runs are equally valid GPU observations of
    # the same case -- see PRE_REGISTRATION.md section 6 / CAPTURE_CONTRACT.json.
    merged, fallback_used_for = merge_with_flake_fallback(cases_a, cases_b)

    report = {
        "schema": 1,
        "runs": [run_a, run_b],
        "n_cases": len(cases_a),
        "status_summary_run_a": _status_summary(cases_a),
        "status_summary_run_b": _status_summary(cases_b),
        "flake_fallback_used_for": fallback_used_for,
        "h1_depth_stencil_slot_reuse": h1_depth_stencil(merged),
        "h2_array_mip_field_mapping": h2_array_mip(merged),
        "h3_boundary_behavior": h3_boundary(merged),
        "h4_msaa_resolve_slot": h4_resolve(merged),
        "h5_attachment_slot_b": h5_slot_b(merged),
    }
    # Cross-run agreement check for the hypothesis-relevant fields specifically
    # (verify.py --captured already checked byte-exactness of the full gated
    # record; this is a redundant, hypothesis-scoped re-check for defense in
    # depth and human-readable reporting). Only flagged when BOTH runs
    # actually captured content and it differs -- a one-sided flake (already
    # reported above) is not a disagreement.
    disagreements = []
    for name in cases_a:
        if name not in cases_b:
            disagreements.append((name, "missing in run_b")); continue
        a, b = cases_a[name], cases_b[name]
        wa = a["named"]["mrt-attachment-descriptors"].get("window_hex")
        wb = b["named"]["mrt-attachment-descriptors"].get("window_hex")
        if wa is not None and wb is not None and wa != wb:
            disagreements.append((name, "mrt-attachment-descriptors window_hex differs"))
    report["cross_run_disagreements"] = disagreements

    text = render_report(report)
    print(text)

    if args.write:
        (HERE / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True))
        (HERE / "analysis" / "report.txt").parent.mkdir(exist_ok=True)
        (HERE / "analysis" / "report.txt").write_text(text)
        print("wrote analysis.json, analysis/report.txt")


def _status_summary(cases):
    s = {}
    for c in cases.values():
        s[c["status"]] = s.get(c["status"], 0) + 1
    return s


def render_report(report):
    lines = []
    lines.append(f"EXP-0132 analysis -- runs {report['runs']}")
    lines.append(f"status summary A: {report['status_summary_run_a']}")
    lines.append(f"status summary B: {report['status_summary_run_b']}")
    lines.append(f"cross-run disagreements: {report['cross_run_disagreements']}")
    lines.append(f"flake fallback used for (content_captured flake, backfilled from run B): "
                  f"{report['flake_fallback_used_for']}")
    for key in ("h1_depth_stencil_slot_reuse", "h2_array_mip_field_mapping",
                "h3_boundary_behavior", "h4_msaa_resolve_slot", "h5_attachment_slot_b"):
        h = report[key]
        lines.append("")
        lines.append(f"== {h['hypothesis']} ==")
        lines.append(f"VERDICT: {h['verdict']}")
        lines.append(json.dumps(h["findings"], indent=2))
    return "\n".join(lines)


if __name__ == "__main__":
    main()
