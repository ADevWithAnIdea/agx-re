#!/usr/bin/env python3
"""EXP-0144 analysis: cross-run gate + per-field verdicts in the
FIELD-SWEEP-PROTOCOL.md section 5 schema.

  python3 analysis/verdicts.py --runs GROUP_A GROUP_B

A "run" may be a single run id under raw/, or a run GROUP whose per-instrument
shards are raw/<group>__<instr>/. Reads raw/ only; never writes to it.
"""
import argparse, collections, json, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import casematrix as CM      # noqa: E402
import oracle as O           # noqa: E402
import rules as R            # noqa: E402
import isadb                 # noqa: E402  read-only

GATED = ["i", "name", "instr", "field", "value", "bytes", "observed", "match",
         "outcome", "validity", "decode"]
M32 = 0xFFFFFFFF
DBI = {i["mnemonic"]: i for i in json.loads(isadb.to_json())["instructions"]}


def load_run(name):
    """`name` may be a run id, a run GROUP (its raw/<group>__* shards are merged),
    or several of either joined by '+'. When two sources carry the same case, a
    VALID record beats a skipped/invalid one -- that is how a run whose instrument
    was skipped can be completed by a later capture without either being edited."""
    recs, bad, shards = {}, 0, []
    for part in name.split("+"):
        dirs = sorted(EXP.glob("raw/%s__*" % part)) or [EXP / "raw" / part]
        for d in dirs:
            f = d / "sweep.jsonl"
            if not f.exists():
                continue
            shards.append(d.name)
            for line in f.read_text().splitlines():
                try:
                    r = json.loads(line)
                except Exception:
                    bad += 1
                    continue
                prev = recs.get(r["i"])
                if prev is None or (prev.get("validity") != "valid"
                                    and r.get("validity") == "valid"):
                    recs[r["i"]] = r
    return recs, bad, shards


