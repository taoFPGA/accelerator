/* data.js -- hardware facts distilled from architecture_data.json +
   architecture_data_accel.json (dump_arch.tcl) and reports/syn/utilization.rpt.
   Globals consumed by app.js: CRO DEV N EDGES ACC GHOST. */
var CRO = ["X0Y0","X1Y0","X0Y1","X1Y1","X0Y2","X1Y2"];
var DEV = { part:"xc7z020clg400-1", lut:51550, lutT:53200, ff:30872, ffT:106400,
           dsp:220, dspT:220, bram:120, bramT:140,
           clk:"clk_fpga_0", mhz:100.0, ns:10.0,
           clkSrc:"design_1_i/processing_system7_0/inst/PS7_i/FCLKCLK[0]" };

/* SoC graph nodes. bbox = placement.slice_bbox [x0,y0,x1,y1] in SLICE index space
   (device extent ~114 x 150). lane = logical pipeline slot (col, row). */
var N = {
 ps7:  {name:"processing_system7_0", path:"design_1_i/processing_system7_0",
        ref:"Zynq-7000 PS7 (hard)", kind:"hard", reg:0.00,
        lut:0,ff:0,dsp:0,bram:0,srl:0, bbox:[0,0,1,134],
        cr:{X0Y1:60,X0Y2:71}, lane:[0,1],
        note:"ARM Cortex-A9 + DDR3 controller in the PS tile at the die's west edge. Zero fabric cells — it is silicon, not LUTs. Sources the 100 MHz fabric clock on FCLKCLK[0]."},
 periph:{name:"ps7_0_axi_periph", path:"design_1_i/ps7_0_axi_periph",
        ref:"AXI Interconnect · AXI4-Lite", kind:"ctrl", reg:0.237,
        lut:718,ff:640,dsp:0,bram:0,srl:65, bbox:[26,84,48,112],
        cr:{X0Y1:1158,X0Y2:218}, lane:[1,0],
        note:"Fans the PS control bus out to every slave's register space: start pulse, status poll, tile base pointers. 4-bit address — a handful of CSRs."},
 smc0: {name:"axi_smc", path:"design_1_i/axi_smc",
        ref:"AXI SmartConnect", kind:"ctrl", reg:0.540,
        lut:608,ff:368,dsp:0,bram:0,srl:2, bbox:[0,28,54,80],
        cr:{X0Y0:548,X0Y1:436,X1Y1:8}, lane:[2,2],
        note:"Crossbar from DMA-0's read master to a PS high-performance memory port (HP0)."},
 smc1: {name:"axi_smc_1", path:"design_1_i/axi_smc_1",
        ref:"AXI SmartConnect", kind:"ctrl", reg:0.540,
        lut:608,ff:368,dsp:0,bram:0,srl:2, bbox:[0,38,105,87],
        cr:{X0Y0:610,X0Y1:332,X1Y1:50}, lane:[2,3],
        note:"Crossbar from DMA-1's read master to a second PS HP memory port."},
 smc2: {name:"axi_smc_2", path:"design_1_i/axi_smc_2",
        ref:"AXI SmartConnect", kind:"ctrl", reg:0.556,
        lut:778,ff:455,dsp:0,bram:0,srl:8, bbox:[23,49,113,87],
        cr:{X0Y0:12,X0Y1:546,X1Y1:691}, lane:[8,2],
        note:"Result path: DMA-2's write master back to PS DDR."},
 dma0: {name:"axi_dma_0", path:"design_1_i/axi_dma_0",
        ref:"AXI DMA · MM2S", kind:"ctrl", reg:0.719,
        lut:1053,ff:1066,dsp:0,bram:4.5,srl:75, bbox:[0,0,101,105],
        cr:{X0Y0:895,X0Y1:999,X1Y0:148,X1Y1:146}, lane:[3,2],
        note:"Reads operand tiles from DDR and turns them into an AXI4-Stream. One of two input feeds — the activation matrix."},
 dma1: {name:"axi_dma_1", path:"design_1_i/axi_dma_1",
        ref:"AXI DMA · MM2S", kind:"ctrl", reg:0.719,
        lut:1053,ff:1066,dsp:0,bram:4.5,srl:75, bbox:[1,0,53,101],
        cr:{X0Y0:1018,X0Y1:1138,X1Y1:12}, lane:[3,3],
        note:"Second MM2S feed — the weight / second-matrix stream."},
 dma2: {name:"axi_dma_2", path:"design_1_i/axi_dma_2",
        ref:"AXI DMA · S2MM", kind:"ctrl", reg:0.760,
        lut:1565,ff:1800,dsp:0,bram:4.5,srl:114, bbox:[2,12,104,145],
        cr:{X0Y1:732,X0Y2:1359,X1Y1:1339}, lane:[7,2],
        note:"Drains the accelerator's result stream and writes it back to DDR."},
 cv0:  {name:"axis_dwidth_converter_0", path:"design_1_i/axis_dwidth_converter_0",
        ref:"AXI4-Stream width converter", kind:"stream", reg:0.890,
        lut:17,ff:265,dsp:0,bram:0,srl:0, bbox:[85,0,107,32],
        cr:{X1Y0:282}, lane:[4,2],
        note:"Widens the DMA stream up to the accelerator's 384-bit ingress (24 lanes x 16-bit)."},
 cv1:  {name:"axis_dwidth_converter_1", path:"design_1_i/axis_dwidth_converter_1",
        ref:"AXI4-Stream width converter", kind:"stream", reg:0.890,
        lut:17,ff:265,dsp:0,bram:0,srl:0, bbox:[5,1,106,37],
        cr:{X0Y0:203,X1Y0:79}, lane:[4,3],
        note:"Widens the second feed to 384-bit."},
 cv2:  {name:"axis_dwidth_converter_2", path:"design_1_i/axis_dwidth_converter_2",
        ref:"AXI4-Stream width converter", kind:"stream", reg:0.030,
        lut:141,ff:266,dsp:0,bram:0,srl:0, bbox:[35,107,64,135],
        cr:{X0Y2:351,X1Y2:56}, lane:[6,2],
        note:"Narrows the 384-bit result stream back down for the S2MM DMA. Low registered ratio — mostly wires and skid buffers."},
 mm:   {name:"MM_ultra_top_0", path:"design_1_i/MM_ultra_top_0",
        ref:"MM_ultra_axi · systolic MatMul", kind:"compute", reg:0.970, big:true,
        lut:44971,ff:24280,dsp:220,bram:110,srl:613, bbox:[0,0,113,149],
        cr:{X0Y0:10618,X1Y0:20734,X0Y1:4027,X1Y1:16878,X0Y2:6500,X1Y2:18436}, lane:[5,2],
        note:"87% of the fabric and every one of the 220 DSP48E1 slices. Spans all six clock regions; densest in the eastern column. Expands into the systolic view."}
};
var EDGES = [
 ["periph","ps7","ctrl",132,"AXI-Lite resp"],
 ["ps7","periph","ctrl",266,"AXI-Lite req"],
 ["periph","dma0","ctrl",104,"CSR"], ["periph","dma1","ctrl",104,"CSR"],
 ["periph","dma2","ctrl",104,"CSR"], ["periph","mm","ctrl",90,"CSR"],
 ["ps7","smc0","ctrl",138,"HP mem"], ["ps7","smc1","ctrl",138,"HP mem"],
 ["smc0","dma0","ctrl",138,"mem read"], ["smc1","dma1","ctrl",138,"mem read"],
 ["dma2","smc2","ctrl",236,"mem write"], ["smc2","ps7","ctrl",250,"HP mem"],
 ["dma0","cv0","stream",132,"AXIS"], ["dma1","cv1","stream",132,"AXIS"],
 ["cv2","dma2","stream",132,"AXIS"],
 ["cv0","mm","stream",384,"AXIS tdata"], ["cv1","mm","stream",384,"AXIS tdata"],
 ["mm","cv2","stream",384,"AXIS tdata"]
];

