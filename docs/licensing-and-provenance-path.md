# Licensing and provenance path for downstream implementers

**Row:** `DOC-03` of `APPLE9_RE_IMPLEMENTATION_GAPS.md`.
**Audience:** the separate implementation team that will add Apple9 support to Mesa `asahi`,
and any later agent who derives a table or an implementation artifact from this repo.
**Status:** normative for how material leaves this repo. Evidence label: `PUBLIC` (license
texts, Mesa's own licensing, and this repo's own `LICENSE` files). No hardware claim is made
here.

> **Not legal advice.** This document records the *engineering* provenance path and the
> decisions that remain open. The relicensing decision in §5 belongs to the copyright holder
> (and, if they want one, their counsel) — not to this document and not to any agent.

---

## 1. What this repo is licensed under today

| Artifact class | Location | License as shipped |
|---|---|---|
| Prose documentation | `docs/**.md`, root `*.md` | **CC-BY-NC-SA-4.0** (`docs/LICENSE`) |
| Code | `tools/**`, `experiments/**/harness`, `**/analysis`, `*.py`, `*.m`, `*.sh` | **GPL-3.0** (`LICENSE`) |
| Authored shader source | `experiments/**/kernels/*.metal` | **GPL-3.0** |
| Machine-readable encoding data | `tools/agx-isa/db.json`, `docs/isa/agx3.xml`, `docs/isa/encoding-tables.md`, `docs/descriptors/format-table.md` | **GPL-3.0** (code/data/XML per `README.md`) |
| Raw captures | `experiments/**/raw/**` | **GPL-3.0** as shipped; see §3 — the *contents* are uncopyrightable measurement data |
| Upstream shader corpora | `thirdparty/**` | **each project's own** permissive license, unmodified, never imported into a deliverable |
| Read-only references | `mesa/` (MIT), `gpu_knowledge/` (mixed, incl. proprietary) | **not ours; never redistributed from here** |

**Copyright holder: a single party** (`Copyright (c) 2026 Cody Ho`, `README.md`). There are no
outside contributors, no CLA to collect, and no multi-party negotiation. This is the single most
important fact in this document: **relicensing is available on request from one person.** The
"obtain relicensing/dual licensing" option that `DOC-03` lists as one of three is, here, the
cheap one.

## 2. Why the current split blocks direct import into Mesa

Mesa is predominantly **MIT**, and its policy is that new code arrives under MIT or a similarly
permissive license. Against that:

- **`CC-BY-NC-SA-4.0` on the prose is fatal twice over.** The **NonCommercial** clause is
  incompatible with Mesa's licensing on its face (Mesa is used commercially throughout), and
  **ShareAlike** is a copyleft term Mesa will not take. A CC-BY-NC-SA document cannot be
  imported into Mesa in any form that carries its license.
- **`GPL-3.0` on the code, data, and XML is incompatible with MIT-licensed Mesa core.** GPL-3.0
  is one-way compatible: MIT code can go into a GPL project, not the reverse. Dropping
  `tools/agx-isa/db.json` or `docs/isa/agx3.xml` into Mesa's tree as-is would relicense the
  surrounding work, which Mesa will reject.

So **no artifact in this repo can be copied into Mesa as it stands.** That is not a defect in
the work; it is a deliberate consequence of the license the repo chose, and it has a clean fix.

## 3. The distinction that actually governs: facts vs. expression

Copyright protects **expression**, not **facts**. Nearly everything this project exists to
produce is fact:

**Not copyrightable — free for the implementation team to use, with no license from us:**
- Bit positions, field widths, opcode values, register indices, encoding constants.
- Measured hardware limits (the 2^43 address wrap, the 261,728 B/thread scratch ceiling, the
  124-component varying capacity, the 2^28 texel-buffer ceiling, the 96-GPR file with the
  `r(R mod 64)` aliasing).
