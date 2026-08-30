#!/usr/bin/env python3
"""EXP-0162 compute capture driver (G17P).

Runs the three EXP-0144 shards that never completed -- `cvt_bf16`,
`packed_half2_hi`, `cvt_f2h_dst` -- against a POISONED read-back buffer, and
appends one JSON object per case to raw/<run_id>/sweep.jsonl with an immediate
flush, so a kill costs at most the case in flight.

  python3 harness/runcompute.py --run-id g17p_YYYYMMDD_runNN --arm cvt_bf16

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every executed byte is the compiled form of
kernels/carriers.metal, spliced by us. No Apple binary is introspected.
"""
import argparse, json, os, struct, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import probe162 as P           # noqa: E402
import cases162 as CM          # noqa: E402
import oracle as O             # noqa: E402

BIN = EXP / "work" / "bin"
SENT0 = 0xA5C3F00D
BASELINE_EVERY = 100
MAX_HANGS = 2
VICTIM = "victim"


def u32s(b):
    return [struct.unpack("<I", b[i:i + 4])[0] for i in range(0, len(b) - 3, 4)]


def fault_class(err):
    if not err:
        return ""
    e = err.lower()
    if "innocent" in e or "victim" in e:
        return "InnocentVictim"
    if "ignored" in e:
        return "IgnoredPriorErrors"
    if "hang" in e:
        return "Hang"
    if "address fault" in e or "page fault" in e:
        return "AddressFault"
    if "interactivity" in e:
        return "Interactivity"
    if "no response" in e:
        return "Watchdog"
    return err[:60]


def sentinel_state(sent, vec0_bits):
    if not sent or len(sent) < 8:
        return "absent"
    w0, w1 = struct.unpack("<II", sent[:8])
    if w0 == SENT0 and w1 == ((vec0_bits ^ 0x5A5A5A5A) & 0xFFFFFFFF):
        return "clean"
    if w0 == P.poison_word(0) and w1 == P.poison_word(1):
        return "absent"          # poison intact -> nothing executed
    if any(sent[:8]):
        return "perturbed"
    return "absent"


def vec0_bits(carrier, vec):
    if carrier == "c_ph2":
        return struct.unpack("<I", struct.pack("<ee", vec[0], vec[1]))[0]
    ch = CM.FIXED[carrier][0][-1]
    return struct.unpack("<I", struct.pack("<" + ch, vec[0]))[0]


def classify(status, err, obs, exp, slots, mask=None):
    mask = mask or {}
    if status == "HANG":
        return "hang"
    if status != "OK":
        return "fault"
    def eq(k):
        m = mask.get(k, 0xFFFFFFFF)
        return k < len(obs) and (obs[k] & m) == (exp[k] & m)
    allm = all(exp.get(k) is None or eq(k) for k in exp)
    if allm:
        return "ok"
    res = [obs[i] if i < len(obs) else None for i in slots]
    if all(v == P.poison_word(i) for i, v in zip(slots, res)):
        return "not_written"
    if all(v == 0 for v in res) and any(exp.get(k) not in (0, None) for k in slots):
        return "silent_zero"
    return "wrong_value"


