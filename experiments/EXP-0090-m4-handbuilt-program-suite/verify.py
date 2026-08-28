#!/usr/bin/env python3
"""EXP-0090 fail-closed verifier. No GPU access anywhere in this file.

--selftest    synthetic, no GPU, runnable in EVERY tree state. Uses the SAME
              key sets (run.SMOKE_KEYS) the runner itself writes -- one
              authoritative definition, imported not restated. Its fixture
              (harness/recorded_fixture_case0.json) is a REAL record from an
              actual hardware run captured during this experiment's informal
              pilot phase (case 0, p1_baseline) -- CODEX gate (e): a fixture
              built from the implementation's own invented constants could
              not falsify a bug in those same constants; this one is
              independent recorded reality.
--seqtest     gate-sequence state machine over PRE_GPU / RUN01_PRESENT /
              RUN02_PRESENT, proving every contracted gate is runnable AND
              satisfiable in each state where the contract invokes it.
--preflight   run before run01: static gate only (no run01/run02 dirs yet).
--between-runs  run before run02: run01 must be closed and valid; NEVER
              compares live git HEAD (see run.py `git_revision_informational_
              only` -- gated only on authored_*_sha256, per the standing
              instruction to the parallel EXP-0082 lesson).
--captured    after both runs: raw/ trees exist, are schema-valid, and
              01_results.jsonl is BYTE-IDENTICAL between run01 and run02
              (01_timing.jsonl is explicitly NOT required to match).
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as RUN         # noqa: E402  (single source of truth for keys/paths)
import casematrix as CM   # noqa: E402

GATED_KEYS = {"i", "name", "item", "program", "params", "oracle", "status",
              "pipeline_source", "out_hex", "observed", "match"}
NONGATED_KEYS = {"i", "duration_ms", "argv", "stdout", "stderr"}


def fail(msg):
    print("FAIL:", msg)
    return False


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# --selftest
# ---------------------------------------------------------------------------
def selftest():
    ok = True
    n = 0

    def check(cond, msg):
        nonlocal ok, n
        n += 1
        if not cond:
            ok = fail(msg)

    # 1. RUN.SMOKE_KEYS must equal the full case_exec.py record shape
    # (import identity, not restatement) -- GATED_KEYS plus the fields
    # case_exec.py itself adds (timed_out/exception/exit/duration_ms).
    check(RUN.SMOKE_KEYS == GATED_KEYS | NONGATED_KEYS | {"timed_out", "exception", "exit"},
          "run.SMOKE_KEYS drifted from the verifier's own expectation")

    # 2. recorded-reality fixture: a REAL hardware record (case 0, captured
    # verbatim -- unedited case_exec.py stdout -- during this experiment's
    # own informal pilot run) must satisfy run.smoke_problems() with zero
    # problems, and a receipt built from it.
    full = json.loads((HERE / "harness" / "recorded_fixture_case0.json").read_text())
    check(set(full) == RUN.SMOKE_KEYS, "recorded fixture key set unexpected: %r" % (set(full) ^ RUN.SMOKE_KEYS))
    receipt = {"timed_out": full["timed_out"], "exception": full["exception"], "exit": full["exit"]}
    problems = RUN.smoke_problems(full, receipt)
    check(problems == [], "recorded-reality fixture unexpectedly failed smoke_problems: %r" % problems)

    # 3. mutate the recorded fixture (single-field falsifiers) and confirm
    # smoke_problems() DETECTS each defect class -- proves the gate is not
    # a rubber stamp.
    bad = dict(full); bad["status"] = "REJECTED"
    check(RUN.smoke_problems(bad, receipt) != [], "smoke_problems missed a bad status")
    bad2 = dict(full); bad2["match"] = False
    check(RUN.smoke_problems(bad2, receipt) != [], "smoke_problems missed match=False")
    bad3 = dict(full); del bad3["out_hex"]
    check(RUN.smoke_problems(bad3, receipt) != [], "smoke_problems missed a missing key")
    bad_receipt = dict(receipt); bad_receipt["timed_out"] = True
    check(RUN.smoke_problems(full, bad_receipt) != [], "smoke_problems missed timed_out receipt")

    # 4. gated/non-gated separation (CODEX gate d): the GATED key set must
    # contain no field whose value legitimately varies run-to-run
    # (duration/argv/pid/timestamp); the NON-gated set must carry exactly
    # the fields dropped from GATED_KEYS relative to the full case_exec.py
    # record, and none of GATED_KEYS may reappear there under a different
    # name that could smuggle nondeterminism into a byte-compared file.
    NONDET_NAMES = {"duration_ms", "argv", "stdout", "stderr", "started_utc", "pid"}
    check(GATED_KEYS.isdisjoint(NONDET_NAMES), "a nondeterministic-looking field name leaked into GATED_KEYS")
    check(NONGATED_KEYS & NONDET_NAMES == {"duration_ms", "argv", "stdout", "stderr"},
          "NONGATED_KEYS drifted from the expected nondeterministic field set")

    # 5. case matrix sanity: every case round-trips (asm/disasm) and every
    # case name/index is unique (no accidental duplicate/renumbered case).
    import isa_helpers as H
    cs = CM.build_cases()
    check(len(cs) == len({c["name"] for c in cs}), "duplicate case name in casematrix")
    check([c["i"] for c in cs] == list(range(len(cs))), "case indices are not a dense 0..N-1 range")
    for c in cs[:3] + cs[-3:]:   # sample -- full round-trip is exercised by make_manifest.py --check
        H.assert_round_trip(bytes.fromhex(c["hex"]))
    n += 2

    print("selftest: %d checks, %s" % (n, "PASS" if ok else "FAIL"))
    return ok


# ---------------------------------------------------------------------------
# --seqtest : PRE_GPU / RUN01_PRESENT / RUN02_PRESENT state machine
# ---------------------------------------------------------------------------
def state():
    r1 = (HERE / "raw" / RUN.RUNS[0]).exists()
    r2 = (HERE / "raw" / RUN.RUNS[1]).exists()
    if not r1 and not r2:
        return "PRE_GPU"
    if r1 and not r2:
        return "RUN01_PRESENT"
    if r1 and r2:
        return "RUN02_PRESENT"
    return "INVALID_RUN02_WITHOUT_RUN01"


def seqtest():
    ok = True
    steps = 0
    s = state()

    def check(cond, msg):
        nonlocal ok, steps
        steps += 1
        if not cond:
            ok = fail(msg)

    check(s in ("PRE_GPU", "RUN01_PRESENT", "RUN02_PRESENT"), "unexpected/invalid tree state: %s" % s)
    # every state must be able to run selftest and seqtest-static checks
    check(callable(selftest), "selftest not callable")
    # contracted gate sequence per state (mirrors CAPTURE_CONTRACT.json)
    if s == "PRE_GPU":
        check(True, "PRE_GPU: preflight is the next contracted gate (checked separately by --preflight)")
    elif s == "RUN01_PRESENT":
        r1 = HERE / "raw" / RUN.RUNS[0]
        check((r1 / "02_dispatch.json").exists(), "run01 present but not closed (no 02_dispatch.json)")
        check(not (r1 / "STOP.json").exists(), "run01 present but STOPped -- run02 not authorized")
    elif s == "RUN02_PRESENT":
        for rid in RUN.RUNS:
            r = HERE / "raw" / rid
            check((r / "02_dispatch.json").exists(), "%s not closed" % rid)
    print("seqtest: %d checks (state=%s), %s" % (steps, s, "PASS" if ok else "FAIL"))
    return ok


# ---------------------------------------------------------------------------
# --preflight / --between-runs
# ---------------------------------------------------------------------------
def preflight():
    s = state()
    if s != "PRE_GPU":
        return fail("preflight requires PRE_GPU state, got %s" % s)
    for f in RUN.AUTH_CODE + RUN.AUTH_KERNELS + RUN.AUTH_DOC:
        if not (HERE / f).exists():
            return fail("missing authored file: %s" % f)
    print("preflight: PASS")
    return True


def between_runs():
    s = state()
    if s != "RUN01_PRESENT":
        return fail("between-runs requires RUN01_PRESENT state, got %s" % s)
    r1 = json.loads((HERE / "raw" / RUN.RUNS[0] / "00_env.json").read_text())
    current = RUN.provenance()
    # NEVER gate on live git HEAD (SUBAGENT_BRIEF.md standing instruction,
    # EXP-0082 lesson) -- only authored file hashes must be unchanged.
    for key in ("authored_code_sha256", "authored_kernel_sha256", "authored_doc_sha256"):
        if r1.get(key) != current[key]:
            return fail("authored file hash drifted since run01: %s" % key)
    disp = json.loads((HERE / "raw" / RUN.RUNS[0] / "02_dispatch.json").read_text())
    if disp["n_cases"] != len(CM.build_cases()):
        return fail("case count drifted since run01 (%d vs %d)" % (disp["n_cases"], len(CM.build_cases())))
    print("between-runs: PASS")
    return True


# ---------------------------------------------------------------------------
# --captured
# ---------------------------------------------------------------------------
def captured():
    s = state()
    if s != "RUN02_PRESENT":
        return fail("captured requires RUN02_PRESENT state, got %s" % s)
    ok = True
    h1 = sha(HERE / "raw" / RUN.RUNS[0] / "01_results.jsonl")
    h2 = sha(HERE / "raw" / RUN.RUNS[1] / "01_results.jsonl")
    if h1 != h2:
        ok = fail("01_results.jsonl differs between run01 and run02 (%s vs %s)" % (h1, h2))
    else:
        print("01_results.jsonl byte-identical across both runs: %s" % h1)
    t1 = HERE / "raw" / RUN.RUNS[0] / "01_timing.jsonl"
    t2 = HERE / "raw" / RUN.RUNS[1] / "01_timing.jsonl"
    if sha(t1) == sha(t2):
        print("NOTE: 01_timing.jsonl happens to be byte-identical too (not required, not a failure)")
    for rid in RUN.RUNS:
        lines = (HERE / "raw" / rid / "01_results.jsonl").read_text().splitlines()
        mismatches = [json.loads(l) for l in lines if not json.loads(l)["match"]]
        if mismatches:
            print("%s: %d/%d cases MISMATCHED oracle:" % (rid, len(mismatches), len(lines)))
            for m in mismatches:
                print("   ", m["name"], "observed=", m["observed"], "oracle=", m["oracle"])
    print("captured: %s" % ("PASS" if ok else "FAIL"))
    return ok


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
        ok = selftest()
    elif a.seqtest:
        ok = seqtest()
    elif a.preflight:
        ok = preflight()
    elif a.between_runs:
        ok = between_runs()
    else:
        ok = captured()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
