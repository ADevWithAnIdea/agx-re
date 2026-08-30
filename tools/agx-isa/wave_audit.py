#!/usr/bin/env python3
"""Re-derive a proposed verdict from the experiment's OWN raw. Trust nothing.

Every problem found on 2026-08-30 was found by re-deriving a claim from raw
rather than reading the claim. Nine experiments are landing at once, so this
consolidates the day's lessons into one gate that runs on arrival.

Per proposed field verdict it reports, from raw only:

  V  distinct VALID payloads      -- the Case-C test. A field with V<=1 across
                                     many legal values ran legally and was
                                     INDISTINGUISHABLE; its "movement" is a
                                     hazard map, not a semantic.
  L  legal values observed
  hard-outcome counts kept SEPARATE from valid payloads. A gate that lumps them
     counts a GPU fault as evidence (found twice today: `fault` as movement, and
     `undecodable` -- our own disassembler -- as movement, with status OK and
     byte-identical output).
  oracle discrimination -- distinct oracle payloads. A CONSTANT oracle across a
     varying field predicts the instruction's effect, not the field's.
  cross-run agreement per value, and moved vs disagree.
  aliasing -- distinct encodings actually dispatched. A sweep can dispatch 256
     values while the hardware sees 8 distinct bytes (DEF-0166-1).

It does NOT decide. It prints what raw says so the orchestrator can rule.
"""
import json, os, sys, collections, glob

HARD = {"fault", "no_draw", "hang", "undecodable", "timeout", "CMDBUF_ERROR",
        "wedge", "MALFORMED", "innocent_victim"}


def is_hard(rec):
    for k in ("outcome", "status", "class"):
        v = rec.get(k)
        if isinstance(v, str) and (v in HARD or v.upper() in {h.upper() for h in HARD}):
            return v
    return None


