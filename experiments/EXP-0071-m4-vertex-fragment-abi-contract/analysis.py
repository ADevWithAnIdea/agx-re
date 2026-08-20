#!/usr/bin/env python3
import argparse,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
CASES=("sep_f32","interleaved_f32","interleaved_offset","separate_offset","u8norm_to_f32","u8raw_to_u32","u16norm_to_f32","center_perspective","center_no_perspective","flat_varying","direct_constant")
a=argparse.ArgumentParser();a.add_argument("--static",action="store_true");x=a.parse_args()
if not x.static:raise SystemExit("capture analysis unavailable before audited runner")
if (HERE/"raw").exists():raise SystemExit("raw exists; use future captured verifier")
print(json.dumps({"state":"PRE_GPU","result":"NO_OBSERVATIONS","cases":CASES},sort_keys=True))
