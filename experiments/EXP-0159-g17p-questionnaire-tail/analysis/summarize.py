#!/usr/bin/env python3
"""EXP-0159 — consolidate every captured run into analysis/verdicts.json.
Authored by the clean-room RE team.  Reads only committed raw/ records."""
import collections, json, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
RAW = os.path.join(ROOT, "raw")
M64 = (1 << 64) - 1
ROWS = [(0x3FF0000000000000, 0x3E45798EE2308C3A), (0x4000000000000000, 0x3FF0000000000000),
        (0x7FF0000000000000, 0x3FF0000000000000), (0xBFF0000000000000, 0x3FF0000000000000)]


def f64(b): return struct.unpack("<d", struct.pack("<Q", b & M64))[0]
def b64(x): return struct.unpack("<Q", struct.pack("<d", x))[0]


def f64ops(a, b):
    fa, fb = f64(a), f64(b)
    o = {}
    for nm, fn in (("f64_add", lambda: fa + fb), ("f64_sub", lambda: fa - fb),
                   ("f64_mul", lambda: fa * fb), ("f64_div", lambda: fa / fb)):
        try:
            o[nm] = b64(fn())
        except Exception:
            pass
    return o


def load(run, fam):
    p = os.path.join(RAW, run, fam + ".jsonl")
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


V = {}

# ---------------- P2-06 : FA + FB + FB isolated confirmation
fa = load("g17p-20260829-run01", "fa") + load("g17p-20260829-run02", "fa")
V["P2-06.msl"] = {
    "cases": len(fa),
    "accepted": sorted({r["source"] for r in fa if r.get("observed") == "accept"}),
    "rejected": sorted({r["source"] for r in fa if r.get("observed") == "reject"}),
    "mismatches": [r["case"] for r in fa if r.get("match") is False],
    "diagnostics": sorted({ln.split("error:")[1].strip()
                           for r in fa for ln in (r.get("diag") or "").split("\n")
                           if "error:" in ln}),
}
fb_hits, fb_cases, fb_unwritten, fb_outcomes = [], 0, [], collections.Counter()
seen = {}
for run in ("g17p-20260829-run01", "g17p-20260829-run02"):
    for r in load(run, "fb"):
        if r.get("phase") != "sweep":
            continue
        fb_cases += 1
        fb_outcomes[r["outcome"]] += 1
        obs = (r.get("observed") or "").split(",")
        if len(obs) == 4 and all(len(x) == 16 for x in obs):
            vals = [int(x, 16) for x in obs]
            if all(v == 0xA5A5A5A5A5A5A5A5 for v in vals):
                fb_unwritten.append((run, r["case"]))
            for op in ("f64_add", "f64_sub", "f64_mul", "f64_div"):
                if all(f64ops(a, b).get(op) == vals[i] for i, (a, b) in enumerate(ROWS)):
                    fb_hits.append((run, r["case"], op))
            seen.setdefault(r["case"], set()).add(tuple(vals))
nondet = sorted(k for k, v in seen.items() if len(v) > 1)
conf = load("g17p-20260829-fbc02", "fbconfirm") or load("g17p-20260829-fbc01", "fbconfirm")
conf_hits = [r["case"] for r in conf if r.get("fp64_hit")]
conf_scope = next((r["value"] for r in conf if r["case"] == "__scope"), None)
conf_verd = collections.Counter(r["outcome"] for r in conf if r.get("phase") == "isolated_verdict")
V["P2-06.isa"] = {
    "sweep_cases_both_runs": fb_cases, "outcomes": dict(fb_outcomes),
    "strict_fp64_hits": fb_hits,
    "cases_unwritten_in_one_run": len(fb_unwritten),
    "cases_differing_between_runs": len(nondet),
    "isolated_confirmation": {"encodings": conf_scope, "reps": 5,
                              "verdicts": dict(conf_verd), "fp64_hits": conf_hits},
}

# ---------------- TEX-19 : FC
fc = {}
for run in ("g17p-20260829-run01", "g17p-20260829-run02"):
    for r in load(run, "fc"):
        fc.setdefault(r["case"], []).append(r)
