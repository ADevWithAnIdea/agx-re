#!/usr/bin/env python3
"""Fail-closed static, post-capture, and self-test verifier for EXP-0072.

--selftest proves every schema gate is satisfiable BEFORE any GPU work, using
synthetic in-memory records and live calls into run.py's own record builders
(lesson from quarantined EXP-0073, whose frozen verifier contained a
contradictory receipt schema that surfaced only after a clean capture).
"""
import argparse, datetime, hashlib, importlib.util, json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md", "RESULTS.md", "PROGRESS.md", "kernels",
        "harness", "run.py", "analysis.py", "make_manifest.py", "verify.py", "manifest.json"}
AUTH = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "kernels/format_batch2.metal",
        "harness/probe.m", "run.py", "analysis.py", "make_manifest.py", "verify.py")
RUNS = ("m4-20260827-run01", "m4-20260827-run02")
# Frozen per-case grammar (independent copy; must equal CAPTURE_CONTRACT.json):
# id -> (MTLPixelFormat, texel bytes, reader)
CASES = (
    ("r8unorm_p100", "R8Unorm", 1, "float"), ("r8unorm_zero", "R8Unorm", 1, "float"),
    ("r8unorm_p050", "R8Unorm", 1, "float"), ("rg8unorm_p100_p050", "RG8Unorm", 2, "float"),
    ("rg8unorm_zero_p100", "RG8Unorm", 2, "float"), ("r8snorm_p100", "R8Snorm", 1, "float"),
    ("r8snorm_zero", "R8Snorm", 1, "float"), ("r8snorm_p050", "R8Snorm", 1, "float"),
    ("r8snorm_m100", "R8Snorm", 1, "float"), ("rg8snorm_p100_p050", "RG8Snorm", 2, "float"),
    ("rg8snorm_m100_zero", "RG8Snorm", 2, "float"), ("rgba8snorm_pack", "RGBA8Snorm", 4, "float"),
    ("r16float_exact", "R16Float", 2, "float"), ("r16float_mid", "R16Float", 2, "float"),
    ("r16float_third", "R16Float", 2, "float"), ("rg16float_exact_mid", "RG16Float", 4, "float"),
    ("rg16float_third_third", "RG16Float", 4, "float"), ("r32float_exact", "R32Float", 4, "float"),
    ("r32float_mid", "R32Float", 4, "float"), ("r32float_third", "R32Float", 4, "float"),
    ("rg11b10float_exact", "RG11B10Float", 4, "float"), ("rg11b10float_mid", "RG11B10Float", 4, "float"),
    ("rgb9e5float_exact", "RGB9E5Float", 4, "float"), ("rgb9e5float_mid", "RGB9E5Float", 4, "float"),
    ("r16sint_1", "R16Sint", 2, "int"), ("r16sint_2", "R16Sint", 2, "int"), ("r16sint_3855", "R16Sint", 2, "int"),
    ("r16uint_1", "R16Uint", 2, "uint"), ("r16uint_2", "R16Uint", 2, "uint"), ("r16uint_3855", "R16Uint", 2, "uint"),
    ("r32sint_1", "R32Sint", 4, "int"), ("r32sint_2", "R32Sint", 4, "int"), ("r32sint_3855", "R32Sint", 4, "int"),
    ("rgba16uint_pack", "RGBA16Uint", 8, "uint"),
)
PRISTINE_BACKING = "5a" * 64 + "00" * 256 + "a5" * 64
PRISTINE_RESULT = "5a" * 64 + "00" * 16 + "a5" * 64
PAYLOAD_KEYS = {"case", "format", "texel_bytes", "reader", "usage_flags", "storage_mode",
                "fast_math_enabled", "status", "library_ok", "library_error", "store_pipeline_ok",
                "store_pipeline_error", "read_pipeline_ok", "read_pipeline_error", "texture_ok",
                "texture_error", "command_buffer_status", "command_buffer_error", "device", "machine",
                "os", "physical_texel_hex", "backing_hex", "result_hex", "read_words_le",
                "backing_prefix_guard", "backing_suffix_guard", "result_prefix_guard", "result_suffix_guard"}
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit", "stdout", "stderr", "exception"}
INPUT_KEYS = {"schema", "git_revision", "git_dirty", "authored_sha256", "sw_vers", "xcrun_version",
              "device_model", "machine", "boundary"}
