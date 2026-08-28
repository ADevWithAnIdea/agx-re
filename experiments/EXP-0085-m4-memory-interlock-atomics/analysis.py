#!/usr/bin/env python3
"""EXP-0085 analysis: reads two closed raw run trees, checks the cross-run
gate (byte-identical on every key except each case's declared
order-sensitive keys; fenced class (d)), recomputes the frozen expected
value/invariant for every case independently of the harness, and writes
analysis.json (OBSERVED vs INTERPRETED).

Usage: python3 -B analysis.py --run-a ID --run-b ID --write
"""
import argparse, json, struct, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM

RAW = HERE / "raw"


def load_run(run_id):
    d = RAW / run_id
    results = [json.loads(l) for l in (d / "04_results.jsonl").read_text().splitlines() if l.strip()]
    receipts = [json.loads(l) for l in (d / "05_receipts.jsonl").read_text().splitlines() if l.strip()]
    manifest = json.loads((d / "06_run_manifest.json").read_text())
    inputs = json.loads((d / "00_inputs.json").read_text())
    return {"results": {r["i"]: r for r in results}, "receipts": receipts,
            "manifest": manifest, "inputs": inputs}


def cross_run_gate(run_a, run_b):
    """Byte-identity gate excluding each case's order-sensitive keys.
    Returns (ok, issues[])."""
    issues = []
    ra, rb = run_a["results"], run_b["results"]
    if set(ra) != set(rb):
        issues.append("case index sets differ between runs")
        return False, issues
    for case in CM.MATRIX:
        i = case["i"]
        if i not in ra:
            continue
        excl = CM.case_order_sensitive_keys(case)
        a, b = ra[i], rb[i]
        for k in CM.RESULT_KEYS_BY_FAMILY[case["family"]]:
            if k in excl:
                continue
            if a.get(k) != b.get(k):
                issues.append(f"case {i} ({case['name']}) key {k} differs: {a.get(k)!r} != {b.get(k)!r}")
    return (len(issues) == 0), issues


def provenance_gate(run_a, run_b):
    ia, ib = run_a["inputs"], run_b["inputs"]
    issues = []
    if ia["git_revision"] != ib["git_revision"]:
        issues.append("git_revision differs")
    if ia["authored_sha256"] != ib["authored_sha256"]:
        issues.append("authored_sha256 differs")
    return (len(issues) == 0), issues


# ---------------------------------------------------------------------------
# Deterministic input reconstruction (must mirror harness fill formulas
# EXACTLY -- harness/atomics_probe.m and harness/interlock_probe.m).
# ---------------------------------------------------------------------------
def deltas_u(n):
    return [(i % 251) + 1 for i in range(n)]


def deltas_i(n):
    return [(i % 251) + 1 for i in range(n)]  # always positive in this matrix


def deltas_f(n):
    return [float((i % 251) + 1) for i in range(n)]


def tags(n):
    return [0x10000 + i for i in range(n)]


def hexN(h, width):
    """Split a hex string into a list of little-endian ints of `width` bytes."""
    step = width * 2
    return [int.from_bytes(bytes.fromhex(h[k:k + step]), "little") for k in range(0, len(h), step)]


def hexN_signed(h, width):
    step = width * 2
    return [int.from_bytes(bytes.fromhex(h[k:k + step]), "little", signed=True) for k in range(0, len(h), step)]


def combine_rmw(op, a, b, dtype):
    mask = (1 << 32) - 1 if dtype != "u64" else (1 << 64) - 1
    if op == "da_add" or op == "da_add_static0":
        return (a + b) & mask
    if op == "da_sub":
        return (a - b) & mask
    if op == "da_and":
        return a & b
    if op == "da_or":
        return a | b
    if op == "da_xor" or op == "da_xor_static0":
        return a ^ b
    if op == "da_umin" or op == "da_umin_static0" or op == "da_umin64":
        return min(a, b)
    if op == "da_umax" or op == "da_umax64":
        return max(a, b)
    if op == "da_smin":
        return min(a, b)
    if op == "da_smax":
        return max(a, b)
    if op == "da_fadd":
        return a + b
    TG_TO_DEV = {"ta_add": "da_add", "ta_sub": "da_sub", "ta_min": "da_umin", "ta_max": "da_umax"}
    if op in TG_TO_DEV:
        return combine_rmw(TG_TO_DEV[op], a, b, dtype)
    raise ValueError(op)


