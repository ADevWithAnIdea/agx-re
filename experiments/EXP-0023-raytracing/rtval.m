// EXP-0023 HW-validation + AS-capture harness (runs ON THE DEVICE).
// Builds a REAL primitive acceleration structure with a KNOWN triangle, binds it to
// our own compute kernel, traces KNOWN rays on the A18 Pro GPU, and reads back the
// hit (t, primitive_id, barycentrics). Confirms the raytracing:: lowering is correct.
// Run under iotrace.dylib to capture how the AS is referenced across userspace<->kernel.
// CLEAN-ROOM: OUR OWN MSL + OUR OWN harness; we only observe hardware behaviour and
// the DATA our own process hands the kernel. No Apple binary is inspected.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>
#include <unistd.h>
#include <signal.h>

static const char *KSRC =
"#include <metal_stdlib>\n"
"#include <metal_raytracing>\n"
"using namespace metal;\n"
"using namespace raytracing;\n"
"kernel void rtval(primitive_acceleration_structure accel [[buffer(0)]],\n"
"                  device float *out [[buffer(1)]],\n"
"                  device const packed_float3 *org [[buffer(2)]],\n"
"                  device const packed_float3 *dir [[buffer(3)]],\n"
"                  uint i [[thread_position_in_grid]]) {\n"
"    ray r; r.origin=float3(org[i]); r.direction=float3(dir[i]);\n"
"    r.min_distance=0.0f; r.max_distance=INFINITY;\n"
"    intersector<triangle_data> isect;\n"
"    isect.assume_geometry_type(geometry_type::triangle);\n"
"    intersection_result<triangle_data> res = isect.intersect(r, accel);\n"
"    uint b=i*4;\n"
"    if (res.type==intersection_type::triangle) {\n"
"        out[b+0]=res.distance;\n"
"        out[b+1]=float(res.primitive_id);\n"
"        out[b+2]=res.triangle_barycentric_coord.x;\n"
"        out[b+3]=res.triangle_barycentric_coord.y;\n"
"    } else { out[b+0]=-1; out[b+1]=-1; out[b+2]=-1; out[b+3]=-1; }\n"
"}\n";