REJECT_FLAGS = {"store_pipeline_rejected": (True, False, False, False),
                "read_pipeline_rejected": (True, True, False, False),
                "texture_rejected": (True, True, True, False)}
RUN_MANIFEST_KEYS = ["schema", "run_id", "cases", "fresh_process_per_case", "runner_sha256",
                     "harness_sha256", "kernel_sha256", "contract_sha256"]

def fail(s):
    raise SystemExit("FAIL " + s)

def req(v, s):
    if not v:
        fail(s)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def regular(p):
    return p.is_file() and not p.is_symlink()

def manifest_expected(capture):
    paths = tuple(sorted(str(p.relative_to(HERE)) for p in HERE.rglob("*")
                         if p.is_file() and not p.is_symlink() and p.name != "manifest.json")) if capture else AUTH + ("README.md", "RESULTS.md", "PROGRESS.md")
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

def check_inputs(i, label):
    req(set(i) == INPUT_KEYS, "inputs key set " + label)
    req(i["schema"] == 1 and i["machine"] == "arm64" and isinstance(i["git_dirty"], bool)
        and i["boundary"] == "public Metal only; owned in-bounds buffers; no binary/archive/BO inspection"
        and set(i["authored_sha256"]) == set(AUTH), "inputs schema " + label)

def check_inputs_bindings(i, label):
    for path, want in i["authored_sha256"].items():
        req(sha(HERE / path) == want, "post-capture source binding " + label + " " + path)

def provenance_row(i):
    return {"git_revision": i["git_revision"], "authored_sha256": i["authored_sha256"],
            "sw_vers_output": {"stdout": i["sw_vers"].get("stdout"), "stderr": i["sw_vers"].get("stderr")},
            "xcrun_version_output": {"stdout": i["xcrun_version"].get("stdout"), "stderr": i["xcrun_version"].get("stderr")},
            "device_model_output": {"stdout": i["device_model"].get("stdout"), "stderr": i["device_model"].get("stderr")}}

