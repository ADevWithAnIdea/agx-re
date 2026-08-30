#!/usr/bin/env python3
"""EXP-0158 -- turn the disclosed pre-freeze pilot's raw JSONL into the frozen
constants the gated generator will use.  Pure analysis; no GPU.

The rule this script enforces is that a value only enters `frozen_pilot.py` if
it was OBSERVED to deliver the correct result on the G17P, and only if that
observation survived the victim filter: any case whose fault class contains
`InnocentVictim` is DISCARDED as evidence about the machine rather than about
the encoding (NEO-TARGET-BRIEF.md, FIELD-SWEEP-PROTOCOL.md section 7).

Usage: freeze_from_pilot.py --pilot work/pilot/<file>.jsonl [--pilot more.jsonl] \
                            --run-id <id> --write
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import synth as S  # noqa: E402

VICTIM = "InnocentVictim"


def load(paths):
    rows = []
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def usable(r):
    """A row is evidence only if it is not a sibling agent's collateral damage."""
    return VICTIM not in (r.get("fault_class") or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="append", required=True)
    ap.add_argument("--ldformat", action="append", default=[])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    rows = load(a.pilot)
    keep = [r for r in rows if usable(r)]
    dropped = len(rows) - len(keep)

    def arm(name):
        return [r for r in keep if r["arm"] == name]

    # --- mod_hi accepted sets, by operand provenance --------------------------
    modhi_alu = sorted(r["params"]["mod_hi"] for r in arm("P1") if r["outcome"] == "ok")
    modhi_load = sorted(r["params"]["mod_hi"] for r in arm("P2") if r["outcome"] == "ok")
    mods_alu = sorted(r["params"]["mods"] for r in arm("P3")
                      if r["outcome"] == "ok" and r["params"]["load_sourced"] == 0)
    mods_load = sorted(r["params"]["mods"] for r in arm("P3")
                       if r["outcome"] == "ok" and r["params"]["load_sourced"] == 1)

    # --- inline immediate: magnitude model + sign convention ------------------
    p4 = [r for r in arm("P4") if r["outcome"] in ("ok", "wrong_value", "silent_zero")]
    seed = S.imm_value(3.0)
    pos_hits = neg_hits = 0
    exceptions = []
    for r in p4:
        k = r["params"]["k"]
        mag = S.inline_imm_value(k)
        obs = r["observed"]
        if obs is None:
            continue
        if abs(obs - S.f32(seed + mag)) == 0.0:
            pos_hits += 1
        elif abs(obs - S.f32(seed - mag)) == 0.0:
            neg_hits += 1
        else:
            exceptions.append({"k": k, "observed": obs,
                               "modelled_plus": S.f32(seed + mag),
                               "modelled_minus": S.f32(seed - mag)})
    sign = None
    if pos_hits or neg_hits:
        sign = 1 if pos_hits >= neg_hits else -1

    # --- does srcB_neg flip an INLINE immediate? ------------------------------
    neg_works = None
    p5 = arm("P5")
    if p5 and sign is not None:
        agree = 0
        total = 0
        for r in p5:
            if r["observed"] is None:
                continue
            total += 1
            k = r["params"]["k"]
            v = S.inline_imm_value(k) * sign
            if r["observed"] == S.f32(seed - v):
                agree += 1
        if total:
            neg_works = (agree == total)

    dl_ok, ds_ok = {}, {}
    for r in arm("P7"):
        dl_ok.setdefault(r["params"]["field"], {})[r["params"]["value"]] = r["outcome"]
    for r in arm("P8"):
        ds_ok.setdefault(r["params"]["field"], {})[r["params"]["value"]] = r["outcome"]

    p9 = [(r["params"], r["outcome"]) for r in arm("P9")]

    # --- P11: iadd2 register-mode fields, measured on G17P -------------------
    iadd_ok, iadd_all = {}, {}
    for r in keep:
        if r.get("arm") != "P11":
            continue
        iadd_all.setdefault(r["field"], {})[r["value"]] = r["outcome"]
        if r["outcome"] == "ok":
            iadd_ok.setdefault(r["field"], []).append(r["value"])
    for k in iadd_ok:
        iadd_ok[k] = sorted(set(iadd_ok[k]))

    # --- ld_format: how many REGISTERS does each code write? ------------------
    ld1reg, ldwide = [], {}
    for pth in a.ldformat or []:
        for line in Path(pth).read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d["status"] != "OK" or not d["sentinel_ok"]:
                continue
            if d["r7_got_load"] and not d["clobbered_registers"]:
                ld1reg.append(d["ld_format"])
            ldwide[str(d["ld_format"])] = {"loads_target": d["r7_got_load"],
                                           "also_writes": d["clobbered_registers"]}
    ld1reg = sorted(set(ld1reg))

    digests = {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in a.pilot}

    summary = {
        "rows_total": len(rows), "rows_used": len(keep), "rows_dropped_as_victim": dropped,
        "FALU2_MODHI_OK_ALU": modhi_alu, "FALU2_MODHI_OK_LOAD": modhi_load,
        "FALU2I_MODS_OK_ALU": mods_alu, "FALU2I_MODS_OK_LOAD": mods_load,
        "inline_positive_hits": pos_hits, "inline_negative_hits": neg_hits,
        "INLINE_NEG0_SIGN": sign, "INLINE_NEG_WORKS": neg_works,
        "INLINE_IMM_EXCEPTIONS": exceptions,
        "DL_FIELD_OK": dl_ok, "DS_FIELD_OK": ds_ok, "P9_iadd": p9,
        "IADD_FIELD_OK": iadd_ok, "IADD_FIELD_ALL": iadd_all,
        "DL_LDFORMAT_ONE_REGISTER": ld1reg, "DL_LDFORMAT_WIDTH_MAP": ldwide,
        "pilot_sha256": digests,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if not a.write:
        return
    if sign is None:
        raise SystemExit("REFUSING TO FREEZE: the pilot produced no usable inline-immediate "
                         "observation, so the sign convention is unmeasured. Re-run the "
                         "pilot (a new file, never overwriting the old one).")
    if not modhi_alu or not modhi_load:
        raise SystemExit("REFUSING TO FREEZE: no usable falu2.mod_hi observation in one of "
                         "the two operand-provenance arms.")

    body = '''#!/usr/bin/env python3
"""EXP-0158 -- constants MEASURED by this experiment's own disclosed pre-freeze
pilot (work/pilot/, PRE_REGISTRATION.md section 6) on the G17P, and frozen here
BEFORE the gated runs.  Nothing in this file is guessed and nothing is copied
from a compiled shader: every value below is the outcome of a hardware sweep
over our own generated bytes, with `InnocentVictim`-class observations
discarded as evidence about the MACHINE rather than about the encoding.

GENERATED by analysis/freeze_from_pilot.py -- do not hand-edit.
"""
FROZEN = True
PILOT_RUN_ID = %(run_id)r
PILOT_JSONL_SHA256 = %(digests)r

# sign of a falu2 inline immediate when srcB_neg == 0
INLINE_NEG0_SIGN = %(sign)r
INLINE_NEG_WORKS = %(neg_works)r
INLINE_IMM_EXCEPTIONS = %(exceptions)r

# falu2.mod_hi values that delivered the correct result, by operand provenance
FALU2_MODHI_OK_ALU = %(modhi_alu)r
FALU2_MODHI_OK_LOAD = %(modhi_load)r

# falu2i.mods values that delivered the correct result, by operand provenance
FALU2I_MODS_OK_ALU = %(mods_alu)r
FALU2I_MODS_OK_LOAD = %(mods_load)r

# device_load / device_store single-field outcomes observed on G17P
DL_FIELD_OK = %(dl_ok)r
DS_FIELD_OK = %(ds_ok)r

# device_load.ld_format codes that load the addressed 32-bit word into the
# extmode target register AND WRITE NO OTHER REGISTER.  EXP-0141 recorded 21 of
# 64 codes as "delivering the 32-bit scalar"; work/diag/diag_ldformat.jsonl
# shows most of those ALSO write 1-3 additional consecutive registers with the
# following memory words, which is invisible in a single-load probe and fatal in
# a register-allocated program.  Only these codes are safe for a scalar emitter.
DL_LDFORMAT_ONE_REGISTER = %(ld1reg)r
DL_LDFORMAT_WIDTH_MAP = %(ldwide)r

# iadd2 register-mode fields, measured on G17P by pilot arm P11.  EXP-0139
# recorded most of these as INERT on the M4; `srcA` is NOT inert here.
IADD_FIELD_OK = %(iadd_ok)r
IADD_FIELD_ALL = %(iadd_all)r
''' % {"run_id": a.run_id, "digests": digests, "sign": sign, "neg_works": neg_works,
       "exceptions": exceptions, "modhi_alu": modhi_alu, "modhi_load": modhi_load,
       "mods_alu": mods_alu, "mods_load": mods_load, "dl_ok": dl_ok, "ds_ok": ds_ok,
       "ld1reg": ld1reg, "ldwide": ldwide, "iadd_ok": iadd_ok, "iadd_all": iadd_all}
    (EXP / "frozen_pilot.py").write_text(body)
    (HERE / "pilot_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print("\\nWROTE frozen_pilot.py and analysis/pilot_summary.json")


if __name__ == "__main__":
    main()
