# MSL Specification Notes

## Contents

### metal-shading-language-spec.pdf (12 MB)
- Downloaded from: https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf
- This is the official Apple Metal Shading Language Specification, Version 4
- Date fetched: 2026-05-09
- Covers the complete MSL language: types, address spaces, built-in functions, attributes,
  graphics shaders, compute shaders, ray tracing functions, mesh shaders, etc.

## Related Resources
- Metal CI Kernels Reference: https://developer.apple.com/metal/MetalCIKLReference6.pdf
- MTLLanguageVersion API: https://developer.apple.com/documentation/metal/mtllanguageversion
- Metal Resources page: https://developer.apple.com/metal/resources/

## Notes for Asahi/Reverse Engineering Context
- The MSL spec describes the shader language that Apple GPUs execute
- Address spaces (device, constant, threadgroup, thread, ray_data) map to GPU memory hierarchy
- Built-in attributes ([[vertex]], [[fragment]], [[kernel]], [[tile]], [[mesh]], [[object]])
  correspond to different shader stages in the Apple GPU pipeline
- The spec documents metal::mesh, imageblock, tile memory access patterns that are unique to
  Apple's TBDR GPU architecture