def payload(p, cid, fmt, nbits, reader, label):
    req(set(p) == PAYLOAD_KEYS, "payload key set " + label)
    req(p["case"] == cid and p["format"] == fmt and p["texel_bytes"] == nbits and p["reader"] == reader, "payload identity " + label)
    req(p["usage_flags"] == "MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead"
        and p["storage_mode"] == "MTLStorageModeShared" and p["fast_math_enabled"] is False, "usage record " + label)
    req(p["status"] in ("ok",) + tuple(REJECT_FLAGS) + ("command_buffer_error",), "status " + label)
    req(p["library_ok"] is True and p["device"] == "Apple M4" and p["machine"] == "arm64"
        and isinstance(p["os"], str) and p["os"], "device identity " + label)
    st = p["status"]
    if st in REJECT_FLAGS:
        req((p["library_ok"], p["store_pipeline_ok"], p["read_pipeline_ok"], p["texture_ok"]) == REJECT_FLAGS[st],
            "rejection flags " + label)
        req(p["command_buffer_status"] == 0 and p["command_buffer_error"] == "", "rejection cb " + label)
        req(p["backing_hex"] == PRISTINE_BACKING and p["result_hex"] == PRISTINE_RESULT
            and p["physical_texel_hex"] == "00" * nbits and p["read_words_le"] == [0, 0, 0, 0], "pristine backing " + label)
        req(all(p[x] is True for x in ("backing_prefix_guard", "backing_suffix_guard", "result_prefix_guard", "result_suffix_guard")),
            "rejection guards " + label)
        return
    req((p["library_ok"], p["store_pipeline_ok"], p["read_pipeline_ok"], p["texture_ok"]) == (True, True, True, True),
        "ok flags " + label)
    if st == "ok":
        req(p["command_buffer_status"] == 4 and p["command_buffer_error"] == "", "ok cb " + label)
    else:  # command_buffer_error: terminal error status per public MTLCommandBufferStatus
        req(p["command_buffer_status"] in (1, 2, 3, 5) and isinstance(p["command_buffer_error"], str),
            "cb error record " + label)
    req(isinstance(p["read_words_le"], list) and len(p["read_words_le"]) == 4
        and all(type(x) is int and 0 <= x < 2 ** 32 for x in p["read_words_le"]), "word grammar " + label)
    req(isinstance(p["physical_texel_hex"], str) and len(p["physical_texel_hex"]) == 2 * nbits
        and re.fullmatch(r"[0-9a-f]+", p["physical_texel_hex"]) and isinstance(p["backing_hex"], str)
        and len(p["backing_hex"]) == 768 and isinstance(p["result_hex"], str) and len(p["result_hex"]) == 288
        and re.fullmatch(r"[0-9a-f]+", p["backing_hex"] + p["result_hex"]), "hex grammar " + label)
    b = bytes.fromhex(p["backing_hex"])
    r = bytes.fromhex(p["result_hex"])
    words = [int.from_bytes(r[64 + i:68 + i], "little") for i in range(0, 16, 4)]
    req(p["physical_texel_hex"] == b[64:64 + nbits].hex() and p["read_words_le"] == words, "derived texel/words " + label)
    req(p["backing_prefix_guard"] == (b[:64] == b"\x5a" * 64) and p["backing_suffix_guard"] == (b[320:] == b"\xa5" * 64)
        and p["result_prefix_guard"] == (r[:64] == b"\x5a" * 64) and p["result_suffix_guard"] == (r[80:] == b"\xa5" * 64),
        "derived guard flags " + label)
    req(all(p[x] is True for x in ("backing_prefix_guard", "backing_suffix_guard", "result_prefix_guard", "result_suffix_guard")),
        "guard mutation " + label)

def validate_run(rid, objs):
    """objs: inputs, build, run_manifest, cases: {cid: receipt} (payload inside stdout)."""
    i = objs["inputs"]
    check_inputs(i, rid)
    check_inputs_bindings(i, rid)
    receipt(i["sw_vers"], ["sw_vers"], HERE, 5, "sw_vers " + rid)
    receipt(i["xcrun_version"], ["xcrun", "--version"], HERE, 5, "xcrun " + rid)
    receipt(i["device_model"], ["sysctl", "-n", "hw.model"], HERE, 5, "hw.model " + rid)
    probe = HERE / "work" / rid / "probe"
    receipt(objs["build"], ["xcrun", "clang", "-fobjc-arc", "-o", probe, HERE / "harness/probe.m",
                            "-framework", "Metal", "-framework", "Foundation"], HERE, 120, "build " + rid)
    rm = objs["run_manifest"]
    req(rm == {"schema": 1, "run_id": rid, "cases": [x[0] for x in CASES], "fresh_process_per_case": True,
               "runner_sha256": i["authored_sha256"]["run.py"],
               "harness_sha256": i["authored_sha256"]["harness/probe.m"],
               "kernel_sha256": i["authored_sha256"]["kernels/format_batch2.metal"],
               "contract_sha256": i["authored_sha256"]["CAPTURE_CONTRACT.json"]}, "run manifest " + rid)
    rows = []
    for cid, fmt, nbits, reader in CASES:
        z = objs["cases"][cid]
        receipt(z, [probe, "--source", HERE / "kernels/format_batch2.metal", "--case", cid,
                    "--format", fmt, "--texel-bytes", nbits, "--reader", reader], HERE, 300, "case process " + cid)
        try:
            p = json.loads(z["stdout"])
        except json.JSONDecodeError:
            fail("case stdout not one JSON object " + cid)
        payload(p, cid, fmt, nbits, reader, cid)
        rows.append(p)
    return provenance_row(i), rows

def compare_runs(provenance, rows):
    if len(provenance) == 2:
        req(provenance[0] == provenance[1], "cross-run revision/authored/environment provenance")
        req(rows[0] == rows[1], "byte-exact repeat")

