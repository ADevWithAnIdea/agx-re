# GPU Devices and Work Submission - Apple Metal Documentation

Source: https://developer.apple.com/documentation/metal/gpu_devices_and_work_submission
Fetched: 2026-05-09

Note: The Apple Developer documentation portal requires JavaScript to render content; the
page skeleton was fetched. The key Metal objects for GPU device access and work submission
are documented below from Apple's public API reference and related WWDC sessions.

---

## Overview

Metal represents GPU hardware as `MTLDevice` objects. To submit work to the GPU, you:
1. Obtain a `MTLDevice` reference
2. Create a `MTLCommandQueue` from the device
3. Create `MTLCommandBuffer` objects from the queue
4. Encode GPU commands into the buffer using encoders
5. Commit the buffer for execution

---

## Key Types

### MTLDevice
- Represents a GPU on the system
- Factory for all other Metal objects (buffers, textures, pipelines, command queues)
- On macOS, multiple devices may be present (discrete + integrated)
- Obtained via `MTLCreateSystemDefaultDevice()` or `MTLCopyAllDevices()`

### MTLCommandQueue
- Ordered queue of command buffers submitted to a GPU
- Created from `MTLDevice.makeCommandQueue()`
- Thread-safe: multiple threads can use the same queue
- Typically create one queue per rendering context

### MTLCommandBuffer
- Container for encoded GPU commands for one submission
- Created from `MTLCommandQueue.makeCommandBuffer()`
- Not thread-safe; use one per thread or protect with locks
- Committed with `.commit()` or `.commit()` + `.waitUntilCompleted()`

### Command Encoders

| Encoder | Purpose |
|---------|---------|
| `MTLRenderCommandEncoder` | Encode draw calls and render state |
| `MTLComputeCommandEncoder` | Encode compute dispatches |
| `MTLBlitCommandEncoder` | Copy/fill buffers and textures |
| `MTLParallelRenderCommandEncoder` | Multi-threaded render encoding for a single render pass |

### MTLRenderPassDescriptor
- Describes attachments (color, depth, stencil) for a render pass
- Specifies load and store actions for each attachment
- Critical for TBDR efficiency (see TBDR optimization notes)

---

## Load and Store Actions

These are critical for Apple TBDR GPU efficiency:

| Action | Effect |
|--------|--------|
| `.load` | Read attachment data from system memory into tile memory |
| `.clear` | Initialize tile memory to a clear value (no system memory read) |
| `.dontCare` | Leave tile memory uninitialized (fastest) |
| `.store` | Write tile memory back to system memory texture |
| `.dontCare` (store) | Discard tile memory contents (saves bandwidth) |
| `.multisampleResolve` | Resolve MSAA during store (keep MSAA texture memoryless) |

**Best practice:** Use `.clear` instead of `.load` when previous frame data is not needed.
Use `.dontCare` store for intermediate attachments that are never read back.

---

## Indirect Command Buffers

Metal also supports GPU-driven rendering via `MTLIndirectCommandBuffer`:
- The GPU can encode its own draw calls into an ICB
- Eliminates CPU-GPU synchronization round-trips for scene traversal
- Used with Argument Buffers to represent scene data on the GPU

---

## Related Documentation

- `MTLDevice`: https://developer.apple.com/documentation/metal/mtldevice
- `MTLCommandQueue`: https://developer.apple.com/documentation/metal/mtlcommandqueue
- `MTLCommandBuffer`: https://developer.apple.com/documentation/metal/mtlcommandbuffer
- `MTLRenderCommandEncoder`: https://developer.apple.com/documentation/metal/mtlrendercommandencoder
- `MTLComputeCommandEncoder`: https://developer.apple.com/documentation/metal/mtlcomputecommandencoder
- `MTLGPUFamily`: https://developer.apple.com/documentation/metal/mtlgpufamily
- WWDC20 "Harness Apple GPUs with Metal": https://developer.apple.com/videos/play/wwdc2020/10602/
