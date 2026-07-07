// texr.m -- EXP-0016 enhanced render testbed (extends tools/agxtest/agxrender.m).
// Forces a (possibly byte-spliced) render pipeline FROM OUR OWN archived machine
// code (MTLPipelineOptionFailOnBinaryArchiveMiss), binds up to TWO distinct input
// textures + TWO samplers, draws a full-screen triangle, and reads pixels back.
//
// Extra vs agxrender.m: a distinct-per-texel GRID texture (so the sampled texel is
// identifiable from the pixel), a second texture at texture(1) and a second sampler
// at sampler(1) with different contents/filtering -- so splicing the texture-slot /
// sampler-slot field of a sample instruction and observing the pixel HW-validates it.
//
// CLEAN-ROOM: public Metal API on OUR OWN compiled shader only. No Apple binary is
// disassembled. Splice-and-reload mirrors the public MIT applegpu hwtestbed.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o texr texr.m
// Usage: texr --archive A.bin --source S.metal --vertex V --fragment F
//             [--width W --height H]
//             [--t0 grid | --t0 R,G,B,A]   (texture(0); default grid)
//             [--t1 R,G,B,A]               (texture(1) solid; default 0,0,180,64)
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit_status(const char *s){ printf("STATUS %s\n", s); }
static void fail(const char *st, const char *msg, NSError *e){
    emit_status(st);
    if(e) printf("ERROR %s: %s\n", msg, [[e localizedDescription] UTF8String]);
    else if(msg) printf("ERROR %s\n", msg);
    fflush(stdout); exit(1);
}

enum { OPT_W=128, OPT_H, OPT_T0, OPT_T1, OPT_NOFM };
static const struct option lo[] = {
    {"archive",required_argument,0,'a'},{"source",required_argument,0,'s'},
    {"vertex",required_argument,0,'v'},{"fragment",required_argument,0,'f'},
    {"width",required_argument,0,OPT_W},{"height",required_argument,0,OPT_H},
    {"t0",required_argument,0,OPT_T0},{"t1",required_argument,0,OPT_T1},
    {"no-fast-math",no_argument,0,OPT_NOFM},{0,0,0,0}
};

