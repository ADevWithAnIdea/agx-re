#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""axes_sidecar.py -- census and cross-check of the section-2 `axes` objects.

RE_EXPERIMENT_PROCESS_CORRECTIONS section 2 requires every field to carry INDEPENDENT
status on six axes (encoding geometry, liveness, semantics, compiler recipe, target,
reproducibility), and says that until the database sidecar's schema is extended those
axes live in `analysis/field_verdicts.json` and `RESULTS.md`.

So today the axes are scattered: a handful sit inline in `tools/agx-isa/validation.json`,
and an experiment may propose more in its own `analysis/axes.json`. This module reads
whichever exist, reports how many rows have NO axes object at all -- as ABSENCE, with an
exact numerator and denominator, never as a zero score (section 5) -- and cross-checks
the declared axes against what `evidence_index.py` re-derives from the same raw.

The cross-check that matters most is the last one: a row whose declared liveness is
`live` or `accepted-inert` while no detection-power control fired in the cited raw. Gate
B makes that `carrier-undecidable`, and it is the EXP-0155 `samp_extra` failure mode.

CLEAN ROOM: reads only this repository's own committed artifacts.
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# Where a row's section-2 `axes` object may live. Neither source is required; a source
# that does not exist is reported as "file not present", which is different from
# "present and empty".
AXES_SOURCES = [
    ("EXP-0208-axis-reclassification/analysis/axes.json",
     os.path.join(ROOT, "experiments", "EXP-0208-axis-reclassification",
                  "analysis", "axes.json")),
]
INLINE = "validation.json (inline)"

# Declared statuses use the section-2 vocabulary; only the leading token is a status,
# the rest of the string is prose.
_GEOM_TOK = {"geometry-mapped": "geometry-mapped",
             "ledger-verified": "ledger-verified",
             "unverified": "no-data"}
_SEM_TOK = {"semantically-mapped": "semantically-mapped",
            "bounded-map": "bounded-map",
            "hypothesis": "checks-present",
            "unknown": "no-semantic-check"}
_LIVE_TOK = ("live", "accepted-inert", "inert", "carrier-undecidable", "fault", "hang")


def _tok(text):
    if not isinstance(text, str):
        return None
    t = text.strip().lower()
    for sep in (":", " --", ","):
        if sep in t:
            t = t.split(sep)[0]
    return t.strip()


def collect(labels=None):
    """Every row carrying a section-2 `axes` object, plus where each came from."""
    out, sources = {}, {}
    val = json.load(open(labels or os.path.join(HERE, "validation.json")))
    n_inline = 0
    for m, entry in val["instructions"].items():
        for f, r in entry.items():
            if isinstance(r, dict) and isinstance(r.get("axes"), dict):
                key = "%s.%s" % (m, f)
                out[key] = r["axes"]
                sources[key] = INLINE
                n_inline += 1
    counts = collections.OrderedDict()
    counts[INLINE] = n_inline
    for name, path in AXES_SOURCES:
        if not os.path.exists(path):
            counts[name] = None          # file not present -- not the same as zero
            continue
        try:
            doc = json.load(open(path))
        except Exception:
            counts[name] = None
            continue
        n = 0
        for key, rec in doc.items():
            ax = rec.get("axes") if isinstance(rec, dict) else None
            if isinstance(ax, dict):
                n += 1
                if key not in out:       # an inline object wins
                    out[key] = ax
                    sources[key] = name
        counts[name] = n
    return out, sources, counts


