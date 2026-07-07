// shdump_tess.m — EXP-O2H OWN-SHADER compile+serialize for a TESSELLATION render pipeline.
//
// Builds an MTLRenderPipelineDescriptor with a POST-TESSELLATION vertex function
// ([[patch(...)]]) + tessellation state + fragment, and serializes it into an
// MTLBinaryArchive so our own parser (agxparse) can isolate the raw AGX bytes of
// the post-tessellation vertex stage and the fragment stage. This lets us ask
// whether the post-tess VS uses any NOVEL opcode (like mesh's 0x43 / matrix 0xcf /
// rt 0xea) or is an ordinary vertex shader that just loads domain coords.
//
// CLEAN-ROOM: public Metal API on OUR OWN source only. Never disassembles any Apple binary.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o shdump_tess shdump_tess.m
// Usage: ./shdump_tess -o out.bin --patch tri|quad src.metal
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <simd/simd.h>

static void die(const char *m, NSError *e){
    if(e) fprintf(stderr,"shdump_tess: %s: %s\n",m,[[e localizedDescription] UTF8String]);
    else  fprintf(stderr,"shdump_tess: %s\n",m);
    exit(1);
}
enum { OPT_PATCH=128 };
static const struct option L[]={{"output",required_argument,0,'o'},{"patch",required_argument,0,OPT_PATCH},{0,0,0,0}};

int main(int argc,char**argv){
  @autoreleasepool{
    const char *out=NULL,*patch="tri"; int c;
    while((c=getopt_long(argc,argv,"o:",L,NULL))>0){ switch(c){
        case 'o': out=optarg; break; case OPT_PATCH: patch=optarg; break; default: return 1; } }
    if(!out||optind>=argc) die("usage: -o out.bin --patch tri|quad src.metal",nil);
    int isQuad=!strcmp(patch,"quad");

    NSError *err=nil;
    NSString *src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[optind]]
                                            encoding:NSUTF8StringEncoding error:&err];
    if(!src) die("read source",err);
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); if(!dev) die("no device",nil);
    fprintf(stderr,"shdump_tess: device=%s\n",[[dev name] UTF8String]);
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err]; if(!lib) die("compile",err);
    id<MTLFunction> vfn=[lib newFunctionWithName:isQuad?@"tess_vertex_quad":@"tess_vertex_tri"];
    id<MTLFunction> ffn=[lib newFunctionWithName:@"tess_frag"];
    if(!vfn||!ffn) die("function missing",nil);

    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=vfn; pd.fragmentFunction=ffn;
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    pd.maxTessellationFactor=16;
    pd.tessellationFactorFormat=MTLTessellationFactorFormatHalf;
    pd.tessellationControlPointIndexType=MTLTessellationControlPointIndexTypeNone;
    pd.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionConstant;
    pd.tessellationOutputWindingOrder=MTLWindingClockwise;
    pd.tessellationPartitionMode=MTLTessellationPartitionModeInteger;
    MTLVertexDescriptor *vd=[MTLVertexDescriptor new];
    vd.attributes[0].format=MTLVertexFormatFloat4; vd.attributes[0].offset=0; vd.attributes[0].bufferIndex=0;
    vd.layouts[0].stride=sizeof(simd_float4); vd.layouts[0].stepFunction=MTLVertexStepFunctionPerPatchControlPoint;
    pd.vertexDescriptor=vd;

    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso) die("tessellation pipeline creation",err);
    fprintf(stderr,"shdump_tess: pipeline OK (patch=%s)\n",patch);

    MTLBinaryArchiveDescriptor *ad=[MTLBinaryArchiveDescriptor new];
    id<MTLBinaryArchive> arc=[dev newBinaryArchiveWithDescriptor:ad error:&err]; if(!arc) die("archive",err);
    if(![arc addRenderPipelineFunctionsWithDescriptor:pd error:&err]) die("addRenderPipelineFunctions",err);
    NSURL *url=[NSURL fileURLWithPath:[NSString stringWithUTF8String:out]];
    if(![arc serializeToURL:url error:&err]) die("serializeToURL",err);
    fprintf(stderr,"shdump_tess: wrote %s\n",out);
    return 0;
  }
}
