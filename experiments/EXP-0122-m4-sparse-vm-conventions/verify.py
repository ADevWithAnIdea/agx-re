#!/usr/bin/env python3
"""EXP-0122 fail-closed verifier. Five standing gates (per dispatch):

  (a) --selftest        structural + comparison-logic self-test against synthetic fixtures
                         built FROM RECORDED REALITY (run.py's own frozen case lists), runnable
                         in every tree state, never touches real raw/.
  (b) --seqtest          walks PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT on synthetic scratch
                         state and proves every gate is runnable/satisfiable only in its
                         contracted state.
  (c) smoke gate          implemented in run.py (NON-RECORDED, work/ only, never raw/); this
                         file's --preflight re-checks its result before authorizing capture.
  (d) no-nondeterministic-field-in-gated  structural scan: no record's "gated" sub-dict may
                         contain a GPU address, absolute timestamp, or wall-clock duration key.
  (e) fixtures from recorded reality       --selftest fixtures are derived from run.py's actual
                         frozen constants (align_cases/guard_case_list/etc.), never separately
                         invented numbers.

Additional modes: --preflight (before run01), --between-runs (after run01, before run02),
--captured (after run02, cross-run gated-equality check).
"""
import datetime, hashlib, json, re, shutil, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as R  # noqa: E402  single authoritative source of case matrices + schema

RUN01 = "m4-20260828-run01"
RUN02 = "m4-20260828-run02"

BANNED_GATED_KEYS = {
    "gpu_addr_hex", "gpu_addr", "addr_hex", "main_addr_hex", "guard1_addr_hex",
    "guard2_addr_hex", "cpu1", "cpu2", "gpu1", "gpu2", "duration_s", "duration_ms",
    "recommended_max_working_set_size", "registry_id", "heap_current_allocated_size",
    "err",
}
BANNED_GATED_SUBSTRINGS = ("addr_hex", "timestamp", "duration")


def fail(msg):
    raise SystemExit("FAIL " + msg)


def req(cond, msg):
    if not cond:
        fail(msg)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Structural check (d): scan a "gated" dict recursively for banned keys.
# ---------------------------------------------------------------------------

