// smp11.m — RT-11 independent USC texture/sampler-array stride probe (GRAPHICS path).
//
// Purpose: independently re-verify RT-2a's correction that samplers occupy a
// 0x20-byte slot in the graphics argument-buffer sampler array (arg buffer
// 0x10000248000): num_samplers = (terminator - samp_ptr)/0x20, NOT /8. Sweep
// 1/2/5/8 samplers with N textures (wider than RT-2a's 1/2/3/4). Distinct samplers
// so none are coalesced. DIFFERENT program from RT-2a uvar.m: this FS samples
// tex[i%T] with smp[i%S] directly (uvar split read()/sample() differently).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API. Our own MSL compiled at runtime.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o smp11 smp11.m
//
// Usage: smp11 --tex T --smp S [--dump]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void pva(const char*l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

int main(int argc,char**argv){@autoreleasepool{
    long T=1,S=1; int doDump=0;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--tex")&&i+1<argc) T=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--smp")&&i+1<argc) S=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--dump")) doDump=1;
    }
    if(T<1)T=1; if(S<1)S=1; if(T>16)T=16; if(S>16)S=16;
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name]UTF8String]);
    printf("CONFIG tex=%ld smp=%ld\n",T,S);

    // FS samples tex[i%T] with smp[i%S] for i in 0..max(T,S)-1 so all T textures
    // and all S samplers are referenced (bound). Distinct structure vs uvar.m.
    NSMutableString*fs=[NSMutableString stringWithString:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct V{float4 p [[position]]; float2 uv;};\n"
       "fragment float4 fm(V in [[stage_in]]"];
    for(long i=0;i<T;i++) [fs appendFormat:@",\n  texture2d<float> t%ld [[texture(%ld)]]",i,i];
    for(long i=0;i<S;i++) [fs appendFormat:@",\n  sampler s%ld [[sampler(%ld)]]",i,i];
    [fs appendString:@") {\n  float4 acc=float4(0);\n"];
    long n=T>S?T:S;
    for(long i=0;i<n;i++) [fs appendFormat:@"  acc += t%ld.sample(s%ld, in.uv);\n", i%T, i%S];
    [fs appendString:@"  return acc; }\n"];

    NSString*vs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V{float4 p [[position]]; float2 uv;};\n"
      "vertex V vm(uint vid [[vertex_id]], const device float2* q [[buffer(0)]]){\n"
      "  V o; o.p=float4(q[vid],0,1); o.uv=q[vid]*0.5+0.5; return o; }\n";

    NSError*err=nil;
    id<MTLLibrary> vl=[dev newLibraryWithSource:vs options:nil error:&err];
    id<MTLLibrary> fl=[dev newLibraryWithSource:fs options:nil error:&err];
    if(!vl||!fl){printf("SHADER_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"vm"];
    pd.fragmentFunction=[fl newFunctionWithName:@"fm"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

    long W=64,H=64;
    MTLTextureDescriptor*rtd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    rtd.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; rtd.storageMode=MTLStorageModeShared;
    NSUInteger bpr=((W*4+255)&~255UL);
    id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    id<MTLTexture> target=[rtb newTextureWithDescriptor:rtd offset:0 bytesPerRow:bpr];
    pva("rtBuf",[rtb gpuAddress]);

    NSMutableArray*texs=[NSMutableArray array];
    for(long i=0;i<T;i++){
        MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float width:4 height:4 mipmapped:NO];
        td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
        id<MTLTexture> tx=[dev newTextureWithDescriptor:td];
        float px[16]; for(int k=0;k<16;k++) px[k]=(float)(i+1)*0.01f;
        [tx replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:px bytesPerRow:16];
        [texs addObject:tx];
    }
    // S DISTINCT samplers (vary filter + address + lod so none coalesce)
    NSMutableArray*smps=[NSMutableArray array];
    for(long i=0;i<S;i++){
        MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];
        sd.minFilter = (i&1)?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
        sd.magFilter = (i&2)?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
        sd.sAddressMode = (MTLSamplerAddressMode)(i%4);
        sd.tAddressMode = (MTLSamplerAddressMode)((i+1)%4);
        sd.lodMinClamp = (float)i*0.25f;
        sd.maxAnisotropy = (i%3)+1;
        [smps addObject:[dev newSamplerStateWithDescriptor:sd]];
    }

    id<MTLBuffer> vb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    pva("vtxBuf",[vb gpuAddress]);

    id<MTLCommandQueue> q=[dev newCommandQueue];
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target;
    rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLViewport v={0,0,(double)W,(double)H,0,1}; [enc setViewport:v];
    [enc setVertexBuffer:vb offset:0 atIndex:0];
    for(long i=0;i<T;i++) [enc setFragmentTexture:texs[i] atIndex:i];
    for(long i=0;i<S;i++) [enc setFragmentSamplerState:smps[i] atIndex:i];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    return 0;
}}