def check_atomic(case, res):
    kernel, shape, dtype, n = case["kernel"], case["shape"], case["dtype"], case["n"]
    addr = case.get("addr")
    tcount = case.get("tcount") or (1 if addr == "uniform" else n)
    width = 8 if dtype == "u64" else 4
    obs = {"status": res.get("status")}
    if res.get("status") != "ok":
        return {"verdict": "N/A", "reason": f"status={res.get('status')}", "observed": obs}

    if shape == "dev_rmw" or shape == "tg_rmw":
        init_hex = case["init"]
        init = int.from_bytes(bytes.fromhex(init_hex), "little")
        if dtype == "f32":
            ds = deltas_f(n)
            init_f = struct.unpack("<f", bytes.fromhex(init_hex))[0]
        elif dtype == "i32":
            ds = deltas_i(n)
        else:
            ds = deltas_u(n)

        if shape == "tg_rmw":
            # target lives in threadgroup memory, 256 slots, readback via tg_result_hex
            th = res.get("tg_result_hex")
            if th is None:
                return {"verdict": "FAIL", "reason": "missing tg_result_hex", "observed": obs}
            slots = hexN(th, 4)
            expect = [init] * 256
            if addr == "uniform":
                acc = init
                for d in ds:
                    acc = combine_rmw(kernel, acc, d, "u32")
                expect[0] = acc
            else:
                for i in range(n):
                    expect[i] = combine_rmw(kernel, init, ds[i], "u32")
            ok = (slots == expect)
            return {"verdict": "PASS" if ok else "FAIL",
                    "observed": {"tg_result_first8": slots[:8], "status": "ok"},
                    "expected_first8": expect[:8]}
        else:
            tf = res.get("target_final_hex")
            if tf is None:
                return {"verdict": "FAIL", "reason": "missing target_final_hex", "observed": obs}
            if dtype == "f32":
                if addr == "uniform":
                    got = struct.unpack("<f", bytes.fromhex(tf))[0]
                    acc = init_f
                    for d in ds:
                        acc = acc + d
                    exp = acc
                    ok = (got == exp)
                    return {"verdict": "PASS" if ok else "FAIL",
                            "observed": {"target_final": got}, "expected": exp}
                else:
                    got_slots = [struct.unpack("<f", bytes.fromhex(tf[k:k+8]))[0] for k in range(0, len(tf), 8)]
                    exp_slots = [init_f + ds[i] for i in range(n)]
                    ok = (got_slots == exp_slots)
                    return {"verdict": "PASS" if ok else "FAIL",
                            "observed": {"target_final_first8": got_slots[:8]},
                            "expected_first8": exp_slots[:8]}
            else:
                signed = (dtype == "i32")
                if addr == "uniform":
                    got = int.from_bytes(bytes.fromhex(tf), "little", signed=signed)
                    acc = init if not signed else int.from_bytes(init_hex and bytes.fromhex(init_hex) or b"\0\0\0\0", "little", signed=True)
                    for d in ds:
                        acc = combine_rmw(kernel, acc, d, dtype)
                        if signed:
                            acc = ((acc + 2**31) % 2**32) - 2**31
                    ok = (got == acc)
                    return {"verdict": "PASS" if ok else "FAIL",
                            "observed": {"target_final": got}, "expected": acc}
                else:
                    got_slots = hexN_signed(tf, width) if signed else hexN(tf, width)
                    init_signed = init if not signed else int.from_bytes(bytes.fromhex(init_hex), "little", signed=True)
                    exp_slots = [combine_rmw(kernel, init_signed, ds[i], dtype) for i in range(n)]
                    if signed:
                        exp_slots = [((v + 2**31) % 2**32) - 2**31 for v in exp_slots]
                    ok = (got_slots == exp_slots)
                    return {"verdict": "PASS" if ok else "FAIL",
                            "observed": {"target_final_first8": got_slots[:8]},
                            "expected_first8": exp_slots[:8]}

    if shape in ("dev_exch", "tg_exch"):
        init = int.from_bytes(bytes.fromhex(case["init"]), "little")
        tg = tags(n)
        oo = hexN(res["old_out_hex"], 4)
        if shape == "dev_exch":
            tf_raw = res.get("target_final_hex")
            final = int.from_bytes(bytes.fromhex(tf_raw), "little") if tf_raw else None
        else:
            th = res.get("tg_result_hex")
            slots = hexN(th, 4) if th else None
            final = slots[0] if slots else None
        if addr == "indexed":
            exp_final_slots = tg[:n] if shape == "dev_exch" else (tg[:n] + [init]*(256-n))
            if shape == "dev_exch":
                got_slots = hexN(res["target_final_hex"], 4)
                ok = (got_slots == exp_final_slots) and (oo == [init]*n)
            else:
                slots = hexN(res["tg_result_hex"], 4)
                ok = (slots == exp_final_slots) and (oo == [init]*n)
            return {"verdict": "PASS" if ok else "FAIL", "observed": {"old_out_first8": oo[:8]}}
        elif kernel in ("da_exch_noret", "da_store"):
            # No-return-value forms: old_out[tid] is DELIBERATELY set to
            # deltas[tid] by the kernel (see kernels/atomics.metal), not the
            # exchange's actual pre-op value, so the old_out/tag permutation
            # invariant does not apply here. The only checkable invariant
            # for a discard-return exchange under uniform-address contention
            # is that the last write wins: final must be SOME lane's tag
            # (the exchange still happened atomically), and old_out must be
            # exactly deltas (proving the discard path truly ignored the
            # atomic's return rather than corrupting the register).
            ds = deltas_u(n)
            ok = (final in set(tg)) and (oo == ds)
            return {"verdict": "PASS" if ok else "FAIL",
                    "reason": "no-return-form invariant: final in tags (some lane's write won); old_out == deltas (return value never consumed)",
                    "observed": {"final": final, "old_out_first8": oo[:8]}}
        else:
            from collections import Counter
            lhs = Counter(oo); lhs[final] += 1
            rhs = Counter(tg); rhs[init] += 1
            ok = (lhs == rhs)
            return {"verdict": "PASS" if ok else "FAIL",
                    "reason": "permutation invariant: multiset(old_out + {final}) == multiset(tags + {init})",
                    "observed": {"final": final, "old_out_first8": oo[:8]}}

    if shape in ("dev_cmpxchg", "tg_cmpxchg"):
        init = int.from_bytes(bytes.fromhex(case["init"]), "little")
        tg = tags(n)
        oo = hexN(res["old_out_hex"], 4)
        succ = res.get("success_out")
        if shape == "dev_cmpxchg":
            final = int.from_bytes(bytes.fromhex(res["target_final_hex"]), "little")
        else:
            final = hexN(res["tg_result_hex"], 4)[0]
        if addr == "indexed":
            got_slots = hexN(res["target_final_hex"], 4) if shape == "dev_cmpxchg" else hexN(res["tg_result_hex"], 4)[:n]
            ok = (got_slots == tg[:n]) and all(s == 1 for s in succ) and (oo == [init] * n)
            return {"verdict": "PASS" if ok else "FAIL", "observed": {"num_success": sum(succ)}}
        else:
            winners = [k for k, s in enumerate(succ) if s == 1]
            ok = (len(winners) == 1)
            if ok:
                w = winners[0]
                ok = ok and (final == tg[w]) and (oo[w] == init)
                ok = ok and all(oo[k] == final for k in range(n) if k != w)
            return {"verdict": "PASS" if ok else "FAIL",
                    "reason": "single-winner invariant: exactly 1 success; final==winner tag; every loser observed final as old",
                    "observed": {"num_success": sum(succ), "winners": winners, "final": final}}

    return {"verdict": "UNKNOWN", "reason": f"no checker for shape {shape}"}


