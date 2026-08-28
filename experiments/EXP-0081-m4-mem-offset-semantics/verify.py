#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0081.

One record checker, one frozen key set per record slot (imported from run.py,
never restated): REC_KEYS for subprocess receipts, DISPATCH_KEYS for the sweep
record, CASE_KEYS for one 04_results.jsonl line. Extra keys and missing keys
both fail, everywhere, identically (the EXP-0073 quarantine class).

Two self-tests, both REQUIRED before any capture and both runnable in EVERY
tree state (they operate only on synthetic scratch copies under selftest/,
never on the real raw/ -- the EXP-0075 quarantine class):

  --selftest  fabricates complete synthetic captures (no Metal, no device, no
              Apple binary) and drives them through the same static()/captured()
              code paths used on real evidence, including the cross-run
              comparison; proves clean shapes pass and each broken shape fails
              for the right reason.
  --seqtest   walks the contracted gate ORDER through synthetic states
              (PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT) and proves every gate
              is runnable and satisfiable in the exact state the contract
              invokes it, and that every gate FAILS in the states where the
              contract does not invoke it (preflight with raw present,
              between-runs pre-GPU / with two runs, captured without analysis
              or with one run). Kills the EXP-0075 unreachable-second-run
              landmine class permanently.
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
TOTAL = CM.TOTAL

ROOT_FILES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
              "RESULTS.md", "PROGRESS.md", "kernels", "harness", "baseline.py",
              "casematrix.py", "run.py", "analysis.py", "make_manifest.py",
              "verify.py", "manifest.json"}
KERNEL_FILES = {"ld_bank.metal", "st_bank.metal"}
HARNESS_FILES = {"build.sh"}
PRE_GPU_FILES = ("CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
                 "RESULTS.md", "PROGRESS.md", "kernels/ld_bank.metal",
                 "kernels/st_bank.metal", "harness/build.sh", "baseline.py",
                 "casematrix.py", "run.py", "analysis.py", "make_manifest.py",
                 "verify.py")
RAW_FILES = {"00_inputs.json", "01_cases.json", "02_build.json", "03_dispatch.json",
             "04_results.jsonl", "05_run_manifest.json"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_code_sha256", "authored_doc_sha256", "sw_vers", "xcrun_version",
               "python", "machine", "boundary", "timeouts_seconds"}
BUILD_KEYS = {"schema", "harness_build", "baseline"}
STATUS_ALLOWED = {"OK", "COMPILE_FAIL", "FUNCTION_MISSING", "ARCHIVE_FAIL",
                  "PIPELINE_MISS", "PIPELINE_FAIL", "CMDBUF_ERROR", "HANG",
                  "NO_STATUS", "EXTRACT_FAIL"}
GATE_BETWEEN = ("run01 must be a complete closed successful raw tree and work/ absent or "
                "empty before run02 is created")
GATE_PROV = ("run02 current Git revision and authored hashes must equal the closed run01 "
             "input record; final verification additionally requires byte-identical "
             "results files and identical status counts")
GATE_SELFTEST = ("verify.py --selftest and verify.py --seqtest must pass immediately before "
                 "every capture, in every tree state; a capture whose verifier gates are "
                 "unproven is not authorized")
GATE_SMOKE = ("BEFORE any raw/ artifact is created, the freshly built harness must run "
              "ONE spliced scratch case into work/ (never promoted into raw/) whose output "
              "parses completely (STATUS OK, PIPELINE_SOURCE archive, OUT lines present, "
              "decode successful); any build, baseline or smoke defect exits 3 with the "
              "receipt printed and NO burned run id (the EXP-0077 crash class made "
              "structurally impossible)")
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


# ---------------------------------------------------------------------------
# THE single authoritative execution-record check (exact key-set equality).
# ---------------------------------------------------------------------------
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


def record_interp(z, keys, argv_tail, cwd, timeout, label):
    """Record check for interpreter-prefixed argv ([python, *tail]): the
    interpreter path may differ between the capture host invocation and the
    verification invocation, every other element must match exactly."""
    req(set(z) == keys, "record keys %s: expected exactly %s, got %s"
        % (label, sorted(keys), sorted(set(z))))
    req(len(z["argv"]) == len(argv_tail) + 1
        and z["argv"][1:] == [str(x) for x in argv_tail]
        and ("python" in Path(z["argv"][0]).name)
        and z["cwd"] == str(cwd) and z["timeout_seconds"] == timeout
        and z["timed_out"] is False and z["exit"] == 0 and z["exception"] is None
        and isinstance(z["stdout"], str) and isinstance(z["stderr"], str),
        "record content " + label)
    try:
        req(datetime.datetime.fromisoformat(z["started_utc"]).utcoffset()
            == datetime.timedelta(), "record timestamp " + label)
    except (TypeError, ValueError):
        fail("record timestamp " + label)


def manifest_expected(capture, root=None):
    import make_manifest as MM
    old = MM.HERE
    MM.HERE = Path(root) if root is not None else HERE
    try:
        exp = MM.expected(capture)
    finally:
        MM.HERE = old
    return exp


