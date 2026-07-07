# Transform Your Geometry with Metal Mesh Shaders - WWDC22
<!-- Source: https://developer.apple.com/videos/play/wwdc2022/10162/ -->
<!-- Hardware requirement: Family7 (A15 Pro / M2) and newer, Mac2 and newer -->

## Overview
Metal mesh shaders replace the traditional vertex shader with two stages:
- **Object shader**: processes objects, generates payloads, spawns mesh groups
- **Mesh shader**: processes meshlets, outputs metal::mesh to rasterizer

## Key Limits
- Payload size: 16 KB (object → mesh)
- Max vertices per mesh: 256
- Max primitives per mesh: 512
- Total mesh size ≤ 16 KB
- Max meshlets per object threadgroup: 1,024 (Family7) → 1,000,000+ (Family9/M3)

## metal::mesh Type
```cpp
using triangle_mesh_t = metal::mesh<
    VertexData,                // vertex type
    PrimitiveData,             // primitive type  
    256,                       // max vertices
    512,                       // max primitives
    metal::topology::triangle  // topology: point|line|triangle
>;
```

## Pipeline Setup
```swift
let desc = MTLMeshRenderPipelineDescriptor()
desc.objectFunction = objectFn
desc.payloadMemoryLength = payloadLength
desc.maxTotalThreadsPerObjectThreadgroup = hairsPerBlock
desc.meshFunction = meshFn
desc.maxTotalThreadsPerMeshThreadgroup = vertexCountPerHair
```

## Encode Draw Call
```swift
encoder.drawMeshThreadgroups(objectGridDims,
    threadsPerObjectThreadgroup: threadsPerObject,
    threadsPerMeshThreadgroup: threadsPerMesh)
```

## Architecture Benefit vs Traditional
Traditional (two-pass): Compute → device memory buffer → Render
Mesh shader (single-pass): Object shader → on-chip payload → Mesh shader → Rasterizer

Eliminates sync points and intermediate buffers.