def load_run(rid):
    d = HERE / "raw" / rid
    names = {"00_inputs.json", "01_host_build.json", "run_manifest.json"} | {f"case_{x[0]}.json" for x in CASES}
    req(d.is_dir() and not d.is_symlink() and {p.name for p in d.iterdir()} == names and all(regular(p) for p in d.iterdir()), "closed raw " + rid)
    return {"inputs": json.loads((d / "00_inputs.json").read_text()),
            "build": json.loads((d / "01_host_build.json").read_text()),
            "run_manifest": json.loads((d / "run_manifest.json").read_text()),
            "cases": {cid: json.loads((d / f"case_{cid}.json").read_text()) for cid, _, _, _ in CASES}}

# ---------------------------------------------------------------- static tree

def static(capture=False, need_analysis=False):
    names = {p.name for p in HERE.iterdir()}
    allowed = ROOT | ({"raw"} if capture else set()) | ({"analysis.json"} if "analysis.json" in names else set()) | ({"work"} if "work" in names else set())
    req(not HERE.is_symlink() and names == allowed, "closed root")
    if capture:
        req((HERE / "raw").is_dir() and not (HERE / "raw").is_symlink(), "raw tree present")
    if need_analysis:
        req(regular(HERE / "analysis.json"), "derived analysis")
    elif "analysis.json" in names:
        req(regular(HERE / "analysis.json"), "derived analysis")
    for p in AUTH + ("README.md", "RESULTS.md", "PROGRESS.md", "manifest.json"):
        req(regular(HERE / p), "regular " + p)
    for d, fs in (("kernels", {"format_batch2.metal"}), ("harness", {"probe.m"})):
        q = HERE / d
        req(q.is_dir() and not q.is_symlink() and {p.name for p in q.iterdir()} == fs and all(regular(x) for x in q.iterdir()), "closed " + d)
    c = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    req(c["state"] == "PRE_GPU" and tuple((x["case"], x["format"], x["texel_bytes"], x["reader"]) for x in c["cases"]) == CASES,
        "contract case matrix")
    for x in c["cases"]:
        req(set(x) == {"case", "format", "texel_bytes", "reader", "inputs", "expected_texel_hex",
                       "expected_read_words_le", "rule", "rule_note"} and isinstance(x["inputs"], list)
            and all(isinstance(v, str) and v for v in x["inputs"]) and re.fullmatch(r"[0-9a-f]+", x["expected_texel_hex"])
            and len(x["expected_texel_hex"]) == 2 * x["texel_bytes"]
            and isinstance(x["expected_read_words_le"], list) and len(x["expected_read_words_le"]) == 4
            and all(re.fullmatch(r"[0-9a-f]{8}", w) for w in x["expected_read_words_le"])
            and x["rule"] in ("a", "b", "c") and isinstance(x["rule_note"], str) and x["rule_note"], "case record " + x["case"])
    req(len({x["format"] for x in c["cases"]}) == 14, "fourteen distinct formats")
    req(set(c["blob_sha256"]) == {"kernels/format_batch2.metal", "harness/probe.m", "run.py",
                                  "analysis.py", "make_manifest.py", "verify.py"}, "contract blob binding set")
    for p, h in c["blob_sha256"].items():
        req(sha(HERE / p) == h, "contract blob binding " + p)
    req(c["boundary"]["accesses"] == "in-bounds 1x1 texture compute store and typed compute read only"
        and c["boundary"]["apple_binary_archive_bo_inspection"] == "NONE" and c["boundary"]["private_api_or_trace"] == "NONE", "boundary")
    req(c["backings"]["texture"]["total_bytes"] == 384 and c["backings"]["texture"]["hex_chars"] == 768
        and c["backings"]["result"]["total_bytes"] == 144 and c["backings"]["result"]["hex_chars"] == 288, "backing contract")
    req(c["timeouts_seconds"] == {"environment": 5, "host_build": 120, "case_process": 300,
                                  "compile_phase": 120, "dispatch_phase": 300}, "timeout contract")
    req(c["capture"]["runs"] == list(RUNS) and c["capture"]["receipt_keys"] == sorted(REC_KEYS)
        and c["capture"]["inputs_keys"] == sorted(INPUT_KEYS) and c["capture"]["payload_keys"] == sorted(PAYLOAD_KEYS)
        and c["capture"]["run_manifest_keys"] == RUN_MANIFEST_KEYS
        and c["capture"]["pre_capture_gate"] == ["python3 -B verify.py --preflight", "python3 -B verify.py --selftest"]
        and c["capture"]["pre_second_run_gate"] == ["python3 -B verify.py --between-runs", "python3 -B verify.py --selftest"]
        and c["capture"]["statuses_exit_zero"] == ["ok", "store_pipeline_rejected", "read_pipeline_rejected", "texture_rejected", "command_buffer_error"],
        "capture grammar")
    k = (HERE / "kernels/format_batch2.metal").read_text()
    h = (HERE / "harness/probe.m").read_text()
    klines = [ln for ln in k.splitlines() if ln.startswith("kernel void ")]
    req(len(klines) == len(CASES) + 3, "kernel count")
    req(sum(1 for ln in klines if ln.startswith("kernel void s_")) == len(CASES), "store kernel count")
    req(sum(1 for ln in klines if ln.startswith("kernel void k_read_")) == 3, "read kernel count")
    req(all(ln.startswith("kernel void s_") or ln.startswith("kernel void k_read_") for ln in klines), "kernel naming")
    req(set(re.findall(r"uint2\(([^)]*)\)", k)) == {"0, 0"}, "in-bounds kernel coordinates")
    req(k.count("t.read(uint2(0, 0))") == 3, "in-bounds typed reads")
    req("width:1 height:1" in h and "newTextureWithDescriptor:td offset:64 bytesPerRow:256" in h
        and "fastMathEnabled = NO" in h and "MTLResourceStorageModeShared" in h
        and "newBufferWithLength:384" in h and "newBufferWithLength:144" in h, "owned buffers and frozen options")
    req(not re.search(r"IOKit|objcMsgSend|objc_msgSend|MTLIO|class-dump|otool|Ghidra|lldb", h + k), "forbidden inspection token")
    req(not re.search(r"contents\s*\+\s*[^6]", h), "forbidden pointer arithmetic")
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
    spec = importlib.util.spec_from_file_location("exp0072_runner", HERE / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def synthetic_receipt(argv, timeout, stdout):
    return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
            "started_utc": "2026-08-27T00:00:00+00:00", "timed_out": False, "exit": 0,
            "stdout": stdout, "stderr": "", "exception": None}

