#!/usr/bin/env python3
"""Fail-closed static, post-capture, self-test, and gate-sequence verifier
for EXP-0095, adapted from EXP-0079/EXP-0083's proven --selftest/--seqtest
pattern (both dead ends -- EXP-0075's frozen gate contradiction, EXP-0072's
truncation class -- are structurally excluded here the same way they were
fixed there):

1. --selftest is STATE-AGNOSTIC: it detects the tree's actual capture state
   (PRE_GPU vs raw/ present) and verifies the closed-root/contract-static
   invariants for THAT state, then runs a synthetic in-process schema
   self-test that never reads the real raw/ tree.
2. --seqtest is a gate-sequence STATE MACHINE: it builds three isolated
   fixture trees (PRE_GPU / RUN01_PRESENT / RUN02_PRESENT) and actually
   subprocess-invokes every contracted gate for that state, proving each is
   both runnable and satisfiable where the contract requires it.
3. The pre-capture NON-RECORDED SMOKE GATE (run.py's smoke_gate/
   smoke_problems) is schema-tested here against the exact truncation class
   that quarantined EXP-0072, plus every other tamper class.
4. NO NONDETERMINISTIC FIELD enters any byte-compared record: every
   receipt/payload validated here is checked field-by-field against a closed
   key set (REC_KEYS / PAYLOAD_KEYS / DESCRIPTOR_KEYS), and cross-run
   comparison (compare_runs) requires the full normalized record to be
   byte-identical between run01 and run02.
5. Selftest fixtures are built from RECORDED REALITY: ok_payload()/
   ok_descriptor_payload() are driven by CAPTURE_CONTRACT.json's own frozen
   case list (loaded live, not hand-copied), and the synthetic two-run
   capture in selftest() is validated with the SAME validate_run()/
   compare_runs() the real captured() gate uses.
"""
import argparse, datetime, hashlib, importlib.util, json, re, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT_NAMES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md", "RESULTS.md", "PROGRESS.md",
              "kernels", "harness", "provenance", "run.py", "analysis.py", "make_manifest.py", "verify.py",
              "manifest.json"}
AUTH = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "kernels/matrix.metal", "kernels/direct128.metal",
        "kernels/gen_direct128.py", "harness/probe.m", "run.py", "analysis.py", "make_manifest.py", "verify.py")
DOC_FILES = ("README.md", "RESULTS.md", "PROGRESS.md")
RUNS = ("m4-20260829-run01", "m4-20260829-run02")
SMOKE_CASE = "a05_1d_read_first"
SMOKE_STEP = "run.py --execute pre-capture smoke invocation (capture.pre_capture_smoke) must pass before raw/ is created"
PAYLOAD_KEYS = {"schema", "family", "case", "status", "library_ok", "library_error", "pipelines",
                 "resource_ok", "resource_error", "command_buffer_status", "command_buffer_error",
                 "device", "machine", "os", "prefix_guard_ok", "suffix_guard_ok", "out_hex", "out_words"}
DESCRIPTOR_KEYS = {"schema", "family", "case", "width", "bytes_needed", "texture_ok", "device"}
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit", "stdout", "stderr", "exception"}
INPUT_KEYS = {"schema", "git_revision", "git_dirty", "authored_sha256", "sw_vers", "xcrun_version",
              "device_model", "machine", "boundary"}
RUN_MANIFEST_KEYS = ["schema", "run_id", "cases", "fresh_process_per_case", "runner_sha256", "harness_sha256",
                     "matrix_kernel_sha256", "direct128_kernel_sha256", "contract_sha256"]
PRE_CAPTURE_GATE = ["python3 -B verify.py --selftest", "python3 -B verify.py --seqtest",
                    "python3 -B make_manifest.py --check", "python3 -B verify.py --preflight", SMOKE_STEP]
PRE_SECOND_RUN_GATE = ["python3 -B verify.py --selftest", "python3 -B verify.py --seqtest",
                       "python3 -B make_manifest.py --check", "python3 -B verify.py --between-runs", SMOKE_STEP]

def fail(s):
    raise SystemExit("FAIL " + s)

