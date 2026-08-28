#!/usr/bin/env python3
"""Fail-closed verifier for EXP-0114. Architecture independently re-authored
from the proven EXP-0079/EXP-0083/EXP-0095/EXP-0106 --selftest/--seqtest
pattern (this project's own prior work):

1. --selftest is STATE-AGNOSTIC: runs the static-tree check against whatever
   state this tree is actually in (PRE_GPU or CAPTURED), then a synthetic
   in-process schema self-test built from CAPTURE_CONTRACT.json's own frozen
   case list (RECORDED REALITY) that never reads a real raw/ tree.
2. --seqtest is a gate-sequence STATE MACHINE: builds three isolated fixture
   trees (PRE_GPU / RUN01_PRESENT / RUN02_PRESENT) and subprocess-invokes the
   real gate for each.
3. --preflight is the static-tree check alone (no captures required).
4. --captured validates both raw/ runs in full and requires byte-exact
   cross-run agreement (NO NONDETERMINISTIC FIELD: every compared payload is
   checked against a closed key set with no timestamp/pointer/PID fields).
5. --between-runs is an alias for the cross-run comparison half of --captured.
"""
import argparse, datetime, hashlib, importlib.util, json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_NAMES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md", "RESULTS.md",
              "PROGRESS.md", "kernels", "harness", "analysis", "run.py", "gen_contract.py",
              "verify.py"}

REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit", "stdout", "stderr", "exception"}
INPUT_KEYS = {"schema", "git_revision", "git_dirty", "authored_sha256", "sw_vers", "xcrun_version",
              "device_model", "machine", "boundary"}

DIFF_KEYS = {"schema", "family", "case", "status", "n_declared", "bundle_count", "op4_sequence",
             "nibble_sequence", "distinct_nibbles", "lownibble_all_zero"}
DIFF_FAIL_KEYS = {"schema", "family", "case", "status", "compiler_stdout_tail", "compiler_stderr_tail"}
SPLICE_TEX_KEYS = {"schema", "family", "case", "status", "tool_exit", "tool_status", "out_word_hex",
                    "applied_splices", "stderr_tail"}
SPLICE_GRAD_KEYS = {"schema", "family", "case", "status", "tool_exit", "tool_status", "pixel",
                     "applied_splices", "stderr_tail"}


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


def runs_tuple():
    return tuple(contract()["capture"]["runs"])


# ---------------------------------------------------------------- static tree

def _no_pycache(it):
    return [x for x in it if x.name != "__pycache__"]


def static(capture=False):
    names = {p.name for p in HERE.iterdir() if p.name != "__pycache__"}
    quarantine_names = {n for n in names if n.lower().startswith("quarantine")}
    names_checked = names - quarantine_names
    allowed = ROOT_NAMES | ({"raw"} if capture else set()) | ({"analysis.json"} if "analysis.json" in names else set()) | ({"work"} if "work" in names else set())
    req(not HERE.is_symlink() and names_checked == allowed, "closed root: " + str(names_checked ^ allowed))
    if capture:
        req((HERE / "raw").is_dir() and not (HERE / "raw").is_symlink(), "raw tree present")
    auth = auth_files()
    for p in auth + ("README.md", "RESULTS.md", "PROGRESS.md", "PRE_REGISTRATION.md"):
        req(regular(HERE / p), "regular " + p)
    kd = HERE / "kernels"
    req(kd.is_dir() and not kd.is_symlink() and all(regular(x) for x in _no_pycache(kd.iterdir())), "closed kernels")
    hd = HERE / "harness"
    req(hd.is_dir() and not hd.is_symlink() and all(regular(x) for x in _no_pycache(hd.iterdir())), "closed harness")
    req((HERE / "analysis").is_dir(), "analysis dir present")

    c = contract()
    req(c["state"] == "PRE_GPU" and c["experiment"] == "EXP-0114-m4-texture-deferred", "contract identity")
    cs = c["cases"]
    ids = [x["case"] for x in cs]
    req(len(ids) == len(set(ids)), "unique case ids")
    for x in cs:
        req(set(x) >= {"case", "family", "args", "expect", "timeout_seconds", "rule_note"}, "case record keys " + x["case"])
        req(x["family"] in ("diff", "splice_tex", "splice_grad"), "case family " + x["case"])
        req(isinstance(x["timeout_seconds"], int) and x["timeout_seconds"] > 0, "timeout " + x["case"])
        req(isinstance(x["rule_note"], str) and x["rule_note"], "rule_note " + x["case"])
    req(set(c["blob_sha256"]) == set(auth) - {"CAPTURE_CONTRACT.json"}, "contract blob binding set")
    for p, h in c["blob_sha256"].items():
        req(sha(p) == h, "contract blob binding " + p)
    req(c["capture"]["runs"] == list(runs_tuple()), "capture runs")