int main(int argc, char**argv){
  @autoreleasepool{
    const char *arch=0,*src=0,*vN=0,*fN=0,*t0="grid"; unsigned char t1[4]={0,0,180,64};
    long W=4,H=4; BOOL fm=YES; int c;
    while((c=getopt_long(argc,argv,"a:s:v:f:",lo,0))>0){switch(c){
        case 'a':arch=optarg;break; case 's':src=optarg;break;
        case 'v':vN=optarg;break;  case 'f':fN=optarg;break;
        case OPT_W:W=strtol(optarg,0,0);break; case OPT_H:H=strtol(optarg,0,0);break;
        case OPT_T0:t0=optarg;break;
        case OPT_T1:{int r=0,g=0,b=0,a=255;sscanf(optarg,"%d,%d,%d,%d",&r,&g,&b,&a);
                    t1[0]=r;t1[1]=g;t1[2]=b;t1[3]=a;break;}
        case OPT_NOFM:fm=NO;break; default:return 1; }}
    if(!arch||!src||!vN||!fN) fail("PIPELINE_FAIL","need --archive --source --vertex --fragment",0);

    id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); if(!dev)fail("PIPELINE_FAIL","no device",0);
    printf("DEVICE %s\n",[[dev name]UTF8String]);
    NSError*err=0;
    NSString*S=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:src]
                                          encoding:NSUTF8StringEncoding error:&err];
    if(!S)fail("COMPILE_FAIL","read source",err);
    MTLCompileOptions*co=[MTLCompileOptions new];[co setFastMathEnabled:fm];
    id<MTLLibrary>lib=[dev newLibraryWithSource:S options:co error:&err];
    if(!lib)fail("COMPILE_FAIL","newLibraryWithSource",err);
    id<MTLFunction>vf=[lib newFunctionWithName:[NSString stringWithUTF8String:vN]];
    id<MTLFunction>ff=[lib newFunctionWithName:[NSString stringWithUTF8String:fN]];
    if(!vf||!ff)fail("FUNCTION_MISSING","newFunctionWithName",0);

    MTLBinaryArchiveDescriptor*ad=[MTLBinaryArchiveDescriptor new];
    [ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:arch]]];
    id<MTLBinaryArchive>archive=[dev newBinaryArchiveWithDescriptor:ad error:&err];
    if(!archive)fail("ARCHIVE_FAIL","newBinaryArchive",err);

    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    [pd setVertexFunction:vf];[pd setFragmentFunction:ff];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    [pd setBinaryArchives:@[archive]];
    id<MTLRenderPipelineState>pso=[dev newRenderPipelineStateWithDescriptor:pd
        options:MTLPipelineOptionFailOnBinaryArchiveMiss reflection:nil error:&err];
    if(!pso)fail("PIPELINE_MISS","render pipeline (FailOnBinaryArchiveMiss)",err);
    printf("VERTEX %s\nFRAGMENT %s\nPIPELINE_SOURCE archive\n",vN,fN);

    // render target
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:
        MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
    id<MTLTexture>target=[dev newTextureWithDescriptor:td];

    // texture(0): 4x4 grid with distinct texels, OR solid.  texel(x,y): R=(y*4+x)*16,
    // G=x*64, B=y*64, A=255 -> the sampled R byte identifies which texel was read.
    id<MTLTexture>T0,T1; id<MTLSamplerState>Sm0,Sm1;
    {
        BOOL grid = (strcmp(t0,"grid")==0);
        int TW = grid?4:1, TH = grid?4:1;
        MTLTextureDescriptor*d0=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:
            MTLPixelFormatRGBA8Unorm width:TW height:TH mipmapped:NO];
        d0.usage=MTLTextureUsageShaderRead; d0.storageMode=MTLStorageModeShared;
        T0=[dev newTextureWithDescriptor:d0];
        unsigned char buf[4*4*4];
        if(grid){ for(int y=0;y<4;y++)for(int x=0;x<4;x++){unsigned char*p=buf+(y*4+x)*4;
            p[0]=(y*4+x)*16;p[1]=x*64;p[2]=y*64;p[3]=255;}
            [T0 replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:buf bytesPerRow:16]; }
        else { int r=0,g=0,b=0,a=255;sscanf(t0,"%d,%d,%d,%d",&r,&g,&b,&a);
            buf[0]=r;buf[1]=g;buf[2]=b;buf[3]=a;
            [T0 replaceRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0 withBytes:buf bytesPerRow:4]; }
    }
    { MTLTextureDescriptor*d1=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:
        MTLPixelFormatRGBA8Unorm width:1 height:1 mipmapped:NO];
      d1.usage=MTLTextureUsageShaderRead; d1.storageMode=MTLStorageModeShared;
      T1=[dev newTextureWithDescriptor:d1];
      [T1 replaceRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0 withBytes:t1 bytesPerRow:4]; }
    // sampler(0): nearest clamp.  sampler(1): linear repeat (distinct filtering).
    { MTLSamplerDescriptor*s0=[MTLSamplerDescriptor new]; Sm0=[dev newSamplerStateWithDescriptor:s0];
      MTLSamplerDescriptor*s1=[MTLSamplerDescriptor new];
      s1.minFilter=MTLSamplerMinMagFilterLinear; s1.magFilter=MTLSamplerMinMagFilterLinear;
      s1.sAddressMode=MTLSamplerAddressModeRepeat; s1.tAddressMode=MTLSamplerAddressModeRepeat;
      Sm1=[dev newSamplerStateWithDescriptor:s1]; }

    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;

    id<MTLCommandQueue>q=[dev newCommandQueue]; id<MTLCommandBuffer>cb=[q commandBuffer];
    id<MTLRenderCommandEncoder>en=[cb renderCommandEncoderWithDescriptor:rp];
    [en setRenderPipelineState:pso];
    [en setFragmentTexture:T0 atIndex:0]; [en setFragmentTexture:T1 atIndex:1];
    [en setFragmentSamplerState:Sm0 atIndex:0]; [en setFragmentSamplerState:Sm1 atIndex:1];
    [en drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [en endEncoding]; [cb commit]; [cb waitUntilCompleted];
    if([cb status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","cmdbuf",[cb error]);

    printf("SIZE %ld %ld\n",W,H);
    unsigned char*px=malloc((size_t)W*H*4);
    [target getBytes:px bytesPerRow:(NSUInteger)(W*4)
          fromRegion:MTLRegionMake2D(0,0,(NSUInteger)W,(NSUInteger)H) mipmapLevel:0];
    for(long y=0;y<H;y++)for(long x=0;x<W;x++){unsigned char*p=px+(y*W+x)*4;
        printf("PIXEL %ld %ld bgra=%02x%02x%02x%02x rgba=%.3f,%.3f,%.3f,%.3f\n",
               x,y,p[0],p[1],p[2],p[3],p[2]/255.0,p[1]/255.0,p[0]/255.0,p[3]/255.0);}
    free(px); emit_status("OK"); fflush(stdout); return 0;
  }
}