def req(v, s):
    if not v:
        fail(s)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def regular(p):
    return p.is_file() and not p.is_symlink()

def cases():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())["cases"]

def manifest_expected(capture):
    paths = tuple(sorted(str(p.relative_to(HERE)) for p in HERE.rglob("*")
                         if p.is_file() and not p.is_symlink() and p.name != "manifest.json")) if capture else None
    if paths is None:
        paths = tuple(sorted(set(AUTH + DOC_FILES + tuple(str(p.relative_to(HERE)) for p in (HERE / "provenance").rglob("*") if p.is_file()))))
    return {"schema": 1, "state": "CAPTURED" if capture else "PRE_GPU",
            "artifacts": [{"path": p, "bytes": (HERE / p).stat().st_size, "sha256": sha(HERE / p)} for p in paths]}

# ---------------------------------------------------------------- schema gates

def receipt(z, argv, cwd, timeout, label):
    req(set(z) == REC_KEYS, "receipt key set " + label)
    req(z["argv"] == [str(x) for x in argv] and z["cwd"] == str(cwd)
        and z["timeout_seconds"] == timeout and z["timed_out"] is False and z["exit"] == 0
        and z["exception"] is None and isinstance(z["stdout"], str) and isinstance(z["stderr"], str), label)
    try:
        req(datetime.datetime.fromisoformat(z["started_utc"]).utcoffset() == datetime.timedelta(), label + " timestamp")
    except (TypeError, ValueError):
        fail(label + " timestamp")

def abort_receipt(z, argv, cwd, timeout, label):
    req(set(z) == REC_KEYS, "abort receipt key set " + label)
    req(z["argv"] == [str(x) for x in argv] and z["cwd"] == str(cwd) and z["timeout_seconds"] == timeout
        and z["timed_out"] is False and z["exception"] is None
        and isinstance(z["exit"], int) and z["exit"] < 0, label + " expected negative-signal exit")

def check_inputs(i, label):
    req(set(i) == INPUT_KEYS, "inputs key set " + label)
    req(i["schema"] == 1 and i["machine"] == "arm64" and isinstance(i["git_dirty"], bool)
        and i["boundary"] == "public Metal only; owned in-bounds resources; no binary/archive/BO inspection"
        and set(i["authored_sha256"]) == set(AUTH), "inputs schema " + label)

def check_inputs_bindings(i, label):
    for path, want in i["authored_sha256"].items():
        req(sha(HERE / path) == want, "post-capture source binding " + label + " " + path)

def provenance_row(i):
    return {"git_revision": i["git_revision"], "authored_sha256": i["authored_sha256"],
            "sw_vers_output": {"stdout": i["sw_vers"].get("stdout"), "stderr": i["sw_vers"].get("stderr")},
            "xcrun_version_output": {"stdout": i["xcrun_version"].get("stdout"), "stderr": i["xcrun_version"].get("stderr")},
            "device_model_output": {"stdout": i["device_model"].get("stdout"), "stderr": i["device_model"].get("stderr")}}

def payload(p, c, label):
    req(set(p) == PAYLOAD_KEYS, "payload key set " + label)
    req(p["family"] == c["family"] and p["case"] == c["case"], "payload identity " + label)
    req(p["status"] == "ok", "payload status must be ok for a contracted expect_status=ok case " + label)
    req(p["library_ok"] is True and p["resource_ok"] is True, "library/resource flags " + label)
    req(p["command_buffer_status"] == 4 and p["command_buffer_error"] == "", "command buffer " + label)
    req(p["device"] == "Apple M4" and p["machine"] == "arm64" and isinstance(p["os"], str) and p["os"], "device identity " + label)
    req(isinstance(p["pipelines"], list) and all(set(x) == {"name", "ok", "error"} and x["ok"] is True for x in p["pipelines"]), "pipeline records " + label)
    req(p["prefix_guard_ok"] is True and p["suffix_guard_ok"] is True, "guard flags " + label)
    oh, ow = p["out_hex"], p["out_words"]
    req(isinstance(oh, str) and len(oh) == 192 and re.fullmatch(r"[0-9a-f]+", oh), "out_hex grammar " + label)
    b = bytes.fromhex(oh)
    req(b[:16] == b"\x5a" * 16 and b[80:96] == b"\xa5" * 16, "derived guard bytes " + label)
    derived = [int.from_bytes(b[16 + 4 * i:20 + 4 * i], "little") for i in range(16)]
    req(isinstance(ow, list) and len(ow) == 16 and all(type(x) is int and 0 <= x < 2 ** 32 for x in ow) and ow == derived,
        "out_words derivation " + label)
    n = c["n_outputs"]
    exp = c["expected_out_words"]
    for i in range(n, 16):
        req(ow[i] == 0xEEEEEEEE, "unexpected write beyond n_outputs at word %d " % i + label)
    for i in range(n):
        if exp[i] is not None:
            req(ow[i] == exp[i], "expected word %d mismatch " % i + label)

