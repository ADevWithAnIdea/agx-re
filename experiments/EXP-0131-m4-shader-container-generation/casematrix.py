#!/usr/bin/env python3
"""EXP-0131 case matrix: the frozen list of --case values run.py drives
harness/codesplice.m through, with the pre-registered prediction for each
(see PRE_REGISTRATION.md). This module has no side effects; it is imported
by run.py, verify.py, and analysis/report.py so all three agree on the case
list and cannot drift apart.
"""

CASES = [
    "baseline_check",
    "splice_green_field",
    "splice_wrong_field",
    "header_size_zero",
    "header_size_max",
    "truncate_main_early",
    "corrupt_next_record_header",
]

# Pre-registered predictions (frozen before the official runs; see
# PRE_REGISTRATION.md "Expected observation per case"). `bgra_pred` is the
# predicted post_mutation_bgra; None means "no specific prediction beyond
# baseline should be unaffected in a way not otherwise stated".
PREDICTIONS = {
    "baseline_check": {
        "post_mutation_bgra": "4080ffff",
        "post_mutation_hang": False,
        "note": "no mutation; reproduces baseline (control)",
    },
    "splice_green_field": {
        "post_mutation_bgra": "4040ffff",
        "post_mutation_hang": False,
        "note": "own-assembler val-field edit (0x80->0x40) at live main+0x06; "
                "predicts EXP-0008's archive-level green-channel mapping "
                "reproduces at the POST-CREATION live container",
    },
    "splice_wrong_field": {
        "post_mutation_bgra": None,
        "post_mutation_hang": False,
        "note": "adjacent byte (main+0x07, src_present_mask); no specific "
                "color predicted, only that it differs in mechanism from "
                "the val-field edit (may or may not visibly change output)",
    },
    "header_size_zero": {
        "post_mutation_bgra": "4080ffff",
        "post_mutation_hang": False,
        "note": "predicts record_size is NOT re-consulted at draw time for "
                "code fetch (main renders unmodified/correctly)",
    },
    "header_size_max": {
        "post_mutation_bgra": "4080ffff",
        "post_mutation_hang": False,
        "note": "same prediction as header_size_zero, opposite boundary",
    },
    "truncate_main_early": {
        "post_mutation_bgra": "00000000",
        "post_mutation_hang": False,
        "note": "predicts the clear color (0,0,0,0) shows through because "
                "an early stop skips frag_tile_setup/frag_color_store",
    },
    "corrupt_next_record_header": {
        "post_mutation_bgra": "4080ffff",
        "post_mutation_hang": False,
        "note": "predicts no visible effect on THIS draw's fragment output "
                "(structural hypothesis under test: the 'following record' "
                "is the vertex shader's own header, not FS metadata; a null "
                "result here is consistent with, but does not by itself "
                "prove, that hypothesis)",
    },
}

assert set(PREDICTIONS.keys()) == set(CASES)
