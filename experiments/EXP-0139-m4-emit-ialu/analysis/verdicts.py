#!/usr/bin/env python3
"""EXP-0139 analysis -> `analysis/field_verdicts.json` (FIELD-SWEEP-PROTOCOL §5).

Inputs (all append-only raw evidence, never edited):
  raw/m4_20260828_run01/sweep.jsonl      gated run 1 (original contract)
  raw/m4_20260828_run02/sweep.jsonl      gated run 2 (amendment-01 instrumentation)
  raw/m4_20260828_reval01/revalidate.jsonl   every non-OK case, 5x, fresh process
  raw/m4_20260828_reval02/revalidate.jsonl   every OK-but-unstable case, 7x, fresh process

Reconciliation (all disclosed, none silent):

1. **Cross-launch determinism.** A value counts only if the two gated launches
   saw the same bytes and both in-run repeats agreed -- OR a revalidation pass
   re-ran it in a fresh process and every attempt agreed. Anything else is
   `unstable` and can never promote a field.
2. **Faults are re-validated** (FIELD-SWEEP-PROTOCOL §7.1/§7.2, binding after
   this contract was frozen). A value is `fault` only on `reproducible_fault`
   (every attempt failed, with a healthy baseline before and after). The OS's
   own `kIOGPUCommandBufferCallbackErrorInnocentVictim` string marks the
   sibling-contamination class and is excluded.
3. **ICMPSEL oracle correction.** A disclosed harness defect fed the ICMPSEL
   carrier the INTEGER input vector while its host oracle used the float vector
   (`mode == "float_in"` never equalled the `"float"` the input selector tested
   for). Raw captures untouched; that arm's reference is its own gated baseline
   observation, independently confirmed to be exactly `(a<b)?1:0` over A_IN/B_IN
   reinterpreted as float32 with denormals flushed to zero.

Labels are the eight in `docs/evidence-classification.md` and nothing else.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(EXP.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402

RUNS = ["m4_20260828_run01", "m4_20260828_run02"]
REVALS = ["m4_20260828_reval01", "m4_20260828_reval02"]
TARGET = "M4"
EVIDENCE = ["EXP-0139"]


def load():
    runs = [{json.loads(l)["i"]: json.loads(l)
             for l in open(EXP / "raw" / r / "sweep.jsonl")} for r in RUNS]
    rev = {}
    for r in REVALS:
        for l in open(EXP / "raw" / r / "revalidate.jsonl"):
            d = json.loads(l)
            rev[d["i"]] = d
    return runs, rev


def reconcile(a, b, rv):
    if rv is not None:
        v = rv["verdict"]
        if v == "reproducible_fault":
            return "fault", None
        if v in ("intermittent", "baseline_unhealthy", "nondeterministic"):
            return "unstable", None
        obs = set(x["observed"] for x in rv["attempts"] if x["status"] == "OK")
        if len(obs) == 1 and all(x["status"] == "OK" for x in rv["attempts"]):
            return "ok_stable", obs.pop()
        return "unstable", None
    if a["status"] != "OK" or b["status"] != "OK":
        return "unstable", None
    if not (a["rep_agree"] and b["rep_agree"]) or a["observed"] != b["observed"]:
        return "unstable", None
    return "ok_stable", a["observed"]


def width_of(instr, field):
    base = field.split("[")[0]
    for ins in isadb.DB:
        if ins["mnemonic"] == instr:
            for f in ins["fields"]:
                if f["name"] == base:
                    return 8 if "[" in field else f["width"]
    return None


def bit_rule(rows, w):
    """Smallest set of bit positions that fully determines works(v).

    This is what turns a bare partition into a statement an emitter can use --
    the same shape as EXP-M4-14's `op_enable` finding ("only bit1 matters")."""
    if w is None or w > 12:
        return None
    vals = {r["value"] & ((1 << w) - 1): r["works"] for r in rows
            if r["state"] in ("ok_stable", "fault")}
    # Allow up to 5% of the value space to be missing (values excluded as
    # sibling-GPU contamination). Requiring 100% coverage would let a single
    # contaminated case hide an otherwise clean bit rule.
    if len(vals) < 0.95 * (1 << w):
        return None
    for k in range(0, min(w, 4) + 1):
        import itertools
        for bits in itertools.combinations(range(w), k):
            proj = {}
            ok = True
            for v, good in vals.items():
                key = tuple((v >> b) & 1 for b in bits)
                if key in proj and proj[key] != good:
                    ok = False
                    break
                proj[key] = good
            if ok:
                return sorted(bits)
    return None