def descriptor_payload(p, c, label):
    req(set(p) == DESCRIPTOR_KEYS, "descriptor payload key set " + label)
    req(p["family"] == c["family"] and p["case"] == c["case"], "descriptor payload identity " + label)
    req(p["width"] == c["args"]["width"], "descriptor width echo " + label)
    req(p["bytes_needed"] == c["args"]["width"] * {"r8uint": 1, "rgba32uint": 16}[c["args"]["format"]], "descriptor bytes_needed " + label)
    req(p["texture_ok"] is True, "descriptor texture_ok " + label)
    req(p["device"] == "Apple M4", "descriptor device " + label)

def validate_run(rid, objs):
    i = objs["inputs"]
    check_inputs(i, rid)
    check_inputs_bindings(i, rid)
    receipt(i["sw_vers"], ["sw_vers"], HERE, 5, "sw_vers " + rid)
    receipt(i["xcrun_version"], ["xcrun", "--version"], HERE, 5, "xcrun " + rid)
    receipt(i["device_model"], ["sysctl", "-n", "hw.model"], HERE, 5, "hw.model " + rid)
    probe = HERE / "work" / rid / "probe"
    receipt(objs["build"], ["xcrun", "clang", "-fobjc-arc", "-o", probe, HERE / "harness/probe.m",
                            "-framework", "Metal", "-framework", "Foundation"], HERE, 120, "build " + rid)
    cs = cases()
    rm = objs["run_manifest"]
    req(rm == {"schema": 1, "run_id": rid, "cases": [c["case"] for c in cs], "fresh_process_per_case": True,
               "runner_sha256": i["authored_sha256"]["run.py"],
               "harness_sha256": i["authored_sha256"]["harness/probe.m"],
               "matrix_kernel_sha256": i["authored_sha256"]["kernels/matrix.metal"],
               "direct128_kernel_sha256": i["authored_sha256"]["kernels/direct128.metal"],
               "contract_sha256": i["authored_sha256"]["CAPTURE_CONTRACT.json"]}, "run manifest " + rid)
    rows = []
    for c in cs:
        z = objs["cases"][c["case"]]
        argv = [probe, "--family", c["family"], "--case", c["case"], "--source", HERE / c["kernel_file"],
                "--args", json.dumps(c["args"], sort_keys=True)]
        timeout = c.get("timeout_seconds", 60)
        if c.get("expect_status") == "abort":
            abort_receipt(z, argv, HERE, timeout, "case process " + c["case"])
            rows.append({"case": c["case"], "abort_exit": z["exit"]})
            continue
        receipt(z, argv, HERE, timeout, "case process " + c["case"])
        try:
            p = json.loads(z["stdout"])
        except json.JSONDecodeError:
            fail("case stdout not one JSON object " + c["case"])
        if c["family"] == "a07_descriptor":
            descriptor_payload(p, c, c["case"])
        else:
            payload(p, c, c["case"])
        rows.append(p)
    return provenance_row(i), rows

def compare_runs(provenance, rows):
    if len(provenance) == 2:
        req(provenance[0] == provenance[1], "cross-run revision/authored/environment provenance")
        req(rows[0] == rows[1], "byte-exact repeat")

