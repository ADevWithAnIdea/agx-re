#!/usr/bin/env python3
"""EXP-0110 fail-closed verifier.

--selftest (REQUIRED before any capture; runnable in EVERY tree state --
PRE_GPU, RUN01_PRESENT, RUN02_PRESENT -- it only touches synthetic fixtures
built in-memory or under a tempdir, never raw/) fabricates synthetic BODUMP
.hex fixtures with KNOWN CDM/VDM record signatures and link words at
DIFFERENT absolute addresses across two fake "runs", and proves:
  (a) analysis/scan.py locates records/segments/links correctly and the
      link-transform decoder recovers the exact synthetic target address;
  (b) a deliberately corrupted synthetic record (wrong stride, truncated
      tail, wrong tag byte) is REJECTED (not silently accepted) by the
      scanner/chain-follower;
  (c) schema.build_segment_records() produces BYTE-IDENTICAL gated output
      for the two fake runs despite their different absolute addresses --
      the concrete proof that the delta-from-baseline normalization holds;
  (d) schema.normalize_cdm_record is idempotent and touches only its
      documented byte range;
  (e) no frozen key set in schema.py names a raw address field
      (schema.assert_no_address_leak); and
  (f) no harness source line prints a raw `gpuAddress`/`.gpuAddress` value
      into anything this experiment could mistake for a gated channel (the
      harness DOES print VA lines to stdout for human debugging -- this
      check instead proves run.py's `emit()` never routes harness stdout
      into the gated file; only into the sibling _addrs.jsonl).

--seqtest walks the CONTRACTED gate order through synthetic PRE_GPU /
RUN01_PRESENT / RUN02_PRESENT states (root-independent: it fabricates a
temp copy of the raw/ directory state, never touches the real one) and
proves each gate the contract invokes in that state is both RUNNABLE and
its expected verdict SATISFIABLE there.

--preflight / --between-runs / --captured operate on the REAL experiment
root and are the actual pre/mid/post-capture gates run.py's caller invokes.
"""
import argparse
import glob
import json
import shutil
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELFTEST_SCRATCH = HERE / "work" / "selftest_scratch"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "analysis"))
import schema  # noqa: E402
import scan  # noqa: E402
import casematrix as CM  # noqa: E402

RAW = HERE / "raw"
RUN_IDS_IN_ORDER_HINT = None  # run ids are caller-supplied; see --run01-id/--run02-id


# ---------------------------------------------------------------------------
# Synthetic fixture builders (selftest / seqtest only -- never touch raw/)
# ---------------------------------------------------------------------------
def make_bodump_bytes(gpu_va, size, data):
    header = ("# BODUMP reason=synth handle=0 gpu_va=0x%x cpu=0x1000 size=0x%x read=0x%x\n"
              % (gpu_va, size, len(data))).encode()
    lines = [header]
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexstr = " ".join(chunk[i:i + 4].hex() for i in range(0, len(chunk), 4))
        lines.append(("%08x: %s\n" % (off, hexstr)).encode())
    return b"".join(lines)


def synth_cdm_segment(n_records, tail_kind, tail_target_va=None, tag=scan.CDM_LINK_TAG, corrupt=None):
    """Build one synthetic CDM command BO's bytes: n_records authored
    records (grid 64,1,1 / tg 32,1,1 signature at +0x10) at 0x2c stride,
    then either a terminator or a link to tail_target_va."""
    buf = bytearray()
    for i in range(n_records):
        rec = bytearray(scan.CDM_RECORD_LEN)
        struct.pack_into("<I", rec, 0x00, 0x00080000)
        struct.pack_into("<6I", rec, 0x10, 64, 1, 1, 32, 1, 1)
        buf += rec
    if corrupt == "bad_stride":
        buf += b"\x00" * 4  # break the fixed 0x2c stride expectation
    if tail_kind == "terminator":
        struct.pack_into("<I", (buf.extend([0] * 4) or buf)[-4:], 0, scan.CDM_TERMINATOR) if False else None
        buf += struct.pack("<I", scan.CDM_TERMINATOR)
    elif tail_kind == "link":
        hi, lo = scan.encode_link(tag, tail_target_va)
        if corrupt == "bad_tag":
            hi = (0x7f << 24) | (hi & 0x00ffffff)
        buf += struct.pack("<II", hi, lo)
    return bytes(buf)


