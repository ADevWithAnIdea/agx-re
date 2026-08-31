# EXP-0216 — PRE-REGISTRATION (frozen before any verdict-bearing statistic)

**Type:** pure re-analysis of already-committed artifacts. **No device is touched**
(EXP-0213 holds the A18 Pro for quiet Gate E confirmations). No Apple binary is read,
disassembled or introspected. No shader is compiled. Nothing under `raw/` is written.
`tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/` and `PROVENANCE.md`
are **read-only** for this experiment and nothing is committed.

**Inputs frozen into `work/` before the first scoring run** (other agents write both
concurrently — EXP-0215 §7.6 last bullet):

```
work/db_frozen.json          sha256 02a47fc6f8ac4589357aa5b620e74a930e9cf3e366d3312cdc9f18064faa7dbb
work/validation_frozen.json  sha256 6e7ff3f1155f5a2ddc0346b32235d860ea705776cf08f1d8a9a6247a669b9a35
repo HEAD                    d8b4b63b
```

`db_frozen.json` is byte-identical to EXP-0215's frozen copy, so the two experiments
score against the same descriptors. `validation.json` has moved since EXP-0215 froze it
(`ebb08661…` → `6e7ff3f1…`); this experiment reads it only for row labels.

**Disclosed prior exposure.** Before freezing this document I opened (a) EXP-0215's
`RESULTS.md`, `analysis/suspect_citations.json` and `analysis/sibling_mnemonics.json`;
(b) the descriptors for `bf_alu`, `bf_add_dst`, `bf_mul_dst`, `cvt_f2h`, `cvt_f2h_dst`,
`imad`, `fspecial`, `mov_zext16`, `half_alu*`, `falu3*`, `iminmax`, `iter_at`,
`reg_move_cb`, `shift_amt_move` in `db.json`; (c) `git log`-derived span history of the
suspect fields; (d) EXP-0154's `PRE_REGISTRATION.md`, `casematrix.py` and the register
plan/seed table in `isa_helpers.py`; and (e) **five** individual records of EXP-0154's
`imad` arm (lines 12598–12600, 12854–12855 of
`raw/g17p_20260829_run02/sweep.jsonl`) to learn the record schema. No aggregate
statistic and no register-identity map had been computed at freeze time.

---

## Q1 — 22 pairs whose records declare a different span than the descriptor

### Competing readings

* **R-decl** — the sweep physically moved the bits the record *declares*; the
  descriptor's span moved later, so the committed verdict is about different bits than
  the row it now sits on.
* **R-cur** — the record's declared span is wrong (a harness bug) and the bits that
  actually moved are the descriptor's current span.
* **R-same** — declared and current spans coincide on every dispatched encoding, so the
  disagreement is cosmetic and undecidable from these bytes.

### What decides it (stated before looking)

**Test G (geometry, Gate A).** For every record with a `value` and committed `bytes`,
decode at the declared span and at the current span.

| observation | verdict |
|---|---|
| `value == bits(bytes, declared)` on ~all records and `!=` at current | **R-decl** |
| the reverse | **R-cur** |
| both agree on every record | **R-same** — undecidable, and the pair is *not* a defect |

**Test I (operand identity — release-on-read oracle).** EXP-0154 H3, already committed
and already positively controlled in its own pilot S3: reading a GPR as a 32-bit source
zeroes it, and the harness dumps all 16 registers with distinct seeds
(`SEED_I = {0:10, 1:21, 2:34, …}`). Therefore:

* if, over the dense sweep, the register that comes back zero equals `(value >> k) & 0xF`
  for a fixed `k`, then **the swept bits are an operand register selector** — a hardware
  fact that owes nothing to the field's name;
* the **arithmetic** then separates the operand *slots*. With distinct seeds, a register
  substituted into a multiplicand moves the destination as a product; into the addend, as
  a sum. A host oracle enumerates the candidate slot assignments from the seeds and the
  prediction is fixed before the observed destination is compared.

**Named prediction for `imad`.** `db.json` now says `srcC_lo=(40,8)`, `srcB=(48,8)`;
EXP-0154 declared `srcB=(40,8)`, `srcC_lo=(48,8)`. If byte 5 is a multiplicand selector
and byte 6 is not (or vice versa), the swap is decided. If **both** bytes select
multiplicands, or **neither** result separates a product from a sum, the swap is
`undecidable` and must be reported as such.

