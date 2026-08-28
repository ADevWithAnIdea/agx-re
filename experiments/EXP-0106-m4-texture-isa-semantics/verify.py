#!/usr/bin/env python3
"""Fail-closed static, post-capture, self-test, and gate-sequence verifier
for EXP-0106. Architecture independently re-authored from the proven
EXP-0079/EXP-0083/EXP-0095 --selftest/--seqtest pattern (this project's own
prior work, not Apple's):

1. --selftest is STATE-AGNOSTIC: detects the tree's actual capture state
   (PRE_GPU vs raw/ present) and verifies the closed-root/contract-static
   invariants for THAT state, then runs a synthetic in-process schema
   self-test that never reads the real raw/ tree.
2. --seqtest is a gate-sequence STATE MACHINE: builds three isolated
   fixture trees (PRE_GPU / RUN01_PRESENT / RUN02_PRESENT) and actually
   subprocess-invokes every contracted gate for that state.
3. The pre-capture NON-RECORDED SMOKE GATE (run.py's smoke_gate/
   smoke_problems) is schema-tested here against tamper classes.
4. NO NONDETERMINISTIC FIELD enters any byte-compared record: every
   receipt/payload validated here is checked field-by-field against a closed
   key set, and cross-run comparison requires the full normalized record to
   be byte-identical between run01 and run02.
5. Selftest fixtures are built from RECORDED REALITY: driven by
   CAPTURE_CONTRACT.json's own frozen case list (loaded live).

Three case families, three JSON payload schemas: DISPATCH_KEYS (compute
dispatch: b02/b04/b05/b06/b07/b08/b09), DESCRIPTOR_KEYS (b_descriptor:
TEX-23/25 texture-creation boundary), QUERY_KEYS (b03_query:
supportsTextureSampleCount). A dispatch case's contracted expect_status may
be "ok" (normal), "abort" (SIGABRT at descriptor validation -- N/A here,
reserved for b_descriptor/b03 families... actually abort applies to
b_descriptor only), "library_failed", or "pipeline_rejected" (both
CONTRACTED, non-harness-fault, exit-0 outcomes distinguished by the JSON
payload's own "status" field).
"""
import argparse, datetime, hashlib, importlib.util, json, re, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT_NAMES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md", "RESULTS.md", "PROGRESS.md",
              "kernels", "harness", "analysis", "run.py", "gen_contract.py", "make_manifest.py", "verify.py",
              "manifest.json"}
RUNS = ("m4-20260830-run01", "m4-20260830-run02")
DISPATCH_KEYS = {"schema", "family", "case", "status", "library_ok", "library_error", "pipelines",
                  "resource_ok", "resource_error", "command_buffer_status", "command_buffer_error",
                  "device", "machine", "os", "prefix_guard_ok", "suffix_guard_ok", "out_hex", "out_words"}
DESCRIPTOR_KEYS = {"schema", "family", "case", "type", "width", "height", "depth", "arrayLength",
                    "sampleCount", "actualSampleCount", "texture_ok", "device"}
QUERY_KEYS = {"schema", "family", "case", "sample_count", "supported", "device"}
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit", "stdout", "stderr", "exception"}
INPUT_KEYS = {"schema", "git_revision", "git_dirty", "authored_sha256", "sw_vers", "xcrun_version",
              "device_model", "machine", "boundary"}
BOUNDARY = "public Metal only; owned in-bounds resources; no binary/archive/BO inspection"

def fail(s):
    raise SystemExit("FAIL " + s)

def req(v, s):
    if not v:
        fail(s)

def sha(p):
    return hashlib.sha256((HERE / p).read_bytes()).hexdigest()

def regular(p):
    return p.is_file() and not p.is_symlink()

def contract():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())

def cases():
    return contract()["cases"]

def auth_files():
    return tuple(contract()["blob_sha256"].keys()) + ("CAPTURE_CONTRACT.json",)

def manifest_expected(capture):
    paths = tuple(sorted(str(p.relative_to(HERE)) for p in HERE.rglob("*")
                         if p.is_file() and not p.is_symlink() and p.name != "manifest.json")) if capture else None
    if paths is None:
        auth = auth_files()
        doc = ("README.md", "RESULTS.md", "PROGRESS.md")
        analysis_dir = tuple(sorted(str(p.relative_to(HERE)) for p in (HERE / "analysis").rglob("*") if p.is_file()))
        paths = tuple(sorted(set(auth) | set(doc) | set(analysis_dir)))
    return {"schema": 1, "state": "CAPTURED" if capture else "PRE_GPU",
            "artifacts": [{"path": p, "bytes": (HERE / p).stat().st_size, "sha256": sha(p)} for p in paths]}

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