def words(rec):
    if not rec.get("observed"):
        return []
    b = bytes.fromhex(rec["observed"])
    return list(struct.unpack("<%dI" % (len(b) // 4), b))


def db_fields_for_byte(mnem, b):
    d = DBI.get(mnem)
    if not d:
        return []
    lo, hi = 8 * b, 8 * b + 8
    return [f["name"] for f in d["fields"] if f["start"] < hi and (f["start"] + f["width"]) > lo]


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    a = ap.parse_args()

    runs, meta = {}, {}
    for r in a.runs:
        recs, bad, shards = load_run(r)
        runs[r] = recs
        meta[r] = {"n": len(recs), "unparsable": bad, "shards": shards}
        print("%s: %d records, %d shards" % (r, len(recs), len(shards)))

    r1 = a.runs[0]
    r2 = a.runs[1] if len(a.runs) > 1 else None

    # A REVALIDATION run carries its own reproducibility: every case is measured
    # N times in the same process and the verdict is the majority over attempts that
    # were themselves clean (no InnocentVictim, sentinel present). For such a run the
    # stability criterion is INTERNAL -- a cross-run gate would be the wrong test,
    # because the thing being controlled for is per-attempt machine noise, not
    # per-run drift.
    is_reval = any("votes" in r for r in list(runs[r1].values())[:50])

    # ---------------- cross-run gate --------------------------------------
    gate = {"runs": a.runs, "gated_keys": GATED, "meta": meta}
    stable = set()
    if r2:
        common = sorted(set(runs[r1]) & set(runs[r2]))
        excl_inv = excl_iv = ident = diff = 0
        diffs, per_instr = [], collections.Counter()
        for i in common:
            x, y = runs[r1][i], runs[r2][i]
            if x["validity"] != "valid" or y["validity"] != "valid":
                excl_inv += 1
                continue
            if "InnocentVictim" in (x.get("err") or "") or "InnocentVictim" in (y.get("err") or ""):
                excl_iv += 1
                continue
            if all(x.get(k) == y.get(k) for k in GATED):
                ident += 1
                stable.add(i)
            else:
                diff += 1
                per_instr[x["instr"]] += 1
                if len(diffs) < 60:
                    diffs.append({"i": i, "name": x["name"],
                                  **{k: [x.get(k), y.get(k)] for k in GATED if x.get(k) != y.get(k)}})
        gate.update(n_common=len(common), excluded_invalid=excl_inv,
                    excluded_innocent_victim=excl_iv, identical=ident, differing=diff,
                    pct_identical=round(100.0 * ident / max(1, ident + diff), 3),
                    differing_by_instr=dict(per_instr), sample_differences=diffs)
        print("GATE: %d/%d byte-identical (%.3f%%); excluded %d invalid, %d innocent-victim"
              % (ident, ident + diff, gate["pct_identical"], excl_inv, excl_iv))
    elif is_reval:
        stable = {i for i, r in runs[r1].items()
                  if r.get("validity") == "valid" and r.get("n_clean", 0) >= 3}
        una = sum(1 for i in stable if runs[r1][i].get("unanimous"))
        esc = sum(1 for i in stable if runs[r1][i].get("n_clean", 0) > 3)
        ind = sum(1 for r in runs[r1].values() if r.get("validity") == "indeterminate")
        nrun = sum(1 for r in runs[r1].values() if r.get("validity") == "not_run")
        disc = collections.Counter()
        for r in runs[r1].values():
            for at in r.get("attempts", []):
                if at.get("discarded"):
                    disc[at["discarded"]] += 1
        gate.update(mode="majority-of-N revalidation (internal stability)",
                    n_stable=len(stable), unanimous_at_3=una, escalated_to_5=esc,
                    indeterminate=ind, not_run=nrun,
                    pct_unanimous=round(100.0 * una / max(1, len(stable)), 3),
                    discarded_attempts=dict(disc))
        print("REVALIDATION: %d stable cases, %d unanimous at 3 reps (%.2f%%), "
              "%d escalated, %d indeterminate, %d not run"
              % (len(stable), una, gate["pct_unanimous"], esc, ind, nrun))
    else:
        stable = set(runs[r1])
        gate["note"] = "single run -- NOT gated"

    prim = runs[r1]
    cases = {c["i"]: c for c in CM.build_cases()}

    # ---------------- per (instr, byte) analysis ---------------------------
    scans = collections.defaultdict(list)
    xarm = collections.defaultdict(list)
    warm = collections.defaultdict(list)
    for i, rec in prim.items():
        if i not in stable or rec["validity"] != "valid":
            continue
        if rec["arm"] == "F":
            scans[(rec["instr"], rec["byte"])].append(rec)
        elif rec["arm"] == "X":
            xarm[(rec["instr"], rec["byte"])].append(rec)
        elif rec["arm"] == "W":
            warm[(rec["instr"], rec["field"])].append(rec)

    verdicts, notes = {}, {}
    for (instr, byte), recs in sorted(scans.items()):
        tgt = next(t for t in CM.TARGETS if t["mnem"] == instr)
        carrier, vec = tgt["carrier"], CM.FIXED[tgt["carrier"]][1]
        slot = CM.RESULT_SLOTS[carrier][0]
        half = carrier in ("c_f2h", "c_f2h_dst", "c_f2bf")
        interp = _interp(carrier, vec)
        anchor = bytes.fromhex(tgt["synth"] if tgt["mode"] == "A" else tgt["anchor"])
        universe = sorted({r["value"] for r in recs})
        okv = [r["value"] for r in recs if r["outcome"] == "ok"]
        oc = collections.Counter(r["outcome"] for r in recs)
        sent = collections.Counter(r.get("sentinel_state") for r in recs)

        # SILENT-ZERO DISCRIMINATION (coordinator rule 4 / the EXP-0140-overturns-
        # EXP-0128 trap). A zero in the result slot can mean "the instruction wrote
        # zero / did not write its destination" OR "nothing was stored at all and we
        # are reading a zero-initialised buffer". These carriers make the two
        # separable WITHOUT assuming anything: besides the instruction's own result
        # they store six OTHER live values through the same device_store path. If
        # those companion slots still carry their host-predicted values, the store
        # path demonstrably ran, so the zero is a real read of a register that holds
        # zero. Only if the companions are ALSO wrong is the case ambiguous.
        want_all = CM.expect(carrier, vec)
        companions = [k for k in want_all if k not in CM.RESULT_SLOTS[carrier]]
        sz_disc = sz_ambig = 0
        for r in recs:
            if r["outcome"] != "silent_zero":
                continue
            wl = words(r)
            intact = all(k < len(wl) and wl[k] == want_all[k] for k in companions)
            if intact:
                sz_disc += 1
            else:
                sz_ambig += 1

        # what did each value actually produce?
        meanings = collections.Counter()
        opmap = {0: [], 1: []}
        for r in recs:
            w = words(r)
            lab = _label(w[slot] if len(w) > slot else 0, interp, half)
            meanings[lab] += 1
            idxs = _operand_indices(lab)
            for pos in (0, 1):
                opmap[pos].append((r["value"], idxs.get(pos)))

        # DESTINATION REDIRECTION: the instruction's own result normally lands in
        # output slot `slot`. If a dst-field value sends it to a register the carrier
        # stores somewhere ELSE, the conversion result appears in a different slot --
        # which is what turns "only the anchor value works" into a real dst map.
        want = CM.expect(carrier, vec)[slot]
        redirect = collections.defaultdict(list)
        for r in recs:
            w = words(r)
            if len(w) <= slot or w[slot] == want:
                continue
            for k, wv in enumerate(w[:8]):
                if k != slot and wv == want and want != 0:
                    redirect[k].append(r["value"])
        rule = R.bit_rule(okv, universe)
        om = {}
        for pos in (0, 1):
            pts = [(v, i) for v, i in opmap[pos] if i is not None]
            if len({i for _v, i in pts}) < 2:
                continue                      # this position never moved: not a source
            fit = R.operand_map(opmap[pos])
            if fit.get("kind") in ("linear", "table"):
                om["operand%d" % pos] = fit
        dbf = db_fields_for_byte(instr, byte)
        key = "%s.byte%d" % (instr, byte)
        verdicts[key] = {
            "instr": instr, "byte": byte, "db_fields": dbf,
            "anchor_value": anchor[byte],
            "n_values_executed": len(recs), "coverage": _cov(universe),
            "outcomes": dict(oc), "sentinel_states": dict(sent),
            "bit_rule": rule, "operand_map": om,
            "silent_zero_discriminated": sz_disc, "silent_zero_ambiguous": sz_ambig,
            "dst_redirect_slots": {str(k): sorted(v)[:16] for k, v in sorted(redirect.items())},
            "observed_meanings": dict(meanings.most_common(10)),
            "target": "M4", "evidence": ["EXP-0144"],
        }

    # ---------------- format maps from the X arm ---------------------------
    fmt = {}
    for (instr, byte), recs in sorted(xarm.items()):
        tgt = next(t for t in CM.TARGETS if t["mnem"] == instr)
        carrier = tgt["carrier"]
        slot = CM.RESULT_SLOTS[carrier][0]
        mfn = R.pack_models if carrier == "c_pack" else R.unpack_models
        vec_of = (lambda r: cases[r["i"]]["vec"])
        m = R.format_map(recs, mfn, slot, vec_of)
        fmt["%s.byte%d" % (instr, byte)] = {
            "n_values_with_a_model": len(m),
            "codes": {("0x%02x" % k): v for k, v in sorted(m.items())},
        }

    # ---------------- wide-field arms --------------------------------------
    wide = {}
    for (instr, field), recs in sorted(warm.items()):
        oc = collections.Counter(r["outcome"] for r in recs)
        okv = [r["value"] for r in recs if r["outcome"] == "ok"]
        wide["%s.%s" % (instr, field)] = {
            "n_values_executed": len(recs), "outcomes": dict(oc),
            "values_reproducing_anchor": ["0x%x" % v for v in sorted(okv)][:32],
            "target": "M4", "evidence": ["EXP-0144"]}

    (HERE / "gate_report.json").write_text(json.dumps(gate, indent=1, sort_keys=True))
    (HERE / "byte_scans.json").write_text(json.dumps(verdicts, indent=1, sort_keys=True))
    (HERE / "format_maps.json").write_text(json.dumps(fmt, indent=1, sort_keys=True))
    (HERE / "wide_fields.json").write_text(json.dumps(wide, indent=1, sort_keys=True))
    print("wrote gate_report / byte_scans (%d) / format_maps (%d) / wide_fields (%d)"
          % (len(verdicts), len(fmt), len(wide)))


# ------------------------- helpers ----------------------------------------
def _cov(universe):
    return ("%d of 256 values (dense 0..255)" % len(universe) if len(universe) > 200
            else "%d values: %s" % (len(universe), ",".join("0x%02x" % v for v in universe[:32])))


def _interp(carrier, vec):
    m = {}
    def put(v, lab):
        m.setdefault(v & M32, lab)
    n = len(vec)
    if carrier == "c_pack":
        for i in range(n):
            for j in range(n):
                put(O.pack_unorm2x16(vec[i], vec[j]), "unorm2x16(v%d,v%d)" % (i, j))
                put(O.pack_snorm2x16(vec[i], vec[j]), "snorm2x16(v%d,v%d)" % (i, j))
                put((O.f16_bits(vec[i]) | (O.f16_bits(vec[j]) << 16)) & M32,
                    "half2x16(v%d,v%d)" % (i, j))
        for i in range(n):
            put(O.f32_bits(vec[i]), "raw(v%d)" % i)
    elif carrier == "c_unpack":
        for i in range(n):
            x, y = O.unpack_unorm2x16(vec[i]); sx, sy = O.unpack_snorm2x16(vec[i])
            put(O.f32_bits(x), "unorm_lo(v%d)" % i); put(O.f32_bits(y), "unorm_hi(v%d)" % i)
            put(O.f32_bits(sx), "snorm_lo(v%d)" % i); put(O.f32_bits(sy), "snorm_hi(v%d)" % i)
            put(O.f32_bits(O.bits_f16(vec[i] & 0xFFFF)), "half_lo(v%d)" % i)
            put(O.f32_bits(O.u2f(vec[i])), "u2f(v%d)" % i)
            put(vec[i], "raw(v%d)" % i)
    elif carrier in ("c_i2f", "c_i2f_src"):
        for i in range(n):
            put(O.f32_bits(O.i2f(vec[i] & M32)), "i2f(v%d)" % i)
            put(O.f32_bits(O.u2f(vec[i] & M32)), "u2f(v%d)" % i)
            put(vec[i] & M32, "raw(v%d)" % i)
            for j in range(n):
                s = struct.unpack("<f", struct.pack("<f", O.i2f(vec[i] & M32) + O.i2f(vec[j] & M32)))[0]
                put(O.f32_bits(s), "i2f(v%d)+i2f(v%d)" % (i, j))
    elif carrier == "c_f2i":
        for i in range(n):
            put(O.f2i(vec[i]), "f2i(v%d)" % i); put(O.f2u(vec[i]), "f2u(v%d)" % i)
            put(O.f32_bits(vec[i]), "raw(v%d)" % i)
    elif carrier in ("c_f2h", "c_f2h_dst", "c_f2bf"):
        for i in range(n):
            put(O.f16_bits(vec[i]), "f2h(v%d)" % i)
            put(O.f2bf_rne(vec[i]), "f2bf_rne(v%d)" % i)
            put(O.f2bf_trunc(vec[i]), "f2bf_trunc(v%d)" % i)
            put(O.f32_bits(vec[i]) & 0xFFFF, "lo16raw(v%d)" % i)
    elif carrier == "c_ph2":
        hb = [O.f16_bits(x) for x in vec]
        for i in range(len(hb)):
            for j in range(len(hb)):
                put(O.hmul(hb[i], hb[j]), "hmul(h%d,h%d)" % (i, j))
        for i in range(0, len(hb) - 1, 2):
            put(hb[i] | (hb[i + 1] << 16), "raw(v%d)" % (i // 2))
    return m


def _label(w, interp, half):
    if w == 0:
        return "zero"
    if w in interp:
        return interp[w]
    if half:
        lo, hi = w & 0xFFFF, w >> 16
        if lo in interp:
            return interp[lo]
    return "unknown"


def _operand_indices(lab):
    """Which live value(s) did this result come from, by OPERAND POSITION?
    A two-operand pack label carries a distinct index per lane, and a sweep of one
    byte typically moves exactly one of them -- which is how the per-lane source
    bytes are told apart from a whole-instruction source descriptor."""
    import re
    m = re.match(r"^(?:unorm2x16|snorm2x16|half2x16)\(v(\d+),v(\d+)\)$", lab)
    if m:
        return {0: int(m.group(1)), 1: int(m.group(2))}
    m = re.match(r"^\w+\(v(\d+)\)$", lab)
    if m:
        return {0: int(m.group(1))}
    return {}


if __name__ == "__main__":
    main()