def ok_payload(c, words_ints):
    texel = c["expected_texel_hex"]
    tb = bytes.fromhex(texel)
    backing = "5a" * 64 + (tb + b"\x00" * (256 - len(tb))).hex() + "a5" * 64
    result = "5a" * 64 + b"".join(w.to_bytes(4, "little") for w in words_ints).hex() + "a5" * 64
    return {"case": c["case"], "format": c["format"], "texel_bytes": c["texel_bytes"], "reader": c["reader"],
            "usage_flags": "MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead", "storage_mode": "MTLStorageModeShared",
            "fast_math_enabled": False, "status": "ok", "library_ok": True, "library_error": "",
            "store_pipeline_ok": True, "store_pipeline_error": "", "read_pipeline_ok": True, "read_pipeline_error": "",
            "texture_ok": True, "texture_error": "", "command_buffer_status": 4, "command_buffer_error": "",
            "device": "Apple M4", "machine": "arm64", "os": "Version 26.6.2 (Build 25G82)",
            "physical_texel_hex": texel, "backing_hex": backing, "result_hex": result,
            "read_words_le": list(words_ints), "backing_prefix_guard": True, "backing_suffix_guard": True,
            "result_prefix_guard": True, "result_suffix_guard": True}

def rejected_payload(c, status):
    base = ok_payload(c, [0, 0, 0, 0])
    base.update({"status": status, "backing_hex": PRISTINE_BACKING, "result_hex": PRISTINE_RESULT,
                 "physical_texel_hex": "00" * c["texel_bytes"], "read_words_le": [0, 0, 0, 0],
                 "command_buffer_status": 0, "command_buffer_error": ""})
    flags = REJECT_FLAGS[status]
    base.update({"library_ok": flags[0], "store_pipeline_ok": flags[1], "read_pipeline_ok": flags[2], "texture_ok": flags[3]})
    errkey = {"store_pipeline_rejected": "store_pipeline_error", "read_pipeline_rejected": "read_pipeline_error",
              "texture_rejected": "texture_error"}[status]
    base[errkey] = "MTLComputePipelineFailure|17|Cannot create pipeline"
    return base

