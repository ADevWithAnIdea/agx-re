# EXP-0176 progress

- 2026-08-30 — dir created; read CLAUDE.md, CODEX.md (§9), SUBAGENT_BRIEF.md, EXP-0173 provenance_audit.py.
- 2026-08-30 — M1 DONE: independent enumeration written (`analysis/enumerate.py` → `enumerate.json`).
  **Re-derived count differs from the dispatch's 36/11.** Over ALL `experiments/EXP-*` dirs
  (numeric + M4 + M5 + G1 + O2), 214 committed dirs, **67 have no PROVENANCE.md row, 43 of those
  are cited in `docs/`**. Restricted to `EXP-NNNN` numeric ids (EXP-0173's scope) it is now
  **35 missing / 11 cited in docs** — EXP-0171/0172 gained rows since EXP-0173 ran, EXP-0173
  itself now needs one. The extra 32 are the ENTIRE EXP-M5-* workstream (23, all cited in docs)
  plus EXP-M4-01..07/09/10/11 (9, all cited in docs).
- NEXT: M2 read RESULTS.md of each missing experiment; M3 draft rows; M4 broken rows; M5 repro sample.
- 2026-08-30 — M2a DONE: read the 11 numeric docs-cited experiments (0068 0078 0080 0104 0105 0106 0111 0114 0115 0142 0170)
  and how docs/ cites each. Key nuance: EXP-0142 and EXP-0080's docs mentions are DISCLAIMERS
  ("IN FLIGHT, not used as evidence" / "quarantined ... UNKNOWN"), not fact-supplying citations.
- 2026-08-30 — M2b DONE: read EXP-M4-01..07/09/10/11 RESULTS.md. NOTE: EXP-M4-05 and EXP-M4-06 ran on the
  **A18 Pro**, not the M4, despite the EXP-M4-* prefix — target must be labelled A18/G17P in their rows.
- 2026-08-30 — M2c DONE: read all 23 EXP-M5-* report.md (M5 uses `report.md`, not RESULTS.md;
  EXP-M5-15 has only `raw/rrm_probe.txt` and no report at all).
- 2026-08-30 — M4 (broken rows) IDENTIFIED: PROVENANCE.md L17, L18, L104 cite no resolvable artifact;
  L28 cites `raw/*info.txt` + `raw/determinism.txt` but its literals (`0e000000`, `1ca01006`) live in
  `raw/k*.main.hex` / `raw/k*.text.hex`. L104's own numbers are ALSO wrong: at its own commit 3ee098e3
  agx3.xml had 116 <ins> elements (65 top-level + 51 group children), not 117 — the 117th "<ins" is
  inside an XML comment and the generator's naive text count picked it up.
- NEXT: read the 24 numeric non-docs experiments, then draft.
- 2026-08-30 — M2d DONE: read the 24 numeric non-docs experiments. Most are QUARANTINED / STOPPED /
  process-history-only; five (EXP-0145/0149/0150/0151/0152, + EXP-0142) are M4-pivot survivors that
  reached a frozen pre-registration and NO verdict — `analysis/` empty, 0 mentions in validation.json.
- 2026-08-30 — M5 (reproduction sample) DONE: seed 20260830 selected PROVENANCE lines
  25, 31, 43, 75, 89, 100, 137, 157, 170, 190. **8 reproduce fully, 1 partial, 1 FAILS AS WRITTEN.**
  * L75 (EXP-0017 `aux = image_bytes/128`) is REFUTED in general by EXP-M4-07 TIL-5 and by
    `docs/tiling/README.md` §4.3 ("the old formula is WRONG for bpp≠4"); the row carries no
    SUPERSEDED marker and the correcting experiment has no row at all.
  * L190 (EXP-0168) load-bearing claim `uniform_mov.dst moved_total=214` reproduces exactly, but its
    cross-run-agreement summary is a BEST-ARM figure: `pack_convert.b7` is reported at 100.000%
    while two of its three arms sit at 99.219%.
- 2026-08-30 — BONUS DEFECT FOUND: PROVENANCE.md has exactly ONE header+delimiter pair (L15/L16),
  and the table is BROKEN at L90-L92 — L90 ends with `|## Operational notes ...` glued on, then two
  `- ` bullets. Everything from L93 to L192 (100 of 174 logical rows) therefore falls outside the
  markdown table. Two rows (L42, L89) are also two logical rows glued onto one physical line.
- NEXT: write the four analysis deliverables + RESULTS.md + manifest.json.
