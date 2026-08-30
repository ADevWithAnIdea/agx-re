# EXP-0176 — the defective `PROVENANCE.md` rows, and corrected text

**`PROVENANCE.md` was NOT edited by this experiment.** Everything below is proposed text for the
orchestrator. Line numbers are as of `PROVENANCE.md` at the time of writing (174 logical data rows,
header at L15, delimiter at L16).

---

## Part 1 — the four rows the dispatch named

### D-1 · L17 — cites no experiment and no artifact

```
| 2026-07-06 | Target is Apple A18 Pro, SoC T8140, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / feature family Apple9 max | ROADMAP | HW-PROBE | bring-up: `sysctl`, `system_profiler`, Metal `supportsFamily` probe |
```

**Defect.** The source cell names three *tools* and no experiment, no file and no commit, so the
row cannot be audited. `artifacts_exist` is false for exactly that reason.

**The claim itself fully reproduces**, from artifacts already committed under `EXP-0002`:

| claimed | verified in |
|---|---|
| Apple A18 Pro | `raw/metal_caps.txt:2` (`name = Apple A18 Pro`), `raw/sysctl_hw.txt:143` (`machdep.cpu.brand_string`) |
| SoC T8140 | `EXP-0002/README.md:7`; device-tree node `compatible="gpu,t8140"` in `raw/ioreg_dt_sgx.txt` |
| macOS 26.6 build 25G5043d | `raw/ioreg_devicetree.txt:4` (`"OS Build Version" = "25G5043d"`), `:249` (`"apmv" = <"26.6">`) |
| 5 GPU cores | `raw/sysprofiler_displays.txt` (`Total Number of Cores: 5`) |
| Metal 4 | `raw/sysprofiler_displays.txt` (`Metal Support: Metal 4`); `raw/metal_caps.txt:68` (`supportsFamily(Metal4 / 5002) = YES`) |
| feature family Apple9 max | `raw/metal_caps.txt:53-61` — Apple1…Apple9 all `YES`, and there is no Apple10 row |

**Corrected row (drop-in replacement for L17):**

```
| 2026-07-06 | Target is Apple A18 Pro, SoC T8140, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / feature family Apple9 max (Apple1-9 all YES, no Apple10 row) | ROADMAP; hardware-overview §1-§3 | HW-PROBE | EXP-0002: `experiments/EXP-0002-hw-identity-recon/{metal_caps.m,raw/metal_caps.txt,raw/sysctl_hw.txt,raw/sysprofiler_displays.txt,raw/ioreg_devicetree.txt,raw/ioreg_dt_sgx.txt}` |
```

---

### D-2 · L18 — cites `mtltest.m`, which does not exist anywhere in the repository

```
| 2026-07-06 | Runtime MSL compilation (`newLibraryWithSource:`) works with Command Line Tools only (no full Xcode / `metal` CLI) | ROADMAP / tooling | HW-PROBE | bring-up: `mtltest.m` built with `clang -framework Metal` |
```

**Defect.** `find . -name 'mtltest*'` returns nothing outside `mesa/` and `gpu_knowledge/`. The
cited artifact **has never been committed**, so this is the one row in the corpus whose named
evidence file cannot be produced. (It is not counted as "cites an absent artifact" by the
`EXP-0173` scan only because `mtltest.m` has no `/` and so does not match its path heuristic —
worth noting as a scanner blind spot, not just a row defect.)

**The claim is nonetheless supported by committed artifacts, from a different source:**

- `tools/shdump/shdump.m:126` calls `[dev newLibraryWithSource:src options:opts error:&err]`, and
  `tools/shdump/shdump.m:13` plus `tools/shdump/README.md:21` both document the build as
  *"on the A18 device, Command Line Tools only — no `metal` CLI needed"*.
- `EXP-0001/README.md:9` records the device state as *"Command Line Tools only (no `metal` CLI)"*
  and `:50` gives the build line; every `EXP-0001` `_agc.main` in `raw/` was produced through that
  path, so the capability is demonstrated by its output, not merely asserted.
- `EXP-0002/metal_caps.m:9` carries the same build comment.

**⚠ It is also now partly historical and should say so:** per `CLAUDE.md` and
`experiments/SUBAGENT_BRIEF.md`, the current G17P test target `users-MacBook-Neo.local`
**has full Xcode**. The row states a property of the *2026-07-06 bring-up host*, not a standing
constraint.

**Corrected row (drop-in replacement for L18):**

