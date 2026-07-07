// EXP-0002 metal_caps.m
// Clean-room category: HW-PROBE.
// Creates the default MTLDevice and prints hardware CAPABILITY VALUES only.
// It does NOT create command queues, command buffers, encoders, pipelines,
// or submit any GPU work. It only queries read-only capability properties of
// the device object (these values describe the silicon's limits and are
// non-copyrightable hardware documentation).
//
// Build (Command Line Tools, no Xcode needed):
//   clang -fobjc-arc -framework Metal -framework Foundation metal_caps.m -o metal_caps
// Run:
//   ./metal_caps
//
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static void pb(const char *k, BOOL v)      { printf("%-44s = %s\n", k, v ? "YES" : "NO"); }
static void pu(const char *k, unsigned long long v) { printf("%-44s = %llu\n", k, v); }
static void px(const char *k, unsigned long long v) { printf("%-44s = 0x%llx (%llu)\n", k, v, v); }
static void ps(const char *k, const char *v){ printf("%-44s = %s\n", k, v); }

int main(void) {
  @autoreleasepool {
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    if (!d) { fprintf(stderr, "no Metal device\n"); return 1; }

    printf("==== IDENTITY ====\n");
    ps("name", d.name.UTF8String);
    px("registryID", d.registryID);
    px("peerGroupID", d.peerGroupID);
    pu("peerCount", d.peerCount);
    pu("peerIndex", d.peerIndex);
    if ([d respondsToSelector:@selector(architecture)]) {
      ps("architecture.name", d.architecture.name.UTF8String);
    }
    pu("locationNumber", d.locationNumber);
    pu("location", (unsigned long long)d.location);
    pu("maxTransferRate", d.maxTransferRate);

    printf("\n==== MEMORY ====\n");
    pb("hasUnifiedMemory", d.hasUnifiedMemory);
    pb("lowPower", d.lowPower);
    pb("headless", d.headless);
    pb("removable", d.removable);
    px("recommendedMaxWorkingSetSize", d.recommendedMaxWorkingSetSize);
    px("maxBufferLength", d.maxBufferLength);
    px("currentAllocatedSize", d.currentAllocatedSize);

    printf("\n==== THREADGROUP / COMPUTE LIMITS ====\n");
    MTLSize mt = d.maxThreadsPerThreadgroup;
    printf("%-44s = (%lu, %lu, %lu)\n", "maxThreadsPerThreadgroup",
           (unsigned long)mt.width, (unsigned long)mt.height, (unsigned long)mt.depth);
    px("maxThreadgroupMemoryLength", d.maxThreadgroupMemoryLength);
    if ([d respondsToSelector:@selector(maxArgumentBufferSamplerCount)])
      pu("maxArgumentBufferSamplerCount", d.maxArgumentBufferSamplerCount);

    printf("\n==== FEATURE FLAGS ====\n");
    // argumentBuffersSupport: Tier1=0, Tier2=1
    pu("argumentBuffersSupport(0=T1,1=T2)", (unsigned long long)d.argumentBuffersSupport);
    // readWriteTextureSupport: None=0, Tier1=1, Tier2=2
    pu("readWriteTextureSupport(0=None..2)", (unsigned long long)d.readWriteTextureSupport);
    pb("supportsRaytracing", d.supportsRaytracing);
    if ([d respondsToSelector:@selector(supportsRaytracingFromRender)])
      pb("supportsRaytracingFromRender", d.supportsRaytracingFromRender);
    if ([d respondsToSelector:@selector(supportsPrimitiveMotionBlur)])
      pb("supportsPrimitiveMotionBlur", d.supportsPrimitiveMotionBlur);
    pb("supportsFunctionPointers", d.supportsFunctionPointers);
    if ([d respondsToSelector:@selector(supportsFunctionPointersFromRender)])
      pb("supportsFunctionPointersFromRender", d.supportsFunctionPointersFromRender);
    pb("supportsDynamicLibraries", d.supportsDynamicLibraries);
    if ([d respondsToSelector:@selector(supportsRenderDynamicLibraries)])
      pb("supportsRenderDynamicLibraries", d.supportsRenderDynamicLibraries);
    pb("supports32BitFloatFiltering", d.supports32BitFloatFiltering);
    pb("supports32BitMSAA", d.supports32BitMSAA);
    pb("supportsBCTextureCompression", d.supportsBCTextureCompression);
    pb("supportsPullModelInterpolation", d.supportsPullModelInterpolation);
    pb("supportsShaderBarycentricCoordinates", d.supportsShaderBarycentricCoordinates);
    pb("barycentricCoordsSupported", d.areBarycentricCoordsSupported);
    pb("programmableSamplePositionsSupported", d.areProgrammableSamplePositionsSupported);
    pb("rasterOrderGroupsSupported", d.areRasterOrderGroupsSupported);
    if ([d respondsToSelector:@selector(supportsQueryTextureLOD)])
      pb("supportsQueryTextureLOD", d.supportsQueryTextureLOD);
    pb("depth24Stencil8PixelFormatSupported", d.isDepth24Stencil8PixelFormatSupported);

    printf("\n==== ATTRIBUTES ====\n");
    px("maxThreadgroupMemoryLength(again)", d.maxThreadgroupMemoryLength);
    if ([d respondsToSelector:@selector(sparseTileSizeInBytes)])
      px("sparseTileSizeInBytes", d.sparseTileSizeInBytes);
    if ([d respondsToSelector:@selector(maxArgumentBufferSamplerCount)])
      pu("maxArgumentBufferSamplerCount", d.maxArgumentBufferSamplerCount);

    printf("\n==== supportsFamily ====\n");
    struct { const char *n; NSInteger v; } fam[] = {
      {"Apple1",  1001}, {"Apple2", 1002}, {"Apple3", 1003}, {"Apple4", 1004},
      {"Apple5",  1005}, {"Apple6", 1006}, {"Apple7", 1007}, {"Apple8", 1008},
      {"Apple9",  1009},
      {"Mac1",    2001}, {"Mac2",   2002},
      {"Common1", 3001}, {"Common2",3002}, {"Common3",3003},
      {"Metal3",  5001}, {"Metal4", 5002},
    };
    for (unsigned i = 0; i < sizeof(fam)/sizeof(fam[0]); i++) {
      BOOL s = [d supportsFamily:(MTLGPUFamily)fam[i].v];
      printf("supportsFamily(%-8s / %ld)%*s= %s\n", fam[i].n, (long)fam[i].v,
             12, "", s ? "YES" : "NO");
    }

    printf("\n==== counterSets (names only) ====\n");
    for (id<MTLCounterSet> cs in d.counterSets) {
      printf("counterSet = %s\n", cs.name.UTF8String);
    }
    return 0;
  }
}