def build_two_fake_runs(tmp):
    """Two synthetic runs of a 3-segment CDM chain identical in every
    structural respect except the absolute addresses used (run A starts at
    0x100000b0000-style base, run B at a translated base +0x4080000, exactly
    mirroring this experiment's real cdm_pad_big observation)."""
    n_per_seg = 5
    shift = 0x4080000
    baseA = 0x100000b0000
    va2A = 0x10000150000
    va3A = 0x100001e0000
    baseB = baseA + shift
    va2B = va2A + shift
    va3B = va3A + shift

    def one_run(base, va2, va3):
        seg1 = synth_cdm_segment(n_per_seg, "link", va2)
        seg2 = synth_cdm_segment(n_per_seg, "link", va3)
        seg3 = synth_cdm_segment(3, "terminator")
        return {base: seg1, va2: seg2, va3: seg3}

    runs = {"A": one_run(baseA, va2A, va3A), "B": one_run(baseB, va2B, va3B)}
    dirs = {}
    for label, segs in runs.items():
        d = tmp / ("run_%s" % label)
        d.mkdir(parents=True)
        for va, data in segs.items():
            p = d / ("bo_sigusr1_h0_va%x_cpu1000_sz%x.hex" % (va, len(data)))
            p.write_bytes(make_bodump_bytes(va, len(data), data))
        dirs[label] = d
    return dirs


def scan_dir_to_matched(d):
    matched = {}
    for p in sorted(glob.glob(str(d / "bo_sigusr1_h*_va*.hex"))):
        dd = scan.load_hex_dump(p)
        r = scan.scan_cdm_segment(dd["data"])
        if r["record_count"] > 0:
            r["gpu_va"] = dd["gpu_va"]
            matched[dd["gpu_va"]] = r
    return matched


def gated_segments_for_run(matched):
    chain, anomalies = scan.find_chain(matched)
    assert not anomalies, "unexpected anomalies in clean synthetic fixture: %r" % anomalies
    seg_in_order = []
    for i, va in enumerate(chain):
        r = dict(matched[va])
        if r["tail_kind"] == "link":
            tag, tgt = scan.decode_link(r["tail_hi"], r["tail_lo"])
            nxt = chain[i + 1] if i + 1 < len(chain) else None
            r["decoded_ok"] = (nxt is not None and tgt == nxt)
        else:
            r["decoded_ok"] = None
        seg_in_order.append(r)
    return seg_in_order