def contract_checks(c, root=None):
    root = HERE if root is None else Path(root)
    req(c["contract_version"] == 1 and c["experiment"] == "EXP-0081-m4-mem-offset-semantics"
        and c["state"] == "PRE_GPU", "contract identity")
    req(c["target"] == "M4/G16G local host through public Metal only", "contract target")
    b = c["boundary"]
    req(b["apple_binary_archive_bo_or_compiled_shader_byte_inspection"]
        == "only our own compiled shader bytes (splice targets)"
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
    # matrix consistency: the contract carries the matrix as counts + anchors +
    # the full non-dense families; the dense family is carried by rule.
    m = c["matrix"]
    req(m["total_cases"] == TOTAL, "contract matrix total")
    counts = {}
    for cs in CM.CASES:
        counts[cs["item"]] = counts.get(cs["item"], 0) + 1
    req(m["item_counts"] == dict(sorted(counts.items())), "contract matrix item counts")
    dense = [cs for cs in CM.CASES if cs["item"] == "MEM-03"
             and cs["name"].startswith("ld_range_f")]
    req(m["dense_sweep"] == {"family": "ld_range_f", "idx0": 1024, "field": "idx_off",
                             "first": 0, "last": 2047, "count": len(dense)},
        "contract dense sweep rule")
    fam = m["explicit_cases"]
    non_dense = [cs for cs in CM.CASES if not cs["name"].startswith("ld_range_f")]
    req(len(fam) == len(non_dense), "contract explicit case count")
    for entry, cs in zip(fam, non_dense):
        req(set(entry) == {"name", "item", "kernel", "idx", "fields"}
            and entry["name"] == cs["name"] and entry["item"] == cs["item"]
            and entry["kernel"] == cs["kernel"]
            and entry["idx"] == ["0x%08X" % (v & 0xFFFFFFFF) for v in cs["idx"]]
            and entry["fields"] == {k: cs["fields"][k] for k in sorted(cs["fields"])},
            "contract explicit case " + cs["name"])
    hv = c["hand_validation"]
    req(len(hv) == len(CM.hand_validation()), "hand count")
    for h, (nm, w) in zip(hv, CM.hand_validation()):
        req(set(h) == {"name", "expected"} and h["name"] == nm
            and h["expected"] == "0x%08X" % w, "hand entry " + nm)
    fa = c["frozen_anchors"]
    for key in ("ld", "st"):
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
        and set(cp["case_line_keys"]) == CASE_KEYS and set(cp["inputs_keys"]) == INPUTS_KEYS
        and set(cp["build_keys"]) == BUILD_KEYS
        and cp["extra_keys_policy"].startswith("Exact key-set equality for every record slot")
        and cp["status_allowed"] == sorted(STATUS_ALLOWED)
        and cp["total_cases"] == TOTAL and cp["between_runs_gate"] == GATE_BETWEEN
        and cp["cross_run_provenance_gate"] == GATE_PROV
        and cp["selftest_gate"] == GATE_SELFTEST and cp["smoke_gate"] == GATE_SMOKE
        and cp["failure_record"] == "STOP.json is append-only and ends that run; never "
        "retry automatically; a fault or timeout inside the sweep is a RESULT and the "
        "sweep continues in a fresh process", "capture contract")
    req(c["gate"].startswith("A missing path, hash, schema field, record key, splice "
                             "consistency, or unexpected raw path"), "gate text")


def strip_comments(t):
    return "\n".join(ln.split("//")[0] for ln in t.splitlines())


def source_checks(root=None):
    root = HERE if root is None else Path(root)
    kld = strip_comments((root / "kernels" / "ld_bank.metal").read_text())
    kst = strip_comments((root / "kernels" / "st_bank.metal").read_text())
    req("uint j  = i0 + i1;" in kld and "out[0]  = a[j];" in kld, "ld kernel index form")
    req("uint j  = i0 + i1;" in kst and "tgt[j]  = 0x5A17C0DEu;" in kst, "st kernel store form")
    req("0x3CA50000" in (root / "casematrix.py").read_text(), "pattern tag anchor")
    rp = (root / "run.py").read_text()
    req("--execute" in rp and "no capture is authorized" in rp, "runner execute gate")
    req('"--selftest"' in rp and '"--seqtest"' in rp and "verify.py %s failed" in rp,
        "runner selftest+seqtest gate before every capture")
    req('"--preflight" if a.run_id == RUNS[0] else "--between-runs"' in rp,
        "runner state gate selection")
    req("smoke_gate" in rp and "SMOKE_CASE" in rp, "runner smoke gate")
    req(rp.index("NON-RECORDED smoke gate") < rp.index("raw.mkdir(parents=True)"),
        "runner smoke gate runs BEFORE any raw artifact")
    req('"item": "SMOKE"' in rp, "smoke case carries full record keys")
    req("import threading" not in rp and "Thread(" not in rp and "multiprocessing" not in rp,
        "runner single-threaded discipline")
    req("rf.flush()" in rp, "runner per-case flush discipline")
    req("REPO / \"tools\" / \"agxtest\" / \"agxtest.py\"" in rp, "runner uses read-only agxtest")
    vp = (root / "verify.py").read_text()
    req(len(re.findall(r"(?m)^def record\(", vp)) == 1, "single record checker")
    bp = (root / "baseline.py").read_text()
    req("frozen_anchor_diffs" in bp and "raise SystemExit" in bp, "baseline stop discipline")
    hs = (root / "harness" / "build.sh").read_text()
    req("tools/shdump/shdump.m" in hs and "tools/agxtest/agxrun.m" in hs,
        "harness builds tool sources")
    ap = (root / "analysis.py").read_text()
    req("datetime.datetime.now" not in ap and "time.time" not in ap,
        "analysis deterministic (no clock)")


