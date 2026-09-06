/* data.js -- hardware facts distilled from architecture_data.json +
   architecture_data_accel.json (dump_arch.tcl over scripts/soc_build/post_route.dcp,
   the routed checkpoint that matches exports/design.bit -- full transformer,
   A_size = 16, Vivado 2025.2). Globals consumed by app.js: CRO DEV N EDGES ACC GHOST. */
var CRO = ["X0Y0","X1Y0","X0Y1","X1Y1","X0Y2","X1Y2"];
var DEV = { part:"xc7z020clg400-1", lut:19919, lutT:53200, ff:14831, ffT:106400,
           dsp:205, dspT:220, bram:83, bramT:140,
           clk:"clk_fpga_0", mhz:100.0, ns:10.0,
           clkSrc:"design_1_i/processing_system7_0/inst/PS7_i/FCLKCLK[0]" };

/* SoC graph nodes. bbox = placement.slice_bbox [x0,y0,x1,y1] in SLICE index space
   (device extent ~114 x 150). lane = logical pipeline slot [column, track]. */
var N = {
 ps7:  {name:"processing_system7_0", path:"design_1_i/processing_system7_0",
        ref:"Zynq-7000 PS7 (hard)", kind:"hard", reg:0.00,
        lut:0,ff:0,dsp:0,bram:0,srl:0, bbox:[0,0,1,134],
        cr:{X0Y1:60,X0Y2:71}, lane:[0,1],
        note:"ARM Cortex-A9 + DDR3 controller in the PS tile at the die's west edge. Zero fabric cells. Sources the 100 MHz fabric clock on FCLKCLK[0]."},
 periph:{name:"ps7_0_axi_periph", path:"design_1_i/ps7_0_axi_periph",
        ref:"AXI Interconnect · AXI4-Lite", kind:"ctrl", reg:0.40,
        lut:718,ff:640,dsp:0,bram:0,srl:65, bbox:[26,83,51,104],
        cr:{X0Y1:1143,X1Y1:9,X0Y2:224}, lane:[1,0],
        note:"Fans the PS control bus out to every slave's register space: start pulse, status poll, tile base pointers."},
 smc0: {name:"axi_smc", path:"design_1_i/axi_smc",
        ref:"AXI SmartConnect", kind:"ctrl", reg:0.540,
        lut:608,ff:368,dsp:0,bram:0,srl:2, bbox:[0,36,26,55],
        cr:{X0Y0:947,X0Y1:45}, lane:[2,2],
        note:"Crossbar from DMA-0's read master to a PS high-performance memory port (HP0)."},
 smc1: {name:"axi_smc_1", path:"design_1_i/axi_smc_1",
        ref:"AXI SmartConnect", kind:"ctrl", reg:0.540,
        lut:608,ff:368,dsp:0,bram:0,srl:2, bbox:[26,45,47,70],
        cr:{X0Y0:50,X0Y1:942}, lane:[2,3],
        note:"Crossbar from DMA-1's read master to a second PS HP memory port."},
 smc2: {name:"axi_smc_2", path:"design_1_i/axi_smc_2",
        ref:"AXI SmartConnect", kind:"ctrl", reg:0.556,
        lut:778,ff:455,dsp:0,bram:0,srl:8, bbox:[26,62,61,100],
        cr:{X0Y1:939,X1Y1:305,X1Y2:5}, lane:[8,2],
        note:"Result path: DMA-2's write master back to PS DDR."},
 dma0: {name:"axi_dma_0", path:"design_1_i/axi_dma_0",
        ref:"AXI DMA · MM2S", kind:"ctrl", reg:0.283,
        lut:1054,ff:1066,dsp:0,bram:4.5,srl:75, bbox:[1,0,48,90],
        cr:{X0Y0:1818,X0Y1:373,X1Y0:3}, lane:[3,2],
        note:"Reads operand tiles from DDR and turns them into a 128-bit AXI4-Stream (16 lanes x 8-bit). One of two input feeds."},
 dma1: {name:"axi_dma_1", path:"design_1_i/axi_dma_1",
        ref:"AXI DMA · MM2S", kind:"ctrl", reg:0.283,
        lut:1054,ff:1066,dsp:0,bram:4.5,srl:75, bbox:[2,10,45,92],
        cr:{X0Y0:983,X0Y1:1206,X1Y1:5}, lane:[3,3],
        note:"Second MM2S feed -- the weight / second-matrix stream."},
 dma2: {name:"axi_dma_2", path:"design_1_i/axi_dma_2",
        ref:"AXI DMA · S2MM", kind:"ctrl", reg:0.301,
        lut:1609,ff:1831,dsp:0,bram:4.5,srl:114, bbox:[3,6,64,92],
        cr:{X0Y0:1655,X0Y1:806,X1Y0:216,X1Y1:847}, lane:[7,2],
        note:"Drains the accelerator's 32-bit GELU output stream and writes it back to DDR."},
 cv0:  {name:"axis_dwidth_converter_0", path:"design_1_i/axis_dwidth_converter_0",
        ref:"AXI4-Stream width converter", kind:"stream", reg:1.00,
        lut:14,ff:200,dsp:0,bram:0,srl:0, bbox:[32,10,56,20],
        cr:{X0Y0:91,X1Y0:123}, lane:[4,2],
        note:"Matches the DMA stream to the accelerator's 128-bit ingress. Fully registered."},
 cv1:  {name:"axis_dwidth_converter_1", path:"design_1_i/axis_dwidth_converter_1",
        ref:"AXI4-Stream width converter", kind:"stream", reg:1.00,
        lut:14,ff:200,dsp:0,bram:0,srl:0, bbox:[22,21,55,32],
        cr:{X0Y0:179,X1Y0:35}, lane:[4,3],
        note:"Width match for the second feed."},
 cv2:  {name:"axis_dwidth_converter_2", path:"design_1_i/axis_dwidth_converter_2",
        ref:"AXI4-Stream width converter", kind:"stream", reg:1.00,
        lut:15,ff:116,dsp:0,bram:0,srl:0, bbox:[27,28,55,41],
        cr:{X0Y0:87,X1Y0:44}, lane:[6,2],
        note:"Matches the 32-bit GELU result stream to the S2MM DMA word."},
 mm:   {name:"transformer_block_axi_top_0", path:"design_1_i/transformer_block_axi_top_0",
        ref:"transformer_block_axi · MatMul + Softmax + GELU", kind:"compute", reg:0.245, big:true,
        lut:13330,ff:8488,dsp:205,bram:73,srl:478, bbox:[0,0,108,133],
        cr:{X0Y0:3014,X1Y0:5983,X0Y1:2042,X1Y1:10241,X0Y2:654,X1Y2:1829}, lane:[5,2],
        note:"The whole accelerator: a 16x16 systolic MatMul feeding LayerNorm, Softmax and GELU as one streaming pipeline. 205 of the device's 220 DSP48E1. Spans all six clock regions, densest in X1Y1. Expands into the systolic + pipeline views."}
};
var EDGES = [
 ["periph","ps7","ctrl",132,"AXI-Lite resp"],
 ["ps7","periph","ctrl",266,"AXI-Lite req"],
 ["periph","dma0","ctrl",104,"CSR"], ["periph","dma1","ctrl",104,"CSR"],
 ["periph","dma2","ctrl",104,"CSR"], ["periph","mm","ctrl",90,"CSR"],
 ["ps7","smc0","ctrl",138,"HP mem"], ["ps7","smc1","ctrl",138,"HP mem"],
 ["smc0","dma0","ctrl",138,"mem read"], ["smc1","dma1","ctrl",138,"mem read"],
 ["dma2","smc2","ctrl",236,"mem write"], ["smc2","ps7","ctrl",250,"HP mem"],
 ["dma0","cv0","stream",128,"AXIS"], ["dma1","cv1","stream",128,"AXIS"],
 ["cv2","dma2","stream",32,"AXIS"],
 ["cv0","mm","stream",128,"s0_axis_tdata"], ["cv1","mm","stream",128,"s1_axis_tdata"],
 ["mm","cv2","stream",32,"m0_axis_tdata"]
];

