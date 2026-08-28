"""casematrix.py -- EXP-0129 frozen case list (single source of truth for
run.py and verify.py). H1 = barycentric-anomaly discrimination; H2 = split
prolog/epilog ABI construction (DRV-ABI-01 / P0.8's last two open items)."""

BARY_SRC = "kernels/bary.metal"

# ---- H1: barycentric-anomaly discriminating factorial matrix --------------
# Each row: (variant_id, vertex_fn, fragment_fn, natt) -- shared between the
# structural (compile+extract+disassemble) and render (real HW readback)
# backends so the two evidence types are directly comparable per variant.
BARY_VARIANTS = [
    ("base",           "v_bary",       "f_base",         2),  # baseline: no position touched
    ("pos3",           "v_bary",       "f_pos3",         3),  # ANOMALY RECIPE: 3 outputs, position OUT
    ("count3_const",   "v_bary",       "f_count3_const", 3),  # isolates: output COUNT alone (no position)
    ("count3_vary",    "v_bary_extra", "f_count3_vary",  3),  # isolates: ANY extra interpolant (no position)
    ("pos2",           "v_bary",       "f_pos2",         2),  # isolates: position OUT, count stays 2
    ("posread_noout",  "v_bary",       "f_posread_noout",2),  # isolates: position READ (device store), never an output
    ("attach3ctrl",    "v_bary",       "f_base",         3),  # isolates: harness/pipeline attachment-count artifact (unchanged shader)
    ("base2",          "v_bary2",      "f_base2",        2),  # CONFIG2 independent-geometry cross-check
    ("pos3_2",         "v_bary2",      "f_pos3_2",       3),  # CONFIG2 independent-geometry cross-check
]

QUAL_CASES = [
    ("qual_persp",    "kernels/bary_qual_persp.metal",         "v_bary_q",  "f_bary_qpersp"),
    ("qual_nopersp",  "kernels/bary_qual_noperspective.metal", "v_bary_q2", "f_bary_qnopersp"),
]


def full_case_list():
    cases = []

    # H1 structural (compile+extract fragment hex+disassemble)
    for vid, vfn, ffn, natt in BARY_VARIANTS:
        cases.append({"id": f"barystruct_{vid}", "family": "bary_struct", "backend": "bary_struct",
                      "source": BARY_SRC, "params": {"vertex": vfn, "fragment": ffn, "natt": natt, "variant": vid}})

    # H1 render (real HW readback)
    for vid, vfn, ffn, natt in BARY_VARIANTS:
        cases.append({"id": f"baryrender_{vid}", "family": "bary_render", "backend": "bary_render",
                      "source": BARY_SRC, "params": {"variant": vid}})

    # H1 grammar probe: does MSL accept an explicit interpolation qualifier
    # on [[barycentric_coord]]?
    for cid, src, vfn, ffn in QUAL_CASES:
        cases.append({"id": f"qualstruct_{cid}", "family": "bary_qual", "backend": "qual_struct",
                      "source": src, "params": {"vertex": vfn, "fragment": ffn}})

    # H2: entry-only-attribute-on-helper own-compiler finding (structural +
    # numeric forwarding check).
    cases.append({"id": "negctrl_struct", "family": "split_negctrl", "backend": "negctrl_struct",
                  "source": "kernels/split_negctrl.metal",
                  "params": {"vertex": "v_negctrl", "fragment": "f_negctrl_caller", "natt": 1}})
    cases.append({"id": "negctrl_render", "family": "split_negctrl", "backend": "negctrl_render",
                  "source": "kernels/split_negctrl.metal", "params": {}})

    # H2: genuinely-called ("noinline") programmable-blend epilog.
    cases.append({"id": "epilog_struct", "family": "split_epilog", "backend": "epilog_struct",
                  "source": "kernels/split_epilog.metal",
                  "params": {"vertex": "v_split_common", "fragment": "f_split_epilog", "natt": 1}})
    for bm in (0, 1):
        cases.append({"id": f"epilog_render_mode{bm}", "family": "split_epilog", "backend": "epilog_render",
                      "source": "kernels/split_epilog.metal", "params": {"blendmode": bm}})

    # H2: genuinely-called ("noinline") vertex-attribute-fetch prolog.
    cases.append({"id": "prolog_struct", "family": "split_prolog", "backend": "prolog_struct",
                  "source": "kernels/split_prolog.metal", "params": {"vertex": "v_split_prolog"}})
    cases.append({"id": "prolog_render", "family": "split_prolog", "backend": "prolog_render",
                  "source": "kernels/split_prolog.metal", "params": {}})

    # H2: multi-argument / multi-component-return CALL-ABI generalization.
    cases.append({"id": "callret_struct", "family": "split_callret", "backend": "callret_struct",
                  "source": "kernels/split_callret.metal", "params": {"function": "k_callret"}})
    cases.append({"id": "callret_render", "family": "split_callret", "backend": "callret_render",
                  "source": "kernels/split_callret.metal", "params": {"n": 4}})

    return cases
