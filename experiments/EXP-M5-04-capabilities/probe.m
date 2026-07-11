// EXP-M5-04 probe.m — Apple M5 (SoC T8142) device capability probe.
//
// Clean-room category: HW-PROBE + OWN-SHADER.
//   * Creates the default MTLDevice and prints hardware/driver-reported CAPABILITY
//     VALUES only (public Metal API on our OWN program).
//   * Compiles a few trivial OUR-OWN shaders (compute, object/mesh/fragment) purely to
//     read pipeline-derived limits and to test whether the runtime will BUILD a mesh
//     pipeline. NO command buffer / encoder / GPU submission of any kind is issued.
//   * No Apple binary is inspected or disassembled. Every fact printed is a value the
//     Metal driver returns to a normal API caller.
//
// Build:  clang -fobjc-arc -framework Metal -framework Foundation probe.m -o probe
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static void pb(const char *k, BOOL v)               { printf("%-46s = %s\n", k, v ? "YES" : "NO"); }
static void pu(const char *k, unsigned long long v) { printf("%-46s = %llu\n", k, v); }
static void px(const char *k, unsigned long long v) { printf("%-46s = 0x%llx (%llu)\n", k, v, v); }
static void ps(const char *k, const char *v)        { printf("%-46s = %s\n", k, v ? v : "(null)"); }

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
    printf("%-46s = (%lu, %lu, %lu)\n", "maxThreadsPerThreadgroup",
           (unsigned long)mt.width, (unsigned long)mt.height, (unsigned long)mt.depth);
    px("maxThreadgroupMemoryLength", d.maxThreadgroupMemoryLength);
    if ([d respondsToSelector:@selector(maxArgumentBufferSamplerCount)])
      pu("maxArgumentBufferSamplerCount", d.maxArgumentBufferSamplerCount);

    printf("\n==== ARGUMENT BUFFERS / RW TEXTURES ====\n");
    pu("argumentBuffersSupport(0=Tier1,1=Tier2)", (unsigned long long)d.argumentBuffersSupport);
    pu("readWriteTextureSupport(0=None,1=T1,2=T2)", (unsigned long long)d.readWriteTextureSupport);

    printf("\n==== RAYTRACING / FUNCTION POINTERS / DYNAMIC LIBS ====\n");
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

    printf("\n==== TEXTURE / RENDER FEATURE FLAGS ====\n");
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

    printf("\n==== TEXTURE SAMPLE-COUNT SUPPORT ====\n");
    for (NSUInteger sc = 1; sc <= 16; sc <<= 1) {
      BOOL s = [d supportsTextureSampleCount:sc];
      printf("supportsTextureSampleCount(%2lu)                 = %s\n", (unsigned long)sc, s ? "YES":"NO");
    }

    printf("\n==== SPARSE / TENSOR ====\n");
    if ([d respondsToSelector:@selector(sparseTileSizeInBytes)])
      px("sparseTileSizeInBytes", d.sparseTileSizeInBytes);
    // sparseTileSizeInBytesForSparsePageSize: — MTLSparsePageSize enum (MTLResource.h):
    //   MTLSparsePageSize16=101, MTLSparsePageSize64=102, MTLSparsePageSize256=103
    if ([d respondsToSelector:@selector(sparseTileSizeInBytesForSparsePageSize:)]) {
      struct { const char *n; NSInteger v; } sp[] = {
        {"16KB(101)",101},{"64KB(102)",102},{"256KB(103)",103}
      };
      for (unsigned i = 0; i < 3; i++) {
        NSUInteger b = [d sparseTileSizeInBytesForSparsePageSize:(MTLSparsePageSize)sp[i].v];
        printf("sparseTileSizeInBytesForSparsePageSize(%-9s)= 0x%lx (%lu)\n",
               sp[i].n, (unsigned long)b, (unsigned long)b);
      }
    }
    // MTLDevice sparseTileSizeWithTextureType:pixelFormat:sampleCount: exists on newer SDKs
    pb("respondsTo:newTensorWithDescriptor:offset:error:",
       [d respondsToSelector:@selector(newTensorWithDescriptor:offset:error:)]);
    pb("respondsTo:newTensorWithDescriptor:error:",
       [d respondsToSelector:NSSelectorFromString(@"newTensorWithDescriptor:error:")]);

    printf("\n==== COUNTER SAMPLING (MTLCounterSamplingPoint 0..4) ====\n");
    if ([d respondsToSelector:@selector(supportsCounterSampling:)]) {
      const char *cn[] = {"AtStageBoundary","AtDrawBoundary","AtDispatchBoundary",
                          "AtTileDispatchBoundary","AtBlitBoundary"};
      for (NSUInteger i = 0; i < 5; i++) {
        BOOL s = [d supportsCounterSampling:(MTLCounterSamplingPoint)i];
        printf("supportsCounterSampling(%-24s) = %s\n", cn[i], s ? "YES":"NO");
      }
    }
    printf("counterSets:\n");
    for (id<MTLCounterSet> cs in d.counterSets)
      printf("  counterSet = %s\n", cs.name.UTF8String);

    printf("\n==== VERTEX AMPLIFICATION ====\n");
    if ([d respondsToSelector:@selector(supportsVertexAmplificationCount:)]) {
      for (NSUInteger n = 1; n <= 8; n <<= 1) {
        BOOL s = [d supportsVertexAmplificationCount:n];
        printf("supportsVertexAmplificationCount(%lu)           = %s\n", (unsigned long)n, s ? "YES":"NO");
      }
    }

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

    // ---- MESH SHADING: compile OUR OWN object+mesh+fragment stages and try to BUILD a
    //      mesh render pipeline (no submission). Success == runtime/HW supports mesh path.
    printf("\n==== MESH SHADING (our own object/mesh/fragment; build-only) ====\n");
    if ([d respondsToSelector:@selector(newRenderPipelineStateWithMeshDescriptor:options:reflection:error:)]) {
      NSString *src =
        @"#include <metal_stdlib>\n"
         "using namespace metal;\n"
         "struct Payload { float dummy; };\n"
         "struct VOut { float4 position [[position]]; };\n"
         "struct POut { };\n"
         "using MyMesh = mesh<VOut, POut, 3, 1, topology::triangle>;\n"
         "[[object, max_total_threadgroups_per_mesh_grid(1)]]\n"
         "void objMain(object_data Payload& p [[payload]], mesh_grid_properties mgp) {\n"
         "  p.dummy = 1.0f; mgp.set_threadgroups_per_grid(uint3(1,1,1));\n"
         "}\n"
         "[[mesh]]\n"
         "void meshMain(MyMesh m, const object_data Payload& p [[payload]], uint tid [[thread_index_in_threadgroup]]) {\n"
         "  if (tid == 0) m.set_primitive_count(1);\n"
         "  VOut v; v.position = float4(0,0,0,1); m.set_vertex(tid, v);\n"
         "  if (tid == 0) { m.set_index(0,0); m.set_index(1,1); m.set_index(2,2); }\n"
         "}\n"
         "fragment float4 fragMain() { return float4(1,0,0,1); }\n";
      NSError *e = nil;
      id<MTLLibrary> lib = [d newLibraryWithSource:src options:nil error:&e];
      if (!lib) {
        ps("mesh_lib_error", e.localizedDescription ?
           [e.localizedDescription componentsSeparatedByString:@"\n"].firstObject.UTF8String : "?");
      } else {
        id<MTLFunction> objFn  = [lib newFunctionWithName:@"objMain"];
        id<MTLFunction> meshFn = [lib newFunctionWithName:@"meshMain"];
        id<MTLFunction> fragFn = [lib newFunctionWithName:@"fragMain"];
        // MTLLibrary.h: MTLFunctionTypeMesh=7, MTLFunctionTypeObject=8
        printf("objMain.functionType   = %lu (expect 8=Object)\n", (unsigned long)objFn.functionType);
        printf("meshMain.functionType  = %lu (expect 7=Mesh)\n",  (unsigned long)meshFn.functionType);
        Class mpdClass = NSClassFromString(@"MTLMeshRenderPipelineDescriptor");
        if (mpdClass && objFn && meshFn) {
          id mpd = [[mpdClass alloc] init];
          [mpd setValue:objFn  forKey:@"objectFunction"];
          [mpd setValue:meshFn forKey:@"meshFunction"];
          [mpd setValue:fragFn forKey:@"fragmentFunction"];
          // set colorAttachments[0].pixelFormat = BGRA8Unorm (80)
          @try {
            id colorAttachments = [mpd valueForKey:@"colorAttachments"];
            id att0 = [colorAttachments objectAtIndexedSubscript:0];
            [att0 setValue:@(MTLPixelFormatBGRA8Unorm) forKey:@"pixelFormat"];
          } @catch (NSException *ex) { printf("mesh colorAttachment set threw: %s\n", ex.name.UTF8String); }
          NSError *pe = nil;
          @try {
            id<MTLRenderPipelineState> mps =
              [d newRenderPipelineStateWithMeshDescriptor:mpd
                                                  options:MTLPipelineOptionNone
                                               reflection:nil
                                                    error:&pe];
            if (mps) {
              printf("mesh_pipeline_build = SUCCESS  (maxTotalThreadsPerThreadgroup=%lu)\n",
                     (unsigned long)mps.maxTotalThreadsPerThreadgroup);
            } else {
              ps("mesh_pipeline_build", "FAILED");
              ps("mesh_pipeline_error", pe.localizedDescription ?
                 [pe.localizedDescription componentsSeparatedByString:@"\n"].firstObject.UTF8String : "?");
            }
          } @catch (NSException *ex) {
            printf("mesh_pipeline_build = THREW (%s: %s)\n", ex.name.UTF8String, ex.reason.UTF8String);
          }
        } else {
          ps("mesh_descriptor_class", mpdClass ? "present-but-fn-missing" : "ABSENT");
        }
      }
    } else {
      ps("newRenderPipelineStateWithMeshDescriptor", "SELECTOR-ABSENT");
    }

    printf("\n==== supportsFamily (incl. speculative future families) ====\n");
    struct { const char *n; NSInteger v; } fam[] = {
      {"Apple1",  1001}, {"Apple2", 1002}, {"Apple3", 1003}, {"Apple4", 1004},
      {"Apple5",  1005}, {"Apple6", 1006}, {"Apple7", 1007}, {"Apple8", 1008},
      {"Apple9",  1009}, {"Apple10",1010}, {"Apple11",1011}, {"Apple12",1012},
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

    printf("\n==== max MSL language version accepted (our own trivial shader) ====\n");
    struct { const char *n; NSUInteger v; } ver[] = {
      {"3.0", (3<<16)|0}, {"3.1", (3<<16)|1}, {"3.2", (3<<16)|2},
      {"4.0", (4<<16)|0}, {"4.1", (4<<16)|1}, {"4.2", (4<<16)|2},
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

    printf("\n==== Metal-4 / newer selector presence (respondsToSelector on MTLDevice) ====\n");
    const char *sels4[] = {
      "supportsFamily:", "sparseTileSizeInBytesForSparsePageSize:",
      "sparsePageSize", "newTensorWithDescriptor:offset:error:",
      "newResidencySetWithDescriptor:error:", "newIOCommandQueueWithDescriptor:error:",
      "sizeOfCounterHeapEntry:", "newCommandQueueWithDescriptor:",
      "newCommandQueueWithDescriptor:error:",
      "newLibraryWithStitchedDescriptor:error:",
      "newArgumentTableWithDescriptor:error:",
      "newComputePipelineStateWithDescriptor:options:reflection:error:",
      "functionHandleWithFunction:",
    };
    for (unsigned i=0;i<sizeof(sels4)/sizeof(sels4[0]);i++) {
      SEL s = NSSelectorFromString([NSString stringWithUTF8String:sels4[i]]);
      printf("respondsToSelector(%-52s) = %s\n", sels4[i], [d respondsToSelector:s] ? "YES":"NO");
    }

    printf("\n==== DONE ====\n");
    return 0;
  }
}
