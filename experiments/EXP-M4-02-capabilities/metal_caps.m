// EXP-M4-02 metal_caps.m  — M4 device capability probe (extends EXP-0002)
// Clean-room category: HW-PROBE + OWN-SHADER.
// Creates the default MTLDevice and prints hardware CAPABILITY VALUES only.
// It creates ONE trivial compute pipeline (compiling OUR OWN 1-line kernel) to
// read threadExecutionWidth / maxTotalThreadsPerThreadgroup — no command buffer,
// encoder, or GPU submission of any kind. No Apple binary is inspected.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation metal_caps.m -o metal_caps
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
    if ([d respondsToSelector:@selector(architecture)])
      ps("architecture.name", d.architecture.name.UTF8String);
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
    pu("argumentBuffersSupport(0=T1,1=T2)", (unsigned long long)d.argumentBuffersSupport);
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

    // ---- threadExecutionWidth / maxTotalThreadsPerThreadgroup via OUR OWN trivial kernel
    printf("\n==== PIPELINE-DERIVED (our own 1-line kernel; no GPU submission) ====\n");
    {
      NSError *e = nil;
      id<MTLLibrary> lib =
        [d newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\n"
                                 "kernel void k(device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[i]=1.0; }"
                        options:nil error:&e];
      if (lib) {
        id<MTLFunction> fn = [lib newFunctionWithName:@"k"];
        id<MTLComputePipelineState> cps = [d newComputePipelineStateWithFunction:fn error:&e];
        if (cps) {
          pu("threadExecutionWidth", cps.threadExecutionWidth);
          pu("maxTotalThreadsPerThreadgroup", cps.maxTotalThreadsPerThreadgroup);
          pu("staticThreadgroupMemoryLength", cps.staticThreadgroupMemoryLength);
        } else ps("pipeline_error", e.localizedDescription.UTF8String);
      } else ps("lib_error", e.localizedDescription.UTF8String);
    }

    printf("\n==== supportsFamily (incl. speculative future families) ====\n");
    struct { const char *n; NSInteger v; } fam[] = {
      {"Apple1",  1001}, {"Apple2", 1002}, {"Apple3", 1003}, {"Apple4", 1004},
      {"Apple5",  1005}, {"Apple6", 1006}, {"Apple7", 1007}, {"Apple8", 1008},
      {"Apple9",  1009}, {"Apple10",1010}, {"Apple11",1011},
      {"Mac1",    2001}, {"Mac2",   2002},
      {"Common1", 3001}, {"Common2",3002}, {"Common3",3003},
      {"MacCatalyst1", 4001}, {"MacCatalyst2", 4002},
      {"Metal3",  5001}, {"Metal4", 5002}, {"Metal5(spec)", 5003},
    };
    for (unsigned i = 0; i < sizeof(fam)/sizeof(fam[0]); i++) {
      BOOL s = [d supportsFamily:(MTLGPUFamily)fam[i].v];
      printf("supportsFamily(%-14s / %ld)%*s= %s\n", fam[i].n, (long)fam[i].v,
             6, "", s ? "YES" : "NO");
    }

    // ---- Max accepted MSL language version (compile a trivial shader per version)
    printf("\n==== max MSL language version accepted (our own trivial shader) ====\n");
    struct { const char *n; NSUInteger v; } ver[] = {
      {"3.0", (3<<16)|0}, {"3.1", (3<<16)|1}, {"3.2", (3<<16)|2},
      {"4.0", (4<<16)|0}, {"4.1", (4<<16)|1},
    };
    for (unsigned i = 0; i < sizeof(ver)/sizeof(ver[0]); i++) {
      MTLCompileOptions *co = [MTLCompileOptions new];
      @try { co.languageVersion = (MTLLanguageVersion)ver[i].v; }
      @catch (NSException *ex) { printf("MSL %-4s = SET-THREW (%s)\n", ver[i].n, ex.name.UTF8String); continue; }
      NSError *e = nil;
      id<MTLLibrary> lib =
        [d newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\nkernel void k(){}"
                        options:co error:&e];
      printf("MSL %-4s = %s%s%s\n", ver[i].n, lib ? "ACCEPTED" : "REJECTED",
             lib ? "" : "  :: ", lib ? "" : (e.localizedDescription ? [e.localizedDescription componentsSeparatedByString:@"\n"].firstObject.UTF8String : "?"));
    }

    printf("\n==== Metal-4 selector presence (respondsToSelector on MTLDevice) ====\n");
    const char *sels4[] = {
      "supportsFamily:", "sparseTileSizeInBytesForSparsePageSize:",
      "sparsePageSize", "newTensorWithDescriptor:offset:error:",
      "newResidencySetWithDescriptor:error:", "newIOCommandQueueWithDescriptor:error:",
      "sizeOfCounterHeapEntry:", "newCommandQueueWithDescriptor:",
    };
    for (unsigned i=0;i<sizeof(sels4)/sizeof(sels4[0]);i++) {
      SEL s = NSSelectorFromString([NSString stringWithUTF8String:sels4[i]]);
      printf("respondsToSelector(%-42s) = %s\n", sels4[i], [d respondsToSelector:s] ? "YES":"NO");
    }

    printf("\n==== counterSets (names only) ====\n");
    for (id<MTLCounterSet> cs in d.counterSets)
      printf("counterSet = %s\n", cs.name.UTF8String);
    return 0;
  }
}