def load_run(rid):
    d = HERE / "raw" / rid
    cs = cases()
    names = {"00_inputs.json", "01_host_build.json", "run_manifest.json"} | {f"case_{c['case']}.json" for c in cs}
    req(d.is_dir() and not d.is_symlink() and {p.name for p in d.iterdir()} == names and all(regular(p) for p in d.iterdir()), "closed raw " + rid)
    return {"inputs": json.loads((d / "00_inputs.json").read_text()),
            "build": json.loads((d / "01_host_build.json").read_text()),
            "run_manifest": json.loads((d / "run_manifest.json").read_text()),
            "cases": {c["case"]: json.loads((d / f"case_{c['case']}.json").read_text()) for c in cs}}

def work_clean():
    w = HERE / "work"
    req(not w.exists() or (w.is_dir() and not w.is_symlink() and not any(w.iterdir())), "work absent or empty")

# ---------------------------------------------------------------- static tree

def static(capture=False, need_analysis=False):
    names = {p.name for p in HERE.iterdir()}
    allowed = ROOT_NAMES | ({"raw"} if capture else set()) | ({"analysis.json"} if "analysis.json" in names else set()) | ({"work"} if "work" in names else set())
    req(not HERE.is_symlink() and names == allowed, "closed root: " + str(names ^ allowed))
    if capture:
        req((HERE / "raw").is_dir() and not (HERE / "raw").is_symlink(), "raw tree present")
    if need_analysis:
        req(regular(HERE / "analysis.json"), "derived analysis")
    elif "analysis.json" in names:
        req(regular(HERE / "analysis.json"), "derived analysis")
    for p in AUTH + DOC_FILES + ("manifest.json",):
        req(regular(HERE / p), "regular " + p)
    kd = HERE / "kernels"
    req(kd.is_dir() and not kd.is_symlink() and {p.name for p in kd.iterdir()} == {"matrix.metal", "direct128.metal", "gen_direct128.py"}
        and all(regular(x) for x in kd.iterdir()), "closed kernels")
    hd = HERE / "harness"
    req(hd.is_dir() and not hd.is_symlink() and {p.name for p in hd.iterdir()} == {"probe.m"} and all(regular(x) for x in hd.iterdir()), "closed harness")
    req((HERE / "provenance").is_dir(), "provenance dir present")

    c = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    req(c["state"] == "PRE_GPU" and c["experiment"] == "EXP-0095-m4-texture-image-matrix", "contract identity")
    cs = c["cases"]
    ids = [x["case"] for x in cs]
    req(len(ids) == len(set(ids)), "unique case ids")
    for x in cs:
        req(set(x) == {"case", "family", "kernel_file", "args", "n_outputs", "expected_out_words",
                       "expect_status", "rule", "rule_note", "timeout_seconds"}, "case record keys " + x["case"])
        req(x["kernel_file"] in ("kernels/matrix.metal", "kernels/direct128.metal"), "kernel file " + x["case"])
        req(isinstance(x["expected_out_words"], list) and len(x["expected_out_words"]) == 16
            and all(v is None or (type(v) is int and 0 <= v < 2 ** 32) for v in x["expected_out_words"]), "expected words grammar " + x["case"])
        req(0 <= x["n_outputs"] <= 16, "n_outputs range " + x["case"])
        req(x["expect_status"] in ("ok", "abort"), "expect_status " + x["case"])
        req(x["rule"] in ("a", "b", "c"), "rule " + x["case"])
        req(isinstance(x["rule_note"], str) and x["rule_note"], "rule_note " + x["case"])
        req(isinstance(x["timeout_seconds"], int) and x["timeout_seconds"] > 0, "timeout " + x["case"])
    req(set(c["blob_sha256"]) == set(AUTH) - {"CAPTURE_CONTRACT.json"}, "contract blob binding set")
    for p, h in c["blob_sha256"].items():
        req(sha(HERE / p) == h, "contract blob binding " + p)
    req(c["boundary"] == "public Metal only; owned in-bounds resources; no binary/archive/BO inspection", "boundary")
    req(c["capture"]["runs"] == list(RUNS) and c["capture"]["payload_keys"] == sorted(PAYLOAD_KEYS)
        and c["capture"]["descriptor_keys"] == sorted(DESCRIPTOR_KEYS)
        and c["capture"]["receipt_keys"] == sorted(REC_KEYS) and c["capture"]["inputs_keys"] == sorted(INPUT_KEYS)
        and c["capture"]["run_manifest_keys"] == RUN_MANIFEST_KEYS
        and c["capture"]["pre_capture_gate"] == PRE_CAPTURE_GATE
        and c["capture"]["pre_second_run_gate"] == PRE_SECOND_RUN_GATE
        and c["capture"]["statuses_exit_zero"] == ["ok"], "capture grammar")
    m = json.loads((HERE / "manifest.json").read_text())
    req(m == manifest_expected(capture), "manifest")

