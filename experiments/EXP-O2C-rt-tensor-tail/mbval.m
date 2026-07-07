// EXP-O2C primitive motion-blur HW validation (runs ON DEVICE). Builds a real
// motion acceleration structure: one triangle whose keyframe-0 sits at z=3 and
// keyframe-1 at z=5. Traces a fixed ray (origin 0, dir +z) at several times and
// reads back the hit distance -- which must LINEARLY INTERPOLATE 3->5 with time,
// proving the intersect() time parameter drives HW motion interpolation.
// CLEAN-ROOM: OUR OWN MSL + harness; observe hardware only.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>

static const char *SRC =
"#include <metal_stdlib>\n"
"#include <metal_raytracing>\n"
"using namespace metal; using namespace raytracing;\n"
"kernel void mbk(acceleration_structure<primitive_motion> accel [[buffer(0)]],\n"
"                device float *out [[buffer(1)]], device const float *tm [[buffer(2)]],\n"
"                uint i [[thread_position_in_grid]]) {\n"
"  ray r; r.origin=float3(0,0,0); r.direction=float3(0,0,1);\n"
"  r.min_distance=0; r.max_distance=INFINITY;\n"
"  intersector<triangle_data, primitive_motion> isect;\n"
"  isect.assume_geometry_type(geometry_type::triangle);\n"
"  auto res = isect.intersect(r, accel, tm[i]);\n"
"  out[i] = (res.type==intersection_type::triangle) ? res.distance : -1.0f; }\n";

int main(void){ @autoreleasepool{
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    fprintf(stderr,"device=%s motionBlur=%d\n", dev.name.UTF8String, (int)[dev supportsPrimitiveMotionBlur]);
    id<MTLCommandQueue> q=[dev newCommandQueue];
    NSError *err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:[NSString stringWithUTF8String:SRC] options:nil error:&err];
    if(!lib){ fprintf(stderr,"compile: %s\n", err.description.UTF8String); return 2; }
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"mbk"] error:&err];
    if(!pso){ fprintf(stderr,"pso: %s\n", err.description.UTF8String); return 3; }

    // two keyframes of the same triangle: z=3 at t=0, z=5 at t=1
    float k0[9] = { -1,-1,3, 1,-1,3, 0,1,3 };
    float k1[9] = { -1,-1,5, 1,-1,5, 0,1,5 };
    id<MTLBuffer> vb0=[dev newBufferWithBytes:k0 length:sizeof(k0) options:MTLResourceStorageModeShared];
    id<MTLBuffer> vb1=[dev newBufferWithBytes:k1 length:sizeof(k1) options:MTLResourceStorageModeShared];

    Class MK = NSClassFromString(@"MTLMotionKeyframeData");
    id kf0 = [MK data]; [kf0 setBuffer:vb0]; [kf0 setOffset:0];
    id kf1 = [MK data]; [kf1 setBuffer:vb1]; [kf1 setOffset:0];

    MTLAccelerationStructureMotionTriangleGeometryDescriptor *geo =
        [MTLAccelerationStructureMotionTriangleGeometryDescriptor descriptor];
    geo.vertexBuffers = @[kf0, kf1];
    geo.vertexStride = sizeof(float)*3;
    geo.triangleCount = 1;
    if([geo respondsToSelector:@selector(setVertexFormat:)]) geo.vertexFormat=MTLAttributeFormatFloat3;

    MTLPrimitiveAccelerationStructureDescriptor *pd=[MTLPrimitiveAccelerationStructureDescriptor descriptor];
    pd.geometryDescriptors=@[geo];
    pd.motionKeyframeCount=2; pd.motionStartTime=0.0f; pd.motionEndTime=1.0f;

    MTLAccelerationStructureSizes sz=[dev accelerationStructureSizesWithDescriptor:pd];
    fprintf(stderr,"AS size=%zu scratch=%zu\n",(size_t)sz.accelerationStructureSize,(size_t)sz.buildScratchBufferSize);
    id<MTLAccelerationStructure> as=[dev newAccelerationStructureWithSize:sz.accelerationStructureSize];
    id<MTLBuffer> scr=[dev newBufferWithLength:sz.buildScratchBufferSize options:MTLResourceStorageModePrivate];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLAccelerationStructureCommandEncoder> ae=[cb accelerationStructureCommandEncoder];
    [ae buildAccelerationStructure:as descriptor:pd scratchBuffer:scr scratchBufferOffset:0];
    [ae endEncoding]; [cb commit]; [cb waitUntilCompleted];
    fprintf(stderr,"motion AS built err=%s\n", cb.error?cb.error.description.UTF8String:"none");

    const int N=5; float times[5]={0.0f,0.25f,0.5f,0.75f,1.0f};
    id<MTLBuffer> tb=[dev newBufferWithBytes:times length:sizeof(times) options:MTLResourceStorageModeShared];
    id<MTLBuffer> ob=[dev newBufferWithLength:N*sizeof(float) options:MTLResourceStorageModeShared];
    memset(ob.contents,0,N*sizeof(float));
    id<MTLCommandBuffer> cb2=[q commandBuffer];
    id<MTLComputeCommandEncoder> ce=[cb2 computeCommandEncoder];
    [ce setComputePipelineState:pso];
    [ce setAccelerationStructure:as atBufferIndex:0];
    [ce setBuffer:ob offset:0 atIndex:1];
    [ce setBuffer:tb offset:0 atIndex:2];
    [ce useResource:as usage:MTLResourceUsageRead];
    [ce dispatchThreads:MTLSizeMake(N,1,1) threadsPerThreadgroup:MTLSizeMake(N,1,1)];
    [ce endEncoding]; [cb2 commit]; [cb2 waitUntilCompleted];
    fprintf(stderr,"dispatch err=%s\n", cb2.error?cb2.error.description.UTF8String:"none");

    float *o=(float*)ob.contents;
    printf("primitive motion blur: triangle z=3 (t=0) -> z=5 (t=1), ray origin 0 dir +z\n");
    for(int i=0;i<N;i++) printf("  time=%.2f  hit_t=%.4f  expected=%.4f  %s\n",
        times[i], o[i], 3.0+2.0*times[i], fabsf(o[i]-(3.0+2.0*times[i]))<0.01?"OK":"MISMATCH");
    return 0;
}}