def check_ordering_probe(case, res):
    status = res.get("status")
    err = res.get("compile_err") or ""
    ok_seqcst = "argument must be" in err and "memory_order_relaxed" in err
    ok_acqrel = "memory_order_acq_rel" in err
    verdict = "PASS" if (status == "compile_fail" and ok_seqcst and ok_acqrel) else "FAIL"
    return {"verdict": verdict, "observed": {"status": status,
            "seqcst_rejected": ok_seqcst, "acqrel_undeclared": ok_acqrel}}


def check_interlock(case, res):
    kernel, n, af = case["kernel"], case["n"], case.get("afactor", 1)
    if res.get("status") != "ok":
        return {"verdict": "N/A", "reason": f"status={res.get('status')}"}
    oh = res.get("out_hex")
    out = [struct.unpack("<f", bytes.fromhex(oh[k:k+8]))[0] for k in range(0, len(oh), 8)]
    a_full = [float(j % 97) for j in range(n * af)]
    b = [float((i % 89) + 1) for i in range(n)]
    idxg = [(i * 7 + 3) % n for i in range(n)]

    if kernel == "il_load_alu":
        exp = [a_full[i] * 2.0 + 1.0 for i in range(n)]
        return {"verdict": "PASS" if out == exp else "FAIL", "observed": {"out_first8": out[:8]}}
    if kernel == "il_gather":
        exp = [a_full[idxg[i]] * 3.0 + 2.0 for i in range(n)]
        return {"verdict": "PASS" if out == exp else "FAIL", "observed": {"out_first8": out[:8]}}
    if kernel == "il_store_src":
        exp = [a_full[i] * b[i] - a_full[i] for i in range(n)]
        return {"verdict": "PASS" if out == exp else "FAIL", "observed": {"out_first8": out[:8]}}
    if kernel == "il_chain48":
        exp = []
        for i in range(n):
            s = 0.0
            for k in range(48):
                s += a_full[i * 48 + k]
            exp.append(s)
        return {"verdict": "PASS" if out == exp else "FAIL", "observed": {"out_first8": out[:8]}}
    if kernel == "il_atomic_alu":
        olds = [(v - 1.0) / 2.0 for v in out]
        ints_ok = all(o == int(o) for o in olds)
        olds_i = sorted(int(o) for o in olds)
        perm_ok = ints_ok and (olds_i == list(range(n)))
        atom_ok = (res.get("atom_final") == n)
        ok = perm_ok and atom_ok
        return {"verdict": "PASS" if ok else "FAIL",
                "reason": "permutation invariant: recovered {old} == {0..N-1}; atom_final==N",
                "observed": {"atom_final": res.get("atom_final"), "perm_ok": perm_ok}}
    if kernel == "il_atomic_src":
        addends = [int(a_full[i] + b[i]) for i in range(n)]
        exp_final = sum(addends) % (2**32)
        ok = (res.get("atom_final") == exp_final)
        return {"verdict": "PASS" if ok else "FAIL",
                "reason": "commutative-sum invariant: atom_final == sum(a[i]+b[i]) mod 2^32",
                "observed": {"atom_final": res.get("atom_final")}, "expected": exp_final}
    return {"verdict": "UNKNOWN", "reason": f"no checker for kernel {kernel}"}


