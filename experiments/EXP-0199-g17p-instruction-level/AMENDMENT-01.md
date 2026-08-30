# EXP-0199 — AMENDMENT 01 (frozen before its first dispatch)

**Why this exists.** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` was added by the user after
EXP-0199's original contract was frozen and after runs `g17p_run01*` / `g17p_run02*` had
been captured. It is normative and it overrides the gates in the original dispatch.
Per its §4 I am **not editing the original pre-registration or the captured runs**:
`PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` and `raw/g17p_run01*`, `raw/g17p_run02*`,
`raw/smoke01`, `raw/prefreeze/*` are retained exactly as they are and are **reclassified as
DISCOVERY** (§10.2). This amendment adds the missing gates and freezes them before the
confirmation capture `raw/g17p_conf01` / `raw/g17p_conf02`.

**What the retained runs are worth:** they are new raw observations, new **geometry** facts
and new **liveness** facts. They are not, by themselves, semantic facts. Nothing is
discarded and nothing is re-run merely because the bar moved (§9).

---

## A1. What each arm is allowed to advance (§4: "the axis each arm may advance")

| Arm | Instruction | May advance | May NOT advance |
|---|---|---|---|
| A | `frag_depth_store` | geometry, liveness, **semantics (bounded: which attachment the store targets)**, target | the micro-op's operand map; compiler recipe |
| B | `vary_slot` | geometry, liveness, **semantics (model selection: is `slot` a slot selector?)**, target | any positive claim about what `vary_slot` *is* |
| C | `sfu_marker` | geometry (**length/framing**), liveness, **semantics (bounded: framing model selection)**, **compiler recipe: generated-point** | the micro-operation the marker controls |
| D | `frame_marker_compact` | geometry (**length/framing**), liveness, **semantics (bounded: framing model selection)**, **compiler recipe: generated-point** | the marker's role/meaning |
| E | `n2_op6` | geometry, liveness only — **semantics is declared `unknown` in advance** | anything semantic; no emitter label |

## A2. Gate A — the actual-byte ledger (new; mandatory)

Both runners now take `--ledger <off>:<len>` and, **after the spliced file has been written
and re-read from disk**, print `ACTUAL <off> <hex>` for each window. Those are the bytes
handed to `newLibraryWithURL:`; nothing between them and the GPU re-encodes anything.

Per case the driver records: `req_value`, `req_bytes`, `actual_bytes`, `decoded_value`
(read out of `actual_bytes` **independently**, by bit-extraction and by
`tools/agx-isa/isadb.decode_one`), `prog_sha256` of the reconstructed dispatched archive,
the instruction offset, `db_sha256`, and the harness md5s. Before any hardware conclusion
the driver asserts

```
req_value == decoded_value  and  actual_bytes[0:len(req_bytes)] == req_bytes
```

and a case that fails is `outcome = invalid_ledger`, excluded from every tally.

Reported per field: requested case count, distinct requested values, **distinct ACTUAL
encodings**, and collisions caused by `match`/overlapping fields. There is no assembler in
this experiment's path — splices are raw byte writes — so DEF-0166 cannot occur here; the
ledger *proves* that rather than assuming it. A round trip is explicitly not this gate and
is not used.

## A3. Gate B — positive control per arm (declared, with its independence argument)

| Arm | Positive control | Why the observable is independent of the swept field |
|---|---|---|
| A | (i) the **colour attachment**, a separate surface written by a separate instruction (`frag_color_store` at a different offset through a different tile bracket); (ii) `frag_depth_store.b5 = 0x00`, which in discovery moved DEPTH alone | the swept bytes are inside the depth store; the colour surface has no byte in common with them, and the read-back plan (attachment 0 vs the depth attachment) is fixed for every case |
| B | `vary_store.out_slot` (byte+4 of a *different* instruction), values `0x80/0xa0/0xc0/0xe0` | the readback is the same four colour channels for every case; the swept field (`vary_slot` bytes) never appears in the control |
| C/D | `06 02` inserted at the same boundary as every other payload | the oracle is 32 host-computed uints in a fixed buffer at a fixed index; the insertion changes neither the store, the index, nor any address |
| E | the same c_depth colour+depth surfaces, shown to move by the arm-A controls | fixed readback plan |

**If a positive control fails, that arm is `carrier-undecidable` and zero movement is NOT
reported as inertness.**

Untouched state is poisoned (0xDEADBEEF) on every read-back surface in both runners; the
compute carrier additionally writes an **independent pre-sentinel** (`o[64+i]`) through its
own store before the mutation point, and leaves `o[32..63]` and `o[96..127]` never written,
so "wrote wrong" / "halted early" / "never ran" / "read-back did not happen" are four
separable observations.

## A4. Gate C — competing semantic models, and a per-case prediction, frozen here

These models were **formed from the retained discovery runs**; that is stated plainly. The
amendment tests them on a **fresh capture in shuffled and reversed order, on a second
independent carrier for arm A**, with the ledger. Predictions are computed by
`analysis/predictor.py` from the model alone and are written to
`analysis/predictions_<run>.json` **before** the run's outputs are read.

### Arm A — which attachment does `frag_depth_store` write?

- **M_A1 (db.json):** it writes the shader's `[[depth]]` output to the **depth attachment**.
  Predicts: (a) unmutated DEPTH equals the host oracle exactly at all three probe pixels,
  three *distinct* values; (b) every mutation of its own bytes produces an outcome in
  {`ok`, `depth_moved`, `tile_discarded`, `fault`} and **never** `color_moved` — the colour
  surface is not reachable from this instruction; (c) with the instruction replaced, the
  depth attachment keeps the **clear** value.
- **M_A2 (fixed function):** the depth attachment is filled by interpolating
  `position.z` (= 0.0 in both carriers) and this instruction does something else.
  Predicts unmutated DEPTH == 0.0, and DEPTH == 0.0 with the instruction removed.
- **M_A3 (general tile store):** it is an untyped tile store whose target is selectable.
  Predicts at least one mutation yields `color_moved` or `both_moved`.
- **M_A4 (carrier artefact):** the DEPTH content is a property of `c_depth` specifically.
  Predicts the second carrier `c_depth2` — whose depth is a **decreasing** function of a
  **different** varying and whose colour carries a **third** varying — does not reproduce
  its own host oracle, or does not reproduce the same per-value outcome classes.

  Buckets: `correct_effect` / `coherent_alternative` / `silent_zero_or_no_write` /
  `rejected` / `invalid`.

### Arm B — is `vary_slot.slot` a slot selector?

- **M_B1 (db.json, "byte+3 = the varying slot, monotone, tracks the store slot"):** at
  least one value of `slot` other than the compiler's makes a fragment channel read a
  **different varying's value** (a *relocation*), exactly as the positive control does.
- **M_B2 (bit-2 enable):** `ok` iff `(v & 0x04) == 0`, `draw_gone` iff `(v & 0x04) != 0`,
  for all 256 values, and **never** a relocation.
- **M_B3 (fully inert):** `ok` for all 256 values.
- **M_PC (positive control, fully deterministic and host-computable):**
  `vary_store.out_slot == index << 5`, so store *j* with `out_slot = k<<5` puts varying
  *j−4*'s value (1000·(j−3)) into fragment channel *k−4* when `k ≥ 4`, and destroys the
  position when `k < 4`. Predicted per case; scored exactly.

### Arms C/D — how many bytes does the hardware consume at this leader?

- **M_len2:** the leader is a 2-byte instruction. Inserting 2 bytes at a boundary leaves
  the following instruction intact ⇒ all 32 lanes equal the host oracle
  (`correct_effect`); inserting 4 bytes leaves 2 extra bytes to be decoded on their own.
- **M_len4:** the leader is a 4-byte instruction. A 2-byte insertion truncates the next
  instruction ⇒ `coherent_alternative`/`silent_zero`/`rejected`, never `correct_effect`;
  a 4-byte insertion ⇒ `correct_effect`.
- **M_notinstr:** the byte pair is not a standalone instruction (a continuation/operand
  word of its predecessor, per EXP-0148's "unresolved continuation-word candidates") ⇒
  neither insertion width is `correct_effect` at any boundary.

  The predictor emits, per case, which of the three models predicts `correct_effect`. A
  model is selected only if it is right on **every** boundary and wrong nowhere, and only if
  the detection-power controls (`00 00`, `ff ff`, 2-byte deletion) are `correct_effect`
  **nowhere**.

### Arm E — declared `unknown` in advance

No model is proposed for `n2_op6`. Its cases may produce liveness numerators/denominators
and a ledger, and nothing else. `sem_checked == 0` for this arm, therefore no
`hardware-run`, no `semantically-mapped`, no `canonical-recipe-proven` (§2).

## A5. Gate D — compiler recipe

Only **`generated-point`** is claimed, and only for arms C and D: an instruction whose bytes
we chose, placed at an offset the compiler did not choose, in a program that otherwise
executes correctly. No `canonical-recipe-proven` is claimed for anything, because no arm
here generates a complete program from documented rules with all operand classes covered.

## A6. Gate E — confirmation

Two confirmation captures on G17P:

- `g17p_conf01` — case order **shuffled**, seed 20260830;
- `g17p_conf02` — case order **reversed** relative to conf01.

Both carry identical ledgers and the same frozen archives. The machine cannot be made quiet
(eight or nine agents share this device by standing policy and there is no lease), so per
FIELD-SWEEP-PROTOCOL §7 the **concurrent GPU activity is measured, not asserted**: the
process table is sampled into `raw/<run>/concurrency.jsonl` throughout, and adjudication of
every non-`ok` case is done **offline from the poison and the sentinels** (EXP-0160's
filter: two agreeing clean dumps win outright, because contamination can destroy an
observation but never fabricate a coherent one). `RESULTS.md` states this explicitly rather
than claiming a quiet machine.

A malformed runner response is `measurement_failure` and never a hardware outcome.
Fault/hang claims are repeated and are only reported with their exact numerator and
denominator.

## A7. Reporting shape (§2, §5)

`analysis/field_verdicts.json` carries, per `<mnemonic>._instruction` and per field, the six
independent axes — `encoding_geometry`, `liveness`, `semantics`, `compiler_recipe`,
`target`, `reproducibility` — plus exact counts: `encodable`, `dispatched`,
`distinct_actual_encodings`, `legal`, `silent`, `faults`, `hangs`, `aliases`, `untested`.
**No percentage is reported alone.** The proposed legacy label is reported separately and is
never rounded up from liveness. Negative wording is
`inert in <exact tested envelope>; global role unknown`.

## A8. Stopping rule and hazards (unchanged from the original contract)

Per-arm hang budget 6, then STOP that arm and report it PARTIAL. Known hazards excluded:
the 2-byte word `01 00` inserted at a `k_line` boundary (5/5 GPU hangs in prefreeze
pilot 02) and `frame_marker_compact` `b1 ∈ {3,7}` (EXP-0172).