def outcome_receipt(z, argv, cwd, timeout, expect, label):
    """A case receipt for a non-'ok' contracted expect_status: either a
    negative-signal process abort (expect=='abort') or a clean exit 0 with a
    JSON payload whose own status equals expect (library_failed/pipeline_rejected)."""
    req(set(z) == REC_KEYS, "receipt key set " + label)
    req(z["argv"] == [str(x) for x in argv] and z["cwd"] == str(cwd) and z["timeout_seconds"] == timeout
        and z["timed_out"] is False and z["exception"] is None, label)
    if expect == "abort":
        req(isinstance(z["exit"], int) and z["exit"] < 0, label + " expected negative-signal exit")
        return None
    req(z["exit"] == 0, label + " expected clean exit for " + expect)
    try:
        p = json.loads(z["stdout"])
    except json.JSONDecodeError:
        fail("case stdout not one JSON object " + label)
    req(set(p) == DISPATCH_KEYS, "payload key set " + label)
    req(p["status"] == expect, "payload status must be " + expect + " " + label)
    return p

def check_inputs(i, label):
    req(set(i) == INPUT_KEYS, "inputs key set " + label)
    req(i["schema"] == 1 and i["machine"] == "arm64" and isinstance(i["git_dirty"], bool)
        and i["boundary"] == BOUNDARY and set(i["authored_sha256"]) == set(auth_files()), "inputs schema " + label)

def check_inputs_bindings(i, label):
    for path, want in i["authored_sha256"].items():
        req(sha(path) == want, "post-capture source binding " + label + " " + path)

def provenance_row(i):
    return {"git_revision": i["git_revision"], "authored_sha256": i["authored_sha256"],
            "sw_vers_output": {"stdout": i["sw_vers"].get("stdout"), "stderr": i["sw_vers"].get("stderr")},
            "xcrun_version_output": {"stdout": i["xcrun_version"].get("stdout"), "stderr": i["xcrun_version"].get("stderr")},
            "device_model_output": {"stdout": i["device_model"].get("stdout"), "stderr": i["device_model"].get("stderr")}}

def dispatch_payload(p, c, label):
    req(set(p) == DISPATCH_KEYS, "payload key set " + label)
    req(p["family"] == c["family"] and p["case"] == c["case"], "payload identity " + label)
    req(p["status"] == "ok", "payload status must be ok " + label)
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
    a = c["args"]
    req(p["type"] == a.get("type", "2d") and p["width"] == a.get("width", 4) and p["height"] == a.get("height", 4)
        and p["depth"] == a.get("depth", 1) and p["arrayLength"] == a.get("arrayLength", 1)
        and p["sampleCount"] == a.get("sampleCount", 1), "descriptor echo " + label)
    req(p["texture_ok"] is True, "descriptor texture_ok " + label)
    req(p["device"] == "Apple M4", "descriptor device " + label)

def query_payload(p, c, label):
    req(set(p) == QUERY_KEYS, "query payload key set " + label)
    req(p["family"] == c["family"] and p["case"] == c["case"], "query payload identity " + label)
    req(p["sample_count"] == c["args"]["sample_count"], "query echo " + label)
    req(isinstance(p["supported"], bool), "query supported type " + label)
    req(p["device"] == "Apple M4", "query device " + label)

