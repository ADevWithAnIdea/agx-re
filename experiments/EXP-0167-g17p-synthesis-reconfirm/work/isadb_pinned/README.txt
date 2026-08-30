PINNED SNAPSHOT of tools/agx-isa/{db.json,isadb.py}, taken at EXP-0158
pre-registration time and hash-recorded in CAPTURE_CONTRACT.json.

WHY.  tools/agx-isa/db.json is owned by the orchestrator and is edited
CONCURRENTLY while this experiment runs (it changed under this agent mid-read
on 2026-08-29: `falu2.mod_lo` was split into `srcA_class`/`srcB_class`,
landing EXP-0138's operand-source-class model).  A capture whose generated
bytes depend on a file that can change between run01 and run02 is not
reproducible, and SUBAGENT_BRIEF.md forbids gating a cross-run comparison on a
moving dependency.  Pinning a byte-identical copy makes the generated corpus a
pure function of files this experiment controls.

The snapshot is NOT edited.  `tools/agx-isa` itself is untouched.