def cberror_payload(c):
    base = ok_payload(c, [0, 0, 0, 0])
    base.update({"status": "command_buffer_error", "command_buffer_status": 5,
                 "command_buffer_error": "MTLCommandBufferFailure|1|executed program is invalid"})
    return base

def synthetic_run(mod, rid, contract_cases, env, run_manifest):
    cases = {}
    special = {"r8unorm_p050": "store", "rgba8snorm_pack": "read", "rgb9e5float_mid": "texture", "rgba16uint_pack": "cb"}
    for c in contract_cases:
        if c["case"] in special:
            p = {"store": rejected_payload(c, "store_pipeline_rejected"),
                 "read": rejected_payload(c, "read_pipeline_rejected"),
                 "texture": rejected_payload(c, "texture_rejected"),
                 "cb": cberror_payload(c)}[special[c["case"]]]
        else:
            p = ok_payload(c, [int(w, 16) for w in c["expected_read_words_le"]])
        argv = mod.case_argv(HERE / "work" / rid, c)
        cases[c["case"]] = synthetic_receipt(argv, 300, json.dumps(p))
    return {"inputs": env, "build": synthetic_receipt(mod.build_argv(HERE / "work" / rid), 120, ""),
            "run_manifest": run_manifest, "cases": cases}

def must_fail(label, fn):
    try:
        fn()
    except SystemExit as e:
        if str(e).startswith("FAIL "):
            return
        raise AssertionError("selftest " + label + ": unexpected SystemExit " + str(e))
    raise AssertionError("selftest " + label + ": check did not fail")

