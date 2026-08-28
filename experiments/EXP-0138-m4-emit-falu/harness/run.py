#!/usr/bin/env python3
"""EXP-0138 gated sweep runner.

  harness/run.py --run <run_id> [--groups G1,...] [--limit N]

Executes every case from `harness/families.py` on the local M4 and appends one
JSON object per case to `raw/<run_id>/sweep.jsonl`, flushed immediately
(FIELD-SWEEP-PROTOCOL section 4). Never buffers results in memory.

Contamination mitigations (protocol section 7 + EXP-0140's poison correction)
live in `harness/bench.py`; this file adds the two that need case context:

  * BASELINE RE-VALIDATION every `--baseline-every` cases per carrier. A
    failed baseline means a GPU error cascade: the child process is restarted
    and the event is recorded in `raw/<run_id>/cascades.json`.
  * INTEGRITY SENTINEL per case. MODE A: the control register r11, written by
    a `falu2i` independent of the instruction under test, must read back 26.0
    AND the untouched words of the poisoned output buffer must still hold
    0xDEADBEEF. MODE B: the poison must be gone from out[0], and where the
    carrier has a second output that word is an independent-path sentinel.
    A case failing its sentinel is `invalid_run`, never a field observation.
"""
import argparse, json, math, struct, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb                    # noqa: E402  (read-only)
import isa_helpers as H         # noqa: E402
import families as F            # noqa: E402
import bench as B               # noqa: E402

BIN = EXP / "work" / "bin"
POISON_F = B.POISON_F


def close(a, b):
    if a is None or b is None:
        return False
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b or abs(a - b) <= 1e-6 * max(1.0, abs(b))
    return a == b


def make_bench(carrier, work):
    if carrier == "carrier":
        return B.Bench(EXP / "kernels" / "carrier.metal", "k", BIN, work)
    if carrier == "carrier_uni":
        return B.Bench(EXP / "kernels" / "carrier_uni.metal", "k", BIN, work)
    c = F.CARRIERS_B[carrier]
    return B.Bench(EXP / "kernels" / c["src"], c["fn"], BIN, work, fast_math=c["fast"])


def carrier_io(carrier, bench):
    """Returns (ins, outs, nwords, decode) for a carrier."""
    if carrier in ("carrier", "carrier_uni"):
        ins = {0: bench.poison_file(64), 1: bench.write_in(1, [float(i) for i in range(16)])}
        if carrier == "carrier_uni":
            ins[2] = bench.write_in(2, F.UNI_VALS)
        return ins, {0: 64}, 16, "f32"
    c = F.CARRIERS_B[carrier]
    n = c["nout"]
    ins = {0: bench.poison_file(n), 1: bench.write_in(1, c["mem"], fmt=c["pack"])}
    return ins, {0: n}, n // (2 if c["dec"] == "half" else 4), c["dec"]


def decode_out(raw, dec, n):
    if dec == "half":
        return B.halfs(raw, n)
    return B.words_f32(raw, n)


