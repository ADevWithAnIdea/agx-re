#!/usr/bin/env python3
"""EXP-0200 -- freeze `harness/arms200.json` from the pre-freeze calibration.

  python3 analysis/gen_arms200.py raw/prefreeze/holeprobe01

THIS DOCSTRING IS THE NORMATIVE ARM-SELECTION RULE (PRE_REGISTRATION.md 7.4).
Nothing outside it may choose an arm.

RULER ARMS (the length measurement).
  A ruler hole is a run of consecutive WALKED instructions summing to exactly
  8 bytes, starting between 2 % and 75 % of `_agc.main`. A hole is ADMITTED iff
  the pre-freeze probe showed, at that hole:
      * the carrier's unmutated baseline came back `ok` at the host oracle, AND
      * the reachability control (`stop` at +0) came back `not_written` with the
        integrity sentinel intact.
  That pair means: the hole is on the executed path, and it executes BEFORE the
  result store, which is the only condition under which the ruler can read
  anything. A hole that fails it is DROPPED and counted -- never repaired, and
  never quietly used with a weaker control (EXP-0187's `rq_ccount#0` is the
  cautionary case: an occurrence that was measured for 256 values and turned out
  to be uninterpretable because nothing ever showed it was executed).
  At most RULER_HOLES_PER_CARRIER admitted holes per carrier, EARLIEST FIRST and
  non-overlapping, so the choice is mechanical rather than outcome-shopped.

  Each ruler hole gets the ENTIRE frozen fill list from
  `harness/words200.py:ruler_fills`, with the frozen `DST_VALUES` / `B3_VALUES`.
  There is NO per-arm cap and NO hang budget: DST_VALUES deliberately contains
  four values that satisfy EXP-0187's hazard predicate `(dst & 0b110) == 0b100`,
  because the point is to test whether that wall reproduces at a program point
  the compiler never chose. Protocol 3(c): a budget cannot map a contiguous
  hazard, it guarantees the region is never mapped.

TRANSPARENCY ARMS (the substitution measurement).
  A transparency hole is a WALKED token of exactly 2 or 4 bytes whose mnemonic
  is one of the six target words (or `pad_operand`, admitted only as an extra
  2-byte slot, never as a target). At most TRANSPARENCY_HOLES_PER_MNEMONIC per
  (carrier, mnemonic), earliest first. Each gets
  `harness/words200.py:transparency_fills`, which always includes its own
  reachability control and its own over-length control, so an arm that turns out
  to be off the executed path is visible in its OWN record rather than being
  read as a transparency result.

  A transparency hole is NOT pre-screened by the probe -- the probe only sized
  ruler holes -- so its `X_reach` fill is the screen, applied at analysis time
  by `analysis/verdicts200.py`.

`value` is a GLOBALLY UNIQUE integer per (arm, fill). `tools/agx-isa/wave_audit.py`
indexes cross-run agreement by `value` alone, so a per-arm counter would make
records from different arms overwrite each other in that audit and report an
agreement figure computed over the wrong pairs.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import carriers200 as C          # noqa: E402
import locate200 as L            # noqa: E402
import words200 as W             # noqa: E402

RULER_HOLES_PER_CARRIER = 2
TRANSPARENCY_HOLES_PER_MNEMONIC = 2

# Frozen. Four of these (0x04, 0x05, 0x44, 0x45) satisfy EXP-0187's hazard
# predicate and eight do not; 0x22 and 0x42 are the two values the compiler
# itself emits. Chosen to span the predicate in both directions at a program
# point the compiler never chose.
DST_VALUES = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
              0x22, 0x42, 0x44, 0x45, 0x46, 0x7F, 0x80, 0xFF]
# Sampled, NOT dense, and explicitly NOT a `n4_cf_word.b3` field claim: that
# field carries a standing decline (EXP-0172 dispatched 256 values and reported
# STILL-UNDERPOWERED; EXP-0184 declined re-litigating it). These values ride
# along with the `_instruction` fills at zero extra design cost and are reported
# as corroboration only.
B3_VALUES = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x7F, 0x80, 0xFF]

TARGET_MNEMONICS_2B = ("n1_word", "n2_compact2", "n3_word")
TARGET_MNEMONICS_4B = ("rtq_pred", "n4_cf_word", "n4_rt_word")


def load_probe(run_dir):
    ok_holes, base_ok = {}, {}
    for ln in (Path(run_dir) / "sweep.jsonl").read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        r = json.loads(ln)
        car = r.get("carrier")
        if r.get("arm") == "carrier_open":
            base_ok[car] = (r.get("outcome") == "ok")
        if r.get("fill_id") == "C_reach":
            obs = r.get("observed") or {}
            good = (r.get("outcome") == "not_written" and obs.get("sentinel_ok"))
            ok_holes.setdefault(car, []).append(
                {"off": r["hole_off"], "admitted": bool(good),
                 "outcome": r.get("outcome"),
                 "sentinel_ok": obs.get("sentinel_ok"),
                 "covers": json.loads(r.get("note") or "{}").get("covers")})
    return base_ok, ok_holes


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    probe_dir = sys.argv[1]
    base_ok, probe = load_probe(probe_dir)

    arms, dropped, vcount = [], [], 0
    ruler_fills = W.ruler_fills(8, DST_VALUES, B3_VALUES)

    # main-bytes are needed for the transparency holes; recompiling is not
    # possible off-device, so the census result is read from the probe run's
    # carrier_ready records via analysis/census200.py output instead.
    census = json.loads((EXP / "raw" / "prefreeze" / "census200.json").read_text())

    for carrier in sorted(C.CARRIERS):
        if not base_ok.get(carrier):
            dropped.append({"carrier": carrier, "why": "baseline not ok or "
                            "carrier failed to start in the probe"})
            continue
        # ---- ruler arms -------------------------------------------------
        adm = [h for h in probe.get(carrier, []) if h["admitted"]]
        adm.sort(key=lambda h: h["off"])
        chosen, last_end = [], -1
        for h in adm:
            if h["off"] >= last_end:
                chosen.append(h)
                last_end = h["off"] + 8
            if len(chosen) >= RULER_HOLES_PER_CARRIER:
                break
        for h in probe.get(carrier, []):
            if not h["admitted"]:
                dropped.append({"carrier": carrier, "off": h["off"],
                                "why": "reachability control did not fire",
                                "outcome": h["outcome"],
                                "sentinel_ok": h["sentinel_ok"]})
        for h in chosen:
            fills = []
            for f in ruler_fills:
                vcount += 1
                g = dict(f)
                g["value"] = vcount
                fills.append(g)
            arms.append({"carrier": carrier, "kind": "ruler",
                         "arm": "%s@ruler%d" % (carrier, h["off"]),
                         "off": h["off"], "len": 8, "covers": h["covers"],
                         "fills": fills})
        # ---- transparency arms ------------------------------------------
        cc = census.get(carrier, {})
        for mn in TARGET_MNEMONICS_2B + TARGET_MNEMONICS_4B + ("pad_operand",):
            holes = cc.get("walk_holes", {}).get(mn, [])[
                :TRANSPARENCY_HOLES_PER_MNEMONIC]
            for h in holes:
                orig = bytes.fromhex(h["bytes"])
                try:
                    tf = W.transparency_fills(h["len"], orig)
                except ValueError:
                    continue
                fills = []
                for f in tf:
                    vcount += 1
                    g = dict(f)
                    g["value"] = vcount
                    fills.append(g)
                arms.append({"carrier": carrier, "kind": "transparency",
                             "arm": "%s@%s_%d" % (carrier, mn, h["off"]),
                             "off": h["off"], "len": h["len"],
                             "covers": [mn], "orig_bytes": h["bytes"],
                             "fills": fills})

    doc = {"generated_from": probe_dir,
           "rule": __doc__,
           "ruler_holes_per_carrier": RULER_HOLES_PER_CARRIER,
           "transparency_holes_per_mnemonic": TRANSPARENCY_HOLES_PER_MNEMONIC,
           "dst_values": DST_VALUES, "b3_values": B3_VALUES,
           "dropped": dropped, "arms": arms,
           "n_arms": len(arms), "n_cases": sum(len(a["fills"]) for a in arms)}
    p = EXP / "harness" / "arms200.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print("arms=%d cases=%d dropped=%d -> %s"
          % (len(arms), doc["n_cases"], len(dropped), p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