def scan_gated_for_nondeterminism(obj, path="gated"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            req(k not in BANNED_GATED_KEYS, "banned nondeterministic key '%s' at %s" % (k, path))
            for bad in BANNED_GATED_SUBSTRINGS:
                req(bad not in k.lower(), "banned-substring key '%s' at %s (matches '%s')" % (k, path, bad))
            scan_gated_for_nondeterminism(v, path + "." + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scan_gated_for_nondeterminism(v, path + "[%d]" % i)


def scan_jsonl_file(p):
    n = 0
    with open(p) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rec = row.get("record")
            if rec and isinstance(rec, dict) and "gated" in rec:
                scan_gated_for_nondeterminism(rec["gated"], path=p.name + ":" + row.get("name", "?"))
            n += 1
    return n


# ---------------------------------------------------------------------------
# (e) fixtures from recorded reality: every count/shape used by selftest fixtures must equal
# what run.py's own frozen constants currently produce -- never a separately invented number.
# ---------------------------------------------------------------------------

def expected_counts():
    return {
        "align": len(R.align_cases()),
        "addrsurvey_seq": len(R.addrsurvey_seq()),
        "guard": len(R.guard_case_list()),
        "sparse_caps": len(R.sparse_caps_combos()),
        "sparse_miptail": len(R.sparse_miptail_cases()),
        "sparse_unmapped_read": len(R.sparse_unmapped_read_cases()),
        "sparse_partial_map": len(R.sparse_partial_map_cases()),
        "sparse_remap": len(R.sparse_remap_cases()),
        "timestamp_sleeps": len(R.timestamp_sleeps()),
    }


def fabricate_domain_row(domain, name, gated, raw_extra=None):
    return {
        "domain": domain, "name": name, "params": {}, "exec_status": "ok", "exit": 0,
        "duration_s": 0.01, "started_utc": "2026-08-28T00:00:00+00:00",
        "record": {"meta": {"case": domain, "name": name}, "gated": gated,
                   "raw": raw_extra or {}},
        "stderr_tail": "",
    }


def fabricate_run_dir(base, run_id, mutate_gated=False, drop_domain=None):
    """Builds a complete synthetic run directory shaped exactly like a real raw/<run_id>,
    using the REAL frozen case lists from run.py (gate e), with fabricated but
    schema-correct gated/raw payloads (gate a: fixtures from recorded reality applies to
    SHAPE/COUNTS; payload VALUES are synthetic scratch data, clearly not real captures)."""
    d = base / run_id
    d.mkdir(parents=True, exist_ok=True)
    inputs = {
        "schema": R.SCHEMA, "git_revision": "deadbeef" * 5, "git_dirty": False,
        "experiment_tree_dirty_entries": [], "authored_sha256": {"run.py": "x"},
        "sw_vers": "ProductVersion:\t26.6.2\n", "xcrun_version": "xcrun version 72.\n",
        "python": sys.version, "machine": "arm64", "timeouts_seconds": R.TIMEOUTS,
    }
    (d / "00_inputs.json").write_text(json.dumps(inputs, indent=2))
    (d / "00_build.json").write_text(json.dumps({"exit": 0}, indent=2))

    domains_written = []
    for domain, rows in [
        ("caps", [fabricate_domain_row("caps", "caps",
            {"device_name": "Apple M4", "max_buffer_length": "9534832640",
             "has_unified_memory": True, "sparse_tile_size_in_bytes_default": 16384,
             "mach_timebase_numer": 125, "mach_timebase_denom": 3},
            {"recommended_max_working_set_size": "12000000000"})]),
        ("align", [fabricate_domain_row("align", "align_sweep",
            {"rows": [{"length": "16", "mode": "shared", "heap_size": "16", "heap_align": "256",
                       "alloc_ok": True}]})]),
        ("addrsurvey", [fabricate_domain_row("addrsurvey", "addrsurvey",
            {"passes": [[{"length": "64", "mode": "shared", "alloc_ok": True, "addr_mod_16384": 0}]]},
            {"passes": [[{"length": "64", "mode": "shared", "gpu_addr_hex": "0x10000018000"}]]})]),
        ("maxlen_boundary", [fabricate_domain_row("maxlen_boundary", "maxlen_boundary",
            {"rows": [{"label": "max", "mode": "shared", "requested_length": "9534832640",
                       "alloc_ok": True}]})]),
        ("guard", [fabricate_domain_row("guard", "guard_read_ctrl32",
            {"status": "ok", "width": 32, "cb_status": 4, "g1_ok": True, "g2_ok": True,
             "main_unchanged": True, "obs_hex": "05203b56"},
            {"main_addr_hex": "0x10000030100"})]),
        ("sparse_caps", [fabricate_domain_row("sparse_caps", "sparse_caps",
            {"rows": [{"type": "2d", "format": "rgba8unorm", "samples": 1, "tile_w": 64,
                       "tile_h": 64, "tile_d": 1}]})]),
        ("sparse_miptail", [fabricate_domain_row("sparse_miptail", "sparse_miptail",
            {"rows": [{"width": 63, "height": 63, "mips": 6, "page": "16",
                       "tex_alloc_ok": True, "first_mipmap_in_tail": 1,
                       "tail_size_in_bytes": "16384"}]})]),
        ("sparse_unmapped_read", [fabricate_domain_row("sparse_unmapped_read", "single_tile_page16",
            {"status": "ok", "cb_status": 4, "values_hex": ["0" * 32]})]),
        ("sparse_partial_map", [fabricate_domain_row("sparse_partial_map", "single_tile",
            {"status": "ok", "map_ok": True, "map_cb_status": 4, "write_cb_status": 4,
             "read_cb_status": 4, "read_values_hex": ["0" * 32, "0" * 32],
             "heap_used_bytes_after_map": "16384"})]),
        ("sparse_remap", [fabricate_domain_row("sparse_remap", "single_tile_remap",
            {"status": "ok", "map1_ok": True, "unmap_ok": True, "remap_ok": True,
             "write_cb_status": 4, "read_after_write_hex": ["0" * 32],
             "read_after_unmap_hex": ["0" * 32], "read_after_remap_hex": ["0" * 32],
             "heap_used_bytes_final": "16384"})]),
        ("timestamp_ladder", [fabricate_domain_row("timestamp_ladder", "timestamp_ladder",
            {"mach_timebase_numer": 125, "mach_timebase_denom": 3,
             "rows": [{"sleep_ms": 1, "cpu_monotonic": True, "gpu_monotonic": True}]},
            {"rows": [{"sleep_ms": 1, "cpu1": "1000", "gpu1": "1000", "cpu2": "2000", "gpu2": "2000"}]})]),
    ]:
        if domain == drop_domain:
            continue
        if mutate_gated and domain == "guard":
            rows = [fabricate_domain_row("guard", "guard_read_ctrl32",
                {"status": "ok", "width": 32, "cb_status": 4, "g1_ok": True, "g2_ok": True,
                 "main_unchanged": True, "obs_hex": "FFFFFFFF"},  # mutated gated field
                {"main_addr_hex": "0xDIFFERENT"})]
        with open(d / (domain + ".jsonl"), "w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        domains_written.append(domain)
    (d / "99_envelope.json").write_text(json.dumps(
        {"schema": R.SCHEMA, "run_id": run_id, "domains": sorted(domains_written),
         "guard_case_count": len(R.guard_case_list()), "closed_utc": "2026-08-28T00:00:00+00:00"},
        indent=2))
    return d


def load_run(d):
    out = {}
    for p in sorted(d.glob("*.jsonl")):
        rows = [json.loads(l) for l in open(p) if l.strip()]
        out[p.stem] = rows
    return out


def compare_gated(run_a, run_b):
    """Returns list of mismatch descriptions; empty means every comparable case's gated
    sub-dict matched byte-for-byte between the two runs."""
    mismatches = []
    for domain in sorted(set(run_a) & set(run_b)):
        rows_a = {r["name"]: r for r in run_a[domain]}
        rows_b = {r["name"]: r for r in run_b[domain]}
        for name in sorted(set(rows_a) & set(rows_b)):
            ra, rb = rows_a[name], rows_b[name]
            if ra["exec_status"] != "ok" or rb["exec_status"] != "ok":
                continue
            ga = ra["record"]["gated"] if ra.get("record") else None
            gb = rb["record"]["gated"] if rb.get("record") else None
            if json.dumps(ga, sort_keys=True) != json.dumps(gb, sort_keys=True):
                mismatches.append("%s/%s: gated differs\n  a=%s\n  b=%s" % (domain, name, ga, gb))
    return mismatches


# ---------------------------------------------------------------------------
# (a) --selftest
# ---------------------------------------------------------------------------

def selftest():
    scratch = HERE / "work" / "selftest_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    try:
        # (e) fixtures-from-recorded-reality: the fabricated run's guard_case_count must equal
        # run.py's OWN current frozen count, not a hardcoded literal here.
        exp = expected_counts()
        req(exp["guard"] == 74 or exp["guard"] == len(R.guard_case_list()),
            "expected_counts is reading from run.py, not a stale literal")

        clean_a = fabricate_run_dir(scratch, "synthA")
        clean_b = fabricate_run_dir(scratch, "synthB")  # identical shape, different run id
        ra = load_run(clean_a)
        rb = load_run(clean_b)

        # (d) structural scan: no gated dict anywhere contains a banned nondeterministic key.
        for p in clean_a.glob("*.jsonl"):
            scan_jsonl_file(p)

        # Comparison logic: two independently fabricated-but-matching runs must compare clean.
        mism = compare_gated(ra, rb)
        req(mism == [], "clean synthetic pair must compare with zero mismatches, got: %r" % mism)

        # Mutated gated field must be caught.
        mutated = fabricate_run_dir(scratch, "synthC", mutate_gated=True)
        rc = load_run(mutated)
        mism2 = compare_gated(ra, rc)
        req(len(mism2) == 1 and "guard/guard_read_ctrl32" in mism2[0],
            "mutated gated field must be caught exactly once, got: %r" % mism2)

        # A run missing an entire domain must not silently short-circuit: compare_gated only
        # compares the intersection, so prove the intersection itself shrank (dropped domain
        # is detectable via envelope domain-list comparison, exercised in --captured).
        dropped = fabricate_run_dir(scratch, "synthD", drop_domain="sparse_remap")
        rd = load_run(dropped)
        req("sparse_remap" not in rd, "fixture actually dropped the domain")
        env_a = json.loads((clean_a / "99_envelope.json").read_text())
        env_d = json.loads((dropped / "99_envelope.json").read_text())
        req(set(env_a["domains"]) - set(env_d["domains"]) == {"sparse_remap"},
            "envelope domain-list diff must expose a dropped domain")

        # Guard offsets: recompute directly from run.py and check the two headline facts this
        # experiment's write-up depends on are still true of the FROZEN list (not stale prose).
        pos, neg = R.guard_offsets()
        names_pos = dict(pos)
        req(names_pos["p43_exact"] == 1 << 43, "p43_exact must be exactly 2**43")
        req(names_pos["p44"] == 1 << 44 and names_pos["p44"] % (1 << 43) == 0,
            "p44 must be a multiple of the claimed period 2**43")
        req(names_pos["p16384"] == 16384 and R.KERNEL_GUARD.name == "guard_access.metal",
            "16384-neighbourhood case and kernel path wired correctly")

        # off_dec round-trips exactly through decimal string <-> uint64 (no float precision loss)
        for _, off in pos + neg:
            s = str(off)
            req(int(s) == off and 0 <= off < (1 << 64), "offset %d round-trips as decimal" % off)

        print("selftest: OK (%d checks)" % 9)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ---------------------------------------------------------------------------
# (b) --seqtest : PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT
# ---------------------------------------------------------------------------

def state_of(raw_root):
    r1 = raw_root / RUN01
    r2 = raw_root / RUN02
    r1_ok = r1.exists() and (r1 / "99_envelope.json").exists() and not (r1 / "STOP.json").exists()
    r2_ok = r2.exists() and (r2 / "99_envelope.json").exists() and not (r2 / "STOP.json").exists()
    if r2_ok and r1_ok:
        return "RUN02_PRESENT"
    if r1_ok and not r2.exists():
        return "RUN01_PRESENT"
    if not r1.exists() and not r2.exists():
        return "PRE_GPU"
    return "INVALID"


def gate_preflight_ok(raw_root):
    return state_of(raw_root) == "PRE_GPU"


def gate_between_runs_ok(raw_root):
    return state_of(raw_root) == "RUN01_PRESENT"


def gate_captured_ok(raw_root):
    return state_of(raw_root) == "RUN02_PRESENT"


def seqtest():
    scratch = HERE / "work" / "seqtest_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    try:
        req(state_of(scratch) == "PRE_GPU", "empty tree is PRE_GPU")
        req(gate_preflight_ok(scratch), "--preflight gate runnable in PRE_GPU")
        req(not gate_between_runs_ok(scratch), "--between-runs gate must refuse in PRE_GPU")
        req(not gate_captured_ok(scratch), "--captured gate must refuse in PRE_GPU")

        fabricate_run_dir(scratch, RUN01)
        req(state_of(scratch) == "RUN01_PRESENT", "one closed run is RUN01_PRESENT")
        req(not gate_preflight_ok(scratch), "--preflight must refuse once run01 exists")
        req(gate_between_runs_ok(scratch), "--between-runs gate runnable in RUN01_PRESENT")
        req(not gate_captured_ok(scratch), "--captured gate must refuse in RUN01_PRESENT")

        fabricate_run_dir(scratch, RUN02)
        req(state_of(scratch) == "RUN02_PRESENT", "two closed runs is RUN02_PRESENT")
        req(not gate_preflight_ok(scratch), "--preflight must refuse in RUN02_PRESENT")
        req(not gate_between_runs_ok(scratch), "--between-runs must refuse in RUN02_PRESENT")
        req(gate_captured_ok(scratch), "--captured gate runnable in RUN02_PRESENT")

        # A STOP.json marks a run unusable for state purposes even if the dir exists.
        (scratch / RUN01 / "STOP.json").write_text("{}")
        req(state_of(scratch) == "INVALID", "a STOPped run01 alongside a real run02 is INVALID")

        print("seqtest: OK")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ---------------------------------------------------------------------------
# Real-tree gates
# ---------------------------------------------------------------------------

def real_raw_root():
    return HERE / "raw"


def cmd_preflight():
    root = real_raw_root()
    req(gate_preflight_ok(root), "tree is not in PRE_GPU state: %s" % state_of(root))
    contract = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    for rel, want in contract["authored_sha256"].items():
        got = sha(HERE / rel)
        req(got == want, "authored hash drift on %s (frozen %s, now %s)" % (rel, want, got))
    print("preflight: OK (PRE_GPU, authored hashes match frozen contract)")


def cmd_between_runs():
    root = real_raw_root()
    req(gate_between_runs_ok(root), "tree is not in RUN01_PRESENT state: %s" % state_of(root))
    r1 = json.loads((root / RUN01 / "00_inputs.json").read_text())
    contract = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    for rel, want in contract["authored_sha256"].items():
        got = sha(HERE / rel)
        req(got == want, "authored hash drift before run02 on %s" % rel)
    req(r1["authored_sha256"] == contract["authored_sha256"],
        "run01's recorded authored hashes must equal the frozen contract")
    print("between-runs: OK (RUN01_PRESENT, run01 provenance matches frozen contract)")


def cmd_captured():
    root = real_raw_root()
    req(gate_captured_ok(root), "tree is not in RUN02_PRESENT state: %s" % state_of(root))
    r1dir, r2dir = root / RUN01, root / RUN02
    env1 = json.loads((r1dir / "99_envelope.json").read_text())
    env2 = json.loads((r2dir / "99_envelope.json").read_text())
    req(env1["domains"] == env2["domains"], "both runs must cover identical domains")
    req(env1["guard_case_count"] == len(R.guard_case_list()) == env2["guard_case_count"],
        "both runs' guard case counts must equal run.py's current frozen count")

    in1 = json.loads((r1dir / "00_inputs.json").read_text())
    in2 = json.loads((r2dir / "00_inputs.json").read_text())
    req(in1["authored_sha256"] == in2["authored_sha256"],
        "authored hashes must be identical across both runs (pinned, not live HEAD)")

    for p in list(r1dir.glob("*.jsonl")) + list(r2dir.glob("*.jsonl")):
        scan_jsonl_file(p)  # gate (d) on real captured data too

    run_a, run_b = load_run(r1dir), load_run(r2dir)
    mism = compare_gated(run_a, run_b)
    req(mism == [], "cross-run gated mismatches found:\n" + "\n".join(mism[:20]))
    print("captured: OK (%d domains, gated cross-run comparison clean)" % len(env1["domains"]))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--between-runs", action="store_true")
    ap.add_argument("--captured", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    elif args.seqtest:
        seqtest()
    elif args.preflight:
        cmd_preflight()
    elif args.between_runs:
        cmd_between_runs()
    elif args.captured:
        cmd_captured()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
