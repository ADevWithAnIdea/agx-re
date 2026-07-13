// EXP-M5-19 rtsplice.m — clean-room OWN-SHADER RT splice-and-observe with a REAL
// acceleration structure (runs ON THE M5 device). Combines the agxrun binary-archive
// technique (force the GPU to run a possibly-BYTE-SPLICED archive via
// MTLPipelineOptionFailOnBinaryArchiveMiss) with an rtval-style real AS build:
// a KNOWN single-triangle primitive AS + KNOWN rays, so a hit vs miss / a wrong t
// tells us which spliced op was load-bearing for the AS-load / ray-data / intersect.
//
// CLEAN-ROOM: only the public Metal API on OUR OWN compiled shader (archive built by
// shdump from our own MSL, spliced out-of-band). No Apple binary is disassembled.
//
// Kernel signature it drives (matches kernels/rtk.metal):
//   kernel void rtk(primitive_acceleration_structure accel [[buffer(0)]],
//                   device float *out [[buffer(1)]],
//                   device const packed_float3 *org [[buffer(2)]],
//                   device const packed_float3 *dir [[buffer(3)]],
//                   uint i [[thread_position_in_grid]]);
//
// Build (device, CLT): clang -fobjc-arc -framework Metal -framework Foundation -o rtsplice rtsplice.m
// Usage: rtsplice --archive A.bin --source rtk.metal --function rtk
//   Prints STATUS + PIPELINE_SOURCE + one "RAY i ... t=.. prim=.. bary=(..)" line per ray.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <math.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit(const char *s){ printf("STATUS %s\n", s); }
static void die(const char *st,const char *m,NSError*e){ emit(st);
    if(e) printf("ERROR %s: %s\n", m, [[e localizedDescription] UTF8String]);
    else if(m) printf("ERROR %s\n", m);
    fflush(stdout); exit(1); }

