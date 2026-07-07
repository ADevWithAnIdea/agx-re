# Learn Performance Best Practices for Metal Shaders

Source: https://developer.apple.com/videos/play/tech-talks/111373/
Event: Tech Talks (2023)
Speaker: Srividya Karumuri, GPU Compiler Engineer, Apple
Fetched: 2026-05-09

## Session Description

Discover how to improve Metal shader performance using the latest advancements in Apple GPUs.
Covers reducing shader execution time with function constants, investigating compiler optimization
with function groups, saving runtime by improving shader execution and resource parallelism,
Apple Family 9 GPU features, and hardware acceleration for ray tracing.

---

## 1. Reducing Shader Execution Time

### Function Constants

**Purpose:** Efficiently specialize shaders and remove unreachable code at compile time.

**Benefits over Macros:**
- Reduces compile time
- Decreases Metal library size
- Creates only needed shader variants
- Reuses intermediate Metal functions

**How It Works:**
- Declare function constants in Metal function code
- Define constant values when creating Metal functions
- Initialize program scope variables in constant address space
- Enables Metal to fold constants and eliminate unreachable code paths

**Use Case:** Ideal for uber shaders that handle multiple material types, rendering modes, or
feature variations.

**Example Scenario:**
```metal
// With function constants (preferred):
// Compile once from source, create specialized variants on-demand
constant bool USE_GLOSSY [[function_constant(0)]];

fragment float4 materialShader(/* ... */) {
    if (USE_GLOSSY) {
        return computeGlossy(/* ... */);
    } else {
        return computeMatte(/* ... */);
    }
}
// With macros: Must compile all possible macro combinations offline
```

### Function Groups

**Purpose:** Optimize shaders that use indirect function calls.

**Key Concepts:**
- **Indirect Function:** A function called without directly invoking by name (via function
  pointers or visible function tables)
- **Challenge:** Metal cannot optimize across function pointer call sites without visibility
  into which functions are being called

**Implementation:**
- Define function groups by assigning a dictionary to linked functions group's property
- String key: name of the function group
- Value: array of functions belonging to that group

**Example:**
```
Lighting function group:  area, spot, sphere functions
Material function group:  wood, glass, metal functions
```

**Limitation:** Only benefits statically linked functions, not functions compiled to binary libraries.

---

## 2. Improving Resource Utilization and Parallelism

### Thread Occupancy

Occupancy is critical for improving latency hiding in shader execution.

Dependencies:
- Register availability
- Memory resources
- Data optimization in shaders

See also:
- "Explore GPU advancements in M3 and A17 Pro" for new occupancy management features
- "Discover new Metal profiling tools for M3 and A17 Pro" for triaging occupancy bottlenecks

### Memory Address Spaces

**Constant Address Space:**
- Read-only memory objects
- Optimized for data constant across all thread dispatch or draw
- **Use when:** Object size is fixed and read many times by different threads
- **Benefit:** Improves memory utilization and thread occupancy

**Device Address Space:**
- Read/write buffers
- **Use when:** Data varies across threads or buffer size is not fixed

**Threadgroup Address Space:**
- Read/write memory for thread collaboration
- Traditionally faster for software-managed caching
- **New in Apple Family 9:** Dynamic shader core memory and flexible on-chip memory

**Apple Family 9 Key Change:**
- Threadgroup, device, and constant memory types now **use the same cache hierarchy**
- If working set size fits in cache, direct buffer access may be as performant as copying
  to threadgroup memory
- Avoids latencies from copying to threadgroup memory
- Profile workloads using Metal debugger in Xcode to validate

### Data Type Optimization

**16-bit Data Types (Recommended):**
- `half` (16-bit floating point)
- `short` (16-bit integer)
- `bfloat` (16-bit truncated float, available since Metal 3.1)

**Benefits:**
- Reduce register footprint
- Decrease memory footprint
- Improve bandwidth utilization
- Enhance thread occupancy
- Improve energy efficiency
- Better ALU pipeline utilization (Apple Family 9)

**Best Practices:**
```metal
// Bad: Literals without suffix -> entire expression evaluates at float32 precision
half result = a + b - 2 + 5;

// Good: Use 'h' suffix on literals for half precision
half result = a + b - 2h + 5h;
```

**Bfloat specifics:**
- 16-bit truncated version of float
- Supports wide range of values at lower precision
- Best suited for machine learning acceleration
- Highly recommended when precision requirements match bfloat capabilities

**Mixed type instructions:** Use float, half, int together for better ALU pipeline utilization.

---

## 3. Ray Tracing Optimization (Apple Family 9)

### Hardware Acceleration

The hardware intersector handles:
- Traversal of acceleration structures
- Invocation of intersection functions
- State update based on intersection results
- Parallel ray testing against multiple primitives

