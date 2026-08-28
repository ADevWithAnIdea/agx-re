# EXP-0148 — scaffolding classification and the over-consuming length rules

**Status:** COMPLETE (desk). **Target:** Apple M4 / G16G. **Date:** 2026-08-28.
**Hardware dispatched: NONE** (see `RESULTS.md` §6).

## Question

1. `tools/agx-isa/db.json` carries 23 descriptors that look like **decode scaffolding rather
   than instructions**. For each: is it (a) a continuation word of a longer instruction — name
   the parent, (b) a genuine standalone instruction lacking characterization — name the family,
   or (c) a decoder artifact that models nothing real?
2. Three descriptors are flagged `emit_unsafe` under
   `length_rule_gaps.doc02_over_consumers_20260828` because their fixed lengths swallow the
   following instruction's leader byte (`half_alu_fma12` 121/126, `falu2_ext8b` 193/250,
   `op04_len8` 823 firings). **Derive the correct modifier/op-select-aware length rule.**

## Hypotheses (frozen in `PRE_REGISTRATION.md` before any A/B run)

- **H1** low-nibble-9: op-select (`byte+2` bits[2:0]) ∈ {0,1} selects a 4-byte compact form, and
  must be tested *before* the `6 + 2*(byte+4 & 3)` extension.
- **H2** the same for `byte0 == 0x10` (fp16). **H3** `byte0 == 0x10` is an overloaded byte.
- **H4** the `0x?b` 10-byte class is `(byte+2 & 0x06) == 0x06`.
- **H5** `op04_len8` is short (2 or 4), not 8.

Refuters: round-trip below 302/302; clean-file count below 803; leftover bytes above 395 390;
resync gaps above 4 902. H2-as-stated and H5 were **refuted**; H1, H4 and the H2-narrow form
were accepted. Full frozen text and the exact metric definitions: `PRE_REGISTRATION.md`.

## Method

Desk analysis over `db.json` plus a full tokenization of the 1080-file own-MSL corpus
(`experiments/EXP-M4-13-full-corpus/hex`). Candidate length rules were applied to **copies** of
the ISA tool tree in `work/variant_*/`; the live `tools/agx-isa/` was never written.
Each variant is gated on `roundtrip_test.py` **plus** the corpus metrics **plus** a per-file diff.

The *continuation test* (`analysis/continuation_test.py`) is the core instrument: for a candidate
`X` and each observed predecessor `P`, it searches every bit of `P`'s own bytes for one that
predicts whether `X` follows. A near-perfect separator means `P` has a longer form and `X` is its
tail. A high `P(prev = P | X)` alone proves nothing.

## Reproduce

```sh
cd experiments/EXP-0148-m4-scaffolding-and-lengths

# baseline + every candidate rule set (writes raw/ab/<variant>/)
bash analysis/ab_run.sh isa_copy
bash analysis/ab_run.sh variant_final4        # the four accepted rules
bash analysis/ab_run.sh variant_final4_del    # + the two descriptor deletions

# what changed, per file
python3 analysis/ab_diff.py isa_copy variant_final4

# classification instruments
python3 analysis/classify_scaffolding.py raw/ab/variant_final4/tokens_strict.jsonl /dev/stdout
python3 analysis/continuation_test.py    raw/ab/variant_final4/tokens_strict.jsonl /dev/stdout

# read any corpus file's raw bytes + tokenization around an offset
python3 analysis/dump_context.py tessellation__pt_tri_linear__vertex.hex 124 200
```

Rebuilding a variant from the frozen sources: `python3 analysis/make_variant.py <name>` or
`analysis/make_variant2.py <name>` (the latter also adds descriptors to the `db.json` copy).
Both assert that each patch anchor occurs **exactly once** and abort if the source has moved.

## Layout

```
PRE_REGISTRATION.md              frozen hypotheses, refuters, metrics, input hashes
RESULTS.md                       observations, interpretation, negatives, limitations, verdict
PROGRESS.md                      timestamped milestone log
analysis/scaffolding_classification.md   THE DELIVERABLE for Task 1 — all 23, with evidence
analysis/proposed_db_changes.json        THE DELIVERABLE for Task 2 — mechanically applicable
analysis/field_verdicts.json             instruction-level verdicts + db_defects (no field upgrades)
analysis/*.py, analysis/ab_run.sh        repeatable instruments
kernels/add.metal                        authored carrier for the (undone) hardware probe
raw/baseline_tokens*.jsonl               baseline token streams (append-only)
raw/ab/<variant>/                        per-variant metrics, round-trip output, token streams
work/isa_copy/                           frozen copy of the ISA tool tree
work/variant_*/                          one candidate rule set each
work/hw/                                 built runners + the compiled carrier (nothing dispatched)
```

## Clean-room statement

```
Clean-room provenance: OWN-SHADER
Inputs inspected: AGX bytes compiled from MSL we authored (committed under
                  experiments/EXP-M4-13-full-corpus/corpus/ and kernels/add.metal);
                  our own tools/agx-isa database and tokenizer.
Apple binary introspection: NONE
Reproduction: the commands above
Evidence: raw/
```

## Headline result

The 23 split **3 / 13 / 7** (continuation / genuine / not-an-instruction). `falu2_ext8b` was
never an instruction — it is a length-rule artifact that vanishes entirely once the rule is
fixed. Four corrections take the corpus from 803 to **832** files tokenizing end-to-end with
round-trip held at 302/302 (30 fixed, 1 broken), and incidentally close
`length_rule_gaps.b_alu10` — the external compiler engineer's 10-byte XOR example that
`EXP-0099` found decodable under no family. `op04_len8` remains **OPEN** with six candidate
rules eliminated.