int main(int argc,char*argv[]){
@autoreleasepool{
    const char *archivePath=NULL,*sourcePath=NULL,*funcName=NULL;
    BOOL fastMath=YES;
    static const struct option lo[]={
        {"archive",required_argument,0,'a'},{"source",required_argument,0,'s'},
        {"function",required_argument,0,'f'},{"no-fast-math",no_argument,0,'n'},{0,0,0,0}};
    int c; while((c=getopt_long(argc,argv,"a:s:f:n",lo,NULL))>0){
        switch(c){case 'a':archivePath=optarg;break;case 's':sourcePath=optarg;break;
            case 'f':funcName=optarg;break;case 'n':fastMath=NO;break;}}
    if(!archivePath||!sourcePath||!funcName) die("ARG","need --archive --source --function",nil);

    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    if(!dev) die("NODEV","no Metal device",nil);
    printf("DEVICE %s raytracing=%d\n",[[dev name]UTF8String],(int)[dev supportsRaytracing]);
    NSError*err=nil;

    // 1. Compile OUR source -> library -> function (the archive-lookup identity).
    NSString*src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                           encoding:NSUTF8StringEncoding error:&err];
    if(!src) die("COMPILE_FAIL","read source",err);
    MTLCompileOptions*co=[MTLCompileOptions new];[co setFastMathEnabled:fastMath];
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:co error:&err];
    if(!lib) die("COMPILE_FAIL","newLibraryWithSource",err);
    id<MTLFunction> fn=[lib newFunctionWithName:[NSString stringWithUTF8String:funcName]];
    if(!fn) die("FUNCTION_MISSING","newFunctionWithName",nil);

    // 2. Load the (possibly spliced) binary archive.
    MTLBinaryArchiveDescriptor*ad=[MTLBinaryArchiveDescriptor new];
    [ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
    id<MTLBinaryArchive> arch=[dev newBinaryArchiveWithDescriptor:ad error:&err];
    if(!arch) die("ARCHIVE_FAIL","newBinaryArchiveWithDescriptor",err);

    // 3. Build pipeline FORCING the archive's (spliced) machine code.
    MTLComputePipelineDescriptor*pd=[MTLComputePipelineDescriptor new];
    [pd setComputeFunction:fn];[pd setBinaryArchives:@[arch]];
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithDescriptor:pd
        options:MTLPipelineOptionFailOnBinaryArchiveMiss reflection:nil error:&err];
    if(!pso) die("PIPELINE_MISS","FailOnBinaryArchiveMiss",err);
    printf("PIPELINE_SOURCE archive\n");

    id<MTLCommandQueue> q=[dev newCommandQueue];

    // 4. Build a REAL primitive AS: KNOWN triangle v0(-1,-1,3) v1(1,-1,3) v2(0,1,3).
    float verts[9]={-1,-1,3, 1,-1,3, 0,1,3};
    id<MTLBuffer> vbuf=[dev newBufferWithBytes:verts length:sizeof(verts)
                                       options:MTLResourceStorageModeShared];
    MTLAccelerationStructureTriangleGeometryDescriptor*geo=
        [MTLAccelerationStructureTriangleGeometryDescriptor descriptor];
    geo.vertexBuffer=vbuf;geo.vertexBufferOffset=0;geo.vertexStride=sizeof(float)*3;geo.triangleCount=1;
    if([geo respondsToSelector:@selector(setVertexFormat:)]) geo.vertexFormat=MTLAttributeFormatFloat3;
    MTLPrimitiveAccelerationStructureDescriptor*pdesc=
        [MTLPrimitiveAccelerationStructureDescriptor descriptor];
    pdesc.geometryDescriptors=@[geo];
    MTLAccelerationStructureSizes sz=[dev accelerationStructureSizesWithDescriptor:pdesc];
    id<MTLAccelerationStructure> as=[dev newAccelerationStructureWithSize:sz.accelerationStructureSize];
    id<MTLBuffer> scratch=[dev newBufferWithLength:sz.buildScratchBufferSize
                                          options:MTLResourceStorageModePrivate];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLAccelerationStructureCommandEncoder> ae=[cb accelerationStructureCommandEncoder];
    [ae buildAccelerationStructure:as descriptor:pdesc scratchBuffer:scratch scratchBufferOffset:0];
    [ae endEncoding];[cb commit];[cb waitUntilCompleted];
    if(cb.error) die("AS_BUILD","AS build",cb.error);

    // 5. KNOWN rays. #0-4 HIT (dir +z into the tri at z=3); #5 MISSES (points away, -z).
    const int N=6;
    float orgs[18]={ 0,0,0,  0,0,1,  0,0,-2,  0.3f,-0.3f,0.5f,  0,0,2,  0,0,0 };
    float dirs[18]={ 0,0,1,  0,0,1,  0,0,1,  0,0,1,  0,0,1,  0,0,-1 };
    id<MTLBuffer> obuf=[dev newBufferWithLength:N*sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> orgb=[dev newBufferWithBytes:orgs length:sizeof(orgs) options:MTLResourceStorageModeShared];
    id<MTLBuffer> dirb=[dev newBufferWithBytes:dirs length:sizeof(dirs) options:MTLResourceStorageModeShared];
    memset(obuf.contents,0,N*sizeof(float));

    id<MTLCommandBuffer> cb2=[q commandBuffer];
    id<MTLComputeCommandEncoder> ce=[cb2 computeCommandEncoder];
    [ce setComputePipelineState:pso];
    [ce setAccelerationStructure:as atBufferIndex:0];
    [ce setBuffer:obuf offset:0 atIndex:1];
    [ce setBuffer:orgb offset:0 atIndex:2];
    [ce setBuffer:dirb offset:0 atIndex:3];
    [ce useResource:as usage:MTLResourceUsageRead];
    [ce dispatchThreads:MTLSizeMake(N,1,1) threadsPerThreadgroup:MTLSizeMake(N,1,1)];
    [ce endEncoding];[cb2 commit];[cb2 waitUntilCompleted];
    if([cb2 status]==MTLCommandBufferStatusError) die("CMDBUF_ERROR","dispatch",[cb2 error]);
    printf("GPUTIME_NS %llu\n",(unsigned long long)(([cb2 GPUEndTime]-[cb2 GPUStartTime])*1e9));

    float*o=(float*)obuf.contents;
    for(int i=0;i<N;i++)
        printf("RAY %d org=(%.2f,%.2f,%.2f) dir=(%.2f,%.2f,%.2f) -> t=%.4f\n",
               i,orgs[i*3],orgs[i*3+1],orgs[i*3+2],dirs[i*3],dirs[i*3+1],dirs[i*3+2],o[i]);
    emit("OK");fflush(stdout);return 0;
}}