# ---------------------------------------------------------------- payload checks

def check_diff_payload(p, c, label):
    if p.get("status") == "compile_failed":
        req(set(p) == DIFF_FAIL_KEYS, "diff-fail payload key set " + label)
        fail("unexpected compile_failed " + label)
    req(set(p) == DIFF_KEYS, "diff payload key set " + label)
    req(p["family"] == "diff" and p["case"] == c["case"] and p["status"] == "ok", "diff identity/status " + label)
    e = c["expect"]
    req(p["bundle_count"] == e["bundle_count"], "bundle_count " + label)
    req(p["distinct_nibbles"] == e["distinct_nibbles"], "distinct_nibbles " + label)
    req(p["lownibble_all_zero"] == e["lownibble_all_zero"], "lownibble_all_zero " + label)
    if e.get("op4_sequence") is not None:
        req(p["op4_sequence"] == e["op4_sequence"], "op4_sequence " + label)


def check_splice_tex_payload(p, c, label):
    req(set(p) == SPLICE_TEX_KEYS, "splice_tex payload key set " + label)
    req(p["family"] == "splice_tex" and p["case"] == c["case"], "splice_tex identity " + label)
    req(p["status"] == c["expect"]["status"], "splice_tex status " + label)
    req(p["out_word_hex"] == c["expect"]["out_word_hex"], "splice_tex out_word_hex " + label)
    req(isinstance(p["applied_splices"], list) and len(p["applied_splices"]) == len(c["splices"]), "splice_tex applied_splices count " + label)
    for applied, spec in zip(p["applied_splices"], c["splices"]):
        req(set(applied) == {"rel_offset", "abs_offset", "before", "after"}, "splice_tex applied entry keys " + label)
        req(applied["rel_offset"] == spec["rel_offset"] and applied["after"] == spec["value"], "splice_tex applied entry values " + label)


def check_splice_grad_payload(p, c, label):
    req(set(p) == SPLICE_GRAD_KEYS, "splice_grad payload key set " + label)
    req(p["family"] == "splice_grad" and p["case"] == c["case"], "splice_grad identity " + label)
    req(p["status"] == c["expect"]["status"], "splice_grad status " + label)
    req(isinstance(p["applied_splices"], list) and len(p["applied_splices"]) == len(c["splices"]), "splice_grad applied_splices count " + label)
    for applied, spec in zip(p["applied_splices"], c["splices"]):
        req(set(applied) == {"rel_offset", "abs_offset", "before", "after"}, "splice_grad applied entry keys " + label)
        req(applied["rel_offset"] == spec["rel_offset"] and applied["after"] == spec["value"], "splice_grad applied entry values " + label)
    want = c["expect"]["rg"]
    pix = p["pixel"] or ""
    if want == "red":
        req("r=1 " in pix and "g=0 " in pix, "splice_grad expected red " + label + " got " + pix)
    elif want == "green":
        req("r=0 " in pix and "g=1 " in pix, "splice_grad expected green " + label + " got " + pix)
    else:
        fail("unknown expect.rg " + label)


def payload_for(kind):
    return {"diff": check_diff_payload, "splice_tex": check_splice_tex_payload, "splice_grad": check_splice_grad_payload}[kind]


# ---------------------------------------------------------------- captured validation

def receipt(z, label):
    req(set(z) == REC_KEYS, "receipt key set " + label)
    req(z["timed_out"] is False and z["exit"] == 0 and z["exception"] is None
        and isinstance(z["stdout"], str) and isinstance(z["stderr"], str), label)
    try:
        req(datetime.datetime.fromisoformat(z["started_utc"]).utcoffset() == datetime.timedelta(), label + " timestamp")
    except (TypeError, ValueError):
        fail(label + " timestamp")


def check_inputs(i, label):
    req(set(i) == INPUT_KEYS, "inputs key set " + label)
    req(i["schema"] == 1 and i["machine"] == "arm64" and isinstance(i["git_dirty"], bool)
        and set(i["authored_sha256"]) == set(auth_files()), "inputs schema " + label)
    for path, want in i["authored_sha256"].items():
        req(sha(path) == want, "post-capture source binding " + label + " " + path)