def family_kind(fam):
    if fam == "b_descriptor":
        return "descriptor"
    if fam == "b03_query":
        return "query"
    return "dispatch"

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
    req(rm["schema"] == 1 and rm["run_id"] == rid and rm["cases"] == [c["case"] for c in cs]
        and rm["fresh_process_per_case"] is True and rm["runner_sha256"] == i["authored_sha256"]["run.py"]
        and rm["harness_sha256"] == i["authored_sha256"]["harness/probe.m"]
        and rm["authored_sha256"] == i["authored_sha256"]
        and rm["contract_sha256"] == i["authored_sha256"]["CAPTURE_CONTRACT.json"], "run manifest " + rid)
    rows = []
    for c in cs:
        z = objs["cases"][c["case"]]
        kind = family_kind(c["family"])
        argv = [probe, "--family", c["family"], "--case", c["case"]]
        if c.get("kernel_file"):
            argv += ["--source", HERE / c["kernel_file"]]
        argv += ["--args", json.dumps(c["args"], sort_keys=True)]
        expect = c.get("expect_status", "ok")
        timeout = c.get("timeout_seconds", 60)
        if expect != "ok":
            p = outcome_receipt(z, argv, HERE, timeout, expect, "case process " + c["case"])
            rows.append({"case": c["case"], "expect": expect, "payload": p})
            continue
        receipt(z, argv, HERE, timeout, "case process " + c["case"])
        try:
            p = json.loads(z["stdout"])
        except json.JSONDecodeError:
            fail("case stdout not one JSON object " + c["case"])
        if kind == "descriptor":
            descriptor_payload(p, c, c["case"])
        elif kind == "query":
            query_payload(p, c, c["case"])
        else:
            dispatch_payload(p, c, c["case"])
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
    auth = auth_files()
    for p in auth + ("README.md", "RESULTS.md", "PROGRESS.md", "manifest.json"):
        req(regular(HERE / p), "regular " + p)
    kd = HERE / "kernels"
    req(kd.is_dir() and not kd.is_symlink() and all(regular(x) for x in kd.iterdir()), "closed kernels")
    hd = HERE / "harness"
    req(hd.is_dir() and not hd.is_symlink() and {p.name for p in hd.iterdir()} == {"probe.m"} and all(regular(x) for x in hd.iterdir()), "closed harness")
    req((HERE / "analysis").is_dir(), "analysis dir present")

    c = contract()
    req(c["state"] == "PRE_GPU" and c["experiment"] == "EXP-0106-m4-texture-isa-semantics", "contract identity")
    cs = c["cases"]
    ids = [x["case"] for x in cs]
    req(len(ids) == len(set(ids)), "unique case ids")
    for x in cs:
        req(set(x) == {"case", "family", "kernel_file", "args", "n_outputs", "expected_out_words",
                       "expect_status", "timeout_seconds", "rule_note"}, "case record keys " + x["case"])
        req(x["kernel_file"] is None or x["kernel_file"] in (a for a in auth if a.endswith(".metal")), "kernel file " + x["case"])
        req(isinstance(x["expected_out_words"], list) and len(x["expected_out_words"]) == 16
            and all(v is None or (type(v) is int and 0 <= v < 2 ** 32) for v in x["expected_out_words"]), "expected words grammar " + x["case"])
        req(0 <= x["n_outputs"] <= 16, "n_outputs range " + x["case"])
        req(x["expect_status"] in ("ok", "abort", "library_failed", "pipeline_rejected"), "expect_status " + x["case"])
        req(isinstance(x["rule_note"], str) and x["rule_note"], "rule_note " + x["case"])
        req(isinstance(x["timeout_seconds"], int) and x["timeout_seconds"] > 0, "timeout " + x["case"])
    req(set(c["blob_sha256"]) == set(auth) - {"CAPTURE_CONTRACT.json"}, "contract blob binding set")
    for p, h in c["blob_sha256"].items():
        req(sha(p) == h, "contract blob binding " + p)
    req(c["boundary"] == BOUNDARY, "boundary")
    req(c["capture"]["runs"] == list(RUNS), "capture runs")
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
    spec = importlib.util.spec_from_file_location("exp0106_runner", HERE / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def synthetic_receipt(argv, timeout, stdout, exit_code=0):
    return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
            "started_utc": "2026-08-30T00:00:00+00:00", "timed_out": False, "exit": exit_code,
            "stdout": stdout, "stderr": "", "exception": None}

def ok_dispatch_payload(c):
    words = [(v if v is not None else 0xEEEEEEEE) for v in c["expected_out_words"]]
    b = b"\x5a" * 16 + b"".join(w.to_bytes(4, "little") for w in words) + b"\xa5" * 16
    return {"schema": 1, "family": c["family"], "case": c["case"], "status": "ok", "library_ok": True,
            "library_error": "", "pipelines": [], "resource_ok": True, "resource_error": "",
            "command_buffer_status": 4, "command_buffer_error": "", "device": "Apple M4", "machine": "arm64",
            "os": "Version 26.6.2 (Build 25G82)", "prefix_guard_ok": True, "suffix_guard_ok": True,
            "out_hex": b.hex(), "out_words": words}

def outcome_dispatch_payload(c, status):
    return {"schema": 1, "family": c["family"], "case": c["case"], "status": status, "library_ok": status != "library_failed",
            "library_error": "", "pipelines": [], "resource_ok": True, "resource_error": "",
            "command_buffer_status": 0, "command_buffer_error": "", "device": "Apple M4", "machine": "arm64",
            "os": "Version 26.6.2 (Build 25G82)", "prefix_guard_ok": True, "suffix_guard_ok": True,
            "out_hex": ("5a" * 16 + "ee" * 64 + "a5" * 16), "out_words": [0xEEEEEEEE] * 16}