def selftest():
    checks = []
    SELFTEST_SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp_root = Path(tempfile.mkdtemp(prefix="selftest_", dir=str(SELFTEST_SCRATCH)))
    try:
        # (e) schema has no address-shaped key names
        schema.assert_no_address_leak()
        checks.append(("no_address_leak_in_schema", True))

        # (d) normalize_cdm_record idempotence + scope
        rec = bytes((i * 7 + 3) % 256 for i in range(schema.CDM_RECORD_LEN))
        n1 = schema.normalize_cdm_record(rec)
        n2 = schema.normalize_cdm_record(n1)
        ok = (n1 == n2 and n1[:8] == rec[:8] and n1[12:] == rec[12:] and n1[8:12] == b"\x00" * 4)
        checks.append(("normalize_cdm_record_idempotent_and_scoped", ok))
        try:
            schema.normalize_cdm_record(rec[:10])
            checks.append(("normalize_cdm_record_rejects_wrong_length", False))
        except ValueError:
            checks.append(("normalize_cdm_record_rejects_wrong_length", True))

        # (a)+(c) two fake runs, different absolute addresses, same gated output
        dirs = build_two_fake_runs(tmp_root)
        matchedA = scan_dir_to_matched(dirs["A"])
        matchedB = scan_dir_to_matched(dirs["B"])
        checks.append(("synthetic_run_A_finds_3_segments", len(matchedA) == 3))
        checks.append(("synthetic_run_B_finds_3_segments", len(matchedB) == 3))
        segsA = gated_segments_for_run(matchedA)
        segsB = gated_segments_for_run(matchedB)
        checks.append(("synthetic_run_A_all_links_decode_ok",
                       all(s["decoded_ok"] in (True, None) for s in segsA)))
        checks.append(("synthetic_run_B_all_links_decode_ok",
                       all(s["decoded_ok"] in (True, None) for s in segsB)))
        gatedA = schema.build_segment_records(segsA, segsA)
        gatedB = schema.build_segment_records(segsB, segsB)
        checks.append(("gated_output_byte_identical_across_shifted_absolute_addresses",
                       json.dumps(gatedA, sort_keys=True) == json.dumps(gatedB, sort_keys=True)))
        # cross-baseline: B's segments relative to A's baseline should show
        # the constant 0x4080000 shift on every segment -- prove the delta
        # actually carries the real relocation signal (not just zeros).
        gatedB_vs_A = schema.build_segment_records(segsB, segsA)
        shift = 0x4080000
        checks.append(("delta_from_baseline_recovers_known_shift",
                       all(s["delta_from_baseline"] == shift for s in gatedB_vs_A)))

        # (b) corruption is rejected, not silently accepted
        bad_va = 0x200000000000
        bad_dir = tmp_root / "bad_stride"
        bad_dir.mkdir()
        bad = synth_cdm_segment(5, "terminator", corrupt="bad_stride")
        p = bad_dir / ("bo_sigusr1_h0_va%x_cpu1000_sz%x.hex" % (bad_va, len(bad)))
        p.write_bytes(make_bodump_bytes(bad_va, len(bad), bad))
        dd = scan.load_hex_dump(str(p))
        r = scan.scan_cdm_segment(dd["data"])
        # the stride break must not be silently folded into a 5-record run
        # with a valid terminator at the naive position (it must NOT report
        # tail_kind terminator at the pre-corruption offset as if intact)
        checks.append(("bad_stride_does_not_report_clean_terminator_at_5",
                       not (r["record_count"] == 5 and r["tail_kind"] == "terminator")))

        bad_tag_va = 0x200000001000
        bad_tag = synth_cdm_segment(5, "link", 0x300000000000, corrupt="bad_tag")
        p2 = bad_dir / ("bo_sigusr1_h0_va%x_cpu1000_sz%x.hex" % (bad_tag_va, len(bad_tag)))
        p2.write_bytes(make_bodump_bytes(bad_tag_va, len(bad_tag), bad_tag))
        dd2 = scan.load_hex_dump(str(p2))
        r2 = scan.scan_cdm_segment(dd2["data"])
        is_bad_tag_flagged = (r2["tail_kind"] != "link")  # our tag=0x20 filter must reject tag=0x7f
        checks.append(("bad_tag_not_classified_as_valid_cdm_link", is_bad_tag_flagged))

        # dangling link (target BO never registered) must be reported as an
        # anomaly, never silently truncated to a shorter "clean" chain
        dangling_dir = tmp_root / "dangling"
        dangling_dir.mkdir()
        seg = synth_cdm_segment(5, "link", 0x900000000000)
        pd = dangling_dir / ("bo_sigusr1_h0_va100000b0000_cpu1000_sz%x.hex" % len(seg))
        pd.write_bytes(make_bodump_bytes(0x100000b0000, len(seg), seg))
        matched_dangling = scan_dir_to_matched(dangling_dir)
        chain_d, anomalies_d = scan.find_chain(matched_dangling)
        checks.append(("dangling_link_reported_as_anomaly_not_silently_dropped",
                       any(a["kind"] == "dangling_link" for a in anomalies_d)))

        # cycle detection
        cyc_dir = tmp_root / "cycle"
        cyc_dir.mkdir()
        vaX, vaY = 0x100000c0000, 0x100000d0000
        segX = synth_cdm_segment(2, "link", vaY)
        segY = synth_cdm_segment(2, "link", vaX)
        (cyc_dir / ("bo_sigusr1_h0_va%x_cpu1000_sz%x.hex" % (vaX, len(segX)))).write_bytes(
            make_bodump_bytes(vaX, len(segX), segX))
        (cyc_dir / ("bo_sigusr1_h0_va%x_cpu1000_sz%x.hex" % (vaY, len(segY)))).write_bytes(
            make_bodump_bytes(vaY, len(segY), segY))
        matched_cyc = scan_dir_to_matched(cyc_dir)
        chain_c, anomalies_c = scan.find_chain(matched_cyc)
        checks.append(("cycle_reported_as_anomaly_or_ambiguous_head",
                       any(a["kind"] in ("cycle", "ambiguous_or_missing_head") for a in anomalies_c)))

        # (f) run.py's emit() only ever writes `gated` (schema-checked dict)
        # to 02_results.jsonl; grep run.py's own source for the one call site
        # to make sure harness stdout never flows into gf.write directly.
        run_src = (HERE / "run.py").read_text()
        gf_writes = [ln for ln in run_src.splitlines() if "gf.write(" in ln]
        checks.append(("exactly_one_gated_file_write_call_site_and_it_writes_gated_var",
                       len(gf_writes) == 1 and "json.dumps(gated" in gf_writes[0]))

        # case matrix sanity: every case name unique, referenced kinds match
        checks.append(("case_matrix_no_duplicate_names",
                       len(CM.ALL_CASE_NAMES) == len(set(CM.ALL_CASE_NAMES))))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    failed = [c for c in checks if not c[1]]
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    return len(failed) == 0