def captured(runs):
    raw = HERE / "raw"
    req(raw.is_dir() and not raw.is_symlink() and {p.name for p in raw.iterdir()} == set(runs), "exact raw runs")
    provenance, rows = [], []
    for rid in runs:
        prov, rws = validate_run(rid, load_run(rid))
        provenance.append(prov)
        rows.append(rws)
    compare_runs(provenance, rows)

# ---------------------------------------------------------------- self-test

def load_runner():
    spec = importlib.util.spec_from_file_location("exp0095_runner", HERE / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def synthetic_receipt(argv, timeout, stdout, exit_code=0):
    return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
            "started_utc": "2026-08-29T00:00:00+00:00", "timed_out": False, "exit": exit_code,
            "stdout": stdout, "stderr": "", "exception": None}

def ok_payload(c):
    words = [(v if v is not None else 0xEEEEEEEE) for v in c["expected_out_words"]]
    b = b"\x5a" * 16 + b"".join(w.to_bytes(4, "little") for w in words) + b"\xa5" * 16
    return {"schema": 1, "family": c["family"], "case": c["case"], "status": "ok", "library_ok": True,
            "library_error": "", "pipelines": [], "resource_ok": True, "resource_error": "",
            "command_buffer_status": 4, "command_buffer_error": "", "device": "Apple M4", "machine": "arm64",
            "os": "Version 26.6.2 (Build 25G82)", "prefix_guard_ok": True, "suffix_guard_ok": True,
            "out_hex": b.hex(), "out_words": words}

def ok_descriptor_payload(c):
    fmt = c["args"]["format"]
    width = c["args"]["width"]
    return {"schema": 1, "family": c["family"], "case": c["case"], "width": width,
            "bytes_needed": width * {"r8uint": 1, "rgba32uint": 16}[fmt], "texture_ok": True, "device": "Apple M4"}

def synthetic_run(mod, rid, contract_cases, env, run_manifest):
    cases_map = {}
    for c in contract_cases:
        probe = HERE / "work" / rid / "probe"
        argv = [probe, "--family", c["family"], "--case", c["case"], "--source", HERE / c["kernel_file"],
                "--args", json.dumps(c["args"], sort_keys=True)]
        if c.get("expect_status") == "abort":
            cases_map[c["case"]] = synthetic_receipt(argv, c.get("timeout_seconds", 60), "", exit_code=-6)
        elif c["family"] == "a07_descriptor":
            cases_map[c["case"]] = synthetic_receipt(argv, c.get("timeout_seconds", 60), json.dumps(ok_descriptor_payload(c)))
        else:
            cases_map[c["case"]] = synthetic_receipt(argv, c.get("timeout_seconds", 60), json.dumps(ok_payload(c)))
    return {"inputs": env, "build": synthetic_receipt(mod.build_argv(HERE / "work" / rid), 120, ""),
            "run_manifest": run_manifest, "cases": cases_map}

def must_fail(label, fn):
    try:
        fn()
    except SystemExit as e:
        if str(e).startswith("FAIL "):
            return
        raise AssertionError("selftest " + label + ": unexpected SystemExit " + str(e))
    raise AssertionError("selftest " + label + ": check did not fail")