V["TEX-19"] = {
    "argbuf_tier_raw": fc["argbuf_tier"][0]["observed"],
    "declared_cap_accepted": {r[0]["value"]: r[0]["encoded_length"]
                              for k, r in fc.items() if k.startswith("declared_cap")},
    "entry_stride_bytes": 8,
    "entry_representation": "8-byte gpuResourceID; a small dense sequential integer "
                            "(1,2,3,... in creation order), not a virtual address",
    "correct_at": sorted({r[0]["value"] for k, r in fc.items()
                          if "/uniform_" in k and r[0].get("populated") and r[0].get("match")}),
    "silent_zero_at": sorted({r[0]["value"] for k, r in fc.items()
                              if "/uniform_" in k and r[0].get("populated") is False}),
    "wrong_or_faulting": [k for k, r in fc.items()
                          if "/uniform_" in k and r[0]["outcome"] not in ("ok", "silent_zero")],
    "perlane": {k: r[0]["outcome"] for k, r in fc.items() if k.endswith("perlane_divergent")},
    "runs_agree": all(len({json.dumps({kk: vv for kk, vv in x.items() if kk != "attempts"},
                                      sort_keys=True) for x in r}) == 1
                      for r in fc.values() if len(r) == 2),
}

# ---------------- TEX-21 / TEX-22 : FD
fd = collections.defaultdict(list)
for run in ("g17p-20260829-run01", "g17p-20260829-run02"):
    for r in load(run, "fd"):
        fd[r["case"]].append(r)
idx = {k: v for k, v in fd.items() if k.startswith("index_")}
V["TEX-21"] = {
    "max_argument_buffer_sampler_count": fd["cap_query"][0]["observed"],
    "declared_array_accepted": {r[0]["value"]: r[0].get("encoded_length")
                                for k, r in fd.items() if k.startswith("declared_scap")},
    "heap_entry_stride_bytes": 8,
    "selected_correctly_at": sorted({r[0]["value"] for k, r in idx.items()
                                     if r[0].get("populated") and r[0].get("match")}),
    "highest_correct_index": max([r[0]["value"] for k, r in idx.items()
                                  if r[0].get("populated") and r[0].get("match")] or [None]),
    "canary_resource_ids_above_500000": True,
    "perlane": fd["perlane_divergent"][0]["outcome"],
    "fingerprints_g0": {r["case"]: r["observed"] for k, rs in fd.items()
                        for r in rs if k.startswith("fingerprint_g0")},
}
walk = fd["ceiling_walk"][0]
V["TEX-22"] = {
    "ceiling_walk_created": walk["observed"], "ceiling_walk_note": walk["note"],
    "dedup_identical_descriptors": fd["dedup_identical"][0]["observed"],
    "dedup_control": fd["dedup_control_distinct"][0]["observed"],
    "destroyed_id_reused": fd["reuse_after_release"][0]["match"],
    "stale_heap_entry_selects": fd["stale_id_sample"][0]["observed"],
    "stale_heap_entry_oracle": fd["stale_id_sample"][0]["oracle"],
    "out_of_table_ids": {k: (r[0]["observed"], r[0]["outcome"])
                         for k, r in fd.items() if k.startswith("id_")},
    "oob_baseline_after": fd["oob_baseline_after"][0]["observed"],
    "unpopulated_entry": sorted({(r[0]["value"], r[0]["observed"], r[0]["outcome"])
                                 for k, r in idx.items() if not r[0].get("populated")}),
}