class Arm:
    def __init__(self, key, workdir, timeout):
        self.key = key
        t = CM.TARGETS[key]
        self.t = t
        self.carrier_name = t["carrier"]
        self.c = P.Carrier(EXP / "kernels" / "carriers.metal", t["carrier"],
                           BIN, workdir, fast_math=False)
        self.off = t["off"]
        anchor = bytes.fromhex(t["anchor"])
        got = self.c.main[self.off:self.off + len(anchor)]
        if got != anchor:
            raise RuntimeError("ANCHOR MISMATCH %s: want %s got %s"
                               % (key, anchor.hex(), got.hex()))
        self.base_bytes = bytes.fromhex(t["synth"]) if t["mode"] == "A" else anchor
        self.mode = t["mode"]
        self.fixed = CM.FIXED[t["carrier"]][1]
        self.slots = CM.RESULT_SLOTS[t["carrier"]]
        self.mask = CM.EXPECT_MASK[t["carrier"]]
        self.bench = P.Bench(self.c, BIN, in_buf=1,
                             in_bytes=CM.invec_bytes(t["carrier"], self.fixed),
                             out_buf=0, out_nbytes=CM.NOUT_BYTES,
                             grid=1, tg=1, timeout=timeout, sent_buf=2, sent_nbytes=16)
        self.hangs = 0

    def overrides(self, byte_index=None, value=None):
        """MODE B mutates the anchor in place; MODE A first writes the whole
        synthesised instruction over the carrier's own half_alu."""
        ov = {}
        if self.mode == "A":
            for i, b in enumerate(self.base_bytes):
                ov[self.off + i] = b
        if byte_index is not None:
            ov[self.off + byte_index] = value
        return ov

    def run_once(self, ov, vec):
        self.bench.set_input(CM.invec_bytes(self.carrier_name, vec))
        st, out, sent, gt, err = self.bench.run(ov)
        return st, u32s(out), sentinel_state(sent, vec0_bits(self.carrier_name, vec)), err

    def measure(self, ov, vec, exp, reps=3):
        """majority-of-N with the InnocentVictim / sentinel-absent discard rules."""
        votes, attempts, discarded = {}, [], 0
        n = 0
        while n < reps and discarded < 12:
            st, obs, sen, err = self.run_once(ov, vec)
            fc = fault_class(err)
            if fc in ("InnocentVictim", "IgnoredPriorErrors"):
                discarded += 1
                attempts.append({"discard": fc})
                continue
            if st == "OK" and sen == "absent":
                discarded += 1
                attempts.append({"discard": "sentinel_absent"})
                continue
            oc = classify(st, err, obs, exp, self.slots, self.mask)
            key = (oc, tuple(obs[:8]))
            votes[key] = votes.get(key, 0) + 1
            attempts.append({"outcome": oc, "fault": fc, "sent": sen})
            n += 1
            if oc == "hang":
                self.hangs += 1
                break
        if not votes:
            return "invalid_run", [], "absent", "", 0, discarded
        best = max(votes.items(), key=lambda kv: kv[1])
        if best[1] == 1 and n >= 3:      # three-way disagreement -> escalate to 5
            while n < 5 and discarded < 16:
                st, obs, sen, err = self.run_once(ov, vec)
                fc = fault_class(err)
                if fc in ("InnocentVictim", "IgnoredPriorErrors"):
                    discarded += 1
                    continue
                oc = classify(st, err, obs, exp, self.slots, self.mask)
                key = (oc, tuple(obs[:8]))
                votes[key] = votes.get(key, 0) + 1
                n += 1
            best = max(votes.items(), key=lambda kv: kv[1])
        oc, obsv = best[0]
        fc = next((a.get("fault", "") for a in attempts if a.get("outcome") == oc), "")
        return oc, list(obsv), "", fc, best[1], discarded

    def close(self):
        self.bench.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm", required=True, choices=list(CM.TARGETS))
    ap.add_argument("--out-root", default="raw")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    outdir = EXP / a.out_root / ("%s__%s" % (a.run_id, a.arm))
    if outdir.exists():
        sys.exit("run id already exists (never reuse or overwrite): %s" % outdir)
    outdir.mkdir(parents=True)
    workdir = EXP / "work" / ("run_%s_%s" % (a.run_id, a.arm))

    # ---- PRE-FLIGHT: evaluate every oracle before a single dispatch ----------
    carrier = CM.TARGETS[a.arm]["carrier"]
    for vec in CM.SEM[carrier]:
        for model in (CM.BF_MODELS if carrier == "c_f2bf" else {"RNE": None}):
            CM.expect(carrier, vec, model)
    CM.expect(carrier, CM.FIXED[carrier][1])

    arm = Arm(a.arm, workdir, a.timeout)
    f = open(outdir / "sweep.jsonl", "w")

    def rec(d):
        d.setdefault("target", "G17P")
        d.setdefault("run_id", a.run_id)
        d.setdefault("arm", a.arm)
        d.setdefault("carrier", carrier)
        f.write(json.dumps(d) + "\n")
        f.flush()
        os.fsync(f.fileno())

    meta = {"kind": "meta", "instr": a.arm, "off": arm.off,
            "anchor": CM.TARGETS[a.arm]["anchor"],
            "base_bytes": arm.base_bytes.hex(), "mode": arm.mode,
            "main_len": len(arm.c.main), "main_sha_prefix": arm.c.main[:16].hex(),
            "poison_base": "0xDEADBEEF"}
    rec(meta)

    exp_fixed = CM.expect(carrier, arm.fixed)

    def baseline(tag):
        # MODE B baseline = the UNMUTATED carrier. MODE A baseline = unmutated too,
        # so the synthesis is scored against a program known to work.
        oc, obs, _, fc, votes, disc = arm.measure({}, arm.fixed, exp_fixed, reps=3)
        rec({"kind": "baseline", "tag": tag, "instr": a.arm, "field": "-", "value": -1,
             "bytes": arm.base_bytes.hex(), "observed": {"w": obs[:8]},
             "oracle": {str(k): v for k, v in exp_fixed.items()},
             "match": oc == "ok", "outcome": oc, "fault_class": fc,
             "votes": votes, "discarded": disc, "note": "unmutated carrier"})
        return oc == "ok"

    if not baseline("pre"):
        rec({"kind": "abort", "note": "baseline failed before any mutation"})
        f.close(); arm.close()
        sys.exit("baseline failed")

    # ---- SEMANTIC VECTORS ---------------------------------------------------
    # MODE B: unmutated instruction, many inputs -> the numeric/rounding answer.
    # MODE A: the SYNTHESISED instruction, same inputs.
    ov_sem = arm.overrides()
    for vi, vec in enumerate(CM.SEM[carrier]):
        models = list(CM.BF_MODELS) if carrier == "c_f2bf" else ["RNE"]
        exp = CM.expect(carrier, vec, models[0])
        oc, obs, _, fc, votes, disc = arm.measure(ov_sem, vec, exp, reps=3)
        scored = {}
        for m in models:
            e = CM.expect(carrier, vec, m)
            scored[m] = all(k < len(obs) and (obs[k] & arm.mask.get(k, 0xFFFFFFFF))
                            == (e[k] & arm.mask.get(k, 0xFFFFFFFF)) for k in e)
        extra = {}
        if carrier == "c_ph2" and arm.mode == "A":
            w0 = obs[0] if obs else None
            extra["ph2_hi_expect"] = CM.ph2_hi(vec)
            extra["ph2_lo_expect"] = CM.ph2_lo(vec)
            extra["ph2_hi_observed"] = (w0 >> 16) if w0 is not None else None
            extra["ph2_lo_observed"] = (w0 & 0xFFFF) if w0 is not None else None
            extra["hi_lane_correct"] = (w0 is not None and (w0 >> 16) == CM.ph2_hi(vec))
            extra["both_lanes_correct"] = (w0 == CM.expect_ph2_both(vec))
            extra["hi_only_poison_low"] = (w0 == CM.expect_ph2_hi_only(vec, P.poison_word(0)))
            extra["hi_only_zero_low"] = (w0 == CM.expect_ph2_hi_lowzero(vec))
        rec({"kind": "semantic", "instr": a.arm, "field": "SEM", "value": vi,
             "bytes": arm.base_bytes.hex(), "vec": [repr(x) for x in vec],
             "observed": {"w": obs[:8]},
             "oracle": {str(k): v for k, v in exp.items()},
             "models": scored, "match": oc == "ok", "outcome": oc,
             "fault_class": fc, "votes": votes, "discarded": disc, **extra})

    # ---- BYTE SWEEPS --------------------------------------------------------
    cases = CM.byte_cases(a.arm)
    if a.limit:
        cases = cases[:a.limit]
    t0 = time.time()
    for i, (label, bi, val) in enumerate(cases):
        if arm.hangs >= MAX_HANGS:
            rec({"kind": "stop_arm", "note": "MAX_HANGS reached at case %d" % i})
            break
        if i and i % BASELINE_EVERY == 0:
            if not baseline("mid%d" % i):
                rec({"kind": "cascade", "note": "baseline failed at case %d" % i})
                break
        ov = arm.overrides(bi, val)
        mut = bytearray(arm.base_bytes)
        mut[bi] = val
        oc, obs, _, fc, votes, disc = arm.measure(ov, arm.fixed, exp_fixed, reps=3)
        rec({"kind": "sweep", "instr": a.arm, "field": label, "byte": bi, "value": val,
             "bytes": bytes(mut).hex(), "observed": {"w": obs[:8]},
             "oracle": {str(k): v for k, v in exp_fixed.items()},
             "match": oc == "ok", "outcome": oc, "fault_class": fc,
             "votes": votes, "discarded": disc, "note": ""})
    baseline("post")
    rec({"kind": "done", "cases": len(cases), "elapsed_s": round(time.time() - t0, 1),
         "hangs": arm.hangs, "runner_restarts": getattr(arm.bench.runner, "restarts", None)})
    f.close()
    arm.close()
    print("DONE %s %s" % (a.run_id, a.arm))


main()
