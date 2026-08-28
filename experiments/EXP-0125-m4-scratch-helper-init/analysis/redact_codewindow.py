#!/usr/bin/env python3
"""One-shot redaction script for the superseded run01 code-window content
capture (see SUPERSEDED.md in the target directory). Replaces each
code-window .hex file's byte content with a redaction notice + sha256 of
the original bytes (for auditability that content existed and was
non-trivial, without retaining it), per CODEX.md's own stated contingency
for material that cannot be committed. Run once, by hand; not part of the
regular run.py/verify.py pipeline.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import traceparse as TP  # noqa: E402

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if not TARGET or not TARGET.is_dir():
    raise SystemExit("usage: redact_codewindow.py <dir-to-scan>")

redacted = []
for p in sorted(TARGET.rglob("bo_va10000000000_sz10000.hex")):
    original = TP.hex_file_bo_bytes(p)
    digest = hashlib.sha256(original).hexdigest()
    nz = sum(1 for b in original if b != 0)
    p.write_text(
        f"# ALLBO_PREFIX gpu_va=0x10000000000 size=0x10000 class=AGXAcceleratorG16G REDACTED\n"
        f"# CONTENT REDACTED per clean-room boundary correction -- see SUPERSEDED.md in this "
        f"run's directory. Original captured length={len(original)} bytes, "
        f"nonzero_byte_count={nz}, sha256={digest}. The actual byte content is not retained.\n"
    )
    redacted.append({"path": str(p), "captured_len": len(original), "nonzero": nz, "sha256": digest})

print(f"redacted {len(redacted)} files")
for r in redacted:
    print(r)
