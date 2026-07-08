# EXP-M4-12 — ISA census residue closure (the final 2.6%)

**Goal:** drive the byte0-group instruction census (EXP-M4-01/EXP-0036) to *total
completeness* — every undecoded resync region understood and labeled — for
everything **except** the fragment blend micro-sequence (clean-room rule 5: we do
not transcribe a compiler-generated blend *algorithm*; individual op encodings are
still documented where clean).

**Baseline (before this experiment):** 97.4% byte coverage, 38 undecoded regions,
252 bytes, 7 never-decodable byte0 groups.

**Method (clean-room, OWN-SHADER):** for each residue op, compile an *isolated*
minimal MSL kernel that emits it, extract the AGX bytes, and trace tokenization so
the op appears cleanly bracketed by known-length ops (the anchored gap gives its
true length). Decode operand fields by input-diffing where clean. We document
per-instruction *encodings and semantics* (hardware facts), never a
compiler-generated *sequence* as an algorithm.

## Work-streams (parallel investigation subagents)

- **S1-sfu** — transcendental SFU: sin/cos argument range-reduction + the round
  family (floor/ceil/trunc/rint/fract/sign). Kernels: k_transcend, k_transcend_round.
- **S2-texture** — texture-address / imageblock 0x54 family. Kernels: k_tex_msaa,
  k_tex_array_cube, k_tex_atomic, k_tex_lod.
- **S3-intmisc** — integer/uint/half/64-bit/convert misc. Kernels: k_int64,
  k_uint_arith, k_half_arith, k_cvt_pack, k_mem.
- **S4-cf-frag** — control-flow / atomics / subgroup / fragment. Kernels: k_cf_loop,
  k_atomics, k_atomics_tg, k_subgroup_shuffle, r_cent_f, r_deriv_f, r_tex_f, r_blend_f.

Subagents gather ground-truth + propose length rules; the main agent integrates
into `tools/agx-isa/isadb.py` serially, re-running the full census + round-trip
after each family (residue must strictly drop with no new gaps, round-trip GREEN).