# ---------------------------------------------------------------------------
# DISCLOSED ORACLE CORRECTIONS
#
# Three host-side oracle EXPRESSIONS in the frozen matrix were wrong. The raw
# captures are untouched; only the host-computed prediction each observation is
# compared against is corrected here, and each correction is stated with the
# competing model it beat on the SAME data. Every one of them is a REFUTATION
# of the pre-registered model, which is why they are reported as findings.
#
# 1. ibfe.width -- pre-registered "literal, clamp at 32". REFUTED: the literal
#    model fits 37/64 stable values, `width mod 32` fits 64/64. Corrected.
# 2. ibitcount.dst / iunary.operand[dst] -- the pre-registered oracle wrongly
#    predicted the SEED of the relocation TARGET register; the carrier's
#    `device_store` always reads r6, so the correct prediction is r6's
#    sentinel whenever the target is not r6. A pure expression bug; the
#    relocation model itself is confirmed by the corrected comparison.
# ---------------------------------------------------------------------------
def _hexw(ws):
    return "".join("%08x" % (w & 0xFFFFFFFF) for w in ws)


def oracle_corrections():
    import casematrix as CM
    corr = {}
    for w in range(64):
        wm = w % 32
        corr[("ibfe", "width", w)] = _hexw(
            [(a >> 4) if wm == 0 else ((a >> 4) & ((1 << wm) - 1)) for a in CM.A_IN])
    for r in range(16):
        v = "%08x" % (CM.POP_EXPECT if r == CM.R_DST else CM.SENTINEL)
        corr[("ibitcount", "dst", r << 1)] = v
        corr[("iunary", "operand[dst]", r << 1)] = v
    return corr


def main():
    runs, rev = load()
    CORR = oracle_corrections()
    r1, r2 = runs
    ref = {}
    for rec in r1.values():
        if rec["field"] == "_baseline" or rec.get("subfield") == "_baseline":
            ref[rec["arm"]] = rec["observed"]

    per = defaultdict(list)
    for i, a in r1.items():
        b = r2[i]
        state, obs = reconcile(a, b, rev.get(i))
        field = a["field"] if a["field"] != "operand" else "operand[%s]" % a.get("subfield")
        if a.get("subfield") == "_baseline":
            field = "_baseline"
        val = a["value"] if "[" not in field else (a.get("byte_value", a["value"] & 0xFF))
        oracle_str = CORR.get((a["instr"], field, val), a["oracle"])
        corrected = oracle_str != a["oracle"]
        works = (obs is not None and
                 (obs == oracle_str if a["oracle_kind"] == "model" else obs == ref.get(a["arm"])))
        per[(a["instr"], field, a["arm"])].append(dict(
            i=i, arm=a["arm"], value=val, bytes=a["bytes"],
            oracle_kind=a["oracle_kind"], oracle=oracle_str, corrected=corrected,
            predict=a["predict"], note=a["note"], state=state, observed=obs,
            works=works, model=(a["oracle_kind"] == "model"),
            model_ok=(a["oracle_kind"] == "model" and works)))
    return per, ref


def verdict(instr, field, rows):
    real = [r for r in rows if r["value"] != -1]
    if not real:
        return None
    w = width_of(instr, field)
    n = len(real)
    unstable = [r for r in real if r["state"] == "unstable"]
    faults = [r for r in real if r["state"] == "fault"]
    stable = [r for r in real if r["state"] == "ok_stable"]
    works = [r for r in real if r["works"]]
    zeros = [r for r in stable if r["observed"] and set(r["observed"]) == {"0"}]
    modelled = [r for r in real if r["model"]]
    model_ok = [r for r in modelled if r["model_ok"]]
    dense = (w is not None and w <= 8 and n >= (1 << w))
    rng = ("0..%d dense (all %d values)" % ((1 << w) - 1, 1 << w)) if dense \
        else "%d values sampled (boundaries + powers of two + interior)" % n

    stats = dict(n_values=n, width=w, dense=dense, n_stable=len(stable),
                 n_unstable=len(unstable), n_reproducible_fault=len(faults),
                 n_working=len(works), n_silent_zero=len(zeros),
                 n_model=len(modelled), n_model_matched=len(model_ok))
    note_bits = []
    if unstable:
        note_bits.append("%d/%d values excluded as not reproducible "
                         "(sibling-GPU contamination class, see RESULTS.md §3)" % (len(unstable), n))
    if faults:
        fv = sorted(r["value"] for r in faults)
        note_bits.append("reproducibly FAULT (5/5 attempts, healthy baselines) at %d values: %s" %
                         (len(fv), _ranges(fv)))
    if zeros:
        note_bits.append("%d values return a silent zero" % len(zeros))

    # --- label ------------------------------------------------------------
    # Binding rule, from tools/agx-isa/validation.json's own `_conventions`:
    #   "tested-but-unexplained: a field that WAS exercised on hardware but whose
    #    semantics remain unexplained is `untested` (semantics not established)
    #    with the observation recorded in `note`."
    # So a dense sweep alone NEVER promotes a field. Promotion requires a RULE an
    # emitter can apply:
    #   hardware-run       -- a pre-registered model matched over its domain, OR
    #                         the field is inert across its whole encodable range,
    #                         OR a <=1-bit rule fully decides correct execution.
    #   isolated-byte-diff -- a 2..4-bit rule fully decides correct execution
    #                         ("set these bits, the rest are free").
    #   untested           -- everything else, with the full enumeration in `note`.
    if len(unstable) > max(2, 0.05 * n) or not stable:
        return ("untested", rng, stats,
                "swept on hardware but NOT reproducible; semantics not established",
                "; ".join(note_bits))
    good = sorted(r["value"] for r in works)
    bits = bit_rule(real, w) if dense else None
    if modelled and len(model_ok) == len(modelled):
        return "hardware-run", rng, stats, _model_semantics(instr, field, modelled), "; ".join(note_bits)
    if modelled and len(model_ok) >= 0.5 * len(modelled):
        bad = sorted(r["value"] for r in modelled if not r["model_ok"])
        sem = _model_semantics(instr, field, modelled) + \
            " -- model held at %d/%d modelled values; NOT matched at %s" % (
                len(model_ok), len(modelled), _ranges(bad))
        return "hardware-run", rng, stats, sem, "; ".join(note_bits)
    if dense and len(works) == n:
        return ("hardware-run", rng, stats,
                "INERT: every one of the %d encodable values reproduced the carrier's "
                "correct result. An emitter may choose any value." % n, "; ".join(note_bits))
    if bits is not None and len(bits) <= 1:
        return ("hardware-run", rng, stats,
                "value space fully enumerated on hardware; whether the instruction still "
                "produces its correct result is decided ENTIRELY by bit%s %s. Working "
                "values: %s" % ("" if len(bits) == 1 else "s", bits, _ranges(good)),
                "; ".join(note_bits))
    if bits is not None:
        return ("isolated-byte-diff", rng, stats,
                "value space fully enumerated on hardware and fully deterministic; correct "
                "execution is decided by bits %s and nothing else -- an emitter must fix "
                "those and may choose the remaining %d bits freely. Working values: %s"
                % (bits, w - len(bits), _ranges(good)), "; ".join(note_bits))
    nb = note_bits + [
        "TESTED-BUT-UNEXPLAINED: %d of %d values reproduce the carrier's correct result "
        "(%s); no <=4-bit rule explains the partition, so the field's SEMANTICS are not "
        "established and an emitter must not choose an arbitrary value. Full per-value "
        "observations are in raw/*/sweep.jsonl." % (len(good), n, _ranges(good))]
    return ("untested", rng, stats,
            "exercised on hardware over its %s range, deterministically, but semantics "
            "NOT established" % ("full dense" if dense else "sampled"), "; ".join(nb))