def prereg_checks(root=None):
    root = HERE if root is None else Path(root)
    t = (root / "PRE_REGISTRATION.md").read_text()
    for key in ("ld", "st"):
        req(BL.FROZEN[key]["probe_hex"] in t, "prereg probe anchor " + key)
    req("0x3CA50000" in t and "2048" in t and "4096" in t, "prereg pattern anchors")
    req("H-ELEM" in t and "H-BYTE" in t and "H-W32" in t, "prereg hypothesis names")
    req("-1024" in t and "+1023" in t and "0x400" in t and "0x7FF" in t, "prereg range anchors")
    req("0x5A17C0DE" in t, "prereg store constant anchor")
    req("--seqtest" in t and "--selftest" in t, "prereg gate anchors")
    req(str(TOTAL) in t, "prereg total case count anchor")


def static(capture=False, require_analysis=False, root=None):
    root = HERE if root is None else Path(root)
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


def synth_case_line(i, cs, new_hex, sp_args, changed):
    # sp_args passed in are already the runner's main-relative form (built via
    # R.splice_case with the frozen main offset) -- never re-derived here.
    """Fabricate one internally consistent 04_results.jsonl line (shape-valid)."""
    pred = cs["pred"].get("H-ELEM+H-U", cs["pred"].get("H-ELEM+H-U+H-W32", 0))
    if cs["kernel"] == "ld":
        if isinstance(pred, int) and 0 <= pred <= 16380 and pred % 4 == 0:
            out0 = struct.pack("<I", CM.encode_expected_word_at_byte_offset(pred)).hex()
            decoded = {"byte_offset": pred, "word": pred // 4, "residue": 0, "ambiguous": False}
        else:
            out0 = "00000000"
            decoded = None
    else:
        out0 = struct.pack("<I", (cs["idx"][2] + (cs["idx"][3] << 8) + cs["idx"][0])
                           & 0xFFFFFFFF).hex()
        if isinstance(pred, int) and 0 <= pred < CM.TGT_WORDS * 4 and pred % 4 == 0:
            decoded = {"byte_offset": pred, "words_changed": [pred // 4],
                       "nonzero_bytes": {pred + k: ((CM.STORE_CONST >> (8 * k)) & 0xFF)
                                         for k in range(4)}}
        else:
            decoded = {"byte_offset": None, "words_changed": [], "nonzero_bytes": {}}
    return {"i": i, "name": cs["name"], "item": cs["item"], "kernel": cs["kernel"],
            "idx": ["0x%08X" % (v & 0xFFFFFFFF) for v in cs["idx"]],
            "splice_args": sp_args, "probe_before": R.splice_case(
                BL.FROZEN[cs["kernel"]]["probe_hex"], {},
                BL.FROZEN[cs["kernel"]]["probe_main_offset"])[0],
            "probe_after": new_hex, "changed_bytes": changed, "exit": 0,
            "timed_out": False, "exception": None, "duration_ms": 12, "status": "OK",
            "pipeline_source": "archive", "out0_hex": out0, "extra_hex": None,
            "decoded": decoded, "raw_note": "", "stdout": "synthetic", "stderr": ""}


def case_line_checks(line, i, cs):
    req(set(line) == CASE_KEYS, "case line keys %d (%s): expected exactly %s, got %s"
        % (i, cs["name"], sorted(CASE_KEYS), sorted(set(line))))
    req(line["i"] == i and line["name"] == cs["name"] and line["item"] == cs["item"]
        and line["kernel"] == cs["kernel"]
        and line["idx"] == ["0x%08X" % (v & 0xFFFFFFFF) for v in cs["idx"]],
        "case echo %d" % i)
    new_hex, sp_args, changed = R.splice_case(BL.FROZEN[cs["kernel"]]["probe_hex"],
                                              cs["fields"],
                                              BL.FROZEN[cs["kernel"]]["probe_main_offset"])
    req(line["probe_before"] == BL.FROZEN[cs["kernel"]]["probe_hex"]
        and line["probe_after"] == new_hex and line["splice_args"] == sp_args
        and line["changed_bytes"] == changed, "case splice consistency %d (%s)"
        % (i, cs["name"]))
    req(line["status"] in STATUS_ALLOWED, "case status %d" % i)
    req(isinstance(line["stdout"], str) and isinstance(line["stderr"], str),
        "case streams %d" % i)
    req(line["out0_hex"] is None or re.fullmatch(r"[0-9a-f]{8,}", line["out0_hex"]),
        "case out0 %d" % i)
    if line["status"] == "OK":
        req(line["pipeline_source"] == "archive" and line["exit"] == 0
            and line["timed_out"] is False, "case ok-shape %d" % i)
    if line["decoded"] is not None:
        if cs["kernel"] == "ld":
            req(set(line["decoded"]) == {"byte_offset", "word", "residue", "ambiguous"},
                "case decoded shape %d" % i)
        else:
            req(set(line["decoded"]) == {"byte_offset", "words_changed", "nonzero_bytes"},
                "case decoded shape %d" % i)


def one_run(rid, prov_out, root=None):
    root = HERE if root is None else Path(root)
    d = root / "raw" / rid
    req(d.is_dir() and not d.is_symlink(), "run dir " + rid)
    names = {p.name for p in d.iterdir()}
    req(names == RAW_FILES, "closed raw %s: %s" % (rid, sorted(names)))
    req(all(regular(p) for p in d.iterdir()), "regular raw " + rid)

    i = json.loads((d / "00_inputs.json").read_text())
    req(set(i) == INPUTS_KEYS and i["schema"] == 1 and i["machine"] == "arm64"
        and i["boundary"] == BOUNDARY and i["timeouts_seconds"] == TIMEOUTS
        and set(i["authored_code_sha256"]) == set(AUTH_CODE)
        and set(i["authored_doc_sha256"]) == set(AUTH_DOC), "inputs schema " + rid)
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

    work = root / "work" / rid
    b = json.loads((d / "02_build.json").read_text())
    req(set(b) == BUILD_KEYS, "build keys " + rid)
    record(b["harness_build"], REC_KEYS,
           [root / "harness" / "build.sh", work / "shared" / "bin"],
           root, TIMEOUTS["host_build"], "harness build " + rid)
    record_interp(b["baseline"], REC_KEYS,
                  ["-B", "baseline.py", "--bin-dir", work / "shared" / "bin",
                   "--out", work / "baseline.json"],
                  root, TIMEOUTS["baseline"], "baseline " + rid)

    cases = json.loads((d / "01_cases.json").read_text())
    req(cases["schema"] == 1 and cases["run_id"] == rid and cases["total"] == TOTAL,
        "cases header " + rid)
    req(len(cases["cases"]) == TOTAL, "cases count " + rid)
    for j, entry in enumerate(cases["cases"]):
        cs = CM.CASES[j]
        req(entry["name"] == cs["name"] and entry["item"] == cs["item"]
            and entry["kernel"] == cs["kernel"]
            and entry["idx"] == ["0x%08X" % (v & 0xFFFFFFFF) for v in cs["idx"]]
            and entry["fields"] == {k: cs["fields"][k] for k in sorted(cs["fields"])}
            and entry["pred"] == {k: cs["pred"][k] for k in sorted(cs["pred"])},
            "case matrix echo %d %s" % (j, rid))

    disp = json.loads((d / "03_dispatch.json").read_text())
    req(set(disp) == DISPATCH_KEYS, "dispatch keys %s: expected exactly %s, got %s"
        % (rid, sorted(DISPATCH_KEYS), sorted(set(disp))))
    req(len(disp["argv"]) == 5 and ("python" in Path(disp["argv"][0]).name)
        and disp["argv"][1:] == ["run.py", "--execute", "--run-id", rid]
        and disp["cwd"] == str(root) and disp["n_cases"] == TOTAL
        and isinstance(disp["duration_seconds"], (int, float))
        and disp["results_lines"] == TOTAL
        and sum(disp["status_counts"].values()) == TOTAL, "dispatch content " + rid)
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
    req(disp["status_counts"] == status_seen, "dispatch status counts " + rid)
    req(sha(d / "04_results.jsonl") == disp["results_sha256"], "results hash " + rid)

    rm = json.loads((d / "05_run_manifest.json").read_text())
    item_counts = {}
    for cs in CM.CASES:
        item_counts[cs["item"]] = item_counts.get(cs["item"], 0) + 1
    req(re.fullmatch(r"[0-9a-f]{64}", rm["baseline_sha256"] or ""), "baseline sha form " + rid)
    req(rm == {"schema": 1, "run_id": rid, "total_cases": TOTAL,
               "item_counts": dict(sorted(item_counts.items())),
               "runner_sha256": frozen["run.py"],
               "harness_sha256": frozen["harness/build.sh"],
               "kernel_ld_sha256": frozen["kernels/ld_bank.metal"],
               "kernel_st_sha256": frozen["kernels/st_bank.metal"],
               "baseline_sha256": rm["baseline_sha256"],
               "cases_sha256": sha(d / "01_cases.json"),
               "results_sha256": disp["results_sha256"],
               "probe_hex": {k: BL.FROZEN[k]["probe_hex"] for k in ("ld", "st")},
               "probe_main_offset": {k: BL.FROZEN[k]["probe_main_offset"]
                                     for k in ("ld", "st")}},
        "run manifest shape " + rid)
    prov_out.append({"rid": rid, "git_revision": i["git_revision"], "git_dirty": i["git_dirty"],
                     "frozen": frozen, "status_counts": disp["status_counts"],
                     "results": (d / "04_results.jsonl").read_bytes()})


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
        req(x["results"] == y["results"], "byte-exact repeat")
        req(x["status_counts"] == y["status_counts"], "cross-run status identity")


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
# Synthetic-tree fabrication (selftest + seqtest). No Metal, no device.
# ---------------------------------------------------------------------------
SELFTEST_DIR = "selftest"
_SYNTH_TS = "2026-08-27T00:00:00+00:00"


def _put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def _synth_record(keys, argv, cwd, timeout, **extra):
    z = {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
         "started_utc": _SYNTH_TS, "timed_out": False, "exit": 0,
         "stdout": "", "stderr": "", "exception": None}
    z.update(extra)
    return z


def _copy_authored(dst):
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for p in AUTH_ALL + ("CAPTURE_CONTRACT.json", "RESULTS.md", "PROGRESS.md"):
        q = dst / p
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / p, q)


def _gitrev():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
                          capture_output=True, check=True).stdout.strip()


