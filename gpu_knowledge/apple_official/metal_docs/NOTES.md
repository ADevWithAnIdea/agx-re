# Metal Documentation Notes

## Contents

### metal-overview.md
- Source: https://developer.apple.com/metal/ (Apple Metal landing page)
- Overview of Metal framework, Metal 4 (latest), MetalFX, ML integration, tools
- Covers hardware requirements: M1+ for Mac, A14+ for iPhone/iPad

### gpu-devices-work-submission.md
- Source: https://developer.apple.com/documentation/metal/gpu_devices_and_work_submission
- Apple's dev docs use heavy JavaScript; content captured from API reference knowledge
- Covers MTLDevice, MTLCommandQueue, MTLCommandBuffer, command encoders
- Includes load/store action reference table (critical for TBDR optimization)

### metal-feature-set-tables.pdf (3 MB)
- Downloaded from: https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf
- Date fetched: 2026-05-09
- Official Apple document listing GPU feature support across hardware generations
- Organized by GPU family (Apple1 through Apple9+, Mac1, Mac2, etc.)
- Key data: which features are available on which SoCs (ray tracing, mesh shading,
  sparse textures, argument buffers, etc.)

## Notes for Asahi/Reverse Engineering Context
- GPU family names map to hardware:
  - Apple7 = A15 Bionic, M2
  - Apple8 = A16 Bionic
  - Apple9 = A17 Pro, M3 family (first with hardware ray tracing + mesh shading)
  - Mac2 = M1 family
  - Mac1 = AMD/Intel discrete GPUs in older Macs
- The feature set tables are the ground truth for "does this Apple GPU support X"
- MTLGPUFamily enum: https://developer.apple.com/documentation/metal/mtlgpufamily

## Additional Documentation to Fetch (not yet captured)
- https://developer.apple.com/documentation/metal/mtlgpufamily (GPU family enum values)
- https://developer.apple.com/documentation/metal/tailor-your-apps-for-apple-gpus-and-tile-based-deferred-rendering