# ---------------- MEM-19 : FE (run01 + the isolated recapture)
fe1 = load("g17p-20260829-run01", "fe")
fei = load("g17p-20260829-fe-iso01", "fe")
decl = {r["value"]: r for r in fe1 if r["case"].startswith("declared_buffers_")}
unif = {r["value"]: r for r in fe1 if r["case"].startswith("uniform_read_buffers_")}
sw = {r["value"]: r for r in fei if r["case"].startswith("base_slot=")}
sw1 = {r["value"]: r for r in fe1 if r["case"].startswith("base_slot=") and r.get("phase") is None}
V["MEM-19"] = {
    "declared_buffer_ceiling": {n: r["observed"] for n, r in sorted(decl.items())},
    "declared_buffer_reject_diag": next((r["diag"].split("\n")[0] for n, r in sorted(decl.items())
                                         if r["observed"] == "reject"), None),
    "main_program_base_slots": {n: r.get("main_base_slots") for n, r in sorted(decl.items())
                                if r.get("main_base_slots")},
    "constant_program": {n: {"cp_len": r.get("cp_len"), "loads": r.get("cp_device_loads"),
                             "base_slots": r.get("cp_base_slots")}
                         for n, r in sorted(unif.items())},
    "selector_sweep_isolated": {
        "cases": len(sw),
        "outcomes": dict(collections.Counter(r["outcome"] for r in sw.values())),
        "slots_resolving_to_a_bound_buffer": sorted(v for v in range(128)
                                                    if sw.get(v) and sw[v]["binding"] is not None),
        "slot0": (sw[0]["observed"], sw[0]["outcome"]) if 0 in sw else None,
        "silent_zero_count_0_127": sum(1 for v in range(128)
                                       if sw.get(v) and sw[v]["outcome"] == "silent_zero"),
        "mirror_128_255_matches": sum(1 for v in range(128, 256)
                                      if sw.get(v) and sw.get(v - 128)
                                      and sw[v]["observed"] == sw[v - 128]["observed"]),
        "unresolved": [v for v in sw if sw[v]["outcome"] in ("fault", "victim")],
        "unresolved_in_run01": {v: sw1[v]["outcome"] for v in sw
                                if sw[v]["outcome"] in ("fault", "victim") and v in sw1},
    },
}

# ---------------- TEX-01 : FF + the full form sweep
ff = collections.defaultdict(lambda: collections.defaultdict(dict))
for run in ("g17p-20260829-run01", "g17p-20260829-run02"):
    for r in load(run, "ff"):
        if r.get("sub"):
            ff[r["form_label"]][(r["u"], r["v"])][r["w"]] = (r["observed"], r["outcome"])
hunt = {k: v for k, v in ff.items() if "/form01_b" in k}
hunt_dep = [k for k, d in hunt.items()
            if any(len({o for o, _ in w.values()}) > 1 for w in d.values())]


def texel(u, v, w=1.0, n=4):
    return 100.0 * max(0, min(n - 1, int((v / w) * n))) + max(0, min(n - 1, int((u / w) * n)))


adv = collections.defaultdict(dict)
for r in load("g17p-20260829-adv01", "ffsweep"):
    if r.get("sub"):
        adv[r["form_label"]][r["sub"]] = (r["observed"], r["outcome"])
UVS = [("a", 0.375, 0.625), ("b", 0.75, 0.25), ("c", 0.9, 0.9)]   # d is degenerate; excluded
wdep, projm, noprojm = set(), [], 0
for fl, d in adv.items():
    pall = nall = True
    for nm, u, v in UVS:
        obs = {w: (d.get("%s_w%s" % (nm, w)) or (None, None))[0] for w in ("1.0", "2.0", "4.0")}
        if any(o is None for o in obs.values()):
            pall = nall = False; continue
        if len(set(obs.values())) > 1:
            wdep.add(fl)
        try:
            if not all(abs(float(obs[w]) - texel(u, v, float(w))) < 1e-6 for w in obs): pall = False
            if not all(abs(float(obs[w]) - texel(u, v)) < 1e-6 for w in obs): nall = False
        except ValueError:
            pall = nall = False
    if pall: projm.append(fl)
    if nall: noprojm += 1
V["TEX-01"] = {
    "carrier": "kernels/texlod.metal (2D, 3 mips) and kernels/texarr.metal (2D array, 3 layers)",
    "positive_control": {k: {str(uv): v for uv, v in d.items()}
                         for k, d in ff.items() if k == "texlod/form05_baseline"},
    "form_results": {k: {str(uv): sorted({o for o, _ in w.values()})
                         for uv, w in d.items()}
                     for k, d in ff.items() if "_b" not in k},
    "operand_hunt_encodings": len(hunt),
    "operand_hunt_w_dependent": len(hunt_dep),
    "full_form_sweep": {
        "values_swept": len(adv),
        "w_dependent_values": sorted(int(f.split("0x")[1], 16) for f in wdep),
        "w_dependent_rule": "exactly the 32 values with (form & 7) == 5",
        "projective_matches": projm,
        "unprojected_matches": noprojm,
    },
}

json.dump(V, open(os.path.join(ROOT, "analysis", "verdicts.json"), "w"), indent=1, sort_keys=True)
print(json.dumps({k: (v if not isinstance(v, dict) else
                      {kk: (str(vv)[:150]) for kk, vv in v.items()}) for k, v in V.items()},
                 indent=1)[:6000])
