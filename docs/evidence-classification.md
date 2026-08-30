# Evidence classification — the per-field labelling standard

**Row:** `DOC-02` of `APPLE9_RE_IMPLEMENTATION_GAPS.md`.
**Status:** normative. Every field in every table this project ships must carry exactly one
label from §2. This document defines the vocabulary; `tools/agx-isa/validation.json` applies it
to the ISA database.

## 1. Why per-field and not per-table

The `CODEX.md` ladder (`HW-VALIDATED` > `DATA-TRACE-VALIDATED` > `OWN-SHADER-DIFF` >
`STRUCTURAL` > `INFERRED` > `UNKNOWN`) grades a **claim**. An implementer does not consume
claims — they consume **fields**, one at a time, and they need to know for each one whether
they can put an arbitrary value in it and expect the hardware to do what the table says.

A table labelled "HW-VALIDATED" as a whole is misleading in the common case, because tables
are mixed. `falu2` is the canonical example: `opsel` was swept exhaustively on hardware,
`srcA_reg`/`srcB_reg` were swept across the full 0–127 field space, and the top bit of those
register fields is **HW-tested inert with its role still unknown** (`EXP-0099`). Three
different strengths, one instruction. Only per-field labels transmit that.

This is not hypothetical bookkeeping. Two of this project's worst errors were exactly a
strength mismatch surviving into a table: `EXP-M4-13`'s `device_load` destination formula
(a byte-pattern correlation promoted as if executed — refuted by `EXP-0101`) and the bit 15/31
retention attribution (derived from byte patterns, never hardware-tested — both models refuted
by `EXP-0099`, retracted at commit `88fa4953`).

## 2. The eight labels

Ordered strongest to weakest. `DOC-02` names these; the right-hand column maps each onto the
`CODEX.md` ladder so the two systems never disagree.

| Label | Means | CODEX equivalent |
|---|---|---|
| `hardware-run` | The field was **given arbitrary values** — ideally its full encodable range, at minimum its boundaries plus interior samples — spliced into a real program, executed, and the output matched prediction. Faults and silent zeros count as observations. | `HW-VALIDATED` |
| `isolated-byte-diff` | Changing exactly this field in code compiled from our own MSL produced an isolated, reproducible byte change, **and** the resulting program ran with the predicted effect at one or more points — but the field's range was not swept. | `HW-VALIDATED` (point) / `OWN-SHADER-DIFF` |
| `corpus-correlation` | The field's meaning is inferred from how its values co-vary across a corpus of our own compiled shaders. Nothing was executed to test it. | `STRUCTURAL` |
| `tokenization-only` | The field is needed to make the instruction length and framing come out right, and round-trips exactly. Its **semantics are unknown**. | `STRUCTURAL` |
| `single-template-inference` | Read out of exactly one captured or compiled example. No variation was observed, so the field could be a constant, a don't-care, or load-bearing. | `INFERRED` |
| `api-accept-reject` | Known only from whether the Metal API or the compiler service accepted or rejected an input. Tells you what the **software stack** permits; says nothing about the hardware field. | `INFERRED` |
| `host-private` | Determined by macOS, the firmware, or the kernel — not a field userspace fills, or one whose value userspace cannot influence. Record it so nobody re-probes it. | *(out of scope)* |
| `untested` | Not established. **This is the default.** A field with no explicit label is `untested`. | `UNKNOWN` |

### The `hardware-run` bar, stated precisely

`hardware-run` requires that **arbitrary operands executed**, not that the instruction executed.
Compiling a shader that happens to use `falu2` with `srcA_reg = 3` and observing the right
answer validates *the instruction*; it does not validate *the field*. To claim `hardware-run`
on a field you must have run values the compiler would not have chosen — boundaries, holes,
and out-of-range — and recorded what happened, including the silent zeros.

### The `emittable` rule (verbatim from DOC-02)

> Do not use "emittable" for a family whose arbitrary operands have not executed.

Concretely: a family may be described as **emittable** only if every field an emitter must
fill is `hardware-run` or `isolated-byte-diff`. If any required field is `corpus-correlation`,
`tokenization-only`, `single-template-inference`, or `untested`, the family is
**"decodable, not yet emittable"** and must be written that way. `tools/agx-isa/db.json`
round-tripping 302/302 proves decode and re-serialize; **it does not prove synthesis**, and
`CLAUDE.md`'s Definition of Done says so explicitly.