def selftest():
    contract = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    cs = contract["cases"]
    req([x["case"] for x in cs] == [x["case"] for x in cases()], "selftest case order/identity vs contract")
    mod = load_runner()
    r = mod.rec(["/usr/bin/true"], 5)
    req(r["exit"] == 0 and r["exception"] is None and set(r) == REC_KEYS, "run.py receipt key set")
    env = mod.env_record()
    check_inputs(env, "selftest")
    for z in (env["sw_vers"], env["xcrun_version"], env["device_model"]):
        req(z["exit"] == 0 and z["timed_out"] is False and z["exception"] is None, "selftest environment command")
    req(mod.env_problems(env) == [], "run.py environment validator accepts a clean record")
    rm = mod.run_manifest_record(RUNS[0], [c["case"] for c in cs])
    req(set(rm) == set(RUN_MANIFEST_KEYS), "run manifest key set")
    probe = HERE / "work" / RUNS[0] / "probe"
    for c in cs[:3] + cs[-2:]:
        argv = mod.case_argv(HERE / "work" / RUNS[0], c)
        req(argv == [probe, "--family", c["family"], "--case", c["case"], "--source", HERE / c["kernel_file"],
                     "--args", json.dumps(c["args"], sort_keys=True)], "case argv template " + c["case"])
    req(mod.SMOKE_CASE == SMOKE_CASE == contract["capture"]["pre_capture_smoke"]["case"],
        "smoke case identity across runner, verifier, and contract")
    pkeys, statuses = contract["capture"]["payload_keys"], contract["capture"]["statuses_exit_zero"]
    sm_case = next(x for x in cs if x["case"] == SMOKE_CASE)
    good = ok_payload(sm_case)
    sm_argv = mod.case_argv(HERE / "work" / RUNS[0], sm_case)
    good_rec = synthetic_receipt(sm_argv, mod.SMOKE_TIMEOUT, json.dumps(good) + "\n")
    req(mod.smoke_problems(good_rec, sm_case, pkeys, statuses) == [], "smoke gate accepts a complete record")
    full = json.dumps(good)
    req(len(full) > 400, "smoke record long enough to truncate meaningfully")
    for cut in (len(full) // 4, len(full) // 2, 3 * len(full) // 4, len(full) - 20, len(full) - 1):
        z = dict(good_rec); z["stdout"] = full[:cut]
        req(mod.smoke_problems(z, sm_case, pkeys, statuses) != [], "smoke gate rejects truncation at %d" % cut)
    for label, mutate in (
        ("missing-field", lambda p: {k: v for k, v in p.items() if k != "device"}),
        ("extra-field", lambda p: dict(p, extra_field=4)),
        ("guard-lie", lambda p: dict(p, prefix_guard_ok=False)),
        ("words-vs-hex-mismatch", lambda p: dict(p, out_words=[x ^ 1 for x in p["out_words"]])),
        ("wrong-status", lambda p: dict(p, status="library_failed")),
        ("short-hex", lambda p: dict(p, out_hex=p["out_hex"][:-2])),
        ("bad-identity", lambda p: dict(p, case="not_a_case")),
    ):
        z = dict(good_rec); z["stdout"] = json.dumps(mutate(json.loads(full)))
        req(mod.smoke_problems(z, sm_case, pkeys, statuses) != [], "smoke gate rejects " + label)
    for label, patch in (("nonzero-exit", {"exit": 1}), ("timeout", {"timed_out": True, "exit": None}),
                         ("os-exception", {"exception": "OSError", "exit": None}), ("empty-stdout", {"stdout": ""})):
        z = dict(good_rec); z.update(patch)
        req(mod.smoke_problems(z, sm_case, pkeys, statuses) != [], "smoke gate rejects " + label)
    envj = json.loads(json.dumps(env))
    runs = [synthetic_run(mod, rid, cs, envj, json.loads(json.dumps(rm))) for rid in RUNS]
    for idx, rid in enumerate(RUNS):
        rm2 = dict(runs[idx]["run_manifest"]); rm2["run_id"] = rid
        runs[idx]["run_manifest"] = rm2
    out = [validate_run(rid, objs) for rid, objs in zip(RUNS, runs)]
    compare_runs([o[0] for o in out], [o[1] for o in out])
    normal_case = next(x["case"] for x in cs if x.get("expect_status") != "abort" and x["family"] != "a07_descriptor")
    must_fail("receipt-nonzero-exit", lambda: validate_run(RUNS[0], {**runs[0], "cases": {**runs[0]["cases"], normal_case: {**runs[0]["cases"][normal_case], "exit": 1}}}))
    bad = json.loads(json.dumps(runs[0])); p = json.loads(bad["cases"][normal_case]["stdout"]); del p["device"]
    bad["cases"][normal_case]["stdout"] = json.dumps(p)
    must_fail("payload-missing-key", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[0])); p = json.loads(bad["cases"][normal_case]["stdout"])
    p["prefix_guard_ok"] = False
    bad["cases"][normal_case]["stdout"] = json.dumps(p)
    must_fail("guard-flag-lie", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[0])); z = bad["cases"][normal_case]
    z["stdout"] = z["stdout"][:len(z["stdout"]) // 2]
    must_fail("case-stdout-truncated", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[1])); p = json.loads(bad["cases"][normal_case]["stdout"])
    p["out_words"] = [p["out_words"][0] ^ 1] + p["out_words"][1:]
    b = bytes.fromhex(p["out_hex"])
    p["out_hex"] = (b[:16] + b"".join(w.to_bytes(4, "little") for w in p["out_words"]) + b[80:]).hex()
    bad["cases"][normal_case]["stdout"] = json.dumps(p)
    out2 = [validate_run(RUNS[0], runs[0]), validate_run(RUNS[1], bad)]
    must_fail("cross-run-payload-mismatch", lambda: compare_runs([o[0] for o in out2], [o[1] for o in out2]))
    prov2 = [out[0][0], dict(out[1][0])]
    prov2[1]["git_revision"] = "0" * 40
    must_fail("cross-run-provenance-mismatch", lambda: compare_runs(prov2, [o[1] for o in out]))
    abort_case = next(x for x in cs if x.get("expect_status") == "abort")
    bad = json.loads(json.dumps(runs[0]))
    bad["cases"][abort_case["case"]]["exit"] = 0
    bad["cases"][abort_case["case"]]["stdout"] = "not json"
    must_fail("abort-case-with-zero-exit", lambda: validate_run(RUNS[0], bad))
    print("PASS selftest: schema gates and the pre-capture smoke gate satisfiable in every tree state; tamper checks bite")