int main(int argc, const char **argv) {
@autoreleasepool {
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { fprintf(stderr,"no device\n"); return 1; }
    fprintf(stderr,"device = %s  raytracing=%d\n", dev.name.UTF8String,
            (int)[dev supportsRaytracing]);
    id<MTLCommandQueue> q = [dev newCommandQueue];

    NSError *err=nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:[NSString stringWithUTF8String:KSRC]
                                           options:nil error:&err];
    if (!lib) { fprintf(stderr,"compile fail: %s\n", err.description.UTF8String); return 2; }
    id<MTLFunction> fn = [lib newFunctionWithName:@"rtval"];
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
    if (!pso) { fprintf(stderr,"pso fail: %s\n", err.description.UTF8String); return 3; }

    // KNOWN triangle: v0(-1,-1,3) v1(1,-1,3) v2(0,1,3), all at z=3.
    float verts[9] = { -1,-1,3,  1,-1,3,  0,1,3 };
    id<MTLBuffer> vbuf = [dev newBufferWithBytes:verts length:sizeof(verts)
                                         options:MTLResourceStorageModeShared];

    MTLAccelerationStructureTriangleGeometryDescriptor *geo =
        [MTLAccelerationStructureTriangleGeometryDescriptor descriptor];
    geo.vertexBuffer = vbuf;
    geo.vertexBufferOffset = 0;
    geo.vertexStride = sizeof(float)*3;
    geo.triangleCount = 1;
    if ([geo respondsToSelector:@selector(setVertexFormat:)]) geo.vertexFormat = MTLAttributeFormatFloat3;

    MTLPrimitiveAccelerationStructureDescriptor *pdesc =
        [MTLPrimitiveAccelerationStructureDescriptor descriptor];
    pdesc.geometryDescriptors = @[geo];

    MTLAccelerationStructureSizes sz = [dev accelerationStructureSizesWithDescriptor:pdesc];
    fprintf(stderr,"AS sizes: as=%zu scratch=%zu refit=%zu\n",
            (size_t)sz.accelerationStructureSize,(size_t)sz.buildScratchBufferSize,
            (size_t)sz.refitScratchBufferSize);
    id<MTLAccelerationStructure> as =
        [dev newAccelerationStructureWithSize:sz.accelerationStructureSize];
    id<MTLBuffer> scratch = [dev newBufferWithLength:sz.buildScratchBufferSize
                                            options:MTLResourceStorageModePrivate];
    fprintf(stderr,"AS gpuResourceID=0x%llx  as.size=%zu\n",
            (unsigned long long)as.gpuResourceID._impl, (size_t)as.size);

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLAccelerationStructureCommandEncoder> aenc = [cb accelerationStructureCommandEncoder];
    [aenc buildAccelerationStructure:as descriptor:pdesc scratchBuffer:scratch scratchBufferOffset:0];
    [aenc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.error) { fprintf(stderr,"AS build error: %s\n", cb.error.description.UTF8String); }
    else fprintf(stderr,"AS built OK\n");

    // KNOWN rays. #0 hits center-ish; #1 hits near v1; #2 MISSES (points away).
    const int N = 6;
    float orgs[18] = { 0.0f,0.0f,0.0f,  0.3f,-0.3f,0.0f,  -0.3f,-0.3f,0.0f,
                       0.0f,-0.5f,0.0f, 0.0f,0.5f,0.0f,   0.0f,3.0f,0.0f };
    float dirs[18] = { 0.0f,0.0f,1.0f,  0.0f,0.0f,1.0f,   0.0f,0.0f,1.0f,
                       0.0f,0.0f,1.0f,  0.0f,0.0f,1.0f,   0.0f,0.0f,1.0f };
    id<MTLBuffer> obuf = [dev newBufferWithLength:N*4*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> orgb = [dev newBufferWithBytes:orgs length:sizeof(orgs) options:MTLResourceStorageModeShared];
    id<MTLBuffer> dirb = [dev newBufferWithBytes:dirs length:sizeof(dirs) options:MTLResourceStorageModeShared];
    memset(obuf.contents,0,N*4*sizeof(float));

    fprintf(stderr,"VA out=0x%llx org=0x%llx dir=0x%llx vbuf=0x%llx\n",
            (unsigned long long)obuf.gpuAddress,(unsigned long long)orgb.gpuAddress,
            (unsigned long long)dirb.gpuAddress,(unsigned long long)vbuf.gpuAddress);
    if ([as respondsToSelector:@selector(gpuAddress)])
        fprintf(stderr,"VA as.gpuAddress=0x%llx\n",(unsigned long long)[(id)as gpuAddress]);
    fprintf(stderr,"as.gpuResourceID=0x%llx\n",(unsigned long long)as.gpuResourceID._impl);

    id<MTLCommandBuffer> cb2 = [q commandBuffer];
    id<MTLComputeCommandEncoder> cenc = [cb2 computeCommandEncoder];
    [cenc setComputePipelineState:pso];
    [cenc setAccelerationStructure:as atBufferIndex:0];
    [cenc setBuffer:obuf offset:0 atIndex:1];
    [cenc setBuffer:orgb offset:0 atIndex:2];
    [cenc setBuffer:dirb offset:0 atIndex:3];
    // The AS itself must be resident; also mark the built AS as used.
    [cenc useResource:as usage:MTLResourceUsageRead];
    [cenc dispatchThreads:MTLSizeMake(N,1,1) threadsPerThreadgroup:MTLSizeMake(N,1,1)];
    [cenc endEncoding];
    [cb2 commit]; [cb2 waitUntilCompleted];
    if (cb2.error) { fprintf(stderr,"dispatch error: %s\n", cb2.error.description.UTF8String); }

    float *o = (float*)obuf.contents;
    for (int i=0;i<N;i++){
        printf("RAY %d org=(%.2f,%.2f,%.2f) dir=(%.2f,%.2f,%.2f)  ->  t=%.4f prim=%.0f bary=(%.4f,%.4f)\n",
               i, orgs[i*3],orgs[i*3+1],orgs[i*3+2], dirs[i*3],dirs[i*3+1],dirs[i*3+2],
               o[i*4+0],o[i*4+1],o[i*4+2],o[i*4+3]);
    }
    fflush(stdout);
    // Signal iotrace to snapshot BOs (only when tracing; default SIGUSR1 kills us).
    if (getenv("RT_SIGUSR1")) kill(getpid(), SIGUSR1);
    return 0;
}
}