## 3. Three qualifiers every labelled field also carries

A label alone is not enough. Each labelled field records:

1. **`range`** — the parameter interval actually exercised, in the field's own units. `"0..127
   dense"` and `"0,1"` are both honest; `"tested"` is not. For `hardware-run` this is the
   claim's real scope; an implementer may not extrapolate past it.
2. **`target`** — `M4` (G16G) or `A18` (G17P), per field, never assumed to transfer.

   > **⚠️ CORRECTION (2026-08-28): the `EXP-0119` A18↔M4 contradiction this rule was written
   > around is RESOLVED.** `EXP-0129` showed it was **operand PROVENANCE**, not a device
   > difference and not dispatch shape: an ALU-seeded operand retains at grid=1 *and* grid=4 with
   > cache=1 *and* cache=0, while a `device_load`-seeded operand gives a different value at
   > cache=1 and a silent `0.0` at cache=0, identically at both grid sizes. `EXP-M4-14` (A18) and
   > `EXP-0119` (M4) differed by how the operand was seeded; **neither prior record was wrong.**
   >
   > **The per-field `target` rule is unchanged and still binding** — it simply no longer rests on
   > that one unresolved contradiction. It rests on a *fresh, live* one: `EXP-0141` found
   > `tg_addr_compute` works on M4/G16G only with byte0 `0x1c`, and `EXP-M4-14`'s A18/G17P `0xfc`
   > **does not reproduce**. Silent generalization across targets remains a defect.

   **Current target rule (2026-08-28).** All live testing has moved to the **A18 Pro / G17P**, which
   is now both the documentation target and the test target, and **closure is measured against full
   G17P** (`CODEX.md`, "Target discipline"). Local M4 GPU testing is retired. Committed M4/G16G
   evidence — which is where the great majority of the labels in `validation.json` come from —
   **stays valid on its own target and is not retracted**, but it is **not** relabelled `A18`.
   **G17P revalidation is under way (`EXP-0153`).** Promotion requires a recorded validation or an
   explicit `INFERRED` label.
3. **`evidence`** — the `EXP-NNNN` that established it. A label with no experiment pointer is
   not a label.

## 4. Where the labels live

| Table | Label carrier | State |
|---|---|---|
| ISA instruction/field database | `tools/agx-isa/validation.json`, keyed `mnemonic → field → {label, range, target, evidence}` | see that file's `coverage` block. **As of `generated: 2026-08-28`: 171 instructions, 1036 fields; 443 fields (42.8 %) at emitter grade (`hardware-run` 349 + `isolated-byte-diff` 94); 38 instructions emittable, 133 decodable-not-yet-emittable.** The reader-facing version of this table, with what each label licenses a compiler back-end to do, is `docs/isa/README.md` → "Emittability status". |
| `docs/isa/encoding-tables.md`, `docs/isa/agx3.xml` | generated from `db.json` + `validation.json`; labels propagate | regenerate after any change |
| Prose in `docs/**` | inline, at the claim | ongoing |
| `PROVENANCE.md` | one row per fact, with the CODEX-ladder label | maintained |

`validation.json` is a **sidecar** rather than a `db.json` extension for a reason: `db.json`
is the encoding authority and is edited by whichever experiment is extending the ISA, while
labels are an audit artifact updated by the orchestrator. Keeping them apart means an
encoding fix and a label revision never collide, and `roundtrip_test.py` stays a pure
encoding test.

## 5. How to use this as an implementer

Read the label before the value.

- `hardware-run` within its stated `range` — emit it.
- `isolated-byte-diff` — emit it at the tested points; treat anything else as unvalidated.
- `corpus-correlation` / `tokenization-only` / `single-template-inference` — **do not emit
  arbitrary values.** Reproduce what the tables show and expect silent zeros off the path;
  on Apple9 a wrong operand-field value usually produces a **silent zero, not a fault**, so
  a wrong guess here fails quietly and far from its cause.
- `api-accept-reject` — a statement about Metal, not about silicon.
- `host-private` — not yours to fill.
- `untested` — a gap. It is listed so you can see it, not so you can fill it by guessing.

The silent-zero pattern is the reason this whole standard exists: on this hardware an
unvalidated field does not announce itself.