/* accelerator internals — scope MM_ultra_axi, conn_depth 4 */
var ACC = {
 inbuf: {name:"u_MM_in_buffer", path:".../u_MM_ultra/u_MM_in_buffer", ref:"MM_in_buffer",
         reg:0.017, lut:406,ff:145,dsp:0,bram:43,srl:0,
         cr:{X0Y0:71,X0Y1:6,X1Y0:398,X1Y1:175},
         note:"Ping-pong operand tile RAM — 43 x RAMB36. Two tiles in flight so the array never waits on DDR latency: fill tile B while the wavefront drains tile A."},
 array: {name:"u_PE_array", path:".../u_MM/u_PE_array", ref:"PE_array · 24 x 24",
         reg:0.213, lut:34225,ff:17773,dsp:220,bram:0,srl:609,
         cr:{X0Y0:7622,X1Y0:15295,X0Y1:2780,X1Y1:11487,X0Y2:3573,X1Y2:12885},
         note:"576 processing elements; 220 hold a DSP48E1 (device-limited), the rest are LUT MACs or idle at the array edge. 609 SRL delay lines skew the systolic wavefront."},
 outbuf:{name:"u_MM_out_buffer", path:".../u_MM_ultra/u_MM_out_buffer", ref:"MM_out_buffer",
         reg:0.290, lut:2453,ff:796,dsp:0,bram:56,srl:0,
         cr:{X0Y1:209,X0Y2:1467,X1Y1:1060,X1Y2:812},
         note:"Partial-sum accumulation and output tile RAM — 56 x RAMB36. Un-skews the diagonal result wavefront back into dense rows for the DMA."},
 rows:24, cols:24, dspTotal:220,
 dspPerLine:[10,9,9,9,9,9,9,9,9,9,10,10,10,9,9,9,9,9,9,9,9,9,9,9]
};