# ---------------------------------------------------------------- gate-sequence state machine

def fixture_receipt(root, argv, timeout, stdout, exit_code=0):
    return {"argv": [str(x) for x in argv], "cwd": str(root), "timeout_seconds": timeout,
            "started_utc": "2026-08-29T00:00:00+00:00", "timed_out": False, "exit": exit_code,
            "stdout": stdout, "stderr": "", "exception": None}

def write_json(p, o):
    p.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")

def sub(root, args, timeout=120):
    return subprocess.run(["python3", "-B"] + args, cwd=root, text=True, capture_output=True, timeout=timeout)

def build_fixture(root, state, mod, cs, env, rm_by_rid):
    root.mkdir(parents=True)
    for rel in AUTH + DOC_FILES:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((HERE / rel).read_bytes())
    for rel in (HERE / "provenance").rglob("*"):
        if rel.is_file():
            dst = root / rel.relative_to(HERE)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(rel.read_bytes())
    if state == "PRE_GPU":
        return
    fixture_env = json.loads(json.dumps(env))
    for key in ("sw_vers", "xcrun_version", "device_model"):
        fixture_env[key]["cwd"] = str(root)
    runs_needed = RUNS if state == "RUN02_PRESENT" else RUNS[:1]
    for rid in runs_needed:
        d = root / "raw" / rid
        d.mkdir(parents=True)
        write_json(d / "00_inputs.json", fixture_env)
        work_dir = root / "work" / rid
        write_json(d / "01_host_build.json", fixture_receipt(root, ["xcrun", "clang", "-fobjc-arc", "-o", work_dir / "probe",
                   root / "harness/probe.m", "-framework", "Metal", "-framework", "Foundation"], 120, ""))
        write_json(d / "run_manifest.json", dict(rm_by_rid, run_id=rid))
        for c in cs:
            probe = work_dir / "probe"
            argv = [probe, "--family", c["family"], "--case", c["case"], "--source", root / c["kernel_file"],
                    "--args", json.dumps(c["args"], sort_keys=True)]
            if c.get("expect_status") == "abort":
                write_json(d / f"case_{c['case']}.json", fixture_receipt(root, argv, c.get("timeout_seconds", 60), "", exit_code=-6))
            elif c["family"] == "a07_descriptor":
                write_json(d / f"case_{c['case']}.json", fixture_receipt(root, argv, c.get("timeout_seconds", 60), json.dumps(ok_descriptor_payload(c))))
            else:
                write_json(d / f"case_{c['case']}.json", fixture_receipt(root, argv, c.get("timeout_seconds", 60), json.dumps(ok_payload(c))))