- Observed behaviors ("`interpolate_at_offset` violates its documented contract", "OOB reads
  return zero but not page-wide", "`extract_bits` has a three-way contract").
- The byte contents of command buffers and descriptors we captured — these are machine-produced
  data, and the Asahi copyright/RE policy this project follows treats them as non-copyrightable.

**Copyrightable — ours, and covered by the licenses in §1:**
- The **prose** of `docs/` — our sentences, our explanations, our organization of the argument.
- The **code** of `tools/` and every harness — our implementation of extractors, assemblers,
  disassemblers, splice testbeds, verifiers.
- The **selection, structure, and arrangement** of our tables and schemas: the XML schema of
  `agx3.xml`, the JSON schema of `db.json`, the choice of which columns a format table has and
  what the fields are named. Thin, but non-zero, and thin-but-non-zero is the awkward case.

**Practical consequence.** A Mesa implementer may take every *number and behavior* in `docs/`
and write their own MIT code from it, and this needs no permission. What they may not do is
copy our sentences, our XML file, our JSON file, or our Python. The existing clean-room split —
we document, they implement — already produces the right behavior; §5 removes the remaining
friction for the machine-readable artifacts, where re-typing thousands of factual rows by hand
is pure waste.

## 4. Inbound provenance: what we consumed, and the strings attached

| Source | License | How we used it | Obligation on us |
|---|---|---|---|
| `mesa/` — pinned at `3c4d3e46d19f2f4e951f3ae059543b03592f7944`, `include/drm-uapi/asahi_drm.h` SHA-256 `69fe416b…5e89` (re-verified 2026-08-28) | **MIT** | Read-only. `EXP-0044`/`EXP-0045` derived the 65-leaf UAPI obligation inventory from it. | Any table that reproduces the **structure and field-name arrangement** of `mesa/include/drm-uapi/asahi_drm.h` must carry the MIT notice. Individual field names are not copyrightable; the header's arrangement plausibly is. Our derived matrix is a re-expression against a *pinned, hash-verified* revision — record that pin wherever the table appears. |
| `gpu_knowledge/apple_official/` | **Apple, proprietary** | Read for publicly-documented API semantics only. | Facts and API names only. **Never** reproduce Apple's prose, tables, or diagrams into `docs/`. Cite, don't quote. |
| `gpu_knowledge/asahi_linux/`, `blog_posts/` | author copyright, various | Read for the copyright/RE policy and public M1/M2 findings. | Cite by URL. Do not lift prose. Findings attributed as `PUBLIC` in `PROVENANCE.md`. |
| `gpu_knowledge/papers/`, `third_party/` | various | Background. | Same. |
| dougallj/applegpu | **MIT** | `EXP-0001` used it as a structural template for our own extractor; it *failed* on Apple9 bytes and was not extended. | Attribute in `tools/shdump/`. Our parser is our own implementation "informed by" it — that attribution is already in `PROVENANCE.md` line 27 and must survive any relicensing. |
| `thirdparty/**` | Apache-2.0 / BSD-3 / MIT / Unlicense | Unmodified shader corpora, disassembler coverage inputs **only**. | Each keeps its own `LICENSE` + `PROVENANCE.md`. **Never** imported into a deliverable; nothing in `docs/` derives from them beyond aggregate coverage percentages, which are facts. |
| Apple binaries, kexts, firmware, the shader compiler | proprietary | **Never inspected.** | The Prime Directive. `PROVENANCE.md` has no `BINARY-RE` category by construction. |

## 5. The three paths `DOC-03` names, evaluated

### Path A — relicense / dual-license the machine-readable deliverables *(recommended)*

Because there is exactly one copyright holder, the holder can add a permissive license to the
artifacts that are meant to be imported, without touching the rest of the repo.

Proposed split, for the copyright holder to accept or reject:

| Artifact | Proposed | Rationale |
|---|---|---|
| `tools/agx-isa/db.json`, `docs/isa/agx3.xml`, `docs/isa/encoding-tables.md`, `docs/descriptors/format-table.md` | **dual GPL-3.0 OR MIT** | These are the import targets. Their content is ~all fact; our expressive contribution is schema choice. Dual-licensing costs nothing and deletes the whole problem. |
| `experiments/**/raw/**` | **CC0 / public-domain dedication** | Measurement data. Asserting copyright over machine-produced captures is both weak and counterproductive to the clean-room defense. |
| `docs/**.md` prose | **unchanged (CC-BY-NC-SA-4.0)** | Nobody needs to import our sentences. Keeping copyleft prose is harmless and preserves attribution. |
| `tools/**` implementations, harnesses | **unchanged (GPL-3.0)** | Mesa does not want our extractor or our splice testbed; these are RE instruments, not driver code. |

**Mechanics if adopted:** add `SPDX-License-Identifier: GPL-3.0-or-later OR MIT` at the top of
each dual-licensed file (JSON gets a `"_license"` key since JSON has no comments), state the
split in `README.md` §Legal, and add a `LICENSE.MIT`. One commit. Carry the dougallj/applegpu
attribution from §4 into that notice.

**This has not been done.** Until the copyright holder says otherwise, everything is as §1
describes, and Path B is what the implementation team must use.

### Path B — deliberate clean-room factual re-expression *(available now, no permission needed)*

The implementation team reads `docs/`, extracts the **facts** (§3), and writes their own
MIT-licensed schemas and code. This is what the project's clean-room split already assumes and
is the reason `CLAUDE.md` forbids us from writing Mesa driver code.

For this to be defensible, the re-expression must be **deliberate**, not incidental:
1. Work from the **fact tables and stated ranges**, not from our prose phrasing or our schema.
2. Choose your own field names, your own file format, your own row/column organization. Where
   Mesa has an existing convention (GenXML), use Mesa's, not ours.
3. Do **not** copy `agx3.xml` or `db.json` and rename things — a renamed copy is a copy.
4. Record, on your side, which of our documents each fact came from, so the fact's provenance
   chain back to an experiment survives.

Cost: real, and it scales with table size — which is exactly why Path A is recommended for the
big machine-readable tables and Path B is fine for everything else.

### Path C — reviewed separation

Keep this repo entirely outside Mesa, ship the documentation as an external normative reference,
and let Mesa cite it. Viable, and the status quo, but it leaves every table to be re-typed by
hand under Path B forever. Recommended only as the fallback if Path A is declined.

## 6. Provenance requirements for any derived artifact

**Binding on every later agent.** When you produce a table, schema, or implementation artifact
that a downstream consumer might import, record all six of these *with the artifact*:

1. **Upstream chain** — the `EXP-NNNN` that produced each fact, and the commit it landed in.
   A table row with no traceable experiment does not ship.
2. **Evidence label** per the `CODEX.md` ladder (`HW-VALIDATED` > `DATA-TRACE-VALIDATED` >
   `OWN-SHADER-DIFF` > `STRUCTURAL` > `INFERRED` > `UNKNOWN`) — per row, not per table.
   See `DOC-02`.
3. **Target** — M4/G16G or A18/G17P, per row. Never silently generalize; the `EXP-0119`
   A18↔M4 contradiction is exactly why.
4. **Tested range** — the parameter interval actually swept. A value validated at one point is
   not a validated range, and a table that hides this invites an implementer to extrapolate off
   a cliff.
5. **Inbound licenses touched** — if any row derives from `mesa/`, name the pinned revision and
   carry the MIT notice (§4). If from a public source, cite it.
6. **A `PROVENANCE.md` row**, per `CLAUDE.md` step 8. No fact enters `docs/` without one.

Artifacts already meeting this bar: `docs/isa/encoding-tables.md` and `docs/isa/agx3.xml` (both
generated from `tools/agx-isa/db.json`, itself round-trip validated 302/302 at commit
`cf544b4d`). Artifacts that need a labeling pass before they can ship: see `DOC-02`.

## 7. What is still open

- **The Path A decision is the copyright holder's and has not been made.** Nothing in this
  document changes any license.
- **`DOC-02` (per-field evidence classification) is a prerequisite for Path A being useful.**
  Dual-licensing a table whose rows are not individually labeled just exports our uncertainty
  into someone else's driver.
- **No downstream consumer has reviewed this path.** It is written from Mesa's public licensing
  posture, not from a conversation with Mesa maintainers.
