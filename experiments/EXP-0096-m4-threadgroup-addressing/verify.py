#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0096.

Methodology and gate structure copied from
../EXP-0082-m4-mem-offset-semantics/verify.py, extended for two case
families (SPLICE + BUDGET) sharing one contract and one pair of runs.

Schema constants (CASE_KEYS, TIMING_KEYS, BUDGET_KEYS, BUDGET_TIMING_KEYS,
DISPATCH_KEYS, REC_KEYS, RUNS, TIMEOUTS, AUTH_*) are imported from run.py --
the single authoritative source -- and never restated here (gate (a) of the
standing gate set).

Two self-tests, both REQUIRED before any capture and both runnable in EVERY
tree state (they operate only on synthetic scratch copies under selftest/,
never on the real raw/):

  --selftest  fabricates complete synthetic captures FROM RECORDED REALITY
              (the real CM.CASES / CM.BUDGET_CASES / BL.FROZEN anchors this
              experiment actually froze -- gate (e): fixtures are not the
              implementation's own made-up constants) and drives them through
              the same static()/captured() code paths used on real evidence,
              including the cross-run comparison; proves clean shapes pass
              and each broken shape fails for the right reason. Includes the
              EXP-0081/0082 timing-isolation property (gate (d)):
              cross_run_timing_only_diff_passes / *_semantic_field_tampered.
  --seqtest   walks the contracted gate ORDER through synthetic states
              (PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT) and proves every
              gate is runnable and satisfiable in the exact state the
              contract invokes it, and FAILS in every other state (gate (b)).
"""
import argparse, datetime, hashlib, json, re, shutil, struct, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import run as R            # noqa: E402  (schema constants + splice builder)
import casematrix as CM    # noqa: E402
import baseline as BL      # noqa: E402

RUNS = R.RUNS
BOUNDARY = R.BOUNDARY
TIMEOUTS = R.TIMEOUTS
AUTH_CODE = R.AUTH_CODE
AUTH_DOC = R.AUTH_DOC
AUTH_ALL = AUTH_DOC + AUTH_CODE
REC_KEYS = R.REC_KEYS
DISPATCH_KEYS = R.DISPATCH_KEYS
CASE_KEYS = R.CASE_KEYS
TIMING_KEYS = R.TIMING_KEYS
BUDGET_KEYS = R.BUDGET_KEYS
BUDGET_TIMING_KEYS = R.BUDGET_TIMING_KEYS
TOTAL = CM.TOTAL
BUDGET_TOTAL = CM.BUDGET_TOTAL

ROOT_FILES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
              "RESULTS.md", "PROGRESS.md", "kernels", "harness", "baseline.py",
              "casematrix.py", "run.py", "analysis.py", "make_manifest.py",
              "verify.py", "manifest.json"}
KERNEL_FILES = {"tga.metal", "tg_ld.metal", "tg_st.metal"}
HARNESS_FILES = {"build.sh", "tgbudget.m"}
PRE_GPU_FILES = ("CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
                 "RESULTS.md", "PROGRESS.md", "kernels/tga.metal",
                 "kernels/tg_ld.metal", "kernels/tg_st.metal",
                 "harness/build.sh", "harness/tgbudget.m", "baseline.py",
                 "casematrix.py", "run.py", "analysis.py", "make_manifest.py",
                 "verify.py")
RAW_FILES = {"00_inputs.json", "01_cases.json", "01b_budget_cases.json", "02_build.json",
             "03_dispatch.json", "04_results.jsonl", "04_timing.jsonl",
             "06_budget_results.jsonl", "06_budget_timing.jsonl", "05_run_manifest.json"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_code_sha256", "authored_doc_sha256", "sw_vers", "xcrun_version",
               "python", "machine", "boundary", "timeouts_seconds"}
BUILD_KEYS = {"schema", "harness_build", "baseline"}
STATUS_ALLOWED = {"OK", "COMPILE_FAIL", "FUNCTION_MISSING", "ARCHIVE_FAIL",
                  "PIPELINE_MISS", "PIPELINE_FAIL", "CMDBUF_ERROR", "HANG",
                  "NO_STATUS", "EXTRACT_FAIL"}
BUDGET_STATUS_ALLOWED = {"OK", "COMPILE_FAIL", "PIPELINE_FAIL", "CMDBUF_ERROR",
                         "EXCEPTION", "NO_STATUS"}
GATE_BETWEEN = ("run01 must be a complete closed successful raw tree and work/ absent or "
                "empty before run02 is created")
GATE_PROV = ("run02 current Git revision and authored hashes must equal the closed run01 "
             "input record; final verification additionally requires byte-identical "
             "results files (SPLICE and BUDGET) and identical status counts")
GATE_SELFTEST = ("verify.py --selftest and verify.py --seqtest must pass immediately before "
                 "every capture, in every tree state; a capture whose verifier gates are "
                 "unproven is not authorized")
GATE_SMOKE = ("BEFORE any raw/ artifact is created, the freshly built harness must run ONE "
              "spliced scratch SPLICE case AND one scratch BUDGET case into work/ (never "
              "promoted into raw/) whose outputs parse completely; any build, baseline or "
              "smoke defect exits 3 with the receipt printed and NO burned run id")
GATE_ORDER = ("PRE_GPU: --selftest, --seqtest, make_manifest --check, --preflight, run01; "
              "RUN01_PRESENT: --selftest, --seqtest, make_manifest --check, --between-runs, "
              "run02; RUN02_PRESENT: analysis --write, make_manifest --write + --check, "
              "--captured")


def fail(s):
    raise SystemExit("FAIL " + s)


def req(v, s):
    if not v:
        fail(s)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def regular(p):
    return Path(p).is_file() and not Path(p).is_symlink()


def record(z, keys, argv, cwd, timeout, label):
    req(set(z) == keys, "record keys %s: expected exactly %s, got %s"
        % (label, sorted(keys), sorted(set(z))))
    req(z["argv"] == [str(x) for x in argv] and z["cwd"] == str(cwd)
        and z["timeout_seconds"] == timeout and z["timed_out"] is False
        and z["exit"] == 0 and z["exception"] is None
        and isinstance(z["stdout"], str) and isinstance(z["stderr"], str),
        "record content " + label)
    try:
        req(datetime.datetime.fromisoformat(z["started_utc"]).utcoffset() == datetime.timedelta(),
            "record timestamp " + label)
    except (TypeError, ValueError):
        fail("record timestamp " + label)


def record_interp(z, keys, argv, cwd, timeout, label):
    req(set(z) == keys, "record keys %s: expected exactly %s, got %s"
        % (label, sorted(keys), sorted(set(z))))
    req(z["argv"] == [str(x) for x in argv] and z["cwd"] == str(cwd)
        and z["timeout_seconds"] == timeout and z["timed_out"] is False
        and z["exit"] == 0 and z["exception"] is None,
        "record content " + label)


def manifest_expected(capture, root=None):
    import make_manifest as MM
    old = MM.HERE
    MM.HERE = Path(root) if root is not None else HERE
    try:
        exp = MM.expected(capture)
    finally:
        MM.HERE = old
    return exp


def timing_isolation_checks():
    """Structural guardrail (gate (d)): the byte-gated CASE_KEYS/BUDGET_KEYS
    may never regain a nondeterministic field, and the TIMING key sets must
    keep carrying every one of them."""
    nondeterministic = {"duration_ms", "gputime_ns", "stdout", "stdout_raw",
                        "stderr", "stderr_raw", "timing_ms"}
    req(not (nondeterministic & CASE_KEYS), "no timing field leaked into CASE_KEYS")
    req(not (nondeterministic & BUDGET_KEYS), "no timing field leaked into BUDGET_KEYS")
    req({"duration_ms", "gputime_ns", "stdout_raw", "stderr_raw"} <= TIMING_KEYS,
        "TIMING_KEYS carries every field moved out of CASE_KEYS")
    req({"duration_ms", "stdout_raw", "stderr_raw"} <= BUDGET_TIMING_KEYS,
        "BUDGET_TIMING_KEYS carries every field moved out of BUDGET_KEYS")
    rp = (HERE / "run.py").read_text()
    for fn in ("parse_agxtest", "parse_tgbudget"):
        m = re.search(r"(?m)^def %s\(.*?\n(?=def |\Z)" % fn, rp, re.S)
        req(m is not None, "%s present" % fn)
    m = re.search(r"(?m)^def parse_agxtest\(.*?\n(?=def |\Z)", rp, re.S)
    body = m.group(0)
    req('sem["gputime_ns"]' not in body and "sem['gputime_ns']" not in body,
        "GPUTIME_NS excluded from the semantic/gated dict inside parse_agxtest")


def contract_checks(c, root=None):
    root = HERE if root is None else Path(root)
    req(c["contract_version"] == 1 and c["experiment"] == "EXP-0096-m4-threadgroup-addressing"
        and c["state"] == "PRE_GPU", "contract identity")
    req(c["target"] == "M4/G16G local host through public Metal only", "contract target")
    b = c["boundary"]
    req(b["apple_binary_archive_bo_or_compiled_shader_byte_inspection"]
        == "only our own compiled shader bytes (splice targets) or freshly-compiled "
           "own-MSL (budget sweep, no splicing)"
        and b["private_api_or_trace"] == "NONE"
        and b["other_machine"] == "NONE (A18 hands-off; never macvdmtool)", "contract boundary")
    req(tuple(c["preflight_sequence"]) ==
        ("python3 -B verify.py --selftest", "python3 -B verify.py --seqtest",
         "python3 -B make_manifest.py --check", "python3 -B verify.py --preflight"),
        "contract preflight sequence")
    req(tuple(c["pre_second_run_sequence"]) ==
        ("python3 -B verify.py --selftest", "python3 -B verify.py --seqtest",
         "python3 -B make_manifest.py --check", "python3 -B verify.py --between-runs"),
        "contract pre-second-run sequence")
    req(tuple(c["post_second_run_sequence"]) ==
        ("python3 -B analysis.py --run-a m4-20260828-run01 --run-b m4-20260828-run02 --write",
         "python3 -B make_manifest.py --write", "python3 -B make_manifest.py --check",
         "python3 -B verify.py --captured"), "contract post-second-run sequence")
    req(c["gate_order"] == GATE_ORDER, "contract gate order text")
    m = c["matrix"]
    req(m["splice_total_cases"] == TOTAL and m["budget_total_cases"] == BUDGET_TOTAL,
        "contract matrix totals")
    counts = {}
    for cs in CM.CASES:
        counts[cs["item"]] = counts.get(cs["item"], 0) + 1
    req(m["splice_item_counts"] == dict(sorted(counts.items())), "contract splice item counts")
    bcounts = {}
    for cs in CM.BUDGET_CASES:
        bcounts[cs["item"]] = bcounts.get(cs["item"], 0) + 1
    req(m["budget_item_counts"] == dict(sorted(bcounts.items())), "contract budget item counts")
    hv = c["hand_validation"]
    req(len(hv) == len(CM.hand_validation()), "hand count")
    for h, (nm, kind, _val) in zip(hv, CM.hand_validation()):
        req(h["name"] == nm and h["kind"] == kind, "hand entry " + nm)
    fa = c["frozen_anchors"]
    for key in ("tga", "tg_ld", "tg_st"):
        f = BL.FROZEN[key]
        req(fa[key]["main_len"] == f["main_len"] and fa[key]["probe_hex"] == f["probe_hex"]
            and fa[key]["probe_main_offset"] == f["probe_main_offset"]
            and fa[key]["probe_fields"] == f["probe_fields"], "frozen anchor " + key)
    req(tuple(c["required_authored_paths"]) == AUTH_ALL, "authored path set")
    req(c["authored_sha256"].keys() == set(AUTH_ALL), "authored hash set")
    for p, h in c["authored_sha256"].items():
        req(h == sha(root / p), "authored hash " + p)
    req(c["timeouts_seconds"] == TIMEOUTS, "timeouts")
    cp = c["capture"]
    req(tuple(cp["runs"]) == RUNS and set(cp["required_run_paths"]) == RAW_FILES
        and set(cp["receipt_keys"]) == REC_KEYS and set(cp["dispatch_record_keys"]) == DISPATCH_KEYS
        and set(cp["case_line_keys"]) == CASE_KEYS
        and set(cp["timing_line_keys"]) == TIMING_KEYS
        and set(cp["budget_line_keys"]) == BUDGET_KEYS
        and set(cp["budget_timing_line_keys"]) == BUDGET_TIMING_KEYS
        and set(cp["inputs_keys"]) == INPUTS_KEYS
        and set(cp["build_keys"]) == BUILD_KEYS
        and cp["status_allowed"] == sorted(STATUS_ALLOWED)
        and cp["budget_status_allowed"] == sorted(BUDGET_STATUS_ALLOWED)
        and cp["between_runs_gate"] == GATE_BETWEEN
        and cp["cross_run_provenance_gate"] == GATE_PROV
        and cp["selftest_gate"] == GATE_SELFTEST and cp["smoke_gate"] == GATE_SMOKE
        and cp["failure_record"] == "STOP.json is append-only and ends that run; never "
        "retry automatically; a fault or timeout inside either sweep is a RESULT and the "
        "sweep continues in a fresh process", "capture contract")
    req(c["gate"].startswith("A missing path, hash, schema field, record key, splice "
                             "consistency, or unexpected raw path"), "gate text")
    req(c["capture"]["cross_run_byte_exact_scope"] == "04_results.jsonl and "
        "06_budget_results.jsonl only (the two *_timing.jsonl files are schema-checked every "
        "run, never byte-compared across runs)", "contract timing-isolation scope")


def strip_comments(t):
    return "\n".join(ln.split("//")[0] for ln in t.splitlines())


def source_checks(root=None):
    root = HERE if root is None else Path(root)
    ktga = (root / "kernels" / "tga.metal").read_text()
    kld = (root / "kernels" / "tg_ld.metal").read_text()
    kst = (root / "kernels" / "tg_st.metal").read_text()
    req("tile[(li + 1u) & 255u] + tile[(li + 2u) & 255u]" in ktga, "tga kernel probe form")
    req("uint j  = i0 + i1;" in kld and "out[0]  = tile[j];" in kld, "tg_ld kernel index form")
    req("uint j  = i0 + i1;" in kst and "tile[j] = 0x5A17C0DEu;" in kst, "tg_st kernel store form")
    req("0x3CA50000" in (root / "casematrix.py").read_text(), "pattern tag anchor")
    tb = (root / "harness" / "tgbudget.m").read_text()
    req("atomic_fetch_add_explicit" in tb and "2654435761" in tb,
        "tgbudget uses a bit-mixing (non-periodic) verification hash")
    rp = (root / "run.py").read_text()
    req("--execute" in rp and "no capture is authorized" in rp, "runner execute gate")
    req('"--selftest"' in rp and '"--seqtest"' in rp and "verify.py %s failed" in rp,
        "runner selftest+seqtest gate before every capture")
    req('"--preflight" if a.run_id == RUNS[0] else "--between-runs"' in rp,
        "runner state gate selection")
    req("smoke_gate_splice" in rp and "smoke_gate_budget" in rp and "SMOKE_SPLICE_CASE" in rp
        and "SMOKE_BUDGET_CASE" in rp, "runner smoke gates (both families)")
    req(rp.index("NON-RECORDED smoke gate") < rp.index("raw.mkdir(parents=True)"),
        "runner smoke gates run BEFORE any raw artifact")
    req("import threading" not in rp and "Thread(" not in rp and "multiprocessing" not in rp,
        "runner single-threaded discipline")
    req("rf.flush()" in rp and "tf.flush()" in rp, "runner per-case flush discipline")
    req("REPO / \"tools\" / \"agxtest\" / \"agxtest.py\"" in rp, "runner uses read-only agxtest")
    req("06_budget_results.jsonl" in rp, "runner writes the budget results file")
    vp = (root / "verify.py").read_text()
    req(len(re.findall(r"(?m)^def record\(", vp)) == 1, "single record checker")
    req("timing_isolation_checks" in vp, "verifier calls the timing-isolation guardrail")
    bp = (root / "baseline.py").read_text()
    req("frozen_anchor_diffs" in bp and "raise SystemExit" in bp, "baseline stop discipline")
    hs = (root / "harness" / "build.sh").read_text()
    req("tools/shdump/shdump.m" in hs and "tools/agxtest/agxrun.m" in hs
        and "tgbudget.m" in hs, "harness builds tool sources + tgbudget")
    ap = (root / "analysis.py").read_text()
    req("datetime.datetime.now" not in ap and "time.time" not in ap,
        "analysis deterministic (no clock)")


def prereg_checks(root=None):
    root = HERE if root is None else Path(root)
    t = (root / "PRE_REGISTRATION.md").read_text()
    req("GLCS-A01" in t and "GLCS-A02" in t, "prereg cites GLCS-A01/A02")
    req("tg_addr_compute" in t, "prereg names the probed instruction")
    req("65536" in t, "prereg names the calibrated combined-budget boundary")
    req("EXP-0099" in t, "prereg cross-references EXP-0099 (retention-flag question)")
    req("retention" in t.lower(), "prereg carries the retention-flag caution")


def static(capture=False, require_analysis=False, root=None):
    root = HERE if root is None else Path(root)
    timing_isolation_checks()
    names = {p.name for p in root.iterdir()}
    allowed = ROOT_FILES | ({"raw"} if capture else set()) \
        | ({"analysis.json"} if require_analysis else set()) \
        | ({"work"} if "work" in names else set())
    req(not root.is_symlink() and names == allowed, "closed root: %s" % sorted(names ^ allowed))
    if require_analysis:
        req(regular(root / "analysis.json"), "derived analysis")
    if "work" in names:
        w = root / "work"
        req(w.is_dir() and not w.is_symlink() and not any(w.iterdir()), "work absent or empty")
    for p in AUTH_ALL + ("manifest.json", "RESULTS.md", "CAPTURE_CONTRACT.json", "PROGRESS.md"):
        req(regular(root / p), "regular " + p)
    for d, fs in (("kernels", KERNEL_FILES), ("harness", HARNESS_FILES)):
        q = root / d
        req(q.is_dir() and not q.is_symlink() and {p.name for p in q.iterdir()} == fs
            and all(regular(x) for x in q.iterdir()), "closed " + d)
    contract_checks(json.loads((root / "CAPTURE_CONTRACT.json").read_text()), root)
    source_checks(root)
    prereg_checks(root)
    m = json.loads((root / "manifest.json").read_text())
    req(m == manifest_expected(capture, root), "manifest")


# ---------------------------------------------------------------------------
# Synthetic-tree fabrication (selftest + seqtest). No Metal, no device. Built
# FROM RECORDED REALITY: the real CM.CASES / CM.BUDGET_CASES / BL.FROZEN
# anchors this experiment actually froze (gate (e)), never invented numbers.
# ---------------------------------------------------------------------------
SELFTEST_DIR = "selftest"
_SYNTH_TS = "2026-08-28T00:00:00+00:00"


def _put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def _synth_record(keys, argv, cwd, timeout, **extra):
    z = {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
         "started_utc": _SYNTH_TS, "timed_out": False, "exit": 0, "stdout": "", "stderr": "",
         "exception": None}
    z.update(extra)
    req(set(z) == keys, "internal: synth record shape")
    return z


def synth_case_line(i, cs, new_hex, sp_args, changed):
    """Fabricate one internally consistent 04_results.jsonl line, built from
    the REAL frozen probe bytes/predictions (gate (e))."""
    if cs["kernel"] == "tga":
        base = cs["item"] == "CTRL" or cs["fields"] == {}
        arr = CM.tga_baseline() if base else CM.tga_corrupt_ip2()
        raw = b"".join(struct.pack("<f", float(v)) for v in arr)
        out0 = None   # too large to store inline (>64 hex chars), matches run.py policy
        decoded = CM.tga_summary(arr)
        result_hex = raw.hex()
    elif cs["kernel"] == "tg_ld":
        pred = cs["pred"].get("H-ELEM+H-U")
        if isinstance(pred, int) and 0 <= pred <= (CM.A_WORDS - 1) * 4:
            out0 = struct.pack("<I", CM.encode_expected_word_at_byte_offset(pred)).hex()
            decoded = {"byte_offset": pred, "word": pred // 4, "residue": 0, "ambiguous": False}
        else:
            out0 = "00000000"
            decoded = None
        result_hex = out0
    else:  # tg_st
        pred = cs["pred"].get("H-ELEM+H-U")
        out0 = struct.pack("<I", (cs["idx"][2] + (cs["idx"][3] << 8) + cs["idx"][0])
                           & 0xFFFFFFFF).hex()
        if isinstance(pred, int) and 0 <= pred < CM.TGT_WORDS * 4:
            decoded = {"byte_offset": pred, "words_changed": [pred // 4],
                       "nonzero_bytes": {pred + k: ((CM.STORE_CONST >> (8 * k)) & 0xFF)
                                         for k in range(4)}}
        else:
            decoded = {"byte_offset": None, "words_changed": [], "nonzero_bytes": {}}
        result_hex = out0
    result_sha256 = hashlib.sha256(("RESULT 0 %d" % int(result_hex, 16)).encode()).hexdigest()
    return {"i": i, "name": cs["name"], "item": cs["item"], "kernel": cs["kernel"],
            "idx": ["0x%08X" % (v & 0xFFFFFFFF) for v in cs["idx"]],
            "splice_args": sp_args, "probe_before": BL.FROZEN[cs["kernel"]]["probe_hex"],
            "probe_after": new_hex, "changed_bytes": changed, "exit": 0,
            "timed_out": False, "exception": None, "status": "OK",
            "pipeline_source": "archive", "main_len": BL.FROZEN[cs["kernel"]]["main_len"],
            "device": "Apple M4 (synthetic)", "function": "k",
            "out0_hex": out0 if (out0 and len(out0) <= 64) else None,
            "extra_hex": None, "result_sha256": result_sha256,
            "decoded": decoded, "raw_note": ""}


def synth_timing_line(i, cs, rid):
    h = int(hashlib.sha256(("%s:%s" % (rid, cs["name"])).encode()).hexdigest()[:8], 16)
    return {"i": i, "name": cs["name"], "duration_ms": 5 + (h % 200),
            "gputime_ns": 1000 + (h % 9000),
            "stdout_raw": "synthetic stdout rid=%s case=%s" % (rid, cs["name"]), "stderr_raw": ""}


def synth_budget_line(i, cs):
    pipeline_ok = cs["expect_pipeline_ok"]
    clean = cs["expect_clean"]
    return {"i": i, "name": cs["name"], "item": cs["item"], "mode": cs["mode"],
            "static_bytes": cs["static_bytes"], "dynamic_bytes": cs["dynamic_bytes"],
            "exit": 0, "timed_out": False, "exception": None,
            "compile_status": "OK",
            "pipeline_status": "OK" if pipeline_ok else "FAIL",
            "pso_static_tgmem": (cs["static_bytes"] if pipeline_ok else None),
            "dispatch_status": "OK" if pipeline_ok else None,
            "bad_byte_count": (0 if clean else (1 if (pipeline_ok and clean is False) else
                               (0 if pipeline_ok else None))),
            "status": "OK" if pipeline_ok else "PIPELINE_FAIL"}


def synth_budget_timing_line(i, cs, rid):
    h = int(hashlib.sha256(("%s:%s:budget" % (rid, cs["name"])).encode()).hexdigest()[:8], 16)
    return {"i": i, "name": cs["name"], "duration_ms": 5 + (h % 300),
            "stdout_raw": "synthetic budget stdout rid=%s case=%s" % (rid, cs["name"]),
            "stderr_raw": ""}


def case_line_checks(line, i, cs):
    req(set(line) == CASE_KEYS, "case line keys %d (%s)" % (i, cs["name"]))
    req(line["i"] == i and line["name"] == cs["name"] and line["item"] == cs["item"]
        and line["kernel"] == cs["kernel"], "case echo %d" % i)
    new_hex, sp_args, changed = R.splice_case(cs["kernel"], BL.FROZEN[cs["kernel"]]["probe_hex"],
                                              cs["fields"], BL.FROZEN[cs["kernel"]]["probe_main_offset"])
    req(line["probe_before"] == BL.FROZEN[cs["kernel"]]["probe_hex"]
        and line["probe_after"] == new_hex and line["splice_args"] == sp_args
        and line["changed_bytes"] == changed, "case splice consistency %d (%s)" % (i, cs["name"]))
    req(line["status"] in STATUS_ALLOWED, "case status %d" % i)
    req(re.fullmatch(r"[0-9a-f]{64}", line["result_sha256"] or ""), "case result hash form %d" % i)


def timing_line_checks(t, i, cs):
    req(set(t) == TIMING_KEYS, "timing line keys %d (%s)" % (i, cs["name"]))
    req(t["i"] == i and t["name"] == cs["name"], "timing echo %d" % i)
    req(isinstance(t["duration_ms"], int) and t["duration_ms"] >= 0, "timing duration %d" % i)


def budget_line_checks(line, i, cs):
    req(set(line) == BUDGET_KEYS, "budget line keys %d (%s)" % (i, cs["name"]))
    req(line["i"] == i and line["name"] == cs["name"] and line["item"] == cs["item"]
        and line["mode"] == cs["mode"] and line["static_bytes"] == cs["static_bytes"]
        and line["dynamic_bytes"] == cs["dynamic_bytes"], "budget echo %d" % i)
    req(line["status"] in BUDGET_STATUS_ALLOWED, "budget status %d" % i)


def budget_timing_line_checks(t, i, cs):
    req(set(t) == BUDGET_TIMING_KEYS, "budget timing line keys %d (%s)" % (i, cs["name"]))
    req(t["i"] == i and t["name"] == cs["name"], "budget timing echo %d" % i)


def one_run(rid, prov_out, root=None):
    root = HERE if root is None else Path(root)
    d = root / "raw" / rid
    req(d.is_dir() and not d.is_symlink(), "run dir " + rid)
    names = {p.name for p in d.iterdir()}
    req(names == RAW_FILES, "closed raw %s: %s" % (rid, sorted(names)))
    req(all(regular(p) for p in d.iterdir()), "regular raw " + rid)

    i = json.loads((d / "00_inputs.json").read_text())
    req(set(i) == INPUTS_KEYS and i["schema"] == 1 and i["machine"] == "arm64"
        and i["boundary"] == BOUNDARY and i["timeouts_seconds"] == TIMEOUTS,
        "inputs schema " + rid)
    c = json.loads((root / "CAPTURE_CONTRACT.json").read_text())
    frozen = {**i["authored_doc_sha256"], **i["authored_code_sha256"]}
    req(frozen == c["authored_sha256"], "inputs frozen-hash binding " + rid)
    for p, h in frozen.items():
        req(h == sha(root / p), "authored drift since capture " + rid + " " + p)
    req(subprocess.run(["git", "cat-file", "-e", i["git_revision"] + "^{commit}"],
                       cwd=REPO).returncode == 0, "revision object " + rid)
    record(i["sw_vers"], REC_KEYS, ["sw_vers"], root, TIMEOUTS["env_command"], "sw_vers " + rid)
    record(i["xcrun_version"], REC_KEYS, ["xcrun", "--version"], root,
           TIMEOUTS["env_command"], "xcrun " + rid)

    b = json.loads((d / "02_build.json").read_text())
    req(set(b) == BUILD_KEYS, "build keys " + rid)

    cases = json.loads((d / "01_cases.json").read_text())
    req(cases["schema"] == 1 and cases["run_id"] == rid and cases["total"] == TOTAL,
        "cases header " + rid)
    bcases = json.loads((d / "01b_budget_cases.json").read_text())
    req(bcases["schema"] == 1 and bcases["run_id"] == rid and bcases["total"] == BUDGET_TOTAL,
        "budget cases header " + rid)

    disp = json.loads((d / "03_dispatch.json").read_text())
    req(set(disp) == DISPATCH_KEYS, "dispatch keys %s" % rid)
    req(disp["n_splice_cases"] == TOTAL and disp["n_budget_cases"] == BUDGET_TOTAL
        and sum(disp["splice_status_counts"].values()) == TOTAL
        and sum(disp["budget_status_counts"].values()) == BUDGET_TOTAL, "dispatch content " + rid)
    for ts in ("started_utc", "finished_utc"):
        try:
            req(datetime.datetime.fromisoformat(disp[ts]).utcoffset() == datetime.timedelta(),
                "dispatch timestamp " + rid)
        except (TypeError, ValueError):
            fail("dispatch timestamp " + rid)

    res = (d / "04_results.jsonl").read_text().splitlines()
    req(len(res) == TOTAL == disp["results_lines"], "result line count " + rid)
    status_seen = {}
    for j, ln in enumerate(res):
        line = json.loads(ln)
        case_line_checks(line, j, CM.CASES[j])
        status_seen[line["status"]] = status_seen.get(line["status"], 0) + 1
    req(disp["splice_status_counts"] == status_seen, "dispatch splice status counts " + rid)
    req(sha(d / "04_results.jsonl") == disp["results_sha256"], "results hash " + rid)

    tim = (d / "04_timing.jsonl").read_text().splitlines()
    req(len(tim) == TOTAL == disp["timing_lines"], "timing line count " + rid)
    for j, ln in enumerate(tim):
        timing_line_checks(json.loads(ln), j, CM.CASES[j])
    req(sha(d / "04_timing.jsonl") == disp["timing_sha256"], "timing hash " + rid)

    bres = (d / "06_budget_results.jsonl").read_text().splitlines()
    req(len(bres) == BUDGET_TOTAL == disp["budget_results_lines"], "budget result line count " + rid)
    bstatus_seen = {}
    for j, ln in enumerate(bres):
        line = json.loads(ln)
        budget_line_checks(line, j, CM.BUDGET_CASES[j])
        bstatus_seen[line["status"]] = bstatus_seen.get(line["status"], 0) + 1
    req(disp["budget_status_counts"] == bstatus_seen, "dispatch budget status counts " + rid)
    req(sha(d / "06_budget_results.jsonl") == disp["budget_results_sha256"],
        "budget results hash " + rid)

    btim = (d / "06_budget_timing.jsonl").read_text().splitlines()
    req(len(btim) == BUDGET_TOTAL == disp["budget_timing_lines"], "budget timing line count " + rid)
    for j, ln in enumerate(btim):
        budget_timing_line_checks(json.loads(ln), j, CM.BUDGET_CASES[j])
    req(sha(d / "06_budget_timing.jsonl") == disp["budget_timing_sha256"], "budget timing hash " + rid)

    rm = json.loads((d / "05_run_manifest.json").read_text())
    req(rm["run_id"] == rid and rm["total_splice_cases"] == TOTAL
        and rm["total_budget_cases"] == BUDGET_TOTAL, "run manifest header " + rid)

    prov_out.append({"rid": rid, "git_revision": i["git_revision"], "git_dirty": i["git_dirty"],
                     "frozen": frozen, "status_counts": disp["splice_status_counts"],
                     "budget_status_counts": disp["budget_status_counts"],
                     "results": (d / "04_results.jsonl").read_bytes(),
                     "budget_results": (d / "06_budget_results.jsonl").read_bytes()})


def captured(runs, root=None):
    root = HERE if root is None else Path(root)
    raw = root / "raw"
    req(raw.is_dir() and not raw.is_symlink() and {p.name for p in raw.iterdir()} == set(runs),
        "exact raw runs")
    prov = []
    for rid in runs:
        one_run(rid, prov, root)
    if len(prov) == 2:
        x, y = prov
        req(x["git_revision"] == y["git_revision"] and x["frozen"] == y["frozen"],
            "cross-run revision/authored provenance")
        req(x["results"] == y["results"], "byte-exact repeat (splice)")
        req(x["budget_results"] == y["budget_results"], "byte-exact repeat (budget)")
        req(x["status_counts"] == y["status_counts"], "cross-run status identity")
        req(x["budget_status_counts"] == y["budget_status_counts"], "cross-run budget status identity")


def gate_preflight(root=None):
    root = HERE if root is None else Path(root)
    static(capture=False, root=root)
    req(not (root / "raw").exists(), "PRE_GPU tree must have no raw")


def gate_between(root=None):
    root = HERE if root is None else Path(root)
    static(capture=True, root=root)
    captured((RUNS[0],), root)


def gate_captured(root=None):
    root = HERE if root is None else Path(root)
    static(capture=True, require_analysis=True, root=root)
    captured(RUNS, root)


# ---------------------------------------------------------------------------
# Synthetic-tree builder
# ---------------------------------------------------------------------------
def _copy_authored(dst):
    dst.mkdir(parents=True, exist_ok=True)
    for p in AUTH_ALL:
        src = HERE / p
        out = dst / p
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(src.read_bytes())
    for extra in ("manifest.json", "RESULTS.md", "CAPTURE_CONTRACT.json", "PROGRESS.md"):
        src = HERE / extra
        if src.exists():
            (dst / extra).write_bytes(src.read_bytes())


def _gitrev():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
                          capture_output=True, check=True).stdout.strip()


def _build_tree(root, runs=RUNS, with_analysis=True, pre_gpu=False, mutate=None):
    shutil.rmtree(root, ignore_errors=True)
    _copy_authored(root)
    if pre_gpu:
        if mutate:
            mutate(root)
        return
    current = {"git_revision": _gitrev(), "git_dirty": False,
               "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
               "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC}}
    probe_hex_map = {k: BL.FROZEN[k]["probe_hex"] for k in ("tga", "tg_ld", "tg_st")}
    probe_off_map = {k: BL.FROZEN[k]["probe_main_offset"] for k in ("tga", "tg_ld", "tg_st")}
    for rid in runs:
        d = root / "raw" / rid
        d.mkdir(parents=True)
        env = {"schema": 1, **current,
               "experiment_tree_dirty_entries": 0,
               "sw_vers": _synth_record(REC_KEYS, ["sw_vers"], root, TIMEOUTS["env_command"]),
               "xcrun_version": _synth_record(REC_KEYS, ["xcrun", "--version"], root,
                                              TIMEOUTS["env_command"]),
               "python": "3.11.0", "machine": "arm64", "boundary": BOUNDARY,
               "timeouts_seconds": TIMEOUTS}
        _put(d / "00_inputs.json", env)
        cases = [dict(c, i=i) for i, c in enumerate(CM.CASES)]
        bcases = [dict(c, i=i) for i, c in enumerate(CM.BUDGET_CASES)]
        _put(d / "01_cases.json", {
            "schema": 1, "run_id": rid, "total": len(cases),
            "cases": [{"i": c["i"], "name": c["name"], "item": c["item"], "kernel": c["kernel"],
                       "idx": ["0x%08X" % (v & 0xFFFFFFFF) for v in c["idx"]],
                       "fields": {k: c["fields"][k] for k in sorted(c["fields"])},
                       "note": c["note"]} for c in cases]})
        _put(d / "01b_budget_cases.json", {
            "schema": 1, "run_id": rid, "total": len(bcases),
            "cases": [{"i": c["i"], "name": c["name"], "item": c["item"], "mode": c["mode"],
                       "static_bytes": c["static_bytes"], "dynamic_bytes": c["dynamic_bytes"],
                       "expect_pipeline_ok": c["expect_pipeline_ok"],
                       "expect_clean": c["expect_clean"], "note": c["note"]} for c in bcases]})
        _put(d / "02_build.json", {"schema": 1,
             "harness_build": _synth_record(REC_KEYS, [HERE / "harness" / "build.sh", "BINDIR"],
                                            root, TIMEOUTS["host_build"]),
             "baseline": _synth_record(REC_KEYS, ["baseline.py", "--bin-dir", "BINDIR",
                                                  "--out", "OUT"], root, TIMEOUTS["baseline"])})
        status_counts, bstatus_counts = {}, {}
        with (d / "04_results.jsonl").open("w") as rf, (d / "04_timing.jsonl").open("w") as tf:
            for c in cases:
                new_hex, sp_args, changed = R.splice_case(c["kernel"], probe_hex_map[c["kernel"]],
                                                          c["fields"], probe_off_map[c["kernel"]])
                line = synth_case_line(c["i"], c, new_hex, sp_args, changed)
                rf.write(json.dumps(line, sort_keys=True) + "\n")
                tf.write(json.dumps(synth_timing_line(c["i"], c, rid), sort_keys=True) + "\n")
                status_counts[line["status"]] = status_counts.get(line["status"], 0) + 1
        with (d / "06_budget_results.jsonl").open("w") as rf, \
                (d / "06_budget_timing.jsonl").open("w") as tf:
            for c in bcases:
                line = synth_budget_line(c["i"], c)
                rf.write(json.dumps(line, sort_keys=True) + "\n")
                tf.write(json.dumps(synth_budget_timing_line(c["i"], c, rid), sort_keys=True) + "\n")
                bstatus_counts[line["status"]] = bstatus_counts.get(line["status"], 0) + 1
        item_counts, bitem_counts = {}, {}
        for c in cases:
            item_counts[c["item"]] = item_counts.get(c["item"], 0) + 1
        for c in bcases:
            bitem_counts[c["item"]] = bitem_counts.get(c["item"], 0) + 1
        dispatch = {"argv": ["python3", "run.py", "--execute", "--run-id", rid],
                    "cwd": str(root), "started_utc": _SYNTH_TS, "finished_utc": _SYNTH_TS,
                    "duration_seconds": 1.0, "n_splice_cases": len(cases),
                    "n_budget_cases": len(bcases), "splice_status_counts": status_counts,
                    "budget_status_counts": bstatus_counts,
                    "results_sha256": sha(d / "04_results.jsonl"),
                    "results_lines": len(cases),
                    "timing_sha256": sha(d / "04_timing.jsonl"), "timing_lines": len(cases),
                    "budget_results_sha256": sha(d / "06_budget_results.jsonl"),
                    "budget_results_lines": len(bcases),
                    "budget_timing_sha256": sha(d / "06_budget_timing.jsonl"),
                    "budget_timing_lines": len(bcases)}
        _put(d / "03_dispatch.json", dispatch)
        _put(d / "05_run_manifest.json", {
            "schema": 1, "run_id": rid, "total_splice_cases": len(cases),
            "total_budget_cases": len(bcases), "item_counts": dict(sorted(item_counts.items())),
            "budget_item_counts": dict(sorted(bitem_counts.items())),
            "runner_sha256": sha(HERE / "run.py"), "harness_sha256": sha(HERE / "harness" / "build.sh"),
            "tgbudget_sha256": sha(HERE / "harness" / "tgbudget.m"),
            "kernel_tga_sha256": sha(HERE / "kernels" / "tga.metal"),
            "kernel_tg_ld_sha256": sha(HERE / "kernels" / "tg_ld.metal"),
            "kernel_tg_st_sha256": sha(HERE / "kernels" / "tg_st.metal"),
            "baseline_sha256": "0" * 64, "cases_sha256": sha(d / "01_cases.json"),
            "budget_cases_sha256": sha(d / "01b_budget_cases.json"),
            "results_sha256": dispatch["results_sha256"],
            "budget_results_sha256": dispatch["budget_results_sha256"],
            "probe_hex": probe_hex_map, "probe_main_offset": probe_off_map})
    if with_analysis:
        _put(root / "analysis.json", {"schema": 1, "synthetic": True})
    subprocess.run([sys.executable, "-B", "make_manifest.py", "--write"], cwd=root, check=True)
    if mutate:
        mutate(root)


def _load(root, rel):
    return json.loads((Path(root) / rel).read_text())


def _rel(kind, rid):
    return "raw/%s/%s" % (rid, {"results": "04_results.jsonl", "timing": "04_timing.jsonl",
                                "budget_results": "06_budget_results.jsonl",
                                "budget_timing": "06_budget_timing.jsonl",
                                "dispatch": "03_dispatch.json"}[kind])


# ---------------------------------------------------------------------------
# Mutators: each breaks ONE thing in an otherwise-clean synthetic tree.
# ---------------------------------------------------------------------------
def m_extra_root_file(root):
    (Path(root) / "stray.txt").write_text("x")


def m_missing_authored(root):
    (Path(root) / "README.md").unlink()


def m_overkeyed_case_line(root):
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    d = json.loads(lines[0]); d["extra_field"] = 1
    lines[0] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")


def m_underkeyed_budget_line(root):
    p = Path(root) / _rel("budget_results", RUNS[0])
    lines = p.read_text().splitlines()
    d = json.loads(lines[0]); del d["bad_byte_count"]
    lines[0] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")


def m_results_hash_mismatch(root):
    disp = Path(root) / _rel("dispatch", RUNS[0])
    d = json.loads(disp.read_text())
    d["results_sha256"] = "0" * 64
    disp.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")


def m_splice_instruction_relative(root):
    """The EXP-0080 defect class: splice_args computed relative to the probe
    instruction instead of _agc.main. Corrupts run01's first splice case."""
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    d = json.loads(lines[1])   # a spliced (non-CTRL) case
    d["splice_args"] = ["_agc.main@0=ff"]   # deliberately wrong absolute offset
    lines[1] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")


def m_run02_result_differs(root):
    p = Path(root) / _rel("results", RUNS[1])
    lines = p.read_text().splitlines()
    d = json.loads(lines[0]); d["out0_hex"] = "ffffffff" if d["out0_hex"] else None
    d["result_sha256"] = "f" * 64
    lines[0] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    disp = Path(root) / _rel("dispatch", RUNS[1])
    dd = json.loads(disp.read_text())
    dd["results_sha256"] = sha(p)
    disp.write_text(json.dumps(dd, indent=2, sort_keys=True) + "\n")


def m_run02_timing_diverges_hard(root):
    """The property EXP-0081/0082 exists to prove: timing-only divergence
    must NOT fail the cross-run gate. Regenerates manifest.json afterward --
    unlike the FAIL-expecting mutators, this one represents a legitimately
    VALID capture (real timing genuinely differs run-to-run), so its
    manifest must reflect the post-mutation tree, exactly as a real
    `make_manifest.py --write` run after two real captures would."""
    p = Path(root) / _rel("timing", RUNS[1])
    lines = p.read_text().splitlines()
    d = json.loads(lines[0])
    d["duration_ms"] = 999999
    d["gputime_ns"] = 1
    d["stdout_raw"] = "TAMPERED FOR SELFTEST"
    lines[0] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    disp = Path(root) / _rel("dispatch", RUNS[1])
    dd = json.loads(disp.read_text())
    dd["timing_sha256"] = sha(p)
    disp.write_text(json.dumps(dd, indent=2, sort_keys=True) + "\n")
    subprocess.run([sys.executable, "-B", "make_manifest.py", "--write"], cwd=root, check=True)


def m_budget_run02_differs(root):
    p = Path(root) / _rel("budget_results", RUNS[1])
    lines = p.read_text().splitlines()
    d = json.loads(lines[0]); d["bad_byte_count"] = 999999
    lines[0] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    disp = Path(root) / _rel("dispatch", RUNS[1])
    dd = json.loads(disp.read_text())
    dd["budget_results_sha256"] = sha(p)
    disp.write_text(json.dumps(dd, indent=2, sort_keys=True) + "\n")


def m_run02_revision_differs(root):
    p = Path(root) / "raw" / RUNS[1] / "00_inputs.json"
    d = json.loads(p.read_text())
    d["git_revision"] = "0" * 40
    p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")


def m_raw_extra_file(root):
    (Path(root) / "raw" / RUNS[0] / "STRAY.json").write_text("{}")


def m_manifest_stale(root):
    (Path(root) / "manifest.json").write_text('{"schema": 1, "state": "STALE", "artifacts": []}\n')


MUTATORS = [
    ("extra_root_file", m_extra_root_file, False, False),
    ("missing_authored", m_missing_authored, False, False),
    ("overkeyed_case_line", m_overkeyed_case_line, True, False),
    ("underkeyed_budget_line", m_underkeyed_budget_line, True, False),
    ("results_hash_mismatch", m_results_hash_mismatch, True, False),
    ("splice_instruction_relative", m_splice_instruction_relative, True, False),
    ("run02_result_differs", m_run02_result_differs, True, True),
    ("budget_run02_differs", m_budget_run02_differs, True, True),
    ("run02_revision_differs", m_run02_revision_differs, True, True),
    ("raw_extra_file", m_raw_extra_file, True, False),
    ("manifest_stale", m_manifest_stale, True, False),
]


def selftest():
    root = HERE / SELFTEST_DIR
    n = 0

    # 1. clean PRE_GPU tree passes gate_preflight
    r = root / "clean_pregpu"
    _build_tree(r, pre_gpu=True)
    gate_preflight(r); n += 1

    # 2. clean single-run tree passes gate_between
    r = root / "clean_run01"
    _build_tree(r, runs=(RUNS[0],), with_analysis=False)
    gate_between(r); n += 1

    # 3. clean two-run tree passes gate_captured
    r = root / "clean_captured"
    _build_tree(r, runs=RUNS, with_analysis=True)
    gate_captured(r); n += 1

    # 4. cross_run_timing_only_diff_passes (gate (d), the core property)
    r = root / "timing_only_diff"
    _build_tree(r, runs=RUNS, with_analysis=True, mutate=m_run02_timing_diverges_hard)
    gate_captured(r); n += 1
    print("PASS cross_run_timing_only_diff_passes")

    # 5. every mutator fails, and for a run-state matching its "needs_two_runs" flag
    for name, fn, needs_run, needs_two in MUTATORS:
        r = root / ("mut_" + name)
        if needs_two:
            _build_tree(r, runs=RUNS, with_analysis=True, mutate=fn)
            gate = gate_captured
        elif needs_run:
            _build_tree(r, runs=(RUNS[0],), with_analysis=False, mutate=fn)
            gate = gate_between
        else:
            _build_tree(r, pre_gpu=True, mutate=fn)
            gate = gate_preflight
        try:
            gate(r)
        except SystemExit:
            n += 1
            print("PASS mutator %s correctly rejected" % name)
            continue
        fail("mutator %s was NOT rejected (gate incorrectly passed)" % name)

    timing_isolation_checks(); n += 1
    print("PASS timing_isolation_checks")

    shutil.rmtree(root, ignore_errors=True)
    print("SELFTEST PASS (%d checks)" % n)
    return 0


# ---------------------------------------------------------------------------
# seqtest: state-machine walk (gate (b))
# ---------------------------------------------------------------------------
def seqtest():
    root = HERE / SELFTEST_DIR / "seq"
    n = 0
    shutil.rmtree(HERE / SELFTEST_DIR, ignore_errors=True)

    def expect_pass(fn, label):
        nonlocal n
        fn(); n += 1
        print("PASS %s" % label)

    def expect_fail(fn, label):
        nonlocal n
        try:
            fn()
        except SystemExit:
            n += 1
            print("PASS %s (correctly rejected)" % label)
            return
        fail("%s should have failed but passed" % label)

    # PRE_GPU state
    _build_tree(root, pre_gpu=True)
    expect_pass(lambda: gate_preflight(root), "preflight in PRE_GPU")
    expect_fail(lambda: gate_between(root), "between-runs in PRE_GPU")
    expect_fail(lambda: gate_captured(root), "captured in PRE_GPU")

    # RUN01_PRESENT state
    _build_tree(root, runs=(RUNS[0],), with_analysis=False)
    expect_fail(lambda: gate_preflight(root), "preflight in RUN01_PRESENT")
    expect_pass(lambda: gate_between(root), "between-runs in RUN01_PRESENT")
    expect_fail(lambda: gate_captured(root), "captured in RUN01_PRESENT")

    # RUN02_PRESENT state (both runs, with analysis.json)
    _build_tree(root, runs=RUNS, with_analysis=True)
    expect_fail(lambda: gate_preflight(root), "preflight in RUN02_PRESENT")
    expect_fail(lambda: gate_between(root), "between-runs in RUN02_PRESENT (raw has 2 runs)")
    expect_pass(lambda: gate_captured(root), "captured in RUN02_PRESENT")

    # RUN02_PRESENT without analysis.json must fail captured
    _build_tree(root, runs=RUNS, with_analysis=False)
    expect_fail(lambda: gate_captured(root), "captured without analysis.json")

    shutil.rmtree(HERE / SELFTEST_DIR, ignore_errors=True)
    print("SEQTEST PASS (%d checks)" % n)
    return 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--seqtest", action="store_true")
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--captured", action="store_true")
    a = ap.parse_args()
    try:
        if a.selftest:
            return selftest()
        if a.seqtest:
            return seqtest()
        if a.preflight:
            gate_preflight(); print("PREFLIGHT PASS"); return 0
        if a.between_runs:
            gate_between(); print("BETWEEN-RUNS PASS"); return 0
        if a.captured:
            gate_captured(); print("CAPTURED PASS"); return 0
    except SystemExit as e:
        print(e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
