#!/usr/bin/env python3
"""EXP-0090 frozen case matrix (single source of truth for run.py/verify.py/
analysis.py). 21 cases across P1/P2/P3 -- the three programs that reached a
working, hardware-validated design (see PROGRESS.md / RESULTS.md for P4's
negative result, excluded from capture). Every case's oracle is computed
purely in Python from programs.py's independent model -- never from a GPU
run.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import programs as P   # noqa: E402
import isa_helpers as H  # noqa: E402

MEM_WORDS = [float(i) for i in range(2100)]   # P2 read buffer backing, big enough for every idx_off case (max byte off ~8188 -> word 2047)


def _p1(name, **kw):
    base = dict(p=[3.0, 4.0, 5.0], k1=2.0, k2=0.5, k3=-1.0, ia0=1000000000, int_k=100)
    base.update(kw)
    prog, oracle, meta = P.build_p1(**base)
    return {"name": name, "item": "P1", "program": "p1", "params": base,
            "hex": prog.hex(), "oracle": oracle, "meta": meta}


def _p2(name, **kw):
    base = dict(mem_words=MEM_WORDS, idx_ld=3, off_ld=5, code_ld=3, slot_ld=1,
                idx_st=2, off_st=10, tk=7)
    base.update(kw)
    prog, oracle, meta = P.build_p2(**base)
    d = dict(base)
    d.pop("mem_words")
    return {"name": name, "item": "P2", "program": "p2", "params": d,
            "hex": prog.hex(), "oracle": oracle, "meta": meta}


def _p3(name, **kw):
    base = dict(a_val=50.0, n_val=3)
    base.update(kw)
    prog, oracle, meta = P.build_p3(**base)
    return {"name": name, "item": "P3", "program": "p3", "params": base,
            "hex": prog.hex(), "oracle": oracle, "meta": meta}


def build_cases():
    cases = []
    cases.append(_p1("p1_baseline"))
    cases.append(_p1("p1_imm_zero", k1=0.0))
    cases.append(_p1("p1_imm_max", k1=30.0))
    cases.append(_p1("p1_imm_negmax", k3=-30.0))
    cases.append(_p1("p1_int_k0", int_k=0))
    cases.append(_p1("p1_int_k127", int_k=127))
    cases.append(_p1("p1_liveness_violate", liveness_violate=True))

    cases.append(_p2("p2_baseline"))
    cases.append(_p2("p2_off_zero", idx_ld=0, off_ld=0))
    cases.append(_p2("p2_off_mid", idx_ld=0, off_ld=1000))
    cases.append(_p2("p2_off_max", idx_ld=0, off_ld=2047))
    cases.append(_p2("p2_off_firstinvalid", idx_ld=0, off_ld=2048))   # 11-bit field: masks to 0 -- tests the field's own boundary
    for code in (0, 1, 2, 4):
        cases.append(_p2("p2_elemcode%d" % code, code_ld=code, off_ld=0, idx_ld=1))
    cases.append(_p2("p2_slot_mirror", slot_ld=1 + 128))     # EXP-0083 7-bit mirror

    cases.append(_p3("p3_baseline"))
    cases.append(_p3("p3_trip0", n_val=0))
    cases.append(_p3("p3_trip1", n_val=1))
    cases.append(_p3("p3_trip_large", n_val=20))
    cases.append(_p3("p3_select_true", a_val=150.0))
    cases.append(_p3("p3_cond_flip", cond_override=7))       # s_gt(6) -> s_lt(7): flips which arm is natural for the SAME data
    cases.append(_p3("p3_liveness_violate", a_val=150.0, liveness_violate=True))

    for i, c in enumerate(cases):
        c["i"] = i
    return cases


def full_case_list():
    return build_cases()


if __name__ == "__main__":
    cs = build_cases()
    print("cases:", len(cs))
    for c in cs:
        print(" ", c["i"], c["name"], c["item"])