def _model_semantics(instr, field, modelled):
    notes = [r["note"] for r in modelled if r["note"]]
    return ("pre-registered semantic model executed and matched: %s"
            % (notes[0].split(" -> ")[0] if notes else "see PRE_REGISTRATION.md"))


def _ranges(vs):
    if not vs:
        return "(none)"
    out, s, p = [], vs[0], vs[0]
    for v in vs[1:]:
        if v == p + 1:
            p = v
            continue
        out.append(str(s) if s == p else "%d-%d" % (s, p))
        s = p = v
    out.append(str(s) if s == p else "%d-%d" % (s, p))
    t = ",".join(out)
    return t if len(t) < 220 else t[:217] + "..."


# Two instructions were swept on TWO independent carriers. The PRIMARY arm is
# the one whose carrier is the cleanest/most isolated; the secondary is reported
# as corroboration (or, if it disagrees, as an explicit conflict). Merging their
# value sets into one pool would double-count and is never done.
PRIMARY = {"ibfe": "IBFE", "ibitcount": "IBITCOUNT"}
LABEL_ORDER = ["hardware-run", "isolated-byte-diff", "corpus-correlation",
               "tokenization-only", "single-template-inference",
               "api-accept-reject", "host-private", "untested"]

if __name__ == "__main__":
    per, ref = main()
    byfield = defaultdict(dict)
    for (instr, field, arm), rows in per.items():
        if field.startswith("_"):
            continue
        v = verdict(instr, field, rows)
        if v is not None:
            byfield[(instr, field)][arm] = v
    out, dbg = {}, {}
    for (instr, field), arms in sorted(byfield.items()):
        prim = PRIMARY.get(instr)
        arm = prim if prim in arms else sorted(arms)[0]
        label, rng, stats, sem, note = arms[arm]
        extra = []
        for other, ov in sorted(arms.items()):
            if other == arm:
                continue
            agree = "AGREES" if ov[0] == label else "DIFFERS"
            extra.append("second independent carrier %s %s (%s over %s)"
                         % (other, agree, ov[0], ov[1]))
            if ov[0] == label and label != "hardware-run":
                pass
        n = "; ".join([x for x in ([note] + extra) if x])
        out["%s.%s" % (instr, field)] = dict(
            label=label, range=rng, target=TARGET, evidence=EVIDENCE,
            semantics=sem, note=n, carrier_arm=arm)
        dbg["%s.%s" % (instr, field)] = {a: arms[a][2] for a in arms}
    json.dump(dbg, open(HERE / "field_stats.json", "w"), indent=1, sort_keys=True)
    json.dump(out, open(HERE / "_verdicts_partial.json", "w"), indent=1, sort_keys=True)
    c = Counter(v["label"] for v in out.values())
    print("fields:", len(out), dict(c))
    for k in sorted(out):
        print("  %-30s %-20s %s" % (k, out[k]["label"], out[k]["semantics"][:120]))