### Custom Intersection Functions

**When to Use:**
- Only when necessary
- Alpha testing implementation (geometric detail like chains, leaves)
- Accepting or rejecting intersections as rays traverse

**Performance Considerations:**
- Opaque triangle intersectors are the fastest path
- Hardware sorts and groups by intersection function
- Avoid duplicate intersection functions
- Use Metal intersection function table indexing with one entry per function

**Parallelism:**
- Multiple rays tested in parallel via SIMDgroups
- Custom intersection functions run in parallel
- Serialization occurs for side-effect operations (memory writes to payload or device memory)
- Divergence (indirect function calls) reduces parallelism

**Optimization Strategy:**
- Perform payload updates late in the intersection function
- Complete work unrelated to payload updates first
- Maximizes parallelism before serialization point

### Ray Payload Optimization

**Impact on Performance:** Larger payload structures negatively impact ray tracing performance.

**Strategies:**

1. **Avoid Payloads When Possible:**
   - Intersection result contains most needed data (hit type, distance, etc.)
   - More performant for visibility rays (shadows, occlusion)

2. **Avoid Global Uber Payload:**
   - Specialize structure for each intersect call
   - Minimize structure size with packed data types
   - Remove unnecessary fields

3. **Example Optimization:**
```
Original payload:
  - Position (float3): 16 bytes (at offset 0)
  - Hit flag (bool):   1 byte  (at offset 16, due to alignment)
  - RGB color (float3): 12 bytes (at offset 32)
  - Total size: 48 bytes

Optimized payload:
  - Packed RGB color: 4 bytes
  - Removed hit flag (use intersection type instead)
  - Compute position from ray origin + direction + intersection distance
  - Total size: 4 bytes

Result: 92% reduction in payload size
```

4. **Packing Methods:**
   - Use Metal shading language packing methods
   - Convert float3 RGB to 4-byte packed format
   - Compute position data from ray properties rather than storing

### Intersection Tags

**Purpose:** Additional state for traversal tracking.

**Constraints:**
- Must match between intersector and intersection functions
- Minimize number of intersection tags needed
- Tags increase ray tracing scratch usage and impact occupancy

### Intersector vs. Intersection Query

**Intersector (Preferred):**
- Aligns with hardware implementation
- Supports custom intersection functions
- Hardware can sort, group, and optimize execution
- More efficient scratch memory usage
- Better performance characteristics

**Intersection Query (Alternative):**
- Supports portability from other shading languages
- Does not use custom intersection functions
- Code executes in original GPU function
- Hardware must wait for completion before continuing traversal
- Cannot group execution or sort by intersection function
- Uses more ray tracing scratch memory

**Optimization for Multiple Intersection Queries:**
```
Use as few query objects as possible.
Reuse query objects by changing properties.
Reset existing object with intersection_params rather than creating new.
Strategy: Complete work with one query before switching to another.
```

---

## Resources

Video Downloads:
- HD: https://devstreaming-cdn.apple.com/videos/tech-talks/111373/4/7A338D0D-9FD5-4E2F-B802-E1D169D6A125/downloads/tech-talks-111373_hd.mp4?dl=1
- SD: https://devstreaming-cdn.apple.com/videos/tech-talks/111373/4/7A338D0D-9FD5-4E2F-B802-E1D169D6A125/downloads/tech-talks-111373_sd.mp4?dl=1

Related Videos:
- Discover new Metal profiling tools for M3 and A17 Pro: https://developer.apple.com/videos/play/tech-talks/111374
- Explore GPU advancements in M3 and A17 Pro: https://developer.apple.com/videos/play/tech-talks/111375
- Optimize GPU renderers with Metal (WWDC23): https://developer.apple.com/videos/play/wwdc2023/10127
- Your guide to Metal ray tracing (WWDC23): https://developer.apple.com/videos/play/wwdc2023/10128
- Optimize Metal Performance for Apple silicon Macs (WWDC20): https://developer.apple.com/videos/play/wwdc2020/10632/

---

## Summary of Best Practices

### Execution Time Reduction
1. Use function constants for efficient shader specialization
2. Apply function groups to optimize indirect function calls
3. Enable Metal compiler optimization opportunities

### Resource Utilization
1. Choose appropriate address spaces (constant, device, threadgroup)
2. Leverage 16-bit data types (half, short, bfloat)
3. Profile with Metal debugger to validate optimizations
4. On Family 9, direct buffer access may match threadgroup memory performance

### Ray Tracing Optimization
1. Use custom intersection functions only when necessary
2. Minimize ray payload size (pack data, compute from ray properties)
3. Reduce number of intersection tags
4. Prefer intersector over intersection query
5. Reuse intersection query objects rather than creating new ones
6. Avoid switching between query objects during traversal
