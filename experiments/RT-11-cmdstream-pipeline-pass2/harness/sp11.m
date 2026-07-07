// sp11.m — RT-11 independent programmable-sample-positions probe.
//
// Purpose: independently confirm RT-4's correction that custom MSAA sample positions
// are written to a CLIENT BO at +0x40 as N (x,y) f32 pairs on a 1/16 grid — and try
// to FALSIFY the "userspace" claim (is there ANY case where positions route to the
// kernel instead of the client BO?). Uses DIFFERENT custom positions than RT-4.
//   RT-4 4x custom was {0.1,0.1},{0.9,0.3},{0.3,0.9},{0.7,0.7}. Here we use exact
//   1/16-grid values so decode is unambiguous and clearly distinct.
//
// --mode: default (no setSamplePositions) | custom (setSamplePositions) | none (no MSAA)
//
// CLEAN-ROOM: OWN-SHADER + public Metal API. Our own MSL compiled at runtime.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o sp11 sp11.m
//
// Usage: sp11 --samples 2|4 --mode default|custom [--dump]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <objc/message.h>

static void pva(const char*l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

int main(int argc,char**argv){@autoreleasepool{
    long samples=4; const char*mode="custom"; int doDump=0;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--samples")&&i+1<argc) samples=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--mode")&&i+1<argc) mode=argv[++i];
        else if(!strcmp(argv[i],"--dump")) doDump=1;
    }
    int custom=!strcmp(mode,"custom");
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name]UTF8String]);
    BOOL psp=NO;
    if([dev respondsToSelector:@selector(areProgrammableSamplePositionsSupported)])
        psp=((BOOL(*)(id,SEL))objc_msgSend)(dev,@selector(areProgrammableSamplePositionsSupported));
    printf("CONFIG samples=%ld mode=%s progSamplePosSupported=%d\n",samples,mode,(int)psp);

    NSString*vs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V{float4 p [[position]];};\n"
      "vertex V vm(uint vid [[vertex_id]], const device float2* q [[buffer(0)]]){ V o; o.p=float4(q[vid],0,1); return o; }\n";
    NSString*fs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V{float4 p [[position]];};\n"
      "fragment float4 fm(V in [[stage_in]]){ return float4(0.2,0.4,0.6,1.0); }\n";
    NSError*err=nil;
    id<MTLLibrary> vl=[dev newLibraryWithSource:vs options:nil error:&err];
    id<MTLLibrary> fl=[dev newLibraryWithSource:fs options:nil error:&err];
    if(!vl||!fl){printf("SHADER_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"vm"];
    pd.fragmentFunction=[fl newFunctionWithName:@"fm"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    pd.rasterSampleCount=(NSUInteger)samples;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

    long W=64,H=64;
    MTLTextureDescriptor*md=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    md.textureType=MTLTextureType2DMultisample; md.sampleCount=(NSUInteger)samples;
    md.usage=MTLTextureUsageRenderTarget; md.storageMode=MTLStorageModePrivate;
    id<MTLTexture> msaa=[dev newTextureWithDescriptor:md];
    MTLTextureDescriptor*rd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    rd.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; rd.storageMode=MTLStorageModeShared;
    NSUInteger bpr=((W*4+255)&~255UL);
    id<MTLBuffer> resb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    id<MTLTexture> resolve=[resb newTextureWithDescriptor:rd offset:0 bytesPerRow:bpr];
    pva("resBuf",[resb gpuAddress]);

    id<MTLBuffer> vb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    pva("vtxBuf",[vb gpuAddress]);

    // DIFFERENT custom positions than RT-4, all exact multiples of 1/16:
    MTLSamplePosition c2[2]={{0.1875,0.8125},{0.8125,0.1875}};              // 3/16,13/16 | 13/16,3/16
    MTLSamplePosition c4[4]={{0.0625,0.9375},{0.5,0.0625},{0.9375,0.5},{0.25,0.75}};
    printf("CUSTOMPOS ");
    if(samples==2) for(int i=0;i<2;i++) printf("(%.4f,%.4f)",c2[i].x,c2[i].y);
    else           for(int i=0;i<4;i++) printf("(%.4f,%.4f)",c4[i].x,c4[i].y);
    printf("\n");

    id<MTLCommandQueue> q=[dev newCommandQueue];
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=msaa;
    rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
    rp.colorAttachments[0].resolveTexture=resolve;
    rp.colorAttachments[0].storeAction=MTLStoreActionMultisampleResolve;
    if(custom){
        if(samples==2) [rp setSamplePositions:c2 count:2];
        else           [rp setSamplePositions:c4 count:4];
    }
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLViewport v={0,0,(double)W,(double)H,0,1}; [enc setViewport:v];
    [enc setVertexBuffer:vb offset:0 atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    return 0;
}}