def crosscheck(scores, axes, sources, counts, denominator, outdir):
    """Do the declared axes agree with what this run re-derives from the same raw?"""
    geo, sem, live = scores["geometry"], scores["semantics"], scores["liveness"]
    rows = []
    agree = collections.Counter()
    for key, ax in sorted(axes.items()):
        g_dec = _GEOM_TOK.get(_tok(ax.get("geometry")))
        s_dec = _SEM_TOK.get(_tok(ax.get("semantics")))
        lt = _tok(ax.get("liveness"))
        l_dec = next((t for t in _LIVE_TOK if lt and lt.startswith(t)), None)
        g_got = (geo.get(key) or (None,))[0]
        s_got = (sem.get(key) or (None,))[0]
        l_got = (live.get(key) or (None,))[0]
        r = {"key": key, "source": sources.get(key),
             "geometry_declared": g_dec, "geometry_rederived": g_got,
             "semantics_declared": s_dec, "semantics_rederived": s_got,
             "liveness_declared": l_dec, "liveness_decidedness": l_got}
        for axis, dec, got in (("geometry", g_dec, g_got),
                               ("semantics", s_dec, s_got)):
            if dec is None or got is None:
                agree["%s:not-comparable" % axis] += 1
            elif dec == got:
                agree["%s:agree" % axis] += 1
            else:
                agree["%s:disagree" % axis] += 1
                r.setdefault("disagreements", []).append(
                    "%s declared %s, re-derived %s" % (axis, dec, got))
        if l_dec in ("live", "accepted-inert", "inert") and \
                l_got == "records-no-control":
            agree["liveness:answer-asserted-without-a-firing-control"] += 1
            r.setdefault("disagreements", []).append(
                "liveness declared `%s` but no detection-power control fired in the "
                "cited raw; Gate B makes that `carrier-undecidable`" % l_dec)
        elif l_dec:
            agree["liveness:declared-with-control-or-no-records"] += 1
        rows.append(r)

    nl = "\n"
    L = []
    L.append("# Section-2 `axes` sidecar - census and cross-check")
    L.append("")
    L.append("**Generated by `tools/agx-isa/axes_sidecar.py` (driven by "
             "`dashboards.py`); do not hand-edit.**")
    L.append("")
    L.append("Section 2 requires every field to carry independent status on six axes. "
             "The database sidecar cannot yet store them all, so section 2 says to put "
             "them in `analysis/field_verdicts.json` and `RESULTS.md` meanwhile. This "
             "page reports **where those axes objects exist today** and **whether they "
             "agree with what this run re-derives from the same raw**. Rows without an "
             "axes object are reported as ABSENT, with an exact numerator and "
             "denominator - not as a zero score.")
    L.append("")
    L.append("## Census")
    L.append("")
    L.append("| source | rows carrying an `axes` object |")
    L.append("|---|---:|")
    for name, n in counts.items():
        L.append("| %s | %s |" % (name, "file not present" if n is None else n))
    L.append("| **union (an inline object wins)** | **%d** |" % len(axes))
    L.append("| **db.json fields with NO axes object** | **%d of %d** |"
             % (denominator - len(axes), denominator))
    L.append("")
    L.append("## Cross-check against this run's re-derivation")
    L.append("")
    L.append("| comparison | rows |")
    L.append("|---|---:|")
    for k in sorted(agree):
        L.append("| %s | %d |" % (k, agree[k]))
    L.append("")
    dis = [r for r in rows if r.get("disagreements")]
    L.append("## Disagreements - %d row(s)" % len(dis))
    L.append("")
    if dis:
        L.append("A disagreement is not automatically a defect in either party: the "
                 "declared axes may rest on a keying or a validity rule this indexer "
                 "scores differently. It marks a row where two independent derivations "
                 "from the same raw did not land in the same place, which is exactly "
                 "what should be looked at next.")
        L.append("")
        L.append("| row | source | disagreement(s) |")
        L.append("|---|---|---|")
        for r in dis[:150]:
            L.append("| `%s` | %s | %s |"
                     % (r["key"], r["source"],
                        "; ".join(r["disagreements"])[:240].replace("|", "\\|")))
    else:
        L.append("None.")
    L.append("")
    open(os.path.join(outdir, "axes_crosscheck.md"), "w").write(nl.join(L) + nl)
    json.dump({"counts": counts, "union": len(axes), "denominator": denominator,
               "agreement": dict(agree), "rows": rows},
              open(os.path.join(outdir, "axes_crosscheck.json"), "w"), indent=1,
              default=str)
    return counts, agree, len(dis)


def selftest():
    """The cross-check must be able to report agreement AND disagreement."""
    ok = True

    def chk(name, cond):
        nonlocal ok
        print("%-4s %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            ok = False

    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="axes-")
    try:
        scores = {
            "geometry": {"a.x": ("geometry-mapped", "", []),
                         "a.y": ("no-data", "", []),
                         "a.z": ("ledger-verified", "", [])},
            "semantics": {"a.x": ("no-semantic-check", "", []),
                          "a.y": ("no-semantic-check", "", []),
                          "a.z": ("semantically-mapped", "", [])},
            "liveness": {"a.x": ("records-no-control", "", []),
                         "a.y": ("decided-multi-carrier", "", []),
                         "a.z": ("records-no-control", "", [])},
        }
        axes = {
            "a.x": {"geometry": "geometry-mapped: all 16 dispatched",
                    "semantics": "unknown -- no predictor",
                    "liveness": "live but INDISTINGUISHABLE"},
            "a.y": {"geometry": "geometry-mapped: all 16 dispatched",
                    "semantics": "semantically-mapped",
                    "liveness": "carrier-undecidable"},
            "a.z": {"geometry": "ledger-verified", "semantics": "semantically-mapped",
                    "liveness": "accepted-inert in the tested envelope"},
        }
        src = {k: "test" for k in axes}
        counts, agree, ndis = crosscheck(scores, axes, src,
                                         collections.OrderedDict([("test", 3)]),
                                         100, tmp)
        chk("an agreeing geometry axis is scored as agreement",
            agree.get("geometry:agree") == 2)
        chk("a disagreeing geometry axis is scored as disagreement (a.y)",
            agree.get("geometry:disagree") == 1)
        chk("an agreeing semantics axis is scored as agreement",
            agree.get("semantics:agree") == 2)
        chk("a disagreeing semantics axis is scored as disagreement (a.y)",
            agree.get("semantics:disagree") == 1)
        chk("a liveness ANSWER asserted with no firing control is flagged (a.x, a.z)",
            agree.get("liveness:answer-asserted-without-a-firing-control") == 2)
        chk("`carrier-undecidable` is NOT flagged as an unsupported answer",
            agree.get("liveness:declared-with-control-or-no-records") == 1)
        chk("the disagreement list is non-empty and enumerated", ndis >= 1)
        chk("absence is reported with a real denominator",
            "100" in open(os.path.join(tmp, "axes_crosscheck.md")).read())

        # And the other direction: a fully agreeing set must report NO disagreement.
        scores2 = {
            "geometry": {"a.x": ("geometry-mapped", "", [])},
            "semantics": {"a.x": ("semantically-mapped", "", [])},
            "liveness": {"a.x": ("decided-multi-carrier", "", [])},
        }
        axes2 = {"a.x": {"geometry": "geometry-mapped: x",
                         "semantics": "semantically-mapped: x", "liveness": "live"}}
        _c, ag2, nd2 = crosscheck(scores2, axes2, {"a.x": "t"},
                                  collections.OrderedDict([("t", 1)]), 1, tmp)
        chk("a fully agreeing row produces ZERO disagreements (not refuse-all)",
            nd2 == 0 and ag2.get("geometry:agree") == 1
            and ag2.get("semantics:agree") == 1)
        print("\nAXES-SIDECAR SELFTEST %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