/* MM_ultra internals (scope transformer_block_axi_top_0, conn_depth 4).
   The systolic detail view (gArray) renders rows x cols; only the first
   12 PE rows hold a DSP48E1 -- the last 4 fall back to LUT MACs. */
var ACC = {
 inbuf: {name:"u_MM_in_buffer", path:".../u_MM_ultra/u_MM_in_buffer", ref:"MM_in_buffer",
         reg:0.02, lut:198,ff:128,dsp:2,bram:29,srl:0,
         cr:{X0Y0:120,X1Y0:270,X1Y1:9,X1Y2:3},
         note:"Operand tile RAM -- 29 x RAMB36. Ping-pong: the array drains tile A while a DMA fills tile B, so the systolic wavefront never waits on DDR latency."},
 array: {name:"u_PE_array", path:".../u_MM/u_PE_array", ref:"PE_array · 16 x 16",
         reg:0.21, lut:7673,ff:4208,dsp:192,bram:0,srl:348,
         cr:{X0Y0:1007,X1Y0:4204,X0Y1:1019,X1Y1:6485,X0Y2:125,X1Y2:321},
         note:"256 processing elements. 192 hold a DSP48E1 (the first 12 rows); the last 4 rows are LUT MACs -- the design is one DSP column short of a full array. 348 SRL delay lines skew the wavefront."},
 outbuf:{name:"u_MM_out_buffer", path:".../u_MM_ultra/u_MM_out_buffer", ref:"MM_out_buffer",
         reg:0.29, lut:1748,ff:537,dsp:3,bram:37.5,srl:0,
         cr:{X0Y0:200,X0Y1:91,X1Y0:200,X1Y1:1974},
         note:"Partial-sum accumulation + output tile RAM -- 37.5 RAMB36 equivalent. Un-skews the diagonal result wavefront back into dense rows for the LayerNorm / Softmax stage."},
 rows:16, cols:16, dspTotal:192,
 dspPerLine:[16,16,16,16,16,16,16,16,16,16,16,16,0,0,0,0]
};

