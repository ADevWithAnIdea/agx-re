#!/usr/bin/env python3
"""EXP-0132 standing gates: --selftest, --seqtest, --preflight,
--between-runs, --captured. Imports run.py's schema/functions as the single
source of truth; never restates masking logic.
"""
import argparse, json, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "harness"))
import run as R
import casematrix as CM

FIXTURES = HERE / "harness" / "fixtures"
RAW = HERE / "raw"


# ---------- shared helpers ----------

def tree_state():
    r1 = RAW / R.RUNS[0]
    r2 = RAW / R.RUNS[1]
    r1_closed = r1.exists() and (r1 / "04_dispatch.json").exists()
    r2_closed = r2.exists() and (r2 / "04_dispatch.json").exists()
    if r2_closed:
        return "RUN02_PRESENT"
    if r1_closed:
        return "RUN01_PRESENT"
    if not r1.exists() and not r2.exists():
        return "PRE_GPU"
    return "PARTIAL"  # a half-finished run dir exists -- never auto-repaired


def load_case_lines(run_id):
    p = RAW / run_id / "03_results.jsonl"
    return [json.loads(l) for l in open(p)]


# ---------- --selftest (no GPU, no raw/ required) ----------

def selftest():
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    # 1. mask_stride masks exactly the expected bytes.
    data = bytes(range(0x40))
    masked = R.mask_stride(data, 0x20, R.ADDR_OFFSET, R.ADDR_LEN)
    expect = bytearray(data)
    for base in (0, 0x20):
        for i in range(R.ADDR_OFFSET, R.ADDR_OFFSET + R.ADDR_LEN):
            expect[base + i] = 0
    check("mask_stride_masks_expected_bytes", masked == bytes(expect))
    check("mask_stride_leaves_other_bytes", masked[0] == data[0] and masked[0x10] == data[0x10])

    # 2. mask_stride is a no-op outside the addr window (idempotent double-mask).
    check("mask_stride_idempotent", R.mask_stride(masked, 0x20, R.ADDR_OFFSET, R.ADDR_LEN) == masked)

    # 3. fixtures from RECORDED REALITY: a real inventory.tsv + real captured
    #    bytes from this experiment's own pre-capture diagnostic phase
    #    (PRE_REGISTRATION.md section 2 / PROGRESS.md M6), committed under
    #    harness/fixtures/. Build a synthetic dumpdir shaped exactly like a
    #    live run's and exercise the real extract_named() on it.
    inv_fixture = FIXTURES / "i1_inventory.tsv"
    mrt_fixture = FIXTURES / "i1_va_10000018200_excerpt.bin"
    cca_fixture = FIXTURES / "i1_va_10000128000_excerpt.bin"
    check("fixtures_present", inv_fixture.exists() and mrt_fixture.exists() and cca_fixture.exists())

    with tempfile.TemporaryDirectory() as td:
        dumpdir = Path(td) / "dumps"
        sub = dumpdir / "dump00"
        sub.mkdir(parents=True)
        shutil.copy(inv_fixture, sub / "inventory.tsv")
        shutil.copy(mrt_fixture, sub / "va_10000018200.bin")
        shutil.copy(cca_fixture, sub / "va_10000128000.bin")
        inv = R.read_inventory(dumpdir)
        check("read_inventory_finds_mrt_role",
              ("0x10000018200", "mrt-attachment-descriptors") in inv)
        addrs = {}
        named = R.extract_named(dumpdir, inv, addrs)
        check("extract_named_schema",
              all(set(v) <= (R.NAMED_KEYS | {"window_hex"}) for v in named.values()))
        check("extract_named_mrt_present_captured",
              named["mrt-attachment-descriptors"]["present"]
              and named["mrt-attachment-descriptors"]["content_captured"])
        base_window = named["mrt-attachment-descriptors"]["window_hex"]
        base_cca = named["clear-color-arena"]["window_hex"]

        # 4. Full-pipeline mutator A: flip a byte OUTSIDE any masked address
        #    subfield (k=1 LOAD record's format byte, relative +0x41, well
        #    away from any +0x08..+0x0c window) -> the gated window MUST
        #    change. Proves the gate is not vacuously insensitive.
        raw = bytearray((sub / "va_10000018200.bin").read_bytes())
        mutate_off = 0x20 + 1 * 0x20 + 0x01  # k=1 record, byte+1 (format-ish byte, not address)
        if mutate_off < len(raw):
            raw[mutate_off] ^= 0xFF
            (sub / "va_10000018200.bin").write_bytes(bytes(raw))
            inv2 = R.read_inventory(dumpdir)
            named2 = R.extract_named(dumpdir, inv2, {})
            check("mutator_semantic_byte_changes_gate",
                  named2["mrt-attachment-descriptors"]["window_hex"] != base_window)
            # restore
            raw[mutate_off] ^= 0xFF
            (sub / "va_10000018200.bin").write_bytes(bytes(raw))
        else:
            check("mutator_semantic_byte_changes_gate", False)

        # 5. Full-pipeline mutator B: flip a byte INSIDE a masked address
        #    subfield (k=1 LOAD record's relative +0x08) -> the gated window
        #    MUST NOT change. Proves the known allocator-address
        #    nondeterminism is actually excluded, per the standing
        #    "no nondeterministic field in a gated record" rule.
        raw = bytearray((sub / "va_10000018200.bin").read_bytes())
        addr_off = 0x20 + 1 * 0x20 + R.ADDR_OFFSET
        if addr_off < len(raw):
            raw[addr_off] ^= 0xFF
            (sub / "va_10000018200.bin").write_bytes(bytes(raw))
            inv3 = R.read_inventory(dumpdir)
            named3 = R.extract_named(dumpdir, inv3, {})
            check("mutator_address_byte_does_not_change_gate",
                  named3["mrt-attachment-descriptors"]["window_hex"] == base_window)
            raw[addr_off] ^= 0xFF
            (sub / "va_10000018200.bin").write_bytes(bytes(raw))
        else:
            check("mutator_address_byte_does_not_change_gate", False)

        # 6. Full-pipeline mutator C: flip one of the two known-flaky
        #    clear-color-arena bytes (relative 0x536) -> gated window MUST
        #    NOT change (this is the empirically-found nondeterministic
        #    field being excluded, PRE_REGISTRATION.md section 6).
        rawc = bytearray((sub / "va_10000128000.bin").read_bytes())
        if R.CCA_FLAKY_OFFSETS[0] < len(rawc):
            rawc[R.CCA_FLAKY_OFFSETS[0]] ^= 0xFF
            (sub / "va_10000128000.bin").write_bytes(bytes(rawc))
            inv4 = R.read_inventory(dumpdir)
            named4 = R.extract_named(dumpdir, inv4, {})
            check("mutator_known_flaky_byte_does_not_change_gate",
                  named4["clear-color-arena"]["window_hex"] == base_cca)
            rawc[R.CCA_FLAKY_OFFSETS[0]] ^= 0xFF
            (sub / "va_10000128000.bin").write_bytes(bytes(rawc))
        else:
            check("mutator_known_flaky_byte_does_not_change_gate", False)

        # 7. A byte just past the known-flaky pair in clear-color-arena
        #    (0x538) DOES still change the gate -- proves masking is
        #    narrowly scoped to the two known bytes, not the whole role.
        rawc = bytearray((sub / "va_10000128000.bin").read_bytes())
        if 0x538 < len(rawc):
            rawc[0x538] ^= 0xFF
            (sub / "va_10000128000.bin").write_bytes(bytes(rawc))
            inv5 = R.read_inventory(dumpdir)
            named5 = R.extract_named(dumpdir, inv5, {})
            check("mutator_adjacent_byte_still_changes_gate",
                  named5["clear-color-arena"]["window_hex"] != base_cca)
            rawc[0x538] ^= 0xFF
            (sub / "va_10000128000.bin").write_bytes(bytes(rawc))
        else:
            check("mutator_adjacent_byte_still_changes_gate", False)

    # 8. Absent-dump directory -> empty inventory, all roles present=False
    #    (models a case where --dump silently produced nothing, e.g. the
    #    fixed WTRACE_DIRECT_SNAPSHOT_UNAVAILABLE path).
    with tempfile.TemporaryDirectory() as td2:
        inv_empty = R.read_inventory(Path(td2) / "nope")
        check("absent_dump_gives_empty_inventory", inv_empty == {})
        named_empty = R.extract_named(Path(td2) / "nope", inv_empty, {})
        check("absent_dump_all_roles_not_present",
              all(not v["present"] for v in named_empty.values()))

    # 9. casematrix invariants: 16 cases, unique names, schema fields present.
    check("casematrix_total_16", CM.TOTAL == 16)
    check("casematrix_unique_names", len({c["name"] for c in CM.CASES}) == CM.TOTAL)
    check("casematrix_has_boundary_cases",
          sum(1 for c in CM.CASES if c["boundary"]) == 2)

    # 10. STATUS_ALLOWED / CASE_KEYS / TIMING_KEYS schema self-consistency.
    check("status_allowed_nonempty", len(R.STATUS_ALLOWED) > 0)
    check("case_keys_frozen", R.CASE_KEYS == {"i", "name", "axis", "boundary", "status",
                                               "cb_status", "cb_error", "rts", "named"})

    ok = all(v for _, v in checks)
    print(f"--selftest: {sum(v for _, v in checks)}/{len(checks)} PASS")
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    return ok


