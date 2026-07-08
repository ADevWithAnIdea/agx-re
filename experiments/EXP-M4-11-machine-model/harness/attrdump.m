// attrdump.m — EXP-0031 stage_in vertex-attribute harness (OWN-SHADER).
// Compiles OUR OWN VS+FS that read [[stage_in]] attributes through a real
// MTLVertexDescriptor, validates the render pipeline, and serializes it into an
// MTLBinaryArchive so agxparse can extract the vertex/fragment AGX bytes.
// Purpose: see how the VS pulls [[stage_in]] attributes (in-shader fetch vs
// driver-preloaded) and whether attribute FORMAT/OFFSET/STRIDE changes the code.
//
// CLEAN-ROOM: only the public Metal API on OUR OWN MSL. No Apple binary is
// disassembled. This is our own harness (mirrors shdump's render path + a vertex
// descriptor).
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o attrdump attrdump.m
// Usage: attrdump -o out.bin --source S.metal [--vertex v_main] [--fragment f_main]
//        [--fmt0 N --off0 N --fmt1 N --off1 N --stride N --nattr K]
//   fmt codes = MTLVertexFormat raw enum (e.g. 30=float2,31=float3,28=float4,
//               45=uchar4Normalized, 4=uchar4, 22=short2, 38=uint, 34=int...)
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void die(const char *m, NSError *e){
    fprintf(stderr,"attrdump: %s%s%s\n", m, e?": ":"",
            e?[[e localizedDescription] UTF8String]:"");
    exit(1);
}
enum { O_SRC=128,O_VTX,O_FRAG,O_FMT0,O_OFF0,O_FMT1,O_OFF1,O_STRIDE,O_NATTR,O_STEP };
static const struct option L[]={
    {"source",required_argument,0,O_SRC},{"vertex",required_argument,0,O_VTX},
    {"fragment",required_argument,0,O_FRAG},{"fmt0",required_argument,0,O_FMT0},
    {"off0",required_argument,0,O_OFF0},{"fmt1",required_argument,0,O_FMT1},
    {"off1",required_argument,0,O_OFF1},{"stride",required_argument,0,O_STRIDE},
    {"nattr",required_argument,0,O_NATTR},{"step",required_argument,0,O_STEP},{0,0,0,0}};

int main(int argc,char**argv){@autoreleasepool{
    const char*out=0,*srcp=0,*vn="v_main",*fn="f_main";
    unsigned fmt0=31,off0=0,fmt1=28,off1=16,stride=32,nattr=2,step=0; // float3@0, float4@16
    int c; while((c=getopt_long(argc,argv,"o:",L,0))>0){switch(c){
        case 'o':out=optarg;break; case O_SRC:srcp=optarg;break;
        case O_VTX:vn=optarg;break; case O_FRAG:fn=optarg;break;
        case O_FMT0:fmt0=atoi(optarg);break; case O_OFF0:off0=atoi(optarg);break;
        case O_FMT1:fmt1=atoi(optarg);break; case O_OFF1:off1=atoi(optarg);break;
        case O_STRIDE:stride=atoi(optarg);break; case O_NATTR:nattr=atoi(optarg);break;
        case O_STEP:step=atoi(optarg);break;
    }}
    if(!out||!srcp) die("need -o and --source",0);
    NSError*err=0;
    id<MTLDevice>dev=MTLCreateSystemDefaultDevice(); if(!dev)die("no device",0);
    NSString*src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp]
                 encoding:NSUTF8StringEncoding error:&err]; if(!src)die("read src",err);
    MTLCompileOptions*co=[MTLCompileOptions new];
    id<MTLLibrary>lib=[dev newLibraryWithSource:src options:co error:&err]; if(!lib)die("compile",err);
    id<MTLFunction>vf=[lib newFunctionWithName:[NSString stringWithUTF8String:vn]];
    id<MTLFunction>ff=[lib newFunctionWithName:[NSString stringWithUTF8String:fn]];
    if(!vf||!ff)die("function missing",0);

    MTLVertexDescriptor*vd=[MTLVertexDescriptor new];
    vd.attributes[0].format=(MTLVertexFormat)fmt0; vd.attributes[0].offset=off0; vd.attributes[0].bufferIndex=0;
    if(nattr>=2){ vd.attributes[1].format=(MTLVertexFormat)fmt1; vd.attributes[1].offset=off1; vd.attributes[1].bufferIndex=0; }
    vd.layouts[0].stride=stride;
    vd.layouts[0].stepFunction= step? MTLVertexStepFunctionPerInstance : MTLVertexStepFunctionPerVertex;
    vd.layouts[0].stepRate=1;

    MTLRenderPipelineDescriptor*rd=[MTLRenderPipelineDescriptor new];
    rd.vertexFunction=vf; rd.fragmentFunction=ff; rd.vertexDescriptor=vd;
    rd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState>pso=[dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if(!pso)die("pipeline",err);
    fprintf(stderr,"attrdump: pipeline OK fmt0=%u off0=%u fmt1=%u off1=%u stride=%u nattr=%u step=%u\n",
            fmt0,off0,fmt1,off1,stride,nattr,step);

    MTLBinaryArchiveDescriptor*ad=[MTLBinaryArchiveDescriptor new];
    id<MTLBinaryArchive>arc=[dev newBinaryArchiveWithDescriptor:ad error:&err]; if(!arc)die("archive",err);
    if(![arc addRenderPipelineFunctionsWithDescriptor:rd error:&err])die("addRenderPipeline",err);
    if(![arc serializeToURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:out]] error:&err])die("serialize",err);
    fprintf(stderr,"attrdump: wrote %s\n",out);
    return 0;
}}