def run_state_gates(root, state):
    steps = []
    def step(label, args, timeout=120):
        r = sub(root, args, timeout)
        steps.append((label, r.returncode, (r.stdout + r.stderr)[-4000:]))
        req(r.returncode == 0, "seqtest %s: %s exited %d: %s" % (state, label, r.returncode, (r.stdout + r.stderr)[-2000:]))
    if state == "PRE_GPU":
        step("manifest --write", ["make_manifest.py", "--write"])
        step("selftest", ["verify.py", "--selftest"])
        step("manifest --check", ["make_manifest.py", "--check"])
        step("preflight", ["verify.py", "--preflight"])
    elif state == "RUN01_PRESENT":
        step("manifest --write", ["make_manifest.py", "--write"])
        step("selftest", ["verify.py", "--selftest"])
        step("manifest --check", ["make_manifest.py", "--check"])
        step("between-runs", ["verify.py", "--between-runs"])
    elif state == "RUN02_PRESENT":
        step("analysis.py --write", ["analysis.py", "--run-a", RUNS[0], "--run-b", RUNS[1], "--write"])
        step("manifest --write", ["make_manifest.py", "--write"])
        step("selftest", ["verify.py", "--selftest"])
        step("manifest --check", ["make_manifest.py", "--check"])
        step("captured", ["verify.py", "--captured"])
    else:
        raise ValueError(state)
    return steps

def seqtest():
    contract = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    cs = contract["cases"]
    mod = load_runner()
    env = mod.env_record()
    req(mod.env_problems(env) == [], "seqtest environment record")
    rm = mod.run_manifest_record(RUNS[0], [c["case"] for c in cs])
    seqroot = HERE / "work" / "seqtest"
    if seqroot.exists():
        shutil.rmtree(seqroot)
    seqroot.mkdir(parents=True)
    report = {}
    try:
        for state, dirname in (("PRE_GPU", "pre_gpu"), ("RUN01_PRESENT", "run01_present"), ("RUN02_PRESENT", "run02_present")):
            root = seqroot / dirname
            build_fixture(root, state, mod, cs, env, rm)
            report[state] = run_state_gates(root, state)
    finally:
        shutil.rmtree(seqroot, ignore_errors=True)
    work_clean()
    for state in ("PRE_GPU", "RUN01_PRESENT", "RUN02_PRESENT"):
        req(state in report and len(report[state]) >= 3, "seqtest coverage " + state)
    print("PASS seqtest: PRE_GPU/RUN01_PRESENT/RUN02_PRESENT gate sequences are each runnable and satisfiable "
          "(%d/%d/%d real subprocess gate checks)" % tuple(len(report[s]) for s in ("PRE_GPU", "RUN01_PRESENT", "RUN02_PRESENT")))

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--seqtest", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--captured", action="store_true")
    a = ap.parse_args()
    if a.preflight:
        static()
        req(not (HERE / "raw").exists(), "PRE_GPU tree must have no raw")
        work_clean()
        print("PASS PRE_GPU contract; no GPU capture")
    elif a.selftest:
        capture = (HERE / "raw").exists()
        static(capture=capture)
        work_clean()
        selftest()
    elif a.seqtest:
        capture = (HERE / "raw").exists()
        static(capture=capture)
        work_clean()
        seqtest()
    elif a.between_runs:
        static(capture=True)
        work_clean()
        captured((RUNS[0],))
        print("PASS run01 contract; run02 may begin")
    else:
        static(capture=True, need_analysis=True)
        work_clean()
        captured(RUNS)
        print("PASS captured public-Metal owned-resource contract")

if __name__ == "__main__":
    main()