# ---------- --seqtest (tree-state detection; uses a temp dir, never real raw/) ----------

def seqtest():
    checks = []
    with tempfile.TemporaryDirectory() as td:
        fake_raw = Path(td) / "raw"
        fake_raw.mkdir()
        orig = R.HERE

        class Shim:
            pass
        # Exercise the SAME tree_state() logic against a temp layout by
        # monkeypatching the module-level RAW path used here.
        global RAW
        real_raw = RAW
        try:
            RAW = fake_raw
            checks.append(("pre_gpu_detected", tree_state() == "PRE_GPU"))

            r1 = fake_raw / R.RUNS[0]
            r1.mkdir()
            checks.append(("run1_open_not_closed_still_pre_gpu_or_partial",
                            tree_state() in ("PARTIAL",)))
            (r1 / "04_dispatch.json").write_text("{}")
            checks.append(("run1_closed_detected", tree_state() == "RUN01_PRESENT"))

            r2 = fake_raw / R.RUNS[1]
            r2.mkdir()
            checks.append(("run2_open_not_closed_still_run1",
                            tree_state() == "RUN01_PRESENT"))
            (r2 / "04_dispatch.json").write_text("{}")
            checks.append(("run2_closed_detected", tree_state() == "RUN02_PRESENT"))
        finally:
            RAW = real_raw

    ok = all(v for _, v in checks)
    print(f"--seqtest: {sum(v for _, v in checks)}/{len(checks)} PASS")
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    return ok