def load_records(expdir):
    """Every jsonl record under raw/, tagged with its run directory."""
    out = []
    for f in sorted(glob.glob(os.path.join(expdir, "raw", "**", "*.jsonl"),
                              recursive=True)):
        run = os.path.basename(os.path.dirname(f))
        for line in open(f, errors="replace"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            r["_run"] = run
            out.append(r)
    return out


def match_field(recs, mnem, field):
    """Field-name keying AND the field:null byte sweeps a name index cannot see.

    71,262 of one experiment's 71,898 records carry field: null -- byte-level
    sweeps keyed by instruction. A field-name query alone manufactures a false
    ABSENCE, which is how six notes came to claim evidence did not exist.
    """
    named = [r for r in recs if r.get("instr") == mnem and r.get("field") == field]
    unnamed = [r for r in recs if r.get("instr") == mnem and r.get("field") in (None, "")]
    return named, unnamed


def report(expdir, mnem, field, spec):
    recs = load_records(expdir)
    named, unnamed = match_field(recs, mnem, field)
    use = named if named else unnamed
    tag = "field-keyed" if named else ("field:null byte sweep" if unnamed else "NONE")
    print("  %-34s %s" % (mnem + "." + field, spec.get("label", "?")))
    if not use:
        print("       NO RAW RECORDS under either keying  <-- claim unsupported by this raw")
        return
    hard = collections.Counter()
    valid = []
    for r in use:
        h = is_hard(r)
        if h:
            hard[h] += 1
        else:
            valid.append(r)
    V = len({json.dumps(r.get("observed"), sort_keys=True) for r in valid})
    L = len({r.get("value") for r in use})
    orc = len({json.dumps(r.get("oracle"), sort_keys=True) for r in use})
    byt = len({r.get("bytes") for r in use if r.get("bytes")})
    # DEF-0202-2 (found by EXP-0202 against this tool): the cross-run figure was
    # wrong twice over. It pooled by `value` ACROSS arms -- and when a run uses
    # reverse case order a different arm wins per run, so identical hardware
    # reads as a disagreement -- and it compared `observed` verbatim, including
    # `gputime_ns`, which never repeats. It reported 0-25% agreement on an
    # experiment whose true figure is 0 disagreements on all nine fields.
    VOLATILE = ("gputime_ns", "gpu_time_ns", "duration_ns", "timestamp", "elapsed_ns")

    def stable(o):
        if isinstance(o, dict):
            return json.dumps({k: v for k, v in o.items() if k not in VOLATILE},
                              sort_keys=True)
        return json.dumps(o, sort_keys=True)

    runs = collections.defaultdict(dict)
    for r in valid:
        arm = r.get("arm") or r.get("carrier") or r.get("group") or ""
        runs[r["_run"]][(arm, r.get("value"))] = stable(r.get("observed"))
    agree = "n/a (1 run)"
    rk = sorted(runs)
    if len(rk) >= 2:
        a, b = runs[rk[0]], runs[rk[1]]
        common = set(a) & set(b)
        dis = [v for v in common if a[v] != b[v]]
        agree = ("%.2f%% (%d/%d disagree)"
                 % (100 * (1 - len(dis) / max(len(common), 1)), len(dis), len(common)))
    print("       records=%-6d via %-22s runs=%d" % (len(use), tag, len(rk)))
    print("       V(distinct VALID payloads)=%-5d L(legal values)=%-5d  %s"
          % (V, L, "<-- V<=1: INDISTINGUISHABLE, hazard map not semantic" if V <= 1 else ""))
    print("       distinct oracles=%-5d %s" % (orc, "<-- CONSTANT ORACLE: predicts the "
          "instruction, not the field" if orc <= 1 else ""))
    print("       distinct encodings dispatched=%-5d %s" % (byt,
          "<-- ALIASED: fewer bytes than values" if byt and byt < L else ""))
    print("       hard outcomes (NOT movement): %s" % (dict(hard) or "none"))
    print("       cross-run agreement: %s  [keyed (arm,value); volatile timing fields excluded]"
          % agree)


def selftest():
    """This gate must be able to say no. Thirteen checks in this corpus could not."""
    ok = True
    good = [{"instr": "x", "field": "f", "value": i, "observed": {"w": i},
             "oracle": {"w": i}, "bytes": "%02x" % i, "status": "OK"} for i in range(4)]
    bad = [{"instr": "x", "field": "f", "value": i, "observed": {"w": 0},
            "oracle": {"w": 0}, "bytes": "00", "status": "OK"} for i in range(4)]
    gV = len({json.dumps(r["observed"], sort_keys=True) for r in good})
    bV = len({json.dumps(r["observed"], sort_keys=True) for r in bad})
    if not (gV == 4 and bV == 1):
        print("SELFTEST FAIL: V discrimination gV=%d bV=%d" % (gV, bV)); ok = False
    f = [{"instr": "x", "field": "f", "value": 1, "outcome": "fault"}]
    if is_hard(f[0]) is None:
        print("SELFTEST FAIL: a fault was not classed as a hard outcome"); ok = False
    if is_hard(good[0]) is not None:
        print("SELFTEST FAIL: a clean record was classed as hard"); ok = False
    u = {"instr": "x", "field": "f", "outcome": "undecodable"}
    if is_hard(u) is None:
        print("SELFTEST FAIL: `undecodable` (our own disassembler) counted as movement")
        ok = False
    # DEF-0202-2 regression: the same (arm, value) with only a timing field
    # differing is NOT a disagreement, and two arms sharing a value are not
    # comparable to each other.
    a = {"w": 1, "gputime_ns": 111}
    b = {"w": 1, "gputime_ns": 999}
    if _stable_probe(a) != _stable_probe(b):
        print("SELFTEST FAIL: a volatile timing field counts as a cross-run disagreement")
        ok = False
    if _stable_probe({"w": 1}) == _stable_probe({"w": 2}):
        print("SELFTEST FAIL: a real payload difference is being masked")
        ok = False
    return ok


def _stable_probe(o):
    VOLATILE = ("gputime_ns", "gpu_time_ns", "duration_ns", "timestamp", "elapsed_ns")
    return json.dumps({k: v for k, v in o.items() if k not in VOLATILE}, sort_keys=True)


def main():
    if not selftest():
        return 2
    if len(sys.argv) < 2:
        print(__doc__)
        print("usage: wave_audit.py <experiment-dir> [...]")
        return 0
    for expdir in sys.argv[1:]:
        vf = os.path.join(expdir, "analysis", "field_verdicts.json")
        print("\n=== %s" % expdir)
        if not os.path.exists(vf):
            print("  no analysis/field_verdicts.json yet")
            continue
        doc = json.load(open(vf))
        for key, spec in sorted(doc.items()):
            if key.startswith("_") or "." not in key:
                continue
            m, f = key.split(".", 1)
            report(expdir, m, f, spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