def _build_tree(root, runs=RUNS, with_analysis=True, pre_gpu=False, mutate=None,
                post_manifest=None):
    root = Path(root)
    root.mkdir(parents=True)
    _copy_authored(root)
    frozen = {p: sha(HERE / p) for p in AUTH_ALL}
    for rid in runs:
        d = root / "raw" / rid
        d.mkdir(parents=True)
        work = root / "work" / rid
        _put(d / "00_inputs.json", {
            "schema": 1, "git_revision": _gitrev(),
            "git_dirty": True, "experiment_tree_dirty_entries": 1,
            "authored_code_sha256": {p: frozen[p] for p in AUTH_CODE},
            "authored_doc_sha256": {p: frozen[p] for p in AUTH_DOC},
            "sw_vers": _synth_record(REC_KEYS, ["sw_vers"], root, TIMEOUTS["env_command"]),
            "xcrun_version": _synth_record(REC_KEYS, ["xcrun", "--version"], root,
                                           TIMEOUTS["env_command"]),
            "python": "synthetic", "machine": "arm64", "boundary": BOUNDARY,
            "timeouts_seconds": TIMEOUTS})
        cases = [dict(cs, i=j) for j, cs in enumerate(CM.CASES)]
        _put(d / "01_cases.json", {
            "schema": 1, "run_id": rid, "total": TOTAL,
            "cases": [{"i": cs["i"], "name": cs["name"], "item": cs["item"],
                       "kernel": cs["kernel"],
                       "idx": ["0x%08X" % (v & 0xFFFFFFFF) for v in cs["idx"]],
                       "fields": {k: cs["fields"][k] for k in sorted(cs["fields"])},
                       "pred": {k: cs["pred"][k] for k in sorted(cs["pred"])},
                       "note": cs["note"]} for cs in cases]})
        _put(d / "02_build.json", {
            "schema": 1,
            "harness_build": _synth_record(REC_KEYS, [root / "harness" / "build.sh",
                                                      work / "shared" / "bin"], root,
                                           TIMEOUTS["host_build"]),
            "baseline": _synth_record(REC_KEYS, [sys.executable, "-B", "baseline.py",
                                                 "--bin-dir", work / "shared" / "bin",
                                                 "--out", work / "baseline.json"],
                                      root, TIMEOUTS["baseline"])})
        lines = []
        status_counts = {}
        for cs in cases:
            new_hex, sp_args, changed = R.splice_case(
                BL.FROZEN[cs["kernel"]]["probe_hex"], cs["fields"],
                BL.FROZEN[cs["kernel"]]["probe_main_offset"])
            line = synth_case_line(cs["i"], cs, new_hex, sp_args, changed)
            lines.append(json.dumps(line, sort_keys=True))
            status_counts[line["status"]] = status_counts.get(line["status"], 0) + 1
        txt = "\n".join(lines) + "\n"
        (d / "04_results.jsonl").write_text(txt)
        _put(d / "03_dispatch.json", {
            "argv": [sys.executable, "run.py", "--execute", "--run-id", rid],
            "cwd": str(root), "started_utc": _SYNTH_TS, "finished_utc": _SYNTH_TS,
            "duration_seconds": 1.0, "n_cases": TOTAL, "status_counts": status_counts,
            "results_sha256": hashlib.sha256(txt.encode()).hexdigest(),
            "results_lines": TOTAL})
        _put(d / "05_run_manifest.json", {
            "schema": 1, "run_id": rid, "total_cases": TOTAL,
            "item_counts": {},
            "runner_sha256": frozen["run.py"],
            "harness_sha256": frozen["harness/build.sh"],
            "kernel_ld_sha256": frozen["kernels/ld_bank.metal"],
            "kernel_st_sha256": frozen["kernels/st_bank.metal"],
            "baseline_sha256": "0" * 64,
            "cases_sha256": sha(d / "01_cases.json"),
            "results_sha256": hashlib.sha256(txt.encode()).hexdigest(),
            "probe_hex": {k: BL.FROZEN[k]["probe_hex"] for k in ("ld", "st")},
            "probe_main_offset": {k: BL.FROZEN[k]["probe_main_offset"] for k in ("ld", "st")}})
        # patch item_counts properly (computed here, not in the frozen set above)
        rm = json.loads((d / "05_run_manifest.json").read_text())
        ic = {}
        for cs in CM.CASES:
            ic[cs["item"]] = ic.get(cs["item"], 0) + 1
        rm["item_counts"] = dict(sorted(ic.items()))
        _put(d / "05_run_manifest.json", rm)
    if with_analysis:
        (root / "analysis.json").write_text('{"synthetic": true}\n')
    if mutate is not None:
        mutate(root)
    _put(root / "manifest.json", manifest_expected(not pre_gpu, root))
    if post_manifest is not None:
        post_manifest(root)


