# EXP-0232 results — canonical `iadd2` register reach

**Verdict: PASS on G17P, with the original destination-boundary hypothesis refuted and
corrected.** The canonical ten-byte b32 register-register `iadd2` directly reads source A from
r0..r31, directly reads source B from r0..r63, and directly writes every physical GPR r0..r95.
G17P r96 is the first invalid destination and raises a contained command-buffer fault; r127 also
faults rather than wrapping.

Pre-registration commit: `e983319c`. Boundary amendments were frozen before their respective
dispatches as commits `9a58b64b` and `1c170338`.

## 1. Main direct-reach result

The two formal runs each contained 8 slot probes, 191 main cases, and 2 wrong-oracle controls:

- `raw/g17p_e0232_run01` — canonical order, 201 dispatches;
- `raw/g17p_e0232_run02` — reverse order, 201 dispatches.

All **382/382 main observations** were exact across the pair:

| role | canonical selector | direct physical set | result |
|---|---|---|---|
| source A | `srcB_ext = A << 2` | r0..r31 | 32/32 exact per run |
| source B | `srcB_imm = B << 2` | r0..r63 | 64/64 exact per run |
| destination | `dst = (D << 1) | 1` | r0..r94 in the main sweep | 95/95 exact per run |

The source-A selector is seven bits, so r32 is not representable in this canonical field. The
source-B selector is eight bits, so r64 is not representable in its canonical field. These are
form-specific encoding bounds, not out-of-file hardware accesses. Alternate extension/control
forms remain separate capability questions.

Every source and its modulo-16/32 alternatives held distinct codewords. Exact source selection
had zero mismatches; modulo-16 was rejected by 16 source-A cases and 48 source-B cases, and
modulo-32 was rejected by 32 source-B cases. Both wrong-oracle controls fired in both runs.

## 2. Corrected destination boundary

The pre-registration mistakenly attributed M4/G16G r95-fault evidence to G17P. Amendment 01 froze
a target-specific check before dispatch. Its immutable run, `raw/g17p_e0232_boundary01`, produced:

- exact r94 controls before and after every candidate fault;
- **an exact write to r95**, refuting the expected-fault model;
- contained command-buffer faults at r96 and r127;
- zero hangs, followed by a responsive device.

The original `analysis/hazard_result.json` therefore remains **failed** at exactly
`h_d95:not-contained-fault`; it is refutation evidence, not a failed experiment.

Amendment 02 froze the corrected model and repeated it in canonical and reverse order as
`raw/g17p_e0232_boundary02` and `raw/g17p_e0232_boundary03`. Both runs agreed exactly:

```text
r95  exact
r96  contained CMDBUF_ERROR
r95  exact after recovery
r127 contained CMDBUF_ERROR
r95  exact after recovery
```

Therefore G17P's maximum valid physical `iadd2` destination is r95, its first invalid destination
is r96, and larger encodable destinations do not silently wrap. This differs from the inherited
M4/G16G observation and must remain target-qualified.

## 3. Five gates

| gate | result |
|---|---|
| **A — geometry** | **PASS.** Every main/control/boundary body contains exactly one generated `iadd2`; both formal pairs have byte-identical programs case-for-case, with no decode or descriptor-alias disagreement. |
| **B — detection** | **PASS.** Distinct target/alias codewords and both wrong-oracle controls prove the result channels discriminate exact selection. Exact controls surrounding every invalid destination prove post-fault execution. |
| **C — semantics** | **PASS.** All main cases are exact; the corrected boundary pair agrees with no failures. The original boundary model is explicitly refuted rather than rewritten. |
| **D — generation** | **PASS.** `CARRIER=0`, `COPIED=0`, and no donor fields in every dispatched program. |
| **E — target/reproduction** | **PASS.** All five captures have quiet-process samples with zero foreign runners/compiler services, zero hangs, and zero runner restarts. Main runs have zero recoveries; each deliberate-boundary run has exactly the two expected recoveries. |

Machine-readable gates: `analysis/formal_result.json`, `analysis/boundary_result.json`,
`analysis/hazard_result.json`, and `analysis/gate_e_result.json`.

## 4. What this closes, and what it does not

This closes the physical-GPR reach of one canonical ten-byte b32 register-register `iadd2` form.
It does not close b16, b64/pair, immediate, uniform, compressed, or alternate extension/control
forms. In particular, an emitter must range-check the two canonical source roles independently:
source A stops at r31 and source B stops at r63 even though the destination reaches r95.

## 5. Clean-room provenance

Clean-room provenance: OWN-SHADER + HW-PROBE.

The programs were assembled from documented project rules and executed through the public Metal
API on Apple A18 Pro / G17P. Apple binary introspection: **NONE**.