# ---------- --preflight (before run01) ----------

def preflight():
    checks = []
    checks.append(("tree_state_pre_gpu_or_run01", tree_state() in ("PRE_GPU", "RUN01_PRESENT")))
    for p in R.AUTH_ALL:
        checks.append((f"authored_file_exists:{p}", (HERE / p).exists()))
    bindir = HERE / "work" / "bin_preflight"
    if bindir.exists():
        shutil.rmtree(bindir)
    build, ok = R.build_harness(bindir)
    checks.append(("harness_builds", ok))
    inputs = R.env_snapshot()
    checks.append(("git_revision_resolves", bool(inputs["git_revision"])))
    ok_all = all(v for _, v in checks)
    print(f"--preflight: {sum(v for _, v in checks)}/{len(checks)} PASS")
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    return ok_all


# ---------- --between-runs (after run01 closed, before run02) ----------

def between_runs():
    checks = []
    state = tree_state()
    checks.append(("state_is_run01_present", state == "RUN01_PRESENT"))
    r1 = RAW / R.RUNS[0]
    for p in ("00_inputs.json", "01_cases.json", "02_build.json",
              "03_results.jsonl", "03_timing.jsonl", "04_dispatch.json"):
        checks.append((f"run01_has:{p}", (r1 / p).exists()))
    if (r1 / "04_dispatch.json").exists():
        d = json.loads((r1 / "04_dispatch.json").read_text())
        checks.append(("run01_n_cases_matches_matrix", d.get("n_cases") == CM.TOTAL))
    checks.append(("run02_not_yet_present", not (RAW / R.RUNS[1]).exists()))
    ok = all(v for _, v in checks)
    print(f"--between-runs: {sum(v for _, v in checks)}/{len(checks)} PASS")
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    return ok


# ---------- --captured (final gate, after both runs) ----------

def captured():
    checks = []
    state = tree_state()
    checks.append(("state_is_run02_present", state == "RUN02_PRESENT"))
    if state != "RUN02_PRESENT":
        print("--captured: FAIL (wrong tree state)")
        return False

    lines_a = load_case_lines(R.RUNS[0])
    lines_b = load_case_lines(R.RUNS[1])
    checks.append(("both_runs_16_cases", len(lines_a) == CM.TOTAL and len(lines_b) == CM.TOTAL))

    flakes = []
    mismatches = []
    for a, b in zip(lines_a, lines_b):
        if a["name"] != b["name"]:
            mismatches.append((a["name"], "name order mismatch"))
            continue
        # Everything in CASE_KEYS is already gated/masked by run.py; compare
        # directly, with one tolerated asymmetry: a role's content_captured
        # flipping true/false while size/presence agree (a residual read
        # flake despite the widened retry budget) -- budget <=3 total.
        for role in R.NAMED_ROLES:
            na, nb = a["named"][role], b["named"][role]
            if na["present"] != nb["present"] or na["size"] != nb["size"]:
                mismatches.append((a["name"], f"{role} present/size mismatch"))
                continue
            if na["content_captured"] != nb["content_captured"]:
                flakes.append((a["name"], role))
                continue
            if na.get("window_hex") != nb.get("window_hex"):
                mismatches.append((a["name"], f"{role} window_hex mismatch"))
        for k in ("status", "cb_status", "cb_error", "rts", "axis", "boundary"):
            if a[k] != b[k]:
                mismatches.append((a["name"], f"{k} mismatch: {a[k]!r} vs {b[k]!r}"))

    checks.append(("no_semantic_mismatches", len(mismatches) == 0))
    checks.append(("flake_budget_le_3", len(flakes) <= 3))

    ok = all(v for _, v in checks)
    print(f"--captured: {sum(v for _, v in checks)}/{len(checks)} PASS")
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    if mismatches:
        print("  MISMATCHES:")
        for m in mismatches:
            print("   ", m)
    if flakes:
        print(f"  TOLERATED FLAKES ({len(flakes)}):")
        for fl in flakes:
            print("   ", fl)
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--seqtest", action="store_true")
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--captured", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.seqtest:
        sys.exit(0 if seqtest() else 1)
    if args.preflight:
        sys.exit(0 if preflight() else 1)
    if args.between_runs:
        sys.exit(0 if between_runs() else 1)
    if args.captured:
        sys.exit(0 if captured() else 1)
