# EXP-0170 Arm C — round-trip blindness

**Scope 2 deliverable.** What the *disassemble → re-assemble → compare* self-check
proved, and what it never could.

Machine-readable companions: `roundtrip_idiom.json` (census), `roundtrip_blindspot.json`
(the demonstration). Reproduce with `python3 analysis/roundtrip_idiom.py &&
python3 analysis/roundtrip_blindspot.py`.

**EXP-0167 owns the EXP-0158-specific ledger check** (204,044 `assemble()` calls,
0 differences, 0 ledger mismatches — clean). This document does **not** re-litigate that
and issues no verdict on EXP-0158's oracle result. It answers only the general question:
*who else relies on the idiom, and what does their gate therefore establish?*

---

## 1. The defect shape

`DEF-0166-1`: the pre-fix `isadb.assemble()` OR-ed the descriptor's `match` constants into
the word and then OR-ed the field values in, with no clear:

```python
v = 0
for (start, width, value) in desc["match"]:
    v |= (value & ((1 << width) - 1)) << start
for f in desc["fields"]:
    v |= (fields.get(f["name"], 0) & mask) << f["start"]   # <-- no `v &= ~(mask << start)`
```

An OR cannot clear a bit. Every `match` bit lying inside a declared field's span was
therefore **stuck at 1 for every caller**: a caller asking for `grp = 0` got
`grp = 0x2F`.

The defect is **symmetric across the codec**. `disassemble()` reads the field back out of
the same word, so it reports `0x2F` — which is what the bytes really say. Encode and
decode agree perfectly. Therefore:

> **A round trip proves the codec self-consistent. It can never prove it correct.**
> `assemble(disassemble(b)) == b` is invariant under any defect that both halves share.

---

## 2. Census: who uses the idiom

`analysis/roundtrip_idiom.py` AST-scanned **1,419** committed Python files for any scope
calling both a decoder (`disassemble`/`decode_one`/`decode`/`disasm`) and an encoder
(`assemble`/`assemble_op`) with a comparison or assert. **160 hits.** Read by hand and
resolved to three classes:

| class | count | what it is |
|---|---|---|
| **A — the shared pre-flight gate** | **28 files** | `def assert_round_trip(buf)` in each experiment's `isa_helpers.py` / `synth.py`. **7 textually distinct bodies, all semantically identical.** |
| B — module co-definition (false positive) | ~100 | `isadb.py` / `agxisa.py` and their frozen per-experiment copies merely *define* both functions. No self-check. |
| C — the repo's suite | 3 + 27 copies | `tools/agx-isa/roundtrip_test.py`, `tools/agx-isa-m5/roundtrip_test.py`, `EXP-M5-22/roundtrip_test.py`, plus 27 `EXP-0148/work/variant_*/` copies. |

### Class A is the load-bearing one

The canonical body (`EXP-0154/harness/isa_helpers.py:184`, and 27 siblings):

```python
def assert_round_trip(buf):
    recs, leftover = isadb.disassemble(buf)
    if leftover:
        raise AssertionError("round-trip: %d leftover bytes" % len(leftover))
    off = 0
    for r in recs:
        got = isadb.assemble(r["mnemonic"], r["fields"])   # fields came FROM disassemble
        want = buf[off:off + r["length"]]
        if got != want:
            raise AssertionError(...)
        off += r["length"]
    return recs
```

`r["fields"]` is the **disassembler's** output, never the generator's intent. There is no
parameter through which a caller's intended value could enter. **This function is
structurally incapable of detecting DEF-0166-1**, and it is the pre-flight gate that ran
before dispatch in all 28 of:

```
EXP-0090, 0099, 0101, 0105, 0112, 0113, 0119, 0128, 0129,
EXP-0138, 0139, 0140, 0141, 0149, 0150, 0151, 0152, 0153, 0154,
EXP-0156, 0157, 0158, 0160, 0161, 0167, 0168, 0169, 0171
```

Its sibling `round_trips(buf)` wraps it in `try/except` and records the boolean as the
per-case `rt_ok` column — so `rt_ok: true` in every one of those experiments' raw records
means *"our tokenizer agrees with itself"*, **not** *"the bytes carry the field value the
harness asked for."*

---

## 3. The demonstration (not an assertion)