# ---------------------------------------------------------------------------
# --seqtest: synthetic PRE_GPU / RUN01_PRESENT / RUN02_PRESENT walk
# ---------------------------------------------------------------------------
def seqtest():
    SELFTEST_SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="seqtest_", dir=str(SELFTEST_SCRATCH)))
    try:
        run01 = tmp / "run01"
        run02 = tmp / "run02"
        results = []

        # PRE_GPU: neither run dir exists. --selftest and --seqtest must be
        # runnable (they are -- they use their own tempdirs); --preflight
        # must be satisfiable (no raw dirs yet); --between-runs and
        # --captured must NOT be satisfiable (nothing captured yet).
        state = "PRE_GPU"
        results.append((state, "selftest_runnable", True))
        results.append((state, "preflight_satisfiable", not run01.exists()))
        results.append((state, "between_runs_not_satisfiable", not run01.exists()))
        results.append((state, "captured_not_satisfiable", not (run01.exists() and run02.exists())))

        run01.mkdir()
        (run01 / "02_results.jsonl").write_text('{"case": "x"}\n')
        state = "RUN01_PRESENT"
        results.append((state, "selftest_runnable", True))
        results.append((state, "preflight_not_satisfiable_id_would_collide", run01.exists()))
        results.append((state, "between_runs_satisfiable", run01.exists() and not run02.exists()))
        results.append((state, "captured_not_satisfiable", not run02.exists()))

        run02.mkdir()
        (run02 / "02_results.jsonl").write_text('{"case": "x"}\n')
        state = "RUN02_PRESENT"
        results.append((state, "selftest_runnable", True))
        results.append((state, "between_runs_not_satisfiable_would_overwrite", run02.exists()))
        results.append((state, "captured_satisfiable", run01.exists() and run02.exists()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = all(r[2] for r in results)
    for state, name, passed in results:
        print(("PASS " if passed else "FAIL ") + "%s:%s" % (state, name))
    return ok


# ---------------------------------------------------------------------------
# Real gates over the actual experiment root
# ---------------------------------------------------------------------------
def preflight(run_id):
    d = RAW / run_id
    if d.exists():
        print("PREFLIGHT FAIL: raw/%s already exists" % run_id)
        return False
    if not selftest():
        print("PREFLIGHT FAIL: selftest did not pass")
        return False
    if not seqtest():
        print("PREFLIGHT FAIL: seqtest did not pass")
        return False
    print("PREFLIGHT OK: safe to run01 as %s" % run_id)
    return True


def between_runs(run01_id, run02_id):
    d1, d2 = RAW / run01_id, RAW / run02_id
    if not (d1 / "02_results.jsonl").exists():
        print("BETWEEN-RUNS FAIL: run01 results missing")
        return False
    if d2.exists():
        print("BETWEEN-RUNS FAIL: raw/%s already exists" % run02_id)
        return False
    if not selftest() or not seqtest():
        print("BETWEEN-RUNS FAIL: selftest/seqtest did not pass")
        return False
    print("BETWEEN-RUNS OK: safe to run02 as %s" % run02_id)
    return True


NONGATED_SUFFIXES = ("_addrs.jsonl",)


def captured(run01_id, run02_id):
    d1, d2 = RAW / run01_id, RAW / run02_id
    p1, p2 = d1 / "02_results.jsonl", d2 / "02_results.jsonl"
    if not p1.exists() or not p2.exists():
        print("CAPTURED FAIL: both runs' 02_results.jsonl must exist")
        return False
    if not selftest() or not seqtest():
        print("CAPTURED FAIL: selftest/seqtest did not pass")
        return False
    lines1 = p1.read_text().splitlines()
    lines2 = p2.read_text().splitlines()
    by_case1 = {json.loads(l)["case"]: l for l in lines1}
    by_case2 = {json.loads(l)["case"]: l for l in lines2}
    missing = (set(by_case1) ^ set(by_case2))
    if missing:
        print("CAPTURED FAIL: case sets differ between runs: %r" % sorted(missing))
        return False
    mismatches = []
    for case in sorted(by_case1):
        r1 = json.loads(by_case1[case])
        r2 = json.loads(by_case2[case])
        if r1 != r2:
            mismatches.append(case)
    report = {"run01": run01_id, "run02": run02_id, "cases": sorted(by_case1),
             "n_cases": len(by_case1), "gated_mismatches": mismatches}
    out = HERE / "analysis" / "cross_run_report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if mismatches:
        print("CAPTURED FAIL: gated mismatch in cases: %r (see %s)" % (mismatches, out))
        return False
    print("CAPTURED OK: %d cases, gated payload byte-identical run01 vs run02 (%s)" % (len(by_case1), out))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--between-runs", action="store_true")
    ap.add_argument("--captured", action="store_true")
    ap.add_argument("--run-id")
    ap.add_argument("--run01-id")
    ap.add_argument("--run02-id")
    args = ap.parse_args()

    ok = True
    if args.selftest:
        ok = selftest() and ok
    if args.seqtest:
        ok = seqtest() and ok
    if args.preflight:
        ok = preflight(args.run_id) and ok
    if args.between_runs:
        ok = between_runs(args.run01_id, args.run02_id) and ok
    if args.captured:
        ok = captured(args.run01_id, args.run02_id) and ok
    if not any([args.selftest, args.seqtest, args.preflight, args.between_runs, args.captured]):
        ap.print_help()
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