def roundtrip_ok(prog):
    try:
        H.assert_round_trip(prog)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--groups", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--baseline-every", type=int, default=200)
    a = ap.parse_args()

    run_dir = EXP / "raw" / a.run
    if run_dir.exists():
        raise SystemExit("run id %s already exists -- never reuse or overwrite a run id" % a.run)
    run_dir.mkdir(parents=True)
    work = EXP / "work" / ("bw_" + a.run)

    cases = F.all_cases()
    if a.groups:
        want = set(a.groups.split(","))
        cases = [c for c in cases if c["group"] in want]
    if a.limit:
        cases = cases[:a.limit]
    # group by carrier so each carrier needs only one persistent child
    order = ["carrier_uni", "carrier"] + list(F.CARRIERS_B)
    cases.sort(key=lambda c: (order.index(c["carrier"]), c["i"]))

    env = {"run": a.run, "host": "Apple M4 (G16G) local", "os": "macOS 26.6.2 (25G82)",
           "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "n_cases": len(cases),
           "poison": "0x%08x" % B.POISON, "python": sys.version.split()[0]}
    (run_dir / "00_env.json").write_text(json.dumps(env, indent=1))

    out = open(run_dir / "sweep.jsonl", "w")
    cascades = []
    bench = None
    cur = None
    counts = {}
    t0 = time.time()
    try:
        for n, c in enumerate(cases):
            if c["carrier"] != cur:
                if bench:
                    bench.close()
                cur = c["carrier"]
                bench = make_bench(cur, work)
                ins, outs, nwords, dec = carrier_io(cur, bench)
                since_base = 0
                base_prog = None
                if cur in ("carrier", "carrier_uni"):
                    base_instr = H.falu2_raw(F.D, 0, 2, opflags5=0)
                    base_prog = H.build_program(F.modeA(base_instr), bench.region_len)
                else:
                    cc = F.CARRIERS_B[cur]
                    got = bench.main_bytes[cc["off"]:cc["off"] + len(cc["anchor"]) // 2]
                    if got.hex() != cc["anchor"]:
                        raise SystemExit("carrier %s anchor moved: %s != %s"
                                         % (cur, got.hex(), cc["anchor"]))
            # ---- periodic baseline re-validation (protocol 7.3) ----------
            if since_base >= a.baseline_every:
                since_base = 0
                if base_prog is not None:
                    r = bench.run([(0, base_prog)], ins=ins, outs=outs)
                    w = decode_out(r["outs"].get(0, b""), dec, nwords)
                    ok = r["status"] == "OK" and len(w) > 4 and close(w[0], F.FADD) and close(w[4], F.CTL)
                else:
                    r = bench.run([], ins=ins, outs=outs)
                    ok = r["status"] == "OK"
                if not ok:
                    cascades.append({"after_case": n, "carrier": cur,
                                     "status": r["status"], "error": (r.get("error") or "")[:200]})
                    bench.restart("baseline failed after case %d" % n)
            ib = bytes.fromhex(c["instr_bytes"])
            if c["mode"] == "A":
                prog = H.build_program(F.modeA(ib, c["dst_reg"]), bench.region_len)
                pairs = [(0, prog)]
                rt = roundtrip_ok(prog)
            else:
                cc = F.CARRIERS_B[cur]
                if len(ib) != len(cc["anchor"]) // 2:
                    raise SystemExit("MODE B splice length mismatch for %s" % c["instr"])
                pairs = [(cc["off"], ib)]
                recs, left = isadb.disassemble(ib)
                rt = (not left) and len(recs) == 1
            resp = bench.run(pairs, ins=ins, outs=outs)
            since_base += 1
            words = decode_out(resp["outs"].get(0, b""), dec, nwords)
            rec = {"i": c["i"], "instr": c["instr"], "field": c["field"], "value": c["value"],
                   "bytes": c["instr_bytes"], "carrier": c["carrier"], "group": c["group"],
                   "mode": c["mode"], "note": c["note"], "expect_match": c["expect_match"],
                   "oracle": c["oracle"], "status": resp["status"],
                   "fault_class": resp.get("outcome_class"),
                   "attempts": resp.get("attempts"), "victim_retries": resp.get("victim_retries", 0),
                   "roundtrip": rt}
            if c["mode"] == "A":
                obs = {"w0": words[0] if len(words) > 0 else None,
                       "w4": words[4] if len(words) > 4 else None,
                       "w8": words[8] if len(words) > 8 else None}
                sentinel = (obs["w4"] is not None and close(obs["w4"], F.CTL))
                untouched = all(close(words[k], POISON_F) for k in (1, 2, 3) if k < len(words))
                key, pred = "w0", c["oracle"].get("w0")
            else:
                obs = {"o0": words[0] if len(words) > 0 else None,
                       "o1": words[1] if len(words) > 1 else None,
                       "o2": words[2] if len(words) > 2 else None}
                sentinel = obs["o0"] is not None and not close(obs["o0"], POISON_F)
                untouched = True
                key, pred = "o0", c["oracle"].get("o0")
            rec["observed"] = obs
            rec["sentinel_ok"] = bool(sentinel)
            rec["poison_intact"] = bool(untouched)
            got = obs[key]
            if resp["status"] != "OK":
                rec["outcome"] = {"victim": "victim", "hang": "hang"}.get(resp.get("outcome_class"), "fault")
                rec["match"] = False
            elif not sentinel:
                rec["outcome"] = "invalid_run"
                rec["match"] = False
            elif pred is None:
                rec["outcome"] = "exploratory"
                rec["match"] = False
            elif close(got, pred):
                rec["outcome"] = "ok"
                rec["match"] = True
            elif got is not None and close(got, 0.0):
                rec["outcome"] = "silent_zero"
                rec["match"] = False
            elif got is not None and close(got, POISON_F):
                rec["outcome"] = "invalid_run"
                rec["match"] = False
            else:
                rec["outcome"] = "wrong_value"
                rec["match"] = False
            if not rt and rec["outcome"] in ("wrong_value", "silent_zero", "fault"):
                rec["outcome_note"] = "instruction does not round-trip at this value " \
                                      "(length/decoder reclassification)"
            counts[rec["outcome"]] = counts.get(rec["outcome"], 0) + 1
            out.write(json.dumps(rec, sort_keys=True) + "\n")
            out.flush()
            if n % 500 == 0:
                print("  %5d/%d  %s  %s  %.0fs" % (n, len(cases), cur,
                      dict(sorted(counts.items())), time.time() - t0), flush=True)
    finally:
        if bench:
            print("victim_retries=%d repeats=%d hangs=%d restarts=%d"
                  % (bench.victim_retries, bench.repeats, bench.hangs, bench.restarts))
            bench.close()
        out.close()
        (run_dir / "01_summary.json").write_text(json.dumps(
            {"counts": counts, "cascades": cascades,
             "elapsed_s": round(time.time() - t0, 1)}, indent=1))
        (run_dir / "cascades.json").write_text(json.dumps(cascades, indent=1))
    print("DONE", a.run, counts)


if __name__ == "__main__":
    main()