Asserting blindness from the code shape is weaker than showing it. `roundtrip_blindspot.py`
re-implements the **pre-fix OR-only assembler** locally (5 lines) and re-runs the repo's own
suite against it. If the suite were sensitive to DEF-0166-1, it would now fail.

| test | shape | cases | failures under the **defective** assembler | verdict |
|---|---|---|---|---|
| **(A)** `test_real_roundtrip` etc. | `asm(disasm(bytes)) == bytes` | **173** | **0** | **BLIND** — passes unchanged |
| **(B)** `test_synth_roundtrip` | `disasm(asm(fields)) == fields` | **37** | **0** | **BLIND in practice** |

### Test (A) is blind by construction

Every input is a real byte string whose `match` bits are already set. The stuck bit changes
nothing. 173/173 pass with the broken encoder.

### Test (B) is the *right shape* and still missed it

`test_synth_roundtrip` iterates `SYNTH = [(mnemonic, fields), …]` and compares the decode
against **the caller's own field dict** — exactly the check that could have caught this.
It failed to only because of what is in its corpus:

- **9 of 37** cases touch one of the 53 overlapping fields;
- **0 of 37** supply a value that *clears* a bit the descriptor's `match` sets inside that
  field's span — the necessary and sufficient condition for (B) to fire.

The reason is circular provenance: the `SYNTH` vectors were seeded from field dicts read
out of **really-observed instructions**, so their values already carry the `match` bits.
The corpus was drawn from the same distribution the defect is invisible on.

### Coverage of the blast radius (Q3)

42 instructions carry at least one overlapping field. The `SYNTH` corpus covers **5**
(`falu3`, `fspecial_est`, `ray_move`, `rt_intersect`, `rt_transform_test`); the `REAL`
corpus covers 17. **No case in either corpus could have caught the defect.**

---

## 4. What each check did and did not prove

| check | DID prove | did NOT prove |
|---|---|---|
| `assert_round_trip` (28 harnesses) | the emitted program tokenizes cleanly under our own disassembler with no leftover bytes, and instruction lengths are self-consistent — a real and useful guard against a desynchronised stream | that any field holds the value the generator asked for. Nothing about encoder correctness. |
| `rt_ok` column in raw records | the case's bytes re-tokenize | nothing about field fidelity |
| `roundtrip_test.py` test (A), 173 cases | `db.json`'s decode of 173 real encodings is invertible | nothing an OR-only encoder would violate |
| `roundtrip_test.py` test (B), 37 cases | for those 37 field dicts, encode∘decode is the identity | nothing about the other ~1,025 fields, and nothing about any value that clears a `match` bit |
| a corpus round trip / byte-exact tokenization | the codec is internally consistent | **never** that the encoder can synthesise an arbitrary legal combination — the acceptance bar in `CLAUDE.md` → Definition of Done |

**Consequence for the citation record.** `tools/agx-isa/roundtrip_test.py` is a
**tokenizer** regression test. It is sound evidence that `db.json` decodes its corpus
invertibly. It is **not** an emitter gate and should not be cited as one: it passes
unmodified with an assembler that cannot clear a bit. Per `CODEX.md`'s evidence ladder,
a round trip cannot rise above `STRUCTURAL`, and *"tokenization or round-trip alone can
never close a synthesis gap."*

---

## 5. The one check in the repo that is not blind

`EXP-0167/analysis/assemble_defect_check.py` compares each emitted field against **the
generator's ledger value** rather than against a re-decode. That is the asymmetric form,
and it is the only shape that can detect an encoder that silently sets bits. Its result
(clean, 204,044 calls) belongs to EXP-0167.

**Recommendation, for the orchestrator to rule on** — EXP-0170 changes no tooling:

1. Add a ledger-comparing assertion to `assert_round_trip`'s call sites, or a
   `assert_encodes(mnemonic, fields)` helper that checks
   `disassemble(assemble(m, f))[0]["fields"] == f` and is run per emitted instruction.
2. Extend `roundtrip_test.py`'s `SYNTH` corpus with, for each of the 53 overlapping fields,
   **one vector whose value clears a `match` bit in its span**. By construction such a
   vector fails against the old assembler and passes against the fixed one — a permanent
   regression test for DEF-0166-1. `static_overlap.json` lists the 53 with their
   `match_bits_in_span`, so the vectors are mechanical to generate.
3. Stop citing a round trip as an emitter gate in `PROVENANCE.md` rows and in `docs/`.
