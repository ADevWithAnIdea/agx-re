// EXP-O2C RT-from-render HW validation (runs ON DEVICE). Builds a real triangle
// acceleration structure, then TRACES A RAY FROM A FRAGMENT SHADER across an 8x8
// render target and reads back the per-pixel hit distance. Confirms
// supportsRaytracingFromRender works end-to-end on the A18 Pro GPU.
// CLEAN-ROOM: OUR OWN MSL + OUR OWN harness; observe hardware behaviour only.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>

static const char *SRC =
"#include <metal_stdlib>\n"
"#include <metal_raytracing>\n"
"using namespace metal; using namespace raytracing;\n"
"struct VOut { float4 pos [[position]]; float2 uv; };\n"
"vertex VOut v_main(uint vid [[vertex_id]]) {\n"
"  float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };\n"
"  VOut o; o.pos = float4(p[vid],0,1); o.uv = p[vid]*0.5+0.5; return o; }\n"
"fragment float4 f_rt(VOut in [[stage_in]],\n"
"                     primitive_acceleration_structure accel [[buffer(0)]]) {\n"
"  ray r; r.origin = float3(in.uv*2.0-1.0, 0.0); r.direction = float3(0,0,1);\n"
"  r.min_distance = 0.0f; r.max_distance = INFINITY;\n"
"  intersection_query<triangle_data> q; q.reset(r, accel);\n"
"  while (q.next()) { if (q.get_candidate_intersection_type()==intersection_type::triangle)\n"
"      q.commit_triangle_intersection(); }\n"
"  float t = (q.get_committed_intersection_type()==intersection_type::triangle)\n"
"          ? q.get_committed_distance() : -1.0f;\n"
"  return float4(t, 0, 0, 1); }\n";

int main(void){ @autoreleasepool{
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    fprintf(stderr,"device=%s RTfromRender=%d\n", dev.name.UTF8String,
            (int)[dev supportsRaytracingFromRender]);
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSError *err=nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:[NSString stringWithUTF8String:SRC] options:nil error:&err];
    if(!lib){ fprintf(stderr,"compile: %s\n", err.description.UTF8String); return 2; }

    // triangle at z=3 (same known triangle as EXP-0023 rtval)
    float verts[9] = { -1,-1,3, 1,-1,3, 0,1,3 };
    id<MTLBuffer> vbuf = [dev newBufferWithBytes:verts length:sizeof(verts) options:MTLResourceStorageModeShared];
    MTLAccelerationStructureTriangleGeometryDescriptor *geo = [MTLAccelerationStructureTriangleGeometryDescriptor descriptor];
    geo.vertexBuffer=vbuf; geo.vertexStride=sizeof(float)*3; geo.triangleCount=1;
    if([geo respondsToSelector:@selector(setVertexFormat:)]) geo.vertexFormat=MTLAttributeFormatFloat3;
    MTLPrimitiveAccelerationStructureDescriptor *pd=[MTLPrimitiveAccelerationStructureDescriptor descriptor];
    pd.geometryDescriptors=@[geo];
    MTLAccelerationStructureSizes sz=[dev accelerationStructureSizesWithDescriptor:pd];
    id<MTLAccelerationStructure> as=[dev newAccelerationStructureWithSize:sz.accelerationStructureSize];
    id<MTLBuffer> scr=[dev newBufferWithLength:sz.buildScratchBufferSize options:MTLResourceStorageModePrivate];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLAccelerationStructureCommandEncoder> ae=[cb accelerationStructureCommandEncoder];
    [ae buildAccelerationStructure:as descriptor:pd scratchBuffer:scr scratchBufferOffset:0];
    [ae endEncoding]; [cb commit]; [cb waitUntilCompleted];
    fprintf(stderr,"AS built err=%s\n", cb.error?cb.error.description.UTF8String:"none");

    // render pipeline: fullscreen triangle, fragment traces a ray
    MTLRenderPipelineDescriptor *rp=[MTLRenderPipelineDescriptor new];
    rp.vertexFunction=[lib newFunctionWithName:@"v_main"];
    rp.fragmentFunction=[lib newFunctionWithName:@"f_rt"];
    rp.colorAttachments[0].pixelFormat=MTLPixelFormatR32Float;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:rp error:&err];
    if(!pso){ fprintf(stderr,"pipeline: %s\n", err.description.UTF8String); return 3; }
    fprintf(stderr,"render pipeline OK (RT fragment)\n");

    const int W=8,H=8;
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float width:W height:H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
    id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
    MTLRenderPassDescriptor *rpd=[MTLRenderPassDescriptor renderPassDescriptor];
    rpd.colorAttachments[0].texture=tex; rpd.colorAttachments[0].loadAction=MTLLoadActionClear;
    rpd.colorAttachments[0].clearColor=MTLClearColorMake(-9,0,0,0); rpd.colorAttachments[0].storeAction=MTLStoreActionStore;

    id<MTLCommandBuffer> cb2=[q commandBuffer];
    id<MTLRenderCommandEncoder> re=[cb2 renderCommandEncoderWithDescriptor:rpd];
    [re setRenderPipelineState:pso];
    [re setFragmentAccelerationStructure:as atBufferIndex:0];
    [re useResource:as usage:MTLResourceUsageRead];
    [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [re endEncoding]; [cb2 commit]; [cb2 waitUntilCompleted];
    fprintf(stderr,"draw err=%s\n", cb2.error?cb2.error.description.UTF8String:"none");

    float px[W*H];
    [tex getBytes:px bytesPerRow:W*sizeof(float) fromRegion:MTLRegionMake2D(0,0,W,H) mipmapLevel:0];
    printf("RT-from-render 8x8 hit-distance grid (uv->ray origin xy in [-1,1], tri at z=3):\n");
    for(int y=0;y<H;y++){ for(int x=0;x<W;x++) printf("%6.2f ", px[y*W+x]); printf("\n"); }
    // center of the framebuffer maps to origin near the triangle -> t=3; corners miss (-1)
    return 0;
}}