def check_tex(case, res):
    if res.get("status") != "ok":
        return {"verdict": "N/A", "reason": f"status={res.get('status')}"}
    w, h = case["w"], case["h"]
    oh = res["out_hex"]
    out = [struct.unpack("<f", bytes.fromhex(oh[k:k+8]))[0] for k in range(0, len(oh), 8)]
    exp = []
    for y in range(h):
        for x in range(w):
            texel = ((y * w + x) % 251) / 255.0
            exp.append(texel * 2.0 + 1.0)
    max_abs = max(abs(o - e) for o, e in zip(out, exp))
    bit_exact = all(struct.pack("<f", o) == struct.pack("<f", struct.unpack("<f", struct.pack("<f", e))[0]) for o, e in zip(out, exp))
    ok = max_abs < 1e-5
    return {"verdict": "PASS" if ok else "FAIL", "observed": {"max_abs_err": max_abs}}


def analyze_case(case, res):
    fam = case["family"]
    if fam == "atomic":
        return check_atomic(case, res)
    if fam == "ordering_probe":
        return check_ordering_probe(case, res)
    if fam == "interlock":
        return check_interlock(case, res)
    if fam == "interlock_tex":
        return check_tex(case, res)
    return {"verdict": "UNKNOWN"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-b", required=True)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    run_a = load_run(args.run_a)
    run_b = load_run(args.run_b)

    gate_ok, gate_issues = cross_run_gate(run_a, run_b)
    prov_ok, prov_issues = provenance_gate(run_a, run_b)

    per_case = {}
    verdict_counts = {"PASS": 0, "FAIL": 0, "N/A": 0, "UNKNOWN": 0}
    for case in CM.MATRIX:
        i = case["i"]
        res_a = run_a["results"].get(i)
        v = analyze_case(case, res_a) if res_a else {"verdict": "UNKNOWN", "reason": "missing"}
        per_case[i] = {"name": case["name"], "atom_item": case["atom_item"], **v}
        verdict_counts[v["verdict"]] = verdict_counts.get(v["verdict"], 0) + 1

    mem13_kernels = {"il_load_alu", "il_gather", "il_atomic_alu", "il_chain48"}
    mem14_kernels = {"il_store_src", "il_atomic_src"}
    mem13_cases = [c for c in CM.MATRIX
                   if c["family"] == "interlock_tex"
                   or (c["family"] == "interlock" and c.get("kernel") in mem13_kernels)]
    mem14_cases = [c for c in CM.MATRIX if c["family"] == "interlock" and c.get("kernel") in mem14_kernels]
    mem13_verdicts = [per_case[c["i"]]["verdict"] for c in mem13_cases]
    mem14_verdicts = [per_case[c["i"]]["verdict"] for c in mem14_cases]
    mem13_ok = all(v == "PASS" for v in mem13_verdicts) and len(mem13_verdicts) > 0
    mem14_ok = all(v == "PASS" for v in mem14_verdicts) and len(mem14_verdicts) > 0

    atom_items = {}
    for case in CM.MATRIX:
        item = case["atom_item"]
        atom_items.setdefault(item, []).append(per_case[case["i"]]["verdict"])
    atom_summary = {k: {"cases": len(v), "pass": v.count("PASS"), "fail": v.count("FAIL"),
                        "na": v.count("N/A"), "unknown": v.count("UNKNOWN")}
                    for k, v in atom_items.items()}

    out = {
        "schema": "exp0085.analysis.v1",
        "run_a": args.run_a, "run_b": args.run_b,
        "cross_run_gate": {"pass": gate_ok, "issues": gate_issues[:50], "issues_total": len(gate_issues)},
        "provenance_gate": {"pass": prov_ok, "issues": prov_issues},
        "verdict_counts": verdict_counts,
        "mem13": {"verdict": "PASS" if mem13_ok else "FAIL", "cases": [c["name"] for c in mem13_cases],
                  "per_case_verdicts": mem13_verdicts},
        "mem14": {"verdict": "PASS" if mem14_ok else "FAIL", "cases": [c["name"] for c in mem14_cases],
                  "per_case_verdicts": mem14_verdicts},
        "atom_items": atom_summary,
        "per_case": per_case,
    }
    if args.write:
        (HERE / "analysis.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps({k: out[k] for k in ("cross_run_gate", "provenance_gate", "verdict_counts", "mem13", "mem14")}, indent=2))
    if not gate_ok or not prov_ok or verdict_counts.get("FAIL", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