/* Post-MatMul pipeline stages -- all placed & routed in this bitstream.
   Structure + net names from sourcecode/top/transformer_block_top.v.
   Rendered as GHOST group in app.js (kept the name; no longer ghosted). */
var GHOST = {
  order: ["downsizer","softmax","upsizer","gelu"],
  netIn: "mm_out_data",
  downsizer:{ name:"axis_downsizer", inst:"u_mm_to_softmax_downsizer", kind:"stream",
    lut:133, ff:134, dsp:0, bram:0, reg:0.75, bbox:[54,53,84,103],
    cr:{X1Y1:249,X1Y2:18},
    role:"wide MM beat -> serial scalars",
    note:"Unpacks each 128-bit MM_ultra beat into 16 sequential scalar cycles and forwards a per-row 'last'. Single-buffered -- it backpressures MM_ultra for ~16 cycles per beat, so this bridge (not the array) sets the transformer pipeline's throughput ceiling." },
  softmax:{ name:"Softmax_control", inst:"u_Softmax_control", kind:"compute",
    lut:630, ff:195, dsp:4, bram:0.5, reg:0.38, bbox:[0,11,91,127],
    cr:{X0Y0:357,X0Y1:6,X0Y2:8,X1Y1:212,X1Y2:336},
    role:"row-wise exp + normalise",
    note:"One scalar in / one normalised scalar out per cycle, with NO output backpressure. Internally: Exp_module (e^x), AdderS (running row sum), right_shifter (scale_out). Completes the self-attention score path." },
  upsizer:{ name:"axis_upsizer_fifo", inst:"u_softmax_to_gelu_fifo", kind:"stream",
    lut:198, ff:66, dsp:0, bram:0, reg:0.95, bbox:[44,84,64,117],
    cr:{X0Y2:23,X1Y1:2,X1Y2:251},
    role:"buffer + repack to num_gelu lanes",
    note:"Absorbs Softmax's unconditional output (GELU_FIFO_DEPTH = 512) and repacks it into 4-wide beats with tkeep. Must be >= the softmax row length or in_overflow fires and samples drop -- there is no flow-control path back into Softmax_control." },
  gelu:{ name:"EightGelus", inst:"u_EightGelus", kind:"compute",
    lut:1444, ff:438, dsp:4, bram:0, reg:0.19, bbox:[0,6,65,126],
    cr:{X0Y0:499,X0Y1:518,X0Y2:351,X1Y1:42,X1Y2:608},
    role:"element-wise GELU, 4 lanes",
    note:"4 fully-pipelined GELU lanes (num_gelu = 4) on the MLP path. Known RTL hazard: valid/last shift registers advance every clock regardless of out_ready (no skid buffer) -- a downstream stall silently drops the in-flight beat. Safe only behind a buffered consumer." },
  ctx:"Whole accelerator (transformer_block_axi_top): 13.3k LUT · 8.5k FF · 205 DSP48E1 · 73 RAMB36, one 100 MHz domain, zero CDC."
};