/* transformer extension — NOT in this bitstream. Structure + net names from
   sourcecode/top/transformer_block_top.v; totals from reports/syn/utilization.rpt
   (transformer_block_top, 16-lane, Vivado 2026.1 OOC synth). */
var GHOST = {
  order: ["downsizer","softmax","upsizer","gelu"],
  netIn: "mm_out_data",
  downsizer:{ name:"axis_downsizer", inst:"u_mm_to_softmax_downsizer",
    role:"wide MM beat → serial scalars",
    note:"Unpacks each A_size-wide MM_ultra beat into A_size sequential scalar cycles and forwards a per-row 'last'. Single-buffered — it backpressures MM_ultra for ~A_size cycles per beat, so this bridge (not the array) sets the transformer pipeline's throughput ceiling." },
  softmax:{ name:"Softmax_control", inst:"u_Softmax_control",
    role:"row-wise exp + normalise",
    note:"One scalar in / one normalised scalar out per cycle, with NO output backpressure. Internally: Exp_module (eˣ), AdderS (running row sum), right_shifter (scale_out). Completes the self-attention score path." },
  upsizer:{ name:"axis_upsizer_fifo", inst:"u_softmax_to_gelu_fifo",
    role:"buffer + repack to num_gelu lanes",
    note:"Absorbs Softmax's unconditional output (GELU_FIFO_DEPTH = 512) and repacks it into num_gelu-wide beats with tkeep. Must be ≥ the softmax row length or in_overflow fires and samples drop — there is no flow-control path back into Softmax_control." },
  gelu:{ name:"EightGelus", inst:"u_EightGelus",
    role:"element-wise GELU, num_gelu lanes",
    note:"num_gelu fully-pipelined GELU lanes on the MLP path. Known RTL hazard: valid/last shift registers advance every clock regardless of out_ready (no skid buffer) — a downstream stall silently drops the in-flight beat. Safe only behind a buffered consumer." },
  synth:"transformer_block_top, 16-lane RTL synth (Vivado 2026.1): 10.5k LUT · 8.2k FF · 205 DSP48E1 · 71 RAMB36. Per-module split needs a hierarchical synth run."
};
