#!/bin/sh
# EXP-0173 — reproduce every verdict in RESULTS.md. Pure analysis: no device, no SSH, no GPU.
# Run from the repository root.
set -e
R=experiments/EXP-0173-closure-audit

echo "=== tool gates, as published ==="
python3 tools/agx-isa/validate_labels.py
python3 tools/agx-isa/match_overlap_report.py
python3 tools/agx-isa/emit_worklist.py | head -30
python3 tools/agx-isa/roundtrip_test.py | tail -3
python3 work/merge_verdicts.py --dry-run experiments/EXP-01*/analysis/field_verdicts.json | tail -8 || true
# match_overlap_report.py REWRITES tools/agx-isa/match_overlap.json; restore it:
git checkout -- tools/agx-isa/match_overlap.json 2>/dev/null || true

echo "=== EXP-0173 analyses ==="
python3 $R/analysis/gate_sensitivity.py
python3 $R/analysis/provenance_audit.py
python3 $R/analysis/template_dependency.py
python3 $R/analysis/vacuous_fields.py
python3 $R/analysis/operand_sanity.py
python3 $R/analysis/closure_rules.py
python3 $R/analysis/compiler_readiness.py
echo "=== done; JSON reports are in $R/analysis/ ==="
