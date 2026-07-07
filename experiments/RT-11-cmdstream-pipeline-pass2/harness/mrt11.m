// mrt11.m — RT-11 independent MRT feasibility + per-attachment stride probe.
//
// Purpose: independently confirm RT-4's "32 KiB is NOT a fixed-function MRT cap":
// render an 8x rgba32f MRT (128 KiB nominal color storage) and read back a correct
// pixel; capture the tiler geometry heap to confirm per-attachment stride 0x1800 for
// rgba32f (vs 0x1000 bgra8). DIFFERENT program from RT-4 tvar4.m (fresh shader that
// writes a distinct per-attachment constant so attachment-0 readback is unambiguous).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API. Our own MSL compiled at runtime.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o mrt11 mrt11.m
//
// Usage: mrt11 --mrt N --fmt bgra8|rgba32f [--dump]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void pva(const char*l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }
static MTLPixelFormat pf(const char*s,int*bpp){
    if(!strcmp(s,"rgba32f")){*bpp=16;return MTLPixelFormatRGBA32Float;}
    if(!strcmp(s,"rgba16f")){*bpp=8; return MTLPixelFormatRGBA16Float;}
    *bpp=4;return MTLPixelFormatBGRA8Unorm;
}

int main(int argc,char**argv){@autoreleasepool{
    long mrt=8; const char*fmtS="rgba32f"; int doDump=0;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--mrt")&&i+1<argc) mrt=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--fmt")&&i+1<argc) fmtS=argv[++i];
        else if(!strcmp(argv[i],"--dump")) doDump=1;
    }
    if(mrt<1)mrt=1; if(mrt>8)mrt=8;
    int bpp; MTLPixelFormat fmt=pf(fmtS,&bpp);
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name]UTF8String]);
    printf("CONFIG mrt=%ld fmt=%s bpp=%d nominalColorTileBytes=%ld maxTGmem=%lu\n",
           mrt,fmtS,bpp,(long)mrt*1024*bpp,(unsigned long)[dev maxThreadgroupMemoryLength]);

    NSMutableString*fs=[NSMutableString stringWithString:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct V{float4 p [[position]];};\n struct FO{\n"];
    for(long i=0;i<mrt;i++) [fs appendFormat:@"  float4 c%ld [[color(%ld)]];\n",i,i];
    [fs appendString:@"};\nfragment FO fm(V in [[stage_in]]){ FO o;\n"];
    // attachment k = distinct constant: 0.0625*(k+1)
    for(long i=0;i<mrt;i++) [fs appendFormat:@"  o.c%ld = float4(0.0625*%ld,0.5,0.5,1.0);\n",i,i+1];
    [fs appendString:@"  return o; }\n"];
    NSString*vs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V{float4 p [[position]];};\n"
      "vertex V vm(uint vid [[vertex_id]], const device float2* q [[buffer(0)]]){ V o; o.p=float4(q[vid],0,1); return o; }\n";
    NSError*err=nil;
    id<MTLLibrary> vl=[dev newLibraryWithSource:vs options:nil error:&err];
    id<MTLLibrary> fl=[dev newLibraryWithSource:fs options:nil error:&err];
    if(!vl||!fl){printf("SHADER_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"vm"];
    pd.fragmentFunction=[fl newFunctionWithName:@"fm"];
    for(long i=0;i<mrt;i++) pd.colorAttachments[i].pixelFormat=fmt;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

    long W=64,H=64;
    id<MTLTexture> color[8]={0}; id<MTLBuffer> rtb=nil;
    NSUInteger bpr=((W*bpp+255)&~255UL);
    for(long i=0;i<mrt;i++){
        MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt width:W height:H mipmapped:NO];
        td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
        if(i==0){ rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
                  color[0]=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr]; pva("rtBuf0",[rtb gpuAddress]); }
        else color[i]=[dev newTextureWithDescriptor:td];
    }
    id<MTLBuffer> vb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    pva("vtxBuf",[vb gpuAddress]);

    id<MTLCommandQueue> q=[dev newCommandQueue];
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    for(long i=0;i<mrt;i++){
        rp.colorAttachments[i].texture=color[i];
        rp.colorAttachments[i].loadAction=MTLLoadActionClear;
        rp.colorAttachments[i].clearColor=MTLClearColorMake(0,0,0,1);
        rp.colorAttachments[i].storeAction=MTLStoreActionStore;
    }
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLViewport v={0,0,(double)W,(double)H,0,1}; [enc setViewport:v];
    [enc setVertexBuffer:vb offset:0 atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld err=%s\n",(long)[cb status],[cb error]?[[[cb error]localizedDescription]UTF8String]:"none");
    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    // read attachment-0 pixel
    unsigned char px[16]; memset(px,0,sizeof px);
    [color[0] getBytes:px bytesPerRow:bpr fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
    if(fmt==MTLPixelFormatRGBA32Float){ float*f=(float*)px; printf("PIXEL att0 rgba=%.4f,%.4f,%.4f,%.4f\n",f[0],f[1],f[2],f[3]); }
    else printf("PIXEL att0 b0..3=%02x%02x%02x%02x\n",px[0],px[1],px[2],px[3]);
    return 0;
}}