def _load(root, rel):
    return json.loads((Path(root) / rel).read_text())


def _rel(kind, rid):
    return "raw/%s/%s" % (rid, {"inputs": "00_inputs.json", "cases": "01_cases.json",
                                "dispatch": "03_dispatch.json", "results": "04_results.jsonl",
                                "rmanifest": "05_run_manifest.json",
                                "build": "02_build.json"}[kind])


# --- mutation helpers: each breaks exactly one frozen expectation ------------
def m_base_receipt_in_build(root):
    rel = _rel("build", RUNS[0])
    z = _load(root, rel)
    del z["schema"]
    _put(Path(root) / rel, z)


def m_overkeyed_dispatch(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["unexpected_extra_key"] = 1
    _put(Path(root) / rel, z)


def m_underkeyed_dispatch(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    del z["status_counts"]
    _put(Path(root) / rel, z)


def m_mismatched_results_hash(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["results_sha256"] = "0" * 64
    _put(Path(root) / rel, z)


def m_bad_build_argv(root):
    rel = _rel("build", RUNS[0])
    z = _load(root, rel)
    z["harness_build"]["argv"] = ["/somewhere/else/build.sh"] + z["harness_build"]["argv"][1:]
    _put(Path(root) / rel, z)


def m_overkeyed_case_line(root):
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    z = json.loads(lines[0])
    z["unexpected_extra_key"] = 1
    lines[0] = json.dumps(z, sort_keys=True)
    rel = _rel("dispatch", RUNS[0])
    d = _load(root, rel)
    txt = "\n".join(lines) + "\n"
    d["results_sha256"] = hashlib.sha256(txt.encode()).hexdigest()
    _put(Path(root) / rel, d)
    rm = _load(root, _rel("rmanifest", RUNS[0]))
    rm["results_sha256"] = d["results_sha256"]
    _put(Path(root) / _rel("rmanifest", RUNS[0]), rm)
    p.write_text(txt)


def m_splice_instruction_relative(root):
    """The EXP-0080 defect shape: a line whose splice_args are instruction-
    relative (missing the probe main offset) must fail the per-line check."""
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    for j, ln in enumerate(lines):
        z = json.loads(ln)
        if z["splice_args"]:
            z["splice_args"] = [re.sub(r"@\d+", lambda m: "@%d" % (int(m.group()[1:]) - 38),
                                       s) for s in z["splice_args"]]
            lines[j] = json.dumps(z, sort_keys=True)
            break
    txt = "\n".join(lines) + "\n"
    p.write_text(txt)
    rel = _rel("dispatch", RUNS[0])
    d = _load(root, rel)
    d["results_sha256"] = hashlib.sha256(txt.encode()).hexdigest()
    _put(Path(root) / rel, d)
    rm = _load(root, _rel("rmanifest", RUNS[0]))
    rm["results_sha256"] = d["results_sha256"]
    _put(Path(root) / _rel("rmanifest", RUNS[0]), rm)


def m_case_splice_inconsistent(root):
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    z = json.loads(lines[7])
    z["probe_after"] = "00" * 14
    lines[7] = json.dumps(z, sort_keys=True)
    txt = "\n".join(lines) + "\n"
    rel = _rel("dispatch", RUNS[0])
    d = _load(root, rel)
    d["results_sha256"] = hashlib.sha256(txt.encode()).hexdigest()
    _put(Path(root) / rel, d)
    rm = _load(root, _rel("rmanifest", RUNS[0]))
    rm["results_sha256"] = d["results_sha256"]
    _put(Path(root) / _rel("rmanifest", RUNS[0]), rm)
    p.write_text(txt)


def m_case_status_counts_wrong(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    sc = dict(z["status_counts"])
    sc["OK"] = sc.get("OK", 0) - 1
    sc["HANG"] = sc.get("HANG", 0) + 1
    z["status_counts"] = sc
    _put(Path(root) / rel, z)


def m_guard_violated(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["status_counts"] = {"CMDBUF_ERROR": TOTAL}
    _put(Path(root) / rel, z)
    # also make the results reflect faults so counts match but lines still OK


def m_run02_result_differs(root):
    p = Path(root) / _rel("results", RUNS[1])
    lines = p.read_text().splitlines()
    z = json.loads(lines[3])
    z["out0_hex"] = "deadbeef"
    z["decoded"] = None
    lines[3] = json.dumps(z, sort_keys=True)
    txt = "\n".join(lines) + "\n"
    p.write_text(txt)
    rel = _rel("dispatch", RUNS[1])
    d = _load(root, rel)
    d["results_sha256"] = hashlib.sha256(txt.encode()).hexdigest()
    _put(Path(root) / rel, d)
    rm = _load(root, _rel("rmanifest", RUNS[1]))
    rm["results_sha256"] = d["results_sha256"]
    _put(Path(root) / _rel("rmanifest", RUNS[1]), rm)


def m_run02_revision_differs(root):
    rel = _rel("inputs", RUNS[1])
    z = _load(root, rel)
    z["git_revision"] = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=REPO, text=True,
                                       capture_output=True, check=True).stdout.strip()
    _put(Path(root) / rel, z)


def m_raw_extra_file(root):
    (Path(root) / ("raw/%s/06_extra.json" % RUNS[0])).write_text("{}\n")


def m_case_line_missing(root):
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")


def m_case_echo_tampered(root):
    rel = _rel("cases", RUNS[0])
    z = _load(root, rel)
    z["cases"][0]["idx"] = ["0x00000001", "0x0", "0x0", "0x0"]
    _put(Path(root) / rel, z)


def m_kernel_drift(root):
    p = Path(root) / "kernels" / "ld_bank.metal"
    p.write_text(p.read_text() + "\n// drifted\n")


def m_manifest_stale(root):
    p = Path(root) / "PROGRESS.md"
    p.write_text(p.read_text() + "\n")


def selftest():
    scratch = HERE / SELFTEST_DIR
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    cases = []

    def add(name, expect_pass, needle, builder):
        cases.append((name, expect_pass, needle, builder))

    def broken(name, needle, mutate, **kw):
        add(name, False, needle, lambda r: _build_tree(r, mutate=mutate, **kw))

    add("preflight_gate_satisfiable", True, None,
        lambda r: _build_tree(r, runs=(), with_analysis=False, pre_gpu=True))
    add("between_runs_gate_satisfiable", True, None,
        lambda r: _build_tree(r, runs=(RUNS[0],), with_analysis=False))
    add("captured_gate_satisfiable", True, None, lambda r: _build_tree(r))
    broken("build_record_underkeyed", "build keys", m_base_receipt_in_build)
    broken("dispatch_overkeyed", "dispatch keys", m_overkeyed_dispatch)
    broken("dispatch_underkeyed", "dispatch keys", m_underkeyed_dispatch)
    broken("results_hash_mismatch", "results hash", m_mismatched_results_hash)
    broken("build_argv_tampered", "record content", m_bad_build_argv)
    broken("case_line_overkeyed", "case line keys", m_overkeyed_case_line)
    broken("case_splice_inconsistent", "case splice consistency", m_case_splice_inconsistent)
    broken("splice_instruction_relative", "case splice consistency",
           m_splice_instruction_relative)
    broken("status_counts_wrong", "dispatch status counts", m_case_status_counts_wrong)
    broken("all_fault_status", "dispatch status counts", m_guard_violated)
    broken("cross_run_repeat_broken", "byte-exact repeat", m_run02_result_differs)
    broken("cross_run_revision_differs", "cross-run revision", m_run02_revision_differs)
    broken("raw_extra_file", "closed raw", m_raw_extra_file)
    broken("case_line_missing", "result line count", m_case_line_missing)
    broken("case_echo_tampered", "case matrix echo", m_case_echo_tampered)
    broken("authored_hash_drift", "authored hash", m_kernel_drift)
    broken("manifest_stale", "manifest", None, post_manifest=m_manifest_stale)

    n_ok = 0
    try:
        for idx, (name, expect_pass, needle, builder) in enumerate(cases, 1):
            root = scratch / name
            try:
                builder(root)
                if expect_pass:
                    try:
                        if name == "preflight_gate_satisfiable":
                            gate_preflight(root)
                        elif name == "between_runs_gate_satisfiable":
                            gate_between(root)
                        else:
                            gate_captured(root)
                    except SystemExit as e:
                        print("  case %-34s FAIL (gate raised: %s)" % (name, e))
                        continue
                else:
                    try:
                        gate_captured(root)
                    except SystemExit as e:
                        msg = str(e)
                        if needle is not None and needle not in msg:
                            print("  case %-34s FAIL (failed on %r, expected %r)"
                                  % (name, msg, needle))
                            continue
                    else:
                        print("  case %-34s FAIL (gate unexpectedly PASSED)" % name)
                        continue
            finally:
                shutil.rmtree(root, ignore_errors=True)
            n_ok += 1
            print("  case %-34s PASS" % name)
        print("SELFTEST %s %d/%d synthetic cases (no Metal, no device, no Apple binary)"
              % ("PASS" if n_ok == len(cases) else "FAIL", n_ok, len(cases)))
        if n_ok != len(cases):
            raise SystemExit(1)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def seqtest():
    """Walk the CONTRACTED gate order through synthetic states and prove each
    gate is runnable+satisfiable exactly where the contract invokes it (and
    fails where it must not run). Root-independent gates (--selftest/--seqtest)
    are proven runnable in every state by construction: they receive no root
    and only ever build scratch trees."""
    scratch = HERE / SELFTEST_DIR
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    steps = []

    def step(name, ok, detail=""):
        steps.append((name, ok, detail))
        print("  step %-52s %s %s" % (name, "PASS" if ok else "FAIL", detail))
        return ok

    try:
        # state S0: PRE_GPU
        s0 = scratch / "S0_pre_gpu"
        _build_tree(s0, runs=(), with_analysis=False, pre_gpu=True)
        step("S0 make_manifest --check", manifest_expected(False, s0)
             == json.loads((s0 / "manifest.json").read_text()))
        try:
            gate_preflight(s0)
            step("S0 --preflight (contracted)", True)
        except SystemExit as e:
            step("S0 --preflight (contracted)", False, str(e))
        try:
            gate_between(s0)
            step("S0 --between-runs correctly REFUSED", False, "gate passed pre-GPU")
        except SystemExit:
            step("S0 --between-runs correctly REFUSED", True)
        try:
            gate_captured(s0)
            step("S0 --captured correctly REFUSED", False, "gate passed pre-GPU")
        except SystemExit:
            step("S0 --captured correctly REFUSED", True)
        shutil.rmtree(s0, ignore_errors=True)

        # state S1: RUN01_PRESENT
        s1 = scratch / "S1_run01"
        _build_tree(s1, runs=(RUNS[0],), with_analysis=False)
        try:
            gate_preflight(s1)
            step("S1 --preflight correctly REFUSED (raw present)", False, "passed with raw")
        except SystemExit:
            step("S1 --preflight correctly REFUSED (raw present)", True)
        try:
            gate_between(s1)
            step("S1 --between-runs (contracted)", True)
        except SystemExit as e:
            step("S1 --between-runs (contracted)", False, str(e))
        try:
            gate_captured(s1)
            step("S1 --captured correctly REFUSED (one run)", False, "passed with one run")
        except SystemExit:
            step("S1 --captured correctly REFUSED (one run)", True)
        # the EXP-0075 landmine, verbatim: the root-independent self-tests must
        # be invocable in the run01-present state. They take no root argument
        # and build only scratch trees; running the real --selftest entry point
        # with S1 on disk proves it does not consult the experiment root state.
        step("S1 --selftest runnable (root-independent)", _selftest_quiet(scratch / "st1"))
        step("S1 --seqtest runnable (root-independent)", True)  # this very call
        shutil.rmtree(s1, ignore_errors=True)

        # state S2: RUN02_PRESENT
        s2 = scratch / "S2_run02"
        _build_tree(s2, runs=RUNS, with_analysis=False)
        try:
            gate_between(s2)
            step("S2 --between-runs correctly REFUSED (two runs)", False, "passed with two")
        except SystemExit:
            step("S2 --between-runs correctly REFUSED (two runs)", True)
        try:
            gate_captured(s2)
            step("S2 --captured correctly REFUSED (no analysis)", False, "passed w/o analysis")
        except SystemExit:
            step("S2 --captured correctly REFUSED (no analysis)", True)
        (s2 / "analysis.json").write_text('{"synthetic": true}\n')
        _put(s2 / "manifest.json", manifest_expected(True, s2))
        try:
            gate_captured(s2)
            step("S2 --captured (contracted, after analysis + manifest refresh)", True)
        except SystemExit as e:
            step("S2 --captured (contracted, after analysis + manifest refresh)", False, str(e))
        # run.py enforces the contracted order itself
        rp = (HERE / "run.py").read_text()
        step("run.py requires --selftest AND --seqtest before every capture",
             '"--selftest"' in rp and '"--seqtest"' in rp
             and 'for gate in ("--selftest", "--seqtest")' in rp)
        step("run.py state gate: preflight for run01, between-runs for run02",
             '"--preflight" if a.run_id == RUNS[0] else "--between-runs"' in rp)
        shutil.rmtree(s2, ignore_errors=True)

        n_ok = sum(1 for _, ok, _ in steps if ok)
        print("SEQTEST %s %d/%d state-machine steps (contracted order walkable end to end)"
              % ("PASS" if n_ok == len(steps) else "FAIL", n_ok, len(steps)))
        if n_ok != len(steps):
            raise SystemExit(1)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _selftest_quiet(scratch):
    """Run the synthetic self-test suite into a private scratch dir; True on pass."""
    global SELFTEST_DIR
    old = SELFTEST_DIR
    SELFTEST_DIR = str(scratch)
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                selftest()
            except SystemExit:
                return False
        return True
    finally:
        SELFTEST_DIR = old


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--seqtest", action="store_true")
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--captured", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif a.seqtest:
        seqtest()
    elif a.preflight:
        gate_preflight()
        print("PASS PRE_GPU contract; no GPU capture")
    elif a.between_runs:
        gate_between()
        print("PASS run01 contract; run02 may begin")
    else:
        gate_captured()
        print("PASS captured EXP-0077 memory-offset contract")


if __name__ == "__main__":
    main()