def selftest():
    cs = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())["cases"]
    req([x["case"] for x in cs] == [x[0] for x in CASES], "selftest case order")
    # 1. Live cross-checks against run.py's own record builders (EXP-0073 class).
    mod = load_runner()
    r = mod.rec(["/usr/bin/true"], 5)
    req(r["exit"] == 0 and r["exception"] is None and set(r) == REC_KEYS, "run.py receipt key set")
    env = mod.env_record()
    check_inputs(env, "selftest")
    for z in (env["sw_vers"], env["xcrun_version"], env["device_model"]):
        req(z["exit"] == 0 and z["timed_out"] is False and z["exception"] is None, "selftest environment command")
    rm = mod.run_manifest_record(RUNS[0], [x[0] for x in CASES])
    req(set(rm) == set(RUN_MANIFEST_KEYS), "run manifest key set")
    probe = HERE / "work" / RUNS[0] / "probe"
    for cid, fmt, nbits, reader in CASES[:3] + CASES[-2:]:
        argv = mod.case_argv(HERE / "work" / RUNS[0], {"case": cid, "format": fmt, "texel_bytes": nbits, "reader": reader})
        req(argv == [probe, "--source", HERE / "kernels/format_batch2.metal", "--case", cid, "--format", fmt,
                     "--texel-bytes", str(nbits), "--reader", reader], "case argv template " + cid)
    # 2. Harness prints exactly the payload key set.
    h = (HERE / "harness/probe.m").read_text()
    keys = set(re.findall(r'[,{]\\"([a-z_]+)\\"', h))
    req(keys == PAYLOAD_KEYS, "harness payload key set mismatch: " + str(keys ^ PAYLOAD_KEYS))
    # 3. Synthetic two-run capture passes every schema gate (uses contract expectations).
    envj = json.loads(json.dumps(env))
    runs = [synthetic_run(mod, rid, cs, envj, json.loads(json.dumps(rm))) for rid in RUNS]
    # the synthetic run_manifest must match what validate_run expects for each rid
    for idx, rid in enumerate(RUNS):
        rm2 = dict(runs[idx]["run_manifest"]); rm2["run_id"] = rid
        runs[idx]["run_manifest"] = rm2
    out = [validate_run(rid, objs) for rid, objs in zip(RUNS, runs)]
    compare_runs([o[0] for o in out], [o[1] for o in out])
    # 4. Tampered variants must fail closed.
    must_fail("receipt-extra-key", lambda: receipt({**runs[0]["cases"][CASES[0][0]], "results_lines": 4}, [], HERE, 300, "x"))
    bad = json.loads(json.dumps(runs[0])); bad["cases"][CASES[0][0]]["exit"] = 1
    must_fail("receipt-nonzero-exit", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[0])); bad["cases"][CASES[0][0]]["argv"] = bad["cases"][CASES[0][0]]["argv"] + ["--extra"]
    must_fail("receipt-argv-drift", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[0])); p = json.loads(bad["cases"][CASES[0][0]]["stdout"]); del p["device"]
    bad["cases"][CASES[0][0]]["stdout"] = json.dumps(p)
    must_fail("payload-missing-key", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[0])); p = json.loads(bad["cases"][CASES[0][0]]["stdout"])
    p["physical_texel_hex"] = ("ff" if p["physical_texel_hex"][0] != "f" else "00") * CASES[0][2]
    bad["cases"][CASES[0][0]]["stdout"] = json.dumps(p)
    must_fail("texel-vs-backing-mismatch", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[0])); p = json.loads(bad["cases"][CASES[0][0]]["stdout"])
    p["backing_prefix_guard"] = False
    bad["cases"][CASES[0][0]]["stdout"] = json.dumps(p)
    must_fail("guard-flag-lie", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[0])); p = json.loads(bad["cases"][CASES[0][0]]["stdout"])
    p["store_pipeline_ok"] = False; p["status"] = "store_pipeline_rejected"; p["command_buffer_status"] = 0
    bad["cases"][CASES[0][0]]["stdout"] = json.dumps(p)
    must_fail("rejection-flag-inconsistency", lambda: validate_run(RUNS[0], bad))
    bad = json.loads(json.dumps(runs[1])); p = json.loads(bad["cases"][CASES[1][0]]["stdout"])
    p["read_words_le"][0] ^= 1  # keep the record internally consistent so only the cross-run comparison can catch it
    p["result_hex"] = "5a" * 64 + b"".join(w.to_bytes(4, "little") for w in p["read_words_le"]).hex() + "a5" * 64
    bad["cases"][CASES[1][0]]["stdout"] = json.dumps(p)
    out2 = [validate_run(RUNS[0], runs[0]), validate_run(RUNS[1], bad)]
    must_fail("cross-run-payload-mismatch", lambda: compare_runs([o[0] for o in out2], [o[1] for o in out2]))
    prov2 = [out[0][0], dict(out[1][0])]
    prov2[1]["git_revision"] = "0" * 40
    must_fail("cross-run-provenance-mismatch", lambda: compare_runs(prov2, [o[1] for o in out]))
    print("PASS selftest: schema gates satisfiable; tamper checks bite")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--captured", action="store_true")
    a = ap.parse_args()
    if a.preflight:
        static()
        req(not (HERE / "raw").exists(), "PRE_GPU tree must have no raw")
        print("PASS PRE_GPU contract; no GPU capture")
    elif a.selftest:
        static()
        req(not (HERE / "raw").exists(), "selftest runs only in the PRE_GPU tree")
        selftest()
    elif a.between_runs:
        static(capture=True)
        captured((RUNS[0],))
        print("PASS run01 contract; run02 may begin")
    else:
        static(capture=True, need_analysis=True)
        captured(RUNS)
        print("PASS captured public-Metal owned-buffer contract")

if __name__ == "__main__":
    main()