```
| 2026-07-06 | Runtime MSL compilation (`newLibraryWithSource:`) works with Command Line Tools only - no full Xcode and no `metal` CLI needed; every EXP-0001 shader was produced through that path. HISTORICAL: this describes the 2026-07-06 A18 bring-up host. The current G17P test target has full Xcode, so CLT-only is no longer a standing constraint. | ROADMAP / tooling; tools/shdump | HW-PROBE + OWN-SHADER | EXP-0001: `experiments/EXP-0001-shader-byte-extraction/{README.md,raw/}`; `tools/shdump/{shdump.m,README.md}` (the cited `mtltest.m` was never committed and is replaced by these) |
```

---

### D-3 · L104 — cites "W3: render from db.json", which resolves to nothing; and its own numbers are wrong

```
| 2026-07-07 | **✅ agx3.xml (W3):** 75-descriptor DB rendered into Mesa src/asahi/isa/AGX2.xml schema (117 ins / 10 group / 33 enum; parses xmllint+etree, 0 bit-conflicts, byte-reproducible via gen_agx3_xml.py). Inferred bytes → <zero> reserved (Mesa idiom). 6/75 zero-residue. | isa/agx3.xml | OWN-SHADER | W3: render from db.json |
```

**Defect 1 — unauditable citation.** "W3" is a work-stream label, not an experiment directory;
there is no `experiments/W3*`. The row names no commit and no file.

**Defect 2 — the `117 ins` figure is wrong, and was wrong when the row was written.** At the row's
own commit `3ee098e3` (`docs(W3): emit agx3.xml`), `docs/isa/agx3.xml` contains **116 `<ins>`
elements** — 65 top-level plus 51 group children — and `10 <group>` / `33 <enum>`, which do match.
The 117th "`<ins`" is inside an **XML comment** ("Each `<ins>`…"), and
`tools/agx-isa/gen_agx3_xml.py` counts with `re.findall(r"<ins\b", text)` over the raw text, so its
own printed total picks the comment up. Verified by parsing that commit's file with `ElementTree`:
`{'enum': 33, 'value': 115, 'group': 10, 'exact': 154, 'dest': 23, 'modifier': 80, 'src': 39,
'ins': 116, 'immediate': 27, 'zero': 196}`.

**Defect 3 — the row reads as a present-tense description of a file that has since changed by 2×.**
`docs/isa/agx3.xml` today holds **134 `<ins>` / 38 `<group>` / 101 `<enum>`** from a 172-descriptor
`db.json`. Nothing marks the row as a snapshot.

**Corrected row (drop-in replacement for L104):**

```
| 2026-07-07 | **✅ agx3.xml (W3) — SNAPSHOT AT `3ee098e3`, superseded by later DB growth:** the then-75-descriptor DB rendered into Mesa's `src/asahi/isa/AGX2.xml` schema, byte-reproducible from `db.json` via `gen_agx3_xml.py`, parsing under xmllint and ElementTree with 0 bit-conflicts; inferred bytes emitted as `<zero>` reserved, following the Mesa idiom; 6/75 descriptors zero-residue. **CORRECTED 2026-08-30 (EXP-0176): the element counts at that commit are 116 `<ins>` (65 top-level + 51 group children) / 10 `<group>` / 33 `<enum>` — NOT the 117 `<ins>` originally recorded.** The 117th token is inside an XML comment; `gen_agx3_xml.py` counts `<ins` by naive text search over the rendered string, so its printed total over-counts by one. The live file has since grown with `db.json` and now holds 134 `<ins>` / 38 `<group>` / 101 `<enum>` from 172 descriptors. | isa/agx3.xml | OWN-SHADER (rendered from our own DB; no device work) | W3, commit `3ee098e3`: `tools/agx-isa/gen_agx3_xml.py`, `tools/agx-isa/db.json`, `docs/isa/agx3.xml` (counts above are `git show 3ee098e3:docs/isa/agx3.xml`) |
```

---

### D-4 · L28 — cites the wrong artifact class for its own literals

