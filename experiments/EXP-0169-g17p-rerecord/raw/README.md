# EXP-0169 raw/ — append-only evidence

Run ids and their role (frozen in `../CAPTURE_CONTRACT.json`):

| run id | role |
|---|---|
| `pilot01` | harness pilot: carriers, baseline, `device_load` `idx_off` calibration, **liveness ladder**, store shape. A `pilot` id, which EXP-0164's `NONGATED` filter excludes from any promotion **by construction**. |
| `g17p_20260830_run01` | gated run A, forward arm order |
| `g17p_20260830_run02` | gated run B, reverse arm order |

Every file here is append-only. A partial run is **retained exactly as it stopped** — never
topped up, never reused, never deleted — and its successor takes a **new** run id
(`SUBAGENT_BRIEF`, learned the hard way in EXP-0085).

`sweep.jsonl` schema: `../PRE_REGISTRATION.md` §10. `instr` is always a db.json mnemonic and
`field` always a db.json field name — that is exactly what EXP-0140's raw got wrong
(`instr: "regmove"`), and why its per-value records could not be attributed.
