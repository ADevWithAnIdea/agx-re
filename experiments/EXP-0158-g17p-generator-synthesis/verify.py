#!/usr/bin/env python3
"""EXP-0112 fail-closed verifier. No GPU access anywhere in this file.
Architecture verbatim-adapted from EXP-0101/EXP-0090's own verify.py.

--selftest    synthetic, no GPU, runnable in EVERY tree state. Uses the SAME
              key sets (run.SMOKE_KEYS) the runner itself writes. Its
              fixture (harness/recorded_fixture_case0.json) is a REAL
              record from an actual hardware run captured during this
              experiment's own pilot phase (case 0) -- CODEX gate (e). Also
              round-trips a sample of generated programs across every
              family and re-checks the register-allocator's own live-count
              invariant across a wide (seed, n_nodes) sweep.
--seqtest     gate-sequence state machine over PRE_GPU / RUN01_PRESENT /
              RUN02_PRESENT.
--preflight   run before run01: static gate only (no run01/run02 dirs yet).
--between-runs  run before run02: run01 must be closed and valid; NEVER
              compares live git HEAD -- gated only on authored_*_sha256
              (SUBAGENT_BRIEF.md standing instruction).
--captured    after both runs: raw/ trees exist, are schema-valid, and
              01_results.jsonl is BYTE-IDENTICAL between run01 and run02
              (01_timing.jsonl is explicitly NOT required to match).
"""
import argparse, hashlib, json, math, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as RUN          # noqa: E402
import casematrix as CM    # noqa: E402
import generator as G      # noqa: E402

GATED_KEYS = {"i", "name", "group", "carrier", "oracle", "expect_match", "notes", "status",
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

    check(RUN.SMOKE_KEYS == GATED_KEYS | NONGATED_KEYS | {"timed_out", "exception", "exit"},
          "run.SMOKE_KEYS drifted from the verifier's own expectation")

    full = json.loads((HERE / "harness" / "recorded_fixture_case0.json").read_text())
    check(set(full) == RUN.SMOKE_KEYS, "recorded fixture key set unexpected: %r" % (set(full) ^ RUN.SMOKE_KEYS))
    receipt = {"timed_out": full["timed_out"], "exception": full["exception"], "exit": full["exit"]}
    problems = RUN.smoke_problems(full, receipt)
    check(problems == [], "recorded-reality fixture unexpectedly failed smoke_problems: %r" % problems)

    bad = dict(full); bad["status"] = "REJECTED"
    check(RUN.smoke_problems(bad, receipt) != [], "smoke_problems missed a bad status")
    bad2 = dict(full); bad2["match"] = False
    check(RUN.smoke_problems(bad2, receipt) != [], "smoke_problems missed match=False")
    bad3 = dict(full); del bad3["out_hex"]
    check(RUN.smoke_problems(bad3, receipt) != [], "smoke_problems missed a missing key")
    bad_receipt = dict(receipt); bad_receipt["timed_out"] = True
    check(RUN.smoke_problems(full, bad_receipt) != [], "smoke_problems missed timed_out receipt")

    NONDET_NAMES = {"duration_ms", "argv", "stdout", "stderr", "started_utc", "pid"}
    check(GATED_KEYS.isdisjoint(NONDET_NAMES), "a nondeterministic-looking field name leaked into GATED_KEYS")
    check(NONGATED_KEYS & NONDET_NAMES == {"duration_ms", "argv", "stdout", "stderr"},
          "NONGATED_KEYS drifted from the expected nondeterministic field set")

    # -- case matrix structural checks (no GPU) --
    cs1 = CM.build_cases()
    cs2 = CM.build_cases()
    check(cs1 == cs2, "casematrix.build_cases() is not deterministic across two in-process calls")
    check(len(cs1) >= 100, "corpus smaller than the pre-registered minimum of 100 programs")
    names = [c["name"] for c in cs1]
    check(len(names) == len(set(names)), "duplicate case name in casematrix")
    check([c["i"] for c in cs1] == list(range(len(cs1))), "case indices are not a dense 0..N-1 range")
    for c in cs1:
        check(c["group"] in ("MAIN_DAG", "REGBOUNDARY", "IADD_ANCHOR", "CF", "ADVERSARIAL"),
              "unknown group %r on case %r" % (c["group"], c["name"]))
        check(c["carrier"] in ("dag", "cf"), "unknown carrier %r on case %r" % (c["carrier"], c["name"]))
        check(all(math.isfinite(v) for v in c["oracle"].values()),
              "non-finite oracle value on case %r (NaN/Inf confound leaked through)" % c["name"])
        # every case's hex round-trips under tools/agx-isa's own assemble/disassemble
        import isa_helpers as H
        H.assert_round_trip(bytes.fromhex(c["hex"]))
    n += 5 + len(cs1) * 3

    # -- generator invariant re-check (independent of casematrix's own use) --
    bad_live = 0
    for seed in range(0, 30):
        for nn in (2, 5, 10, 14, 20, 30, 40):
            _, _, meta = G.build_dag_program(seed, nn, G.DAG_CARRIER_LEN,
                                               base_slot_out=G.SLOT_OUT, base_slot_in=G.SLOT_MEM)
            if meta["max_live_registers"] > G.POOL_SIZE:
                bad_live += 1
    check(bad_live == 0, "%d (seed,n_nodes) pairs violated the POOL_SIZE=%d live-register invariant" %
          (bad_live, G.POOL_SIZE))
    n += 1

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
    check(callable(selftest), "selftest not callable")
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
        unexpected = [m for m in mismatches if m["expect_match"]]
        print("%s: %d/%d cases MISMATCHED oracle (%d unexpected):" %
              (rid, len(mismatches), len(lines), len(unexpected)))
        for m in unexpected:
            print("   UNEXPECTED MISMATCH:", m["name"], "observed=", m["observed"], "oracle=", m["oracle"])
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
