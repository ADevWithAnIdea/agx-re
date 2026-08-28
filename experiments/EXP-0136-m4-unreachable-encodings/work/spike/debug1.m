#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <unistd.h>

int main() {
  @autoreleasepool {
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:NO];
    td.usage = MTLTextureUsageShaderRead; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
    uint8_t px[4*4*4]; memset(px,0x40,sizeof(px));
    [tex replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:px bytesPerRow:16];
    MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
    id<MTLSamplerState> smp = [dev newSamplerStateWithDescriptor:sd];
    NSString *msl = @"#include <metal_stdlib>\nusing namespace metal;\nkernel void k(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4* o [[buffer(0)]]) { o[0]=t.sample(s, float2(0.5,0.5), level(0)); }\n";
    NSError *err=nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:msl options:nil error:&err];
    id<MTLFunction> fn = [lib newFunctionWithName:@"k"];
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
    id<MTLBuffer> outBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    fprintf(stderr, "outVA=0x%llx\n", (unsigned long long)[outBuf gpuAddress]);
    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setTexture:tex atIndex:0];
    [enc setSamplerState:smp atIndex:0];
    [enc setBuffer:outBuf offset:0 atIndex:0];
    [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [enc endEncoding];
    fprintf(stderr, "PRE-COMMIT dump\n");
    kill(getpid(), SIGUSR1); usleep(300000);
    [cb commit];
    fprintf(stderr, "POST-COMMIT (pre-schedule-wait) dump\n");
    kill(getpid(), SIGUSR1); usleep(300000);
    [cb waitUntilScheduled];
    fprintf(stderr, "POST-SCHEDULED dump\n");
    kill(getpid(), SIGUSR1); usleep(300000);
    [cb waitUntilCompleted];
    fprintf(stderr, "POST-COMPLETED dump\n");
    kill(getpid(), SIGUSR1); usleep(300000);
    fprintf(stderr, "status=%ld\n", (long)[cb status]);
    float *o = (float*)[outBuf contents];
    fprintf(stderr, "pixel=%f %f %f %f\n", o[0],o[1],o[2],o[3]);
  }
  return 0;
}
