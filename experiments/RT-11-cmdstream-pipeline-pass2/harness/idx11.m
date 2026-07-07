// idx11.m — RT-11 independent DRAW-record probe (DIFFERENT program from RT-2a dvar.m).
//
// Purpose: independently re-verify the *indexed* VDM draw-record shift documented by
// RT-2a (instanceCount@+0x78, u32 opcode 0x61f4, idxVA@+0x70, indexCount@+0x74,
// baseVertex@+0x7c, cut-index@+0x68) and the non-indexed layout (prim@+0x65,
// vertexCount@+0x68, instanceCount@+0x6c). Fresh shaders/values, full base-vertex /
// base-instance / vertexStart coverage via the *full* draw entrypoints.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API. Our own MSL, compiled at runtime; we
// print our own resource GPU VAs for correlation. No Apple binary is inspected.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o idx11 idx11.m
//
// Usage: idx11 [--indexed] [--itype u16|u32] [--prim tri|strip|line|point]
//              [--icount N] [--vcount N] [--inst N] [--start N]
//              [--basevert N] [--baseinst N] [--idxoff N] [--dump]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void pva(const char *l, uint64_t va){
    unsigned char b[8]; for(int i=0;i<8;i++) b[i]=(va>>(8*i))&0xff;
    printf("VA %-10s = 0x%016llx le=",l,(unsigned long long)va);
    for(int i=0;i<8;i++) printf("%02x",b[i]); printf("\n");
}
static MTLPrimitiveType parse_prim(const char*s){
    if(!strcmp(s,"point"))return MTLPrimitiveTypePoint;
    if(!strcmp(s,"line")) return MTLPrimitiveTypeLine;
    if(!strcmp(s,"strip"))return MTLPrimitiveTypeTriangleStrip;
    return MTLPrimitiveTypeTriangle;
}

int main(int argc,char**argv){@autoreleasepool{
    long icount=6,vcount=6,inst=1,start=0,basevert=0,baseinst=0,idxoff=0;
    const char *primS="tri",*itypeS="u16"; int indexed=0,doDump=0;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--indexed")) indexed=1;
        else if(!strcmp(argv[i],"--itype")&&i+1<argc) itypeS=argv[++i];
        else if(!strcmp(argv[i],"--prim")&&i+1<argc) primS=argv[++i];
        else if(!strcmp(argv[i],"--icount")&&i+1<argc) icount=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--vcount")&&i+1<argc) vcount=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--inst")&&i+1<argc) inst=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--start")&&i+1<argc) start=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--basevert")&&i+1<argc) basevert=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--baseinst")&&i+1<argc) baseinst=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--idxoff")&&i+1<argc) idxoff=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--dump")) doDump=1;
    }
    int u32=!strcmp(itypeS,"u32");
    MTLPrimitiveType prim=parse_prim(primS);

    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name]UTF8String]);
    printf("CONFIG indexed=%d itype=%s prim=%s icount=%ld vcount=%ld inst=%ld start=%ld basevert=%ld baseinst=%ld idxoff=%ld\n",
           indexed,itypeS,primS,icount,vcount,inst,start,basevert,baseinst,idxoff);

    // fresh shaders (distinct from dvar.m): pos from buffer(0), flat magenta-ish color
    NSString *vs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V{float4 p [[position]]; float4 c;};\n"
      "vertex V vm(uint vid [[vertex_id]], uint iid [[instance_id]], const device float2* q [[buffer(0)]]){\n"
      "  V o; o.p=float4(q[vid],0,1); o.c=float4(0.9,0.1,0.6,1.0); return o; }\n";
    NSString *fs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V{float4 p [[position]]; float4 c;};\n"
      "fragment float4 fm(V in [[stage_in]]){ return in.c; }\n";
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
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
    NSUInteger bpr=((W*4+255)&~255UL);
    id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
    pva("rtBuf",[rtb gpuAddress]);

    // vertex buffer: enough verts for a full-screen tri plus padding
    long nv = vcount+basevert+16; if(nv<16) nv=16;
    id<MTLBuffer> vb=[dev newBufferWithLength:(NSUInteger)(nv*8) options:MTLResourceStorageModeShared];
    float*vp=(float*)[vb contents];
    for(long i=0;i<nv;i++){ vp[2*i]=-1.0f; vp[2*i+1]=-1.0f; }
    vp[0]=-1;vp[1]=-1; vp[2]=3;vp[3]=-1; vp[4]=-1;vp[5]=3;   // fs-tri in first 3
    pva("vtxBuf",[vb gpuAddress]);

    // index buffer (u16 or u32) with a distinct offset region
    id<MTLBuffer> ib=nil; long nidx=icount+idxoff+8;
    if(indexed){
        NSUInteger es = u32?4:2;
        ib=[dev newBufferWithLength:(NSUInteger)(nidx*es) options:MTLResourceStorageModeShared];
        if(u32){ uint32_t*ip=(uint32_t*)[ib contents]; for(long i=0;i<nidx;i++) ip[i]=(uint32_t)(i%3); }
        else   { uint16_t*ip=(uint16_t*)[ib contents]; for(long i=0;i<nidx;i++) ip[i]=(uint16_t)(i%3); }
        pva("idxBuf",[ib gpuAddress]);
    }

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
    if(indexed){
        [enc drawIndexedPrimitives:prim indexCount:(NSUInteger)icount
             indexType:(u32?MTLIndexTypeUInt32:MTLIndexTypeUInt16)
             indexBuffer:ib indexBufferOffset:(NSUInteger)(idxoff*(u32?4:2))
             instanceCount:(NSUInteger)inst baseVertex:(NSInteger)basevert
             baseInstance:(NSUInteger)baseinst];
    } else {
        [enc drawPrimitives:prim vertexStart:(NSUInteger)start vertexCount:(NSUInteger)vcount
             instanceCount:(NSUInteger)inst baseInstance:(NSUInteger)baseinst];
    }
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    return 0;
}}