**Refuters.** (i) If the release-on-read oracle does not fire — no register is zeroed, or
the zeroed register does not track the value — Test I has no detection power on that arm
and the arm is `carrier-undecidable`, not "no swap". (ii) If the observed destination is
identical across the whole sweep, Test I's arithmetic half is blind and only Test G's
verdict stands. (iii) A `wrong_value` outcome is not evidence of an operand identity by
itself; the identity claim must come from *which* register zeroed or *which* seed appears
in the result.

**Forbidden inference.** Test G alone can never rename a field. It reports which bits an
observation is about. Only Test I can say what those bits *are*.

---

## Q2 — 15 638 records keyed to a mnemonic their bytes do not decode to

* EXP-0171: 10 938 records keyed `bf_alu` → tokenize `bf_add_dst` / `bf_mul_dst`.
* EXP-0144: 4 700 records keyed `cvt_f2h` → tokenize `cvt_f2h_dst`.

### Competing readings

* **S-key** — the experiment's `instr` string is right and our disassembler's descriptor
  choice is wrong (bad `match`, bad length rule, or a wrongly-preferred sibling).
* **S-bytes** — the committed bytes are right and the `instr` key is a stale label; the
  records belong to the sibling descriptor.
* **S-benign** — both descriptors assign the swept bits to the *same span*, so the
  records are unambiguous about which bits were exercised and the disagreement is a naming
  question with no operand hazard.

### What decides it (stated before looking)

1. **Span overlay.** For each swept byte, list every field of *both* descriptors that
   covers it. If the keyed field and the sibling field occupy the **same** `(start,width)`,
   re-pointing cannot move a verdict onto a different operand and the hazard named in the
   dispatch does not exist for that field. If they differ, it does, and the arithmetic
   test below is mandatory before anything is said.
2. **Match arithmetic.** Compute, per record, which of the two descriptors' match bits the
   committed bytes satisfy. A descriptor that no committed encoding satisfies cannot be the
   instruction that ran, whatever the key says.
3. **Behaviour.** The records carry outcomes and (where the harness dumps them) registers.
   If the two readings assign the same bits, behaviour cannot separate them and the honest
   answer is *undecidable by behaviour, decided by geometry*.

**Refuter for S-bytes:** a committed encoding that satisfies the keyed descriptor's match
and not the sibling's. **Refuter for S-key:** the keyed descriptor's match failing on
every committed encoding.

**Tokenizer-defect check (required).** `isadb.instr_length` changed today. Before blaming
`db.json`, re-run the tokenization of the committed anchor bytes and record whether the
decode is a *length-rule* outcome or a *descriptor-match* outcome. If the length rule
refuses the bytes, that is a tokenizer finding and must be reported as one.

---

## Q3 — four `cvt_f2h` citations whose bytes fail `cvt_f2h`'s own match on all 1280 records

### Competing readings

* **T-desc** — `cvt_f2h`'s `match` is wrong (over-fit) and the records are that
  instruction.
* **T-other** — the records are a genuinely different instruction.

### What decides it

`cvt_f2h`'s match is a **single 8-bit** constraint, byte0 == 0x11. Decompose it: for every
record, report byte0 and which half of the constraint fails — the low nibble (the group)
or the high nibble (which, in every dst-parameterised sibling in this database, is a `dst`
register field). If the low nibble holds on all records and only the high nibble varies,
the descriptor is over-fit on a destination register and **T-desc** is supported. If the
low nibble also fails, **T-other**. Either way the answer must be given *with the bytes*.

---

## Stopping rule and non-actions

* No label is changed and none is proposed. No rename is proposed unless a hardware
  behaviour, not a name overlap, decides it.
* Any pair where the two spans coincide on every dispatched encoding is reported
  **not-a-defect**, not "resolved in favour of the descriptor".
* Any pair where the carrier has no detection power for operand identity is reported
  **undecidable**, and the count of undecidables is published beside the count resolved.
* Every proposed `db.json` edit, if any, is written to
  `analysis/proposed_db_edits.json` as a **proposal** and applied nowhere.