```
| 2026-07-06 | G17P shader-code byte observations: 2-byte instruction parcels; `0e000000` terminates every main (empty kernel = just this); fixed `1ca01006…` preamble; 64-byte constant-program prolog. Interpretations pending HW round-trip. | isa/README §"Preliminary encoding observations" | OWN-SHADER | EXP-0001: `raw/*info.txt`, `raw/determinism.txt` |
```

**Defect.** The row's two load-bearing literals, `0e000000` and `1ca01006`, appear in **neither**
cited artifact. `raw/*info.txt` are section/symbol reports and `raw/determinism.txt` is a table of
sha256 values; the bytes live in `raw/k*.main.hex`, `raw/k*.text.hex` and `raw/k*.cprog.hex`.
This is the one row the audit flagged as `claim_reproduced: false` purely because of a mis-pointed
citation — the claim is fine.

**Every part of the claim reproduces against the right files:**

| claimed | verified |
|---|---|
| `0e000000` terminates every main | present in every `raw/k*.main.hex`; e.g. `k01_fadd.main.hex` ends `…9011000e000000` |
| empty kernel = just this | `raw/k00_empty.main.hex` is exactly `0e000000` (4 bytes) |
| fixed `1ca01006…` preamble | `raw/k01_fadd.main.hex` begins `1ca01006…`; present in 26 of the 42 `k*.hex` files, and every one of the 14 `k*.main.hex` files ends in `0e000000` |
| 64-byte constant-program prolog | `raw/k00_empty.cprog.hex` is 128 hex chars = **64 bytes**; `raw/k00_empty.info.txt` independently records `region _agc.main.constant_program: [0:64] (64 bytes)` and `region _agc.main: [64:68] (4 bytes)` |
| deterministic / sha256-stable | `raw/determinism.txt` — 14/14 kernels `[STABLE]` over 3 independent compilations (this is the ONE claim the original citation did support) |

**Corrected row (drop-in replacement for L28):**

```
| 2026-07-06 | G17P shader-code byte observations: 2-byte instruction parcels; `0e000000` ends every main (the empty kernel `k00_empty` is exactly those 4 bytes); fixed `1ca01006…` preamble; 64-byte constant-program prolog (`_agc.main.constant_program` = [0:64], `_agc.main` = [64:68] for the empty kernel). Deterministic: 14/14 kernels sha256-STABLE over 3 independent compilations. Interpretations pending HW round-trip; the terminator reading was later CORRECTED by EXP-0003/EXP-0010 (`0e000000` is NOT a required stop - splicing it is a no-op; program extent is out-of-band metadata). | isa/README §"Preliminary encoding observations" | OWN-SHADER | EXP-0001: `experiments/EXP-0001-shader-byte-extraction/raw/{k00_empty.main.hex,k00_empty.cprog.hex,k01_fadd.main.hex,k00_empty.info.txt,determinism.txt}` |
```

---

## Part 2 — three further structural defects found while checking the four

These were not in the dispatch. **The first is the most serious thing in this file.**

### D-5 · L90 — a markdown heading is glued into a table row, and it takes 100 of the 174 rows out of the table

`PROVENANCE.md` has exactly **one** header row (L15) and **one** delimiter row (L16). GFM needs
both to start a table, and any non-table line ends it.

L90 ends like this — note there is no newline before the `##`:

```
… | pipeline/README | DATA-TRACE + HW-PROBE | EXP-0021: MSAA/storage/action diffs |## Operational notes (not doc facts, but part of the paper trail)
```

Consequences, all mechanical:

1. **The `## Operational notes` heading never renders as a heading.** It is swallowed into a sixth
   cell of L90, which itself becomes a 6-cell row in a 5-column table.
2. L91–L92 are `- ` bullets, which **terminate the table**.
3. **L93 onward — 100 of the 174 logical rows, 57% of the log — restart with `|` but have no
   header or delimiter above them, so GFM does not render them as a table at all.** Every row from
   the ISA consolidation entry through the newest G17P rows is affected.

**Fix.** Split L90 into two lines and give the resumed table its own header + delimiter:

```
| 2026-07-07 | **✅ MSAA + memoryless + load/store:** … EXP-0021: MSAA/storage/action diffs |
                                       ← (newline here; the row ends at its own trailing pipe)
## Operational notes (not doc facts, but part of the paper trail)

- 2026-07-06: Device configured for unattended work …
- 2026-07-06: **Reboot recovery validated end-to-end.** …

## Provenance log (continued)

| Date | Fact (as documented) | Where in docs | Category | Experiment / source |
|------|----------------------|---------------|----------|---------------------|
| 2026-07-07 | ISA consolidation: DB 61 descriptors … |
```

### D-6 · L42 and L89 — two logical rows glued onto one physical line

Both lines carry a second complete row starting mid-line with `|| <date> |`:

- **L42**: `… EXP-0022: opcode diff vs FMA/shuffle controls + HW matmul || 2026-07-06 | **✅ HW-VALIDATED:** packed float immediate = 8-bit minifloat …`
- **L89**: `… EXP-0024: state-toggle + tgmem sweep || 2026-07-07 | **✅ TBDR tile size = 32×32 fixed …`

Each renders as one 11-cell row, so the second row's Date / Where / Category / Source columns are
silently dropped, and **any row-wise audit — including `EXP-0173`'s — treats the pair as a single
row and mis-attributes its cells.** Both were re-verified as *true* by the reproduction sample
(see `reproduction_sample.md`, rows L89-a and L89-b); the defect is purely structural. **Fix: break
each at the `||` into two lines.**

### D-7 · Bare `|` inside code spans splits cells and shifts columns — 11 rows affected

A `|` inside backticks is **not** protected in GFM. Splitting on unescaped pipes, these rows do not
have 5 cells:

| line | cells | what the extra split is | effect when rendered |
|---:|---:|---|---|
| L39 | 6 | `(reg<<1)\|size` written with a bare pipe | fact truncated; Where/Category/Source shift right by one |
| L42 | 11 | glued row (D-6) | second row's metadata dropped |
| L89 | 11 | glued row (D-6) | second row's metadata dropped |
| L90 | 6 | glued heading (D-5) | trailing heading becomes a 6th cell |
| L148 | 6 | `(dst_ext9<<2)` fact contains a bare pipe | columns shift |
| L165 | 6 | `((byte+6 & 0x3F) << 1)` fact contains a bare pipe | columns shift |
| L182 | 8 | `` `op_lsb|op|per_lane|op_msb` `` — three bare pipes in one code span | **Where / Category / Source are pushed past column 5 and dropped from the render** |
| L183 | 6 | bare pipe in the fact | columns shift |
| L187 | 7 | `` `0x16 = 0x06|0x10` `` | Where/Category/Source shift by two |
| L191 | 6 | `` `(reg<<1)|is32` `` | columns shift |
| L192 | 6 | `` `(dst<<4)|0x0b` `` | columns shift |

Ten further rows (L37, L56, L70, L75 and others) already use the correct `\|` escape and render
fine — so the convention exists in the file and is simply applied inconsistently.

**Fix: escape every `|` inside a table cell as `\|`.** Mechanical check, safe to run repeatedly:

```
python3 experiments/EXP-0176-provenance-chain/analysis/table_integrity.py
```

which writes `analysis/table_integrity.json` and prints every row whose GFM cell count is not 5,
every physical line carrying two logical rows, and the line at which the table stops rendering.

---

## Part 3 — one defect of *content*, not of formatting

### D-8 · L75 states a formula that a later experiment REFUTED, and is not marked `SUPERSEDED`

```
| 2026-07-06 | **Lossless compression:** … aux size = image_bytes/128 = 1 state byte per 8×4 block … | tiling/README | HW-PROBE + DATA-TRACE | EXP-0017: entropy tests (gradient/noise/split) |
```

`EXP-M4-07` (TIL-5) refuted `aux = image_bytes/128` at bpp8 and bpp16 and replaced it with
`aux = numTexels/32 = paddedImageBytes/(32·bpp)`; `docs/tiling/README.md:236-237` already says so
in as many words — *"The old `aux_bytes = image_bytes / 128` formula is WRONG for bpp≠4 — it
over-counts 2× at bpp8 and 4× at bpp16"*.

So the deliverable is correct and **the provenance log is the only place the refuted formula still
stands unqualified.** `CODEX.md` §8 requires the superseded record to be marked, the correcting
experiment cited, and every derived document updated; the first two were never done — in part
because **`EXP-M4-07` has no `PROVENANCE.md` row at all** (see `drafted_rows.md` §1a).

**Corrected row (drop-in replacement for L75):**

```
| 2026-07-06 | **Lossless compression:** enabled iff no-ShaderWrite AND size >= ~16x16 tile. Secondary VA @desc+0x10 = (word4 \| word5[0:11]<<32)<<4 = base+paddedImageBytes; **aux size = 1 state byte per 8x4-texel block** (states 0x03/0x15/0x7f observed), Morton-of-blocks order. **SUPERSEDED IN PART 2026-07-07 by EXP-M4-07 (TIL-5): the byte-form written here as `image_bytes/128` holds ONLY at bpp4. The general rule is `aux_bytes = numTexels/32 = paddedImageBytes/(32*bpp)`; the /128 form over-counts 2x at bpp8 and 4x at bpp16.** UNKNOWN: compressed-block codec bit-layout + state-code meaning (a driver can wire up flags/aux or disable compression). | tiling/README §4.3 | HW-PROBE + DATA-TRACE | EXP-0017: `experiments/EXP-0017-tiling/{RESULTS.md,raw/compress_rt64.txt,raw/compress_split64.txt}` (bpp4 only); corrected by EXP-M4-07: `experiments/EXP-M4-07-tiling-coverage/RESULTS.md` |
```

---

## Suggested order of application

1. **D-5** first — it is the only defect that changes what a reader *sees*, and it hides 57% of the log.
2. **D-6** and **D-7** — mechanical; re-run `table_integrity.py` until it reports 0.
3. **D-8** — a wrong formula standing in the paper trail; pair it with the `EXP-M4-07` row from `drafted_rows.md` §1a so the correction has a home.
4. **D-1 … D-4** — the four the dispatch named; all four claims survive, only their citations change.