def ok_descriptor_payload(c):
    a = c["args"]
    return {"schema": 1, "family": c["family"], "case": c["case"], "type": a.get("type", "2d"),
            "width": a.get("width", 4), "height": a.get("height", 4), "depth": a.get("depth", 1),
            "arrayLength": a.get("arrayLength", 1), "sampleCount": a.get("sampleCount", 1),
            "actualSampleCount": a.get("sampleCount", 1), "texture_ok": True, "device": "Apple M4"}

def ok_query_payload(c):
    return {"schema": 1, "family": c["family"], "case": c["case"], "sample_count": c["args"]["sample_count"],
            "supported": c["args"]["sample_count"] in (1, 2, 4), "device": "Apple M4"}

def synthetic_run(mod, rid, contract_cases, env, run_manifest):
    cases_map = {}
    for c in contract_cases:
        probe = HERE / "work" / rid / "probe"
        argv = [probe, "--family", c["family"], "--case", c["case"]]
        if c.get("kernel_file"):
            argv += ["--source", HERE / c["kernel_file"]]
        argv += ["--args", json.dumps(c["args"], sort_keys=True)]
        expect = c.get("expect_status", "ok")
        timeout = c.get("timeout_seconds", 60)
        if expect == "abort":
            cases_map[c["case"]] = synthetic_receipt(argv, timeout, "", exit_code=-6)
        elif expect in ("library_failed", "pipeline_rejected"):
            cases_map[c["case"]] = synthetic_receipt(argv, timeout, json.dumps(outcome_dispatch_payload(c, expect)))
        elif family_kind(c["family"]) == "descriptor":
            cases_map[c["case"]] = synthetic_receipt(argv, timeout, json.dumps(ok_descriptor_payload(c)))
        elif family_kind(c["family"]) == "query":
            cases_map[c["case"]] = synthetic_receipt(argv, timeout, json.dumps(ok_query_payload(c)))
        else:
            cases_map[c["case"]] = synthetic_receipt(argv, timeout, json.dumps(ok_dispatch_payload(c)))
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
    c = contract()
    cs = c["cases"]
    req([x["case"] for x in cs] == [x["case"] for x in cases()], "selftest case order/identity vs contract")
    mod = load_runner()
    r = mod.rec(["/usr/bin/true"], 5)
    req(r["exit"] == 0 and r["exception"] is None and set(r) == REC_KEYS, "run.py receipt key set")
    env = mod.env_record()
    check_inputs(env, "selftest")
    for z in (env["sw_vers"], env["xcrun_version"], env["device_model"]):
        req(z["exit"] == 0 and z["timed_out"] is False and z["exception"] is None, "selftest environment command")
    req(mod.env_problems(env) == [], "run.py environment validator accepts a clean record")
    rm = mod.run_manifest_record(RUNS[0], [x["case"] for x in cs])
    for x in cs[:3] + cs[-2:]:
        argv = mod.case_argv(HERE / "work" / RUNS[0], x)
        expect_argv = [HERE / "work" / RUNS[0] / "probe", "--family", x["family"], "--case", x["case"]]
        if x.get("kernel_file"):
            expect_argv += ["--source", HERE / x["kernel_file"]]
        expect_argv += ["--args", json.dumps(x["args"], sort_keys=True)]
        req(argv == expect_argv, "case argv template " + x["case"])
    smoke_case_name = c["capture"]["pre_capture_smoke"]["case"]
    sm_case = next(x for x in cs if x["case"] == smoke_case_name)
    req(sm_case.get("expect_status", "ok") == "ok", "smoke case must be a normal ok-status case")
    good = ok_dispatch_payload(sm_case)
    sm_argv = mod.case_argv(HERE / "work" / RUNS[0], sm_case)
    good_rec = synthetic_receipt(sm_argv, mod.SMOKE_TIMEOUT, json.dumps(good) + "\n")
    req(mod.smoke_problems(good_rec, sm_case, None) == [], "smoke gate accepts a complete record")
    full = json.dumps(good)
    req(len(full) > 300, "smoke record long enough to truncate meaningfully")
    for cut in (len(full) // 4, len(full) // 2, 3 * len(full) // 4, len(full) - 20, len(full) - 1):
        z = dict(good_rec); z["stdout"] = full[:cut]
        req(mod.smoke_problems(z, sm_case, None) != [], "smoke gate rejects truncation at %d" % cut)
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
        req(mod.smoke_problems(z, sm_case, None) != [], "smoke gate rejects " + label)
    for label, patch in (("nonzero-exit", {"exit": 1}), ("timeout", {"timed_out": True, "exit": None}),
                         ("os-exception", {"exception": "OSError", "exit": None}), ("empty-stdout", {"stdout": ""})):
        z = dict(good_rec); z.update(patch)
        req(mod.smoke_problems(z, sm_case, None) != [], "smoke gate rejects " + label)
    envj = json.loads(json.dumps(env))
    runs = [synthetic_run(mod, rid, cs, envj, json.loads(json.dumps(rm))) for rid in RUNS]
    for idx, rid in enumerate(RUNS):
        rm2 = dict(runs[idx]["run_manifest"]); rm2["run_id"] = rid
        runs[idx]["run_manifest"] = rm2
    out = [validate_run(rid, objs) for rid, objs in zip(RUNS, runs)]
    compare_runs([o[0] for o in out], [o[1] for o in out])
    # Must be a dispatch case whose word 0 has NO hard expectation (None), so mutating word 0 in
    # the cross-run-mismatch fixture below trips compare_runs's byte-exact check specifically,
    # not dispatch_payload's per-word expectation check (which would fire first and mask the
    # thing this fixture exists to test).
    normal_case = next(x["case"] for x in cs if x.get("expect_status", "ok") == "ok"
                       and family_kind(x["family"]) == "dispatch" and x["expected_out_words"][0] is None)
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
    abort_case = next((x for x in cs if x.get("expect_status") == "abort"), None)
    if abort_case:
        bad = json.loads(json.dumps(runs[0]))
        bad["cases"][abort_case["case"]]["exit"] = 0
        bad["cases"][abort_case["case"]]["stdout"] = "not json"
        must_fail("abort-case-with-zero-exit", lambda: validate_run(RUNS[0], bad))
    print("PASS selftest: schema gates and the pre-capture smoke gate satisfiable in every tree state; tamper checks bite")

# ---------------------------------------------------------------- gate-sequence state machine

def fixture_receipt(root, argv, timeout, stdout, exit_code=0):
    return {"argv": [str(x) for x in argv], "cwd": str(root), "timeout_seconds": timeout,
            "started_utc": "2026-08-30T00:00:00+00:00", "timed_out": False, "exit": exit_code,
            "stdout": stdout, "stderr": "", "exception": None}

def write_json(p, o):
    p.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")

def sub(root, args, timeout=180):
    return subprocess.run(["python3", "-B"] + args, cwd=root, text=True, capture_output=True, timeout=timeout)

def build_fixture(root, state, mod, cs, env, rm_by_rid):
    root.mkdir(parents=True)
    for rel in auth_files() + ("README.md", "RESULTS.md", "PROGRESS.md"):
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((HERE / rel).read_bytes())
    for rel in (HERE / "analysis").rglob("*"):
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
            argv = [probe, "--family", c["family"], "--case", c["case"]]
            if c.get("kernel_file"):
                argv += ["--source", root / c["kernel_file"]]
            argv += ["--args", json.dumps(c["args"], sort_keys=True)]
            expect = c.get("expect_status", "ok")
            timeout = c.get("timeout_seconds", 60)
            if expect == "abort":
                write_json(d / f"case_{c['case']}.json", fixture_receipt(root, argv, timeout, "", exit_code=-6))
            elif expect in ("library_failed", "pipeline_rejected"):
                write_json(d / f"case_{c['case']}.json", fixture_receipt(root, argv, timeout, json.dumps(outcome_dispatch_payload(c, expect))))
            elif family_kind(c["family"]) == "descriptor":
                write_json(d / f"case_{c['case']}.json", fixture_receipt(root, argv, timeout, json.dumps(ok_descriptor_payload(c))))
            elif family_kind(c["family"]) == "query":
                write_json(d / f"case_{c['case']}.json", fixture_receipt(root, argv, timeout, json.dumps(ok_query_payload(c))))
            else:
                write_json(d / f"case_{c['case']}.json", fixture_receipt(root, argv, timeout, json.dumps(ok_dispatch_payload(c))))

def run_state_gates(root, state):
    steps = []
    def step(label, args, timeout=180):
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
        step("analysis.py --write", ["analysis/analysis.py", "--run-a", RUNS[0], "--run-b", RUNS[1], "--write"])
        step("manifest --write", ["make_manifest.py", "--write"])
        step("selftest", ["verify.py", "--selftest"])
        step("manifest --check", ["make_manifest.py", "--check"])
        step("captured", ["verify.py", "--captured"])
    else:
        raise ValueError(state)
    return steps

def seqtest():
    c = contract()
    cs = c["cases"]
    mod = load_runner()
    env = mod.env_record()
    req(mod.env_problems(env) == [], "seqtest environment record")
    rm = mod.run_manifest_record(RUNS[0], [x["case"] for x in cs])
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
