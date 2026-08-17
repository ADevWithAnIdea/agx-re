#!/usr/bin/env python3
"""Measure synthesis evidence in the repository-authored Apple9 ISA database."""

import collections
import importlib.util
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def load_roundtrip(repo, tool_dir):
    sys.path.insert(0, str(tool_dir))
    import isadb  # pylint: disable=import-error,import-outside-toplevel

    spec = importlib.util.spec_from_file_location(
        "agx_roundtrip", tool_dir / "roundtrip_test.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return isadb, module


def main():
    repo = Path(__file__).resolve().parents[3]
    tool_dir = repo / "tools/agx-isa"
    subprocess.run(
        [sys.executable, str(tool_dir / "roundtrip_test.py")],
        cwd=tool_dir,
        check=True,
        stdout=subprocess.DEVNULL,
    )

    database = json.loads((tool_dir / "db.json").read_text())
    descriptors = database["instructions"]
    isadb, roundtrip = load_roundtrip(repo, tool_dir)

    real_mnemonics = []
    for encoded in roundtrip.REAL_INSTRS.values():
        record, _ = isadb.decode_one(bytes.fromhex(encoded), 0)
        real_mnemonics.append(record["mnemonic"])

    program_mnemonics = []
    for encoded in roundtrip.REAL_PROGRAMS.values():
        records, leftover = isadb.disassemble(bytes.fromhex(encoded))
        if leftover:
            raise RuntimeError(f"round-trip program left {len(leftover)} bytes")
        program_mnemonics.extend(record["mnemonic"] for record in records)

    synth_mnemonics = [mnemonic for mnemonic, _ in roundtrip.SYNTH]
    fixed_coverage = set(real_mnemonics + program_mnemonics + synth_mnemonics)
    descriptor_names = {descriptor["mnemonic"] for descriptor in descriptors}
    field_types = collections.Counter(
        field["type"] for descriptor in descriptors for field in descriptor.get("fields", [])
    )

    def combined_text(descriptor):
        return " ".join(
            [descriptor.get("semantics", ""), descriptor.get("provenance", "")]
        ).lower()

    xml_root = ET.parse(repo / "docs/isa/agx3.xml").getroot()
    report = {
        "schema": 1,
        "scope": "repository structural audit; no new hardware claim",
        "database": {
            "descriptors": len(descriptors),
            "fields": sum(field_types.values()),
            "field_types": dict(sorted(field_types.items())),
            "descriptors_with_raw_fields": sum(
                any(field["type"] == "raw" for field in descriptor.get("fields", []))
                for descriptor in descriptors
            ),
            "descriptors_with_inferred_text": sum(
                "infer" in combined_text(descriptor) for descriptor in descriptors
            ),
            "descriptors_with_needs_splice": sum(
                "needs-splice" in combined_text(descriptor) for descriptor in descriptors
            ),
            "non_standalone_fallback_descriptors": sorted(
                descriptor["mnemonic"]
                for descriptor in descriptors
                if "not a standalone hardware opcode" in combined_text(descriptor)
            ),
        },
        "central_tests": {
            "real_instruction_vectors": len(real_mnemonics),
            "real_vector_unique_descriptors": len(set(real_mnemonics)),
            "whole_program_unique_descriptors": len(set(program_mnemonics)),
            "synthesized_field_vectors": len(synth_mnemonics),
            "synthesized_unique_descriptors": len(set(synth_mnemonics)),
            "any_fixed_vector_unique_descriptors": len(fixed_coverage),
            "descriptors_without_fixed_vector": sorted(descriptor_names - fixed_coverage),
        },
        "generated_xml": {
            "instruction_elements": len(xml_root.findall(".//ins")),
            "group_elements": len(xml_root.findall(".//group")),
            "zero_placeholders": len(xml_root.findall(".//zero")),
        },
        "verdict": "OPEN: codec round-trip is not compiler-ready synthesis proof",
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