def provenance_row(i):
    return {"git_revision": i["git_revision"], "authored_sha256": i["authored_sha256"]}


def load_run(rid):
    d = HERE / "raw" / rid
    cs = cases()
    names = {"00_inputs.json", "01_host_build.json", "run_manifest.json"} | {f"case_{c['case']}.json" for c in cs}
    req(d.is_dir() and not d.is_symlink() and {p.name for p in d.iterdir()} == names and all(regular(p) for p in d.iterdir()), "closed raw " + rid)
    return {"inputs": json.loads((d / "00_inputs.json").read_text()),
            "build": json.loads((d / "01_host_build.json").read_text()),
            "run_manifest": json.loads((d / "run_manifest.json").read_text()),
            "cases": {c["case"]: json.loads((d / f"case_{c['case']}.json").read_text()) for c in cs}}


def validate_run(rid, objs):
    i = objs["inputs"]
    check_inputs(i, rid)
    for key in ("sw_vers", "xcrun_version", "device_model"):
        receipt(i[key], key + " " + rid)
    for key in ("shdump", "texsplice", "gradsplice"):
        b = objs["build"][key]
        req(b["exit"] == 0 and b["timed_out"] is False, "build " + key + " " + rid)
    cs = cases()
    rm = objs["run_manifest"]
    req(rm["schema"] == 1 and rm["run_id"] == rid and rm["cases"] == [c["case"] for c in cs]
        and rm["fresh_process_per_case"] is True and rm["runner_sha256"] == i["authored_sha256"]["run.py"]
        and rm["harness_sha256"] == i["authored_sha256"]["harness/case_runner.py"]
        and rm["contract_sha256"] == i["authored_sha256"]["CAPTURE_CONTRACT.json"], "run manifest " + rid)
    rows = []
    for c in cs:
        z = objs["cases"][c["case"]]
        receipt(z, "case process " + c["case"])
        try:
            p = json.loads(z["stdout"])
        except json.JSONDecodeError:
            fail("case stdout not one JSON object " + c["case"])
        payload_for(c["family"])(p, c, c["case"])
        rows.append(p)
    return provenance_row(i), rows


def compare_runs(provenance, rows):
    req(provenance[0] == provenance[1], "cross-run revision/authored provenance")
    req(rows[0] == rows[1], "byte-exact repeat")


def captured(runs):
    raw = HERE / "raw"
    present = {p.name for p in raw.iterdir() if not p.name.lower().startswith("quarantine")}
    req(raw.is_dir() and not raw.is_symlink() and present == set(runs), "exact raw runs")
    provenance, rows = [], []
    for rid in runs:
        prov, rws = validate_run(rid, load_run(rid))
        provenance.append(prov)
        rows.append(rws)
    compare_runs(provenance, rows)
    return rows[0]


# ---------------------------------------------------------------- self-test

def synthetic_receipt(stdout, exit_code=0):
    return {"argv": ["x"], "cwd": str(HERE), "timeout_seconds": 30, "started_utc": "2026-08-28T00:00:00+00:00",
            "timed_out": False, "exit": exit_code, "stdout": stdout, "stderr": "", "exception": None}


