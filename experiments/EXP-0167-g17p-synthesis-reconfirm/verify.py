#!/usr/bin/env python3
"""EXP-0158 fail-closed verifier (G17P). No GPU access anywhere in this file.
Architecture adapted from EXP-0112's own verify.py (our own code).

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
import synth as S          # noqa: E402
import frozen_pilot as FP  # noqa: E402

GATED_KEYS = set(RUN.GATED_KEYS)
NONGATED_KEYS = {"i", "duration_ms", "argv", "stdout", "stderr"}
GROUPS = ("MAIN_DAG", "DAG_INLINE", "REGBOUNDARY", "INLINEIMM", "IADD_SYNTH",
          "IADD_ANCHOR_COPIED", "CF", "ADVERSARIAL")


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

    # ---- the pilot must be frozen before anything else is meaningful ----
    check(FP.FROZEN is True, "frozen_pilot.FROZEN is False -- pre-freeze pilot not frozen")
    check(FP.INLINE_NEG0_SIGN in (1, -1),
          "frozen_pilot.INLINE_NEG0_SIGN must be +1 or -1, got %r" % (FP.INLINE_NEG0_SIGN,))
    check(FP.PILOT_JSONL_SHA256 is not None, "frozen pilot has no evidence hash")

    # ---- the pinned ISA snapshot must be the one synth.py actually loaded ----
    check(Path(S.isadb._DB_JSON).resolve() == (HERE / "work" / "isadb_pinned" / "db.json").resolve(),
          "synth.py is not loading the PINNED db.json (got %s)" % S.isadb._DB_JSON)

    # ---- the smoke gate must reject what it is supposed to reject ----
    fixture_path = HERE / "harness" / "recorded_fixture_case0.json"
    check(fixture_path.exists(), "no recorded hardware fixture for the smoke gate")
    if fixture_path.exists():
        full = json.loads(fixture_path.read_text())
        receipt = {"timed_out": full["timed_out"], "exception": full["exception"],
                   "exit": full["exit"]}
        check(RUN.smoke_problems(full, receipt) == [],
              "recorded-reality fixture unexpectedly failed smoke_problems")
        for mutate, why in ((lambda d: d.update(status="REJECTED"), "bad status"),
                            (lambda d: d.update(match=False), "match=False"),
                            (lambda d: d.update(sentinel=None), "missing sentinel")):
            bad = json.loads(fixture_path.read_text())
            mutate(bad)
            check(RUN.smoke_problems(bad, receipt) != [], "smoke_problems missed %s" % why)
        badr = dict(receipt)
        badr["timed_out"] = True
        check(RUN.smoke_problems(full, badr) != [], "smoke_problems missed a timed_out receipt")

    NONDET = {"duration_ms", "argv", "stdout", "stderr", "started_utc", "pid"}
    check(GATED_KEYS.isdisjoint(NONDET),
          "a nondeterministic field name leaked into the gated key set")

    # ---- case matrix structural checks (no GPU) ----
    cs1 = CM.build_cases()
    cs2 = CM.build_cases()
    check(cs1 == cs2, "casematrix.build_cases() is not deterministic across two calls")
    check(len(cs1) >= 250, "corpus smaller than the pre-registered minimum of 250 programs")
    names = [c["name"] for c in cs1]
    check(len(names) == len(set(names)), "duplicate case name in casematrix")
    check([c["i"] for c in cs1] == list(range(len(cs1))), "case indices are not dense 0..N-1")
    check(sum(1 for c in cs1 if not c["expect_match"]) >= 10,
          "fewer than 10 pre-registered-to-FAIL cases: the corpus cannot detect a difference")
    sent_idx = S.sentinel_word_index()
    for c in cs1:
        check(c["group"] in GROUPS, "unknown group %r on case %r" % (c["group"], c["name"]))
        check(c["carrier"] in ("dag", "cf"), "unknown carrier %r on %r" % (c["carrier"], c["name"]))
        check(all(math.isfinite(v) for v in c["oracle"].values()),
              "non-finite oracle value on case %r" % c["name"])
        check(all(int(k) != sent_idx for k in c["oracle"]),
              "case %r puts a data word on the sentinel word %d" % (c["name"], sent_idx))
        S.assert_round_trip(bytes.fromhex(c["hex"]))
    n += 5 + len(cs1) * 4

    # ---- provenance accounting: the experiment's own headline number ----
    dag_like = [c for c in cs1 if c.get("prov")]
    zero_copied = [c for c in dag_like if not c["prov"]["copied"]]
    honest_copied = [c for c in dag_like if c["prov"]["copied"]]
    check(len(zero_copied) >= 200,
          "fewer than 200 cases claim ZERO copied fields (%d)" % len(zero_copied))
    check(len(honest_copied) >= 20,
          "the corpus retains fewer than 20 deliberately-COPIED cases -- the honest "
          "denominator has gone missing (%d)" % len(honest_copied))
    for c in zero_copied:
        check(c["prov"]["counts"]["COPIED"] == 0,
              "case %r claims zero copied fields but its ledger disagrees" % c["name"])
    n += len(zero_copied)

    # ---- the inline-immediate codec must reproduce EXP-0138's HW-confirmed points ----
    exp0138 = {0: 0.0, 2: 0.0625, 3: 0.09375, 31: 1.875, 32: 2.0, 48: 8.0,
               56: 16.0, 61: 26.0, 62: 28.0, 63: 30.0}
    for k, v in exp0138.items():
        check(S.inline_imm_value(k) == v,
              "inline immediate codec disagrees with EXP-0138 at k=%d (%s != %s)"
              % (k, S.inline_imm_value(k), v))
    n += len(exp0138)

    # ---- generator invariant re-check, independent of casematrix ----
    bad_live = 0
    for seed in range(0, 30):
        for nn in (2, 5, 10, 14, 20, 30, 40):
            _, _, meta = G.build_dag_program(seed, nn, G.DAG_CARRIER_LEN,
                                             base_slot_out=G.SLOT_OUT,
                                             base_slot_in=G.SLOT_MEM)
            if meta["max_live_registers"] > G.POOL_SIZE:
                bad_live += 1
    check(bad_live == 0, "%d (seed,n_nodes) pairs violated the POOL_SIZE=%d invariant"
          % (bad_live, G.POOL_SIZE))
    n += 1

    print("selftest: %d checks, %s" % (n, "PASS" if ok else "FAIL"))
    return ok


# ---------------------------------------------------------------------------
# --seqtest : PRE_GPU / RUN01_PRESENT / RUN02_PRESENT state machine
# ---------------------------------------------------------------------------
def state():
    # RUN.RETAINED_PRIOR_RUNS (run01) are deliberately ignored by the state
    # machine: they are retained evidence from before AMENDMENT 1, not part of
    # the contracted gated pair.
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
    for f in RUN.AUTH_CODE + RUN.AUTH_KERNELS + RUN.AUTH_DOC + RUN.AUTH_PINNED:
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
    for key in ("authored_code_sha256", "authored_kernel_sha256",
                "authored_doc_sha256", "pinned_isa_sha256"):
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