def ok_diff_payload(c):
    e = c["expect"]
    seq = e.get("op4_sequence")
    if seq is None:
        seq = ([0, 128] * (e["bundle_count"] // 2 + 1))[:e["bundle_count"]]
    return {"schema": 1, "family": "diff", "case": c["case"], "status": "ok", "n_declared": c["n_declared"],
            "bundle_count": e["bundle_count"], "op4_sequence": seq,
            "nibble_sequence": [x >> 4 for x in seq], "distinct_nibbles": e["distinct_nibbles"],
            "lownibble_all_zero": e["lownibble_all_zero"]}


def ok_splice_tex_payload(c):
    applied = [{"rel_offset": s["rel_offset"], "abs_offset": 7840 + s["rel_offset"], "before": 0, "after": s["value"]} for s in c["splices"]]
    return {"schema": 1, "family": "splice_tex", "case": c["case"], "status": "ok", "tool_exit": 0,
            "tool_status": "OK", "out_word_hex": c["expect"]["out_word_hex"], "applied_splices": applied, "stderr_tail": ""}


def ok_splice_grad_payload(c):
    applied = [{"rel_offset": s["rel_offset"], "abs_offset": 16160 + s["rel_offset"], "before": 0, "after": s["value"]} for s in c["splices"]]
    pix = "PIXEL r=1 g=0 b=1 a=1" if c["expect"]["rg"] == "red" else "PIXEL r=0 g=1 b=1 a=1"
    return {"schema": 1, "family": "splice_grad", "case": c["case"], "status": "ok", "tool_exit": 0,
            "tool_status": "OK", "pixel": pix, "applied_splices": applied, "stderr_tail": ""}


OK_PAYLOAD = {"diff": ok_diff_payload, "splice_tex": ok_splice_tex_payload, "splice_grad": ok_splice_grad_payload}


def must_fail(label, fn):
    try:
        fn()
    except SystemExit as e:
        if str(e).startswith("FAIL "):
            return
        raise AssertionError("selftest " + label + ": unexpected SystemExit " + str(e))
    raise AssertionError("selftest " + label + ": check did not fail")


def selftest():
    # 1. Static tree check against whatever state this tree is actually in.
    raw = HERE / "raw"
    real_runs_present = raw.is_dir() and {p.name for p in raw.iterdir() if not p.name.lower().startswith("quarantine")} == set(runs_tuple())
    capture_present = raw.exists()
    static(capture=capture_present)
    if capture_present and not real_runs_present:
        # raw/ holds only quarantined attempts -- nothing further to validate.
        print("SELFTEST PASS (raw/ holds only quarantined attempts; no live capture to validate)")
        return
    if capture_present:
        captured(runs_tuple())

    # 2. Synthetic, state-agnostic schema self-test using RECORDED REALITY
    #    (CAPTURE_CONTRACT.json's own case list), never touching a real raw/ tree.
    cs = cases()
    req(len(cs) > 0, "selftest: contract has cases")
    for c in cs:
        good = OK_PAYLOAD[c["family"]](c)
        payload_for(c["family"])(good, c, "selftest " + c["case"])

        # mutation: wrong status must fail
        bad = dict(good)
        bad["status"] = "bogus"
        if c["family"] == "diff":
            must_fail("bad status " + c["case"], lambda bad=bad, c=c: payload_for(c["family"])(bad, c, "x"))
        else:
            must_fail("bad status " + c["case"], lambda bad=bad, c=c: payload_for(c["family"])(bad, c, "x"))

        # mutation: extra key must fail closed key-set check
        extra = dict(good); extra["bogus_extra_field"] = 1
        must_fail("extra key " + c["case"], lambda extra=extra, c=c: payload_for(c["family"])(extra, c, "x"))

        # mutation: missing key must fail
        missing = dict(good); del missing[next(iter(missing))]
        must_fail("missing key " + c["case"], lambda missing=missing, c=c: payload_for(c["family"])(missing, c, "x"))

    # receipt schema self-test
    good_rec = synthetic_receipt("{}")
    receipt(good_rec, "selftest receipt")
    for label, mutate in (
        ("timed_out", lambda z: {**z, "timed_out": True}),
        ("nonzero exit", lambda z: {**z, "exit": 1}),
        ("extra key", lambda z: {**z, "bogus": 1}),
        ("missing key", lambda z: {k: v for k, v in z.items() if k != "exit"}),
    ):
        must_fail("receipt " + label, lambda z=good_rec, m=mutate: receipt(m(z), "x"))

    # non-recorded smoke gate schema self-test (mirrors run.py's smoke_problems)
    spec = importlib.util.spec_from_file_location("exp0114_runner", HERE / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sm = contract()["capture"]["pre_capture_smoke"]
    sm_case = next(c for c in cs if c["case"] == sm["case"])
    good_smoke = synthetic_receipt(json.dumps(ok_splice_tex_payload(sm_case)))
    req(mod.smoke_problems(good_smoke, sm_case) == [], "smoke gate accepts a complete record")
    bad_smoke = synthetic_receipt(json.dumps(ok_splice_tex_payload(sm_case))[:20])
    req(mod.smoke_problems(bad_smoke, sm_case) != [], "smoke gate rejects truncated record")

    print("SELFTEST PASS")


# ---------------------------------------------------------------- seqtest (fixture state machine)

def build_fixture(tmpdir, state):
    """Build an isolated copy of this experiment tree in `tmpdir`, then bring
    it to the requested state (PRE_GPU / RUN01_PRESENT / RUN02_PRESENT) using
    SYNTHETIC (but schema-correct, RECORDED-REALITY-derived) case records --
    never a live GPU dispatch inside the fixture."""
    dst = Path(tmpdir) / ("fixture_" + state)
    shutil.copytree(HERE, dst, ignore=shutil.ignore_patterns("raw", "work", "analysis.json", "__pycache__",
                                                               "quarantine*", "QUARANTINE*"))
    c = json.loads((dst / "CAPTURE_CONTRACT.json").read_text())
    runs = c["capture"]["runs"]

    def write_run(rid):
        raw = dst / "raw" / rid
        raw.mkdir(parents=True)
        auth = {p: hashlib.sha256((dst / p).read_bytes()).hexdigest() for p in c["blob_sha256"]}
        auth["CAPTURE_CONTRACT.json"] = hashlib.sha256((dst / "CAPTURE_CONTRACT.json").read_bytes()).hexdigest()
        inputs = {"schema": 1, "git_revision": "0" * 40, "git_dirty": False, "authored_sha256": auth,
                   "sw_vers": synthetic_receipt("ProductName:\tmacOS\n"), "xcrun_version": synthetic_receipt("xcrun version 1\n"),
                   "device_model": synthetic_receipt("Mac16,10\n"), "machine": "arm64", "boundary": c["boundary"]}
        (raw / "00_inputs.json").write_text(json.dumps(inputs))
        build = {k: synthetic_receipt("", 0) for k in ("shdump", "texsplice", "gradsplice")}
        (raw / "01_host_build.json").write_text(json.dumps(build))
        rm = {"schema": 1, "run_id": rid, "cases": [x["case"] for x in c["cases"]], "fresh_process_per_case": True,
              "runner_sha256": auth["run.py"], "harness_sha256": auth["harness/case_runner.py"],
              "authored_sha256": auth, "contract_sha256": auth["CAPTURE_CONTRACT.json"]}
        (raw / "run_manifest.json").write_text(json.dumps(rm))
        for x in c["cases"]:
            payload = OK_PAYLOAD[x["family"]](x)
            (raw / f"case_{x['case']}.json").write_text(json.dumps(synthetic_receipt(json.dumps(payload))))

    if state in ("RUN01_PRESENT", "RUN02_PRESENT"):
        write_run(runs[0])
    if state == "RUN02_PRESENT":
        write_run(runs[1])
    return dst


def seqtest():
    # NEVER use the system temp dir (outside-the-repo write is forbidden) --
    # build fixtures under this experiment's own work/ scratch directory.
    checks = 0
    tmp = HERE / "work" / "seqtest_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        for state in ("PRE_GPU", "RUN01_PRESENT", "RUN02_PRESENT"):
            fixture = build_fixture(tmp, state)
            if state == "PRE_GPU":
                r = subprocess.run([sys.executable, "verify.py", "--preflight"], cwd=fixture, capture_output=True, text=True)
                req(r.returncode == 0, "seqtest PRE_GPU --preflight: " + r.stdout + r.stderr)
                r2 = subprocess.run([sys.executable, "verify.py", "--captured"], cwd=fixture, capture_output=True, text=True)
                req(r2.returncode != 0, "seqtest PRE_GPU --captured should fail (no raw/)")
                checks += 2
            elif state == "RUN01_PRESENT":
                r = subprocess.run([sys.executable, "verify.py", "--captured"], cwd=fixture, capture_output=True, text=True)
                req(r.returncode != 0, "seqtest RUN01_PRESENT --captured should fail (only 1 of 2 runs)")
                r2 = subprocess.run([sys.executable, "verify.py", "--preflight"], cwd=fixture, capture_output=True, text=True)
                req(r2.returncode == 0, "seqtest RUN01_PRESENT --preflight: " + r2.stdout + r2.stderr)
                checks += 2
            else:
                r = subprocess.run([sys.executable, "verify.py", "--captured"], cwd=fixture, capture_output=True, text=True)
                req(r.returncode == 0, "seqtest RUN02_PRESENT --captured: " + r.stdout + r.stderr)
                checks += 1
        print(f"SEQTEST PASS ({checks} subprocess gate checks across PRE_GPU/RUN01_PRESENT/RUN02_PRESENT)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--seqtest", action="store_true")
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--captured", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    elif args.seqtest:
        seqtest()
    elif args.preflight:
        static(capture=(HERE / "raw").exists())
        print("PREFLIGHT PASS")
    elif args.captured or args.between_runs:
        static(capture=True)
        captured(runs_tuple())
        print("CAPTURED PASS")


if __name__ == "__main__":
    main()
